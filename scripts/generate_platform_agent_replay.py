#!/usr/bin/env python3
"""Generate public platform-agent release replay evidence assets."""

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
REPORT_PATH = OUTPUT_DIR / "study-anything-platform-agent-replay.json"
MARKDOWN_PATH = OUTPUT_DIR / "study-anything-platform-agent-replay.md"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-platform-agent-replay.zip"
CHECKSUM_PATH = OUTPUT_DIR / "study-anything-platform-agent-replay.sha256"
ARCHIVE_ROOT = "study-anything-platform-agent-replay"

SCHEMA_VERSION = "platform-agent-release-replay-v1"
RELEASE_VERSION = "v0.3.27-alpha"
RELEASE_REPO = "jzvcpe-goat/study-anything"
RELEASE_URL = f"https://github.com/{RELEASE_REPO}/releases/tag/{RELEASE_VERSION}"
REQUIRED_TOOLS = [
    "study_anything_health",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
]
PLATFORMS = ["kimi", "codex", "workbuddy", "generic-openapi"]
PUBLIC_ASSET_PATHS = (
    "docs/platform-agent-release-replay.md",
    "docs/release-asset-bootstrap.md",
    "docs/release-asset-adoption.md",
    "docs/platform-agent-integrations.md",
    "scripts/replay_platform_agent_from_release.py",
    "scripts/bootstrap_from_release.py",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/packs/kimi/README.md",
    "platform/packs/codex/README.md",
    "platform/packs/workbuddy/README.md",
)
CLASSIFICATION_MATRIX = [
    (
        "platform_agent_replay_ready",
        "pass",
        "Release assets were unpacked, platform tool import succeeded, and the minimal learning tool chain completed against a running API.",
    ),
    (
        "platform_agent_replay_metadata_ready",
        "metadata_only",
        "Release assets and tool imports are valid, but no API runtime was called.",
    ),
    (
        "tool_import_invalid",
        "block_release_claim",
        "OpenAI tools or OpenAPI operations are malformed, missing required tools, or expose unsafe security schemes.",
    ),
    ("api_unavailable", "needs_runtime", "The selected runtime did not expose a reachable Study Anything API."),
    ("runtime_launch_failed", "needs_runtime", "The local Skill Mode runtime could not be launched."),
    ("tool_call_failed", "block_release_claim", "A required platform tool call failed after import."),
    ("schema_mismatch", "block_release_claim", "A tool response did not match the expected schema or state."),
    ("privacy_leak", "block_release_claim", "The replay transcript included private source text, answers, secrets, or local paths."),
    (
        "platform_entrypoint_missing",
        "block_release_claim",
        "The selected platform pack entrypoint is missing from the adoption pack.",
    ),
    ("release_asset_invalid", "block_release_claim", "The release assets could not be downloaded, verified, or unpacked."),
]
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private platform replay source text",
    "Private platform replay learner answer",
    "AGENT_ENDPOINT=http",
]


class PlatformAgentReplayGenerationError(RuntimeError):
    """Readable platform-agent replay generation failure."""


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
        raise PlatformAgentReplayGenerationError(f"Platform replay evidence file is missing: {relative_path}")
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
        raise PlatformAgentReplayGenerationError(f"Platform replay evidence leaked private data: {leaks}")


def build_report(include_archive_metadata: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Prove that a Kimi, Codex, WorkBuddy, or generic OpenAPI operator can start from "
            "GitHub Release assets, import platform tool definitions, and replay the minimal "
            "Study Anything learning tool chain without exposing private learning data."
        ),
        "release_identity": {
            "tag": RELEASE_VERSION,
            "release_url": RELEASE_URL,
            "repo": RELEASE_REPO,
        },
        "commands": {
            "metadata_only": (
                "python3 scripts/replay_platform_agent_from_release.py --tag "
                f"{RELEASE_VERSION} --platform kimi --runtime metadata-only"
            ),
            "skill_mode": (
                "python3 scripts/replay_platform_agent_from_release.py --tag "
                f"{RELEASE_VERSION} --platform kimi --runtime skill-mode"
            ),
            "external_api": (
                "python3 scripts/replay_platform_agent_from_release.py --tag "
                f"{RELEASE_VERSION} --platform kimi --runtime external-api --api-base http://127.0.0.1:8000"
            ),
            "fixture_metadata_only": (
                "python3 scripts/replay_platform_agent_from_release.py --fixture "
                "fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated "
                "--platform kimi --runtime metadata-only"
            ),
        },
        "required_tools": REQUIRED_TOOLS,
        "platforms": PLATFORMS,
        "runtime_modes": ["metadata-only", "skill-mode", "external-api", "published-image"],
        "classification_matrix": [
            {"classification": item[0], "release_gate": item[1], "meaning": item[2]}
            for item in CLASSIFICATION_MATRIX
        ],
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
            raise PlatformAgentReplayGenerationError("archive bytes are required for archive metadata")
        report["archive"] = {
            "path": "platform/generated/study-anything-platform-agent-replay.zip",
            "sha256_path": "platform/generated/study-anything-platform-agent-replay.sha256",
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
    tools = "\n".join(f"- `{tool}`" for tool in report["required_tools"])
    return f"""# Study Anything Platform Agent Release Replay

Schema: `{report['schema_version']}`
Version: `{report['version']}`
Status: `{report['status']}`

This evidence verifies the platform Agent path after release assets are
available: import the tool manifest, call the minimum learning tool chain, and
emit a redacted transcript that is safe to attach to GitHub issues.

## Archive

{archive_line}

## Commands

{commands}

## Required Replay Tools

{tools}

## Classification Matrix

{matrix}

## Privacy

No raw source text, learner answers, Agent prompts, endpoint secrets, real model
keys, private support bundle payloads, or local absolute paths are included.
"""


def archive_readme() -> str:
    return f"""# Study Anything Platform Agent Release Replay

Version: {RELEASE_VERSION}
Schema: {SCHEMA_VERSION}

Run `python3 scripts/replay_platform_agent_from_release.py --tag {RELEASE_VERSION} --platform kimi --runtime metadata-only`
to verify release asset import readiness, then use `--runtime skill-mode` or
`--runtime external-api --api-base <url>` for tool-call replay.
"""


def archive_bytes(base_report: dict[str, Any], markdown: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        records: list[tuple[str, bytes]] = [
            (f"{ARCHIVE_ROOT}/EVIDENCE_README.md", archive_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(base_report).encode("utf-8")),
            (f"{ARCHIVE_ROOT}/study-anything-platform-agent-replay.md", markdown.encode("utf-8")),
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
    report, markdown, archive, checksum = build_outputs()
    REPORT_PATH.write_text(report, encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    CHECKSUM_PATH.write_text(checksum, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"wrote {MARKDOWN_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")
    print(f"wrote {CHECKSUM_PATH.relative_to(ROOT)}")


def check_outputs() -> None:
    expected_report, expected_markdown, expected_archive, expected_checksum = build_outputs()
    expected = {
        REPORT_PATH: expected_report.encode("utf-8"),
        MARKDOWN_PATH: expected_markdown.encode("utf-8"),
        ARCHIVE_PATH: expected_archive,
        CHECKSUM_PATH: expected_checksum.encode("utf-8"),
    }
    stale = [path for path, content in expected.items() if not path.is_file() or path.read_bytes() != content]
    if stale:
        names = ", ".join(str(path.relative_to(ROOT)) for path in stale)
        raise PlatformAgentReplayGenerationError(
            f"Generated platform-agent replay evidence is stale: {names}. "
            "Run `python3 scripts/generate_platform_agent_replay.py`."
        )
    print("ok    generated platform-agent release replay evidence is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            check_outputs()
        else:
            write_outputs()
    except PlatformAgentReplayGenerationError as exc:
        print(f"generate_platform_agent_replay failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
