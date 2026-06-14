#!/usr/bin/env python3
"""Generate redacted field-adoption rehearsal transcripts and failed-import fixtures."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "platform" / "generated" / "study-anything-platform-field-rehearsal.json"
FIXTURE_DIR = ROOT / "fixtures" / "platform-import-failures"
SCHEMA_VERSION = "platform-field-adoption-rehearsal-v1"
FIXTURE_SCHEMA_VERSION = "platform-import-failure-fixture-v1"
RELEASE_VERSION = "v0.3.24-alpha"
PLATFORMS = ("kimi", "codex", "workbuddy", "generic")
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
    "Private source text:",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
]


class PlatformFieldRehearsalGenerationError(RuntimeError):
    """Readable field-rehearsal generation failure."""


QUIRKS: list[dict[str, Any]] = [
    {
        "id": "schema_mismatch",
        "title": "Schema mismatch",
        "detection_signal": "Imported asset declares an unexpected schema_version or OpenAPI version.",
        "likely_cause": "The platform imported an old adoption pack or a generated asset from another release.",
        "next_commands": [
            "python3 scripts/generate_platform_agent_assets.py --check",
            "python3 scripts/verify_platform_field_rehearsal.py --check",
        ],
        "safe_feedback_fields": ["schema_version", "asset_path", "expected_version", "found_version"],
    },
    {
        "id": "missing_local_gateway",
        "title": "Missing local gateway",
        "detection_signal": "The platform cannot reach the local Study Anything API or user-owned Agent gateway.",
        "likely_cause": "Skill Mode, Docker Compose, or the user's external Agent gateway is not running.",
        "next_commands": [
            "./scripts/launch_skill_mode.sh",
            "python3 scripts/diagnose_adoption.py",
        ],
        "safe_feedback_fields": ["platform_id", "api_base", "gateway_mode", "diagnostic_code"],
    },
    {
        "id": "unsupported_auth_mode",
        "title": "Unsupported auth mode",
        "detection_signal": "The platform requests API key auth for Study Anything platform tools.",
        "likely_cause": "The import flow confused user-owned Agent credentials with Study Anything tools.",
        "next_commands": [
            "python3 scripts/verify_ecosystem_submission_pack.py",
            "python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check",
        ],
        "safe_feedback_fields": ["platform_id", "auth_mode", "tool_asset"],
    },
    {
        "id": "tool_naming_drift",
        "title": "Tool naming drift",
        "detection_signal": "Imported tool names or OpenAPI operationIds differ from the source manifest.",
        "likely_cause": "The platform renamed tools during import or mixed OpenAI tools with OpenAPI paths.",
        "next_commands": [
            "python3 scripts/generate_platform_bundle_manifest.py --check",
            "python3 scripts/verify_ecosystem_submission_pack.py",
        ],
        "safe_feedback_fields": ["platform_id", "missing_tool", "import_asset"],
    },
    {
        "id": "timeout",
        "title": "Timeout",
        "detection_signal": "A platform tool call exceeds the platform or local gateway timeout.",
        "likely_cause": "First-run dependency setup, slow Docker pull, or a cold user-owned Agent gateway.",
        "next_commands": [
            "python3 scripts/diagnose_adoption.py",
            "python3 scripts/verify_clean_clone_adoption.py --repo .",
        ],
        "safe_feedback_fields": ["platform_id", "tool_name", "timeout_seconds", "diagnostic_code"],
    },
    {
        "id": "cors_localhost",
        "title": "CORS or localhost restriction",
        "detection_signal": "Browser-based platform import cannot call localhost directly.",
        "likely_cause": "The platform runs in a browser sandbox without local network permission.",
        "next_commands": [
            "python3 scripts/openai_compatible_agent_gateway.py --help",
            "python3 scripts/diagnose_adoption.py",
        ],
        "safe_feedback_fields": ["platform_id", "runtime_surface", "blocked_origin"],
    },
    {
        "id": "package_corruption",
        "title": "Package corruption",
        "detection_signal": "The adoption pack zip cannot be opened or its sha256 manifest does not match.",
        "likely_cause": "The pack was edited manually, partially downloaded, or re-zipped by another tool.",
        "next_commands": [
            "python3 scripts/generate_platform_adoption_pack.py",
            "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
        ],
        "safe_feedback_fields": ["archive_name", "expected_sha256", "found_sha256"],
    },
    {
        "id": "version_drift",
        "title": "Version drift",
        "detection_signal": "The platform pack, generated report, release notes, or ecosystem submission versions differ.",
        "likely_cause": "A branch mixed artifacts from multiple alpha releases.",
        "next_commands": [
            "python3 scripts/verify_platform_field_rehearsal.py --check",
            "./scripts/release_check.sh",
        ],
        "safe_feedback_fields": ["expected_version", "found_version", "asset_path"],
    },
]


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformFieldRehearsalGenerationError(
            f"Generated field rehearsal payload contains private data: {leaks}"
        )


def platform_transcript(platform_id: str) -> dict[str, Any]:
    import_asset = {
        "kimi": "platform/generated/study-anything-openai-tools.json",
        "codex": "skills/study-anything/SKILL.md",
        "workbuddy": "platform/generated/study-anything-platform-openapi.json",
        "generic": "platform/generated/study-anything-platform-openapi.json",
    }[platform_id]
    platform_name = {
        "kimi": "Kimi-compatible tool workspace",
        "codex": "Codex Skill workspace",
        "workbuddy": "WorkBuddy-style HTTP workspace",
        "generic": "Generic OpenAPI or MCP-capable platform",
    }[platform_id]
    return {
        "platform_id": platform_id,
        "platform_name": platform_name,
        "status": "ready_for_field_rehearsal",
        "import_asset": import_asset,
        "events": [
            {
                "step": "download_pack",
                "actor": "operator",
                "evidence": "study-anything-platform-adoption-pack.zip opened and manifest sha256 checked",
            },
            {
                "step": "import_tools",
                "actor": "platform_agent",
                "evidence": f"{import_asset} selected without exposing management endpoints",
            },
            {
                "step": "start_local_runtime",
                "actor": "operator",
                "evidence": "Skill Mode, source Compose, or published-image runtime started locally",
            },
            {
                "step": "run_safe_probe",
                "actor": "platform_agent",
                "evidence": "health, tool catalog, and deterministic fake-agent lesson flow checked",
            },
            {
                "step": "collect_feedback",
                "actor": "operator",
                "evidence": "redacted feedback package available for manual support handoff",
            },
        ],
        "expected_evidence": [
            "platform_field_rehearsal.schema_version == platform-field-adoption-rehearsal-v1",
            "platform_feedback_package.schema_version == platform-feedback-package-v1",
            "no raw source text, learner answers, or model secrets in transcript",
        ],
    }


def fixture_payload(quirk: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "failure_id": quirk["id"],
        "status": "mock_failure_ready",
        "platform_ids": list(PLATFORMS),
        "observed_error": {
            "message": f"Simulated {quirk['title']} during external platform import.",
            "diagnostic_code": quirk["id"],
            "raw_error_redacted": True,
        },
        "diagnosis": {
            "detection_signal": quirk["detection_signal"],
            "likely_cause": quirk["likely_cause"],
            "next_commands": quirk["next_commands"],
        },
        "safe_feedback_fields": quirk["safe_feedback_fields"],
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "real_model_keys_included": False,
            "agent_endpoint_secrets_included": False,
            "browser_video_private_context_included": False,
        },
    }


def build_report() -> dict[str, Any]:
    fixture_paths = [
        str((FIXTURE_DIR / f"{quirk['id']}.json").relative_to(ROOT)) for quirk in QUIRKS
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Turn platform adoption diagnostics into reusable Kimi, Codex, WorkBuddy, "
            "and generic OpenAPI import rehearsals with actionable failed-import fixtures."
        ),
        "platforms": [platform_transcript(platform_id) for platform_id in PLATFORMS],
        "quirks_catalog": QUIRKS,
        "failed_import_fixtures": [
            {
                "failure_id": quirk["id"],
                "path": str((FIXTURE_DIR / f"{quirk['id']}.json").relative_to(ROOT)),
                "schema_version": FIXTURE_SCHEMA_VERSION,
            }
            for quirk in QUIRKS
        ],
        "support_handoff": {
            "feedback_package": "platform/generated/study-anything-platform-feedback-package.zip",
            "manual_only": True,
            "automatic_upload": False,
            "safe_fields": [
                "platform_id",
                "release_version",
                "diagnostic_code",
                "asset_path",
                "redacted_log_sample",
                "reproduction_commands",
            ],
        },
        "privacy_assertions": {
            "real_model_keys_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_prompts_in_report": False,
            "browser_video_private_context_in_report": False,
            "fixtures_are_mock_only": True,
        },
        "acceptance": {
            "generate_command": "python3 scripts/generate_platform_field_rehearsal.py --check",
            "verify_command": "python3 scripts/verify_platform_field_rehearsal.py --check",
            "fixture_count": len(fixture_paths),
            "fixture_paths": fixture_paths,
        },
    }
    assert_no_leaks(report)
    return report


def build_outputs() -> dict[Path, str]:
    outputs = {OUTPUT_PATH: dump_json(build_report())}
    for quirk in QUIRKS:
        payload = fixture_payload(quirk)
        assert_no_leaks(payload)
        outputs[FIXTURE_DIR / f"{quirk['id']}.json"] = dump_json(payload)
    return outputs


def write_outputs() -> None:
    outputs = build_outputs()
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


def check_outputs() -> None:
    outputs = build_outputs()
    missing = [str(path.relative_to(ROOT)) for path in outputs if not path.exists()]
    stale = [
        str(path.relative_to(ROOT))
        for path, content in outputs.items()
        if path.exists() and path.read_text(encoding="utf-8") != content
    ]
    if missing or stale:
        raise PlatformFieldRehearsalGenerationError(
            "Platform field rehearsal assets are stale. Run "
            "`python3 scripts/generate_platform_field_rehearsal.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform field rehearsal assets are up to date")


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
        print(f"generate_platform_field_rehearsal failed: {exc}", file=sys.stderr)
        sys.exit(1)
