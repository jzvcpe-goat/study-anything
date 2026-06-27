#!/usr/bin/env python3
"""Generate public release-asset bootstrap evidence assets."""

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

from localhost_diagnostics import redact_diagnostic


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
REPORT_PATH = OUTPUT_DIR / "study-anything-release-asset-bootstrap.json"
MARKDOWN_PATH = OUTPUT_DIR / "study-anything-release-asset-bootstrap.md"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-release-asset-bootstrap.zip"
CHECKSUM_PATH = OUTPUT_DIR / "study-anything-release-asset-bootstrap.sha256"
ARCHIVE_ROOT = "study-anything-release-asset-bootstrap"

SCHEMA_VERSION = "release-asset-bootstrap-v1"
TRANSCRIPT_SCHEMA_VERSION = "release-asset-bootstrap-transcript-v1"
RELEASE_VERSION = "v0.3.29-alpha"
RELEASE_REPO = "jzvcpe-goat/study-anything"
RELEASE_URL = f"https://github.com/{RELEASE_REPO}/releases/tag/{RELEASE_VERSION}"
ADOPTION_PACK_SCHEMA_VERSION = "study-anything-platform-adoption-pack-v1"
PROOF_SCHEMA_VERSION = "release-asset-adoption-proof-v1"

PUBLIC_ASSET_PATHS = (
    "docs/release-asset-bootstrap.md",
    "docs/release-cleanroom-bootstrap.md",
    "docs/release-asset-adoption.md",
    "docs/platform-agent-release-replay.md",
    "docs/support-desk.md",
    "docs/adoption.md",
    "docs/github-launch.md",
    "docs/ecosystem-submission.md",
    "platform/bootstrap/study_anything_release_bootstrap.py",
    "scripts/generate_release_cleanroom_bootstrap.py",
    "scripts/bootstrap_from_release.py",
    "scripts/verify_release_asset_adoption.py",
    "scripts/replay_platform_agent_from_release.py",
    "scripts/replay_support_bundle.py",
    "scripts/generate_platform_support_bundle_replay.py",
    "scripts/verify_platform_support_bundle_replay.py",
    "scripts/generate_release_asset_bootstrap.py",
    "platform/generated/study-anything-platform-support-bundle-replay.json",
    "platform/generated/study-anything-release-asset-adoption.json",
    "platform/generated/study-anything-release-cleanroom-bootstrap.json",
    "platform/generated/study-anything-release-cleanroom-bootstrap.md",
    "platform/generated/study-anything-release-cleanroom-bootstrap.zip",
    "platform/generated/study-anything-release-cleanroom-bootstrap.sha256",
    "platform/generated/study-anything-platform-agent-replay.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
)

CLASSIFICATIONS = (
    "release_asset_bootstrap_ready",
    "release_asset_missing",
    "release_asset_digest_mismatch",
    "release_asset_pack_corrupted",
    "release_asset_published_evidence_missing",
    "release_asset_network_unavailable",
    "tool_manifest_invalid",
    "local_api_unavailable",
    "published_image_unavailable",
    "non_ascii_path_risk",
    "bootstrap_failed",
)

FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private " + "answer:",
    "Private " + "source text:",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
]


class ReleaseAssetBootstrapError(RuntimeError):
    """Readable release-asset bootstrap generation failure."""


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"generate_release_asset_bootstrap failed: {diagnostic}",
            "",
            "Next steps:",
            "1. Rebuild the public release-asset bootstrap evidence: python3 scripts/generate_release_asset_bootstrap.py",
            "2. Re-check the generated assets: python3 scripts/generate_release_asset_bootstrap.py --check",
            "3. Re-run release asset adoption verification: python3 scripts/verify_release_asset_adoption.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only",
            "4. If this is an adopter report, replay the redacted support bundle: python3 scripts/replay_support_bundle.py --bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json",
        ]
    )


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
        raise ReleaseAssetBootstrapError(f"Release asset bootstrap evidence leaked private data: {leaks}")


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise ReleaseAssetBootstrapError(f"Release asset bootstrap file is missing: {relative_path}")
    return path


def public_file_ref(relative_path: str) -> dict[str, Any]:
    path = require_file(relative_path)
    return {
        "path": relative_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def recovery_matrix() -> list[dict[str, Any]]:
    return [
        {
            "classification": "release_asset_missing",
            "release_gate": "block_release_claim",
            "operator_next_step": "Attach all required public release zip assets before announcing external adoption.",
        },
        {
            "classification": "release_asset_digest_mismatch",
            "release_gate": "block_release_claim",
            "operator_next_step": "Delete local downloads and recreate the release asset from the matching main commit.",
        },
        {
            "classification": "release_asset_pack_corrupted",
            "release_gate": "block_release_claim",
            "operator_next_step": "Re-download or regenerate the platform adoption pack.",
        },
        {
            "classification": "release_asset_published_evidence_missing",
            "release_gate": "block_release_claim",
            "operator_next_step": "Regenerate published-image evidence before packaging the adoption pack.",
        },
        {
            "classification": "release_asset_network_unavailable",
            "release_gate": "needs_independent_recheck",
            "operator_next_step": "Retry from another network or use a safely mirrored asset directory.",
        },
        {
            "classification": "tool_manifest_invalid",
            "release_gate": "block_platform_submission",
            "operator_next_step": "Regenerate platform tool assets and adoption pack before importing into Kimi/Codex/WorkBuddy.",
        },
        {
            "classification": "local_api_unavailable",
            "release_gate": "runtime_recheck_required",
            "operator_next_step": "Launch Skill Mode or Docker self-host from a normal terminal that permits localhost sockets before running live platform tools.",
        },
        {
            "classification": "published_image_unavailable",
            "release_gate": "runtime_recheck_required",
            "operator_next_step": "Check GHCR manifest and docker-images workflow before claiming published-image readiness.",
        },
        {
            "classification": "non_ascii_path_risk",
            "release_gate": "operator_environment_warning",
            "operator_next_step": "Use Skill Mode or published images, or move source builds into an ASCII-only path.",
        },
        {
            "classification": "bootstrap_failed",
            "release_gate": "needs_triage",
            "operator_next_step": "Run the lower-level release asset verifier and attach the redacted transcript to GitHub.",
        },
    ]


def build_report(include_archive_metadata: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Make the GitHub Release page a complete external adoption entrypoint: "
            "download assets, verify digests, inspect platform import manifests, and "
            "emit a redacted bootstrap transcript for Kimi, Codex, WorkBuddy, or generic HTTP tool hosts."
        ),
        "release_identity": {
            "tag": RELEASE_VERSION,
            "release_url": RELEASE_URL,
            "repo": RELEASE_REPO,
        },
        "schemas": {
            "bootstrap": SCHEMA_VERSION,
            "transcript": TRANSCRIPT_SCHEMA_VERSION,
            "release_asset_proof": PROOF_SCHEMA_VERSION,
            "adoption_pack": ADOPTION_PACK_SCHEMA_VERSION,
        },
        "commands": {
            "metadata_only": f"python3 scripts/bootstrap_from_release.py --tag {RELEASE_VERSION} --runtime metadata-only",
            "skill_mode": f"python3 scripts/bootstrap_from_release.py --tag {RELEASE_VERSION} --runtime skill-mode",
            "published_image": f"python3 scripts/bootstrap_from_release.py --tag {RELEASE_VERSION} --runtime published-image",
            "offline_fixture": (
                "python3 scripts/bootstrap_from_release.py "
                "--fixture fixtures/release-asset-adoption/asset-only-pass.json "
                "--asset-dir platform/generated --runtime metadata-only"
            ),
        },
        "platform_imports": {
            "kimi": "OpenAI-compatible tools plus local HTTP API endpoint.",
            "codex": "Skill entrypoint plus CLI/demo commands.",
            "workbuddy": "OpenAPI import plus tool catalog.",
        },
        "classification_matrix": [
            {"classification": "release_asset_bootstrap_ready", "release_gate": "pass", "meaning": "Release assets, pack digests, platform imports, and selected runtime replay are usable."},
            *[
                {
                    "classification": item["classification"],
                    "release_gate": item["release_gate"],
                    "meaning": item["operator_next_step"],
                }
                for item in recovery_matrix()
            ],
        ],
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
            "minimum_command": "python3 scripts/bootstrap_from_release.py --runtime metadata-only",
            "fixture_command": "python3 scripts/bootstrap_from_release.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only",
            "generate_command": "python3 scripts/generate_release_asset_bootstrap.py --check",
            "release_gate": "scripts/release_check.sh",
        },
    }
    if include_archive_metadata:
        if archive is None:
            raise ReleaseAssetBootstrapError("archive bytes are required for archive metadata")
        report["archive"] = {
            "path": "platform/generated/study-anything-release-asset-bootstrap.zip",
            "sha256_path": "platform/generated/study-anything-release-asset-bootstrap.sha256",
            "bytes": len(archive),
            "sha256": sha256_bytes(archive),
            "archive_root": ARCHIVE_ROOT,
        }
    assert_no_leaks(report)
    return report


def markdown_report(report: dict[str, Any]) -> str:
    commands = "\n".join(f"- `{command}`" for command in report["commands"].values())
    matrix = "\n".join(
        f"- `{item['classification']}` -> `{item['release_gate']}`: {item['meaning']}"
        for item in report["classification_matrix"]
    )
    archive = report.get("archive") or {}
    archive_line = (
        f"- Archive: `{archive.get('path')}` sha256 `{archive.get('sha256')}`"
        if archive
        else "- Archive: generated during packaging"
    )
    return f"""# Study Anything Release Asset Bootstrap

Schema: `{report['schema_version']}`
Version: `{report['version']}`
Status: `{report['status']}`

This evidence makes the GitHub Release page the first adoption surface for
external platform Agents. It verifies public assets, import manifests, and
runtime choices without requiring a development checkout as the starting point.

## Archive

{archive_line}

## Commands

{commands}

## Classification Matrix

{matrix}

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
"""


def archive_readme() -> str:
    return f"""# Study Anything Release Asset Bootstrap

Version: {RELEASE_VERSION}
Schema: {SCHEMA_VERSION}

Run `python3 scripts/bootstrap_from_release.py --tag {RELEASE_VERSION} --runtime metadata-only`
to verify public release assets and platform import readiness.
"""


def archive_bytes(base_report: dict[str, Any], markdown: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        records: list[tuple[str, bytes]] = [
            (f"{ARCHIVE_ROOT}/BOOTSTRAP_README.md", archive_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(base_report).encode("utf-8")),
            (f"{ARCHIVE_ROOT}/study-anything-release-asset-bootstrap.md", markdown.encode("utf-8")),
        ]
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
    report_text, markdown, archive, checksum = build_outputs()
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    CHECKSUM_PATH.write_text(checksum, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"wrote {MARKDOWN_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")
    print(f"wrote {CHECKSUM_PATH.relative_to(ROOT)}")


def check_outputs() -> None:
    report_text, markdown, archive, checksum = build_outputs()
    expected = {
        REPORT_PATH: report_text,
        MARKDOWN_PATH: markdown,
        ARCHIVE_PATH: archive,
        CHECKSUM_PATH: checksum,
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
        raise ReleaseAssetBootstrapError(
            "Release asset bootstrap evidence assets are stale. Run "
            "`python3 scripts/generate_release_asset_bootstrap.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated release-asset bootstrap evidence assets are up to date")


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
        print(format_cli_failure(exc), file=sys.stderr)
        sys.exit(1)
