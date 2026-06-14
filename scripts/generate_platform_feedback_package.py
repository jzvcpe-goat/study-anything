#!/usr/bin/env python3
"""Generate a redacted local feedback package for platform adoption failures."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
MANIFEST_PATH = OUTPUT_DIR / "study-anything-platform-feedback-package.json"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-platform-feedback-package.zip"
ARCHIVE_ROOT = "study-anything-platform-feedback-package"
SCHEMA_VERSION = "platform-feedback-package-v1"
DIAGNOSTICS_SCHEMA = "platform-adoption-feedback-diagnostics-v1"
RELEASE_VERSION = "v0.3.21-alpha"
DIAGNOSTIC_CATEGORIES = [
    "pack_schema_invalid",
    "required_file_missing",
    "openapi_import_missing_operation",
    "openai_tools_malformed",
    "unsupported_platform_capability",
    "localhost_api_unreachable",
    "agent_endpoint_unreachable",
    "agent_eval_evidence_missing",
    "version_drift",
    "missing_required_command",
    "privacy_contract_violation",
]
REDACTED_LOG_SAMPLE = """Study Anything platform feedback log sample
status=needs_attention
platform=${PLATFORM_ID}
error_type=${ERROR_TYPE}
api_base=http://127.0.0.1:8000
agent_endpoint=${REDACTED_AGENT_ENDPOINT}
raw_source_text=${REDACTED}
learner_answer=${REDACTED}
model_or_judge_secret=${REDACTED}
"""


class PlatformFeedbackPackageError(RuntimeError):
    """Readable feedback-package generation failure."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "name": "study-anything-platform-feedback-package",
        "status": "ready",
        "diagnostics_schema": DIAGNOSTICS_SCHEMA,
        "summary": (
            "Local-only, redacted feedback payload for Kimi/Codex/WorkBuddy import, "
            "runtime, and adoption failures."
        ),
        "supported_platforms": [
            "kimi-work",
            "codex",
            "workbuddy-style-http",
            "generic-http-tools",
        ],
        "diagnostic_categories": DIAGNOSTIC_CATEGORIES,
        "included_sections": [
            "version",
            "platform",
            "error_type",
            "diagnostic_summary",
            "redacted_logs",
            "reproduction_commands",
        ],
        "excluded_sections": [
            "raw source text",
            "learner answers",
            "agent prompts",
            "real model API keys",
            "agent endpoint secrets",
            "personal profile",
            "browser or video private context",
        ],
        "privacy": {
            "redacted": True,
            "automatic_upload": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "real_model_keys_included": False,
            "agent_endpoint_secrets_included": False,
            "personal_profile_included": False,
            "browser_video_private_context_included": False,
        },
        "operator_commands": {
            "diagnose": "python3 scripts/diagnose_adoption.py",
            "verify_diagnostics": (
                "python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check"
            ),
            "generate_feedback_package": "python3 scripts/generate_platform_feedback_package.py",
            "external_adoption": (
                "python3 scripts/verify_external_adoption.py --pack "
                "platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree"
            ),
        },
    }


def archive_bytes(manifest: dict[str, Any]) -> bytes:
    import io

    diagnostics_summary = {
        "schema_version": DIAGNOSTICS_SCHEMA,
        "version": RELEASE_VERSION,
        "status": "redacted-template",
        "diagnostic_categories": DIAGNOSTIC_CATEGORIES,
        "feedback_package_schema": SCHEMA_VERSION,
    }
    files = [
        (f"{ARCHIVE_ROOT}/manifest.json", dump_json(manifest).encode("utf-8")),
        (
            f"{ARCHIVE_ROOT}/diagnostics-summary.json",
            dump_json(diagnostics_summary).encode("utf-8"),
        ),
        (f"{ARCHIVE_ROOT}/redacted-log-sample.txt", REDACTED_LOG_SAMPLE.encode("utf-8")),
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in files:
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return buffer.getvalue()


def build_outputs() -> tuple[str, bytes]:
    manifest = build_manifest()
    archive = archive_bytes(manifest)
    enriched = dict(manifest)
    enriched["archive_name"] = ARCHIVE_PATH.name
    enriched["archive_sha256"] = sha256_bytes(archive)
    enriched["archive_bytes"] = len(archive)
    return dump_json(enriched), archive


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_text, archive = build_outputs()
    MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")


def check_outputs() -> None:
    expected_manifest, expected_archive = build_outputs()
    missing = [
        str(path.relative_to(ROOT))
        for path in (MANIFEST_PATH, ARCHIVE_PATH)
        if not path.exists()
    ]
    stale = []
    if MANIFEST_PATH.exists() and MANIFEST_PATH.read_text(encoding="utf-8") != expected_manifest:
        stale.append(str(MANIFEST_PATH.relative_to(ROOT)))
    if ARCHIVE_PATH.exists() and ARCHIVE_PATH.read_bytes() != expected_archive:
        stale.append(str(ARCHIVE_PATH.relative_to(ROOT)))
    if missing or stale:
        raise PlatformFeedbackPackageError(
            "Platform feedback package is stale. Run "
            "`python3 scripts/generate_platform_feedback_package.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform feedback package is up to date")


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
        print(f"generate_platform_feedback_package failed: {exc}", file=sys.stderr)
        sys.exit(1)
