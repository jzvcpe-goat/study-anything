#!/usr/bin/env python3
"""Verify GitHub-first support triage assets for external platform adoption."""

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
SCHEMA_VERSION = "platform-support-triage-v1"
TICKET_SCHEMA_VERSION = "platform-support-ticket-fixture-v1"
ISSUE_TEMPLATE_SCHEMA_VERSION = "platform-support-issue-template-v1"
FIELD_REHEARSAL_SCHEMA_VERSION = "platform-field-adoption-rehearsal-v1"
FEEDBACK_SCHEMA_VERSION = "platform-feedback-package-v1"
RELEASE_VERSION = "v0.3.20-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-platform-support-triage.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
SUPPORT_CATEGORY_IDS = (
    "platform_import_failure",
    "local_gateway_failure",
    "published_image_pull_failure",
    "agent_eval_evidence_failure",
    "docs_confusion",
)
QUIRK_IDS = (
    "schema_mismatch",
    "missing_local_gateway",
    "unsupported_auth_mode",
    "tool_naming_drift",
    "timeout",
    "cors_localhost",
    "package_corruption",
    "version_drift",
)
REQUIRED_SUPPORT_FIELDS = (
    "release_version",
    "platform_id",
    "command_ran",
    "diagnostic_code",
    "fixture_id",
    "redacted_log_excerpt",
    "next_commands_tried",
)
REQUIRED_COMMAND = "verify_platform_support_triage.py --check"
REQUIRED_GENERATOR_COMMAND = "generate_platform_support_triage.py --check"
REQUIRED_EVIDENCE = "platform_support_triage.schema_version == platform-support-triage-v1"
REQUIRED_TICKET_EVIDENCE = (
    "platform_support_ticket_fixture.schema_version == platform-support-ticket-fixture-v1"
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
    "Private source text:",
    "Private platform browser/video context",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
]


class PlatformSupportTriageError(RuntimeError):
    """Readable platform support-triage validation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlatformSupportTriageError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlatformSupportTriageError(f"JSON object expected: {path}")
    return value


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise PlatformSupportTriageError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise PlatformSupportTriageError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise PlatformSupportTriageError(
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
        raise PlatformSupportTriageError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise PlatformSupportTriageError(f"Required support triage asset is missing: {relative_path}")
    return target


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformSupportTriageError(f"Platform support triage leaked private data: {leaks}")


def assert_text_has_no_leaks(text: str, relative_path: str) -> None:
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in text]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text))
    if leaks:
        raise PlatformSupportTriageError(f"{relative_path} leaked private data: {leaks}")


def validate_ticket(root: Path, relative_path: str, ticket_id: str) -> dict[str, Any]:
    payload = read_json(require_file(root, relative_path))
    if payload.get("schema_version") != TICKET_SCHEMA_VERSION:
        raise PlatformSupportTriageError(f"{relative_path} ticket schema drifted.")
    if payload.get("version") != RELEASE_VERSION:
        raise PlatformSupportTriageError(f"{relative_path} ticket version drifted.")
    if payload.get("ticket_id") != ticket_id:
        raise PlatformSupportTriageError(f"{relative_path} ticket_id drifted.")
    support_bundle = payload.get("support_bundle")
    if not isinstance(support_bundle, dict):
        raise PlatformSupportTriageError(f"{relative_path} must include support_bundle.")
    missing = [field for field in REQUIRED_SUPPORT_FIELDS if field not in support_bundle]
    if missing:
        raise PlatformSupportTriageError(f"{relative_path} support bundle missing: {missing}")
    if not support_bundle.get("next_commands_tried"):
        raise PlatformSupportTriageError(f"{relative_path} must include next_commands_tried.")
    linked = payload.get("linked_import_failure_fixture")
    if not isinstance(linked, str) or not linked.startswith("fixtures/platform-import-failures/"):
        raise PlatformSupportTriageError(f"{relative_path} must link an import failure fixture.")
    require_file(root, linked)
    privacy = payload.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "learner_answers_included",
        "agent_prompts_included",
        "real_model_keys_included",
        "agent_endpoint_secrets_included",
        "browser_video_private_context_included",
        "personal_profile_included",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise PlatformSupportTriageError(f"{relative_path} privacy.{key} must be false.")
    assert_no_leaks(payload)
    return {
        "ticket_id": ticket_id,
        "path": relative_path,
        "schema_version": payload.get("schema_version"),
        "support_field_count": len(support_bundle),
    }


def validate_issue_template(root: Path, relative_path: str, category_id: str) -> dict[str, Any]:
    text = require_file(root, relative_path).read_text(encoding="utf-8")
    for needle in (
        ISSUE_TEMPLATE_SCHEMA_VERSION,
        RELEASE_VERSION,
        "Do not paste raw source text",
        "## Command Ran",
        "## Diagnostic Code",
        "## Fixture Or Quirk Id",
        "## Redacted Log Excerpt",
        "## Next Commands Tried",
    ):
        if needle not in text:
            raise PlatformSupportTriageError(f"{relative_path} missing {needle!r}.")
    if category_id.replace("_", " ") not in text.replace("-", " ").lower():
        raise PlatformSupportTriageError(f"{relative_path} does not describe category {category_id}.")
    assert_text_has_no_leaks(text, relative_path)
    return {
        "category_id": category_id,
        "path": relative_path,
        "schema_version": ISSUE_TEMPLATE_SCHEMA_VERSION,
    }


def validate_report(root: Path) -> dict[str, Any]:
    report = read_json(
        require_file(root, "platform/generated/study-anything-platform-support-triage.json")
    )
    if report.get("schema_version") != SCHEMA_VERSION:
        raise PlatformSupportTriageError("Support triage report schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise PlatformSupportTriageError("Support triage report version drifted.")
    if report.get("status") != "pass":
        raise PlatformSupportTriageError("Support triage report must pass.")
    contract = report.get("support_bundle_contract") or {}
    if contract.get("schema_version") != "platform-support-bundle-v1":
        raise PlatformSupportTriageError("Support bundle contract schema drifted.")
    if set(contract.get("required_fields", [])) != set(REQUIRED_SUPPORT_FIELDS):
        raise PlatformSupportTriageError("Support bundle required fields drifted.")
    if contract.get("automatic_upload") is not False or contract.get("safe_handoff_only") is not True:
        raise PlatformSupportTriageError("Support bundle must be manual and safe-handoff only.")

    templates = report.get("issue_templates")
    if not isinstance(templates, list) or len(templates) != len(SUPPORT_CATEGORY_IDS):
        raise PlatformSupportTriageError("Support triage report issue template count drifted.")
    template_results = [
        validate_issue_template(root, str(item.get("path")), str(item.get("category_id")))
        for item in templates
        if isinstance(item, dict)
    ]
    if {item["category_id"] for item in template_results} != set(SUPPORT_CATEGORY_IDS):
        raise PlatformSupportTriageError("Support triage issue categories drifted.")

    tickets = report.get("support_ticket_fixtures")
    if not isinstance(tickets, list) or len(tickets) != len(SUPPORT_CATEGORY_IDS):
        raise PlatformSupportTriageError("Support triage report ticket fixture count drifted.")
    ticket_results = [
        validate_ticket(root, str(item.get("path")), str(item.get("ticket_id")))
        for item in tickets
        if isinstance(item, dict)
    ]
    if {item["ticket_id"] for item in ticket_results} != set(SUPPORT_CATEGORY_IDS):
        raise PlatformSupportTriageError("Support triage ticket ids drifted.")

    playbook = report.get("maintainer_playbook")
    if not isinstance(playbook, list) or len(playbook) != len(QUIRK_IDS):
        raise PlatformSupportTriageError("Maintainer playbook must cover every import quirk.")
    if {str(item.get("failure_id")) for item in playbook if isinstance(item, dict)} != set(QUIRK_IDS):
        raise PlatformSupportTriageError("Maintainer playbook quirk ids drifted.")
    for item in playbook:
        if not item.get("first_response") or not item.get("reproduction_steps"):
            raise PlatformSupportTriageError(f"Maintainer playbook entry is not actionable: {item}")
        if not item.get("close_when") or not item.get("escalate_when"):
            raise PlatformSupportTriageError(f"Maintainer playbook entry lacks closure/escalation: {item}")

    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_in_report",
        "agent_endpoint_secrets_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "browser_video_private_context_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise PlatformSupportTriageError(f"Support triage privacy.{key} must be false.")
    if privacy.get("fixtures_are_mock_only") is not True:
        raise PlatformSupportTriageError("Support triage fixtures must be mock-only.")
    assert_no_leaks(report)
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "issue_template_count": len(template_results),
        "ticket_fixture_count": len(ticket_results),
        "playbook_entry_count": len(playbook),
        "tickets": ticket_results,
    }


def validate_field_and_feedback_dependencies(root: Path) -> dict[str, Any]:
    field = read_json(
        require_file(root, "platform/generated/study-anything-platform-field-rehearsal.json")
    )
    if field.get("schema_version") != FIELD_REHEARSAL_SCHEMA_VERSION:
        raise PlatformSupportTriageError("Field rehearsal dependency schema drifted.")
    feedback = read_json(
        require_file(root, "platform/generated/study-anything-platform-feedback-package.json")
    )
    if feedback.get("schema_version") != FEEDBACK_SCHEMA_VERSION:
        raise PlatformSupportTriageError("Feedback package dependency schema drifted.")
    return {
        "field_rehearsal": field.get("schema_version"),
        "feedback_package": feedback.get("schema_version"),
    }


def validate_platform_packs(root: Path) -> dict[str, Any]:
    platform_results: dict[str, Any] = {}
    for platform_id in ("codex", "kimi", "workbuddy"):
        pack = read_json(require_file(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
            if command not in commands:
                raise PlatformSupportTriageError(f"{platform_id} pack missing {command}.")
        for item in (REQUIRED_EVIDENCE, REQUIRED_TICKET_EVIDENCE):
            if item not in evidence:
                raise PlatformSupportTriageError(f"{platform_id} pack missing {item}.")
        platform_results[platform_id] = {
            "support_triage_command_declared": True,
            "ticket_fixture_evidence_declared": True,
        }
    return platform_results


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(require_file(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise PlatformSupportTriageError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise PlatformSupportTriageError("Ecosystem submission version drifted.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "scripts/generate_platform_support_triage.py",
        "scripts/verify_platform_support_triage.py",
        "platform/generated/study-anything-platform-support-triage.json",
        "docs/support-desk.md",
        *[f".github/ISSUE_TEMPLATE/{category_id}.md" for category_id in SUPPORT_CATEGORY_IDS],
        *[f"fixtures/platform-support-tickets/{category_id}.json" for category_id in SUPPORT_CATEGORY_IDS],
    }
    missing = sorted(required_assets - shared_assets)
    if missing:
        raise PlatformSupportTriageError(f"Ecosystem submission missing support triage assets: {missing}")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
        if command not in command_text:
            raise PlatformSupportTriageError(f"Ecosystem submission missing {command}.")
    for schema in (SCHEMA_VERSION, TICKET_SCHEMA_VERSION, ISSUE_TEMPLATE_SCHEMA_VERSION):
        if schema not in prove_text:
            raise PlatformSupportTriageError(f"Ecosystem submission must prove {schema}.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "support_assets_included": len(required_assets),
    }


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        raise PlatformSupportTriageError("Adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required_paths = {
        "scripts/generate_platform_support_triage.py",
        "scripts/verify_platform_support_triage.py",
        "platform/generated/study-anything-platform-support-triage.json",
        "docs/support-desk.md",
        "docs/release-notes/v0.3.20-alpha.md",
        *[f".github/ISSUE_TEMPLATE/{category_id}.md" for category_id in SUPPORT_CATEGORY_IDS],
        *[f"fixtures/platform-support-tickets/{category_id}.json" for category_id in SUPPORT_CATEGORY_IDS],
    }
    missing = sorted(required_paths - paths)
    if missing:
        raise PlatformSupportTriageError(f"Adoption pack missing support triage assets: {missing}")
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    for schema in (SCHEMA_VERSION, TICKET_SCHEMA_VERSION, ISSUE_TEMPLATE_SCHEMA_VERSION):
        if schema not in must_verify:
            raise PlatformSupportTriageError(f"Adoption pack must verify {schema}.")
    return {
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "support_assets_included": len(required_paths),
    }


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/support-desk.md": [
            SCHEMA_VERSION,
            TICKET_SCHEMA_VERSION,
            ISSUE_TEMPLATE_SCHEMA_VERSION,
            "GitHub-first",
        ],
        "docs/adoption.md": [SCHEMA_VERSION, "verify_platform_support_triage.py"],
        "docs/platform-agent-integrations.md": [SCHEMA_VERSION, "support desk"],
        "docs/ecosystem-submission.md": [SCHEMA_VERSION, "support triage"],
        "docs/release-checklist.md": ["verify_platform_support_triage.py --check"],
        "docs/roadmap.md": ["v0.3.20-alpha", SCHEMA_VERSION],
    }
    for relative_path, needles in checked.items():
        text = require_file(root, relative_path).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise PlatformSupportTriageError(f"{relative_path} is missing required text: {missing}")
        assert_text_has_no_leaks(text, relative_path)
    return {"checked_docs": sorted(checked)}


def build_report(root: Path) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Verify that external platform support tickets can be triaged through GitHub "
            "without exposing private learning data or user-owned Agent secrets."
        ),
        "support_triage": validate_report(root),
        "dependencies": validate_field_and_feedback_dependencies(root),
        "platform_packs": validate_platform_packs(root),
        "ecosystem_submission": validate_submission(root),
        "adoption_pack": validate_adoption_pack(root),
        "docs": validate_docs(root),
        "privacy_assertions": {
            "real_model_keys_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_prompts_in_report": False,
            "browser_video_private_context_in_report": False,
            "automatic_upload": False,
            "support_upload_is_manual": True,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_platform_support_triage.py --check",
            "generate_command": "python3 scripts/generate_platform_support_triage.py --check",
            "pack_command": (
                "python3 scripts/verify_platform_support_triage.py "
                "--pack platform/generated/study-anything-platform-adoption-pack.zip"
            ),
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise PlatformSupportTriageError(f"Support triage report missing: {path}")
    generated = read_json(path)
    if generated.get("schema_version") != SCHEMA_VERSION:
        raise PlatformSupportTriageError("Generated support triage report schema drifted.")
    if generated.get("version") != RELEASE_VERSION:
        raise PlatformSupportTriageError("Generated support triage report version drifted.")
    if payload.get("status") != "pass":
        raise PlatformSupportTriageError("Platform support triage validation did not pass.")
    print("ok    platform support triage assets are valid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-support-triage-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_platform_support_triage.py")
            require_file(root, "platform/generated/study-anything-platform-support-triage.json")
        report = build_report(root)

    if args.check:
        check_report(Path(args.output), report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_support_triage failed: {exc}", file=sys.stderr)
        sys.exit(1)
