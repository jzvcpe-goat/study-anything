#!/usr/bin/env python3
"""Generate public support status and maintainer dashboard assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "platform" / "generated" / "study-anything-public-support-status.json"
DASHBOARD_JSON_PATH = ROOT / "platform" / "generated" / "study-anything-public-maintainer-dashboard.json"
DASHBOARD_MD_PATH = ROOT / "platform" / "generated" / "study-anything-public-maintainer-dashboard.md"
STATUS_LINKAGE_DIR = ROOT / "fixtures" / "platform-status-links"

PUBLIC_STATUS_SCHEMA_VERSION = "public-support-status-v1"
PUBLIC_DASHBOARD_SCHEMA_VERSION = "public-maintainer-dashboard-v1"
STATUS_LINKAGE_SCHEMA_VERSION = "public-status-linkage-fixture-v1"
RELEASE_VERSION = "v0.3.21-alpha"
PLATFORMS = ("kimi", "codex", "workbuddy", "generic")
SLA_LABELS = (
    "intake",
    "needs-repro",
    "confirmed",
    "blocked-by-platform",
    "docs-fix",
    "release-blocker",
    "resolved",
)
RELEASE_BLOCKERS = (
    "tool_import_blocker",
    "local_gateway_blocker",
    "published_image_blocker",
    "agent_eval_blocker",
    "support_bundle_privacy_blocker",
)
PUBLIC_COMMANDS = (
    "python3 scripts/verify_platform_public_support_status.py --check",
    "python3 scripts/generate_platform_public_support_status.py --check",
    "python3 scripts/verify_platform_onboarding_readiness.py --check",
    "python3 scripts/verify_platform_support_triage.py --check",
)
PRIVATE_FIELDS_EXCLUDED = (
    "raw_source_text",
    "learner_answers",
    "agent_prompts",
    "real_agent_endpoints",
    "real_model_keys",
    "browser_video_app_private_context",
    "personal_profile_data",
    "full_support_bundle_payload",
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


class PublicSupportStatusGenerationError(RuntimeError):
    """Readable public support status generation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PublicSupportStatusGenerationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PublicSupportStatusGenerationError(f"JSON object expected: {path.relative_to(ROOT)}")
    return payload


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
        raise PublicSupportStatusGenerationError(f"Public support status leaked private data: {leaks}")


def safe_public_ref(path: Path) -> dict[str, str]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
    }


def platform_statuses() -> list[dict[str, Any]]:
    names = {
        "kimi": "Kimi-compatible workspace",
        "codex": "Codex Skill workspace",
        "workbuddy": "WorkBuddy-style HTTP workspace",
        "generic": "Generic OpenAPI/MCP-capable workspace",
    }
    return [
        {
            "platform_id": platform_id,
            "display_name": names[platform_id],
            "public_status": "supported_for_first_adopter",
            "last_verified_commands": [
                "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
                "python3 scripts/verify_platform_onboarding_readiness.py --check",
            ],
            "visible_limitations": [
                "Localhost access depends on the host platform.",
                "Real model credentials stay inside the user's own Agent or platform runtime.",
            ],
        }
        for platform_id in PLATFORMS
    ]


def public_blockers() -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for blocker_id in RELEASE_BLOCKERS:
        path = ROOT / "fixtures" / "platform-release-blockers" / f"{blocker_id}.json"
        payload = read_json(path)
        blockers.append(
            {
                "blocker_id": blocker_id,
                "linked_support_category": payload["linked_support_category"],
                "public_status": "mock_fixture_ready_no_open_blocker",
                "minimum_reproduction_command": payload["minimum_reproduction_command"],
                "required_labels": payload["required_labels"],
                "fixture_ref": safe_public_ref(path),
            }
        )
    return blockers


def status_linkage_payload(label: str) -> dict[str, Any]:
    status_by_label = {
        "intake": "new_issue_needs_support_bundle_completeness",
        "needs-repro": "waiting_for_fixture_backed_reproduction",
        "confirmed": "maintainer_reproduced_with_current_assets",
        "blocked-by-platform": "host_platform_limitation_documented",
        "docs-fix": "docs_or_copyable_command_fix_pending",
        "release-blocker": "supported_happy_path_currently_failing",
        "resolved": "closing_command_or_limitation_verified",
    }
    command_by_label = {
        "intake": "python3 scripts/verify_platform_support_triage.py --check",
        "needs-repro": "python3 scripts/verify_platform_field_rehearsal.py --check",
        "confirmed": "python3 scripts/verify_platform_onboarding_readiness.py --check",
        "blocked-by-platform": "python3 scripts/diagnose_adoption.py",
        "docs-fix": "python3 scripts/verify_platform_public_support_status.py --check",
        "release-blocker": "python3 scripts/verify_platform_public_support_status.py --check",
        "resolved": "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
    }
    return {
        "schema_version": STATUS_LINKAGE_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "label": label,
        "public_status": status_by_label[label],
        "public_fields": {
            "label": label,
            "status": status_by_label[label],
            "next_public_action": command_by_label[label],
            "verification_command": command_by_label[label],
            "linked_schema": PUBLIC_STATUS_SCHEMA_VERSION,
        },
        "private_fields_excluded": list(PRIVATE_FIELDS_EXCLUDED),
        "example_public_note": (
            f"`{label}` issues may publish label, status, command, and fixture references only."
        ),
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_prompts_included": False,
            "real_model_keys_included": False,
            "agent_endpoint_secrets_included": False,
            "browser_video_private_context_included": False,
            "personal_profile_data_included": False,
            "automatic_upload": False,
        },
    }


def status_linkage_refs() -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for label in SLA_LABELS:
        path = STATUS_LINKAGE_DIR / f"{label}.json"
        refs.append({"label": label, **safe_public_ref(path)})
    return refs


def build_public_status() -> dict[str, Any]:
    onboarding = read_json(
        ROOT / "platform" / "generated" / "study-anything-platform-onboarding-readiness.json"
    )
    triage = read_json(ROOT / "platform" / "generated" / "study-anything-platform-support-triage.json")
    dashboard = read_json(ROOT / "platform" / "generated" / "study-anything-platform-triage-dashboard.json")
    refs = [
        safe_public_ref(ROOT / "platform" / "generated" / "study-anything-platform-onboarding-readiness.json"),
        safe_public_ref(ROOT / "platform" / "generated" / "study-anything-platform-support-triage.json"),
        safe_public_ref(ROOT / "platform" / "generated" / "study-anything-platform-triage-dashboard.json"),
    ]
    report = {
        "schema_version": PUBLIC_STATUS_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Publish maintainer-readable support status without exposing support bundles, "
            "learning content, Agent secrets, or private platform context."
        ),
        "source_reports": {
            "onboarding_readiness_schema": onboarding.get("schema_version"),
            "support_triage_schema": triage.get("schema_version"),
            "triage_dashboard_schema": dashboard.get("schema_version"),
            "public_refs": refs,
        },
        "platform_statuses": platform_statuses(),
        "known_blockers": public_blockers(),
        "maintainer_sla": {
            "schema_version": "maintainer-sla-labels-v1",
            "labels": list(SLA_LABELS),
            "status_linkage_schema": STATUS_LINKAGE_SCHEMA_VERSION,
            "status_linkage_refs": status_linkage_refs(),
        },
        "maintainer_rotation": {
            "schema_version": "maintainer-rotation-checklist-v1",
            "public_rotation_checklist": [
                "Run the public support status verifier before publishing status.",
                "Publish only status labels, commands, schema names, and fixture hashes.",
                "Escalate release blockers only when a documented first-adopter path fails.",
                "Close public status items only with a verified command or documented platform limitation.",
            ],
        },
        "release_readiness": {
            "release_gate": "scripts/release_check.sh",
            "required_ci": ["main ci", "main docker-images", "tag docker-images"],
            "published_image_smoke": "python3 scripts/verify_published_image_launch.py --tag v0.3.21-alpha --pull-timeout-seconds 180 --allow-pull-timeout-report",
            "current_status": "ready_when_release_gates_pass",
        },
        "privacy_assertions": {
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_prompts_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "real_model_keys_in_report": False,
            "browser_video_private_context_in_report": False,
            "personal_profile_data_in_report": False,
            "support_bundle_private_fields_in_report": False,
            "automatic_upload": False,
        },
        "public_dashboard": {
            "schema_version": PUBLIC_DASHBOARD_SCHEMA_VERSION,
            "json_path": "platform/generated/study-anything-public-maintainer-dashboard.json",
            "markdown_path": "platform/generated/study-anything-public-maintainer-dashboard.md",
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_platform_public_support_status.py --check",
            "generate_command": "python3 scripts/generate_platform_public_support_status.py --check",
            "pack_command": "python3 scripts/verify_platform_public_support_status.py --pack platform/generated/study-anything-platform-adoption-pack.zip",
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def build_dashboard(report: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": PUBLIC_DASHBOARD_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "summary": {
            "platform_count": len(report["platform_statuses"]),
            "known_blocker_count": len(report["known_blockers"]),
            "sla_label_count": len(report["maintainer_sla"]["labels"]),
            "status_linkage_fixture_count": len(report["maintainer_sla"]["status_linkage_refs"]),
            "public_release_readiness": report["release_readiness"]["current_status"],
        },
        "platforms": report["platform_statuses"],
        "known_blockers": report["known_blockers"],
        "maintainer_labels": report["maintainer_sla"]["labels"],
        "last_verified_commands": list(PUBLIC_COMMANDS),
        "privacy": report["privacy_assertions"],
    }
    assert_no_leaks(payload)
    return payload


def dashboard_markdown(payload: dict[str, Any]) -> str:
    blocker_lines = "\n".join(
        f"- `{item['blocker_id']}` -> `{item['linked_support_category']}`: "
        f"`{item['minimum_reproduction_command']}`"
        for item in payload["known_blockers"]
    )
    platform_lines = "\n".join(
        f"- `{item['platform_id']}`: `{item['public_status']}`" for item in payload["platforms"]
    )
    label_lines = "\n".join(f"- `{label}`" for label in payload["maintainer_labels"])
    command_lines = "\n".join(f"- `{command}`" for command in payload["last_verified_commands"])
    return f"""# Study Anything Public Maintainer Dashboard

Schema: `{payload['schema_version']}`
Version: `{payload['version']}`
Status: `{payload['status']}`

## Platforms

{platform_lines}

## Known Blocker Fixtures

{blocker_lines}

## Maintainer Labels

{label_lines}

## Public Verification Commands

{command_lines}

## Privacy

This dashboard is generated from schema metadata, status labels, fixture hashes, and copyable
commands only. It must not include raw source text, learner answers, Agent prompts, real Agent
endpoints, model keys, personal profiles, or browser/video/app private context.
"""


def write_outputs() -> None:
    STATUS_LINKAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    for label in SLA_LABELS:
        payload = status_linkage_payload(label)
        assert_no_leaks(payload)
        (STATUS_LINKAGE_DIR / f"{label}.json").write_text(dump_json(payload), encoding="utf-8")
    report = build_public_status()
    dashboard = build_dashboard(report)
    OUTPUT_PATH.write_text(dump_json(report), encoding="utf-8")
    DASHBOARD_JSON_PATH.write_text(dump_json(dashboard), encoding="utf-8")
    DASHBOARD_MD_PATH.write_text(dashboard_markdown(dashboard), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"wrote {DASHBOARD_JSON_PATH.relative_to(ROOT)}")
    print(f"wrote {DASHBOARD_MD_PATH.relative_to(ROOT)}")
    print(f"wrote {STATUS_LINKAGE_DIR.relative_to(ROOT)}/*.json")


def check_outputs() -> None:
    missing: list[str] = []
    stale: list[str] = []
    expected_linkage = {
        STATUS_LINKAGE_DIR / f"{label}.json": dump_json(status_linkage_payload(label))
        for label in SLA_LABELS
    }
    for path, expected in expected_linkage.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
        elif path.read_text(encoding="utf-8") != expected:
            stale.append(str(path.relative_to(ROOT)))
    report = build_public_status()
    dashboard = build_dashboard(report)
    expected = {
        OUTPUT_PATH: dump_json(report),
        DASHBOARD_JSON_PATH: dump_json(dashboard),
        DASHBOARD_MD_PATH: dashboard_markdown(dashboard),
    }
    for path, text in expected.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
        elif path.read_text(encoding="utf-8") != text:
            stale.append(str(path.relative_to(ROOT)))
    if missing or stale:
        raise PublicSupportStatusGenerationError(
            "Platform public support status assets are stale. Run "
            "`python3 scripts/generate_platform_public_support_status.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform public support status assets are up to date")


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
        print(f"generate_platform_public_support_status failed: {exc}", file=sys.stderr)
        sys.exit(1)
