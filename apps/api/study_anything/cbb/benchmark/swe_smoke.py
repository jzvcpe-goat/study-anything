"""SWE-bench-Live task snapshot and official result adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from study_anything.cbb.benchmark.adapters import benchmark_privacy
from study_anything.cbb.benchmark.fixtures import pilot_assets, pilot_seeds
from study_anything.cbb.benchmark.models import (
    BenchmarkSource,
    CandidateDeliveryV1,
    EvidenceObservationV1,
    EvidenceStatus,
    OfficialScorerOutcome,
    ScorerExecutionReceiptV1,
)
from study_anything.cbb.benchmark.runner import reviewer_candidate_view
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)


SWE_SCORER_REVISION = "70ec57e852e3f2d195790fe71f553e272c691833"
SWE_TASK_DATA_REVISION = "608f7ae9ab8ea1f9f0d030fe04562cf6bd1a0c8b"
ADAPTER_VERSION = "swe-bench-live-result-adapter-v0.1"
DATASET_ID = "SWE-bench-Live/MultiLang"
SELECTED_TASKS_FILE = "selected-tasks.jsonl"
SELECTED_IDENTITIES_FILE = "selected-task-identities.json"
TASK_DATA_PROVENANCE_FILE = "task-data-provenance.json"
RUN_PROVENANCE_FILE = "run-provenance.json"
RUNTIME_TASK_FILE = "runtime-selected-task.jsonl"


class SweScorerError(RuntimeError):
    """Raised when SWE task data or official scorer output is not trustworthy."""


@dataclass(frozen=True)
class SweTaskSnapshot:
    revision: str
    rows_by_id: dict[str, dict[str, Any]]
    selected_tasks_digest_sha256: str
    provenance_digest_sha256: str


@dataclass(frozen=True)
class SweEvaluationObservation:
    candidate_kind: str
    outcome: OfficialScorerOutcome
    started_at: str
    completed_at: str
    results_digest_sha256: str
    report_digest_sha256: str | None
    provenance_digest_sha256: str
    command_digest_sha256: str


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _raw_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _docker_image_inspect(image_ref: str) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "image", "inspect", image_ref],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise SweScorerError(f"cannot inspect SWE runtime image: {image_ref}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SweScorerError("SWE runtime image inspection returned invalid JSON") from exc
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise SweScorerError("SWE runtime image inspection returned an invalid object")
    return payload[0]


def _runtime_image_override(
    row: dict[str, Any],
    *,
    evaluation_dir: Path,
    source_ref: str | None,
    source_digest_sha256: str | None,
    runtime_ref: str | None,
) -> tuple[Path | None, dict[str, Any]]:
    values = (source_ref, source_digest_sha256, runtime_ref)
    if not any(values):
        return None, {"runtime_image_override_applied": False}
    if not all(values):
        raise SweScorerError(
            "SWE runtime override requires source ref, source digest, and runtime ref"
        )
    assert source_ref is not None
    assert source_digest_sha256 is not None
    assert runtime_ref is not None
    if len(source_digest_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in source_digest_sha256
    ):
        raise SweScorerError("SWE runtime source digest must be lowercase SHA-256")

    source = _docker_image_inspect(source_ref)
    runtime = _docker_image_inspect(runtime_ref)
    source_id = str(source.get("Id", "")).removeprefix("sha256:")
    runtime_id = str(runtime.get("Id", "")).removeprefix("sha256:")
    if source_id != source_digest_sha256:
        raise SweScorerError("SWE runtime source image digest drifted")
    if len(runtime_id) != 64:
        raise SweScorerError("SWE runtime override image has no stable digest")
    if source.get("Os") != "linux" or source.get("Architecture") != "amd64":
        raise SweScorerError("SWE runtime source image must be linux/amd64")
    if (runtime.get("Os"), runtime.get("Architecture")) != (
        source.get("Os"),
        source.get("Architecture"),
    ):
        raise SweScorerError("SWE runtime override changed the image platform")
    source_rootfs = source.get("RootFS")
    runtime_rootfs = runtime.get("RootFS")
    if not isinstance(source_rootfs, dict) or not isinstance(runtime_rootfs, dict):
        raise SweScorerError("SWE runtime image has no stable RootFS metadata")
    if source_rootfs != runtime_rootfs:
        raise SweScorerError("SWE runtime override changed filesystem layers")

    source_config = dict(source.get("Config") or {})
    runtime_config = dict(runtime.get("Config") or {})
    source_entrypoint = source_config.pop("Entrypoint", None)
    source_config.pop("Cmd", None)
    runtime_entrypoint = runtime_config.pop("Entrypoint", None)
    runtime_config.pop("Cmd", None)
    if source_config != runtime_config:
        raise SweScorerError("SWE runtime override changed non-entrypoint config")
    if not source_entrypoint or runtime_entrypoint not in (None, []):
        raise SweScorerError("SWE runtime override must only clear the entrypoint")

    runtime_row = dict(row)
    runtime_row["docker_image"] = runtime_ref
    runtime_task_path = evaluation_dir / RUNTIME_TASK_FILE
    runtime_task_path.write_text(
        json.dumps(runtime_row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    metadata = {
        "runtime_image_override_applied": True,
        "runtime_image_override_kind": "clear-broken-entrypoint-only",
        "upstream_runtime_image_ref": str(row.get("docker_image", "")),
        "runtime_image_source_ref": source_ref,
        "runtime_image_source_digest_sha256": source_id,
        "runtime_image_ref": runtime_ref,
        "runtime_image_digest_sha256": runtime_id,
        "runtime_rootfs_digest_sha256": canonical_sha256(source_rootfs),
        "runtime_task_digest_sha256": _sha256_file(runtime_task_path),
    }
    return runtime_task_path, metadata


def _text_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _git_value(checkout: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=checkout,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or len(value) not in {40, 64}:
        raise SweScorerError(f"cannot resolve pinned SWE-bench-Live object: {ref}")
    return value


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SweScorerError(f"{label} is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SweScorerError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise SweScorerError(f"{label} must be a JSON object")
    return value


def _integer(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SweScorerError(f"{label} must be an integer")
    return value


def _fixture(case_id: str) -> tuple[Any, CandidateDeliveryV1]:
    for case, candidate in pilot_assets():
        if case.case_id == case_id and case.source.benchmark_id == BenchmarkSource.SWE_BENCH_LIVE:
            return case, candidate
    raise SweScorerError(f"case is not a preregistered SWE-bench-Live pilot case: {case_id}")


def selected_swe_task_ids() -> list[str]:
    return [
        seed.task_id
        for seed in pilot_seeds()[BenchmarkSource.SWE_BENCH_LIVE]
    ]


def write_swe_task_snapshot(
    output_dir: Path,
    *,
    metadata_payload_path: Path,
    rows_payload_path: Path,
) -> dict[str, Any]:
    """Create a pinned local scorer input from official HF API responses."""

    metadata = _read_object(metadata_payload_path, label="Hugging Face dataset metadata")
    rows_payload = _read_object(rows_payload_path, label="Hugging Face rows response")
    if metadata.get("sha") != SWE_TASK_DATA_REVISION:
        raise SweScorerError("Hugging Face dataset metadata revision drifted")
    if metadata.get("private") is not False or metadata.get("gated") is not False:
        raise SweScorerError("SWE task data must remain public and ungated")
    rows = rows_payload.get("rows")
    if not isinstance(rows, list):
        raise SweScorerError("Hugging Face rows response has no rows")
    selected_ids = selected_swe_task_ids()
    selected: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("row"), dict):
            continue
        row = item["row"]
        task_id = row.get("instance_id")
        if task_id in selected_ids:
            if task_id in selected:
                raise SweScorerError("Hugging Face rows response contains a duplicate task")
            selected[str(task_id)] = row
    if set(selected) != set(selected_ids):
        raise SweScorerError("Hugging Face rows response is missing preregistered tasks")

    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_path = output_dir / SELECTED_TASKS_FILE
    tasks_path.write_text(
        "\n".join(
            json.dumps(selected[task_id], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for task_id in selected_ids
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / SELECTED_IDENTITIES_FILE).write_text(
        json.dumps(selected_ids, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    provenance = {
        "schema_version": "swe-data-provenance-v1",
        "dataset_id": DATASET_ID,
        "dataset_revision": SWE_TASK_DATA_REVISION,
        "dataset_config": "default",
        "dataset_split": "js",
        "selected_task_count": len(selected_ids),
        "selected_task_ids": selected_ids,
        "selected_tasks_file": SELECTED_TASKS_FILE,
        "selected_tasks_digest_sha256": _sha256_file(tasks_path),
        "metadata_response_digest_sha256": _sha256_file(metadata_payload_path),
        "rows_response_digest_sha256": _sha256_file(rows_payload_path),
        "raw_task_payload_in_provenance": False,
        "source_uri": "https://huggingface.co/datasets/SWE-bench-Live/MultiLang",
    }
    assert_safe_metadata(provenance, label="SWE task data provenance")
    (output_dir / TASK_DATA_PROVENANCE_FILE).write_text(
        pretty_json(provenance), encoding="utf-8"
    )
    return provenance


def load_swe_task_snapshot(task_data_root: Path) -> SweTaskSnapshot:
    provenance_path = task_data_root / TASK_DATA_PROVENANCE_FILE
    provenance = _read_object(provenance_path, label="SWE task data provenance")
    if provenance.get("schema_version") != "swe-data-provenance-v1":
        raise SweScorerError("SWE task data provenance schema drifted")
    if provenance.get("dataset_id") != DATASET_ID:
        raise SweScorerError("SWE task data provenance dataset drifted")
    if provenance.get("dataset_revision") != SWE_TASK_DATA_REVISION:
        raise SweScorerError("SWE task data provenance revision drifted")
    identities_path = task_data_root / SELECTED_IDENTITIES_FILE
    try:
        identities = json.loads(identities_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SweScorerError("SWE selected task identities are missing or invalid") from exc
    expected_ids = selected_swe_task_ids()
    if identities != expected_ids or provenance.get("selected_task_ids") != expected_ids:
        raise SweScorerError("SWE selected task identities drifted")
    tasks_path = task_data_root / SELECTED_TASKS_FILE
    if not tasks_path.is_file():
        raise SweScorerError("SWE selected task data is missing")
    tasks_digest = _sha256_file(tasks_path)
    if tasks_digest != provenance.get("selected_tasks_digest_sha256"):
        raise SweScorerError("SWE selected task data digest drifted")
    rows: dict[str, dict[str, Any]] = {}
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SweScorerError("SWE selected task data is not valid JSONL") from exc
        if not isinstance(row, dict) or not isinstance(row.get("instance_id"), str):
            raise SweScorerError("SWE selected task row is invalid")
        task_id = str(row["instance_id"])
        if task_id in rows:
            raise SweScorerError("SWE selected task data contains a duplicate")
        rows[task_id] = row
    if list(rows) != expected_ids:
        raise SweScorerError("SWE selected task row ordering or coverage drifted")
    return SweTaskSnapshot(
        revision=SWE_TASK_DATA_REVISION,
        rows_by_id=rows,
        selected_tasks_digest_sha256=tasks_digest,
        provenance_digest_sha256=_sha256_file(provenance_path),
    )


def parse_swe_evaluation(
    evaluation_dir: Path,
    *,
    expected_case_id: str,
    expected_task_id: str,
    expected_candidate_kind: str,
) -> SweEvaluationObservation:
    provenance_path = evaluation_dir / RUN_PROVENANCE_FILE
    results_path = evaluation_dir / "results.json"
    provenance = _read_object(provenance_path, label="SWE scorer run provenance")
    results = _read_object(results_path, label="SWE official scorer results")
    expected_provenance = {
        "schema_version": "swe-scorer-run-provenance-v1",
        "case_id": expected_case_id,
        "upstream_task_id": expected_task_id,
        "candidate_kind": expected_candidate_kind,
        "scorer_revision": SWE_SCORER_REVISION,
        "task_data_revision": SWE_TASK_DATA_REVISION,
        "process_exit_code": 0,
    }
    for field_name, expected in expected_provenance.items():
        if provenance.get(field_name) != expected:
            raise SweScorerError(f"SWE scorer provenance field drifted: {field_name}")
    command_digest = provenance.get("command_digest_sha256")
    if not isinstance(command_digest, str) or len(command_digest) != 64:
        raise SweScorerError("SWE scorer provenance has no command digest")
    if results.get("submitted_ids") != [expected_task_id]:
        raise SweScorerError("SWE scorer result task does not match the preregistered case")
    if _integer(results.get("submitted"), label="SWE submitted count") != 1:
        raise SweScorerError("SWE scorer import requires exactly one submitted case")
    counts = {
        key: _integer(results.get(key), label=f"SWE {key} count")
        for key in ("success", "failure", "empty_patch", "error", "incomplete")
    }
    if counts["error"] or counts["incomplete"]:
        raise SweScorerError("SWE official scorer result is errored or incomplete")
    report_path = evaluation_dir / expected_task_id / "report.json"
    report_digest: str | None = None
    if expected_candidate_kind == "gold":
        if counts != {
            "success": 1,
            "failure": 0,
            "empty_patch": 0,
            "error": 0,
            "incomplete": 0,
        }:
            raise SweScorerError("SWE gold control did not resolve cleanly")
        report = _read_object(report_path, label="SWE per-case scorer report")
        if report.get("instance_id") != expected_task_id or report.get("resolved") is not True:
            raise SweScorerError("SWE per-case scorer report did not resolve the task")
        report_digest = _sha256_file(report_path)
        outcome = OfficialScorerOutcome.PASSED
    elif expected_candidate_kind == "empty":
        if counts != {
            "success": 0,
            "failure": 0,
            "empty_patch": 1,
            "error": 0,
            "incomplete": 0,
        }:
            raise SweScorerError("SWE empty-patch control was not classified as empty")
        outcome = OfficialScorerOutcome.FAILED
    else:
        raise SweScorerError("unsupported SWE fixed candidate kind")
    return SweEvaluationObservation(
        candidate_kind=expected_candidate_kind,
        outcome=outcome,
        started_at=str(provenance.get("started_at", "")),
        completed_at=str(provenance.get("completed_at", "")),
        results_digest_sha256=_sha256_file(results_path),
        report_digest_sha256=report_digest,
        provenance_digest_sha256=_sha256_file(provenance_path),
        command_digest_sha256=command_digest,
    )


def run_swe_official_case(
    case_id: str,
    *,
    checkout: Path,
    task_data_root: Path,
    evaluation_dir: Path,
    runtime_image_source_ref: str | None = None,
    runtime_image_source_digest_sha256: str | None = None,
    runtime_image_ref: str | None = None,
) -> dict[str, Any]:
    """Execute one fixed SWE control and bind its output to run provenance."""

    case, _ = _fixture(case_id)
    observed_revision = _git_value(checkout, "HEAD")
    if observed_revision != SWE_SCORER_REVISION:
        raise SweScorerError("SWE-bench-Live scorer checkout does not match the pinned revision")
    snapshot = load_swe_task_snapshot(task_data_root)
    task_id = case.source.upstream_task_id
    row = snapshot.rows_by_id.get(task_id)
    if row is None or row.get("base_commit") != case.source.task_snapshot_ref:
        raise SweScorerError("SWE task row does not match the preregistered base commit")
    python = checkout / ".venv" / "bin" / "python"
    if not python.is_file():
        raise SweScorerError("SWE-bench-Live scorer environment is missing")
    candidate_kind = (
        "gold" if case.candidate_assignment == "known_safe_control" else "empty"
    )
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    if (evaluation_dir / "results.json").exists():
        raise SweScorerError("SWE evaluation output already exists")
    runtime_task_path, runtime_metadata = _runtime_image_override(
        row,
        evaluation_dir=evaluation_dir,
        source_ref=runtime_image_source_ref,
        source_digest_sha256=runtime_image_source_digest_sha256,
        runtime_ref=runtime_image_ref,
    )
    task_data_path = runtime_task_path or (task_data_root / SELECTED_TASKS_FILE)
    if candidate_kind == "gold":
        patch_argument = "gold"
    else:
        prediction_path = evaluation_dir / "fixed-candidate.json"
        prediction_path.write_text(
            json.dumps({task_id: {"model_patch": ""}}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        patch_argument = str(prediction_path)
    command = [
        str(python),
        "-m",
        "evaluation.evaluation",
        "--dataset",
        str(task_data_path),
        "--instance_ids",
        task_id,
        "--platform",
        "linux",
        "--patch_dir",
        patch_argument,
        "--output_dir",
        str(evaluation_dir),
        "--workers",
        "1",
        "--overwrite",
        "1",
    ]
    command_digest = canonical_sha256(
        {
            "adapter_version": ADAPTER_VERSION,
            "argv_without_local_paths": [
                "python",
                "-m",
                "evaluation.evaluation",
                "--dataset",
                SELECTED_TASKS_FILE,
                "--instance_ids",
                task_id,
                "--platform",
                "linux",
                "--patch_dir",
                candidate_kind,
                "--output_dir",
                "evaluation-output",
                "--workers",
                "1",
                "--overwrite",
                "1",
                "--runtime-image-override",
                str(runtime_metadata.get("runtime_image_override_kind", "none")),
            ],
        }
    )
    started_at = _utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=checkout,
            check=False,
            capture_output=True,
            text=True,
            timeout=3 * 60 * 60,
        )
        exit_code = completed.returncode
        process_output_digest = sha256(
            (completed.stdout + "\n" + completed.stderr).encode("utf-8")
        ).hexdigest()
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        process_output_digest = sha256(
            (_text_output(exc.stdout) + "\n" + _text_output(exc.stderr)).encode("utf-8")
        ).hexdigest()
    completed_at = _utc_now()
    provenance = {
        "schema_version": "swe-scorer-run-provenance-v1",
        "case_id": case_id,
        "upstream_task_id": task_id,
        "candidate_kind": candidate_kind,
        "scorer_revision": observed_revision,
        "task_data_revision": snapshot.revision,
        "process_exit_code": exit_code,
        "command_digest_sha256": command_digest,
        "process_output_digest_sha256": process_output_digest,
        "started_at": started_at,
        "completed_at": completed_at,
        "raw_process_output_included": False,
        "model_calls_performed": False,
        "production_mutation_performed": False,
        **runtime_metadata,
    }
    assert_safe_metadata(provenance, label="SWE scorer run provenance")
    (evaluation_dir / RUN_PROVENANCE_FILE).write_text(
        pretty_json(provenance), encoding="utf-8"
    )
    if exit_code != 0:
        raise SweScorerError(f"SWE official scorer process failed with exit code {exit_code}")
    return provenance


def score_swe_case(
    case_id: str,
    *,
    checkout: Path,
    task_data_root: Path,
    evaluation_dir: Path,
) -> tuple[CandidateDeliveryV1, ScorerExecutionReceiptV1, dict[str, Any]]:
    case, fixture_candidate = _fixture(case_id)
    observed_revision = _git_value(checkout, "HEAD")
    if observed_revision != SWE_SCORER_REVISION:
        raise SweScorerError("SWE-bench-Live scorer checkout does not match the pinned revision")
    scorer_tree_id = _git_value(checkout, "HEAD:evaluation")
    dependency_file = checkout / "pyproject.toml"
    if not dependency_file.is_file():
        raise SweScorerError("pinned SWE-bench-Live dependency declaration is missing")
    snapshot = load_swe_task_snapshot(task_data_root)
    task_id = case.source.upstream_task_id
    row = snapshot.rows_by_id.get(task_id)
    if row is None or row.get("base_commit") != case.source.task_snapshot_ref:
        raise SweScorerError("SWE task row does not match the preregistered base commit")
    candidate_kind = (
        "gold" if case.candidate_assignment == "known_safe_control" else "empty"
    )
    observation = parse_swe_evaluation(
        evaluation_dir,
        expected_case_id=case_id,
        expected_task_id=task_id,
        expected_candidate_kind=candidate_kind,
    )
    task_row_digest = _raw_json_sha256(row)
    source_environment_digest = canonical_sha256(
        {
            "benchmark_id": BenchmarkSource.SWE_BENCH_LIVE.value,
            "scorer_revision": observed_revision,
            "scorer_tree_id": scorer_tree_id,
            "task_data_revision": snapshot.revision,
            "task_row_digest_sha256": task_row_digest,
            "task_data_provenance_digest_sha256": snapshot.provenance_digest_sha256,
        }
    )
    subject_digest = canonical_sha256(
        {
            "case_id": case_id,
            "candidate_recipe_code": case.candidate_recipe_code,
            "source_environment_digest_sha256": source_environment_digest,
            "scorer_adapter": ADAPTER_VERSION,
            "candidate_kind": candidate_kind,
        }
    )
    scorer_output_digest = canonical_sha256(
        {
            "results_digest_sha256": observation.results_digest_sha256,
            "report_digest_sha256": observation.report_digest_sha256,
            "run_provenance_digest_sha256": observation.provenance_digest_sha256,
        }
    )
    receipt_payload = {
        "schema_version": "scorer-execution-receipt-v1",
        "receipt_id": f"scorer:{case_id}",
        "suite_id": case.suite_id,
        "case_id": case_id,
        "benchmark_id": BenchmarkSource.SWE_BENCH_LIVE.value,
        "upstream_task_id": task_id,
        "subject_digest_sha256": subject_digest,
        "source_environment_digest_sha256": source_environment_digest,
        "scorer_source_uri": case.source.scorer_source_uri,
        "scorer_source_revision": observed_revision,
        "official_scorer_ref": case.source.official_scorer_ref,
        "dependency_lock_digest_sha256": _sha256_file(dependency_file),
        "asset_manifest_digest_sha256": canonical_sha256(
            {
                "selected_tasks_digest_sha256": snapshot.selected_tasks_digest_sha256,
                "task_row_digest_sha256": task_row_digest,
            }
        ),
        "runtime_image_digests_sha256": [],
        "command_digest_sha256": observation.command_digest_sha256,
        "scorer_output_digest_sha256": scorer_output_digest,
        "outcome": observation.outcome.value,
        "numeric_reward": 1.0 if observation.outcome == OfficialScorerOutcome.PASSED else 0.0,
        "utility_passed": None,
        "security_passed": None,
        "exit_code": 0,
        "official_scorer_executed": True,
        "started_at": observation.started_at,
        "completed_at": observation.completed_at,
        "raw_scorer_output_included": False,
        "raw_hidden_tests_included": False,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    receipt = ScorerExecutionReceiptV1.model_validate(
        {**receipt_payload, "trace_digest_sha256": canonical_sha256(receipt_payload)}
    )
    scorer_passed = observation.outcome == OfficialScorerOutcome.PASSED
    evidence = [
        EvidenceObservationV1(
            evidence_type="source-provenance",
            status=EvidenceStatus.PASSED,
            evidence_ref=f"observed-source:{case_id}",
            evidence_digest_sha256=source_environment_digest,
            summary_code="acquired-source-scorer-revision-verified",
            blocking=True,
        ),
        EvidenceObservationV1(
            evidence_type="scorer-result",
            status=EvidenceStatus.PASSED if scorer_passed else EvidenceStatus.FAILED,
            evidence_ref=f"observed-scorer:{case_id}",
            evidence_digest_sha256=canonical_sha256(receipt),
            summary_code=(
                "official-swe-scorer-passed"
                if scorer_passed
                else "official-swe-scorer-rejected-empty-patch"
            ),
            blocking=True,
        ),
        *[
            item
            for item in fixture_candidate.evidence
            if item.evidence_type
            in {"scope-boundary", "rollback-or-containment", "responsibility-boundary"}
        ],
    ]
    candidate = CandidateDeliveryV1(
        schema_version="candidate-delivery-v1",
        suite_id=case.suite_id,
        case_id=case_id,
        candidate_id=fixture_candidate.candidate_id,
        subject_digest_sha256=subject_digest,
        source_snapshot_digest_sha256=source_environment_digest,
        context_digest_sha256=fixture_candidate.context_digest_sha256,
        task_summary_code=fixture_candidate.task_summary_code,
        evidence_origin="observed_agent_run",
        declared_risk_level=fixture_candidate.declared_risk_level,
        target_scope=fixture_candidate.target_scope,
        intended_recipient_role=fixture_candidate.intended_recipient_role,
        risk_owner_role=fixture_candidate.risk_owner_role,
        prohibited_use_codes=list(fixture_candidate.prohibited_use_codes),
        scorer_outcome=observation.outcome,
        scorer_execution_origin="observed_official_scorer",
        official_scorer_executed=True,
        scorer_trace_digest_sha256=receipt.trace_digest_sha256,
        evidence=evidence,
        tool_permission_ids=list(fixture_candidate.tool_permission_ids),
        reference_label_included=False,
        hidden_tests_included=False,
        privacy=benchmark_privacy(),
    )
    packet = {
        "schema_version": "reviewer-case-packet-v1",
        "suite_id": case.suite_id,
        "case_id": case_id,
        "candidate": reviewer_candidate_view(candidate),
        "official_scorer_result_included": False,
        "reference_label_included": False,
        "hidden_tests_included": False,
    }
    assert_safe_metadata(packet, label=f"SWE-bench-Live reviewer packet {case_id}")
    return candidate, receipt, packet


def write_swe_smoke(
    output_dir: Path,
    *,
    checkout: Path,
    task_data_root: Path,
    case_evaluations: dict[str, Path],
) -> dict[str, Any]:
    candidates_dir = output_dir / "observed-candidates"
    packets_dir = output_dir / "reviewer-packets"
    receipts_dir = output_dir / "scorer-receipts"
    for directory in (candidates_dir, packets_dir, receipts_dir):
        directory.mkdir(parents=True, exist_ok=True)
    manifest_cases = []
    for case_id, evaluation_dir in sorted(case_evaluations.items()):
        candidate, receipt, packet = score_swe_case(
            case_id,
            checkout=checkout,
            task_data_root=task_data_root,
            evaluation_dir=evaluation_dir,
        )
        (candidates_dir / f"{case_id}.json").write_text(
            pretty_json(candidate), encoding="utf-8"
        )
        (packets_dir / f"{case_id}.json").write_text(
            pretty_json(packet), encoding="utf-8"
        )
        (receipts_dir / f"{case_id}.json").write_text(
            pretty_json(receipt), encoding="utf-8"
        )
        manifest_cases.append(
            {
                "case_id": case_id,
                "candidate_digest_sha256": canonical_sha256(candidate),
                "scorer_receipt_digest_sha256": canonical_sha256(receipt),
                "scorer_outcome": receipt.outcome.value,
            }
        )
    manifest = {
        "schema_version": "swe-bench-live-scorer-smoke-manifest-v1",
        "suite_id": "pilot-v0.1",
        "case_count": len(manifest_cases),
        "cases": manifest_cases,
        "official_scorer_executed": True,
        "model_calls_performed": False,
        "four_arm_review_executed": False,
        "human_reconstruction_completed": False,
        "claim_boundary": (
            "This adapter accepts only clean single-case SWE-bench-Live outputs bound to "
            "the pinned scorer and task-data revisions. It does not establish the 40-case "
            "treatment effect, production readiness, or professional certification."
        ),
    }
    assert_safe_metadata(manifest, label="SWE-bench-Live scorer smoke manifest")
    (output_dir / "manifest.json").write_text(pretty_json(manifest), encoding="utf-8")
    return manifest
