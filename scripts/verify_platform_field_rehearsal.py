#!/usr/bin/env python3
"""Verify external platform field-adoption rehearsal and import-failure fixtures."""

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
SCHEMA_VERSION = "platform-field-adoption-rehearsal-v1"
FIXTURE_SCHEMA_VERSION = "platform-import-failure-fixture-v1"
FEEDBACK_SCHEMA_VERSION = "platform-feedback-package-v1"
RELEASE_VERSION = "v0.3.26-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-platform-field-rehearsal.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
PLATFORM_IDS = ("codex", "kimi", "workbuddy")
REHEARSAL_PLATFORM_IDS = ("kimi", "codex", "workbuddy", "generic")
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
REQUIRED_COMMAND = "verify_platform_field_rehearsal.py --check"
REQUIRED_GENERATOR_COMMAND = "generate_platform_field_rehearsal.py --check"
REQUIRED_EVIDENCE = (
    "platform_field_rehearsal.schema_version == platform-field-adoption-rehearsal-v1"
)
REQUIRED_FIXTURE_EVIDENCE = (
    "platform_import_failure_fixture.schema_version == platform-import-failure-fixture-v1"
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
    "learner@example.com",
    "AGENT_ENDPOINT=http",
]


class PlatformFieldRehearsalError(RuntimeError):
    """Readable platform field-rehearsal validation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PlatformFieldRehearsalError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlatformFieldRehearsalError(f"JSON object expected: {path}")
    return value


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise PlatformFieldRehearsalError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise PlatformFieldRehearsalError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise PlatformFieldRehearsalError(
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
        raise PlatformFieldRehearsalError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise PlatformFieldRehearsalError(f"Required field rehearsal asset is missing: {relative_path}")
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    text = require_file(root, relative_path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise PlatformFieldRehearsalError(f"{relative_path} is missing required text: {missing}")
    return text


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformFieldRehearsalError(
            f"Platform field rehearsal leaked private data: {leaks}"
        )


def validate_fixture(root: Path, relative_path: str, failure_id: str) -> dict[str, Any]:
    payload = read_json(require_file(root, relative_path))
    if payload.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise PlatformFieldRehearsalError(f"{relative_path} fixture schema drifted.")
    if payload.get("version") != RELEASE_VERSION:
        raise PlatformFieldRehearsalError(f"{relative_path} fixture version drifted.")
    if payload.get("failure_id") != failure_id:
        raise PlatformFieldRehearsalError(f"{relative_path} failure_id drifted.")
    diagnosis = payload.get("diagnosis") or {}
    if not diagnosis.get("detection_signal") or not diagnosis.get("likely_cause"):
        raise PlatformFieldRehearsalError(f"{relative_path} fixture is not actionable.")
    if not isinstance(diagnosis.get("next_commands"), list) or not diagnosis["next_commands"]:
        raise PlatformFieldRehearsalError(f"{relative_path} fixture must include next_commands.")
    privacy = payload.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "learner_answers_included",
        "agent_prompts_included",
        "real_model_keys_included",
        "agent_endpoint_secrets_included",
        "browser_video_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise PlatformFieldRehearsalError(f"{relative_path} privacy.{key} must be false.")
    assert_no_leaks(payload)
    return {
        "failure_id": failure_id,
        "path": relative_path,
        "schema_version": payload.get("schema_version"),
        "next_command_count": len(diagnosis["next_commands"]),
    }


def validate_report(root: Path) -> dict[str, Any]:
    report_path = safe_relative(
        root, "platform/generated/study-anything-platform-field-rehearsal.json"
    )
    report = read_json(report_path)
    if report.get("schema_version") != SCHEMA_VERSION:
        raise PlatformFieldRehearsalError("Field rehearsal report schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise PlatformFieldRehearsalError("Field rehearsal report version drifted.")
    if report.get("status") != "pass":
        raise PlatformFieldRehearsalError("Field rehearsal report must pass.")
    platforms = report.get("platforms")
    if not isinstance(platforms, list):
        raise PlatformFieldRehearsalError("Field rehearsal report must include platforms.")
    platform_ids = {str(item.get("platform_id")) for item in platforms if isinstance(item, dict)}
    if platform_ids != set(REHEARSAL_PLATFORM_IDS):
        raise PlatformFieldRehearsalError(f"Field rehearsal platforms drifted: {sorted(platform_ids)}")
    for platform in platforms:
        events = platform.get("events") if isinstance(platform, dict) else None
        if not isinstance(events, list) or len(events) < 5:
            raise PlatformFieldRehearsalError("Each platform transcript must include at least 5 events.")
    quirks = report.get("quirks_catalog")
    if not isinstance(quirks, list):
        raise PlatformFieldRehearsalError("Field rehearsal report must include quirks_catalog.")
    quirk_ids = {str(item.get("id")) for item in quirks if isinstance(item, dict)}
    if quirk_ids != set(QUIRK_IDS):
        raise PlatformFieldRehearsalError(f"Quirks catalog drifted: {sorted(quirk_ids)}")
    for quirk in quirks:
        if not quirk.get("detection_signal") or not quirk.get("likely_cause"):
            raise PlatformFieldRehearsalError(f"Quirk is not actionable: {quirk}")
        if not isinstance(quirk.get("next_commands"), list) or not quirk["next_commands"]:
            raise PlatformFieldRehearsalError(f"Quirk must include next_commands: {quirk}")
    fixtures = report.get("failed_import_fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != len(QUIRK_IDS):
        raise PlatformFieldRehearsalError("Field rehearsal report must include every failure fixture.")
    fixture_results = [
        validate_fixture(root, str(item.get("path")), str(item.get("failure_id")))
        for item in fixtures
        if isinstance(item, dict)
    ]
    if len(fixture_results) != len(QUIRK_IDS):
        raise PlatformFieldRehearsalError("Fixture result count drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_in_report",
        "agent_endpoint_secrets_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "browser_video_private_context_in_report",
    ):
        if privacy.get(key) is not False:
            raise PlatformFieldRehearsalError(f"Field rehearsal privacy.{key} must be false.")
    assert_no_leaks(report)
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "platform_count": len(platforms),
        "quirk_count": len(quirks),
        "fixture_count": len(fixture_results),
        "fixtures": fixture_results,
    }


def validate_feedback_package(root: Path) -> dict[str, Any]:
    payload = read_json(
        safe_relative(root, "platform/generated/study-anything-platform-feedback-package.json")
    )
    if payload.get("schema_version") != FEEDBACK_SCHEMA_VERSION:
        raise PlatformFieldRehearsalError("Feedback package schema drifted.")
    if payload.get("version") != RELEASE_VERSION:
        raise PlatformFieldRehearsalError("Feedback package version drifted.")
    privacy = payload.get("privacy") or {}
    if privacy.get("redacted") is not True or privacy.get("automatic_upload") is not False:
        raise PlatformFieldRehearsalError("Feedback package must be redacted and local-only.")
    assert_no_leaks(payload)
    return {
        "schema_version": payload.get("schema_version"),
        "version": payload.get("version"),
        "redacted": True,
        "automatic_upload": False,
    }


def validate_platform_packs(root: Path) -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    for platform_id in PLATFORM_IDS:
        pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
            if command not in commands:
                raise PlatformFieldRehearsalError(f"{platform_id} pack missing {command}.")
        for item in (REQUIRED_EVIDENCE, REQUIRED_FIXTURE_EVIDENCE):
            if item not in evidence:
                raise PlatformFieldRehearsalError(f"{platform_id} pack missing {item}.")
        platforms[platform_id] = {
            "integration_mode": pack.get("integration_mode"),
            "field_rehearsal_command_declared": True,
            "fixture_evidence_declared": True,
        }
    return platforms


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise PlatformFieldRehearsalError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise PlatformFieldRehearsalError("Ecosystem submission version drifted.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "scripts/generate_platform_field_rehearsal.py",
        "scripts/verify_platform_field_rehearsal.py",
        "platform/generated/study-anything-platform-field-rehearsal.json",
        *[f"fixtures/platform-import-failures/{failure_id}.json" for failure_id in QUIRK_IDS],
    }
    missing = sorted(required_assets - shared_assets)
    if missing:
        raise PlatformFieldRehearsalError(f"Ecosystem submission missing field assets: {missing}")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
        if command not in command_text:
            raise PlatformFieldRehearsalError(f"Ecosystem submission missing {command}.")
    for schema in (SCHEMA_VERSION, FIXTURE_SCHEMA_VERSION):
        if schema not in prove_text:
            raise PlatformFieldRehearsalError(f"Ecosystem submission must prove {schema}.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "field_assets_included": len(required_assets),
    }


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        raise PlatformFieldRehearsalError("Adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required_paths = {
        "scripts/generate_platform_field_rehearsal.py",
        "scripts/verify_platform_field_rehearsal.py",
        "platform/generated/study-anything-platform-field-rehearsal.json",
        "docs/release-notes/v0.3.26-alpha.md",
        *[f"fixtures/platform-import-failures/{failure_id}.json" for failure_id in QUIRK_IDS],
    }
    missing = sorted(required_paths - paths)
    if missing:
        raise PlatformFieldRehearsalError(f"Adoption pack missing field assets: {missing}")
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    for schema in (SCHEMA_VERSION, FIXTURE_SCHEMA_VERSION):
        if schema not in must_verify:
            raise PlatformFieldRehearsalError(f"Adoption pack must verify {schema}.")
    return {
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "field_assets_included": len(required_paths),
    }


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/adoption.md": [
            SCHEMA_VERSION,
            FIXTURE_SCHEMA_VERSION,
            "verify_platform_field_rehearsal.py",
        ],
        "docs/platform-agent-integrations.md": [
            SCHEMA_VERSION,
            "import quirks catalog",
            "failed import fixture",
        ],
        "docs/ecosystem-submission.md": [
            SCHEMA_VERSION,
            FIXTURE_SCHEMA_VERSION,
            "generate_platform_field_rehearsal.py",
        ],
        "docs/release-checklist.md": [
            "verify_platform_field_rehearsal.py --check",
            "generate_platform_field_rehearsal.py --check",
        ],
        "docs/roadmap.md": ["v0.3.26-alpha", SCHEMA_VERSION],
    }
    for path, needles in checked.items():
        assert_contains(root, path, *needles)
    return {"checked_docs": sorted(checked)}


def build_report(root: Path) -> dict[str, Any]:
    for path in (
        "scripts/generate_platform_field_rehearsal.py",
        "scripts/verify_platform_field_rehearsal.py",
        "platform/generated/study-anything-platform-field-rehearsal.json",
        "platform/generated/study-anything-platform-feedback-package.json",
    ):
        require_file(root, path)
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Make platform field adoption rehearsable before marketplace submission "
            "and make common import failures actionable without leaking learning data."
        ),
        "field_rehearsal": validate_report(root),
        "feedback_package": validate_feedback_package(root),
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
            "fixtures_are_mock_only": True,
            "feedback_upload_is_manual": True,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_platform_field_rehearsal.py --check",
            "generate_command": "python3 scripts/generate_platform_field_rehearsal.py --check",
            "pack_command": (
                "python3 scripts/verify_platform_field_rehearsal.py "
                "--pack platform/generated/study-anything-platform-adoption-pack.zip"
            ),
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise PlatformFieldRehearsalError(f"Field rehearsal report missing: {path}")
    generated = read_json(path)
    if generated.get("schema_version") != SCHEMA_VERSION:
        raise PlatformFieldRehearsalError("Generated field rehearsal report schema drifted.")
    if generated.get("version") != RELEASE_VERSION:
        raise PlatformFieldRehearsalError("Generated field rehearsal report version drifted.")
    if payload.get("status") != "pass":
        raise PlatformFieldRehearsalError("Platform field rehearsal validation did not pass.")
    print("ok    platform field rehearsal assets are valid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--write", action="store_true", help="Write the generated verification report.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-field-rehearsal-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_platform_field_rehearsal.py")
            require_file(root, "platform/generated/study-anything-platform-field-rehearsal.json")
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
        print(f"verify_platform_field_rehearsal failed: {exc}", file=sys.stderr)
        sys.exit(1)
