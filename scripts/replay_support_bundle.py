#!/usr/bin/env python3
"""Replay a redacted Study Anything support bundle for maintainer triage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from localhost_diagnostics import redact_diagnostic


SCHEMA_VERSION = "platform-support-bundle-replay-v1"
SUPPORT_BUNDLE_SCHEMA = "platform-support-bundle-v1"
CLEANROOM_SCHEMA = "release-cleanroom-bootstrap-v1"
DEFAULT_VERSION = "v0.3.29-alpha"

REQUIRED_FIELDS = (
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

REDACTION_KEYS = (
    "raw_source_text_included",
    "learner_answers_included",
    "agent_prompts_included",
    "agent_endpoint_secrets_included",
    "real_model_keys_included",
    "local_absolute_paths_included",
    "browser_video_private_context_included",
    "personal_profile_included",
    "automatic_upload",
)

FORBIDDEN_LITERALS = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "Private platform browser/video context",
    "raw_source_text=",
    "learner_answer=",
    "AGENT_ENDPOINT=http",
    "full_support_bundle_payload",
)

FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/private/var/folders/[^\s\"']+"),
    re.compile(r"/var/folders/[^\s\"']+"),
)


class SupportBundleReplayError(RuntimeError):
    """Readable support bundle replay failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SupportBundleReplayError(f"Cannot read support bundle JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SupportBundleReplayError("Support bundle must be a JSON object.")
    return payload


def sanitize_text(value: Any) -> str:
    return redact_diagnostic(str(value or ""))[:1200]


def assert_no_leaks(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise SupportBundleReplayError(f"Support bundle contains private data: {leaks}")


def cleanroom_to_support_bundle(report: dict[str, Any]) -> dict[str, Any]:
    runtime = report.get("runtime") if isinstance(report.get("runtime"), dict) else {}
    privacy = report.get("privacy") if isinstance(report.get("privacy"), dict) else {}
    release_assets = report.get("release_assets") if isinstance(report.get("release_assets"), dict) else {}
    tool_import = report.get("tool_import") if isinstance(report.get("tool_import"), dict) else {}
    classification = str(report.get("classification") or "cleanroom_bootstrap_failed")
    tag = str(report.get("tag") or DEFAULT_VERSION)
    replay_command = (
        "python3 scripts/replay_support_bundle.py "
        "--bundle support-bundle.json --issue-body"
    )
    next_steps = []
    recovery = report.get("recovery_plan")
    if isinstance(recovery, dict):
        steps = recovery.get(classification)
        if isinstance(steps, list):
            next_steps = [str(step) for step in steps]
    if not next_steps:
        next_steps = ["Ask the reporter for this redacted support bundle and rerun the matching verifier."]
    return {
        "schema_version": SUPPORT_BUNDLE_SCHEMA,
        "release_version": tag,
        "platform_id": str(report.get("platform") or "generic"),
        "runtime": str(runtime.get("requested") or "metadata-only"),
        "failure_class": classification,
        "workflow_stage": "cleanroom_bootstrap",
        "command_ran": (
            "python3 platform/bootstrap/study_anything_release_bootstrap.py "
            f"--tag {tag} --platform {report.get('platform') or 'generic'} "
            f"--runtime {runtime.get('requested') or 'metadata-only'}"
        ),
        "diagnostic_code": classification,
        "fixture_id": "release-cleanroom-report",
        "redacted_log_excerpt": sanitize_text(report.get("diagnostic")),
        "next_commands_tried": [
            "metadata-only bootloader",
            f"{runtime.get('requested') or 'metadata-only'} replay",
        ],
        "recommended_next_steps": next_steps,
        "replay_command": replay_command,
        "release_assets": {
            "tag": tag,
            "asset_count": release_assets.get("asset_count"),
            "github_digest_verified_count": release_assets.get("github_digest_verified_count"),
        },
        "tool_import_status": tool_import.get("status") or "unknown",
        "manifest_evidence": report.get("manifest_evidence") or {},
        "redaction_flags": {key: bool(privacy.get(key, False)) for key in REDACTION_KEYS},
    }


def normalize_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    schema = payload.get("schema_version")
    if schema == SUPPORT_BUNDLE_SCHEMA:
        return dict(payload)
    if schema == CLEANROOM_SCHEMA:
        return cleanroom_to_support_bundle(payload)
    if "api_image" in payload and "manifest_evidence" in payload:
        classification = str(payload.get("classification") or payload.get("status") or "needs_triage")
        return {
            "schema_version": SUPPORT_BUNDLE_SCHEMA,
            "release_version": str(payload.get("tag") or DEFAULT_VERSION),
            "platform_id": "generic",
            "runtime": "published-image",
            "failure_class": classification,
            "workflow_stage": "published_image_launch",
            "command_ran": (
                "python3 scripts/verify_published_image_launch.py "
                f"--tag {payload.get('tag') or DEFAULT_VERSION} --allow-pull-timeout-report"
            ),
            "diagnostic_code": classification,
            "fixture_id": "published-image-report",
            "redacted_log_excerpt": sanitize_text(payload.get("diagnostic")),
            "next_commands_tried": list(payload.get("next_steps") or []),
            "recommended_next_steps": list(payload.get("next_steps") or []),
            "replay_command": "python3 scripts/replay_support_bundle.py --bundle support-bundle.json",
            "manifest_evidence": payload.get("manifest_evidence") or {},
            "image_evidence": {"api_image": payload.get("api_image")},
            "redaction_flags": {key: False for key in REDACTION_KEYS},
        }
    raise SupportBundleReplayError(f"Unsupported support bundle schema: {schema!r}")


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    if bundle.get("schema_version") != SUPPORT_BUNDLE_SCHEMA:
        raise SupportBundleReplayError("Normalized bundle schema drifted.")
    missing = [field for field in REQUIRED_FIELDS if field not in bundle]
    if missing:
        raise SupportBundleReplayError(f"Support bundle missing required fields: {missing}")
    if not isinstance(bundle.get("next_commands_tried"), list):
        raise SupportBundleReplayError("Support bundle next_commands_tried must be a list.")
    if not isinstance(bundle.get("recommended_next_steps"), list):
        raise SupportBundleReplayError("Support bundle recommended_next_steps must be a list.")
    flags = bundle.get("redaction_flags")
    if not isinstance(flags, dict):
        raise SupportBundleReplayError("Support bundle redaction_flags must be an object.")
    leaking_flags = [key for key in REDACTION_KEYS if flags.get(key) is not False]
    if leaking_flags:
        return leaking_flags
    assert_no_leaks(bundle)
    return []


def classify_bundle(bundle: dict[str, Any], leaking_flags: list[str]) -> str:
    if leaking_flags:
        return "privacy_contract_violation"
    failure_class = str(bundle.get("failure_class") or "")
    diagnostic = str(bundle.get("diagnostic_code") or "")
    combined = f"{failure_class} {diagnostic}".lower()
    manifest = bundle.get("manifest_evidence") if isinstance(bundle.get("manifest_evidence"), dict) else {}
    manifest_status = str(manifest.get("status") or "").lower()
    platforms = set(manifest.get("platforms") or [])

    if failure_class in {"cleanroom_bootstrap_ready", "release_asset_bootstrap_ready"}:
        return "no_action_required"
    if "blocked_by_local_ghcr_pull" in combined or "local_pull_timeout" in combined:
        if manifest_status == "ok" and {"linux/amd64", "linux/arm64"}.issubset(platforms):
            return "local_ghcr_pull_timeout"
        return "published_image_manifest_unavailable"
    if "ghcr_manifest_unavailable" in combined or "manifest" in combined and "unavailable" in combined:
        return "published_image_manifest_unavailable"
    if "release_asset_missing" in combined:
        return "release_asset_missing"
    if "digest_mismatch" in combined:
        return "release_asset_digest_mismatch"
    if "pack_corrupted" in combined or "package_corruption" in combined:
        return "release_asset_pack_corrupted"
    if "api_unreachable" in combined or "local_api_unavailable" in combined:
        return "local_api_unreachable"
    if "agent_endpoint_unreachable" in combined:
        return "agent_endpoint_unreachable"
    if "agent_eval" in combined:
        return "agent_eval_evidence_missing"
    if "schema_mismatch" in combined:
        return "platform_import_schema_mismatch"
    if failure_class:
        return failure_class
    return "needs_triage"


def issue_body(bundle: dict[str, Any], classification: str) -> str:
    flags = bundle.get("redaction_flags") if isinstance(bundle.get("redaction_flags"), dict) else {}
    return "\n".join(
        [
            "## Study Anything support bundle replay",
            "",
            f"- release: `{bundle.get('release_version')}`",
            f"- platform: `{bundle.get('platform_id')}`",
            f"- runtime: `{bundle.get('runtime')}`",
            f"- workflow stage: `{bundle.get('workflow_stage')}`",
            f"- diagnostic code: `{bundle.get('diagnostic_code')}`",
            f"- replay classification: `{classification}`",
            "",
            "### Command Ran",
            "```sh",
            str(bundle.get("command_ran") or "").strip(),
            "```",
            "",
            "### Redacted Log Excerpt",
            "```text",
            sanitize_text(bundle.get("redacted_log_excerpt")),
            "```",
            "",
            "### Privacy Checklist",
            f"- raw source text included: {str(flags.get('raw_source_text_included') is True).lower()}",
            f"- learner answers included: {str(flags.get('learner_answers_included') is True).lower()}",
            f"- real model keys included: {str(flags.get('real_model_keys_included') is True).lower()}",
            f"- local absolute paths included: {str(flags.get('local_absolute_paths_included') is True).lower()}",
            "",
            "### Maintainer Replay",
            "```sh",
            str(bundle.get("replay_command") or "").strip(),
            "```",
        ]
    )


def build_replay(payload: dict[str, Any]) -> dict[str, Any]:
    bundle = normalize_bundle(payload)
    leaking_flags = validate_bundle(bundle)
    classification = classify_bundle(bundle, leaking_flags)
    status = "blocked" if classification == "privacy_contract_violation" else "pass"
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "bundle_schema_version": SUPPORT_BUNDLE_SCHEMA,
        "release_version": bundle.get("release_version"),
        "platform_id": bundle.get("platform_id"),
        "runtime": bundle.get("runtime"),
        "workflow_stage": bundle.get("workflow_stage"),
        "diagnostic_code": bundle.get("diagnostic_code"),
        "fixture_id": bundle.get("fixture_id"),
        "redaction": {
            "status": "blocked" if leaking_flags else "pass",
            "leaking_flags": leaking_flags,
        },
        "maintainer_action": maintainer_action(classification),
        "recommended_next_steps": bundle.get("recommended_next_steps"),
        "replay_command": bundle.get("replay_command"),
        "issue_body": issue_body(bundle, classification),
    }
    assert_no_leaks(result)
    return result


def maintainer_action(classification: str) -> str:
    actions = {
        "no_action_required": "Close as verified if the reporter confirms their release tag matches.",
        "local_ghcr_pull_timeout": "Mark as environment/network limited; ask for manifest evidence and suggest Skill Mode.",
        "published_image_manifest_unavailable": "Keep open as release blocker until GHCR manifest and docker-images workflow pass.",
        "release_asset_missing": "Block release claim and re-upload the missing public release assets.",
        "release_asset_digest_mismatch": "Recreate the affected release asset from the matching tag commit.",
        "release_asset_pack_corrupted": "Regenerate the adoption pack and ask the reporter to retry.",
        "local_api_unreachable": "Ask the reporter to run Skill Mode or self-host launch, then rerun diagnostics.",
        "agent_endpoint_unreachable": "Keep Study Anything issue focused on gateway contract; user-owned Agent secrets stay external.",
        "agent_eval_evidence_missing": "Ask for redacted Agent audit/eval artifact output and rerun eval verifiers.",
        "platform_import_schema_mismatch": "Reproduce against the current adoption pack and update platform import docs or tools.",
        "privacy_contract_violation": "Do not process publicly; ask the reporter to regenerate a redacted bundle.",
    }
    return actions.get(classification, "Triage with the linked fixture and ask only for missing redacted fields.")


def format_replay_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"replay_support_bundle failed: {diagnostic}",
            "Supported inputs:",
            "- platform-support-bundle-v1 JSON from Study Anything diagnostics",
            "- release-cleanroom-bootstrap-v1 JSON from the cleanroom bootstrap",
            "- published-image pull-timeout reports with manifest_evidence",
            "Next steps:",
            "1. Regenerate a redacted diagnostic report: python3 scripts/diagnose_adoption.py",
            "2. Re-run a known fixture: python3 scripts/replay_support_bundle.py --bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json",
            "3. Do not paste raw source text, learner answers, Agent endpoints, model keys, browser context, or local absolute paths into public issues.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, help="Path to platform-support-bundle-v1 JSON or compatible report.")
    parser.add_argument("--issue-body", action="store_true", help="Print copyable issue body after JSON.")
    parser.add_argument("--expect-classification")
    args = parser.parse_args()

    payload = read_json(Path(args.bundle))
    replay = build_replay(payload)
    if args.expect_classification and replay["classification"] != args.expect_classification:
        raise SupportBundleReplayError(
            f"Expected classification {args.expect_classification}, got {replay['classification']}"
        )
    print(dump_json(replay), end="")
    if args.issue_body:
        print("\n--- issue-body ---")
        print(replay["issue_body"])
    if replay["status"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(format_replay_failure(exc), file=sys.stderr)
        sys.exit(1)
