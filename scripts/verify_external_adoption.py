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
    "docs/agent-eval.md",
    "docs/eval-frameworks.md",
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
    "scripts/verify_external_agent_adapter_hardening.py",
    "scripts/verify_notebooklm_obsidian_bridge_hardening.py",
    "scripts/verify_plugin_quarantine.py",
    "scripts/verify_security_recovery_hardening.py",
    "scripts/verify_platform_submission_dry_run.py",
    "platform/generated/study-anything-operator-drill-transcript.json",
    "platform/generated/study-anything-platform-submission-dry-run.json",
    "scripts/verify_platform_manual_submission_rehearsal.py",
    "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
    "scripts/verify_first_lesson_authoring_kit.py",
    "platform/generated/study-anything-first-lesson-authoring-kit.json",
    "scripts/verify_external_eval_marketplace_harness.py",
    "platform/generated/study-anything-external-eval-harness.json",
    "scripts/verify_agent_eval_marketplace_enforcement.py",
    "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
    "scripts/verify_platform_adoption_feedback_diagnostics.py",
    "scripts/generate_platform_feedback_package.py",
    "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
    "platform/generated/study-anything-platform-feedback-package.json",
    "platform/generated/study-anything-platform-feedback-package.zip",
    "scripts/generate_platform_field_rehearsal.py",
    "scripts/verify_platform_field_rehearsal.py",
    "platform/generated/study-anything-platform-field-rehearsal.json",
    "scripts/generate_platform_support_triage.py",
    "scripts/verify_platform_support_triage.py",
    "platform/generated/study-anything-platform-support-triage.json",
    "scripts/generate_platform_onboarding_readiness.py",
    "scripts/verify_platform_onboarding_readiness.py",
    "platform/generated/study-anything-platform-onboarding-readiness.json",
    "platform/generated/study-anything-platform-triage-dashboard.json",
    "platform/generated/study-anything-platform-triage-dashboard.md",
    "scripts/generate_platform_public_support_status.py",
    "scripts/verify_platform_public_support_status.py",
    "platform/generated/study-anything-public-support-status.json",
    "platform/generated/study-anything-public-maintainer-dashboard.json",
    "platform/generated/study-anything-public-maintainer-dashboard.md",
    "docs/public-support-status.md",
    "scripts/generate_published_image_evidence.py",
    "scripts/verify_published_image_evidence.py",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-published-image-evidence.sha256",
    "docs/published-image-evidence.md",
    "scripts/generate_adopter_evidence_archive.py",
    "scripts/verify_adopter_evidence_archive.py",
    "platform/generated/study-anything-adopter-evidence-archive.json",
    "platform/generated/study-anything-adopter-evidence-archive.md",
    "platform/generated/study-anything-adopter-evidence-archive.zip",
    "platform/generated/study-anything-adopter-evidence-archive.sha256",
    "docs/adopter-evidence-archive.md",
    "scripts/generate_release_asset_adoption.py",
    "scripts/verify_release_asset_adoption.py",
    "platform/generated/study-anything-release-asset-adoption.json",
    "platform/generated/study-anything-release-asset-adoption.md",
    "platform/generated/study-anything-release-asset-adoption.zip",
    "platform/generated/study-anything-release-asset-adoption.sha256",
    "docs/release-asset-adoption.md",
    "fixtures/release-asset-adoption/asset-only-pass.json",
    "fixtures/release-asset-adoption/asset-missing.json",
    "fixtures/release-asset-adoption/digest-mismatch.json",
    "fixtures/release-asset-adoption/pack-corrupted.json",
    "fixtures/release-asset-adoption/published-evidence-missing.json",
    "fixtures/release-asset-adoption/network-unavailable.json",
    "fixtures/platform-release-blockers/tool_import_blocker.json",
    "fixtures/platform-release-blockers/local_gateway_blocker.json",
    "fixtures/platform-release-blockers/published_image_blocker.json",
    "fixtures/platform-release-blockers/agent_eval_blocker.json",
    "fixtures/platform-release-blockers/support_bundle_privacy_blocker.json",
    "fixtures/platform-status-links/intake.json",
    "fixtures/platform-status-links/needs-repro.json",
    "fixtures/platform-status-links/confirmed.json",
    "fixtures/platform-status-links/blocked-by-platform.json",
    "fixtures/platform-status-links/docs-fix.json",
    "fixtures/platform-status-links/release-blocker.json",
    "fixtures/platform-status-links/resolved.json",
    "fixtures/adopter-evidence-archive/successful-release.json",
    "fixtures/adopter-evidence-archive/local-ghcr-pull-timeout.json",
    "fixtures/adopter-evidence-archive/needs-repro-issue.json",
    "fixtures/adopter-evidence-archive/release-blocker.json",
    "fixtures/adopter-evidence-archive/platform-blocked.json",
    "fixtures/adopter-evidence-archive/resolved-support-case.json",
    "fixtures/published-image-evidence/manifest-pass-local-pull-timeout.json",
    "fixtures/published-image-evidence/manifest-missing-platform.json",
    "fixtures/published-image-evidence/docker-images-failed.json",
    "fixtures/published-image-evidence/ghcr-unavailable.json",
    "fixtures/published-image-evidence/remote-smoke-pass.json",
    "fixtures/published-image-evidence/remote-smoke-failed.json",
    ".github/ISSUE_TEMPLATE/platform_import_failure.md",
    ".github/ISSUE_TEMPLATE/local_gateway_failure.md",
    ".github/ISSUE_TEMPLATE/published_image_pull_failure.md",
    ".github/ISSUE_TEMPLATE/agent_eval_evidence_failure.md",
    ".github/ISSUE_TEMPLATE/docs_confusion.md",
    "fixtures/platform-support-tickets/platform_import_failure.json",
    "fixtures/platform-support-tickets/local_gateway_failure.json",
    "fixtures/platform-support-tickets/published_image_pull_failure.json",
    "fixtures/platform-support-tickets/agent_eval_evidence_failure.json",
    "fixtures/platform-support-tickets/docs_confusion.json",
    "docs/support-desk.md",
    "docs/adopter-onboarding.md",
    "docs/maintainer-rotation.md",
    "fixtures/platform-import-failures/schema_mismatch.json",
    "fixtures/platform-import-failures/missing_local_gateway.json",
    "fixtures/platform-import-failures/unsupported_auth_mode.json",
    "fixtures/platform-import-failures/tool_naming_drift.json",
    "fixtures/platform-import-failures/timeout.json",
    "fixtures/platform-import-failures/cors_localhost.json",
    "fixtures/platform-import-failures/package_corruption.json",
    "fixtures/platform-import-failures/version_drift.json",
    "scripts/verify_plugin_ecosystem_adoption_kit.py",
    "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
    "scripts/verify_deployment_hardening.py",
    "platform/generated/study-anything-deployment-hardening.json",
    "scripts/verify_learning_enrichment_bridge.py",
    "platform/generated/study-anything-learning-enrichment-bridge.json",
    "plugins/registry.json",
    "plugins/example-note-importer/plugin.json",
    "plugins/example-note-importer/plugin.py",
    "plugins/example-web-importer/plugin.json",
    "plugins/example-web-importer/plugin.py",
    "plugins/example-enrichment-importer/plugin.json",
    "plugins/example-enrichment-importer/plugin.py",
    "plugins/example-exporter/plugin.json",
    "plugins/example-exporter/plugin.py",
    "plugins/example-agent-provider/plugin.json",
    "plugins/example-agent-provider/plugin.py",
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
                "docs/support-desk.md",
                "docs/adopter-onboarding.md",
                "docs/maintainer-rotation.md",
                "docs/public-support-status.md",
                "docs/adopter-evidence-archive.md",
                "docs/published-image-evidence.md",
                "docs/release-asset-adoption.md",
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
        "platform-onboarding-readiness-v1",
        "platform-triage-dashboard-v1",
        "public-support-status-v1",
        "public-maintainer-dashboard-v1",
        "public-status-linkage-fixture-v1",
        "published-image-evidence-v1",
        "published-image-evidence-fixture-v1",
        "adopter-evidence-archive-v1",
        "adopter-evidence-fixture-v1",
        "release-asset-adoption-v1",
        "release-asset-adoption-fixture-v1",
        "release-asset-adoption-proof-v1",
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
    run(["sh", "scripts/launch_skill_mode.sh"], cwd=workspace, env=env, timeout_seconds=args.timeout_seconds)
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
                "external_agent_adapter_hardening",
                [python_bin, "scripts/verify_external_agent_adapter_hardening.py"],
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
                "platform_manual_submission_rehearsal",
                [python_bin, "scripts/verify_platform_manual_submission_rehearsal.py"],
                90,
            ),
            (
                "first_lesson_authoring_kit",
                [python_bin, "scripts/verify_first_lesson_authoring_kit.py"],
                90,
            ),
            (
                "external_eval_marketplace_harness",
                [python_bin, "scripts/verify_external_eval_marketplace_harness.py"],
                90,
            ),
            (
                "agent_eval_marketplace_enforcement",
                [python_bin, "scripts/verify_agent_eval_marketplace_enforcement.py"],
                90,
            ),
            (
                "platform_adoption_feedback_diagnostics",
                [python_bin, "scripts/verify_platform_adoption_feedback_diagnostics.py"],
                90,
            ),
            (
                "platform_field_rehearsal",
                [python_bin, "scripts/verify_platform_field_rehearsal.py"],
                90,
            ),
            (
                "platform_support_triage",
                [python_bin, "scripts/verify_platform_support_triage.py"],
                90,
            ),
            (
                "platform_onboarding_readiness",
                [python_bin, "scripts/verify_platform_onboarding_readiness.py"],
                90,
            ),
            (
                "platform_public_support_status",
                [python_bin, "scripts/verify_platform_public_support_status.py"],
                90,
            ),
            (
                "published_image_evidence",
                [python_bin, "scripts/verify_published_image_evidence.py"],
                90,
            ),
            (
                "release_asset_adoption",
                [
                    python_bin,
                    "scripts/verify_release_asset_adoption.py",
                    "--fixture",
                    "fixtures/release-asset-adoption/asset-only-pass.json",
                    "--asset-dir",
                    "platform/generated",
                    "--runtime",
                    "metadata-only",
                ],
                90,
            ),
            (
                "plugin_ecosystem_adoption_kit",
                [python_bin, "scripts/verify_plugin_ecosystem_adoption_kit.py"],
                90,
            ),
            (
                "deployment_hardening",
                [python_bin, "scripts/verify_deployment_hardening.py"],
                90,
            ),
            (
                "learning_enrichment_bridge",
                [python_bin, "scripts/verify_learning_enrichment_bridge.py"],
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
        run(["sh", "scripts/stop_skill_mode.sh"], cwd=workspace, env=env, timeout_seconds=30, required=False)


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
    if label == "platform_manual_submission_rehearsal":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "operator_step_count": len(value.get("operator_steps", [])),
            "time_budget_minutes": (value.get("time_budget") or {}).get("target_minutes"),
            "report_is_redacted": (value.get("privacy_assertions") or {}).get(
                "report_is_redacted"
            ),
        }
    if label == "first_lesson_authoring_kit":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "prompt_languages": sorted((value.get("copyable_prompts") or {}).keys()),
            "tool_call_count": len(value.get("tool_call_sequence", [])),
            "time_budget_minutes": (value.get("time_budget") or {}).get("target_minutes"),
            "report_is_redacted": (value.get("privacy_assertions") or {}).get(
                "report_is_redacted"
            ),
        }
    if label == "external_eval_marketplace_harness":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "adapter_ids": [
                item.get("adapter_id")
                for item in value.get("external_adapters", [])
                if isinstance(item, dict)
            ],
            "native_gate_count": len(value.get("native_fast_gates", [])),
            "sample_case_count": len(value.get("sample_eval_cases", [])),
            "report_is_redacted": (value.get("privacy_assertions") or {}).get(
                "report_is_redacted"
            ),
        }
    if label == "agent_eval_marketplace_enforcement":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "adapter_ids": [
                item.get("adapter_id")
                for item in value.get("external_judge_contracts", [])
                if isinstance(item, dict)
            ],
            "required_exit_nonzero": (
                (value.get("runtime_diagnostics") or {})
                .get("promptfoo_missing_runtime", {})
                .get("required_exit_nonzero")
            ),
            "adoption_pack_included": (value.get("adoption_pack") or {}).get("included"),
            "report_is_redacted": (value.get("privacy_assertions") or {}).get(
                "report_is_redacted"
            ),
        }
    if label == "platform_adoption_feedback_diagnostics":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "diagnostic_category_count": len(
                (value.get("diagnostic_contract") or {}).get("diagnostic_categories", [])
            ),
            "feedback_package_included": (value.get("feedback_package") or {}).get("included"),
            "adoption_pack_included": (value.get("adoption_pack") or {}).get("included"),
            "feedback_package_is_redacted": (value.get("privacy_assertions") or {}).get(
                "feedback_package_is_redacted"
            ),
        }
    if label == "platform_field_rehearsal":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "platform_count": (value.get("field_rehearsal") or {}).get("platform_count"),
            "quirk_count": (value.get("field_rehearsal") or {}).get("quirk_count"),
            "fixture_count": (value.get("field_rehearsal") or {}).get("fixture_count"),
            "feedback_upload_is_manual": (value.get("privacy_assertions") or {}).get(
                "feedback_upload_is_manual"
            ),
        }
    if label == "platform_support_triage":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "issue_template_count": (value.get("support_triage") or {}).get("issue_template_count"),
            "ticket_fixture_count": (value.get("support_triage") or {}).get("ticket_fixture_count"),
            "playbook_entry_count": (value.get("support_triage") or {}).get("playbook_entry_count"),
            "support_upload_is_manual": (value.get("privacy_assertions") or {}).get(
                "support_upload_is_manual"
            ),
        }
    if label == "platform_onboarding_readiness":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "walkthrough_count": (value.get("onboarding_readiness") or {}).get(
                "walkthrough_count"
            ),
            "sla_label_count": (value.get("onboarding_readiness") or {}).get(
                "sla_label_count"
            ),
            "release_blocker_fixture_count": (
                value.get("onboarding_readiness") or {}
            ).get("release_blocker_fixture_count"),
            "dashboard_schema": (value.get("triage_dashboard") or {}).get("schema_version"),
            "support_upload_is_manual": (value.get("privacy_assertions") or {}).get(
                "support_upload_is_manual"
            ),
        }
    if label == "plugin_ecosystem_adoption_kit":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "bundled_plugin_count": len(value.get("bundled_plugins", [])),
            "registry_schema": (value.get("plugin_registry") or {}).get("schema_version"),
            "digest_verified_count": (value.get("plugin_registry") or {}).get("digest_verified_count"),
            "default_install_action": (value.get("trust_policy") or {}).get("default_install_action"),
            "report_is_redacted": (value.get("privacy_assertions") or {}).get(
                "report_is_redacted"
            ),
        }
    if label == "learning_enrichment_bridge":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "source_types": sorted(
                (value.get("context_contract") or {}).get("source_types", [])
            ),
            "html_article_schema": (
                (value.get("exports") or {}).get("html_artifact", {}).get("article_schema")
            ),
            "report_is_redacted": (value.get("privacy_assertions") or {}).get(
                "report_is_redacted"
            ),
        }
    if label == "deployment_hardening":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "deployment_modes": [
                item.get("id")
                for item in value.get("deployment_modes", [])
                if isinstance(item, dict)
            ],
            "published_image_fallback": (value.get("published_image_smoke") or {}).get(
                "fallback_is_acceptance_when_ci_manifest_and_release_check_pass"
            ),
            "failure_class_count": len(value.get("failure_classes", [])),
            "report_is_redacted": (value.get("privacy_assertions") or {}).get(
                "report_is_redacted"
            ),
        }
    if label == "published_image_evidence":
        evidence = value.get("published_image_evidence") or {}
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "evidence_schema": evidence.get("schema_version"),
            "fixture_count": evidence.get("fixture_count"),
            "classification_count": evidence.get("classification_count"),
            "local_paths_in_report": (value.get("privacy_assertions") or {}).get(
                "local_absolute_paths_in_report"
            ),
        }
    if label == "release_asset_adoption":
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "classification": value.get("classification"),
            "evidence_schema": (value.get("acceptance") or {}).get("evidence_schema"),
            "fixture_schema": (value.get("acceptance") or {}).get("fixture_schema"),
            "runtime": (value.get("acceptance") or {}).get("runtime"),
            "asset_count": value.get("asset_count"),
            "pack_schema": (value.get("pack") or {}).get("schema_version"),
            "published_image_evidence_schema": (value.get("pack") or {}).get(
                "published_image_evidence_schema"
            ),
        }
    if label == "external_agent_adapter_hardening":
        external_eval = value.get("external_agent_eval") or {}
        return {
            "status": value.get("status"),
            "schema_version": value.get("schema_version"),
            "version": value.get("version"),
            "used_external_agent": external_eval.get("used_external_agent"),
            "used_fake_agent": external_eval.get("used_fake_agent"),
            "native_fast_gate_status": external_eval.get("native_fast_gate_status"),
            "bad_output_diagnostics_covered": (value.get("release_gate") or {}).get(
                "bad_output_diagnostics_covered"
            ),
            "secret_like_metadata_values_redacted": (value.get("privacy") or {}).get(
                "secret_like_metadata_values_redacted"
            ),
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
