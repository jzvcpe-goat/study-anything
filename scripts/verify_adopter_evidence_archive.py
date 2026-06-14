#!/usr/bin/env python3
"""Verify adopter evidence archive assets and pack wiring."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-adopter-evidence-archive.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
SCHEMA_VERSION = "adopter-evidence-archive-v1"
FIXTURE_SCHEMA_VERSION = "adopter-evidence-fixture-v1"
RELEASE_VERSION = "v0.3.27-alpha"
PUBLIC_STATUS_SCHEMA_VERSION = "public-support-status-v1"
PUBLIC_DASHBOARD_SCHEMA_VERSION = "public-maintainer-dashboard-v1"
ADOPTION_PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
ECOSYSTEM_SUBMISSION_SCHEMA_VERSION = "ecosystem-submission-v1"
PUBLISHED_IMAGE_EVIDENCE_SCHEMA_VERSION = "published-image-evidence-v1"
RELEASE_ASSET_ADOPTION_SCHEMA_VERSION = "release-asset-adoption-v1"
ARCHIVE_ROOT = "study-anything-adopter-evidence-archive"

FIXTURES = {
    "successful-release",
    "local-ghcr-pull-timeout",
    "needs-repro-issue",
    "release-blocker",
    "platform-blocked",
    "resolved-support-case",
}
PLATFORMS = {"codex", "kimi", "workbuddy"}

REQUIRED_REPORT_ASSETS = {
    "scripts/generate_adopter_evidence_archive.py",
    "scripts/verify_adopter_evidence_archive.py",
    "scripts/generate_published_image_evidence.py",
    "scripts/verify_published_image_evidence.py",
    "docs/adopter-evidence-archive.md",
    "docs/published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-published-image-evidence.sha256",
    "scripts/generate_release_asset_adoption.py",
    "scripts/verify_release_asset_adoption.py",
    "docs/release-asset-adoption.md",
    "platform/generated/study-anything-release-asset-adoption.json",
    "platform/generated/study-anything-release-asset-adoption.md",
    "platform/generated/study-anything-release-asset-adoption.zip",
    "platform/generated/study-anything-release-asset-adoption.sha256",
    "platform/generated/study-anything-adopter-evidence-archive.json",
    "platform/generated/study-anything-adopter-evidence-archive.md",
    "platform/generated/study-anything-adopter-evidence-archive.zip",
    "platform/generated/study-anything-adopter-evidence-archive.sha256",
    *[f"fixtures/adopter-evidence-archive/{fixture}.json" for fixture in FIXTURES],
}
REQUIRED_COMMAND = "verify_adopter_evidence_archive.py --check"
REQUIRED_GENERATOR_COMMAND = "generate_adopter_evidence_archive.py --check"
REQUIRED_PACK_COMMAND = (
    "verify_adopter_evidence_archive.py --pack "
    "platform/generated/study-anything-platform-adoption-pack.zip"
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
    "full_support_bundle_payload",
]


class AdopterEvidenceArchiveError(RuntimeError):
    """Readable adopter evidence archive validation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdopterEvidenceArchiveError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AdopterEvidenceArchiveError(f"JSON object expected: {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise AdopterEvidenceArchiveError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise AdopterEvidenceArchiveError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise AdopterEvidenceArchiveError(
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
        raise AdopterEvidenceArchiveError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise AdopterEvidenceArchiveError(f"Required adopter evidence archive asset missing: {relative_path}")
    return target


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise AdopterEvidenceArchiveError(f"Adopter evidence archive leaked private data: {leaks}")


def assert_text_has_no_leaks(text: str, relative_path: str) -> None:
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in text]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text))
    if leaks:
        raise AdopterEvidenceArchiveError(f"{relative_path} leaked private data: {leaks}")


def validate_file_ref(root: Path, ref: dict[str, Any]) -> None:
    relative_path = str(ref.get("path"))
    path = require_file(root, relative_path)
    if ref.get("sha256") != sha256_file(path):
        raise AdopterEvidenceArchiveError(f"sha256 drifted for {relative_path}")
    if ref.get("bytes") != path.stat().st_size:
        raise AdopterEvidenceArchiveError(f"byte count drifted for {relative_path}")


def validate_fixtures(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture_id in FIXTURES:
        relative_path = f"fixtures/adopter-evidence-archive/{fixture_id}.json"
        payload = read_json(require_file(root, relative_path))
        if payload.get("schema_version") != FIXTURE_SCHEMA_VERSION:
            raise AdopterEvidenceArchiveError(f"{relative_path} schema drifted.")
        if payload.get("version") != RELEASE_VERSION:
            raise AdopterEvidenceArchiveError(f"{relative_path} version drifted.")
        if payload.get("fixture_id") != fixture_id:
            raise AdopterEvidenceArchiveError(f"{relative_path} fixture id drifted.")
        mapping = payload.get("evidence_mapping") or {}
        if mapping.get("linked_archive_schema") != SCHEMA_VERSION:
            raise AdopterEvidenceArchiveError(f"{relative_path} linked archive schema drifted.")
        if not mapping.get("required_public_command"):
            raise AdopterEvidenceArchiveError(f"{relative_path} missing public command.")
        privacy = payload.get("privacy") or {}
        for key, value in privacy.items():
            if isinstance(value, bool) and value is not False:
                raise AdopterEvidenceArchiveError(f"{relative_path} privacy.{key} must be false.")
        assert_no_leaks(payload)
        results.append({"fixture_id": fixture_id, "public_status": payload.get("public_status")})
    return sorted(results, key=lambda item: item["fixture_id"])


def validate_report(root: Path) -> dict[str, Any]:
    report = read_json(require_file(root, "platform/generated/study-anything-adopter-evidence-archive.json"))
    if report.get("schema_version") != SCHEMA_VERSION:
        raise AdopterEvidenceArchiveError("Adopter evidence archive schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise AdopterEvidenceArchiveError("Adopter evidence archive version drifted.")
    if report.get("status") != "pass":
        raise AdopterEvidenceArchiveError("Adopter evidence archive must pass.")
    release_identity = report.get("release_identity") or {}
    if release_identity.get("tag") != RELEASE_VERSION:
        raise AdopterEvidenceArchiveError("Release identity tag drifted.")
    source_schemas = report.get("source_schemas") or {}
    expected_sources = {
        "public_support_status": PUBLIC_STATUS_SCHEMA_VERSION,
        "public_maintainer_dashboard": PUBLIC_DASHBOARD_SCHEMA_VERSION,
        "published_image_evidence": PUBLISHED_IMAGE_EVIDENCE_SCHEMA_VERSION,
        "release_asset_adoption": RELEASE_ASSET_ADOPTION_SCHEMA_VERSION,
        "platform_adoption_pack": ADOPTION_PACK_SCHEMA_VERSION,
        "ecosystem_submission": ECOSYSTEM_SUBMISSION_SCHEMA_VERSION,
    }
    for key, expected_schema in expected_sources.items():
        item = source_schemas.get(key) or {}
        if item.get("schema_version") != expected_schema:
            raise AdopterEvidenceArchiveError(f"{key} source schema drifted.")
        if key == "platform_adoption_pack":
            command_text = "\n".join(
                str(item.get(field, ""))
                for field in ("verification_command", "generation_command", "note")
            )
            for required in (
                "verify_external_adoption.py --pack",
                "generate_platform_adoption_pack.py --check",
                "evidence archive",
            ):
                if required not in command_text:
                    raise AdopterEvidenceArchiveError(
                        f"platform_adoption_pack source missing {required}."
                    )
        else:
            validate_file_ref(root, item.get("ref") or {})
    for ref in report.get("platform_pack_checksums", []):
        validate_file_ref(root, ref)
    for ref in report.get("public_asset_refs", []):
        validate_file_ref(root, ref)
    fixture_ids = {str(item.get("fixture_id")) for item in report.get("fixture_refs", [])}
    if fixture_ids != FIXTURES:
        raise AdopterEvidenceArchiveError("Adopter evidence fixture coverage drifted.")
    commands = "\n".join(str(item) for item in (report.get("operator_reproduction") or {}).get("minimum_commands", []))
    for command in (
        REQUIRED_COMMAND,
        REQUIRED_GENERATOR_COMMAND,
        "verify_published_image_evidence.py --check",
        "generate_published_image_evidence.py --check",
        "verify_release_asset_adoption.py",
        "generate_release_asset_adoption.py --check",
    ):
        if command not in commands:
            raise AdopterEvidenceArchiveError(f"Archive reproduction commands missing {command}.")
    privacy = report.get("privacy_assertions") or {}
    for key, value in privacy.items():
        if isinstance(value, bool) and value is not False:
            raise AdopterEvidenceArchiveError(f"Archive privacy.{key} must be false.")
    archive = report.get("archive") or {}
    if root.resolve() == ROOT.resolve():
        archive_path = require_file(root, "platform/generated/study-anything-adopter-evidence-archive.zip")
        checksum_path = require_file(root, "platform/generated/study-anything-adopter-evidence-archive.sha256")
        archive_hash = sha256_file(archive_path)
        if archive.get("sha256") != archive_hash:
            raise AdopterEvidenceArchiveError("Archive sha256 metadata drifted.")
        checksum_text = checksum_path.read_text(encoding="utf-8").strip()
        if archive_hash not in checksum_text:
            raise AdopterEvidenceArchiveError("Archive sha256 sidecar drifted.")
        with zipfile.ZipFile(archive_path) as evidence_archive:
            names = set(evidence_archive.namelist())
        required_archive_names = {
            f"{ARCHIVE_ROOT}/EVIDENCE_README.md",
            f"{ARCHIVE_ROOT}/manifest.json",
            f"{ARCHIVE_ROOT}/study-anything-adopter-evidence-archive.md",
        }
        if not required_archive_names.issubset(names):
            raise AdopterEvidenceArchiveError("Archive zip is missing required handoff files.")
    assert_no_leaks(report)
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "fixture_count": len(report.get("fixture_refs", [])),
        "public_asset_count": len(report.get("public_asset_refs", [])),
    }


def validate_markdown(root: Path) -> dict[str, Any]:
    text = require_file(root, "platform/generated/study-anything-adopter-evidence-archive.md").read_text(
        encoding="utf-8"
    )
    for needle in (SCHEMA_VERSION, RELEASE_VERSION, "Reproduction Commands", "Fixture Hashes"):
        if needle not in text:
            raise AdopterEvidenceArchiveError(f"Evidence archive Markdown missing {needle}.")
    assert_text_has_no_leaks(text, "platform/generated/study-anything-adopter-evidence-archive.md")
    return {"markdown_checked": True}


def validate_platform_packs(root: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for platform_id in PLATFORMS:
        pack = read_json(require_file(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
            if command not in commands:
                raise AdopterEvidenceArchiveError(f"{platform_id} pack missing {command}.")
        for item in (
            "adopter_evidence_archive.schema_version == adopter-evidence-archive-v1",
            "adopter_evidence_fixture.schema_version == adopter-evidence-fixture-v1",
            "published_image_evidence.schema_version == published-image-evidence-v1",
            "published_image_evidence_fixture.schema_version == published-image-evidence-fixture-v1",
            "release_asset_adoption.schema_version == release-asset-adoption-v1",
            "release_asset_adoption_fixture.schema_version == release-asset-adoption-fixture-v1",
            "release_asset_adoption_proof.schema_version == release-asset-adoption-proof-v1",
        ):
            if item not in evidence:
                raise AdopterEvidenceArchiveError(f"{platform_id} pack missing {item}.")
        results[platform_id] = {"command_declared": True, "acceptance_evidence_declared": True}
    return results


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(require_file(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != ECOSYSTEM_SUBMISSION_SCHEMA_VERSION:
        raise AdopterEvidenceArchiveError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise AdopterEvidenceArchiveError("Ecosystem submission version drifted.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    missing = sorted(REQUIRED_REPORT_ASSETS - shared_assets)
    if missing:
        raise AdopterEvidenceArchiveError(f"Ecosystem submission missing adopter evidence assets: {missing}")
    acceptance = submission.get("acceptance") or {}
    commands = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    must_prove = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
        if command not in commands:
            raise AdopterEvidenceArchiveError(f"Ecosystem submission missing {command}.")
    for schema in (SCHEMA_VERSION, FIXTURE_SCHEMA_VERSION, RELEASE_ASSET_ADOPTION_SCHEMA_VERSION):
        if schema not in must_prove:
            raise AdopterEvidenceArchiveError(f"Ecosystem submission must prove {schema}.")
    return {"schema_version": submission.get("schema_version"), "version": submission.get("version")}


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != ADOPTION_PACK_SCHEMA_VERSION:
        raise AdopterEvidenceArchiveError("Adoption pack schema drifted.")
    if manifest.get("version") != RELEASE_VERSION:
        raise AdopterEvidenceArchiveError("Adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    missing = sorted(REQUIRED_REPORT_ASSETS - paths)
    if missing:
        raise AdopterEvidenceArchiveError(f"Adoption pack missing adopter evidence assets: {missing}")
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    for schema in (SCHEMA_VERSION, FIXTURE_SCHEMA_VERSION, RELEASE_ASSET_ADOPTION_SCHEMA_VERSION):
        if schema not in must_verify:
            raise AdopterEvidenceArchiveError(f"Adoption pack must verify {schema}.")
    return {"schema_version": manifest.get("schema_version"), "version": manifest.get("version")}


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/adopter-evidence-archive.md": [SCHEMA_VERSION, FIXTURE_SCHEMA_VERSION, REQUIRED_COMMAND],
        "docs/published-image-evidence.md": [PUBLISHED_IMAGE_EVIDENCE_SCHEMA_VERSION],
        "docs/release-asset-adoption.md": [RELEASE_ASSET_ADOPTION_SCHEMA_VERSION],
        "docs/adoption.md": [SCHEMA_VERSION, "verify_adopter_evidence_archive.py"],
        "docs/platform-agent-integrations.md": [SCHEMA_VERSION, "evidence archive"],
        "docs/support-desk.md": [SCHEMA_VERSION, "handoff"],
        "docs/adopter-onboarding.md": [SCHEMA_VERSION, "External Adopter Evidence"],
        "docs/maintainer-rotation.md": [SCHEMA_VERSION, "maintainer handoff"],
        "docs/ecosystem-submission.md": [SCHEMA_VERSION, "Adopter Evidence Archive"],
        "docs/release-checklist.md": ["verify_adopter_evidence_archive.py --check"],
        "docs/roadmap.md": ["v0.3.27-alpha", SCHEMA_VERSION],
    }
    for relative_path, needles in checked.items():
        text = require_file(root, relative_path).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise AdopterEvidenceArchiveError(f"{relative_path} missing required text: {missing}")
        assert_text_has_no_leaks(text, relative_path)
    return {"checked_docs": sorted(checked)}


def build_report(root: Path) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": "Verify public adopter evidence archive and maintainer handoff assets.",
        "adopter_evidence_archive": validate_report(root),
        "adopter_evidence_markdown": validate_markdown(root),
        "adopter_evidence_fixtures": validate_fixtures(root),
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
            "support_bundle_private_payload_in_report": False,
            "automatic_upload": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_adopter_evidence_archive.py --check",
            "generate_command": "python3 scripts/generate_adopter_evidence_archive.py --check",
            "pack_command": REQUIRED_PACK_COMMAND,
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise AdopterEvidenceArchiveError(f"Adopter evidence archive report missing: {path}")
    generated = read_json(path)
    if generated.get("schema_version") != SCHEMA_VERSION:
        raise AdopterEvidenceArchiveError("Generated adopter evidence archive schema drifted.")
    if generated.get("version") != RELEASE_VERSION:
        raise AdopterEvidenceArchiveError("Generated adopter evidence archive version drifted.")
    if payload.get("status") != "pass":
        raise AdopterEvidenceArchiveError("Adopter evidence archive validation did not pass.")
    print("ok    adopter evidence archive assets are valid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--check", action="store_true", help="Require generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-adopter-evidence-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_adopter_evidence_archive.py")
            require_file(root, "platform/generated/study-anything-adopter-evidence-archive.json")
        report = build_report(root)

    if args.check:
        check_report(Path(args.output), report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_adopter_evidence_archive failed: {exc}", file=sys.stderr)
        sys.exit(1)
