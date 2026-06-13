#!/usr/bin/env python3
"""Verify external-platform adoption from a distributable adoption pack."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
DEFAULT_MANIFEST = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.json"
PROOF_SCHEMA = "adoption-proof-v1"

REQUIRED_ARCHIVE_PATHS = [
    "manifest.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/packs/kimi/README.md",
    "platform/packs/codex/README.md",
    "platform/packs/workbuddy/README.md",
    "docs/learning-enrichment.md",
    "docs/second-brain-handoff.md",
    "docs/obsidian-export.md",
    "docs/notebooklm-bridge.md",
    "docs/plugin-sdk.md",
    "docs/plugin-registry.md",
    "docs/use-with-kimi.md",
    "docs/adoption-telemetry.md",
    "skills/study-anything/SKILL.md",
    "scripts/openai_compatible_agent_gateway.py",
    "scripts/mock_http_agent.py",
    "scripts/doctor.sh",
    "scripts/launch_self_host.sh",
    "scripts/stop_self_host.sh",
    "scripts/verify_published_image_launch.py",
    "scripts/verify_external_adoption.py",
    "scripts/verify_adoption_telemetry.py",
    "scripts/verify_agent_eval_baseline.py",
    "scripts/verify_notebooklm_obsidian_bridge_hardening.py",
    "scripts/verify_plugin_quarantine.py",
    "scripts/verify_security_recovery_hardening.py",
    "scripts/verify_platform_submission_dry_run.py",
    "platform/generated/study-anything-platform-submission-dry-run.json",
    "scripts/verify_platform_operator_drill.py",
    "scripts/verify_platform_ecosystem_eval_flow.py",
    "evals/baselines/study-anything-agent-eval-baseline.json",
    "fixtures/notebooklm/notebooklm-style-context-package.json",
]

REMEDIATION = {
    "docker_hub_or_ghcr": [
        "Retry with published images after `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:<tag>` succeeds.",
        "Use mirror/public ECR image overrides for Postgres/Python when Docker Hub returns EOF.",
        "Use `--runtime skill-mode` when local registry pulls are temporarily unreliable.",
    ],
    "non_ascii_path": [
        "Use `USE_PUBLISHED_IMAGES=true`, clone into an ASCII-only path, or set `ALLOW_NON_ASCII_DOCKER_BUILD=true` only after accepting the local Docker risk.",
    ],
    "port_in_use": [
        "Set `API_PORT`, `APP_POSTGRES_PORT`, or other port env vars to free values before launch.",
        "Run `./scripts/doctor.sh` to identify conflicting listeners.",
    ],
    "agent_endpoint": [
        "For local host agents use `AGENT_ENDPOINT=http://127.0.0.1:8787`.",
        "Inside Docker Compose smoke stacks use `AGENT_ENDPOINT=http://mock-http-agent:8787`.",
    ],
    "node_promptfoo": [
        "Install Node/npm or run Promptfoo only through `scripts/run_external_agent_evals.py` with explicit timeout.",
        "Promptfoo is an optional external gate unless `--promptfoo-required` is set.",
    ],
}


class AdoptionProofError(RuntimeError):
    """Readable adoption proof failure."""


def output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_seconds: int,
    capture_output: bool = True,
    required: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=capture_output,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdoptionProofError(
            f"Command timed out after {timeout_seconds}s: {' '.join(command)}\n"
            f"stdout:\n{output_text(exc.stdout)}\n"
            f"stderr:\n{output_text(exc.stderr)}"
        ) from exc
    if required and completed.returncode != 0:
        raise AdoptionProofError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def safe_json_from_stdout(label: str, stdout: str) -> dict[str, Any]:
    stripped = stdout.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(stripped.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise AdoptionProofError(f"Could not parse {label} output: {stdout}") from exc


def validate_adoption_pack(pack_path: Path, manifest_path: Path | None) -> dict[str, Any]:
    if not pack_path.exists():
        raise AdoptionProofError(
            f"Adoption pack archive is missing: {pack_path}. "
            "Run `python3 scripts/generate_platform_adoption_pack.py`."
        )
    external_manifest: dict[str, Any] | None = None
    if manifest_path and manifest_path.exists():
        external_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if external_manifest.get("archive_sha256") != sha256_file(pack_path):
            raise AdoptionProofError("External adoption pack manifest archive_sha256 mismatch.")

    with zipfile.ZipFile(pack_path) as archive:
        names = set(archive.namelist())
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise AdoptionProofError(f"Adoption pack archive should have one root, got {sorted(roots)}")
        root = next(iter(roots))
        missing = [path for path in REQUIRED_ARCHIVE_PATHS if f"{root}/{path}" not in names]
        if missing:
            raise AdoptionProofError(f"Adoption pack archive missing required files: {missing}")
        manifest = json.loads(archive.read(f"{root}/manifest.json").decode("utf-8"))
        if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
            raise AdoptionProofError(f"Unexpected adoption pack schema: {manifest.get('schema_version')}")
        for record in manifest.get("files", []):
            archive_path = str(record.get("archive_path"))
            if archive_path not in names:
                raise AdoptionProofError(f"Manifest file missing from archive: {archive_path}")
            actual = sha256_bytes(archive.read(archive_path))
            if actual != record.get("sha256"):
                raise AdoptionProofError(f"Archive file sha256 mismatch: {archive_path}")
        openai_tools = json.loads(
            archive.read(f"{root}/platform/generated/study-anything-openai-tools.json").decode("utf-8")
        )
        openapi = json.loads(
            archive.read(f"{root}/platform/generated/study-anything-platform-openapi.json").decode("utf-8")
        )
        pack_text = "\n".join(
            archive.read(f"{root}/{path}").decode("utf-8", errors="replace")
            for path in [
                "platform/packs/kimi/README.md",
                "platform/packs/codex/README.md",
                "platform/packs/workbuddy/README.md",
                "docs/platform-agent-integrations.md",
                "docs/second-brain-handoff.md",
                "docs/notebooklm-bridge.md",
                "docs/commercial-readiness.md",
                "docs/adoption-telemetry.md",
                "docs/plugin-sdk.md",
                "docs/plugin-registry.md",
            ]
        )
    required_terms = [
        "Kimi",
        "Codex",
        "WorkBuddy",
        "NotebookLM",
        "Obsidian",
        "deployment-guide-v1",
        "commercial-readiness-v1",
        "adoption-telemetry-v1",
        "pmf-readiness-v1",
    ]
    missing_terms = [term for term in required_terms if term not in pack_text]
    if missing_terms:
        raise AdoptionProofError(f"Adoption pack operator docs missing terms: {missing_terms}")
    tool_names = [
        item.get("function", {}).get("name")
        for item in openai_tools
        if isinstance(item, dict)
    ]
    return {
        "schema_version": manifest["schema_version"],
        "version": manifest.get("version"),
        "archive_sha256": sha256_file(pack_path),
        "external_manifest_sha256": sha256_file(manifest_path) if manifest_path and manifest_path.exists() else None,
        "file_count": len(manifest.get("files", [])),
        "tool_count": len(openai_tools),
        "openapi_path_count": len(openapi.get("paths", {})),
        "required_tools_present": [
            name for name in manifest.get("required_tool_names", []) if name in tool_names
        ],
        "supported_platforms": manifest.get("supported_platforms", []),
        "no_frontend_required": manifest.get("no_frontend_required"),
        "real_model_keys_stored_by_study_anything": manifest.get(
            "real_model_keys_stored_by_study_anything"
        ),
    }


def copy_worktree(source: Path, target: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "data",
        "*.pyc",
    )
    shutil.copytree(source, target, ignore=ignored)


def prepare_workspace(args: argparse.Namespace, work_root: Path) -> Path:
    if args.current_worktree:
        return ROOT
    workspace = work_root / "study-anything"
    if args.copy_worktree:
        copy_worktree(Path(args.repo).resolve(), workspace)
        return workspace
    run(["git", "clone", "--no-local", args.repo, str(workspace)], cwd=ROOT, timeout_seconds=180)
    if args.ref:
        run(["git", "checkout", args.ref], cwd=workspace, timeout_seconds=60)
    return workspace


def python_for_workspace(workspace: Path, args: argparse.Namespace) -> str:
    candidates = [
        args.python,
        str(workspace / ".venv" / "bin" / "python3"),
        str(workspace / ".venv" / "bin" / "python"),
        sys.executable,
        shutil.which("python3.12"),
        shutil.which("python3.11"),
        shutil.which("python3"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate_path = Path(candidate)
        if (candidate_path.is_absolute() or "/" in candidate) and not candidate_path.exists():
            continue
        completed = subprocess.run(
            [
                candidate,
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return candidate
    raise AdoptionProofError("Python 3.11+ is required for external adoption verification.")


def make_env(workspace: Path, work_root: Path, args: argparse.Namespace) -> dict[str, str]:
    api_port = free_port()
    venv = Path(args.venv) if args.venv else workspace / ".venv"
    if args.current_worktree and not args.venv and (ROOT / ".venv").exists():
        venv = ROOT / ".venv"
    python_bin = python_for_workspace(workspace, args)
    env = os.environ.copy()
    env.update(
        {
            "PYTHON_BIN": python_bin,
            "STUDY_ANYTHING_VENV": str(venv),
            "STUDY_ANYTHING_DATA_DIR": str(work_root / "skill-mode-data"),
            "STUDY_ANYTHING_RETRIEVAL_BACKEND": "memory",
            "API_PORT": str(api_port),
            "SKILL_API_HOST": "127.0.0.1",
            "STUDY_ANYTHING_API_BASE": f"http://127.0.0.1:{api_port}",
            "API_BASE": f"http://127.0.0.1:{api_port}",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    return env


def api_request(api_base: str, path: str) -> dict[str, Any]:
    req = Request(f"{api_base.rstrip('/')}{path}", method="GET")
    with urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api(api_base: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            if api_request(api_base, "/v1/health").get("status") == "ok":
                return
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise AdoptionProofError(f"API did not become healthy at {api_base}: {last_error}")


def run_runtime_checks(workspace: Path, env: dict[str, str], args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    run(["./scripts/launch_skill_mode.sh"], cwd=workspace, env=env, timeout_seconds=args.timeout_seconds)
    wait_for_api(env["API_BASE"], 60)
    python_bin = python_for_workspace(workspace, args)
    try:
        command_results: dict[str, Any] = {}
        checks = [
            (
                "operator_drill",
                [
                    python_bin,
                    "scripts/verify_platform_operator_drill.py",
                    "--pack",
                    str(Path(args.pack).resolve()),
                ],
                90,
            ),
            (
                "agent_eval_baseline",
                [python_bin, "scripts/verify_agent_eval_baseline.py", "--check"],
                90,
            ),
            (
                "commercial_readiness",
                [python_bin, "scripts/verify_commercial_readiness.py", "--api-base", env["API_BASE"]],
                90,
            ),
            (
                "adoption_telemetry",
                [
                    python_bin,
                    "scripts/verify_adoption_telemetry.py",
                    "--api-base",
                    env["API_BASE"],
                ],
                90,
            ),
            (
                "agent_gateway_hardening",
                [python_bin, "scripts/verify_agent_gateway_hardening.py"],
                90,
            ),
            (
                "notebooklm_obsidian_bridge_hardening",
                [python_bin, "scripts/verify_notebooklm_obsidian_bridge_hardening.py"],
                90,
            ),
            (
                "plugin_quarantine",
                [python_bin, "scripts/verify_plugin_quarantine.py"],
                90,
            ),
            (
                "security_recovery_hardening",
                [python_bin, "scripts/verify_security_recovery_hardening.py"],
                90,
            ),
            (
                "platform_submission_dry_run",
                [python_bin, "scripts/verify_platform_submission_dry_run.py"],
                90,
            ),
            (
                "platform_tools",
                [python_bin, "scripts/verify_platform_agent_tools.py"],
                args.timeout_seconds,
            ),
            (
                "platform_ecosystem",
                [python_bin, "scripts/verify_platform_ecosystem_eval_flow.py"],
                args.timeout_seconds,
            ),
            (
                "notebooklm_importer",
                [python_bin, "scripts/verify_importer_lesson_flow.py"],
                args.timeout_seconds,
            ),
            (
                "retrieval_eval_runner",
                [
                    python_bin,
                    "scripts/run_external_agent_evals.py",
                    "--tool",
                    "retrieval",
                    "--create-session",
                    "--required",
                    "--timeout-seconds",
                    "120",
                ],
                args.timeout_seconds,
            ),
            (
                "deepeval_runner",
                [
                    python_bin,
                    "scripts/run_external_agent_evals.py",
                    "--tool",
                    "deepeval",
                    "--create-session",
                    "--allow-native-quality-fallback",
                    "--required",
                    "--timeout-seconds",
                    "120",
                ],
                args.timeout_seconds,
            ),
        ]
        for label, command, timeout in checks:
            completed = run(command, cwd=workspace, env=env, timeout_seconds=timeout)
            command_results[label] = safe_json_from_stdout(label, completed.stdout)
        diagnostics = run(
            [
                python_bin,
                "scripts/diagnose_adoption.py",
                "--api-base",
                env["API_BASE"],
                "--ghcr-timeout-seconds",
                "5",
            ],
            cwd=workspace,
            env=env,
            timeout_seconds=90,
            required=False,
        )
        diagnosis = safe_json_from_stdout("diagnose_adoption", diagnostics.stdout)
        health = api_request(env["API_BASE"], "/v1/health")
        return {
            "runtime": "skill-mode",
            "api_base": env["API_BASE"],
            "health_version": health.get("version"),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "commands": {
                key: summarize_command_result(key, value) for key, value in command_results.items()
            },
            "diagnostics": summarize_diagnostics(diagnosis),
        }
    finally:
        run(["./scripts/stop_skill_mode.sh"], cwd=workspace, env=env, timeout_seconds=30, required=False)


def summarize_command_result(label: str, value: dict[str, Any]) -> dict[str, Any]:
    if label == "platform_ecosystem":
        return {
            "status": value.get("status"),
            "retrieval_quality_status": value.get("retrieval_quality_status"),
            "agent_quality_status": value.get("agent_quality_status"),
            "retrieval_eval_tool": value.get("retrieval_eval_tool"),
            "deepeval_tool": value.get("deepeval_tool"),
            "obsidian_schema": value.get("obsidian_schema"),
            "learning_package_schema": value.get("learning_package_schema"),
            "second_brain_schema": value.get("second_brain_schema"),
            "plugin_sdk_schema": value.get("plugin_sdk_schema"),
            "plugin_capability_index_schema": value.get("plugin_capability_index_schema"),
            "plugin_package_validation_schema": value.get("plugin_package_validation_schema"),
        }
    if label == "platform_tools":
        return {
            "status": value.get("status"),
            "tool_count": value.get("tool_count"),
            "manifest_schema": value.get("manifest_schema"),
            "agent_audit_status": value.get("agent_audit_status"),
            "commercial_readiness_schema": value.get("commercial_readiness_schema"),
            "adoption_telemetry_schema": value.get("adoption_telemetry_schema"),
            "pmf_readiness_schema": value.get("pmf_readiness_schema"),
            "quality_schema": value.get("quality_schema"),
            "plugin_sdk_schema": value.get("plugin_sdk_schema"),
            "plugin_capability_index_schema": value.get("plugin_capability_index_schema"),
            "plugin_package_validation_schema": value.get("plugin_package_validation_schema"),
        }
    if label == "plugin_quarantine":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "api_quarantine_lifecycle": (value.get("api") or {}).get("quarantine_lifecycle"),
            "api_install_lifecycle": (value.get("api") or {}).get("install_lifecycle"),
            "blocked_recommendation": (value.get("blocked_digest") or {}).get(
                "install_recommendation"
            ),
            "cli_lifecycle_status": (value.get("cli") or {}).get("lifecycle_status"),
            "cli_approved_lifecycle_status": (value.get("cli") or {}).get(
                "approved_lifecycle_status"
            ),
        }
    if label == "security_recovery_hardening":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "tamper_detected": (value.get("backup_manifest") or {}).get("tamper_detected"),
            "path_traversal_rejected": (value.get("backup_manifest") or {}).get(
                "path_traversal_rejected"
            ),
            "restore_preview_schema": (value.get("sync_restore_preview") or {}).get(
                "restore_preview_schema"
            ),
            "restore_api_enabled": (value.get("recovery_status") or {}).get(
                "restore_api_enabled"
            ),
        }
    if label == "platform_submission_dry_run":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "blocked_platforms": value.get("blocked_platforms"),
            "platforms": sorted((value.get("platforms") or {}).keys()),
            "report_is_redacted": (value.get("privacy") or {}).get("report_is_redacted"),
        }
    if label == "adoption_telemetry":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "api_checked": value.get("api_checked"),
            "telemetry_schema": (value.get("core") or {}).get("telemetry_schema"),
            "readiness_schema": (value.get("core") or {}).get("readiness_schema"),
        }
    if label == "commercial_readiness":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "readiness_schema": value.get("readiness_schema"),
            "readiness_status": value.get("readiness_status"),
            "hosted_paid_services": value.get("hosted_paid_services"),
        }
    if label == "operator_drill":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "pack_version": value.get("pack", {}).get("version"),
            "openai_tool_count": value.get("generated_tool_assets", {}).get("openai_tool_count"),
            "openapi_path_count": value.get("generated_tool_assets", {}).get("openapi_path_count"),
            "platforms": sorted(value.get("platforms", {}).keys()),
            "no_frontend_required": value.get("pack", {}).get("no_frontend_required"),
        }
    if label == "agent_eval_baseline":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "baseline_version": value.get("baseline_version"),
            "current_version": value.get("current_version"),
            "failed_checks": [
                check.get("check_id")
                for check in value.get("checks", [])
                if isinstance(check, dict) and check.get("status") != "pass"
            ],
            "external_eval_policy": value.get("external_eval_policy"),
        }
    if label == "notebooklm_obsidian_bridge_hardening":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "context_item_count": value.get("context_item_count"),
            "source_types": value.get("context_source_types"),
            "archive_file_count": (value.get("exports") or {}).get("archive_file_count"),
            "strict_second_brain_excludes_answers": (value.get("exports") or {}).get(
                "strict_second_brain_excludes_answers"
            ),
            "agent_endpoint_redacted_from_learning_package": (value.get("exports") or {}).get(
                "agent_endpoint_redacted_from_learning_package"
            ),
        }
    if label == "notebooklm_importer":
        return {
            "status": value.get("status"),
            "source_types": value.get("source_types"),
            "notebooklm_bridge_status": value.get("notebooklm_bridge_status"),
            "obsidian_schema": value.get("obsidian_schema"),
            "learning_package_schema": value.get("learning_package_schema"),
            "second_brain_schema": value.get("second_brain_schema"),
        }
    return {
        "status": value.get("status"),
        "tool": value.get("tool"),
        "framework": value.get("framework"),
        "schema_version": value.get("schema_version"),
        "report_status": value.get("report_status"),
    }


def summarize_diagnostics(value: dict[str, Any]) -> dict[str, Any]:
    checks = value.get("checks", [])
    summary = {
        "status": value.get("status"),
        "ok": [],
        "warnings": [],
        "blocking": [],
    }
    for check in checks:
        record = {
            "name": check.get("name"),
            "status": check.get("status"),
            "fix": check.get("fix"),
        }
        if check.get("status") == "ok":
            summary["ok"].append(record)
        elif check.get("status") == "warning":
            summary["warnings"].append(record)
        else:
            summary["blocking"].append(record)
    return summary


def assert_redacted(proof: dict[str, Any]) -> None:
    serialized = json.dumps(proof, ensure_ascii=False)
    forbidden = [
        "Private importer note",
        "Private platform browser/video context",
        "Private answer:",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    leaks = [item for item in forbidden if item in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}", serialized):
        leaks.append("secret-looking sk token")
    if re.search(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{12,}", serialized):
        leaks.append("secret-looking key/value text")
    if leaks:
        raise AdoptionProofError(f"Adoption proof leaked private data: {leaks}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=str(DEFAULT_PACK))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--ref")
    parser.add_argument("--copy-worktree", action="store_true")
    parser.add_argument("--current-worktree", action="store_true")
    parser.add_argument("--work-dir")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--python")
    parser.add_argument("--venv")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--target-minutes", type=float, default=15.0)
    args = parser.parse_args()

    started = time.monotonic()
    work_root = Path(args.work_dir) if args.work_dir else Path(
        tempfile.mkdtemp(prefix="study-anything-external-adoption-")
    )
    cleanup = not args.keep and args.work_dir is None
    try:
        pack = validate_adoption_pack(
            Path(args.pack),
            Path(args.manifest) if args.manifest else None,
        )
        workspace = prepare_workspace(args, work_root)
        env = make_env(workspace, work_root, args)
        runtime = run_runtime_checks(workspace, env, args)
        elapsed = round(time.monotonic() - started, 3)
        proof = {
            "schema_version": PROOF_SCHEMA,
            "status": "ok",
            "elapsed_seconds": elapsed,
            "target_minutes": args.target_minutes,
            "within_target_minutes": elapsed <= args.target_minutes * 60,
            "source": {
                "mode": "current_worktree"
                if args.current_worktree
                else "copy_worktree"
                if args.copy_worktree
                else "git_clone",
                "repo": args.repo,
                "ref": args.ref,
            },
            "pack": pack,
            "runtime": runtime,
            "privacy": {
                "redacted": True,
                "real_model_keys_stored_by_study_anything": False,
                "no_frontend_required": True,
            },
            "remediation": REMEDIATION,
        }
        assert_redacted(proof)
        print(json.dumps(proof, ensure_ascii=False, sort_keys=True))
    finally:
        if cleanup:
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_external_adoption failed: {exc}", file=sys.stderr)
        sys.exit(1)
