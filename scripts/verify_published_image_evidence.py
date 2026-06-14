#!/usr/bin/env python3
"""Verify published-image deployment evidence assets and pack wiring."""

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
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-published-image-evidence.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
SCHEMA_VERSION = "published-image-evidence-v1"
FIXTURE_SCHEMA_VERSION = "published-image-evidence-fixture-v1"
RELEASE_VERSION = "v0.3.28-alpha"
ADOPTION_PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
ECOSYSTEM_SUBMISSION_SCHEMA_VERSION = "ecosystem-submission-v1"
ARCHIVE_ROOT = "study-anything-published-image-evidence"

FIXTURES = {
    "manifest-pass-local-pull-timeout",
    "cached-image-missing",
    "compose-up-timeout",
    "manifest-only-runtime-unverified",
    "manifest-missing-platform",
    "docker-images-failed",
    "ghcr-unavailable",
    "remote-smoke-pass",
    "remote-smoke-failed",
}
EXPECTED_CLASSIFICATIONS = {
    "local_pull_timeout_with_valid_release_evidence",
    "cached_image_missing",
    "compose_up_timeout",
    "manifest_available_runtime_unverified",
    "published_image_platform_gap",
    "ci_image_publish_failed",
    "registry_or_network_unavailable",
    "published_image_ready",
    "published_image_runtime_failed",
}
PLATFORMS = {"codex", "kimi", "workbuddy"}

REQUIRED_REPORT_ASSETS = {
    "scripts/generate_published_image_evidence.py",
    "scripts/verify_published_image_evidence.py",
    "docs/published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-published-image-evidence.sha256",
    *[f"fixtures/published-image-evidence/{fixture}.json" for fixture in FIXTURES],
}
REQUIRED_COMMAND = "verify_published_image_evidence.py --check"
REQUIRED_GENERATOR_COMMAND = "generate_published_image_evidence.py --check"
REQUIRED_PACK_COMMAND = (
    "verify_published_image_evidence.py --pack "
    "platform/generated/study-anything-platform-adoption-pack.zip"
)

FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
    re.compile(r"/Users/[^\\s\"']+"),
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


class PublishedImageEvidenceError(RuntimeError):
    """Readable published-image evidence validation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PublishedImageEvidenceError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PublishedImageEvidenceError(f"JSON object expected: {path}")
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
            raise PublishedImageEvidenceError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise PublishedImageEvidenceError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise PublishedImageEvidenceError(
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
        raise PublishedImageEvidenceError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise PublishedImageEvidenceError(f"Required published-image evidence asset missing: {relative_path}")
    return target


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PublishedImageEvidenceError(f"Published-image evidence leaked private data: {leaks}")


def assert_text_has_no_leaks(text: str, relative_path: str) -> None:
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in text]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text))
    if leaks:
        raise PublishedImageEvidenceError(f"{relative_path} leaked private data: {leaks}")


def validate_file_ref(root: Path, ref: dict[str, Any]) -> None:
    relative_path = str(ref.get("path"))
    path = require_file(root, relative_path)
    if ref.get("sha256") != sha256_file(path):
        raise PublishedImageEvidenceError(f"sha256 drifted for {relative_path}")
    if ref.get("bytes") != path.stat().st_size:
        raise PublishedImageEvidenceError(f"byte count drifted for {relative_path}")


def validate_fixtures(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    classifications: set[str] = set()
    for fixture_id in FIXTURES:
        relative_path = f"fixtures/published-image-evidence/{fixture_id}.json"
        payload = read_json(require_file(root, relative_path))
        if payload.get("schema_version") != FIXTURE_SCHEMA_VERSION:
            raise PublishedImageEvidenceError(f"{relative_path} schema drifted.")
        if payload.get("version") != RELEASE_VERSION:
            raise PublishedImageEvidenceError(f"{relative_path} version drifted.")
        if payload.get("fixture_id") != fixture_id:
            raise PublishedImageEvidenceError(f"{relative_path} fixture id drifted.")
        classification = str(payload.get("classification"))
        classifications.add(classification)
        signals = payload.get("signals") or {}
        if signals.get("tag") != RELEASE_VERSION:
            raise PublishedImageEvidenceError(f"{relative_path} tag drifted.")
        if "ghcr.io/jzvcpe-goat/study-anything/api:" not in str(signals.get("api_image")):
            raise PublishedImageEvidenceError(f"{relative_path} API image drifted.")
        if not payload.get("operator_next_step"):
            raise PublishedImageEvidenceError(f"{relative_path} missing operator next step.")
        privacy = payload.get("privacy") or {}
        for key, value in privacy.items():
            if isinstance(value, bool) and value is not False:
                raise PublishedImageEvidenceError(f"{relative_path} privacy.{key} must be false.")
        assert_no_leaks(payload)
        results.append(
            {
                "fixture_id": fixture_id,
                "classification": classification,
                "release_gate": payload.get("release_gate"),
            }
        )
    if classifications != EXPECTED_CLASSIFICATIONS:
        raise PublishedImageEvidenceError(
            f"Published-image fixture classifications drifted: {sorted(classifications)}"
        )
    return sorted(results, key=lambda item: item["fixture_id"])


def validate_report(root: Path) -> dict[str, Any]:
    report = read_json(require_file(root, "platform/generated/study-anything-published-image-evidence.json"))
    if report.get("schema_version") != SCHEMA_VERSION:
        raise PublishedImageEvidenceError("Published-image evidence schema drifted.")
    if report.get("version") != RELEASE_VERSION:
        raise PublishedImageEvidenceError("Published-image evidence version drifted.")
    if report.get("status") != "pass":
        raise PublishedImageEvidenceError("Published-image evidence must pass.")
    identity = report.get("release_identity") or {}
    if identity.get("tag") != RELEASE_VERSION:
        raise PublishedImageEvidenceError("Published-image evidence release tag drifted.")
    manifest = report.get("manifest_evidence") or {}
    if set(str(item) for item in manifest.get("required_platforms", [])) != {"linux/amd64", "linux/arm64"}:
        raise PublishedImageEvidenceError("Published-image evidence required platform coverage drifted.")
    local_smoke = report.get("local_smoke_evidence") or {}
    if local_smoke.get("timeout_status") != "blocked_by_local_ghcr_pull":
        raise PublishedImageEvidenceError("Published-image evidence timeout classification drifted.")
    matrix = report.get("classification_matrix") or []
    matrix_classes = {str(item.get("classification")) for item in matrix if isinstance(item, dict)}
    if matrix_classes != EXPECTED_CLASSIFICATIONS:
        raise PublishedImageEvidenceError("Published-image evidence classification matrix drifted.")
    fixture_ids = {str(item.get("fixture_id")) for item in report.get("fixture_refs", [])}
    if fixture_ids != FIXTURES:
        raise PublishedImageEvidenceError("Published-image evidence fixture coverage drifted.")
    for ref in report.get("fixture_refs", []):
        validate_file_ref(root, ref)
    for ref in report.get("public_asset_refs", []):
        validate_file_ref(root, ref)
    privacy = report.get("privacy_assertions") or {}
    for key, value in privacy.items():
        if isinstance(value, bool) and value is not False:
            raise PublishedImageEvidenceError(f"Published-image evidence privacy.{key} must be false.")
    archive = report.get("archive") or {}
    if root.resolve() == ROOT.resolve():
        archive_path = require_file(root, "platform/generated/study-anything-published-image-evidence.zip")
        checksum_path = require_file(root, "platform/generated/study-anything-published-image-evidence.sha256")
        archive_hash = sha256_file(archive_path)
        if archive.get("sha256") != archive_hash:
            raise PublishedImageEvidenceError("Published-image evidence archive sha256 metadata drifted.")
        checksum_text = checksum_path.read_text(encoding="utf-8").strip()
        if archive_hash not in checksum_text:
            raise PublishedImageEvidenceError("Published-image evidence sha256 sidecar drifted.")
        with zipfile.ZipFile(archive_path) as evidence_archive:
            names = set(evidence_archive.namelist())
        required_archive_names = {
            f"{ARCHIVE_ROOT}/EVIDENCE_README.md",
            f"{ARCHIVE_ROOT}/manifest.json",
            f"{ARCHIVE_ROOT}/study-anything-published-image-evidence.md",
        }
        if not required_archive_names.issubset(names):
            raise PublishedImageEvidenceError("Published-image evidence zip is missing required handoff files.")
    assert_no_leaks(report)
    return {
        "schema_version": report.get("schema_version"),
        "version": report.get("version"),
        "fixture_count": len(report.get("fixture_refs", [])),
        "classification_count": len(matrix_classes),
    }


def validate_markdown(root: Path) -> dict[str, Any]:
    text = require_file(root, "platform/generated/study-anything-published-image-evidence.md").read_text(
        encoding="utf-8"
    )
    for needle in (SCHEMA_VERSION, RELEASE_VERSION, "Classification Matrix", "blocked_by_local_ghcr_pull"):
        if needle not in text:
            raise PublishedImageEvidenceError(f"Published-image evidence Markdown missing {needle}.")
    assert_text_has_no_leaks(text, "platform/generated/study-anything-published-image-evidence.md")
    return {"markdown_checked": True}


def validate_platform_packs(root: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for platform_id in PLATFORMS:
        pack = read_json(require_file(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
            if command not in commands:
                raise PublishedImageEvidenceError(f"{platform_id} pack missing {command}.")
        for item in (
            "published_image_evidence.schema_version == published-image-evidence-v1",
            "published_image_evidence_fixture.schema_version == published-image-evidence-fixture-v1",
        ):
            if item not in evidence:
                raise PublishedImageEvidenceError(f"{platform_id} pack missing {item}.")
        results[platform_id] = {"command_declared": True, "acceptance_evidence_declared": True}
    return results


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(require_file(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != ECOSYSTEM_SUBMISSION_SCHEMA_VERSION:
        raise PublishedImageEvidenceError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise PublishedImageEvidenceError("Ecosystem submission version drifted.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    missing = sorted(REQUIRED_REPORT_ASSETS - shared_assets)
    if missing:
        raise PublishedImageEvidenceError(f"Ecosystem submission missing published-image assets: {missing}")
    acceptance = submission.get("acceptance") or {}
    commands = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    must_prove = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for command in (REQUIRED_COMMAND, REQUIRED_GENERATOR_COMMAND):
        if command not in commands:
            raise PublishedImageEvidenceError(f"Ecosystem submission missing {command}.")
    for schema in (SCHEMA_VERSION, FIXTURE_SCHEMA_VERSION):
        if schema not in must_prove:
            raise PublishedImageEvidenceError(f"Ecosystem submission must prove {schema}.")
    return {"schema_version": submission.get("schema_version"), "version": submission.get("version")}


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != ADOPTION_PACK_SCHEMA_VERSION:
        raise PublishedImageEvidenceError("Adoption pack schema drifted.")
    if manifest.get("version") != RELEASE_VERSION:
        raise PublishedImageEvidenceError("Adoption pack version drifted.")
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    missing = sorted(REQUIRED_REPORT_ASSETS - paths)
    if missing:
        raise PublishedImageEvidenceError(f"Adoption pack missing published-image evidence assets: {missing}")
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    for schema in (SCHEMA_VERSION, FIXTURE_SCHEMA_VERSION):
        if schema not in must_verify:
            raise PublishedImageEvidenceError(f"Adoption pack must verify {schema}.")
    return {"schema_version": manifest.get("schema_version"), "version": manifest.get("version")}


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/published-image-evidence.md": [
            SCHEMA_VERSION,
            FIXTURE_SCHEMA_VERSION,
            REQUIRED_COMMAND,
            "blocked_by_local_ghcr_pull",
        ],
        "docs/adoption.md": [SCHEMA_VERSION, "verify_published_image_evidence.py"],
        "docs/self-hosting.md": [SCHEMA_VERSION, "published-image evidence"],
        "docs/platform-agent-integrations.md": [SCHEMA_VERSION, "published-image evidence"],
        "docs/ecosystem-submission.md": [SCHEMA_VERSION, "Published Image Evidence"],
        "docs/release-checklist.md": ["verify_published_image_evidence.py --check"],
        "docs/roadmap.md": ["v0.3.28-alpha", SCHEMA_VERSION],
    }
    for relative_path, needles in checked.items():
        text = require_file(root, relative_path).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise PublishedImageEvidenceError(f"{relative_path} missing required text: {missing}")
        if relative_path == "docs/published-image-evidence.md":
            assert_text_has_no_leaks(text, relative_path)
    return {"checked_docs": sorted(checked)}


def build_report(root: Path) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": "Verify public published-image deployment evidence and fallback classification.",
        "published_image_evidence": validate_report(root),
        "published_image_markdown": validate_markdown(root),
        "published_image_fixtures": validate_fixtures(root),
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
            "support_bundle_private_payload_in_report": False,
            "local_absolute_paths_in_report": False,
            "automatic_upload": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_published_image_evidence.py --check",
            "generate_command": "python3 scripts/generate_published_image_evidence.py --check",
            "pack_command": REQUIRED_PACK_COMMAND,
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise PublishedImageEvidenceError(f"Published-image evidence report missing: {path}")
    generated = read_json(path)
    if generated.get("schema_version") != SCHEMA_VERSION:
        raise PublishedImageEvidenceError("Generated published-image evidence schema drifted.")
    if generated.get("version") != RELEASE_VERSION:
        raise PublishedImageEvidenceError("Generated published-image evidence version drifted.")
    if payload.get("status") != "pass":
        raise PublishedImageEvidenceError("Published-image evidence validation did not pass.")
    print("ok    published-image evidence assets are valid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--check", action="store_true", help="Require generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-published-image-evidence-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_published_image_evidence.py")
            require_file(root, "platform/generated/study-anything-published-image-evidence.json")
        report = build_report(root)

    if args.check:
        check_report(Path(args.output), report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_published_image_evidence failed: {exc}", file=sys.stderr)
        sys.exit(1)
