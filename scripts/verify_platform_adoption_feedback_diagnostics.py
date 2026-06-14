#!/usr/bin/env python3
"""Verify platform import diagnostics and local feedback handoff boundaries."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "platform-adoption-feedback-diagnostics-v1"
FEEDBACK_SCHEMA_VERSION = "platform-feedback-package-v1"
RELEASE_VERSION = "v0.3.27-alpha"
DEFAULT_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-platform-adoption-feedback-diagnostics.json"
)
DEFAULT_FEEDBACK_MANIFEST = (
    ROOT / "platform" / "generated" / "study-anything-platform-feedback-package.json"
)
DEFAULT_FEEDBACK_ARCHIVE = (
    ROOT / "platform" / "generated" / "study-anything-platform-feedback-package.zip"
)
PLATFORM_IDS = ("codex", "kimi", "workbuddy")
REQUIRED_PACK_COMMAND = "verify_platform_adoption_feedback_diagnostics.py --check"
REQUIRED_FEEDBACK_COMMAND = "generate_platform_feedback_package.py --check"
REQUIRED_EVIDENCE = (
    "platform_adoption_feedback_diagnostics.schema_version == "
    "platform-adoption-feedback-diagnostics-v1"
)
REQUIRED_FEEDBACK_EVIDENCE = (
    "platform_feedback_package.schema_version == platform-feedback-package-v1"
)
DIAGNOSTIC_CATEGORIES = (
    "pack_schema_invalid",
    "required_file_missing",
    "openapi_import_missing_operation",
    "openai_tools_malformed",
    "unsupported_platform_capability",
    "localhost_api_unreachable",
    "agent_endpoint_unreachable",
    "agent_eval_evidence_missing",
    "version_drift",
    "missing_required_command",
    "privacy_contract_violation",
)
REQUIRED_FILES = [
    "scripts/diagnose_adoption.py",
    "scripts/verify_external_adoption.py",
    "scripts/verify_platform_operator_drill.py",
    "scripts/verify_agent_eval_marketplace_enforcement.py",
    "scripts/generate_platform_feedback_package.py",
    "platform/study-anything-platform-tools.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
    "platform/ecosystem-submission.json",
    "docs/adoption.md",
    "docs/platform-agent-integrations.md",
    "docs/ecosystem-submission.md",
]
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "Private answer:",
    "Private platform browser/video context",
    "raw source text returned",
    "learner@example.com",
    "AGENT_ENDPOINT=http",
]


class PlatformAdoptionFeedbackDiagnosticsError(RuntimeError):
    """Readable platform-adoption diagnostics failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlatformAdoptionFeedbackDiagnosticsError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlatformAdoptionFeedbackDiagnosticsError(f"JSON object expected: {path}")
    return value


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise PlatformAdoptionFeedbackDiagnosticsError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise PlatformAdoptionFeedbackDiagnosticsError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise PlatformAdoptionFeedbackDiagnosticsError(
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
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Unsafe path escapes pack root: {relative_path}"
        ) from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Required platform adoption diagnostics asset is missing: {relative_path}"
        )
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    text = require_file(root, relative_path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"{relative_path} is missing required text: {missing}"
        )
    return text


def assert_no_leaks(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Platform adoption feedback diagnostics leaked private data: {leaks}"
        )


def operation_ids(openapi: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for methods in openapi.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if isinstance(operation, dict) and operation.get("operationId"):
                found.add(str(operation["operationId"]))
    return found


def validate_import_assets(root: Path) -> dict[str, Any]:
    tool_manifest = read_json(safe_relative(root, "platform/study-anything-platform-tools.json"))
    openapi = read_json(safe_relative(root, "platform/generated/study-anything-platform-openapi.json"))
    openai_tools_raw = json.loads(
        safe_relative(root, "platform/generated/study-anything-openai-tools.json").read_text(
            encoding="utf-8"
        )
    )
    if tool_manifest.get("schema_version") != "study-anything-platform-tools-v1":
        raise PlatformAdoptionFeedbackDiagnosticsError("Platform tool manifest schema drifted.")
    if openapi.get("openapi") != "3.1.0":
        raise PlatformAdoptionFeedbackDiagnosticsError("OpenAPI import asset must be OpenAPI 3.1.0.")
    if openapi.get("components", {}).get("securitySchemes"):
        raise PlatformAdoptionFeedbackDiagnosticsError("OpenAPI import asset must not expose API keys.")
    if not isinstance(openai_tools_raw, list):
        raise PlatformAdoptionFeedbackDiagnosticsError("OpenAI-compatible tools must be a list.")

    required_tools = {
        str(tool.get("name"))
        for tool in tool_manifest.get("tools", [])
        if isinstance(tool, dict) and tool.get("name")
    }
    openapi_names = operation_ids(openapi)
    malformed: list[str] = []
    openai_names: set[str] = set()
    for item in openai_tools_raw:
        function = item.get("function") if isinstance(item, dict) else None
        if not isinstance(function, dict):
            malformed.append("<missing function>")
            continue
        name = str(function.get("name") or "")
        openai_names.add(name)
        if (
            item.get("type") != "function"
            or not name.startswith("study_anything_")
            or not isinstance(function.get("parameters"), dict)
        ):
            malformed.append(name or "<unnamed>")
    if malformed:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Malformed OpenAI-compatible tool definitions: {malformed}"
        )
    missing = sorted(required_tools - openapi_names - openai_names)
    if missing:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Tool import assets miss required tools: {missing}"
        )
    return {
        "tool_manifest_schema": tool_manifest.get("schema_version"),
        "required_tool_count": len(required_tools),
        "openapi_path_count": len(openapi.get("paths", {})),
        "openai_tool_count": len(openai_tools_raw),
        "management_endpoints_exposed": False,
        "api_key_security_schemes_exposed": False,
    }


def validate_diagnostic_contract(root: Path) -> dict[str, Any]:
    diagnose_text = assert_contains(
        root,
        "scripts/diagnose_adoption.py",
        "adoption-diagnostics-v1",
        "adoption-diagnostic-plan-v1",
        "check_ghcr_manifest",
        "provider_capability_report",
        "api_unreachable",
        "agent_endpoint_unreachable",
        "provider_defaults_missing",
    )
    external_text = assert_contains(
        root,
        "scripts/verify_external_adoption.py",
        "adoption-proof-v1",
        "REQUIRED_ARCHIVE_PATHS",
        "agent_eval_marketplace_enforcement",
    )
    return {
        "diagnose_adoption_has_recovery_plan": "build_recovery_plan" in diagnose_text,
        "external_adoption_proof_schema": "adoption-proof-v1" in external_text,
        "diagnostic_categories": list(DIAGNOSTIC_CATEGORIES),
        "copyable_recovery_commands": [
            "python3 scripts/setup_env.py",
            "./scripts/doctor.sh",
            "./scripts/launch_skill_mode.sh",
            "./scripts/launch_self_host.sh",
        ],
    }


def validate_agent_eval_evidence(root: Path) -> dict[str, Any]:
    report = read_json(
        safe_relative(root, "platform/generated/study-anything-agent-eval-marketplace-enforcement.json")
    )
    if report.get("schema_version") != "agent-eval-marketplace-enforcement-v1":
        raise PlatformAdoptionFeedbackDiagnosticsError("Agent eval enforcement schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Agent eval enforcement version must be {RELEASE_VERSION}."
        )
    if report.get("status") != "pass":
        raise PlatformAdoptionFeedbackDiagnosticsError("Agent eval enforcement report must pass.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_or_judge_keys_stored_by_study_anything",
        "judge_api_keys_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_endpoint_secrets_in_report",
    ):
        if privacy.get(key) is not False:
            raise PlatformAdoptionFeedbackDiagnosticsError(
                f"Agent eval enforcement privacy.{key} must be false."
            )
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "status": report.get("status"),
        "external_judge_optional": True,
        "required_mode_can_block": True,
    }


def validate_feedback_package(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(
        root, "platform/generated/study-anything-platform-feedback-package.json"
    )
    archive_path = safe_relative(
        root, "platform/generated/study-anything-platform-feedback-package.zip"
    )
    if not manifest_path.is_file() or not archive_path.is_file():
        return {
            "included": False,
            "reason": "feedback_package_not_generated",
            "expected_command": "python3 scripts/generate_platform_feedback_package.py",
        }
    payload = read_json(manifest_path)
    if payload.get("schema_version") != FEEDBACK_SCHEMA_VERSION:
        raise PlatformAdoptionFeedbackDiagnosticsError("Feedback package schema drifted.")
    if payload.get("version") != RELEASE_VERSION:
        raise PlatformAdoptionFeedbackDiagnosticsError("Feedback package version drifted.")
    if payload.get("privacy", {}).get("redacted") is not True:
        raise PlatformAdoptionFeedbackDiagnosticsError("Feedback package must be redacted.")
    if payload.get("privacy", {}).get("automatic_upload") is not False:
        raise PlatformAdoptionFeedbackDiagnosticsError("Feedback package must be local-only.")
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    required_names = {
        "study-anything-platform-feedback-package/manifest.json",
        "study-anything-platform-feedback-package/diagnostics-summary.json",
        "study-anything-platform-feedback-package/redacted-log-sample.txt",
    }
    missing = sorted(required_names - names)
    if missing:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Feedback package archive missing files: {missing}"
        )
    assert_no_leaks(payload)
    return {
        "included": True,
        "schema_version": payload.get("schema_version"),
        "version": payload.get("version"),
        "archive_name": archive_path.name,
        "diagnostic_categories": payload.get("diagnostic_categories", []),
        "local_only": True,
    }


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/adoption.md": [
            "platform-adoption-feedback-diagnostics-v1",
            "platform-feedback-package-v1",
            "generate_platform_feedback_package.py",
        ],
        "docs/platform-agent-integrations.md": [
            "platform-adoption-feedback-diagnostics-v1",
            "platform-feedback-package-v1",
        ],
        "docs/ecosystem-submission.md": [
            "platform-adoption-feedback-diagnostics-v1",
            "platform-feedback-package-v1",
        ],
    }
    for path, needles in checked.items():
        assert_contains(root, path, *needles)
    return {"checked_docs": sorted(checked), "feedback_upload_is_manual": True}


def validate_platform_packs(root: Path) -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    for platform_id in PLATFORM_IDS:
        pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        if REQUIRED_PACK_COMMAND not in commands:
            raise PlatformAdoptionFeedbackDiagnosticsError(
                f"{platform_id} pack missing feedback diagnostics command."
            )
        if REQUIRED_FEEDBACK_COMMAND not in commands:
            raise PlatformAdoptionFeedbackDiagnosticsError(
                f"{platform_id} pack missing feedback package command."
            )
        if REQUIRED_EVIDENCE not in evidence:
            raise PlatformAdoptionFeedbackDiagnosticsError(
                f"{platform_id} pack missing feedback diagnostics evidence."
            )
        if REQUIRED_FEEDBACK_EVIDENCE not in evidence:
            raise PlatformAdoptionFeedbackDiagnosticsError(
                f"{platform_id} pack missing feedback package evidence."
            )
        platforms[platform_id] = {
            "integration_mode": pack.get("integration_mode"),
            "command_declared": True,
            "feedback_package_declared": True,
        }
    return platforms


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("version") != RELEASE_VERSION:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Ecosystem submission version must be {RELEASE_VERSION}."
        )
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "scripts/verify_platform_adoption_feedback_diagnostics.py",
        "scripts/generate_platform_feedback_package.py",
        "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
        "platform/generated/study-anything-platform-feedback-package.json",
        "platform/generated/study-anything-platform-feedback-package.zip",
    }
    missing_assets = required_assets - shared_assets
    if missing_assets:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Ecosystem submission missing feedback assets: {sorted(missing_assets)}"
        )
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for fragment in (
        REQUIRED_PACK_COMMAND,
        REQUIRED_FEEDBACK_COMMAND,
    ):
        if fragment not in command_text:
            raise PlatformAdoptionFeedbackDiagnosticsError(
                f"Ecosystem submission missing command fragment: {fragment}"
            )
    for schema in (SCHEMA_VERSION, FEEDBACK_SCHEMA_VERSION):
        if schema not in prove_text:
            raise PlatformAdoptionFeedbackDiagnosticsError(
                f"Ecosystem submission must prove {schema}."
            )
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "shared_assets_included": len(required_assets),
        "submission_count": len(submission.get("submissions", [])),
    }


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    if not manifest_path.is_file():
        return {"included": False, "reason": "manifest_not_generated_yet"}
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        return {
            "included": False,
            "reason": "manifest_version_mismatch",
            "found_version": manifest.get("version"),
            "expected_version": RELEASE_VERSION,
        }
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required = {
        "scripts/verify_platform_adoption_feedback_diagnostics.py",
        "scripts/generate_platform_feedback_package.py",
        "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
        "platform/generated/study-anything-platform-feedback-package.json",
        "platform/generated/study-anything-platform-feedback-package.zip",
        "docs/release-notes/v0.3.27-alpha.md",
    }
    missing = required - paths
    if missing:
        return {"included": False, "missing": sorted(missing)}
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    missing_schemas = [schema for schema in (SCHEMA_VERSION, FEEDBACK_SCHEMA_VERSION) if schema not in must_verify]
    if missing_schemas:
        return {"included": False, "missing": missing_schemas}
    return {
        "included": True,
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "feedback_assets_included": len(required),
    }


def build_report(root: Path) -> dict[str, Any]:
    for path in REQUIRED_FILES:
        require_file(root, path)
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Make external platform import failures diagnosable and make local feedback "
            "packages useful without uploading private learning data."
        ),
        "import_assets": validate_import_assets(root),
        "diagnostic_contract": validate_diagnostic_contract(root),
        "agent_eval_evidence": validate_agent_eval_evidence(root),
        "feedback_package": validate_feedback_package(root),
        "docs": validate_docs(root),
        "platform_packs": validate_platform_packs(root),
        "ecosystem_submission": validate_submission(root),
        "adoption_pack": validate_adoption_pack(root),
        "privacy_assertions": {
            "automatic_feedback_upload": False,
            "real_model_keys_in_feedback": False,
            "agent_endpoint_secrets_in_feedback": False,
            "raw_source_text_in_feedback": False,
            "learner_answers_in_feedback": False,
            "agent_prompts_in_feedback": False,
            "personal_profile_in_feedback": False,
            "browser_video_private_context_in_feedback": False,
            "feedback_package_is_redacted": True,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check",
            "feedback_package_command": "python3 scripts/generate_platform_feedback_package.py --check",
            "pack_command": (
                "python3 scripts/verify_platform_adoption_feedback_diagnostics.py "
                "--pack platform/generated/study-anything-platform-adoption-pack.zip"
            ),
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise PlatformAdoptionFeedbackDiagnosticsError(f"Feedback diagnostics report missing: {path}")
    expected = dump_json(payload)
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            "Platform adoption feedback diagnostics report is stale. Run "
            "`python3 scripts/verify_platform_adoption_feedback_diagnostics.py --write`."
        )
    adoption = payload.get("adoption_pack") or {}
    feedback = payload.get("feedback_package") or {}
    if adoption.get("included") is not True:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Adoption pack missing feedback diagnostics evidence: {adoption}"
        )
    if feedback.get("included") is not True:
        raise PlatformAdoptionFeedbackDiagnosticsError(
            f"Feedback package is missing or invalid: {feedback}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--write", action="store_true", help="Write the generated report.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-feedback-diagnostics-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_platform_adoption_feedback_diagnostics.py")
            require_file(
                root,
                "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            )
        report = build_report(root)

    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dump_json(report), encoding="utf-8")
    if args.check:
        check_report(output, report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_adoption_feedback_diagnostics failed: {exc}", file=sys.stderr)
        sys.exit(1)
