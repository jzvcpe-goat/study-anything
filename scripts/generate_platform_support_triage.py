#!/usr/bin/env python3
"""Generate GitHub-first support triage assets for platform adoption failures."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "platform" / "generated" / "study-anything-platform-support-triage.json"
TICKET_DIR = ROOT / "fixtures" / "platform-support-tickets"
ISSUE_TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
SCHEMA_VERSION = "platform-support-triage-v1"
TICKET_SCHEMA_VERSION = "platform-support-ticket-fixture-v1"
ISSUE_TEMPLATE_SCHEMA_VERSION = "platform-support-issue-template-v1"
RELEASE_VERSION = "v0.3.22-alpha"
PLATFORMS = ("kimi", "codex", "workbuddy", "generic")
SUPPORT_CATEGORY_IDS = (
    "platform_import_failure",
    "local_gateway_failure",
    "published_image_pull_failure",
    "agent_eval_evidence_failure",
    "docs_confusion",
)
QUIRK_IDS = (
    "schema_mismatch",
    "missing_local_gateway",
    "unsupported_auth_mode",
    "tool_naming_drift",
    "timeout",
    "cors_localhost",
    "package_corruption",
    "version_drift",
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


class PlatformSupportTriageGenerationError(RuntimeError):
    """Readable support-triage generation failure."""


SUPPORT_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "platform_import_failure",
        "title": "Platform import failure",
        "labels": ["support", "platform-import"],
        "diagnostic_codes": list(QUIRK_IDS),
        "minimum_command": "python3 scripts/verify_platform_field_rehearsal.py --check",
        "fixture_id": "schema_mismatch",
    },
    {
        "id": "local_gateway_failure",
        "title": "Local gateway failure",
        "labels": ["support", "local-runtime"],
        "diagnostic_codes": ["missing_local_gateway", "cors_localhost", "timeout"],
        "minimum_command": "python3 scripts/diagnose_adoption.py",
        "fixture_id": "missing_local_gateway",
    },
    {
        "id": "published_image_pull_failure",
        "title": "Published image pull failure",
        "labels": ["support", "deployment"],
        "diagnostic_codes": ["timeout", "package_corruption", "version_drift"],
        "minimum_command": "python3 scripts/verify_published_image_launch.py --tag v0.3.22-alpha --pull-timeout-seconds 180 --allow-pull-timeout-report",
        "fixture_id": "timeout",
    },
    {
        "id": "agent_eval_evidence_failure",
        "title": "Agent eval evidence failure",
        "labels": ["support", "agent-eval"],
        "diagnostic_codes": ["agent_eval_evidence_missing", "missing_required_command", "version_drift"],
        "minimum_command": "python3 scripts/verify_agent_eval_marketplace_enforcement.py --check",
        "fixture_id": "version_drift",
    },
    {
        "id": "docs_confusion",
        "title": "Docs confusion",
        "labels": ["support", "docs"],
        "diagnostic_codes": ["docs_step_unclear", "missing_required_command", "unsupported_platform_capability"],
        "minimum_command": "python3 scripts/verify_ecosystem_submission_pack.py",
        "fixture_id": "tool_naming_drift",
    },
]


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise PlatformSupportTriageGenerationError(
            f"Generated support triage payload contains private data: {leaks}"
        )


def issue_template(category: dict[str, Any]) -> str:
    labels = ",".join(category["labels"])
    title_prefix = category["title"]
    return f"""---
name: {category["title"]}
about: Request help with a redacted Study Anything platform adoption issue
title: "[Support]: {title_prefix} - "
labels: {labels}
assignees: ""
---

<!--
schema_version: {ISSUE_TEMPLATE_SCHEMA_VERSION}
release_target: {RELEASE_VERSION}
Do not paste raw source text, learner answers, Agent prompts, Agent endpoints, model keys,
browser/video private context, or personal profile data.
-->

## Summary

## Platform

- Platform id: <!-- kimi | codex | workbuddy | generic -->
- Study Anything release: {RELEASE_VERSION}
- Runtime mode: <!-- skill-mode | published-image | source-compose | other -->

## Command Ran

```sh
{category["minimum_command"]}
```

## Diagnostic Code

<!-- Use one of: {", ".join(category["diagnostic_codes"])} -->

## Fixture Or Quirk Id

<!-- Link to a fixture under fixtures/platform-import-failures/ or fixtures/platform-support-tickets/. -->

## Redacted Log Excerpt

```text
status=needs_attention
diagnostic_code=<redacted diagnostic code>
source_text_redacted=<yes>
answer_redacted=<yes>
agent_endpoint=<redacted>
model_or_judge_secret=<redacted>
```

## Next Commands Tried

- 

## Expected Result

## Actual Result
"""


def ticket_payload(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": TICKET_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "ticket_id": category["id"],
        "status": "mock_ticket_ready",
        "platform_ids": list(PLATFORMS),
        "support_category": category["id"],
        "linked_import_failure_fixture": (
            f"fixtures/platform-import-failures/{category['fixture_id']}.json"
        ),
        "support_bundle": {
            "release_version": RELEASE_VERSION,
            "platform_id": "generic",
            "command_ran": category["minimum_command"],
            "diagnostic_code": category["diagnostic_codes"][0],
            "fixture_id": category["fixture_id"],
            "redacted_log_excerpt": (
                "status=needs_attention\n"
                f"diagnostic_code={category['diagnostic_codes'][0]}\n"
                "source_text_redacted=<yes>\n"
                "answer_redacted=<yes>\n"
                "agent_endpoint=<redacted>\n"
                "model_or_judge_secret=<redacted>\n"
            ),
            "next_commands_tried": [category["minimum_command"]],
        },
        "triage": {
            "first_response": "Ask for the redacted support bundle and exact platform import surface.",
            "reproduction": "Re-run the minimum command against the same adoption pack version.",
            "close_when": "The user can import tools or has a documented platform limitation workaround.",
            "escalate_when": "The fixture reproduces on main with a current release pack.",
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "real_model_keys_included": False,
            "agent_endpoint_secrets_included": False,
            "browser_video_private_context_included": False,
            "personal_profile_included": False,
            "automatic_upload": False,
        },
    }


def playbook_entry(quirk_id: str) -> dict[str, Any]:
    return {
        "failure_id": quirk_id,
        "first_response": (
            "Confirm release version, platform id, diagnostic code, fixture id, and redacted logs."
        ),
        "reproduction_steps": [
            "Run python3 scripts/generate_platform_field_rehearsal.py --check.",
            "Run python3 scripts/verify_platform_support_triage.py --check.",
            f"Open fixtures/platform-import-failures/{quirk_id}.json and match the diagnostic code.",
        ],
        "close_when": "The current adoption pack reproduces the documented workaround or the issue is fixed on main.",
        "escalate_when": "The failure reproduces with current generated assets and no user-private data is needed.",
    }


def build_report() -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Turn field adoption rehearsal failures into a GitHub-first support desk "
            "triage loop that is actionable for maintainers and safe for users."
        ),
        "support_bundle_contract": {
            "schema_version": "platform-support-bundle-v1",
            "required_fields": list(REQUIRED_SUPPORT_FIELDS),
            "automatic_upload": False,
            "safe_handoff_only": True,
        },
        "issue_templates": [
            {
                "category_id": category["id"],
                "path": f".github/ISSUE_TEMPLATE/{category['id']}.md",
                "schema_version": ISSUE_TEMPLATE_SCHEMA_VERSION,
                "minimum_command": category["minimum_command"],
            }
            for category in SUPPORT_CATEGORIES
        ],
        "support_ticket_fixtures": [
            {
                "ticket_id": category["id"],
                "path": f"fixtures/platform-support-tickets/{category['id']}.json",
                "schema_version": TICKET_SCHEMA_VERSION,
            }
            for category in SUPPORT_CATEGORIES
        ],
        "maintainer_playbook": [playbook_entry(quirk_id) for quirk_id in QUIRK_IDS],
        "linked_assets": {
            "field_rehearsal": "platform/generated/study-anything-platform-field-rehearsal.json",
            "feedback_package": "platform/generated/study-anything-platform-feedback-package.zip",
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
            "generate_command": "python3 scripts/generate_platform_support_triage.py --check",
            "verify_command": "python3 scripts/verify_platform_support_triage.py --check",
            "ticket_fixture_count": len(SUPPORT_CATEGORIES),
            "issue_template_count": len(SUPPORT_CATEGORIES),
            "playbook_entry_count": len(QUIRK_IDS),
        },
    }
    assert_no_leaks(report)
    return report


def build_outputs() -> dict[Path, str]:
    outputs = {OUTPUT_PATH: dump_json(build_report())}
    for category in SUPPORT_CATEGORIES:
        payload = ticket_payload(category)
        assert_no_leaks(payload)
        outputs[TICKET_DIR / f"{category['id']}.json"] = dump_json(payload)
        outputs[ISSUE_TEMPLATE_DIR / f"{category['id']}.md"] = issue_template(category)
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
        raise PlatformSupportTriageGenerationError(
            "Platform support triage assets are stale. Run "
            "`python3 scripts/generate_platform_support_triage.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform support triage assets are up to date")


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
        print(f"generate_platform_support_triage failed: {exc}", file=sys.stderr)
        sys.exit(1)
