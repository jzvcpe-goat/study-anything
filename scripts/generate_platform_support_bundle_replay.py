#!/usr/bin/env python3
"""Generate support bundle replay evidence and fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from localhost_diagnostics import redact_diagnostic


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "platform" / "generated" / "study-anything-platform-support-bundle-replay.json"
FIXTURE_DIR = ROOT / "fixtures" / "platform-support-bundles"
SCHEMA_VERSION = "platform-support-bundle-replay-evidence-v1"
REPLAY_SCHEMA_VERSION = "platform-support-bundle-replay-v1"
BUNDLE_SCHEMA_VERSION = "platform-support-bundle-v1"
RELEASE_VERSION = "v0.3.29-alpha"

REQUIRED_BUNDLE_FIELDS = (
    "release_version",
    "platform_id",
    "runtime",
    "failure_class",
    "workflow_stage",
    "command_ran",
    "diagnostic_code",
    "redacted_log_excerpt",
    "next_commands_tried",
    "recommended_next_steps",
    "replay_command",
    "redaction_flags",
)

REDACTION_FLAGS = {
    "raw_source_text_included": False,
    "learner_answers_included": False,
    "agent_prompts_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
    "local_absolute_paths_included": False,
    "browser_video_private_context_included": False,
    "personal_profile_included": False,
    "automatic_upload": False,
}

FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
]


class SupportBundleReplayGenerationError(RuntimeError):
    """Readable support-bundle replay generation failure."""


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"generate_platform_support_bundle_replay failed: {diagnostic}",
            "",
            "Next steps:",
            "1. Rebuild support bundle replay evidence: python3 scripts/generate_platform_support_bundle_replay.py",
            "2. Re-check generated support bundle replay evidence: python3 scripts/generate_platform_support_bundle_replay.py --check",
            "3. Verify the replay fixtures: python3 scripts/verify_platform_support_bundle_replay.py --check",
            "4. Replay a known fixture: python3 scripts/replay_support_bundle.py --bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json",
        ]
    )


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise SupportBundleReplayGenerationError(
            f"Support bundle replay evidence leaked private data: {leaks}"
        )


def fixture_payloads() -> dict[str, dict[str, Any]]:
    base = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "release_version": RELEASE_VERSION,
        "platform_id": "kimi",
        "replay_command": (
            "python3 scripts/replay_support_bundle.py "
            "--bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json"
        ),
        "redaction_flags": dict(REDACTION_FLAGS),
    }
    return {
        "local-ghcr-pull-timeout": {
            **base,
            "runtime": "published-image",
            "failure_class": "blocked_by_local_ghcr_pull",
            "workflow_stage": "published_image_pull",
            "command_ran": (
                "python3 scripts/verify_published_image_launch.py "
                f"--tag {RELEASE_VERSION} --pull-timeout-seconds 180 --allow-pull-timeout-report"
            ),
            "diagnostic_code": "blocked_by_local_ghcr_pull",
            "fixture_id": "local-ghcr-pull-timeout",
            "redacted_log_excerpt": (
                "Published image manifest is available, but this local machine could not finish "
                "pulling the image within the configured timeout."
            ),
            "next_commands_tried": [
                "docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
                "python3 scripts/verify_published_image_launch.py --tag v0.3.29-alpha --manifest-only",
            ],
            "recommended_next_steps": [
                "Verify GitHub docker-images workflow for the same tag.",
                "Retry full published-image smoke from a faster network or use Skill Mode.",
            ],
            "manifest_evidence": {
                "status": "ok",
                "platforms": ["linux/amd64", "linux/arm64"],
                "required_platforms": ["linux/amd64", "linux/arm64"],
            },
            "image_evidence": {
                "api_image": "ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha",
                "docker_images_workflow_status": "success",
            },
        },
        "cleanroom-runtime-launch-failed": {
            **base,
            "runtime": "skill-mode",
            "failure_class": "runtime_launch_failed",
            "workflow_stage": "cleanroom_bootstrap",
            "command_ran": (
                "python3 platform/bootstrap/study_anything_release_bootstrap.py "
                f"--tag {RELEASE_VERSION} --platform kimi --runtime skill-mode"
            ),
            "diagnostic_code": "runtime_launch_failed",
            "fixture_id": "cleanroom-runtime-launch-failed",
            "redacted_log_excerpt": "Skill Mode replay could not launch before the health check timeout.",
            "next_commands_tried": ["metadata-only bootloader", "skill-mode replay"],
            "recommended_next_steps": [
                "Run metadata-only first and attach this support bundle.",
                "Retry Skill Mode on an unused port or run the maintainer replay command.",
            ],
            "release_assets": {
                "tag": RELEASE_VERSION,
                "asset_count": 6,
                "github_digest_verified_count": 6,
            },
            "tool_import_status": "ready",
        },
        "privacy-contract-violation": {
            **base,
            "runtime": "skill-mode",
            "failure_class": "privacy_contract_violation",
            "workflow_stage": "support_handoff",
            "command_ran": "python3 scripts/replay_support_bundle.py --bundle support-bundle.json",
            "diagnostic_code": "privacy_contract_violation",
            "fixture_id": "privacy-contract-violation",
            "redacted_log_excerpt": "Reporter indicated an unsafe support bundle was generated.",
            "next_commands_tried": ["support bundle replay"],
            "recommended_next_steps": [
                "Do not post the unsafe bundle publicly.",
                "Regenerate diagnostics with source text, answers, endpoints, and secrets redacted.",
            ],
            "redaction_flags": {
                **REDACTION_FLAGS,
                "raw_source_text_included": True,
            },
        },
    }


def build_report() -> dict[str, Any]:
    fixtures = fixture_payloads()
    fixture_refs = []
    for fixture_id, payload in fixtures.items():
        text = dump_json(payload)
        fixture_refs.append(
            {
                "fixture_id": fixture_id,
                "path": f"fixtures/platform-support-bundles/{fixture_id}.json",
                "schema_version": payload["schema_version"],
                "expected_classification": {
                    "local-ghcr-pull-timeout": "local_ghcr_pull_timeout",
                    "cleanroom-runtime-launch-failed": "runtime_launch_failed",
                    "privacy-contract-violation": "privacy_contract_violation",
                }[fixture_id],
                "sha256": sha256_text(text),
            }
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Close the external adopter support loop: a user shares a redacted support bundle, "
            "then a maintainer replays it into a stable classification and issue body."
        ),
        "schemas": {
            "support_bundle": BUNDLE_SCHEMA_VERSION,
            "maintainer_replay": REPLAY_SCHEMA_VERSION,
        },
        "required_bundle_fields": list(REQUIRED_BUNDLE_FIELDS),
        "fixture_refs": fixture_refs,
        "commands": {
            "maintainer_replay": (
                "python3 scripts/replay_support_bundle.py "
                "--bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json"
            ),
            "copy_issue_body": (
                "python3 scripts/replay_support_bundle.py "
                "--bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json --issue-body"
            ),
            "verify": "python3 scripts/verify_platform_support_bundle_replay.py --check",
        },
        "privacy_assertions": {
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_prompts_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "real_model_keys_in_report": False,
            "local_absolute_paths_in_report": False,
            "browser_video_private_context_in_report": False,
            "automatic_upload": False,
            "fixtures_are_mock_only": True,
        },
        "release_gate": {
            "pass_when": [
                "support bundle schema validates",
                "maintainer replay produces expected classification",
                "issue body is copyable and redacted",
                "privacy violation bundles are blocked",
            ],
            "block_when": [
                "bundle includes raw source text, answers, Agent endpoints, model keys, or local paths",
                "replay cannot classify the failure",
                "adoption pack omits replay scripts or fixtures",
            ],
        },
    }
    assert_no_leaks(report)
    return report


def build_outputs() -> dict[Path, str]:
    outputs = {OUTPUT_PATH: dump_json(build_report())}
    for fixture_id, payload in fixture_payloads().items():
        if fixture_id != "privacy-contract-violation":
            assert_no_leaks(payload)
        outputs[FIXTURE_DIR / f"{fixture_id}.json"] = dump_json(payload)
    return outputs


def write_outputs() -> None:
    for path, content in build_outputs().items():
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
        raise SupportBundleReplayGenerationError(
            "Support bundle replay assets are stale. Run "
            "`python3 scripts/generate_platform_support_bundle_replay.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated support bundle replay assets are up to date")


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
