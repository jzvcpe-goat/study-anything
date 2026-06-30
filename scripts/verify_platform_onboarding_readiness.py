#!/usr/bin/env python3
"""Verify first-adopter onboarding and maintainer SLA readiness assets."""

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
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-platform-onboarding-readiness.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
SCHEMA_VERSION = "platform-onboarding-readiness-v1"
WALKTHROUGH_SCHEMA_VERSION = "first-external-adopter-walkthrough-v1"
SLA_SCHEMA_VERSION = "maintainer-sla-labels-v1"
ROTATION_SCHEMA_VERSION = "maintainer-rotation-checklist-v1"
DASHBOARD_SCHEMA_VERSION = "platform-triage-dashboard-v1"
RELEASE_BLOCKER_SCHEMA_VERSION = "platform-release-blocker-fixture-v1"
SUPPORT_TRIAGE_SCHEMA_VERSION = "platform-support-triage-v1"
RELEASE_VERSION = "v0.3.31-alpha"
PLATFORMS = {"kimi", "codex", "workbuddy", "generic"}
SLA_LABELS = {
    "intake",
    "needs-repro",
    "confirmed",
    "blocked-by-platform",
    "docs-fix",
    "release-blocker",
    "resolved",
}
SUPPORT_CATEGORIES = {
    "platform_import_failure",
    "local_gateway_failure",
    "published_image_pull_failure",
    "agent_eval_evidence_failure",
    "docs_confusion",
}
RELEASE_BLOCKER_IDS = {
    "tool_import_blocker",
    "local_gateway_blocker",
    "published_image_blocker",
    "agent_eval_blocker",
    "support_bundle_privacy_blocker",
}
REQUIRED_SUPPORT_FIELDS = {
    "release_version",
    "platform_id",
    "command_ran",
    "diagnostic_code",
    "fixture_id",
    "redacted_log_excerpt",
    "next_commands_tried",
}
REQUIRED_COMMAND = "verify_platform_onboarding_readiness.py --check"
REQUIRED_GENERATOR_COMMAND = "generate_platform_onboarding_readiness.py --check"
REQUIRED_PACK_COMMAND = (
    "verify_platform_onboarding_readiness.py --pack "
    "platform/generated/study-anything-platform-adoption-pack.zip"
)
REQUIRED_EVIDENCE = "platform_onboarding_readiness.schema_version == platform-onboarding-readiness-v1"
REQUIRED_DASHBOARD_EVIDENCE = "platform_triage_dashboard.schema_version == platform-triage-dashboard-v1"
REQUIRED_BLOCKER_EVIDENCE = (
    "platform_release_blocker_fixture.schema_version == platform-release-blocker-fixture-v1"
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


class PlatformOnboardingReadinessError(RuntimeError):
    """Readable onboarding-readiness validation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlatformOnboardingReadinessError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlatformOnboardingReadinessError(f"JSON object expected: {path}")
    return value


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise PlatformOnboardingReadinessError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise PlatformOnboardingReadinessError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise PlatformOnboardingReadinessError(
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
        raise PlatformOnboardingReadinessError(
            f"Unsafe path escapes pack root: {relative_path}"
        ) from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise PlatformOnboardingReadinessError(
            f"Required onboarding readiness asset is missing: {relative_path}"
        )
    return target


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformOnboardingReadinessError(
            f"Platform onboarding readiness leaked private data: {leaks}"
        )


def assert_text_has_no_leaks(text: str, relative_path: str) -> None:
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in text]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text))
    if leaks:
        raise PlatformOnboardingReadinessError(f"{relative_path} leaked private data: {leaks}")


def validate_release_blocker(root: Path, relative_path: str, blocker_id: str) -> dict[str, Any]:
    payload = read_json(require_file(root, relative_path))
    if payload.get("schema_version") != RELEASE_BLOCKER_SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError(f"{relative_path} release blocker schema drifted.")
    if payload.get("version") != RELEASE_VERSION:
        raise PlatformOnboardingReadinessError(f"{relative_path} release blocker version drifted.")
    if payload.get("blocker_id") != blocker_id:
        raise PlatformOnboardingReadinessError(f"{relative_path} blocker_id drifted.")
    if payload.get("linked_support_category") not in SUPPORT_CATEGORIES:
        raise PlatformOnboardingReadinessError(f"{relative_path} support category drifted.")
    support_bundle = payload.get("support_bundle")
    if not isinstance(support_bundle, dict):
        raise PlatformOnboardingReadinessError(f"{relative_path} must include support_bundle.")
    if set(support_bundle) != REQUIRED_SUPPORT_FIELDS:
        raise PlatformOnboardingReadinessError(f"{relative_path} support bundle fields drifted.")
    labels = set(str(item) for item in payload.get("required_labels", []))
    if not {"intake", "needs-repro", "release-blocker"}.issubset(labels):
        raise PlatformOnboardingReadinessError(f"{relative_path} must declare release-blocker labels.")
    privacy = payload.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "learner_answers_included",
        "agent_prompts_included",
        "real_model_keys_included",
        "agent_endpoint_secrets_included",
        "browser_video_private_context_included",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise PlatformOnboardingReadinessError(f"{relative_path} privacy.{key} must be false.")
    assert_no_leaks(payload)
    return {
        "blocker_id": blocker_id,
        "path": relative_path,
        "linked_support_category": payload.get("linked_support_category"),
    }


def validate_dashboard(root: Path) -> dict[str, Any]:
    dashboard = read_json(
        require_file(root, "platform/generated/study-anything-platform-triage-dashboard.json")
    )
    if dashboard.get("schema_version") != DASHBOARD_SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError("Triage dashboard schema drifted.")
    if dashboard.get("version") != RELEASE_VERSION:
        raise PlatformOnboardingReadinessError("Triage dashboard version drifted.")
    if dashboard.get("status") != "pass":
        raise PlatformOnboardingReadinessError("Triage dashboard must pass.")
    completeness = dashboard.get("support_bundle_completeness") or {}
    if set(completeness.get("required_fields", [])) != REQUIRED_SUPPORT_FIELDS:
        raise PlatformOnboardingReadinessError("Triage dashboard support fields drifted.")
    if completeness.get("release_blocker_fixture_count") != len(RELEASE_BLOCKER_IDS):
        raise PlatformOnboardingReadinessError("Triage dashboard release blocker count drifted.")
    coverage = dashboard.get("fixture_coverage") or {}
    if set(coverage.get("platform_walkthroughs", [])) != PLATFORMS:
        raise PlatformOnboardingReadinessError("Triage dashboard platform walkthroughs drifted.")
    privacy = dashboard.get("privacy_scan") or {}
    for key in (
        "raw_source_text_found",
        "learner_answers_found",
        "agent_endpoint_secrets_found",
        "real_model_keys_found",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise PlatformOnboardingReadinessError(f"Triage dashboard privacy.{key} must be false.")
    md = require_file(root, "platform/generated/study-anything-platform-triage-dashboard.md").read_text(
        encoding="utf-8"
    )
    for needle in (DASHBOARD_SCHEMA_VERSION, RELEASE_VERSION, "Release Blockers", "Maintainer Labels"):
        if needle not in md:
            raise PlatformOnboardingReadinessError(f"Triage dashboard Markdown missing {needle!r}.")
    assert_no_leaks(dashboard)
    assert_text_has_no_leaks(md, "platform/generated/study-anything-platform-triage-dashboard.md")
    return {
        "schema_version": dashboard.get("schema_version"),
        "release_blocker_count": len(dashboard.get("release_blockers", [])),
    }


def validate_report(root: Path) -> dict[str, Any]:
    report = read_json(
        require_file(root, "platform/generated/study-anything-platform-onboarding-readiness.json")
    )
    if report.get("schema_version") != SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError("Onboarding readiness report schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise PlatformOnboardingReadinessError("Onboarding readiness report version drifted.")
    if report.get("status") != "pass":
        raise PlatformOnboardingReadinessError("Onboarding readiness report must pass.")

    walkthrough = report.get("walkthrough") or {}
    if walkthrough.get("schema_version") != WALKTHROUGH_SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError("Walkthrough schema drifted.")
    platforms = walkthrough.get("platforms")
    if not isinstance(platforms, list) or len(platforms) != len(PLATFORMS):
        raise PlatformOnboardingReadinessError("Walkthrough must cover every platform.")
    if {str(item.get("platform_id")) for item in platforms if isinstance(item, dict)} != PLATFORMS:
        raise PlatformOnboardingReadinessError("Walkthrough platform ids drifted.")
    for item in platforms:
        if not item.get("shortest_success_path") or not item.get("failure_fallback_path"):
            raise PlatformOnboardingReadinessError(f"Walkthrough entry is not actionable: {item}")

    maintainer_sla = report.get("maintainer_sla") or {}
    if maintainer_sla.get("schema_version") != SLA_SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError("Maintainer SLA schema drifted.")
    labels = maintainer_sla.get("labels")
    if not isinstance(labels, list) or {str(item.get("label")) for item in labels} != SLA_LABELS:
        raise PlatformOnboardingReadinessError("Maintainer SLA labels drifted.")
    for item in labels:
        if not item.get("meaning") or "target_first_response_hours" not in item:
            raise PlatformOnboardingReadinessError(f"SLA label is not actionable: {item}")

    rotation = report.get("maintainer_rotation") or {}
    if rotation.get("schema_version") != ROTATION_SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError("Maintainer rotation schema drifted.")
    if len(rotation.get("checklist", [])) < 5:
        raise PlatformOnboardingReadinessError("Maintainer rotation checklist is too short.")
    if set(rotation.get("required_labels", [])) != SLA_LABELS:
        raise PlatformOnboardingReadinessError("Maintainer rotation labels drifted.")

    fixtures = report.get("release_blocker_fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != len(RELEASE_BLOCKER_IDS):
        raise PlatformOnboardingReadinessError("Release blocker fixture count drifted.")
    fixture_results = [
        validate_release_blocker(root, str(item.get("path")), str(item.get("blocker_id")))
        for item in fixtures
        if isinstance(item, dict)
    ]
    if {item["blocker_id"] for item in fixture_results} != RELEASE_BLOCKER_IDS:
        raise PlatformOnboardingReadinessError("Release blocker ids drifted.")

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
            raise PlatformOnboardingReadinessError(f"Onboarding readiness privacy.{key} must be false.")
    if privacy.get("fixtures_are_mock_only") is not True:
        raise PlatformOnboardingReadinessError("Onboarding readiness fixtures must be mock-only.")
    assert_no_leaks(report)
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "walkthrough_count": len(platforms),
        "sla_label_count": len(labels),
        "release_blocker_fixture_count": len(fixture_results),
        "release_blockers": fixture_results,
    }


def validate_support_triage_dependency(root: Path) -> dict[str, Any]:
    report = read_json(require_file(root, "platform/generated/study-anything-platform-support-triage.json"))
    if report.get("schema_version") != SUPPORT_TRIAGE_SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError("Support triage dependency schema drifted.")
    categories = {
        str(item.get("category_id")) for item in report.get("issue_templates", []) if isinstance(item, dict)
    }
    if categories != SUPPORT_CATEGORIES:
        raise PlatformOnboardingReadinessError("Support triage categories drifted.")
    return {"support_triage": report.get("schema_version"), "category_count": len(categories)}


def validate_platform_packs(root: Path) -> dict[str, Any]:
    platform_results: dict[str, Any] = {}
    for platform_id in ("codex", "kimi", "workbuddy", "hermes"):
        pack = read_json(require_file(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
            if command not in commands:
                raise PlatformOnboardingReadinessError(f"{platform_id} pack missing {command}.")
        for item in (REQUIRED_EVIDENCE, REQUIRED_DASHBOARD_EVIDENCE, REQUIRED_BLOCKER_EVIDENCE):
            if item not in evidence:
                raise PlatformOnboardingReadinessError(f"{platform_id} pack missing {item}.")
        platform_results[platform_id] = {
            "onboarding_readiness_command_declared": True,
            "triage_dashboard_evidence_declared": True,
            "release_blocker_evidence_declared": True,
        }
    return platform_results


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(require_file(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise PlatformOnboardingReadinessError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise PlatformOnboardingReadinessError("Ecosystem submission version drifted.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "scripts/generate_platform_onboarding_readiness.py",
        "scripts/verify_platform_onboarding_readiness.py",
        "platform/generated/study-anything-platform-onboarding-readiness.json",
        "platform/generated/study-anything-platform-triage-dashboard.json",
        "platform/generated/study-anything-platform-triage-dashboard.md",
        "docs/adopter-onboarding.md",
        "docs/maintainer-rotation.md",
        *[f"fixtures/platform-release-blockers/{blocker_id}.json" for blocker_id in RELEASE_BLOCKER_IDS],
    }
    missing = sorted(required_assets - shared_assets)
    if missing:
        raise PlatformOnboardingReadinessError(
            f"Ecosystem submission missing onboarding readiness assets: {missing}"
        )
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
        if command not in command_text:
            raise PlatformOnboardingReadinessError(f"Ecosystem submission missing {command}.")
    for schema in (SCHEMA_VERSION, DASHBOARD_SCHEMA_VERSION, RELEASE_BLOCKER_SCHEMA_VERSION):
        if schema not in prove_text:
            raise PlatformOnboardingReadinessError(f"Ecosystem submission must prove {schema}.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "onboarding_assets_included": len(required_assets),
    }


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        raise PlatformOnboardingReadinessError("Adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required_paths = {
        "scripts/generate_platform_onboarding_readiness.py",
        "scripts/verify_platform_onboarding_readiness.py",
        "platform/generated/study-anything-platform-onboarding-readiness.json",
        "platform/generated/study-anything-platform-triage-dashboard.json",
        "platform/generated/study-anything-platform-triage-dashboard.md",
        "docs/adopter-onboarding.md",
        "docs/maintainer-rotation.md",
        "docs/release-notes/v0.3.31-alpha.md",
        *[f"fixtures/platform-release-blockers/{blocker_id}.json" for blocker_id in RELEASE_BLOCKER_IDS],
    }
    missing = sorted(required_paths - paths)
    if missing:
        raise PlatformOnboardingReadinessError(
            f"Adoption pack missing onboarding readiness assets: {missing}"
        )
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    for schema in (SCHEMA_VERSION, DASHBOARD_SCHEMA_VERSION, RELEASE_BLOCKER_SCHEMA_VERSION):
        if schema not in must_verify:
            raise PlatformOnboardingReadinessError(f"Adoption pack must verify {schema}.")
    return {
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "onboarding_assets_included": len(required_paths),
    }


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/adopter-onboarding.md": [
            SCHEMA_VERSION,
            WALKTHROUGH_SCHEMA_VERSION,
            "Kimi",
            "Codex",
            "WorkBuddy",
        ],
        "docs/maintainer-rotation.md": [
            SLA_SCHEMA_VERSION,
            ROTATION_SCHEMA_VERSION,
            "release-blocker",
        ],
        "docs/support-desk.md": [SCHEMA_VERSION, DASHBOARD_SCHEMA_VERSION, "SLA"],
        "docs/adoption.md": [SCHEMA_VERSION, "verify_platform_onboarding_readiness.py"],
        "docs/platform-agent-integrations.md": [SCHEMA_VERSION, "first adopter"],
        "docs/ecosystem-submission.md": [SCHEMA_VERSION, "onboarding readiness"],
        "docs/release-checklist.md": ["verify_platform_onboarding_readiness.py --check"],
        "docs/roadmap.md": ["v0.3.31-alpha", SCHEMA_VERSION],
    }
    for relative_path, needles in checked.items():
        text = require_file(root, relative_path).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise PlatformOnboardingReadinessError(
                f"{relative_path} is missing required text: {missing}"
            )
        assert_text_has_no_leaks(text, relative_path)
    return {"checked_docs": sorted(checked)}


def build_report(root: Path) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Verify that first external adopters can complete onboarding and that maintainers "
            "can triage release blockers without private user data."
        ),
        "onboarding_readiness": validate_report(root),
        "triage_dashboard": validate_dashboard(root),
        "support_triage_dependency": validate_support_triage_dependency(root),
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
            "minimum_command": "python3 scripts/verify_platform_onboarding_readiness.py --check",
            "generate_command": "python3 scripts/generate_platform_onboarding_readiness.py --check",
            "pack_command": REQUIRED_PACK_COMMAND,
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise PlatformOnboardingReadinessError(f"Onboarding readiness report missing: {path}")
    generated = read_json(path)
    if generated.get("schema_version") != SCHEMA_VERSION:
        raise PlatformOnboardingReadinessError("Generated onboarding readiness report schema drifted.")
    if generated.get("version") != RELEASE_VERSION:
        raise PlatformOnboardingReadinessError("Generated onboarding readiness report version drifted.")
    if payload.get("status") != "pass":
        raise PlatformOnboardingReadinessError("Platform onboarding readiness validation did not pass.")
    print("ok    platform onboarding readiness assets are valid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-onboarding-readiness-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_platform_onboarding_readiness.py")
            require_file(root, "platform/generated/study-anything-platform-onboarding-readiness.json")
        report = build_report(root)

    if args.check:
        check_report(Path(args.output), report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_onboarding_readiness failed: {exc}", file=sys.stderr)
        sys.exit(1)
