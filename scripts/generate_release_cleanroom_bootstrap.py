#!/usr/bin/env python3
"""Generate release-only cleanroom bootstrap evidence assets."""

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
REPORT_PATH = OUTPUT_DIR / "study-anything-release-cleanroom-bootstrap.json"
MARKDOWN_PATH = OUTPUT_DIR / "study-anything-release-cleanroom-bootstrap.md"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-release-cleanroom-bootstrap.zip"
CHECKSUM_PATH = OUTPUT_DIR / "study-anything-release-cleanroom-bootstrap.sha256"
ARCHIVE_ROOT = "study-anything-release-cleanroom-bootstrap"

SCHEMA_VERSION = "release-cleanroom-bootstrap-evidence-v1"
BOOTLOADER_SCHEMA_VERSION = "release-cleanroom-bootstrap-v1"
RELEASE_VERSION = "v0.3.27-alpha"
RELEASE_REPO = "jzvcpe-goat/study-anything"
RELEASE_URL = f"https://github.com/{RELEASE_REPO}/releases/tag/{RELEASE_VERSION}"

PUBLIC_ASSET_PATHS = (
    "platform/bootstrap/study_anything_release_bootstrap.py",
    "docs/release-cleanroom-bootstrap.md",
    "docs/release-asset-bootstrap.md",
    "docs/release-asset-adoption.md",
    "docs/platform-agent-release-replay.md",
    "docs/adoption.md",
    "docs/self-hosting.md",
    "docs/platform-agent-integrations.md",
    "scripts/bootstrap_from_release.py",
    "scripts/replay_platform_agent_from_release.py",
)

CLASSIFICATION_MATRIX = [
    ("cleanroom_bootstrap_ready", "pass", "Release assets, platform imports, and selected runtime path are usable from a clean directory."),
    ("release_asset_missing", "block_release_claim", "One or more required public zip assets are absent from the GitHub Release."),
    ("release_asset_digest_mismatch", "block_release_claim", "A downloaded asset does not match GitHub sha256 metadata."),
    ("release_asset_pack_corrupted", "block_release_claim", "The platform adoption pack cannot be unpacked safely."),
    ("tool_import_invalid", "block_platform_submission", "OpenAI tools or OpenAPI operation IDs are malformed or incomplete."),
    ("platform_entrypoint_missing", "block_platform_submission", "The selected Kimi, Codex, WorkBuddy, or generic entrypoint is missing."),
    ("source_download_failed", "needs_network_or_source_dir", "Runtime replay needs source code but the GitHub tag source archive could not be downloaded."),
    ("runtime_launch_failed", "needs_runtime_triage", "The selected Skill Mode, external API, or published-image runtime could not be launched."),
    ("api_unavailable", "needs_runtime_triage", "The Study Anything API was not reachable for tool replay."),
    ("schema_mismatch", "block_release_claim", "A runtime response did not match the expected learning/eval schema."),
    ("privacy_leak", "block_release_claim", "A report included source text, answers, local paths, prompts, endpoints, or keys."),
    ("network_unavailable", "needs_independent_recheck", "GitHub release metadata or assets could not be fetched."),
    ("cleanroom_bootstrap_failed", "needs_triage", "The bootloader failed outside a more specific classification."),
]

FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "Private platform replay source text",
    "Private platform replay learner answer",
    "AGENT_ENDPOINT=http",
]


class CleanroomBootstrapGenerationError(RuntimeError):
    """Readable cleanroom bootstrap generation failure."""


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


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise CleanroomBootstrapGenerationError(f"Cleanroom bootstrap file is missing: {relative_path}")
    return path


def public_file_ref(relative_path: str) -> dict[str, Any]:
    path = require_file(relative_path)
    return {
        "path": relative_path,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise CleanroomBootstrapGenerationError(f"Cleanroom bootstrap evidence leaked private data: {leaks}")


def example_success_report() -> dict[str, Any]:
    return {
        "schema_version": BOOTLOADER_SCHEMA_VERSION,
        "status": "ok",
        "classification": "cleanroom_bootstrap_ready",
        "tag": RELEASE_VERSION,
        "repo": RELEASE_REPO,
        "platform": "kimi",
        "runtime": {
            "requested": "metadata-only",
            "mode": "metadata-only",
            "status": "skipped",
        },
        "release_assets": {
            "asset_count": 6,
            "github_digest_verified_count": 6,
        },
        "adoption_pack": {
            "schema_version": "study-anything-platform-adoption-pack-v1",
            "version": RELEASE_VERSION,
            "tool_count": 30,
            "no_frontend_required": True,
            "real_model_keys_stored_by_study_anything": False,
        },
        "diagnostic": "Cleanroom bootloader completed.",
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


def build_report(include_archive_metadata: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Make the GitHub Release page a repo-free entrypoint: external operators "
            "can download public assets, verify digests, import platform tools, run a "
            "metadata or runtime drill, and produce a redacted issue-ready report."
        ),
        "release_identity": {
            "tag": RELEASE_VERSION,
            "release_url": RELEASE_URL,
            "repo": RELEASE_REPO,
        },
        "commands": {
            "metadata_only": (
                "python3 study_anything_release_bootstrap.py "
                f"--tag {RELEASE_VERSION} --platform kimi --runtime metadata-only"
            ),
            "skill_mode": (
                "python3 study_anything_release_bootstrap.py "
                f"--tag {RELEASE_VERSION} --platform kimi --runtime skill-mode"
            ),
            "published_image": (
                "python3 study_anything_release_bootstrap.py "
                f"--tag {RELEASE_VERSION} --platform generic-openapi --runtime published-image"
            ),
            "fixture_metadata_only": (
                "python3 platform/bootstrap/study_anything_release_bootstrap.py "
                "--fixture fixtures/release-asset-adoption/asset-only-pass.json "
                "--asset-dir platform/generated --runtime metadata-only"
            ),
        },
        "required_release_assets": sorted(
            [
                "study-anything-adopter-evidence-archive.zip",
                "study-anything-platform-adoption-pack.zip",
                "study-anything-platform-agent-replay.zip",
                "study-anything-platform-feedback-package.zip",
                "study-anything-published-image-evidence.zip",
                "study-anything-release-asset-bootstrap.zip",
            ]
        ),
        "platforms": ["kimi", "codex", "workbuddy", "generic-openapi"],
        "runtime_modes": ["metadata-only", "skill-mode", "published-image", "external-api"],
        "classification_matrix": [
            {"classification": item[0], "release_gate": item[1], "meaning": item[2]}
            for item in CLASSIFICATION_MATRIX
        ],
        "example_report": example_success_report(),
        "privacy_assertions": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "support_bundle_private_payload_included": False,
            "local_absolute_paths_included": False,
            "automatic_upload": False,
        },
        "public_assets": [public_file_ref(path) for path in PUBLIC_ASSET_PATHS],
    }
    if include_archive_metadata:
        if archive is None:
            raise CleanroomBootstrapGenerationError("archive bytes are required for archive metadata")
        report["archive"] = {
            "path": "platform/generated/study-anything-release-cleanroom-bootstrap.zip",
            "sha256_path": "platform/generated/study-anything-release-cleanroom-bootstrap.sha256",
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
    return f"""# Study Anything Release Cleanroom Bootstrap

Version: `{report['version']}`

`{report['schema_version']}` proves that Study Anything can be bootstrapped
from GitHub Release assets without assuming an existing repository checkout.

## Commands

{commands}

## Classification Matrix

{matrix}

## Privacy

- Raw source text included: `false`
- Learner answers included: `false`
- Real model keys included: `false`
- Agent endpoint secrets included: `false`
- Local absolute paths included: `false`

## Archive

{archive_line}
"""


def archive_readme() -> str:
    return f"""# Study Anything Release Cleanroom Bootstrap

This archive contains the standalone release bootloader and a public evidence
report for `{RELEASE_VERSION}`.

Start with:

```bash
python3 platform/bootstrap/study_anything_release_bootstrap.py --tag {RELEASE_VERSION} --runtime metadata-only
```

The bootloader does not store real model keys. Runtime mode delegates real model
work to the user's own platform Agent or to the deterministic demo Agent.
"""


def build_archive(base_report: dict[str, Any], markdown: str) -> bytes:
    records: list[tuple[str, bytes]] = [
        (f"{ARCHIVE_ROOT}/README.md", archive_readme().encode("utf-8")),
        (f"{ARCHIVE_ROOT}/manifest.json", dump_json(base_report).encode("utf-8")),
        (f"{ARCHIVE_ROOT}/study-anything-release-cleanroom-bootstrap.md", markdown.encode("utf-8")),
    ]
    for relative_path in PUBLIC_ASSET_PATHS:
        records.append((f"{ARCHIVE_ROOT}/{relative_path}", require_file(relative_path).read_bytes()))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in records:
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return buffer.getvalue()


def generate() -> dict[Path, bytes]:
    base_report = build_report()
    base_markdown = markdown_report(base_report)
    archive = build_archive(base_report, base_markdown)
    report = build_report(include_archive_metadata=True, archive=archive)
    markdown = markdown_report(report)
    checksum = f"{sha256_bytes(archive)}  {ARCHIVE_PATH.name}\n"
    return {
        REPORT_PATH: dump_json(report).encode("utf-8"),
        MARKDOWN_PATH: markdown.encode("utf-8"),
        ARCHIVE_PATH: archive,
        CHECKSUM_PATH: checksum.encode("utf-8"),
    }


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, data in generate().items():
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)}")


def check_outputs() -> None:
    expected = generate()
    stale = []
    for path, data in expected.items():
        if not path.exists() or path.read_bytes() != data:
            stale.append(str(path.relative_to(ROOT)))
    if stale:
        raise CleanroomBootstrapGenerationError(
            "release cleanroom bootstrap assets are stale; run "
            "`python3 scripts/generate_release_cleanroom_bootstrap.py`: "
            + ", ".join(stale)
        )
    print("release cleanroom bootstrap assets are up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            check_outputs()
        else:
            write_outputs()
    except Exception as exc:
        print(f"generate_release_cleanroom_bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
