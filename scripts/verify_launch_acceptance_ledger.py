#!/usr/bin/env python3
"""Generate and verify the public launch acceptance ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-launch-acceptance-ledger.json"
ECOSYSTEM_SUBMISSION = ROOT / "platform" / "ecosystem-submission.json"
ADOPTION_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.json"
COMMERCIAL_READINESS_SOURCE = ROOT / "apps" / "api" / "study_anything" / "core" / "commercial_readiness.py"
VERSION = "v0.3.30-alpha"
SCHEMA_VERSION = "launch-acceptance-ledger-v1"
EVIDENCE = "launch_acceptance_ledger.schema_version == launch-acceptance-ledger-v1"
MINIMUM_COMMAND = "python3 scripts/verify_launch_acceptance_ledger.py --check"
PRIVATE_NEEDLES = (
    "sk-proj-",
    "secret_access_key",
    "api_key",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private source text:",
    "Private answer:",
    "AGENT_ENDPOINT=http",
)
SOURCE_REPORTS: tuple[dict[str, Any], ...] = (
    {
        "report_id": "platform_handoff_checklist",
        "path": "platform/generated/study-anything-platform-handoff-checklist.json",
        "schema_version": "platform-handoff-checklist-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "external platform handoff",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "platform_onboarding_readiness",
        "path": "platform/generated/study-anything-platform-onboarding-readiness.json",
        "schema_version": "platform-onboarding-readiness-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "first adopter onboarding",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "public_support_status",
        "path": "platform/generated/study-anything-public-support-status.json",
        "schema_version": "public-support-status-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "public support and status",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "published_image_evidence",
        "path": "platform/generated/study-anything-published-image-evidence.json",
        "schema_version": "published-image-evidence-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "published image evidence",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "release_asset_adoption",
        "path": "platform/generated/study-anything-release-asset-adoption.json",
        "schema_version": "release-asset-adoption-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "release asset adoption",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "release_asset_bootstrap",
        "path": "platform/generated/study-anything-release-asset-bootstrap.json",
        "schema_version": "release-asset-bootstrap-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "release asset bootstrap",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "release_cleanroom_bootstrap",
        "path": "platform/generated/study-anything-release-cleanroom-bootstrap.json",
        "schema_version": "release-cleanroom-bootstrap-evidence-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "cleanroom bootstrap",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "platform_agent_release_replay",
        "path": "platform/generated/study-anything-platform-agent-replay.json",
        "schema_version": "platform-agent-release-replay-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "platform Agent release replay",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "adopter_evidence_archive",
        "path": "platform/generated/study-anything-adopter-evidence-archive.json",
        "schema_version": "adopter-evidence-archive-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "adopter evidence archive",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "deployment_hardening",
        "path": "platform/generated/study-anything-deployment-hardening.json",
        "schema_version": "deployment-hardening-verification-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "deployment recovery",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "platform_feedback_package",
        "path": "platform/generated/study-anything-platform-feedback-package.json",
        "schema_version": "platform-feedback-package-v1",
        "accepted_statuses": ("ready",),
        "launch_area": "redacted feedback escalation",
        "required_for_github_oss_launch": True,
    },
    {
        "report_id": "cognitive_loop_pack_extract_smoke",
        "path": "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json",
        "schema_version": "cognitive-loop-pack-extract-smoke-v1",
        "accepted_statuses": ("pass",),
        "launch_area": "zip-only platform adoption",
        "required_for_github_oss_launch": True,
    },
)


class LaunchAcceptanceLedgerError(RuntimeError):
    """Readable launch acceptance ledger verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LaunchAcceptanceLedgerError(f"Cannot read {relative_path(path)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LaunchAcceptanceLedgerError(f"{relative_path(path)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LaunchAcceptanceLedgerError(f"{relative_path(path)} must contain a JSON object.")
    return payload


def reject_private_text(payload: Any, *, label: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = serialized.lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if leaked:
        raise LaunchAcceptanceLedgerError(f"{label} contains private or secret-like text: {leaked}")


def status_from(payload: dict[str, Any]) -> str | None:
    status = payload.get("status")
    if isinstance(status, str):
        return status
    readiness = payload.get("readiness_status")
    if isinstance(readiness, str):
        return readiness
    return None


def verify_source_report(spec: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / str(spec["path"])
    payload = load_json(path)
    expected_schema = spec["schema_version"]
    if payload.get("schema_version") != expected_schema:
        raise LaunchAcceptanceLedgerError(
            f"{spec['report_id']} schema drifted: expected {expected_schema}, got {payload.get('schema_version')}"
        )
    if payload.get("version") is not None and payload.get("version") != VERSION:
        raise LaunchAcceptanceLedgerError(f"{spec['report_id']} version drifted.")
    status = status_from(payload)
    if status not in set(spec["accepted_statuses"]):
        raise LaunchAcceptanceLedgerError(
            f"{spec['report_id']} status {status!r} not in {list(spec['accepted_statuses'])}."
        )
    reject_private_text(payload, label=str(spec["path"]))
    return {
        "report_id": spec["report_id"],
        "path": spec["path"],
        "schema_version": expected_schema,
        "status": status,
        "launch_area": spec["launch_area"],
        "required_for_github_oss_launch": spec["required_for_github_oss_launch"],
    }


def commercial_row() -> dict[str, Any]:
    try:
        source = COMMERCIAL_READINESS_SOURCE.read_text(encoding="utf-8")
    except OSError as exc:
        raise LaunchAcceptanceLedgerError(f"Cannot read commercial readiness source: {exc}") from exc
    expected = {
        "github_oss_launch": "ready",
        "platform_agent_distribution": "ready",
        "self_host_alpha": "ready",
        "standalone_app": "not_in_launch_path",
        "hosted_paid_services": "not_ready",
    }
    for key, value in expected.items():
        if f'"{key}": "{value}"' not in source:
            raise LaunchAcceptanceLedgerError(f"Commercial readiness source missing {key}={value}.")
    for marker in (
        'COMMERCIAL_READINESS_SCHEMA_VERSION = "commercial-readiness-v1"',
        "real_model_keys_stored_by_study_anything",
        "hosted_account_required_for_local_core",
        "billing_required_for_local_core",
        "raw_source_text_in_readiness_report",
        "learner_answers_in_readiness_report",
        "agent_endpoints_in_readiness_report",
        "Study Anything-hosted model keys",
        "obsidian_inspired",
    ):
        if marker not in source:
            raise LaunchAcceptanceLedgerError(f"Commercial readiness source missing marker {marker}.")
    reject_private_text({"source": source}, label="commercial readiness source")
    return {
        "report_id": "commercial_readiness",
        "path": str(COMMERCIAL_READINESS_SOURCE.relative_to(ROOT)),
        "schema_version": "commercial-readiness-v1",
        "status": "architecture_ready_for_oss_platform_alpha",
        "launch_area": "commercial boundary",
        "launch_assessment": expected,
        "required_for_github_oss_launch": True,
    }


def verify_adoption_pack() -> dict[str, Any]:
    manifest = load_json(ADOPTION_PACK)
    if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
        raise LaunchAcceptanceLedgerError("Adoption pack schema drifted.")
    if manifest.get("version") != VERSION:
        raise LaunchAcceptanceLedgerError("Adoption pack version drifted.")
    if manifest.get("no_frontend_required") is not True:
        raise LaunchAcceptanceLedgerError("Adoption pack must remain no-frontend required.")
    if manifest.get("real_model_keys_stored_by_study_anything") is not False:
        raise LaunchAcceptanceLedgerError("Study Anything must not store real model keys.")
    required_tools = set(manifest.get("required_tool_names") or manifest.get("required_tools_present") or [])
    for tool in (
        "study_anything_deployment_guide",
        "study_anything_commercial_readiness",
        "study_anything_pmf_readiness",
        "study_anything_agent_eval_report",
        "study_anything_learning_package_export",
    ):
        if tool not in required_tools:
            raise LaunchAcceptanceLedgerError(f"Adoption pack missing required platform tool {tool}.")
    reject_private_text(manifest, label="adoption pack manifest")
    return {
        "report_id": "platform_adoption_pack",
        "path": str(ADOPTION_PACK.relative_to(ROOT)),
        "schema_version": manifest["schema_version"],
        "status": "ready",
        "file_count": manifest.get("file_count"),
        "tool_count": manifest.get("tool_count"),
        "supported_platforms": manifest.get("supported_platforms"),
        "no_frontend_required": True,
        "real_model_keys_stored_by_study_anything": False,
        "required_for_github_oss_launch": True,
    }


def verify_ecosystem_submission() -> dict[str, Any]:
    submission = load_json(ECOSYSTEM_SUBMISSION)
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise LaunchAcceptanceLedgerError("Ecosystem submission schema drifted.")
    if submission.get("version") != VERSION:
        raise LaunchAcceptanceLedgerError("Ecosystem submission version drifted.")
    acceptance = submission.get("acceptance") or {}
    commands = set(str(item) for item in acceptance.get("minimum_commands", []))
    if MINIMUM_COMMAND not in commands:
        raise LaunchAcceptanceLedgerError("Ecosystem submission must include the launch acceptance ledger command.")
    must_prove = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    if "launch-acceptance-ledger-v1" not in must_prove:
        raise LaunchAcceptanceLedgerError("Ecosystem submission must prove launch-acceptance-ledger-v1.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    for asset in (
        "platform/generated/study-anything-launch-acceptance-ledger.json",
        "scripts/verify_launch_acceptance_ledger.py",
    ):
        if asset not in shared_assets:
            raise LaunchAcceptanceLedgerError(f"Ecosystem submission missing shared asset {asset}.")
    platforms = submission.get("submissions") or submission.get("platforms")
    if not isinstance(platforms, list) or len(platforms) < 4:
        raise LaunchAcceptanceLedgerError("Ecosystem submission must include platform rows.")
    for row in platforms:
        if not isinstance(row, dict):
            raise LaunchAcceptanceLedgerError("Ecosystem platform rows must be objects.")
        import_assets = set(str(item) for item in row.get("import_assets", []))
        commands = "\n".join(str(item) for item in row.get("local_verification_commands", []))
        if "platform/generated/study-anything-launch-acceptance-ledger.json" not in import_assets:
            raise LaunchAcceptanceLedgerError(f"{row.get('platform_id')} missing launch ledger import asset.")
        if "scripts/verify_launch_acceptance_ledger.py" not in import_assets:
            raise LaunchAcceptanceLedgerError(f"{row.get('platform_id')} missing launch ledger verifier asset.")
        if "verify_launch_acceptance_ledger.py --check" not in commands:
            raise LaunchAcceptanceLedgerError(f"{row.get('platform_id')} missing launch ledger verification command.")
    reject_private_text(submission, label="ecosystem submission")
    return {
        "report_id": "ecosystem_submission",
        "path": str(ECOSYSTEM_SUBMISSION.relative_to(ROOT)),
        "schema_version": submission["schema_version"],
        "status": "ready",
        "platform_count": len(platforms),
        "required_for_github_oss_launch": True,
    }


def build_report() -> dict[str, Any]:
    source_rows = [commercial_row(), verify_adoption_pack(), verify_ecosystem_submission()]
    source_rows.extend(verify_source_report(spec) for spec in SOURCE_REPORTS)
    source_by_id = {row["report_id"]: row for row in source_rows}
    missing = {spec["report_id"] for spec in SOURCE_REPORTS} - set(source_by_id)
    if missing:
        raise LaunchAcceptanceLedgerError(f"Launch ledger missing source rows: {sorted(missing)}")
    status = "pass" if all(row["required_for_github_oss_launch"] for row in source_rows) else "partial"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "version": VERSION,
        "purpose": (
            "One machine-readable launch acceptance ledger for GitHub OSS and platform-Agent adoption. "
            "It aggregates existing evidence without adding a standalone frontend or model-key custody."
        ),
        "launch_assessment": {
            "github_oss_launch": "ready",
            "platform_agent_distribution": "ready",
            "self_host_alpha": "ready",
            "skill_mode": "ready",
            "published_image_path": "ready_with_public_evidence_and_timeout_fallback",
            "standalone_frontend": "not_in_launch_path",
            "hosted_paid_services": "not_ready_before_pmf",
        },
        "current_launch_path": [
            "GitHub OSS repository",
            "Skill Mode local API",
            "Docker/source self-host path",
            "platform-Agent adoption pack for Codex, Kimi, WorkBuddy, and generic OpenAPI hosts",
            "user-owned external Agent gateway for real model/tool work",
        ],
        "not_current_launch_path": [
            "standalone web app sale",
            "hosted Sync/Publish/Teams billing",
            "Study Anything-hosted model keys",
            "automatic private data upload",
            "browser/video/private app context capture by Study Anything",
        ],
        "source_reports": sorted(source_rows, key=lambda row: row["report_id"]),
        "release_gate": {
            "local_gate": "./scripts/release_check.sh",
            "minimum_command": MINIMUM_COMMAND,
            "expected_ci_checks": ["api-tests", "compose-smoke"],
            "manual_acceptance": [
                "Open the draft PR and confirm both GitHub checks pass.",
                "Verify the adoption pack archive is attached or reproducible from the generated manifest.",
                "Publish only redacted support/status evidence.",
            ],
        },
        "commercial_boundary": {
            "sell_now": "nothing packaged as a paid app",
            "prepare_for_later": [
                "hosted encrypted sync",
                "team workspaces",
                "trusted plugin ecosystem",
                "professional support and operational convenience",
            ],
            "pmf_required_before": [
                "hosted subscriptions",
                "managed teams",
                "marketplace payments",
                "enterprise SSO",
            ],
        },
        "privacy_assertions": {
            "real_model_keys_stored_by_study_anything": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "browser_video_private_context_in_report": False,
            "automatic_upload": False,
            "standalone_frontend_required": False,
            "report_is_redacted": True,
        },
        "acceptance": {
            "evidence": EVIDENCE,
            "minimum_command": MINIMUM_COMMAND,
            "blocks_release_check": True,
        },
    }
    reject_private_text(report, label="launch acceptance ledger")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail when the generated ledger is stale.")
    parser.add_argument("--write", action="store_true", help="Write the generated ledger.")
    args = parser.parse_args()
    if args.check and args.write:
        raise LaunchAcceptanceLedgerError("Use only one of --check or --write.")

    report = build_report()
    rendered = dump_json(report)
    if args.write:
        REPORT.write_text(rendered, encoding="utf-8")
    elif args.check:
        try:
            existing = REPORT.read_text(encoding="utf-8")
        except OSError as exc:
            raise LaunchAcceptanceLedgerError(f"Cannot read {relative_path(REPORT)}: {exc}") from exc
        if existing != rendered:
            raise LaunchAcceptanceLedgerError(
                f"{relative_path(REPORT)} is stale. Run python3 scripts/verify_launch_acceptance_ledger.py --write."
            )
    else:
        print(rendered, end="")
        return

    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "status": report["status"],
                "version": VERSION,
                "source_report_count": len(report["source_reports"]),
                "github_oss_launch": report["launch_assessment"]["github_oss_launch"],
                "platform_agent_distribution": report["launch_assessment"]["platform_agent_distribution"],
                "hosted_paid_services": report["launch_assessment"]["hosted_paid_services"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_launch_acceptance_ledger failed: {exc}", file=sys.stderr)
        sys.exit(1)
