"""Read-only preflight for pinned public benchmark sources and scorers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Final, Iterable, Literal

from study_anything.cbb.benchmark.adapters import (
    PILOT_SUITE_ID,
    SOURCE_DEFINITIONS,
    benchmark_privacy,
)
from study_anything.cbb.benchmark.agentdojo_smoke import BRIDGE_SCRIPT
from study_anything.cbb.benchmark.fixtures import pilot_seeds
from study_anything.cbb.benchmark.models import (
    BenchmarkSource,
    SourcePreflightCheckV1,
    SourcePreflightReceiptV1,
)
from study_anything.cbb.benchmark.swe_smoke import (
    ADAPTER_VERSION as SWE_ADAPTER_VERSION,
    SweScorerError,
    load_swe_task_snapshot,
)
from study_anything.cbb.benchmark.tau_smoke import BRIDGE_SCRIPT as TAU_BRIDGE_SCRIPT
from study_anything.cbb.benchmark.tua_smoke import ADAPTER_VERSION as TUA_ADAPTER_VERSION
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)


CHECKOUT_NAMES: Final = {
    BenchmarkSource.SWE_BENCH_LIVE: "swe-bench-live",
    BenchmarkSource.TUA_BENCH: "tua-bench",
    BenchmarkSource.TAU_BENCH: "tau-bench",
    BenchmarkSource.AGENTDOJO: "agentdojo",
}
SCORER_PATHS: Final = {
    BenchmarkSource.SWE_BENCH_LIVE: ("evaluation/evaluation.py",),
    BenchmarkSource.TUA_BENCH: tuple(
        f"tasks/{seed.task_id}/tests" for seed in pilot_seeds()[BenchmarkSource.TUA_BENCH]
    ),
    BenchmarkSource.TAU_BENCH: ("src/tau2/evaluator/evaluator.py",),
    BenchmarkSource.AGENTDOJO: ("src/agentdojo/benchmark.py",),
}
DOCKER_REQUIRED: Final = {
    BenchmarkSource.SWE_BENCH_LIVE,
    BenchmarkSource.TUA_BENCH,
}
SCORER_RUNTIME_IMPORTS: Final = {
    BenchmarkSource.TUA_BENCH: "harbor",
    BenchmarkSource.TAU_BENCH: "tau2",
    BenchmarkSource.AGENTDOJO: "agentdojo",
}


class SourcePreflightError(RuntimeError):
    """Raised when a live source preflight cannot produce a safe receipt."""


def _command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 20,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _git_revision(checkout: Path | None) -> str | None:
    if checkout is None or not (checkout / ".git").exists():
        return None
    result = _command(["git", "rev-parse", "HEAD"], cwd=checkout)
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and len(revision) == 40 else None


def _git_objects_digest(checkout: Path, refs: Iterable[str]) -> str | None:
    objects: list[dict[str, str]] = []
    for ref in refs:
        result = _command(["git", "rev-parse", f"HEAD:{ref}"], cwd=checkout)
        object_id = result.stdout.strip()
        if result.returncode != 0 or len(object_id) not in {40, 64}:
            return None
        objects.append({"ref": ref, "git_object_id": object_id})
    return canonical_sha256({"objects": objects})


def _platform_architecture() -> Literal["arm64", "x86_64", "other"]:
    architecture = platform.machine().lower()
    if architecture in {"arm64", "aarch64"}:
        return "arm64"
    if architecture in {"x86_64", "amd64"}:
        return "x86_64"
    return "other"


def _memory_bytes() -> int:
    if platform.system() == "Darwin":
        result = _command(["sysctl", "-n", "hw.memsize"])
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return int(result.stdout.strip())
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return 0


def _docker_daemon_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = _command(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=10)
    return result.returncode == 0 and bool(result.stdout.strip())


def _docker_platform_available(platform_name: str) -> bool:
    if shutil.which("docker") is None:
        return False
    result = _command(["docker", "buildx", "inspect"], timeout=20)
    if result.returncode != 0:
        return False
    platforms = ""
    for line in result.stdout.splitlines():
        if line.strip().startswith("Platforms:"):
            platforms = line.split(":", maxsplit=1)[1]
            break
    return platform_name in {item.strip() for item in platforms.split(",")}


def _swe_runtime_images_present(task_data_root: Path | None) -> tuple[bool, int, int]:
    if task_data_root is None or shutil.which("docker") is None:
        return False, 0, 0
    try:
        snapshot = load_swe_task_snapshot(task_data_root)
    except SweScorerError:
        return False, 0, 0
    images = sorted(
        {
            str(row.get("docker_image"))
            for row in snapshot.rows_by_id.values()
            if isinstance(row.get("docker_image"), str) and row.get("docker_image")
        }
    )
    present = 0
    for image in images:
        result = _command(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            timeout=10,
        )
        present += result.returncode == 0 and bool(result.stdout.strip())
    return bool(images) and present == len(images), present, len(images)


def _model_runtime_available() -> bool:
    provider_env_names = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    )
    return shutil.which("codex") is not None or any(os.getenv(name) for name in provider_env_names)


def _scorer_runtime_ready(checkout: Path, benchmark_id: BenchmarkSource) -> bool:
    module_name = SCORER_RUNTIME_IMPORTS.get(benchmark_id)
    if module_name is None:
        return True
    python = checkout / ".venv" / "bin" / "python"
    if not python.is_file():
        return False
    result = _command(
        [str(python), "-c", f"import {module_name}"],
        cwd=checkout,
        timeout=30,
    )
    return result.returncode == 0


def _hash_json_without_validation(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _agentdojo_tasks(checkout: Path, task_ids: list[str]) -> tuple[bool, str | None]:
    python = checkout / ".venv" / "bin" / "python"
    if not python.is_file():
        return False, None
    user_ids = sorted(task_id.split(":")[1] for task_id in task_ids if task_id.endswith(":clean"))
    injection_ids = sorted(
        task_id.split(":")[2] for task_id in task_ids if ":injection_task_" in task_id
    )
    script = (
        "import json; "
        "from agentdojo.task_suite.load_suites import get_suite; "
        "s=get_suite('v1.2.2','workspace'); "
        f"u={user_ids!r}; i={injection_ids!r}; "
        "m=[x for x in u if x not in s.user_tasks]+"
        "[x for x in i if x not in s.injection_tasks]; "
        "print(json.dumps({'missing':m,'user_count':len(s.user_tasks),"
        "'injection_count':len(s.injection_tasks)},sort_keys=True))"
    )
    result = _command([str(python), "-c", script], cwd=checkout, timeout=60)
    if result.returncode != 0:
        return False, None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, None
    verified = not payload.get("missing")
    digest = _hash_json_without_validation(
        {
            "selected_task_ids": task_ids,
            "registered_user_task_count": payload.get("user_count"),
            "registered_injection_task_count": payload.get("injection_count"),
        }
    )
    return verified, digest


def _task_identity_state(
    benchmark_id: BenchmarkSource,
    checkout: Path | None,
    task_ids: list[str],
    *,
    swe_task_data_root: Path | None,
) -> tuple[bool, bool, str | None, str | None]:
    if benchmark_id == BenchmarkSource.SWE_BENCH_LIVE:
        if swe_task_data_root is None:
            return False, False, None, None
        try:
            snapshot = load_swe_task_snapshot(swe_task_data_root)
        except SweScorerError:
            return False, False, None, None
        verified = list(snapshot.rows_by_id) == task_ids
        return (
            True,
            verified,
            snapshot.revision,
            snapshot.selected_tasks_digest_sha256,
        )

    if checkout is None or _git_revision(checkout) is None:
        return False, False, None, None
    revision = _git_revision(checkout)
    if benchmark_id == BenchmarkSource.TUA_BENCH:
        refs = [f"tasks/{task_id}" for task_id in task_ids]
        digest = _git_objects_digest(checkout, refs)
        verified = digest is not None and all(
            (checkout / "tasks" / task_id / "tests").is_dir() for task_id in task_ids
        )
        return True, verified, revision, digest
    if benchmark_id == BenchmarkSource.TAU_BENCH:
        path = checkout / "data" / "tau2" / "domains" / "retail" / "tasks.json"
        if not path.is_file():
            return True, False, revision, None
        try:
            tasks = json.loads(path.read_text(encoding="utf-8"))
            indexes = [int(task_id.split(":")[1]) for task_id in task_ids]
            selected = [tasks[index] for index in indexes]
        except (IndexError, KeyError, OSError, ValueError, json.JSONDecodeError):
            return True, False, revision, None
        return True, True, revision, _hash_json_without_validation(selected)
    verified, digest = _agentdojo_tasks(checkout, task_ids)
    return True, verified, revision, digest


def _check(
    check_id: str,
    *,
    passed: bool,
    pass_code: str,
    fail_code: str,
    failure_is_warning: bool = False,
    evidence: object,
) -> SourcePreflightCheckV1:
    status: Literal["passed", "warning", "blocked"] = (
        "passed" if passed else ("warning" if failure_is_warning else "blocked")
    )
    return SourcePreflightCheckV1(
        check_id=check_id,
        status=status,
        blocking=status == "blocked",
        detail_code=pass_code if passed else fail_code,
        evidence_digest_sha256=_hash_json_without_validation(evidence),
    )


def build_source_preflight(
    benchmark_id: BenchmarkSource,
    *,
    source_root: Path,
    swe_task_data_root: Path | None = None,
    observed_adapter_available: bool | None = None,
    generated_at: str | None = None,
) -> SourcePreflightReceiptV1:
    definition = SOURCE_DEFINITIONS[benchmark_id]
    if observed_adapter_available is None:
        observed_adapter_available = bool(
            benchmark_id == BenchmarkSource.SWE_BENCH_LIVE
            and bool(SWE_ADAPTER_VERSION)
            or benchmark_id == BenchmarkSource.AGENTDOJO
            and BRIDGE_SCRIPT.is_file()
            or benchmark_id == BenchmarkSource.TAU_BENCH
            and TAU_BRIDGE_SCRIPT.is_file()
            or benchmark_id == BenchmarkSource.TUA_BENCH
            and bool(TUA_ADAPTER_VERSION)
        )
    checkout = source_root / CHECKOUT_NAMES[benchmark_id]
    scorer_revision = _git_revision(checkout)
    scorer_acquired = scorer_revision is not None
    scorer_digest = (
        _git_objects_digest(checkout, SCORER_PATHS[benchmark_id]) if scorer_acquired else None
    )
    scorer_present = scorer_digest is not None
    seeds = pilot_seeds()[benchmark_id]
    task_ids = [seed.task_id for seed in seeds]
    task_acquired, tasks_verified, task_revision, task_digest = _task_identity_state(
        benchmark_id,
        checkout if scorer_acquired else None,
        task_ids,
        swe_task_data_root=swe_task_data_root,
    )
    docker_cli = shutil.which("docker") is not None
    docker_daemon = _docker_daemon_available()
    uv_available = shutil.which("uv") is not None
    model_runtime = _model_runtime_available()
    architecture = _platform_architecture()
    memory_bytes = _memory_bytes()

    checks = [
        _check(
            "benchmark-data-acquired",
            passed=task_acquired,
            pass_code="benchmark-data-acquired",
            fail_code="benchmark-data-not-acquired",
            evidence={"benchmark_id": benchmark_id.value, "acquired": task_acquired},
        ),
        _check(
            "benchmark-data-revision",
            passed=task_revision == definition.task_data_revision,
            pass_code="benchmark-data-revision-matched",
            fail_code="benchmark-data-revision-missing-or-mismatched",
            evidence={
                "expected": definition.task_data_revision,
                "observed": task_revision,
            },
        ),
        _check(
            "selected-case-identities",
            passed=tasks_verified,
            pass_code="selected-case-identities-verified",
            fail_code="selected-case-identities-unverified",
            evidence={"selected_task_ids": task_ids, "verified": tasks_verified},
        ),
        _check(
            "scorer-source-acquired",
            passed=scorer_acquired,
            pass_code="scorer-source-acquired",
            fail_code="scorer-source-not-acquired",
            evidence={"benchmark_id": benchmark_id.value, "acquired": scorer_acquired},
        ),
        _check(
            "scorer-revision",
            passed=scorer_revision == definition.scorer_revision,
            pass_code="scorer-revision-matched",
            fail_code="scorer-revision-missing-or-mismatched",
            evidence={"expected": definition.scorer_revision, "observed": scorer_revision},
        ),
        _check(
            "official-scorer-ref",
            passed=scorer_present,
            pass_code="official-scorer-ref-present",
            fail_code="official-scorer-ref-missing",
            evidence={"official_scorer_ref": seeds[0].official_scorer_ref},
        ),
        _check(
            "third-party-asset-terms",
            passed=definition.third_party_asset_terms_reviewed,
            pass_code="third-party-asset-terms-reviewed",
            fail_code="third-party-asset-terms-unreviewed",
            evidence={
                "license_id": definition.license_id,
                "reviewed": definition.third_party_asset_terms_reviewed,
            },
        ),
        _check(
            "model-runtime",
            passed=model_runtime,
            pass_code="model-runtime-available",
            fail_code="model-runtime-unavailable",
            evidence={"available": model_runtime},
        ),
        _check(
            "observed-adapter",
            passed=observed_adapter_available,
            pass_code="observed-adapter-available",
            fail_code="observed-adapter-missing",
            evidence={"benchmark_id": benchmark_id.value},
        ),
    ]
    if benchmark_id in DOCKER_REQUIRED:
        checks.append(
            _check(
                "docker-runtime",
                passed=docker_cli and docker_daemon,
                pass_code="docker-runtime-ready",
                fail_code="docker-daemon-unavailable",
                evidence={"cli": docker_cli, "daemon": docker_daemon},
            )
        )
    if benchmark_id in SCORER_RUNTIME_IMPORTS:
        scorer_runtime_ready = _scorer_runtime_ready(checkout, benchmark_id)
        checks.append(
            _check(
                "scorer-runtime-environment",
                passed=scorer_runtime_ready,
                pass_code="scorer-runtime-environment-ready",
                fail_code="scorer-runtime-environment-missing",
                evidence={
                    "benchmark_id": benchmark_id.value,
                    "required_module": SCORER_RUNTIME_IMPORTS[benchmark_id],
                    "python_environment_ready": scorer_runtime_ready,
                },
            )
        )
    if benchmark_id == BenchmarkSource.SWE_BENCH_LIVE:
        amd64_runner = docker_daemon and _docker_platform_available("linux/amd64")
        images_ready, present_image_count, required_image_count = (
            _swe_runtime_images_present(swe_task_data_root)
        )
        checks.append(
            _check(
                "amd64-scorer-runner",
                passed=amd64_runner,
                pass_code="amd64-scorer-runner-available",
                fail_code="amd64-scorer-runner-unavailable",
                evidence={
                    "platform_architecture": architecture,
                    "docker_linux_amd64_available": amd64_runner,
                },
            )
        )
        checks.append(
            _check(
                "selected-runtime-images",
                passed=images_ready,
                pass_code="selected-runtime-images-present",
                fail_code="selected-runtime-images-unavailable",
                evidence={
                    "present_image_count": present_image_count,
                    "required_image_count": required_image_count,
                },
            )
        )
    if benchmark_id == BenchmarkSource.TUA_BENCH:
        checks.extend(
            [
                _check(
                    "minimum-memory",
                    passed=memory_bytes >= 8 * 1024**3,
                    pass_code="minimum-memory-available",
                    fail_code="minimum-memory-unavailable",
                    evidence={"memory_bytes": memory_bytes},
                ),
                _check(
                    "vision-judge-provider",
                    passed=os.getenv("TUA_VISION_JUDGE_READY") == "1",
                    pass_code="vision-judge-provider-configured",
                    fail_code="tua-vision-judge-provider-unconfigured",
                    evidence={"configured": os.getenv("TUA_VISION_JUDGE_READY") == "1"},
                ),
            ]
        )

    blocker_codes = sorted(item.detail_code for item in checks if item.status == "blocked")
    warning_codes = sorted(item.detail_code for item in checks if item.status == "warning")
    if not task_acquired or not scorer_acquired:
        readiness: Literal[
            "source_unavailable",
            "source_ready_execution_blocked",
            "execution_ready",
        ] = "source_unavailable"
    elif blocker_codes:
        readiness = "source_ready_execution_blocked"
    else:
        readiness = "execution_ready"
    generated = generated_at or datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    receipt = SourcePreflightReceiptV1(
        schema_version="source-preflight-receipt-v1",
        receipt_id=f"source-preflight:{benchmark_id.value}",
        suite_id=PILOT_SUITE_ID,
        benchmark_id=benchmark_id,
        expected_task_data_revision=definition.task_data_revision,
        observed_task_data_revision=task_revision,
        expected_scorer_revision=definition.scorer_revision,
        observed_scorer_revision=scorer_revision,
        task_data_digest_sha256=task_digest,
        scorer_tree_digest_sha256=scorer_digest,
        selected_task_count=len(task_ids),
        selected_task_identity_digest_sha256=canonical_sha256(
            {"benchmark_id": benchmark_id.value, "task_ids": task_ids}
        ),
        selected_task_identities_verified=tasks_verified,
        official_scorer_ref=seeds[0].official_scorer_ref,
        official_scorer_present=scorer_present,
        task_data_acquired=task_acquired,
        scorer_source_acquired=scorer_acquired,
        license_id=definition.license_id,
        license_use_scope=definition.license_use_scope,
        third_party_asset_terms_reviewed=definition.third_party_asset_terms_reviewed,
        platform_architecture=architecture,
        memory_bytes=memory_bytes,
        docker_cli_available=docker_cli,
        docker_daemon_available=docker_daemon,
        uv_available=uv_available,
        model_runtime_available=model_runtime,
        observed_adapter_available=observed_adapter_available,
        execution_readiness=readiness,
        blocker_codes=blocker_codes,
        warning_codes=warning_codes,
        checks=checks,
        generated_at=generated,
        privacy=benchmark_privacy(),
    )
    assert_safe_metadata(receipt.model_dump(mode="json"), label="source preflight receipt")
    return receipt


def write_source_preflights(
    output_dir: Path,
    *,
    source_root: Path,
    benchmark_ids: Iterable[BenchmarkSource],
    swe_task_data_root: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    receipts = [
        build_source_preflight(
            benchmark_id,
            source_root=source_root,
            swe_task_data_root=swe_task_data_root,
            generated_at=generated_at,
        )
        for benchmark_id in benchmark_ids
    ]
    for receipt in receipts:
        (output_dir / f"{receipt.benchmark_id.value}.json").write_text(
            pretty_json(receipt), encoding="utf-8"
        )
    manifest: dict[str, object] = {
        "schema_version": "source-preflight-manifest-v1",
        "suite_id": PILOT_SUITE_ID,
        "receipt_count": len(receipts),
        "execution_ready_count": sum(
            receipt.execution_readiness == "execution_ready" for receipt in receipts
        ),
        "receipts": [
            {
                "benchmark_id": receipt.benchmark_id.value,
                "execution_readiness": receipt.execution_readiness,
                "receipt_digest_sha256": canonical_sha256(receipt),
                "blocker_codes": receipt.blocker_codes,
            }
            for receipt in receipts
        ],
        "claim_boundary": (
            "Live preflight verifies local source and scorer prerequisites only. It does "
            "not claim official scorer execution or Delivery Clearance effectiveness."
        ),
    }
    assert_safe_metadata(manifest, label="source preflight manifest")
    (output_dir / "manifest.json").write_text(pretty_json(manifest), encoding="utf-8")
    return manifest
