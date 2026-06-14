#!/usr/bin/env python3
"""Verify public support status and maintainer dashboard assets."""

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
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-public-support-status.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
PUBLIC_STATUS_SCHEMA_VERSION = "public-support-status-v1"
PUBLIC_DASHBOARD_SCHEMA_VERSION = "public-maintainer-dashboard-v1"
STATUS_LINKAGE_SCHEMA_VERSION = "public-status-linkage-fixture-v1"
ONBOARDING_SCHEMA_VERSION = "platform-onboarding-readiness-v1"
SUPPORT_TRIAGE_SCHEMA_VERSION = "platform-support-triage-v1"
TRIAGE_DASHBOARD_SCHEMA_VERSION = "platform-triage-dashboard-v1"
RELEASE_VERSION = "v0.3.23-alpha"
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
RELEASE_BLOCKERS = {
    "tool_import_blocker",
    "local_gateway_blocker",
    "published_image_blocker",
    "agent_eval_blocker",
    "support_bundle_privacy_blocker",
}
REQUIRED_COMMAND = "verify_platform_public_support_status.py --check"
REQUIRED_GENERATOR_COMMAND = "generate_platform_public_support_status.py --check"
REQUIRED_PACK_COMMAND = (
    "verify_platform_public_support_status.py --pack "
    "platform/generated/study-anything-platform-adoption-pack.zip"
)
REQUIRED_EVIDENCE = "public_support_status.schema_version == public-support-status-v1"
REQUIRED_DASHBOARD_EVIDENCE = (
    "public_maintainer_dashboard.schema_version == public-maintainer-dashboard-v1"
)
REQUIRED_LINKAGE_EVIDENCE = (
    "public_status_linkage_fixture.schema_version == public-status-linkage-fixture-v1"
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


class PublicSupportStatusError(RuntimeError):
    """Readable public support status validation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PublicSupportStatusError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PublicSupportStatusError(f"JSON object expected: {path}")
    return payload


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise PublicSupportStatusError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise PublicSupportStatusError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise PublicSupportStatusError(
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
        raise PublicSupportStatusError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise PublicSupportStatusError(f"Required public support status asset missing: {relative_path}")
    return target


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PublicSupportStatusError(f"Public support status leaked private data: {leaks}")


def assert_text_has_no_leaks(text: str, relative_path: str) -> None:
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in text]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text))
    if leaks:
        raise PublicSupportStatusError(f"{relative_path} leaked private data: {leaks}")


def validate_status_linkage(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for label in SLA_LABELS:
        relative_path = f"fixtures/platform-status-links/{label}.json"
        payload = read_json(require_file(root, relative_path))
        if payload.get("schema_version") != STATUS_LINKAGE_SCHEMA_VERSION:
            raise PublicSupportStatusError(f"{relative_path} schema drifted.")
        if payload.get("version") != RELEASE_VERSION:
            raise PublicSupportStatusError(f"{relative_path} version drifted.")
        if payload.get("label") != label:
            raise PublicSupportStatusError(f"{relative_path} label drifted.")
        public_fields = payload.get("public_fields")
        if not isinstance(public_fields, dict) or public_fields.get("linked_schema") != PUBLIC_STATUS_SCHEMA_VERSION:
            raise PublicSupportStatusError(f"{relative_path} public fields are incomplete.")
        excluded = set(str(item) for item in payload.get("private_fields_excluded", []))
        if "full_support_bundle_payload" not in excluded or "real_model_keys" not in excluded:
            raise PublicSupportStatusError(f"{relative_path} private exclusions drifted.")
        privacy = payload.get("privacy") or {}
        for key in (
            "raw_source_text_included",
            "learner_answers_included",
            "agent_prompts_included",
            "real_model_keys_included",
            "agent_endpoint_secrets_included",
            "browser_video_private_context_included",
            "personal_profile_data_included",
            "automatic_upload",
        ):
            if privacy.get(key) is not False:
                raise PublicSupportStatusError(f"{relative_path} privacy.{key} must be false.")
        assert_no_leaks(payload)
        results.append({"label": label, "path": relative_path, "public_status": payload["public_status"]})
    return sorted(results, key=lambda item: item["label"])


def validate_public_status(root: Path) -> dict[str, Any]:
    report = read_json(require_file(root, "platform/generated/study-anything-public-support-status.json"))
    if report.get("schema_version") != PUBLIC_STATUS_SCHEMA_VERSION:
        raise PublicSupportStatusError("Public support status schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise PublicSupportStatusError("Public support status version drifted.")
    if report.get("status") != "pass":
        raise PublicSupportStatusError("Public support status must pass.")
    source_reports = report.get("source_reports") or {}
    expected_sources = {
        "onboarding_readiness_schema": ONBOARDING_SCHEMA_VERSION,
        "support_triage_schema": SUPPORT_TRIAGE_SCHEMA_VERSION,
        "triage_dashboard_schema": TRIAGE_DASHBOARD_SCHEMA_VERSION,
    }
    for key, expected in expected_sources.items():
        if source_reports.get(key) != expected:
            raise PublicSupportStatusError(f"Public status source {key} drifted.")
    platforms = report.get("platform_statuses")
    if not isinstance(platforms, list) or {str(item.get("platform_id")) for item in platforms} != PLATFORMS:
        raise PublicSupportStatusError("Public status platform coverage drifted.")
    for item in platforms:
        if not item.get("last_verified_commands") or item.get("public_status") != "supported_for_first_adopter":
            raise PublicSupportStatusError(f"Public platform status is not actionable: {item}")
    blockers = report.get("known_blockers")
    if not isinstance(blockers, list) or {str(item.get("blocker_id")) for item in blockers} != RELEASE_BLOCKERS:
        raise PublicSupportStatusError("Public status blocker coverage drifted.")
    for item in blockers:
        if "support_bundle" in item:
            raise PublicSupportStatusError("Public blocker must not include private support_bundle.")
        if not (item.get("fixture_ref") or {}).get("sha256"):
            raise PublicSupportStatusError(f"Public blocker missing fixture hash: {item}")
    maintainer_sla = report.get("maintainer_sla") or {}
    if set(maintainer_sla.get("labels", [])) != SLA_LABELS:
        raise PublicSupportStatusError("Public status SLA labels drifted.")
    if maintainer_sla.get("status_linkage_schema") != STATUS_LINKAGE_SCHEMA_VERSION:
        raise PublicSupportStatusError("Public status linkage schema drifted.")
    linkage_refs = maintainer_sla.get("status_linkage_refs")
    if not isinstance(linkage_refs, list) or {str(item.get("label")) for item in linkage_refs} != SLA_LABELS:
        raise PublicSupportStatusError("Public status linkage refs drifted.")
    readiness = report.get("release_readiness") or {}
    if readiness.get("release_gate") != "scripts/release_check.sh":
        raise PublicSupportStatusError("Public status release gate drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "agent_endpoint_secrets_in_report",
        "real_model_keys_in_report",
        "browser_video_private_context_in_report",
        "personal_profile_data_in_report",
        "support_bundle_private_fields_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise PublicSupportStatusError(f"Public status privacy.{key} must be false.")
    assert_no_leaks(report)
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "platform_count": len(platforms),
        "known_blocker_count": len(blockers),
        "sla_label_count": len(maintainer_sla.get("labels", [])),
    }


def validate_dashboard(root: Path) -> dict[str, Any]:
    dashboard = read_json(require_file(root, "platform/generated/study-anything-public-maintainer-dashboard.json"))
    if dashboard.get("schema_version") != PUBLIC_DASHBOARD_SCHEMA_VERSION:
        raise PublicSupportStatusError("Public maintainer dashboard schema drifted.")
    if dashboard.get("version") != RELEASE_VERSION:
        raise PublicSupportStatusError("Public maintainer dashboard version drifted.")
    if dashboard.get("status") != "pass":
        raise PublicSupportStatusError("Public maintainer dashboard must pass.")
    summary = dashboard.get("summary") or {}
    if summary.get("platform_count") != len(PLATFORMS):
        raise PublicSupportStatusError("Dashboard platform count drifted.")
    if summary.get("known_blocker_count") != len(RELEASE_BLOCKERS):
        raise PublicSupportStatusError("Dashboard blocker count drifted.")
    if summary.get("status_linkage_fixture_count") != len(SLA_LABELS):
        raise PublicSupportStatusError("Dashboard linkage count drifted.")
    privacy = dashboard.get("privacy") or {}
    for key, value in privacy.items():
        if isinstance(value, bool) and value is not False:
            raise PublicSupportStatusError(f"Dashboard privacy.{key} must be false.")
    md = require_file(root, "platform/generated/study-anything-public-maintainer-dashboard.md").read_text(
        encoding="utf-8"
    )
    for needle in (PUBLIC_DASHBOARD_SCHEMA_VERSION, RELEASE_VERSION, "Known Blocker Fixtures"):
        if needle not in md:
            raise PublicSupportStatusError(f"Dashboard Markdown missing {needle}.")
    assert_no_leaks(dashboard)
    assert_text_has_no_leaks(md, "platform/generated/study-anything-public-maintainer-dashboard.md")
    return {
        "schema_version": dashboard.get("schema_version"),
        "known_blocker_count": summary.get("known_blocker_count"),
        "status_linkage_fixture_count": summary.get("status_linkage_fixture_count"),
    }


def validate_platform_packs(root: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for platform_id in ("codex", "kimi", "workbuddy"):
        pack = read_json(require_file(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
            if command not in commands:
                raise PublicSupportStatusError(f"{platform_id} pack missing {command}.")
        for item in (REQUIRED_EVIDENCE, REQUIRED_DASHBOARD_EVIDENCE, REQUIRED_LINKAGE_EVIDENCE):
            if item not in evidence:
                raise PublicSupportStatusError(f"{platform_id} pack missing {item}.")
        results[platform_id] = {"command_declared": True, "acceptance_evidence_declared": True}
    return results


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(require_file(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise PublicSupportStatusError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise PublicSupportStatusError("Ecosystem submission version drifted.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "scripts/generate_platform_public_support_status.py",
        "scripts/verify_platform_public_support_status.py",
        "platform/generated/study-anything-public-support-status.json",
        "platform/generated/study-anything-public-maintainer-dashboard.json",
        "platform/generated/study-anything-public-maintainer-dashboard.md",
        "docs/public-support-status.md",
        *[f"fixtures/platform-status-links/{label}.json" for label in SLA_LABELS],
    }
    missing = sorted(required_assets - shared_assets)
    if missing:
        raise PublicSupportStatusError(f"Ecosystem submission missing public status assets: {missing}")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
        if command not in command_text:
            raise PublicSupportStatusError(f"Ecosystem submission missing {command}.")
    for schema in (
        PUBLIC_STATUS_SCHEMA_VERSION,
        PUBLIC_DASHBOARD_SCHEMA_VERSION,
        STATUS_LINKAGE_SCHEMA_VERSION,
    ):
        if schema not in prove_text:
            raise PublicSupportStatusError(f"Ecosystem submission must prove {schema}.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "public_status_assets_included": len(required_assets),
    }


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        raise PublicSupportStatusError("Adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required_paths = {
        "scripts/generate_platform_public_support_status.py",
        "scripts/verify_platform_public_support_status.py",
        "platform/generated/study-anything-public-support-status.json",
        "platform/generated/study-anything-public-maintainer-dashboard.json",
        "platform/generated/study-anything-public-maintainer-dashboard.md",
        "docs/public-support-status.md",
        "docs/release-notes/v0.3.23-alpha.md",
        *[f"fixtures/platform-status-links/{label}.json" for label in SLA_LABELS],
    }
    missing = sorted(required_paths - paths)
    if missing:
        raise PublicSupportStatusError(f"Adoption pack missing public support status assets: {missing}")
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    for schema in (
        PUBLIC_STATUS_SCHEMA_VERSION,
        PUBLIC_DASHBOARD_SCHEMA_VERSION,
        STATUS_LINKAGE_SCHEMA_VERSION,
    ):
        if schema not in must_verify:
            raise PublicSupportStatusError(f"Adoption pack must verify {schema}.")
    return {
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "public_status_assets_included": len(required_paths),
    }


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/public-support-status.md": [
            PUBLIC_STATUS_SCHEMA_VERSION,
            PUBLIC_DASHBOARD_SCHEMA_VERSION,
            STATUS_LINKAGE_SCHEMA_VERSION,
        ],
        "docs/adoption.md": [PUBLIC_STATUS_SCHEMA_VERSION, "verify_platform_public_support_status.py"],
        "docs/platform-agent-integrations.md": [PUBLIC_STATUS_SCHEMA_VERSION, "public support"],
        "docs/support-desk.md": [PUBLIC_STATUS_SCHEMA_VERSION, "public maintainer"],
        "docs/adopter-onboarding.md": [PUBLIC_STATUS_SCHEMA_VERSION, "public status"],
        "docs/maintainer-rotation.md": [PUBLIC_STATUS_SCHEMA_VERSION, "public dashboard"],
        "docs/ecosystem-submission.md": [PUBLIC_STATUS_SCHEMA_VERSION, "public support status"],
        "docs/release-checklist.md": ["verify_platform_public_support_status.py --check"],
        "docs/roadmap.md": ["v0.3.23-alpha", PUBLIC_STATUS_SCHEMA_VERSION],
    }
    for relative_path, needles in checked.items():
        text = require_file(root, relative_path).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise PublicSupportStatusError(f"{relative_path} missing required text: {missing}")
        assert_text_has_no_leaks(text, relative_path)
    return {"checked_docs": sorted(checked)}


def build_report(root: Path) -> dict[str, Any]:
    report = {
        "schema_version": PUBLIC_STATUS_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Verify that public maintainer status evidence is publishable without private support "
            "bundle or learning data."
        ),
        "public_support_status": validate_public_status(root),
        "public_maintainer_dashboard": validate_dashboard(root),
        "status_linkage_fixtures": validate_status_linkage(root),
        "platform_packs": validate_platform_packs(root),
        "ecosystem_submission": validate_submission(root),
        "adoption_pack": validate_adoption_pack(root),
        "docs": validate_docs(root),
        "privacy_assertions": {
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_prompts_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "real_model_keys_in_report": False,
            "browser_video_private_context_in_report": False,
            "personal_profile_data_in_report": False,
            "support_bundle_private_fields_in_report": False,
            "automatic_upload": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_platform_public_support_status.py --check",
            "generate_command": "python3 scripts/generate_platform_public_support_status.py --check",
            "pack_command": REQUIRED_PACK_COMMAND,
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise PublicSupportStatusError(f"Public support status report missing: {path}")
    generated = read_json(path)
    if generated.get("schema_version") != PUBLIC_STATUS_SCHEMA_VERSION:
        raise PublicSupportStatusError("Generated public support status schema drifted.")
    if generated.get("version") != RELEASE_VERSION:
        raise PublicSupportStatusError("Generated public support status version drifted.")
    if payload.get("status") != "pass":
        raise PublicSupportStatusError("Public support status validation did not pass.")
    print("ok    platform public support status assets are valid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--check", action="store_true", help="Require generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-public-support-status-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_platform_public_support_status.py")
            require_file(root, "platform/generated/study-anything-public-support-status.json")
        report = build_report(root)

    if args.check:
        check_report(Path(args.output), report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_public_support_status failed: {exc}", file=sys.stderr)
        sys.exit(1)
