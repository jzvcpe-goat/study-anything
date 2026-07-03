#!/usr/bin/env python3
"""Generate public release-asset adoption replay evidence assets."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
REPORT_PATH = OUTPUT_DIR / "study-anything-release-asset-adoption.json"
MARKDOWN_PATH = OUTPUT_DIR / "study-anything-release-asset-adoption.md"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-release-asset-adoption.zip"
CHECKSUM_PATH = OUTPUT_DIR / "study-anything-release-asset-adoption.sha256"
FIXTURE_DIR = ROOT / "fixtures" / "release-asset-adoption"
ARCHIVE_ROOT = "study-anything-release-asset-adoption"

SCHEMA_VERSION = "release-asset-adoption-v1"
FIXTURE_SCHEMA_VERSION = "release-asset-adoption-fixture-v1"
RELEASE_VERSION = "v0.3.31-alpha"
RELEASE_REPO = "jzvcpe-goat/study-anything"
RELEASE_URL = f"https://github.com/{RELEASE_REPO}/releases/tag/{RELEASE_VERSION}"
VERIFIER_SCHEMA_VERSION = "release-asset-adoption-proof-v1"
ADOPTION_PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
PUBLISHED_IMAGE_SCHEMA_VERSION = "published-image-evidence-v1"

FIXTURES = (
    "asset-only-pass",
    "asset-missing",
    "digest-mismatch",
    "pack-corrupted",
    "published-evidence-missing",
    "network-unavailable",
)
CLASSIFICATIONS = {
    "release_asset_adoption_ready",
    "release_asset_missing",
    "release_asset_digest_mismatch",
    "release_asset_pack_corrupted",
    "release_asset_published_evidence_missing",
    "release_asset_network_unavailable",
}
REQUIRED_RELEASE_ASSETS = (
    "study-anything-platform-adoption-pack.zip",
    "study-anything-published-image-evidence.zip",
    "study-anything-adopter-evidence-archive.zip",
    "study-anything-platform-feedback-package.zip",
    "study-anything-release-asset-bootstrap.zip",
    "study-anything-platform-agent-replay.zip",
    "study-anything-codex-plugin-pack.json",
    "study-anything-codex-plugin-pack.zip",
    "study-anything-codex-plugin-pack.sha256",
    "study-anything-kimi-plugin-pack.json",
    "study-anything-kimi-plugin-pack.zip",
    "study-anything-kimi-plugin-pack.sha256",
    "study-anything-workbuddy-plugin-pack.json",
    "study-anything-workbuddy-plugin-pack.zip",
    "study-anything-workbuddy-plugin-pack.sha256",
    "study-anything-hermes-plugin-pack.json",
    "study-anything-hermes-plugin-pack.zip",
    "study-anything-hermes-plugin-pack.sha256",
    "study-anything-dual-loop-trust-scenario-pack.json",
    "study-anything-dual-loop-trust-scenario-pack.zip",
    "study-anything-dual-loop-trust-scenario-pack.sha256",
)
PUBLIC_ASSET_PATHS = (
    "README.md",
    "docs/adoption.md",
    "docs/github-launch.md",
    "docs/ecosystem-submission.md",
    "docs/release-asset-adoption.md",
    "docs/dual-loop-trust-scenario-pack.md",
    "docs/platform-plugin-downloads.md",
    "docs/platform-agent-release-replay.md",
    "docs/release-checklist.md",
    "docs/roadmap.md",
    "platform/ecosystem-submission.json",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-platform-plugin-downloads.json",
    "platform/generated/study-anything-platform-plugin-downloads.md",
    "scripts/verify_release_asset_adoption.py",
    "scripts/generate_platform_plugin_downloads.py",
    "scripts/verify_platform_plugin_downloads.py",
    "scripts/replay_platform_agent_from_release.py",
    "scripts/generate_platform_agent_replay.py",
    "scripts/generate_release_asset_adoption.py",
    "scripts/generate_dual_loop_trust_scenario_pack.py",
    "scripts/verify_dual_loop_trust_scenario_pack.py",
    "scripts/verify_external_adoption.py",
    "scripts/verify_published_image_evidence.py",
    "scripts/verify_published_image_launch.py",
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


class ReleaseAssetAdoptionError(RuntimeError):
    """Readable release-asset adoption generation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise ReleaseAssetAdoptionError(f"Release asset adoption evidence leaked private data: {leaks}")


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise ReleaseAssetAdoptionError(f"Release asset evidence file is missing: {relative_path}")
    return path


def public_file_ref(relative_path: str) -> dict[str, Any]:
    path = require_file(relative_path)
    return {
        "path": relative_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def fixture_payload(fixture_id: str) -> dict[str, Any]:
    mapping: dict[str, tuple[str, str, str]] = {
        "asset-only-pass": (
            "release_asset_adoption_ready",
            "pass",
            "All required release zip assets exist, digests match, and pack/evidence verification passes.",
        ),
        "asset-missing": (
            "release_asset_missing",
            "block_release_claim",
            "The GitHub release is missing a required zip asset.",
        ),
        "digest-mismatch": (
            "release_asset_digest_mismatch",
            "block_release_claim",
            "A downloaded release asset does not match the GitHub sha256 digest.",
        ),
        "pack-corrupted": (
            "release_asset_pack_corrupted",
            "block_release_claim",
            "The adoption pack zip cannot be opened or its manifest hashes do not match.",
        ),
        "published-evidence-missing": (
            "release_asset_published_evidence_missing",
            "block_release_claim",
            "The adoption pack does not include published-image evidence.",
        ),
        "network-unavailable": (
            "release_asset_network_unavailable",
            "needs_independent_recheck",
            "GitHub release metadata or asset download was unavailable from the operator network.",
        ),
    }
    classification, release_gate, note = mapping[fixture_id]
    assets: list[dict[str, Any]] = []
    if fixture_id == "asset-only-pass":
        for name in REQUIRED_RELEASE_ASSETS:
            assets.append(
                {
                    "name": name,
                    "browser_download_url": f"https://github.com/{RELEASE_REPO}/releases/download/{RELEASE_VERSION}/{name}",
                }
            )
    elif fixture_id == "digest-mismatch":
        for name in REQUIRED_RELEASE_ASSETS:
            asset = {
                "name": name,
                "browser_download_url": f"https://github.com/{RELEASE_REPO}/releases/download/{RELEASE_VERSION}/{name}",
            }
            if name == REQUIRED_RELEASE_ASSETS[0]:
                asset["digest"] = f"sha256:{'0' * 64}"
            assets.append(asset)
    elif fixture_id not in {"asset-missing", "network-unavailable"}:
        for name in REQUIRED_RELEASE_ASSETS:
            assets.append(
                {
                    "name": name,
                    "browser_download_url": f"https://github.com/{RELEASE_REPO}/releases/download/{RELEASE_VERSION}/{name}",
                }
            )
    payload = {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "fixture_id": fixture_id,
        "classification": classification,
        "release_gate": release_gate,
        "release": {
            "tag_name": RELEASE_VERSION,
            "html_url": RELEASE_URL,
            "assets": assets,
        },
        "operator_next_step": note,
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "support_bundle_private_payload_included": False,
            "local_absolute_paths_included": False,
            "automatic_upload": False,
        },
    }
    assert_no_leaks(payload)
    return payload


def fixture_refs() -> list[dict[str, Any]]:
    return [
        {"fixture_id": fixture_id, **public_file_ref(f"fixtures/release-asset-adoption/{fixture_id}.json")}
        for fixture_id in FIXTURES
    ]


def build_report(include_archive_metadata: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Prove that GitHub Release zip attachments are enough for external platform "
            "operators to validate and replay Study Anything adoption without treating a "
            "local development checkout as the entrypoint."
        ),
        "release_identity": {
            "tag": RELEASE_VERSION,
            "release_url": RELEASE_URL,
            "required_asset_names": list(REQUIRED_RELEASE_ASSETS),
        },
        "verification": {
            "metadata_only_command": (
                f"python3 scripts/verify_release_asset_adoption.py --tag {RELEASE_VERSION} "
                "--runtime metadata-only"
            ),
            "published_image_command": (
                f"python3 scripts/verify_release_asset_adoption.py --tag {RELEASE_VERSION} "
                "--runtime published-image --skip-pull"
            ),
            "skill_mode_command": (
                f"python3 scripts/verify_release_asset_adoption.py --tag {RELEASE_VERSION} "
                "--runtime skill-mode"
            ),
            "proof_schema": VERIFIER_SCHEMA_VERSION,
        },
        "classification_matrix": [
            {
                "classification": "release_asset_adoption_ready",
                "release_gate": "pass",
                "meaning": "Required assets are present, digests match, and pack/evidence validation passes.",
            },
            {
                "classification": "release_asset_missing",
                "release_gate": "block_release_claim",
                "meaning": "A required release zip asset is missing.",
            },
            {
                "classification": "release_asset_digest_mismatch",
                "release_gate": "block_release_claim",
                "meaning": "An asset digest does not match GitHub release metadata.",
            },
            {
                "classification": "release_asset_pack_corrupted",
                "release_gate": "block_release_claim",
                "meaning": "The adoption pack cannot be opened or its manifest hashes drifted.",
            },
            {
                "classification": "release_asset_published_evidence_missing",
                "release_gate": "block_release_claim",
                "meaning": "Published-image evidence is absent from the adoption pack.",
            },
            {
                "classification": "release_asset_network_unavailable",
                "release_gate": "needs_independent_recheck",
                "meaning": "GitHub release metadata or asset download is unreachable from the operator network.",
            },
        ],
        "schema_requirements": {
            "adoption_pack": ADOPTION_PACK_SCHEMA_VERSION,
            "published_image_evidence": PUBLISHED_IMAGE_SCHEMA_VERSION,
        },
        "fixture_refs": fixture_refs(),
        "public_asset_refs": [public_file_ref(path) for path in PUBLIC_ASSET_PATHS],
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
            "minimum_command": "python3 scripts/verify_release_asset_adoption.py --runtime metadata-only",
            "generate_command": "python3 scripts/generate_release_asset_adoption.py --check",
            "release_gate": "scripts/release_check.sh",
        },
    }
    if include_archive_metadata:
        if archive is None:
            raise ReleaseAssetAdoptionError("archive bytes are required for archive metadata")
        report["archive"] = {
            "path": "platform/generated/study-anything-release-asset-adoption.zip",
            "sha256_path": "platform/generated/study-anything-release-asset-adoption.sha256",
            "bytes": len(archive),
            "sha256": sha256_bytes(archive),
            "archive_root": ARCHIVE_ROOT,
        }
    assert_no_leaks(report)
    return report


def markdown_report(report: dict[str, Any]) -> str:
    matrix = "\n".join(
        f"- `{item['classification']}` -> `{item['release_gate']}`: {item['meaning']}"
        for item in report["classification_matrix"]
    )
    fixtures = "\n".join(
        f"- `{item['fixture_id']}`: `{item['sha256']}`" for item in report["fixture_refs"]
    )
    commands = "\n".join(f"- `{command}`" for command in report["verification"].values() if isinstance(command, str))
    archive = report.get("archive") or {}
    archive_line = (
        f"- Archive: `{archive.get('path')}` sha256 `{archive.get('sha256')}`"
        if archive
        else "- Archive: generated during packaging"
    )
    return f"""# Study Anything Release Asset Adoption

Schema: `{report['schema_version']}`
Version: `{report['version']}`
Status: `{report['status']}`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

{archive_line}

## Commands

{commands}

## Classification Matrix

{matrix}

## Fixture Hashes

{fixtures}

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
"""


def archive_readme() -> str:
    return f"""# Study Anything Release Asset Adoption

Version: {RELEASE_VERSION}
Schema: {SCHEMA_VERSION}

Run `python3 scripts/verify_release_asset_adoption.py --tag {RELEASE_VERSION} --runtime metadata-only`
to verify GitHub Release assets without launching the app.
"""


def archive_bytes(base_report: dict[str, Any], markdown: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        records: list[tuple[str, bytes]] = [
            (f"{ARCHIVE_ROOT}/EVIDENCE_README.md", archive_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(base_report).encode("utf-8")),
            (f"{ARCHIVE_ROOT}/study-anything-release-asset-adoption.md", markdown.encode("utf-8")),
        ]
        for fixture_id in FIXTURES:
            records.append(
                (
                    f"{ARCHIVE_ROOT}/fixtures/release-asset-adoption/{fixture_id}.json",
                    dump_json(fixture_payload(fixture_id)).encode("utf-8"),
                )
            )
        for relative_path in PUBLIC_ASSET_PATHS:
            records.append((f"{ARCHIVE_ROOT}/{relative_path}", require_file(relative_path).read_bytes()))
        for name, content in sorted(records, key=lambda item: item[0]):
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return buffer.getvalue()


def build_outputs() -> tuple[str, str, bytes, str]:
    base_report = build_report()
    base_markdown = markdown_report(base_report)
    archive = archive_bytes(base_report, base_markdown)
    report = build_report(include_archive_metadata=True, archive=archive)
    markdown = markdown_report(report)
    checksum = f"{sha256_bytes(archive)}  {ARCHIVE_PATH.name}\n"
    return dump_json(report), markdown, archive, checksum


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fixture_id in FIXTURES:
        (FIXTURE_DIR / f"{fixture_id}.json").write_text(
            dump_json(fixture_payload(fixture_id)),
            encoding="utf-8",
        )
    report_text, markdown, archive, checksum = build_outputs()
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    CHECKSUM_PATH.write_text(checksum, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"wrote {MARKDOWN_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")
    print(f"wrote {CHECKSUM_PATH.relative_to(ROOT)}")
    print(f"wrote {FIXTURE_DIR.relative_to(ROOT)}/*.json")


def check_outputs() -> None:
    expected_fixtures = {
        FIXTURE_DIR / f"{fixture_id}.json": dump_json(fixture_payload(fixture_id))
        for fixture_id in FIXTURES
    }
    report_text, markdown, archive, checksum = build_outputs()
    expected = {
        REPORT_PATH: report_text,
        MARKDOWN_PATH: markdown,
        ARCHIVE_PATH: archive,
        CHECKSUM_PATH: checksum,
        **expected_fixtures,
    }
    missing: list[str] = []
    stale: list[str] = []
    for path, content in expected.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        if isinstance(content, bytes):
            if path.read_bytes() != content:
                stale.append(str(path.relative_to(ROOT)))
        elif path.read_text(encoding="utf-8") != content:
            stale.append(str(path.relative_to(ROOT)))
    if missing or stale:
        raise ReleaseAssetAdoptionError(
            "Release asset adoption evidence assets are stale. Run "
            "`python3 scripts/generate_release_asset_adoption.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated release-asset adoption evidence assets are up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_release_asset_adoption failed: {exc}", file=sys.stderr)
        sys.exit(1)
