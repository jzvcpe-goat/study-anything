#!/usr/bin/env python3
"""Verify manual platform-submission rehearsal handoff evidence."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "platform-manual-submission-rehearsal-v1"
RELEASE_VERSION = "v0.3.22-alpha"
DEFAULT_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-platform-manual-submission-rehearsal.json"
)
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

PLATFORM_IDS = ("codex", "kimi", "workbuddy")
REQUIRED_REPORT_EVIDENCE = [
    "platform/generated/study-anything-platform-submission-dry-run.json",
    "platform/generated/study-anything-operator-drill-transcript.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "platform/generated/study-anything-external-eval-harness.json",
    "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
    "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
    "platform/generated/study-anything-platform-feedback-package.json",
    "platform/generated/study-anything-platform-feedback-package.zip",
    "platform/generated/study-anything-platform-field-rehearsal.json",
    "platform/generated/study-anything-public-support-status.json",
    "platform/generated/study-anything-public-maintainer-dashboard.json",
    "platform/generated/study-anything-public-maintainer-dashboard.md",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-published-image-evidence.sha256",
    "platform/generated/study-anything-adopter-evidence-archive.json",
    "platform/generated/study-anything-adopter-evidence-archive.md",
    "platform/generated/study-anything-adopter-evidence-archive.zip",
    "platform/generated/study-anything-adopter-evidence-archive.sha256",
    "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
    "platform/generated/study-anything-deployment-hardening.json",
    "platform/generated/study-anything-learning-enrichment-bridge.json",
]
REQUIRED_OPERATOR_ASSETS = [
    "platform/ecosystem-submission.json",
    "platform/study-anything-platform-tools.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/generated/study-anything-tool-catalog.md",
    "docs/use-with-kimi.md",
    "docs/platform-agent-integrations.md",
    "docs/adoption.md",
    "docs/ecosystem-submission.md",
    "scripts/verify_external_adoption.py",
    "scripts/verify_platform_submission_dry_run.py",
    "scripts/verify_external_agent_adapter_hardening.py",
    "scripts/verify_platform_operator_drill.py",
    "scripts/verify_platform_manual_submission_rehearsal.py",
    "scripts/verify_first_lesson_authoring_kit.py",
    "scripts/verify_external_eval_marketplace_harness.py",
    "scripts/verify_agent_eval_marketplace_enforcement.py",
    "scripts/verify_platform_adoption_feedback_diagnostics.py",
    "scripts/generate_platform_feedback_package.py",
    "scripts/generate_platform_field_rehearsal.py",
    "scripts/verify_platform_field_rehearsal.py",
    "scripts/generate_platform_public_support_status.py",
    "scripts/verify_platform_public_support_status.py",
    "scripts/generate_published_image_evidence.py",
    "scripts/verify_published_image_evidence.py",
    "scripts/generate_adopter_evidence_archive.py",
    "scripts/verify_adopter_evidence_archive.py",
    "scripts/verify_plugin_ecosystem_adoption_kit.py",
    "scripts/verify_deployment_hardening.py",
    "scripts/verify_learning_enrichment_bridge.py",
    "platform/generated/study-anything-first-lesson-authoring-kit.json",
    "platform/generated/study-anything-external-eval-harness.json",
    "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
    "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
    "platform/generated/study-anything-platform-feedback-package.json",
    "platform/generated/study-anything-platform-feedback-package.zip",
    "platform/generated/study-anything-platform-field-rehearsal.json",
    "platform/generated/study-anything-public-support-status.json",
    "platform/generated/study-anything-public-maintainer-dashboard.json",
    "platform/generated/study-anything-public-maintainer-dashboard.md",
    "docs/public-support-status.md",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-published-image-evidence.sha256",
    "docs/published-image-evidence.md",
    "platform/generated/study-anything-adopter-evidence-archive.json",
    "platform/generated/study-anything-adopter-evidence-archive.md",
    "platform/generated/study-anything-adopter-evidence-archive.zip",
    "platform/generated/study-anything-adopter-evidence-archive.sha256",
    "docs/adopter-evidence-archive.md",
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
    "fixtures/platform-import-failures/schema_mismatch.json",
    "fixtures/platform-import-failures/missing_local_gateway.json",
    "fixtures/platform-import-failures/unsupported_auth_mode.json",
    "fixtures/platform-import-failures/tool_naming_drift.json",
    "fixtures/platform-import-failures/timeout.json",
    "fixtures/platform-import-failures/cors_localhost.json",
    "fixtures/platform-import-failures/package_corruption.json",
    "fixtures/platform-import-failures/version_drift.json",
    "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
    "platform/generated/study-anything-deployment-hardening.json",
    "platform/generated/study-anything-learning-enrichment-bridge.json",
    "scripts/openai_compatible_agent_gateway.py",
    "scripts/study_anything_cli.py",
    "scripts/run_skill_mode_demo.sh",
]
REQUIRED_PACK_COMMAND = "verify_platform_manual_submission_rehearsal.py --check"
REQUIRED_EVIDENCE = (
    "platform_manual_submission_rehearsal.schema_version == platform-manual-submission-rehearsal-v1"
)
PUBLIC_STATUS_EVIDENCE = (
    "public_support_status.schema_version == public-support-status-v1",
    "public_maintainer_dashboard.schema_version == public-maintainer-dashboard-v1",
    "public_status_linkage_fixture.schema_version == public-status-linkage-fixture-v1",
    "published_image_evidence.schema_version == published-image-evidence-v1",
    "published_image_evidence_fixture.schema_version == published-image-evidence-fixture-v1",
    "adopter_evidence_archive.schema_version == adopter-evidence-archive-v1",
    "adopter_evidence_fixture.schema_version == adopter-evidence-fixture-v1",
)
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private platform browser/video context",
    "raw source text returned",
]


class ManualSubmissionRehearsalError(RuntimeError):
    """Readable manual-submission rehearsal failure."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ManualSubmissionRehearsalError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManualSubmissionRehearsalError(f"JSON object expected: {path}")
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise ManualSubmissionRehearsalError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise ManualSubmissionRehearsalError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise ManualSubmissionRehearsalError(
                    f"Adoption pack archive should have one root, got {sorted(roots)}"
                )
            archive.extractall(tmp_root)
        return tmp_root / next(iter(roots))
    return ROOT


def safe_relative(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ManualSubmissionRehearsalError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> None:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise ManualSubmissionRehearsalError(f"Required rehearsal asset is missing: {relative_path}")


def operation_ids(openapi: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for methods in openapi.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if isinstance(operation, dict) and operation.get("operationId"):
                found.add(str(operation["operationId"]))
    return found


def validate_tool_assets(root: Path) -> dict[str, Any]:
    manifest = read_json(safe_relative(root, "platform/study-anything-platform-tools.json"))
    required_tools = [
        str(tool.get("name"))
        for tool in manifest.get("tools", [])
        if isinstance(tool, dict) and tool.get("name")
    ]
    openai_tools = json.loads(
        safe_relative(root, "platform/generated/study-anything-openai-tools.json").read_text(
            encoding="utf-8"
        )
    )
    openapi = read_json(safe_relative(root, "platform/generated/study-anything-platform-openapi.json"))
    if not isinstance(openai_tools, list):
        raise ManualSubmissionRehearsalError("OpenAI-compatible tool asset must be a list.")
    openai_names = {
        str(item.get("function", {}).get("name"))
        for item in openai_tools
        if isinstance(item, dict)
    }
    openapi_names = operation_ids(openapi)
    missing = sorted(set(required_tools) - openai_names - openapi_names)
    if missing:
        raise ManualSubmissionRehearsalError(f"Tool import assets miss required tools: {missing}")
    if openapi.get("components", {}).get("securitySchemes"):
        raise ManualSubmissionRehearsalError("Platform OpenAPI import must not require API keys.")
    return {
        "openai_tool_count": len(openai_tools),
        "openapi_path_count": len(openapi.get("paths", {})),
        "required_tool_count": len(required_tools),
        "management_endpoints_exposed": False,
    }


def sanitize_command(command: str) -> str:
    sanitized = command.replace("http://127.0.0.1:8787/invoke", "${AGENT_ENDPOINT}")
    sanitized = sanitized.replace("http://127.0.0.1:8787", "${AGENT_ENDPOINT}")
    sanitized = re.sub(r"AGENT_ENDPOINT=\S+", "AGENT_ENDPOINT=${USER_OWNED_AGENT_ENDPOINT}", sanitized)
    return sanitized


def validate_platform_pack(root: Path, platform_id: str) -> dict[str, Any]:
    pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
    if pack.get("schema_version") != "study-anything-platform-pack-v1":
        raise ManualSubmissionRehearsalError(f"{platform_id} pack schema drifted.")
    commands = [str(command) for command in pack.get("local_verification_commands", [])]
    command_text = "\n".join(commands)
    if REQUIRED_PACK_COMMAND not in command_text:
        raise ManualSubmissionRehearsalError(
            f"{platform_id} pack must include {REQUIRED_PACK_COMMAND}."
        )
    evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
    if REQUIRED_EVIDENCE not in evidence:
        raise ManualSubmissionRehearsalError(f"{platform_id} pack is missing manual rehearsal evidence.")
    for item in PUBLIC_STATUS_EVIDENCE:
        if item not in evidence:
            raise ManualSubmissionRehearsalError(f"{platform_id} pack is missing public status evidence {item}.")
    return {
        "platform_id": platform_id,
        "integration_mode": pack.get("integration_mode"),
        "status": "ready_for_manual_rehearsal",
        "entrypoints": pack.get("entrypoints", {}),
        "import_assets": pack.get("import_assets", []),
        "commands": [sanitize_command(command) for command in commands],
        "acceptance_evidence_count": len(evidence),
    }


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise ManualSubmissionRehearsalError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise ManualSubmissionRehearsalError(
            f"Ecosystem submission version must be {RELEASE_VERSION}."
        )
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    for asset in (
        "scripts/verify_platform_manual_submission_rehearsal.py",
        "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
        "scripts/verify_first_lesson_authoring_kit.py",
        "platform/generated/study-anything-first-lesson-authoring-kit.json",
        "scripts/verify_plugin_ecosystem_adoption_kit.py",
        "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
        "scripts/verify_deployment_hardening.py",
        "platform/generated/study-anything-deployment-hardening.json",
        "scripts/verify_learning_enrichment_bridge.py",
        "platform/generated/study-anything-learning-enrichment-bridge.json",
        "scripts/verify_agent_eval_marketplace_enforcement.py",
        "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
        "scripts/verify_platform_adoption_feedback_diagnostics.py",
        "scripts/generate_platform_feedback_package.py",
        "scripts/generate_platform_field_rehearsal.py",
        "scripts/verify_platform_field_rehearsal.py",
        "scripts/generate_platform_public_support_status.py",
        "scripts/verify_platform_public_support_status.py",
        "scripts/generate_published_image_evidence.py",
        "scripts/verify_published_image_evidence.py",
        "scripts/generate_adopter_evidence_archive.py",
        "scripts/verify_adopter_evidence_archive.py",
        "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
        "platform/generated/study-anything-platform-feedback-package.json",
        "platform/generated/study-anything-platform-feedback-package.zip",
        "platform/generated/study-anything-platform-field-rehearsal.json",
        "platform/generated/study-anything-public-support-status.json",
        "platform/generated/study-anything-public-maintainer-dashboard.json",
        "platform/generated/study-anything-public-maintainer-dashboard.md",
        "docs/public-support-status.md",
        "platform/generated/study-anything-published-image-evidence.json",
        "platform/generated/study-anything-published-image-evidence.md",
        "platform/generated/study-anything-published-image-evidence.zip",
        "platform/generated/study-anything-published-image-evidence.sha256",
        "docs/published-image-evidence.md",
        "platform/generated/study-anything-adopter-evidence-archive.json",
        "platform/generated/study-anything-adopter-evidence-archive.md",
        "platform/generated/study-anything-adopter-evidence-archive.zip",
        "platform/generated/study-anything-adopter-evidence-archive.sha256",
        "docs/adopter-evidence-archive.md",
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
    ):
        if asset not in shared_assets:
            raise ManualSubmissionRehearsalError(f"Ecosystem submission missing shared asset {asset}.")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    if "verify_platform_manual_submission_rehearsal.py --check" not in command_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission missing manual rehearsal check.")
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    if SCHEMA_VERSION not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove manual rehearsal schema.")
    if "deployment-hardening-verification-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove deployment hardening schema.")
    if "learning-enrichment-bridge-verification-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove learning enrichment bridge schema.")
    if "agent-eval-marketplace-enforcement-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove Agent eval marketplace enforcement schema.")
    if "platform-adoption-feedback-diagnostics-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove platform adoption feedback diagnostics schema.")
    if "platform-feedback-package-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove platform feedback package schema.")
    if "platform-field-adoption-rehearsal-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove platform field rehearsal schema.")
    if "platform-import-failure-fixture-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove platform import failure fixture schema.")
    if "public-support-status-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove public support status schema.")
    if "public-maintainer-dashboard-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove public maintainer dashboard schema.")
    if "public-status-linkage-fixture-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove public status linkage schema.")
    if "published-image-evidence-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove published-image evidence schema.")
    if "published-image-evidence-fixture-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove published-image evidence fixture schema.")
    if "adopter-evidence-archive-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove adopter evidence archive schema.")
    if "adopter-evidence-fixture-v1" not in prove_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission must prove adopter evidence fixture schema.")
    if "verify_platform_public_support_status.py --check" not in command_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission missing public support status check.")
    if "verify_published_image_evidence.py --check" not in command_text:
        raise ManualSubmissionRehearsalError("Ecosystem submission missing published-image evidence check.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "platform_count": len(submission.get("submissions", [])),
        "no_frontend_required": (submission.get("project") or {}).get(
            "standalone_frontend_required"
        )
        is False,
    }


def validate_existing_reports(root: Path) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    expected = {
        "platform_submission_dry_run": (
            "platform/generated/study-anything-platform-submission-dry-run.json",
            "platform-submission-dry-run-v1",
        ),
        "operator_drill": (
            "platform/generated/study-anything-operator-drill-transcript.json",
            "study-anything-operator-drill-v1",
        ),
        "deployment_hardening": (
            "platform/generated/study-anything-deployment-hardening.json",
            "deployment-hardening-verification-v1",
        ),
        "learning_enrichment_bridge": (
            "platform/generated/study-anything-learning-enrichment-bridge.json",
            "learning-enrichment-bridge-verification-v1",
        ),
        "agent_eval_marketplace_enforcement": (
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            "agent-eval-marketplace-enforcement-v1",
        ),
        "platform_adoption_feedback_diagnostics": (
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            "platform-adoption-feedback-diagnostics-v1",
        ),
        "platform_feedback_package": (
            "platform/generated/study-anything-platform-feedback-package.json",
            "platform-feedback-package-v1",
        ),
        "platform_field_rehearsal": (
            "platform/generated/study-anything-platform-field-rehearsal.json",
            "platform-field-adoption-rehearsal-v1",
        ),
        "public_support_status": (
            "platform/generated/study-anything-public-support-status.json",
            "public-support-status-v1",
        ),
        "public_maintainer_dashboard": (
            "platform/generated/study-anything-public-maintainer-dashboard.json",
            "public-maintainer-dashboard-v1",
        ),
    }
    for label, (relative_path, schema) in expected.items():
        report = read_json(safe_relative(root, relative_path))
        if report.get("schema_version") != schema:
            raise ManualSubmissionRehearsalError(f"{label} schema drifted.")
        reports[label] = {"schema_version": schema, "status": report.get("status")}
    return reports


def operator_steps() -> list[dict[str, Any]]:
    return [
        {
            "step_id": "unpack_adoption_pack",
            "operator_action": "Unzip the adoption pack and open ADOPTION_PACK_README.md plus manifest.json.",
            "command": "unzip study-anything-platform-adoption-pack.zip -d /tmp/study-anything-pack",
            "expected_outputs": ["manifest schema study-anything-platform-adoption-pack-v1"],
            "evidence_paths": ["manifest.json", "ADOPTION_PACK_README.md"],
            "failure_remediation": ["Regenerate the pack with generate_platform_adoption_pack.py."],
        },
        {
            "step_id": "import_tools",
            "operator_action": "Import OpenAPI or OpenAI-compatible tool assets into the host platform.",
            "command": "platform import platform/generated/study-anything-platform-openapi.json",
            "expected_outputs": ["tool names start with study_anything_", "no API-key security scheme"],
            "evidence_paths": [
                "platform/generated/study-anything-platform-openapi.json",
                "platform/generated/study-anything-openai-tools.json",
            ],
            "failure_remediation": ["Use the tool catalog when the host OpenAPI importer is incomplete."],
        },
        {
            "step_id": "start_runtime_health",
            "operator_action": "Start Skill Mode or the published Docker image and verify /v1/health.",
            "command": "./scripts/launch_skill_mode.sh && curl ${STUDY_ANYTHING_API_BASE}/v1/health",
            "expected_outputs": ["health status ok", "version matches the pack release"],
            "evidence_paths": ["scripts/launch_skill_mode.sh", "docs/self-hosting.md"],
            "failure_remediation": ["Run scripts/diagnose_adoption.py and follow the returned plan."],
        },
        {
            "step_id": "configure_user_owned_http_agent",
            "operator_action": "Point Study Anything at the user's local/private HTTP Agent gateway.",
            "command": "python3 scripts/study_anything_cli.py agent-add-http --endpoint ${USER_OWNED_AGENT_ENDPOINT} --set-default",
            "expected_outputs": ["provider saved", "capabilities include quiz.generate and answer.grade"],
            "evidence_paths": ["docs/use-with-kimi.md", "docs/platform-agent-integrations.md"],
            "failure_remediation": ["Run verify_agent_gateway_hardening.py before sharing evidence."],
        },
        {
            "step_id": "run_first_lesson",
            "operator_action": "Run a first lesson with fake demo or the user's HTTP Agent and collect mastery.",
            "command": "API_BASE=${STUDY_ANYTHING_API_BASE} python3 scripts/verify_platform_lesson_flow.py",
            "expected_outputs": ["stage completed", "agent audit verified", "quality status pass"],
            "evidence_paths": ["scripts/verify_platform_lesson_flow.py"],
            "failure_remediation": ["Fallback to run_skill_mode_demo.sh to separate runtime issues from Agent issues."],
        },
        {
            "step_id": "export_learning_evidence",
            "operator_action": "Export learning package, Obsidian markdown, and second-brain handoff evidence.",
            "command": "API_BASE=${STUDY_ANYTHING_API_BASE} python3 scripts/verify_platform_ecosystem_eval_flow.py",
            "expected_outputs": [
                "learning-package-v1",
                "obsidian-markdown-export-v1",
                "second-brain-handoff-v1",
            ],
            "evidence_paths": ["docs/second-brain-handoff.md", "docs/obsidian-export.md"],
            "failure_remediation": ["Keep user-owned exports local; share only redacted schema evidence."],
        },
        {
            "step_id": "review_plugin_ecosystem",
            "operator_action": "Review bundled plugin examples, registry digests, and quarantine-first trust policy before proposing any plugin install.",
            "command": "python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check",
            "expected_outputs": [
                "plugin-ecosystem-adoption-kit-v1",
                "all bundled plugin digests verified",
                "entrypoints not executed",
            ],
            "evidence_paths": [
                "plugins/registry.json",
                "docs/plugins.md",
                "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
            ],
            "failure_remediation": ["Run verify_plugin_quarantine.py and regenerate the adoption pack before submitting."],
        },
        {
            "step_id": "review_deployment_path",
            "operator_action": "Verify Skill Mode, published-image, source-build, Docker/Compose diagnostics, GHCR fallback, and Agent endpoint recovery before asking an external platform user to deploy.",
            "command": "python3 scripts/verify_deployment_hardening.py --check",
            "expected_outputs": [
                "deployment-hardening-verification-v1",
                "Skill Mode, published image, and source build modes present",
                "GHCR pull timeout fallback documented",
            ],
            "evidence_paths": [
                "scripts/verify_deployment_hardening.py",
                "platform/generated/study-anything-deployment-hardening.json",
                "docs/self-hosting.md",
            ],
            "failure_remediation": ["Run scripts/diagnose_adoption.py and prefer Skill Mode or published images for first-run users."],
        },
        {
            "step_id": "verify_learning_enrichment_bridge",
            "operator_action": "Verify the platform Agent enrichment, HTML micro-lesson, NotebookLM manual bridge, Obsidian export, and second-brain handoff path.",
            "command": "python3 scripts/verify_learning_enrichment_bridge.py --check",
            "expected_outputs": [
                "learning-enrichment-bridge-verification-v1",
                "web/document/video/app/Markdown/Obsidian source coverage",
                "strict second-brain handoff excludes learner answers",
            ],
            "evidence_paths": [
                "scripts/verify_learning_enrichment_bridge.py",
                "platform/generated/study-anything-learning-enrichment-bridge.json",
                "docs/learning-enrichment.md",
                "docs/notebooklm-bridge.md",
            ],
            "failure_remediation": ["Run verify_notebooklm_obsidian_bridge_hardening.py to isolate privacy validation failures."],
        },
        {
            "step_id": "verify_agent_eval_marketplace_enforcement",
            "operator_action": "Verify native Agent eval gates and optional external judge contracts before submitting to an external platform or marketplace.",
            "command": "python3 scripts/verify_agent_eval_marketplace_enforcement.py --check",
            "expected_outputs": [
                "agent-eval-marketplace-enforcement-v1",
                "optional external judge runtimes fail as skipped evidence unless required",
                "required judge mode exits non-zero when a configured judge is missing or invalid",
            ],
            "evidence_paths": [
                "scripts/verify_agent_eval_marketplace_enforcement.py",
                "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
                "docs/agent-eval.md",
                "docs/eval-frameworks.md",
            ],
            "failure_remediation": [
                "Keep judge and model credentials in the operator's Agent environment.",
                "Use native fast gates as the baseline and rerun run_external_agent_evals.py with --required only after the external judge runtime is installed.",
            ],
        },
        {
            "step_id": "collect_platform_feedback_package",
            "operator_action": "Verify platform import diagnostics and generate a local-only redacted feedback package before sharing adoption failures.",
            "command": "python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check && python3 scripts/generate_platform_feedback_package.py --check",
            "expected_outputs": [
                "platform-adoption-feedback-diagnostics-v1",
                "platform-feedback-package-v1",
                "no source text, answers, prompts, personal profiles, or secrets",
            ],
            "evidence_paths": [
                "scripts/verify_platform_adoption_feedback_diagnostics.py",
                "scripts/generate_platform_feedback_package.py",
                "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
                "platform/generated/study-anything-platform-feedback-package.json",
                "platform/generated/study-anything-platform-feedback-package.zip",
                "docs/adoption.md",
            ],
            "failure_remediation": [
                "Run diagnose_adoption.py first, then regenerate the feedback package after the import failure is categorized.",
            ],
        },
        {
            "step_id": "run_platform_field_rehearsal",
            "operator_action": "Verify Kimi, Codex, WorkBuddy, and generic OpenAPI import rehearsals plus the mock failed-import fixture catalog before sharing the pack with external users.",
            "command": "python3 scripts/generate_platform_field_rehearsal.py --check && python3 scripts/verify_platform_field_rehearsal.py --check",
            "expected_outputs": [
                "platform-field-adoption-rehearsal-v1",
                "platform-import-failure-fixture-v1",
                "schema mismatch, gateway, auth, naming, timeout, localhost, package corruption, and version drift fixtures",
            ],
            "evidence_paths": [
                "scripts/generate_platform_field_rehearsal.py",
                "scripts/verify_platform_field_rehearsal.py",
                "platform/generated/study-anything-platform-field-rehearsal.json",
                "fixtures/platform-import-failures/schema_mismatch.json",
                "fixtures/platform-import-failures/version_drift.json",
                "docs/platform-agent-integrations.md",
            ],
            "failure_remediation": [
                "Run verify_platform_field_rehearsal.py without --check to print the current mismatch summary.",
                "Regenerate fixtures only after confirming they remain mock-only and redacted.",
            ],
        },
        {
            "step_id": "publish_public_support_status",
            "operator_action": "Verify and publish the metadata-only public maintainer status report before asking external users to rely on the pack.",
            "command": "python3 scripts/generate_platform_public_support_status.py --check && python3 scripts/verify_platform_public_support_status.py --check",
            "expected_outputs": [
                "public-support-status-v1",
                "public-maintainer-dashboard-v1",
                "public-status-linkage-fixture-v1",
                "no raw source, answers, prompts, Agent endpoints, model keys, or private platform context",
            ],
            "evidence_paths": [
                "platform/generated/study-anything-public-support-status.json",
                "platform/generated/study-anything-public-maintainer-dashboard.json",
                "platform/generated/study-anything-public-maintainer-dashboard.md",
                "docs/public-support-status.md",
            ],
            "failure_remediation": [
                "Run verify_platform_public_support_status.py without --check to print the current mismatch summary.",
                "Publish only labels, schema names, fixture hashes, and copyable commands.",
            ],
        },
        {
            "step_id": "package_published_image_evidence",
            "operator_action": "Generate and verify the public published-image evidence before release or platform handoff.",
            "command": "python3 scripts/generate_published_image_evidence.py --check && python3 scripts/verify_published_image_evidence.py --check",
            "expected_outputs": [
                "published-image-evidence-v1",
                "published-image-evidence-fixture-v1",
                "blocked_by_local_ghcr_pull",
                "manifest platforms and docker-images workflow classifications",
                "no raw source, answers, prompts, Agent endpoints, model keys, support bundle private payloads, or local absolute paths",
            ],
            "evidence_paths": [
                "platform/generated/study-anything-published-image-evidence.json",
                "platform/generated/study-anything-published-image-evidence.md",
                "platform/generated/study-anything-published-image-evidence.zip",
                "platform/generated/study-anything-published-image-evidence.sha256",
                "docs/published-image-evidence.md",
            ],
            "failure_remediation": [
                "Run verify_published_image_evidence.py without --check to print the current mismatch summary.",
                "Do not treat local pull timeout as failure when manifest and docker-images evidence are valid.",
            ],
        },
        {
            "step_id": "package_adopter_evidence_archive",
            "operator_action": "Generate and verify the public adopter evidence archive before release or platform handoff.",
            "command": "python3 scripts/generate_adopter_evidence_archive.py --check && python3 scripts/verify_adopter_evidence_archive.py --check",
            "expected_outputs": [
                "adopter-evidence-archive-v1",
                "adopter-evidence-fixture-v1",
                "archive checksum",
                "no raw source, answers, prompts, Agent endpoints, model keys, support bundle private payloads, or private platform context",
            ],
            "evidence_paths": [
                "platform/generated/study-anything-adopter-evidence-archive.json",
                "platform/generated/study-anything-adopter-evidence-archive.md",
                "platform/generated/study-anything-adopter-evidence-archive.zip",
                "platform/generated/study-anything-adopter-evidence-archive.sha256",
                "docs/adopter-evidence-archive.md",
            ],
            "failure_remediation": [
                "Run verify_adopter_evidence_archive.py without --check to print the current mismatch summary.",
                "Share only the archive checksum, public command, known limitation, and release URL.",
            ],
        },
        {
            "step_id": "collect_redacted_handoff",
            "operator_action": "Run the manual rehearsal verifier and share the redacted JSON report.",
            "command": "python3 scripts/verify_platform_manual_submission_rehearsal.py --check",
            "expected_outputs": [
                SCHEMA_VERSION,
                "first-run-lesson-authoring-kit-v1",
                "status pass",
            ],
            "evidence_paths": [
                "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
                "platform/generated/study-anything-first-lesson-authoring-kit.json",
            ],
            "failure_remediation": ["Run release_check.sh locally before resubmitting the platform pack."],
        },
    ]


def assert_no_leaks(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise ManualSubmissionRehearsalError(
            f"Manual submission rehearsal report leaked private data: {leaks}"
        )


def build_report(root: Path) -> dict[str, Any]:
    running_from_adoption_pack = safe_relative(root, "manifest.json").is_file()
    required_report_evidence = list(REQUIRED_REPORT_EVIDENCE)
    if running_from_adoption_pack:
        required_report_evidence.remove("platform/generated/study-anything-platform-adoption-pack.json")
        require_file(root, "manifest.json")
    for path in REQUIRED_OPERATOR_ASSETS + required_report_evidence:
        require_file(root, path)
    tool_assets = validate_tool_assets(root)
    platforms = {platform_id: validate_platform_pack(root, platform_id) for platform_id in PLATFORM_IDS}
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "submission": validate_submission(root),
        "tool_assets": tool_assets,
        "platforms": platforms,
        "operator_steps": operator_steps(),
        "commands_run": [
            {
                "step_id": step["step_id"],
                "command": sanitize_command(str(step["command"])),
                "mode": "rehearsed_manual_acceptance",
            }
            for step in operator_steps()
        ],
        "expected_outputs": {
            step["step_id"]: step["expected_outputs"] for step in operator_steps()
        },
        "evidence_paths": sorted(
            set(
                REQUIRED_OPERATOR_ASSETS
                + required_report_evidence
                + (["manifest.json"] if running_from_adoption_pack else [])
            )
        ),
        "existing_reports": validate_existing_reports(root),
        "failure_remediation": {
            "tool_import_failed": [
                "Use platform/generated/study-anything-tool-catalog.md as a manual mapping fallback.",
                "Confirm management endpoints are absent from the imported OpenAPI asset.",
            ],
            "runtime_unreachable": [
                "Run scripts/diagnose_adoption.py.",
                "Use Skill Mode when Docker or registry pulls are unreliable.",
            ],
            "agent_unhealthy": [
                "Keep model credentials in the user's Agent, then rerun verify_agent_gateway_hardening.py.",
                "Use fake deterministic provider only to isolate Study Anything runtime issues.",
            ],
            "evidence_not_redacted": [
                "Do not share raw source, answers, endpoints, model keys, or browser/video context.",
                "Rerun this verifier and share only the generated redacted report.",
            ],
        },
        "privacy_assertions": {
            "raw_source_text_returned": False,
            "learner_answers_returned": False,
            "agent_endpoint_secrets_returned": False,
            "real_model_keys_stored_by_study_anything": False,
            "browser_video_private_context_returned": False,
            "report_is_redacted": True,
        },
        "time_budget": {
            "target_minutes": 30,
            "estimated_operator_minutes": 18,
            "stop_on_first_blocker": True,
        },
    }
    assert_no_leaks(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="Optional adoption-pack zip to rehearse.")
    parser.add_argument("--pack-root", help="Optional unpacked adoption-pack or repo root.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="study-anything-manual-submission-"))
    try:
        root = resolve_pack_root(args, tmp_root)
        payload = build_report(root)
        text = dump_json(payload)
        output = Path(args.output)
        if args.check:
            if not output.exists():
                raise ManualSubmissionRehearsalError(f"Manual rehearsal report missing: {output}")
            if output.read_text(encoding="utf-8") != text:
                raise ManualSubmissionRehearsalError(
                    "Manual submission rehearsal report is stale. Run "
                    "`python3 scripts/verify_platform_manual_submission_rehearsal.py --write`."
                )
            print("ok    platform manual submission rehearsal report is up to date")
            return
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
            print(f"wrote {output.relative_to(ROOT)}")
            return
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_manual_submission_rehearsal failed: {exc}", file=sys.stderr)
        sys.exit(1)
