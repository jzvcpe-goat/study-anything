#!/usr/bin/env python3
"""Generate external-adopter onboarding and maintainer readiness assets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "platform" / "generated" / "study-anything-platform-onboarding-readiness.json"
DASHBOARD_JSON_PATH = ROOT / "platform" / "generated" / "study-anything-platform-triage-dashboard.json"
DASHBOARD_MD_PATH = ROOT / "platform" / "generated" / "study-anything-platform-triage-dashboard.md"
RELEASE_BLOCKER_DIR = ROOT / "fixtures" / "platform-release-blockers"

SCHEMA_VERSION = "platform-onboarding-readiness-v1"
WALKTHROUGH_SCHEMA_VERSION = "first-external-adopter-walkthrough-v1"
SLA_SCHEMA_VERSION = "maintainer-sla-labels-v1"
ROTATION_SCHEMA_VERSION = "maintainer-rotation-checklist-v1"
DASHBOARD_SCHEMA_VERSION = "platform-triage-dashboard-v1"
RELEASE_BLOCKER_SCHEMA_VERSION = "platform-release-blocker-fixture-v1"
RELEASE_VERSION = "v0.3.31-alpha"
PLATFORMS = ("kimi", "codex", "workbuddy", "generic")
SUPPORT_CATEGORIES = (
    "platform_import_failure",
    "local_gateway_failure",
    "published_image_pull_failure",
    "agent_eval_evidence_failure",
    "docs_confusion",
)
RELEASE_BLOCKER_IDS = (
    "tool_import_blocker",
    "local_gateway_blocker",
    "published_image_blocker",
    "agent_eval_blocker",
    "support_bundle_privacy_blocker",
)
SLA_LABELS = (
    ("intake", "New external adopter issue needs support bundle completeness check.", 24),
    ("needs-repro", "Maintainer needs a fixture-backed reproduction.", 48),
    ("confirmed", "Maintainer reproduced the issue with current generated assets.", 48),
    ("blocked-by-platform", "A host platform capability or localhost policy blocks the path.", 72),
    ("docs-fix", "Documentation or copyable command fix is enough to close.", 48),
    ("release-blocker", "A supported happy path fails with current release assets.", 24),
    ("resolved", "Reporter or maintainer verified the closing command.", 0),
)
REQUIRED_SUPPORT_FIELDS = (
    "release_version",
    "platform_id",
    "command_ran",
    "diagnostic_code",
    "fixture_id",
    "redacted_log_excerpt",
    "next_commands_tried",
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
]


class PlatformOnboardingReadinessGenerationError(RuntimeError):
    """Readable onboarding-readiness generation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformOnboardingReadinessGenerationError(
            f"Generated onboarding readiness payload contains private data: {leaks}"
        )


def walkthrough_entry(platform_id: str) -> dict[str, Any]:
    platform_names = {
        "kimi": "Kimi-compatible workspace",
        "codex": "Codex Skill workspace",
        "workbuddy": "WorkBuddy-style HTTP workspace",
        "generic": "Generic OpenAPI/MCP-capable workspace",
    }
    return {
        "platform_id": platform_id,
        "display_name": platform_names[platform_id],
        "schema_version": WALKTHROUGH_SCHEMA_VERSION,
        "shortest_success_path": [
            "Start Study Anything with Skill Mode or the published image.",
            "Import the generated OpenAPI or OpenAI-compatible tools from the adoption pack.",
            "Ask the platform Agent to create one session, add one cited reading, run quiz generation, answer once, and check mastery.",
            "Run python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree.",
        ],
        "failure_fallback_path": [
            "Run python3 scripts/diagnose_adoption.py.",
            "Run python3 scripts/verify_platform_support_triage.py --check.",
            "Attach only the redacted platform-support-bundle-v1 fields to the matching GitHub issue template.",
        ],
        "success_evidence": [
            "adoption-proof-v1",
            "platform-onboarding-readiness-v1",
            "platform-triage-dashboard-v1",
        ],
        "must_not_request": [
            "raw source text",
            "learner answers",
            "real Agent endpoint secrets",
            "model keys",
            "browser or video private context",
        ],
    }


def sla_labels() -> list[dict[str, Any]]:
    return [
        {
            "label": label,
            "schema_version": SLA_SCHEMA_VERSION,
            "meaning": meaning,
            "target_first_response_hours": hours,
            "close_when": "The linked verification command passes or the issue is documented as a platform limitation.",
        }
        for label, meaning, hours in SLA_LABELS
    ]


def release_blocker_payload(blocker_id: str) -> dict[str, Any]:
    category_by_blocker = {
        "tool_import_blocker": "platform_import_failure",
        "local_gateway_blocker": "local_gateway_failure",
        "published_image_blocker": "published_image_pull_failure",
        "agent_eval_blocker": "agent_eval_evidence_failure",
        "support_bundle_privacy_blocker": "docs_confusion",
    }
    command_by_blocker = {
        "tool_import_blocker": "python3 scripts/verify_ecosystem_submission_pack.py",
        "local_gateway_blocker": "python3 scripts/verify_openai_compatible_gateway.py --gateway-only",
        "published_image_blocker": "python3 scripts/verify_published_image_launch.py --tag v0.3.31-alpha --pull-timeout-seconds 180 --allow-pull-timeout-report",
        "agent_eval_blocker": "python3 scripts/verify_agent_eval_marketplace_enforcement.py --check",
        "support_bundle_privacy_blocker": "python3 scripts/verify_platform_onboarding_readiness.py --check",
    }
    return {
        "schema_version": RELEASE_BLOCKER_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "blocker_id": blocker_id,
        "linked_support_category": category_by_blocker[blocker_id],
        "status": "mock_release_blocker_ready",
        "minimum_reproduction_command": command_by_blocker[blocker_id],
        "required_labels": ["intake", "needs-repro", "release-blocker"],
        "close_when": "The current release assets pass the minimum reproduction command and the affected platform walkthrough is updated.",
        "escalate_when": "The blocker affects a documented shortest success path for Kimi, Codex, WorkBuddy, or generic OpenAPI/MCP.",
        "support_bundle": {
            "release_version": RELEASE_VERSION,
            "platform_id": "generic",
            "command_ran": command_by_blocker[blocker_id],
            "diagnostic_code": blocker_id,
            "fixture_id": blocker_id,
            "redacted_log_excerpt": (
                "status=release_blocker\n"
                f"diagnostic_code={blocker_id}\n"
                "source_text_redacted=<yes>\n"
                "answer_redacted=<yes>\n"
                "agent_endpoint=<redacted>\n"
                "model_or_judge_secret=<redacted>\n"
            ),
            "next_commands_tried": [
                command_by_blocker[blocker_id],
                "python3 scripts/verify_platform_support_triage.py --check",
            ],
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "real_model_keys_included": False,
            "agent_endpoint_secrets_included": False,
            "browser_video_private_context_included": False,
            "automatic_upload": False,
        },
    }


def rotation_checklist() -> dict[str, Any]:
    return {
        "schema_version": ROTATION_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "handoff_window": "weekly_or_before_release",
        "checklist": [
            "Run python3 scripts/verify_platform_onboarding_readiness.py --check.",
            "Open platform/generated/study-anything-platform-triage-dashboard.md.",
            "Review every release-blocker fixture under fixtures/platform-release-blockers/.",
            "Confirm at least one maintainer can reproduce each support category without private user data.",
            "Close only with a verified command, documented platform limitation, or merged docs/code fix.",
        ],
        "required_labels": [label for label, _meaning, _hours in SLA_LABELS],
    }


def dashboard_payload(report: dict[str, Any]) -> dict[str, Any]:
    blocker_categories = Counter(
        item["linked_support_category"] for item in report["release_blocker_fixtures"]
    )
    return {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "support_bundle_completeness": {
            "required_fields": list(REQUIRED_SUPPORT_FIELDS),
            "support_ticket_fixture_count": len(SUPPORT_CATEGORIES),
            "release_blocker_fixture_count": len(RELEASE_BLOCKER_IDS),
            "complete_fixture_count": len(SUPPORT_CATEGORIES) + len(RELEASE_BLOCKER_IDS),
        },
        "diagnostic_code_distribution": dict(sorted(blocker_categories.items())),
        "fixture_coverage": {
            "support_categories": list(SUPPORT_CATEGORIES),
            "release_blockers": list(RELEASE_BLOCKER_IDS),
            "platform_walkthroughs": list(PLATFORMS),
        },
        "privacy_scan": {
            "status": "pass",
            "raw_source_text_found": False,
            "learner_answers_found": False,
            "agent_endpoint_secrets_found": False,
            "real_model_keys_found": False,
            "automatic_upload": False,
        },
        "release_blockers": [
            {
                "blocker_id": item["blocker_id"],
                "linked_support_category": item["linked_support_category"],
                "minimum_reproduction_command": item["minimum_reproduction_command"],
            }
            for item in report["release_blocker_fixtures"]
        ],
    }


def dashboard_markdown(payload: dict[str, Any]) -> str:
    blockers = "\n".join(
        f"- `{item['blocker_id']}` -> `{item['linked_support_category']}`: `{item['minimum_reproduction_command']}`"
        for item in payload["release_blockers"]
    )
    labels = "\n".join(f"- `{label}`" for label, _meaning, _hours in SLA_LABELS)
    return f"""# Study Anything Platform Triage Dashboard

Schema: `{payload["schema_version"]}`
Version: `{RELEASE_VERSION}`
Status: `{payload["status"]}`

## Fixture Coverage

- support categories: {len(SUPPORT_CATEGORIES)}
- release blockers: {len(RELEASE_BLOCKER_IDS)}
- platform walkthroughs: {len(PLATFORMS)}

## Release Blockers

{blockers}

## Maintainer Labels

{labels}

## Privacy

This dashboard is generated from mock fixtures and schema metadata only. It must not include raw
source text, learner answers, real Agent endpoints, model keys, or browser/video private context.
"""


def build_report() -> dict[str, Any]:
    blockers = [release_blocker_payload(blocker_id) for blocker_id in RELEASE_BLOCKER_IDS]
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Turn support desk triage into a first-adopter onboarding path and maintainer "
            "SLA loop that can be verified before an alpha release is promoted."
        ),
        "walkthrough": {
            "schema_version": WALKTHROUGH_SCHEMA_VERSION,
            "platforms": [walkthrough_entry(platform_id) for platform_id in PLATFORMS],
            "shortest_success_path_minutes_target": 15,
        },
        "maintainer_sla": {
            "schema_version": SLA_SCHEMA_VERSION,
            "labels": sla_labels(),
            "release_blocker_first_response_hours": 24,
        },
        "maintainer_rotation": rotation_checklist(),
        "release_blocker_fixtures": [
            {
                "blocker_id": blocker["blocker_id"],
                "path": f"fixtures/platform-release-blockers/{blocker['blocker_id']}.json",
                "schema_version": RELEASE_BLOCKER_SCHEMA_VERSION,
                "linked_support_category": blocker["linked_support_category"],
            }
            for blocker in blockers
        ],
        "linked_assets": {
            "support_triage": "platform/generated/study-anything-platform-support-triage.json",
            "triage_dashboard_json": "platform/generated/study-anything-platform-triage-dashboard.json",
            "triage_dashboard_markdown": "platform/generated/study-anything-platform-triage-dashboard.md",
            "adoption_pack": "platform/generated/study-anything-platform-adoption-pack.zip",
        },
        "privacy_assertions": {
            "real_model_keys_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_prompts_in_report": False,
            "browser_video_private_context_in_report": False,
            "automatic_upload": False,
            "fixtures_are_mock_only": True,
        },
        "acceptance": {
            "generate_command": "python3 scripts/generate_platform_onboarding_readiness.py --check",
            "verify_command": "python3 scripts/verify_platform_onboarding_readiness.py --check",
            "pack_command": (
                "python3 scripts/verify_platform_onboarding_readiness.py "
                "--pack platform/generated/study-anything-platform-adoption-pack.zip"
            ),
            "walkthrough_count": len(PLATFORMS),
            "sla_label_count": len(SLA_LABELS),
            "release_blocker_fixture_count": len(RELEASE_BLOCKER_IDS),
        },
    }
    assert_no_leaks(report)
    return report


def build_outputs() -> dict[Path, str]:
    report = build_report()
    dashboard = dashboard_payload(
        {
            **report,
            "release_blocker_fixtures": [
                release_blocker_payload(blocker_id) for blocker_id in RELEASE_BLOCKER_IDS
            ],
        }
    )
    assert_no_leaks(report)
    assert_no_leaks(dashboard)
    outputs = {
        OUTPUT_PATH: dump_json(report),
        DASHBOARD_JSON_PATH: dump_json(dashboard),
        DASHBOARD_MD_PATH: dashboard_markdown(dashboard),
    }
    for blocker_id in RELEASE_BLOCKER_IDS:
        payload = release_blocker_payload(blocker_id)
        assert_no_leaks(payload)
        outputs[RELEASE_BLOCKER_DIR / f"{blocker_id}.json"] = dump_json(payload)
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
        raise PlatformOnboardingReadinessGenerationError(
            "Platform onboarding readiness assets are stale. Run "
            "`python3 scripts/generate_platform_onboarding_readiness.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform onboarding readiness assets are up to date")


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
        print(f"generate_platform_onboarding_readiness failed: {exc}", file=sys.stderr)
        sys.exit(1)
