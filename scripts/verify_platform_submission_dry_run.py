#!/usr/bin/env python3
"""Verify external platform submission dry-run readiness."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from verify_platform_operator_drill import (
    DEFAULT_PACK,
    assert_redacted,
    build_transcript,
    dump_json,
    resolve_pack_root,
    validate_platform,
    validate_tool_import_assets,
)
from generate_platform_adoption_pack import ARCHIVE_PATH, PACK_FILES


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "platform-submission-dry-run-v1"
RELEASE_VERSION = "v0.3.23-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-platform-submission-dry-run.json"
PUBLIC_SUPPORT_ASSETS = [
    "scripts/generate_platform_public_support_status.py",
    "scripts/verify_platform_public_support_status.py",
    "platform/generated/study-anything-public-support-status.json",
    "platform/generated/study-anything-public-maintainer-dashboard.json",
    "platform/generated/study-anything-public-maintainer-dashboard.md",
    "docs/public-support-status.md",
    "fixtures/platform-status-links/intake.json",
    "fixtures/platform-status-links/needs-repro.json",
    "fixtures/platform-status-links/confirmed.json",
    "fixtures/platform-status-links/blocked-by-platform.json",
    "fixtures/platform-status-links/docs-fix.json",
    "fixtures/platform-status-links/release-blocker.json",
    "fixtures/platform-status-links/resolved.json",
]
PUBLIC_SUPPORT_COMMANDS = [
    "generate_platform_public_support_status.py",
    "verify_platform_public_support_status.py",
]

PLATFORM_PROFILES: dict[str, dict[str, Any]] = {
    "kimi-compatible": {
        "pack_id": "kimi",
        "display": "Kimi-compatible Tool Workspace",
        "expected_mode": "openai_compatible_tools",
        "required_assets": [
            "platform/generated/study-anything-openai-tools.json",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
            "scripts/openai_compatible_agent_gateway.py",
            "docs/use-with-kimi.md",
            "docs/plugins.md",
            "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
            "platform/generated/study-anything-deployment-hardening.json",
            "platform/generated/study-anything-learning-enrichment-bridge.json",
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            "platform/generated/study-anything-platform-feedback-package.json",
            "platform/generated/study-anything-platform-field-rehearsal.json",
            "platform/generated/study-anything-platform-support-triage.json",
            "platform/generated/study-anything-platform-onboarding-readiness.json",
            "platform/generated/study-anything-platform-triage-dashboard.json",
            "platform/packs/kimi/README.md",
            "platform/packs/kimi/pack.json",
        ],
        "required_commands": [
            "verify_platform_submission_dry_run.py",
            "verify_platform_manual_submission_rehearsal.py",
            "verify_first_lesson_authoring_kit.py",
            "verify_external_eval_marketplace_harness.py",
            "verify_agent_eval_marketplace_enforcement.py",
            "verify_platform_adoption_feedback_diagnostics.py",
            "generate_platform_feedback_package.py",
            "generate_platform_field_rehearsal.py",
            "verify_platform_field_rehearsal.py",
            "generate_platform_support_triage.py",
            "verify_platform_support_triage.py",
            "generate_platform_onboarding_readiness.py",
            "verify_platform_onboarding_readiness.py",
            "verify_plugin_ecosystem_adoption_kit.py",
            "verify_deployment_hardening.py",
            "verify_learning_enrichment_bridge.py",
            "verify_openai_compatible_gateway.py --gateway-only",
            "verify_external_adoption.py",
        ],
        "manual_steps": [
            "Import OpenAI-compatible tools or OpenAPI assets into the Kimi-compatible workspace.",
            "Start the user-owned local/private Agent gateway outside Study Anything.",
            "Register Study Anything tools against the local API endpoint.",
            "Run the adoption proof and keep only redacted JSON evidence.",
        ],
        "warnings": [
            "Browser-only chat surfaces may not be able to call localhost directly.",
            "Kimi or Moonshot credentials must stay in the user's gateway or platform environment.",
        ],
    },
    "codex-skill": {
        "pack_id": "codex",
        "display": "Codex Skill",
        "expected_mode": "terminal_skill",
        "required_assets": [
            "skills/study-anything/SKILL.md",
            "scripts/study_anything_cli.py",
            "scripts/run_skill_mode_demo.sh",
            "platform/generated/study-anything-tool-catalog.md",
            "docs/plugins.md",
            "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
            "platform/generated/study-anything-deployment-hardening.json",
            "platform/generated/study-anything-learning-enrichment-bridge.json",
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            "platform/generated/study-anything-platform-feedback-package.json",
            "platform/generated/study-anything-platform-field-rehearsal.json",
            "platform/generated/study-anything-platform-support-triage.json",
            "platform/generated/study-anything-platform-onboarding-readiness.json",
            "platform/generated/study-anything-platform-triage-dashboard.json",
            "platform/packs/codex/README.md",
            "platform/packs/codex/pack.json",
        ],
        "required_commands": [
            "verify_platform_submission_dry_run.py",
            "verify_platform_manual_submission_rehearsal.py",
            "verify_first_lesson_authoring_kit.py",
            "verify_external_eval_marketplace_harness.py",
            "verify_agent_eval_marketplace_enforcement.py",
            "verify_platform_adoption_feedback_diagnostics.py",
            "generate_platform_feedback_package.py",
            "generate_platform_field_rehearsal.py",
            "verify_platform_field_rehearsal.py",
            "generate_platform_support_triage.py",
            "verify_platform_support_triage.py",
            "generate_platform_onboarding_readiness.py",
            "verify_platform_onboarding_readiness.py",
            "verify_plugin_ecosystem_adoption_kit.py",
            "verify_deployment_hardening.py",
            "verify_learning_enrichment_bridge.py",
            "run_skill_mode_demo.sh",
            "verify_external_adoption.py",
        ],
        "manual_steps": [
            "Expose the repo-local Skill to a terminal-capable Codex workspace.",
            "Run Skill Mode locally or use the published API image.",
            "Run the deterministic demo and external adoption proof.",
            "Share the Skill entrypoint and redacted report, not raw learning content.",
        ],
        "warnings": [
            "Requires local checkout access and a terminal-capable Agent.",
        ],
    },
    "workbuddy-style-http": {
        "pack_id": "workbuddy",
        "display": "WorkBuddy-style HTTP Workspace",
        "expected_mode": "openapi_http_tools",
        "required_assets": [
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
            "docs/api.md",
            "docs/plugins.md",
            "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
            "platform/generated/study-anything-deployment-hardening.json",
            "platform/generated/study-anything-learning-enrichment-bridge.json",
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            "platform/generated/study-anything-platform-feedback-package.json",
            "platform/generated/study-anything-platform-field-rehearsal.json",
            "platform/generated/study-anything-platform-support-triage.json",
            "platform/generated/study-anything-platform-onboarding-readiness.json",
            "platform/generated/study-anything-platform-triage-dashboard.json",
            "platform/packs/workbuddy/README.md",
            "platform/packs/workbuddy/pack.json",
        ],
        "required_commands": [
            "verify_platform_submission_dry_run.py",
            "verify_platform_manual_submission_rehearsal.py",
            "verify_first_lesson_authoring_kit.py",
            "verify_external_eval_marketplace_harness.py",
            "verify_agent_eval_marketplace_enforcement.py",
            "verify_platform_adoption_feedback_diagnostics.py",
            "generate_platform_feedback_package.py",
            "generate_platform_field_rehearsal.py",
            "verify_platform_field_rehearsal.py",
            "generate_platform_support_triage.py",
            "verify_platform_support_triage.py",
            "generate_platform_onboarding_readiness.py",
            "verify_platform_onboarding_readiness.py",
            "verify_plugin_ecosystem_adoption_kit.py",
            "verify_deployment_hardening.py",
            "verify_learning_enrichment_bridge.py",
            "verify_platform_agent_tools.py",
            "verify_external_adoption.py",
        ],
        "manual_steps": [
            "Import the constrained OpenAPI asset into the HTTP tool workspace.",
            "Point the workspace at a local or private Study Anything API.",
            "Run platform tool and ecosystem eval checks.",
            "Confirm management endpoints remain absent from imported tools.",
        ],
        "warnings": [
            "The workspace must be allowed to call local or private HTTP endpoints.",
        ],
    },
    "generic-openapi-tools": {
        "pack_id": "workbuddy",
        "display": "Generic OpenAPI Tool Platform",
        "expected_mode": "generic_openapi_tools",
        "required_assets": [
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
            "docs/platform-agent-integrations.md",
            "platform/study-anything-platform-tools.json",
            "docs/plugins.md",
            "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
            "platform/generated/study-anything-deployment-hardening.json",
            "platform/generated/study-anything-learning-enrichment-bridge.json",
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            "platform/generated/study-anything-platform-feedback-package.json",
            "platform/generated/study-anything-platform-field-rehearsal.json",
            "platform/generated/study-anything-platform-support-triage.json",
            "platform/generated/study-anything-platform-onboarding-readiness.json",
            "platform/generated/study-anything-platform-triage-dashboard.json",
        ],
        "required_commands": [
            "verify_platform_submission_dry_run.py",
            "verify_platform_manual_submission_rehearsal.py",
            "verify_first_lesson_authoring_kit.py",
            "verify_external_eval_marketplace_harness.py",
            "verify_agent_eval_marketplace_enforcement.py",
            "verify_platform_adoption_feedback_diagnostics.py",
            "generate_platform_feedback_package.py",
            "generate_platform_field_rehearsal.py",
            "verify_platform_field_rehearsal.py",
            "generate_platform_support_triage.py",
            "verify_platform_support_triage.py",
            "generate_platform_onboarding_readiness.py",
            "verify_platform_onboarding_readiness.py",
            "verify_plugin_ecosystem_adoption_kit.py",
            "verify_deployment_hardening.py",
            "verify_learning_enrichment_bridge.py",
            "generate_platform_agent_assets.py --check",
            "verify_external_adoption.py",
        ],
        "manual_steps": [
            "Import the OpenAPI asset or map tools from the human-readable catalog.",
            "Verify imported tools map only to local learning endpoints.",
            "Run the external adoption proof from a clean checkout or adoption pack.",
            "Record host-platform import quirks as warnings, not code changes.",
        ],
        "warnings": [
            "OpenAPI import behavior differs by host platform.",
        ],
    },
}

FORBIDDEN_SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{12,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_./+=-]{12,}"),
]


class SubmissionDryRunError(RuntimeError):
    """Readable platform submission dry-run failure."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SubmissionDryRunError(f"Cannot read JSON {path}: {exc}") from exc


def asset_exists(pack_root: Path, relative_path: str) -> bool:
    target = (pack_root / relative_path).resolve()
    try:
        target.relative_to(pack_root.resolve())
    except ValueError:
        return False
    return target.is_file()


def validate_submission_manifest(submission: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise SubmissionDryRunError("ecosystem-submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise SubmissionDryRunError(
            f"ecosystem-submission version must be {RELEASE_VERSION}."
        )
    project = submission.get("project") or {}
    if project.get("standalone_frontend_required") is not False:
        raise SubmissionDryRunError("Submission must not require a standalone frontend.")
    if project.get("billing_required") is not False:
        raise SubmissionDryRunError("Submission must not require billing.")
    privacy = submission.get("privacy") or {}
    for key in (
        "real_model_keys_stored_by_study_anything",
        "agent_endpoints_in_submission",
        "raw_learning_data_in_submission",
        "management_endpoints_exposed_to_platform_tools",
    ):
        if privacy.get(key) is not False:
            raise SubmissionDryRunError(f"privacy.{key} must be false.")
    submissions = submission.get("submissions")
    if not isinstance(submissions, list):
        raise SubmissionDryRunError("Submission must include platform submissions.")
    by_id = {str(item.get("platform_id")): item for item in submissions if isinstance(item, dict)}
    missing = sorted(set(PLATFORM_PROFILES) - set(by_id))
    if missing:
        raise SubmissionDryRunError(f"Submission is missing platforms: {missing}")
    return by_id


def validate_no_secret_leaks(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    leaks = [pattern.pattern for pattern in FORBIDDEN_SECRET_PATTERNS if pattern.search(serialized)]
    for literal in (
        "Private answer:",
        "Private platform browser/video context",
        "learner@example.com",
    ):
        if literal in serialized:
            leaks.append(literal)
    if leaks:
        raise SubmissionDryRunError(f"Submission dry-run report leaked private data: {leaks}")
    assert_redacted(payload)


def platform_report(
    *,
    platform_id: str,
    profile: dict[str, Any],
    pack_root: Path,
    submission: dict[str, Any],
    transcript_platform: dict[str, Any],
    shared_assets: set[str],
) -> dict[str, Any]:
    required_assets = [str(item) for item in profile["required_assets"]] + PUBLIC_SUPPORT_ASSETS
    submission_entrypoints = submission.get("entrypoints") or {}
    import_assets = set(str(item) for item in submission.get("import_assets", []))
    pack_import_assets = set(str(item) for item in transcript_platform.get("import_assets", []))
    entrypoint_assets = set(str(item) for item in submission_entrypoints.values())
    missing_assets = [
        asset for asset in required_assets if not asset_exists(pack_root, asset)
    ]
    missing_references = [
        asset
        for asset in required_assets
        if asset not in import_assets
        and asset not in shared_assets
        and asset not in pack_import_assets
        and asset not in entrypoint_assets
        and asset
        not in {
            "docs/api.md",
            "docs/platform-agent-integrations.md",
            "docs/plugins.md",
            "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
            "platform/generated/study-anything-deployment-hardening.json",
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            "platform/generated/study-anything-platform-feedback-package.json",
            "platform/generated/study-anything-platform-field-rehearsal.json",
            "platform/generated/study-anything-platform-support-triage.json",
            "platform/generated/study-anything-platform-onboarding-readiness.json",
            "platform/generated/study-anything-platform-triage-dashboard.json",
        }
    ]

    commands = [
        str(command)
        for command in submission.get("verification_commands", [])
    ] + [
        str(command)
        for command in transcript_platform.get("local_verification_commands", [])
    ]
    command_text = "\n".join(commands)
    missing_commands = [
        fragment
        for fragment in list(profile["required_commands"]) + PUBLIC_SUPPORT_COMMANDS
        if fragment not in command_text
    ]

    integration_mode = submission.get("integration_mode")
    mode_ok = integration_mode == profile["expected_mode"]
    warnings = list(profile.get("warnings", [])) + [
        str(item) for item in submission.get("known_limits", [])
    ]
    warnings = sorted(set(warnings))
    blocked = missing_assets or missing_references or missing_commands or not mode_ok
    status = "blocked" if blocked else ("ready_with_warnings" if warnings else "ready")
    return {
        "platform_id": platform_id,
        "display": profile["display"],
        "status": status,
        "integration_mode": integration_mode,
        "expected_mode": profile["expected_mode"],
        "required_assets": required_assets,
        "missing_assets": sorted(set(missing_assets)),
        "missing_asset_references": sorted(set(missing_references)),
        "acceptance_commands": commands,
        "missing_acceptance_commands": missing_commands,
        "manual_submission_checklist": list(profile["manual_steps"]),
        "warnings": warnings,
        "privacy": {
            "no_frontend_required": submission.get("no_frontend_required") is True,
            "real_model_keys_stored_by_study_anything": False,
            "raw_learning_data_in_report": False,
            "agent_endpoint_secrets_in_report": False,
        },
    }


def build_report(pack_root: Path, pack_path: Path | None) -> dict[str, Any]:
    transcript = build_transcript_for_root(pack_root, pack_path)
    submission = read_json(pack_root / "platform" / "ecosystem-submission.json")
    by_id = validate_submission_manifest(submission)
    shared_assets = set(str(asset) for asset in submission.get("shared_assets", []))
    platforms: dict[str, Any] = {}
    for platform_id, profile in sorted(PLATFORM_PROFILES.items()):
        pack_id = str(profile["pack_id"])
        platforms[platform_id] = platform_report(
            platform_id=platform_id,
            profile=profile,
            pack_root=pack_root,
            submission=by_id[platform_id],
            transcript_platform=transcript["platforms"][pack_id],
            shared_assets=shared_assets,
        )
    blocked = [platform_id for platform_id, report in platforms.items() if report["status"] == "blocked"]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if blocked else "pass",
        "version": RELEASE_VERSION,
        "submission_schema": submission.get("schema_version"),
        "pack": {
            "schema_version": transcript["pack"]["schema_version"],
            "version": transcript["pack"]["version"],
            "archive_name": transcript["pack"]["archive_name"],
            "archive_sha256": None,
            "file_count": transcript["pack"]["file_count"],
            "no_frontend_required": transcript["pack"]["no_frontend_required"],
            "real_model_keys_stored_by_study_anything": transcript["pack"][
                "real_model_keys_stored_by_study_anything"
            ],
        },
        "platforms": platforms,
        "blocked_platforms": blocked,
        "manual_submission_order": [
            "codex-skill",
            "kimi-compatible",
            "workbuddy-style-http",
            "generic-openapi-tools",
        ],
        "privacy": {
            "real_model_keys_stored_by_study_anything": False,
            "agent_endpoint_secrets_in_report": False,
            "raw_learning_data_in_report": False,
            "management_endpoints_exposed_to_platform_tools": False,
            "report_is_redacted": True,
        },
        "acceptance": {
            "operator_drill_schema": transcript["schema_version"],
            "required_report_schema": SCHEMA_VERSION,
            "public_support_status_schema": "public-support-status-v1",
            "public_maintainer_dashboard_schema": "public-maintainer-dashboard-v1",
            "public_status_linkage_fixture_schema": "public-status-linkage-fixture-v1",
            "minimum_command": "python3 scripts/verify_platform_submission_dry_run.py --check",
        },
    }
    validate_no_secret_leaks(report)
    return report


def build_transcript_for_root(pack_root: Path, pack_path: Path | None) -> dict[str, Any]:
    if (pack_root / "manifest.json").exists():
        return build_transcript(pack_root, pack_path)

    tool_manifest = read_json(pack_root / "platform" / "study-anything-platform-tools.json")
    required_tools = [
        str(tool.get("name"))
        for tool in tool_manifest.get("tools", [])
        if isinstance(tool, dict) and tool.get("name")
    ]
    generated_assets = validate_tool_import_assets(pack_root, required_tools)
    platforms = {
        platform_id: validate_platform(pack_root, platform_id)
        for platform_id in ("codex", "kimi", "workbuddy")
    }
    return {
        "schema_version": "study-anything-operator-drill-v1",
        "status": "ok",
        "pack": {
            "schema_version": "study-anything-platform-adoption-pack-v1",
            "version": RELEASE_VERSION,
            "archive_name": ARCHIVE_PATH.name,
            "file_count": len(PACK_FILES),
            "no_frontend_required": True,
            "real_model_keys_stored_by_study_anything": False,
        },
        "generated_tool_assets": generated_assets,
        "platforms": platforms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=str(DEFAULT_PACK))
    parser.add_argument("--pack-root")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="study-anything-submission-dry-run-"))
    try:
        if args.pack_root and not (Path(args.pack_root).resolve() / "manifest.json").exists():
            pack_root = Path(args.pack_root).resolve()
            pack_path = None
        else:
            pack_root = resolve_pack_root(args, tmp_root)
            pack_path = None if args.pack_root else Path(args.pack).resolve()
        report = build_report(pack_root, pack_path)
        text = dump_json(report)
        output = Path(args.output)
        if args.check:
            if not output.exists():
                raise SubmissionDryRunError(f"Submission dry-run report missing: {output}")
            if output.read_text(encoding="utf-8") != text:
                raise SubmissionDryRunError(
                    "Submission dry-run report is stale. Run "
                    "`python3 scripts/verify_platform_submission_dry_run.py --write`."
                )
            print("ok    platform submission dry-run report is up to date")
            return
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
            print(f"wrote {output.relative_to(ROOT)}")
            return
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_submission_dry_run failed: {exc}", file=sys.stderr)
        sys.exit(1)
