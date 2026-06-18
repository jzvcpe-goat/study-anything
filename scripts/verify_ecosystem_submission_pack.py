#!/usr/bin/env python3
"""Verify the ecosystem submission pack for external platform handoff."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_PATH = ROOT / "platform" / "ecosystem-submission.json"
TOOL_MANIFEST_PATH = ROOT / "platform" / "study-anything-platform-tools.json"
PACKS_DIR = ROOT / "platform" / "packs"
OPENAPI_PATH = ROOT / "platform" / "generated" / "study-anything-platform-openapi.json"
OPENAI_TOOLS_PATH = ROOT / "platform" / "generated" / "study-anything-openai-tools.json"
ADOPTION_PACK_PATH = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.json"
COGNITIVE_LOOP_CLI_ARTIFACT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-cli-artifact.json"
)
COGNITIVE_LOOP_RUN_ONCE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-run-once-evidence.json"
)
COGNITIVE_LOOP_SNAPSHOT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-project-snapshot.json"
)
COGNITIVE_LOOP_HUMAN_GATE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-human-gate.json"
)
COGNITIVE_LOOP_EVIDENCE_BUNDLE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-evidence-bundle.json"
)
COGNITIVE_LOOP_EVENT_INDEX_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-event-index.json"
)
COGNITIVE_LOOP_ARTIFACT_DOCTOR_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-artifact-doctor.json"
)
COGNITIVE_LOOP_REPAIR_PLAN_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-repair-plan.json"
)
COGNITIVE_LOOP_ARTIFACT_INDEX_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-artifact-index.json"
)
COGNITIVE_LOOP_ADOPTION_COOKBOOK_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-adoption-cookbook.json"
)
COGNITIVE_LOOP_ADOPTION_RECIPES_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-adoption-recipes.json"
)
COGNITIVE_LOOP_RECIPE_REPLAY_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-replay.json"
)
COGNITIVE_LOOP_SKILL_ENTRYPOINT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-skill-entrypoint.json"
)
COGNITIVE_LOOP_RECIPE_CLI_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli.json"
)
COGNITIVE_LOOP_RECIPE_CLI_RECEIPTS_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-receipts.json"
)
COGNITIVE_LOOP_RECIPE_CLI_FAILURES_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-failures.json"
)
COGNITIVE_LOOP_RECIPE_CLI_SCHEMAS_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-recipe-cli-schemas.json"
)
COGNITIVE_LOOP_RECIPE_CLI_SCHEMA_NEGATIVE_FIXTURES_PATH = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json"
)
COGNITIVE_LOOP_SCHEMA_PACK_CONSUMER_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cognitive-loop-schema-pack-consumer.json"
)
SUBMISSION_DRY_RUN_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-submission-dry-run.json"
)
MANUAL_REHEARSAL_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-manual-submission-rehearsal.json"
)
FIRST_LESSON_KIT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-first-lesson-authoring-kit.json"
)
EXTERNAL_EVAL_HARNESS_PATH = (
    ROOT / "platform" / "generated" / "study-anything-external-eval-harness.json"
)
AGENT_EVAL_MARKETPLACE_ENFORCEMENT_PATH = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-agent-eval-marketplace-enforcement.json"
)
PLATFORM_ADOPTION_FEEDBACK_DIAGNOSTICS_PATH = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-platform-adoption-feedback-diagnostics.json"
)
PLATFORM_FEEDBACK_PACKAGE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-feedback-package.json"
)
PLATFORM_FEEDBACK_PACKAGE_ARCHIVE = (
    ROOT / "platform" / "generated" / "study-anything-platform-feedback-package.zip"
)
PLATFORM_FIELD_REHEARSAL_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-field-rehearsal.json"
)
PLATFORM_SUPPORT_TRIAGE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-support-triage.json"
)
PLATFORM_ONBOARDING_READINESS_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-onboarding-readiness.json"
)
PLATFORM_TRIAGE_DASHBOARD_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-triage-dashboard.json"
)
PLUGIN_ECOSYSTEM_KIT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-plugin-ecosystem-adoption-kit.json"
)
DEPLOYMENT_HARDENING_PATH = (
    ROOT / "platform" / "generated" / "study-anything-deployment-hardening.json"
)
LEARNING_ENRICHMENT_BRIDGE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-learning-enrichment-bridge.json"
)
PUBLIC_SUPPORT_STATUS_PATH = (
    ROOT / "platform" / "generated" / "study-anything-public-support-status.json"
)
PUBLIC_MAINTAINER_DASHBOARD_PATH = (
    ROOT / "platform" / "generated" / "study-anything-public-maintainer-dashboard.json"
)
PUBLISHED_IMAGE_EVIDENCE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-published-image-evidence.json"
)
RELEASE_ASSET_ADOPTION_PATH = (
    ROOT / "platform" / "generated" / "study-anything-release-asset-adoption.json"
)
RELEASE_ASSET_BOOTSTRAP_PATH = (
    ROOT / "platform" / "generated" / "study-anything-release-asset-bootstrap.json"
)
RELEASE_CLEANROOM_BOOTSTRAP_PATH = (
    ROOT / "platform" / "generated" / "study-anything-release-cleanroom-bootstrap.json"
)
PLATFORM_AGENT_REPLAY_PATH = (
    ROOT / "platform" / "generated" / "study-anything-platform-agent-replay.json"
)
ADOPTER_EVIDENCE_ARCHIVE_PATH = (
    ROOT / "platform" / "generated" / "study-anything-adopter-evidence-archive.json"
)
COMMERCIAL_DOC = ROOT / "docs" / "commercial-readiness.md"

REQUIRED_PLATFORMS = {
    "kimi-compatible",
    "codex-skill",
    "workbuddy-style-http",
    "generic-openapi-tools",
}
REQUIRED_SHARED_ASSETS = {
    "platform/study-anything-platform-tools.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/generated/study-anything-tool-catalog.md",
    "platform/generated/study-anything-operator-drill-transcript.json",
    "docs/ecosystem-submission.md",
    "docs/release-checklist.md",
    "docs/roadmap.md",
    "docs/platform-agent-integrations.md",
    "docs/cognitive-loop-adoption-cookbook.md",
    "docs/use-with-kimi.md",
    "docs/commercial-readiness.md",
    "docs/security.md",
    "docs/adoption.md",
    "docs/adoption-telemetry.md",
    "docs/learning-enrichment.md",
    "docs/notebooklm-bridge.md",
    "docs/second-brain-handoff.md",
    "docs/agent-eval.md",
    "docs/eval-frameworks.md",
    "docs/cognitive-loop-contracts.md",
    ".cognitive-loop/config.yaml",
    ".cognitive-loop/permissions.yaml",
    ".cognitive-loop/evals.yaml",
    ".cognitive-loop/risk.yaml",
    "scripts/verify_cognitive_loop_contracts.py",
    "scripts/cognitive_loop_cli.py",
    "scripts/verify_cognitive_loop_cli.py",
    "scripts/verify_cognitive_loop_run_once.py",
    "scripts/verify_cognitive_loop_snapshot.py",
    "scripts/verify_cognitive_loop_human_gate.py",
    "scripts/verify_cognitive_loop_evidence_bundle.py",
    "scripts/verify_cognitive_loop_event_index.py",
    "scripts/verify_cognitive_loop_artifact_doctor.py",
    "scripts/verify_cognitive_loop_repair_plan.py",
    "scripts/verify_cognitive_loop_artifact_index.py",
    "scripts/verify_cognitive_loop_adoption_cookbook.py",
    "scripts/generate_cognitive_loop_adoption_recipes.py",
    "scripts/verify_cognitive_loop_recipe_replay.py",
    "scripts/verify_cognitive_loop_skill_entrypoint.py",
    "scripts/cognitive_loop_recipe_cli.py",
    "scripts/verify_cognitive_loop_recipe_cli.py",
    "scripts/verify_cognitive_loop_recipe_cli_receipts.py",
    "scripts/verify_cognitive_loop_recipe_cli_failures.py",
    "scripts/verify_cognitive_loop_recipe_cli_schemas.py",
    "scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py",
    "scripts/verify_cognitive_loop_schema_pack_consumer.py",
    "platform/generated/study-anything-cognitive-loop-contracts.json",
    "platform/generated/study-anything-cognitive-loop-cli-artifact.json",
    "platform/generated/study-anything-cognitive-loop-run-once-evidence.json",
    "platform/generated/study-anything-cognitive-loop-project-snapshot.json",
    "platform/generated/study-anything-cognitive-loop-human-gate.json",
    "platform/generated/study-anything-cognitive-loop-evidence-bundle.json",
    "platform/generated/study-anything-cognitive-loop-event-index.json",
    "platform/generated/study-anything-cognitive-loop-artifact-doctor.json",
    "platform/generated/study-anything-cognitive-loop-repair-plan.json",
    "platform/generated/study-anything-cognitive-loop-artifact-index.json",
    "platform/generated/study-anything-cognitive-loop-adoption-cookbook.json",
    "platform/generated/study-anything-cognitive-loop-adoption-recipes.json",
    "platform/generated/study-anything-cognitive-loop-recipe-replay.json",
    "platform/generated/study-anything-cognitive-loop-skill-entrypoint.json",
    "platform/generated/study-anything-cognitive-loop-recipe-cli.json",
    "platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json",
    "platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json",
    "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json",
    "platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json",
    "platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json",
    "scripts/verify_adoption_telemetry.py",
    "scripts/verify_agent_gateway_hardening.py",
    "scripts/verify_external_agent_adapter_hardening.py",
    "scripts/verify_notebooklm_obsidian_bridge_hardening.py",
    "scripts/verify_learning_enrichment_bridge.py",
    "scripts/verify_plugin_quarantine.py",
    "scripts/verify_security_recovery_hardening.py",
    "scripts/verify_platform_submission_dry_run.py",
    "scripts/verify_platform_manual_submission_rehearsal.py",
    "scripts/verify_first_lesson_authoring_kit.py",
    "scripts/verify_external_eval_marketplace_harness.py",
    "scripts/verify_agent_eval_marketplace_enforcement.py",
    "scripts/verify_platform_adoption_feedback_diagnostics.py",
    "scripts/generate_platform_feedback_package.py",
    "scripts/generate_platform_field_rehearsal.py",
    "scripts/verify_platform_field_rehearsal.py",
    "scripts/generate_platform_support_triage.py",
    "scripts/verify_platform_support_triage.py",
    "scripts/generate_platform_onboarding_readiness.py",
    "scripts/verify_platform_onboarding_readiness.py",
    "scripts/generate_platform_public_support_status.py",
    "scripts/verify_platform_public_support_status.py",
    "scripts/verify_plugin_ecosystem_adoption_kit.py",
    "scripts/verify_deployment_hardening.py",
    "scripts/install_local_plugin.py",
    "platform/generated/study-anything-platform-submission-dry-run.json",
    "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
    "platform/generated/study-anything-first-lesson-authoring-kit.json",
    "platform/generated/study-anything-external-eval-harness.json",
    "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
    "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
    "platform/generated/study-anything-platform-feedback-package.json",
    "platform/generated/study-anything-platform-feedback-package.zip",
    "platform/generated/study-anything-platform-field-rehearsal.json",
    "platform/generated/study-anything-platform-support-triage.json",
    "platform/generated/study-anything-platform-onboarding-readiness.json",
    "platform/generated/study-anything-platform-triage-dashboard.json",
    "platform/generated/study-anything-platform-triage-dashboard.md",
    "platform/generated/study-anything-public-support-status.json",
    "platform/generated/study-anything-public-maintainer-dashboard.json",
    "platform/generated/study-anything-public-maintainer-dashboard.md",
    "scripts/generate_published_image_evidence.py",
    "scripts/verify_published_image_evidence.py",
    "platform/generated/study-anything-published-image-evidence.json",
    "platform/generated/study-anything-published-image-evidence.md",
    "platform/generated/study-anything-published-image-evidence.zip",
    "platform/generated/study-anything-published-image-evidence.sha256",
    "docs/published-image-evidence.md",
    "scripts/generate_release_asset_adoption.py",
    "scripts/verify_release_asset_adoption.py",
    "platform/generated/study-anything-release-asset-adoption.json",
    "platform/generated/study-anything-release-asset-adoption.md",
    "platform/generated/study-anything-release-asset-adoption.zip",
    "platform/generated/study-anything-release-asset-adoption.sha256",
    "docs/release-asset-adoption.md",
    "scripts/bootstrap_from_release.py",
    "scripts/generate_release_asset_bootstrap.py",
    "platform/generated/study-anything-release-asset-bootstrap.json",
    "platform/generated/study-anything-release-asset-bootstrap.md",
    "platform/generated/study-anything-release-asset-bootstrap.zip",
    "platform/generated/study-anything-release-asset-bootstrap.sha256",
    "docs/release-asset-bootstrap.md",
    "platform/bootstrap/study_anything_release_bootstrap.py",
    "scripts/generate_release_cleanroom_bootstrap.py",
    "platform/generated/study-anything-release-cleanroom-bootstrap.json",
    "platform/generated/study-anything-release-cleanroom-bootstrap.md",
    "platform/generated/study-anything-release-cleanroom-bootstrap.zip",
    "platform/generated/study-anything-release-cleanroom-bootstrap.sha256",
    "docs/release-cleanroom-bootstrap.md",
    "scripts/replay_platform_agent_from_release.py",
    "scripts/generate_platform_agent_replay.py",
    "platform/generated/study-anything-platform-agent-replay.json",
    "platform/generated/study-anything-platform-agent-replay.md",
    "platform/generated/study-anything-platform-agent-replay.zip",
    "platform/generated/study-anything-platform-agent-replay.sha256",
    "docs/platform-agent-release-replay.md",
    "scripts/generate_adopter_evidence_archive.py",
    "scripts/verify_adopter_evidence_archive.py",
    "platform/generated/study-anything-adopter-evidence-archive.json",
    "platform/generated/study-anything-adopter-evidence-archive.md",
    "platform/generated/study-anything-adopter-evidence-archive.zip",
    "platform/generated/study-anything-adopter-evidence-archive.sha256",
    "docs/adopter-evidence-archive.md",
    "fixtures/platform-import-failures/schema_mismatch.json",
    "fixtures/platform-import-failures/missing_local_gateway.json",
    "fixtures/platform-import-failures/unsupported_auth_mode.json",
    "fixtures/platform-import-failures/tool_naming_drift.json",
    "fixtures/platform-import-failures/timeout.json",
    "fixtures/platform-import-failures/cors_localhost.json",
    "fixtures/platform-import-failures/package_corruption.json",
    "fixtures/platform-import-failures/version_drift.json",
    ".github/ISSUE_TEMPLATE/platform_import_failure.md",
    ".github/ISSUE_TEMPLATE/local_gateway_failure.md",
    ".github/ISSUE_TEMPLATE/published_image_pull_failure.md",
    ".github/ISSUE_TEMPLATE/agent_eval_evidence_failure.md",
    ".github/ISSUE_TEMPLATE/docs_confusion.md",
    "fixtures/platform-support-tickets/platform_import_failure.json",
    "fixtures/platform-support-tickets/local_gateway_failure.json",
    "fixtures/platform-support-tickets/published_image_pull_failure.json",
    "fixtures/platform-support-tickets/agent_eval_evidence_failure.json",
    "fixtures/platform-support-tickets/docs_confusion.json",
    "fixtures/platform-release-blockers/tool_import_blocker.json",
    "fixtures/platform-release-blockers/local_gateway_blocker.json",
    "fixtures/platform-release-blockers/published_image_blocker.json",
    "fixtures/platform-release-blockers/agent_eval_blocker.json",
    "fixtures/platform-release-blockers/support_bundle_privacy_blocker.json",
    "fixtures/platform-status-links/intake.json",
    "fixtures/platform-status-links/needs-repro.json",
    "fixtures/platform-status-links/confirmed.json",
    "fixtures/platform-status-links/blocked-by-platform.json",
    "fixtures/platform-status-links/docs-fix.json",
    "fixtures/platform-status-links/release-blocker.json",
    "fixtures/platform-status-links/resolved.json",
    "fixtures/adopter-evidence-archive/successful-release.json",
    "fixtures/adopter-evidence-archive/local-ghcr-pull-timeout.json",
    "fixtures/adopter-evidence-archive/needs-repro-issue.json",
    "fixtures/adopter-evidence-archive/release-blocker.json",
    "fixtures/adopter-evidence-archive/platform-blocked.json",
    "fixtures/adopter-evidence-archive/resolved-support-case.json",
    "fixtures/published-image-evidence/manifest-pass-local-pull-timeout.json",
    "fixtures/published-image-evidence/cached-image-missing.json",
    "fixtures/published-image-evidence/compose-up-timeout.json",
    "fixtures/published-image-evidence/manifest-only-runtime-unverified.json",
    "fixtures/published-image-evidence/manifest-missing-platform.json",
    "fixtures/published-image-evidence/docker-images-failed.json",
    "fixtures/published-image-evidence/ghcr-unavailable.json",
    "fixtures/published-image-evidence/remote-smoke-pass.json",
    "fixtures/published-image-evidence/remote-smoke-failed.json",
    "fixtures/release-asset-adoption/asset-only-pass.json",
    "fixtures/release-asset-adoption/asset-missing.json",
    "fixtures/release-asset-adoption/digest-mismatch.json",
    "fixtures/release-asset-adoption/pack-corrupted.json",
    "fixtures/release-asset-adoption/published-evidence-missing.json",
    "fixtures/release-asset-adoption/network-unavailable.json",
    "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
    "platform/generated/study-anything-deployment-hardening.json",
    "platform/generated/study-anything-learning-enrichment-bridge.json",
    "docs/plugins.md",
    "docs/plugin-sdk.md",
    "docs/plugin-registry.md",
    "docs/support-desk.md",
    "docs/adopter-onboarding.md",
    "docs/maintainer-rotation.md",
    "docs/public-support-status.md",
    "plugins/registry.json",
    "plugins/example-note-importer/plugin.json",
    "plugins/example-note-importer/plugin.py",
    "plugins/example-web-importer/plugin.json",
    "plugins/example-web-importer/plugin.py",
    "plugins/example-enrichment-importer/plugin.json",
    "plugins/example-enrichment-importer/plugin.py",
    "plugins/example-exporter/plugin.json",
    "plugins/example-exporter/plugin.py",
    "plugins/example-agent-provider/plugin.json",
    "plugins/example-agent-provider/plugin.py",
}
REQUIRED_ACCEPTANCE_COMMANDS = {
    "verify_ecosystem_submission_pack.py",
    "verify_cognitive_loop_contracts.py --check",
    "verify_cognitive_loop_cli.py --check",
    "verify_cognitive_loop_run_once.py --check",
    "verify_cognitive_loop_snapshot.py --check",
    "verify_cognitive_loop_human_gate.py --check",
    "verify_cognitive_loop_evidence_bundle.py --check",
    "verify_cognitive_loop_event_index.py --check",
    "verify_cognitive_loop_artifact_doctor.py --check",
    "verify_cognitive_loop_repair_plan.py --check",
    "verify_cognitive_loop_artifact_index.py --check",
    "verify_cognitive_loop_adoption_cookbook.py --check",
    "generate_cognitive_loop_adoption_recipes.py --check",
    "verify_cognitive_loop_recipe_replay.py --check",
    "verify_cognitive_loop_skill_entrypoint.py --check",
    "verify_cognitive_loop_recipe_cli.py --check",
    "verify_cognitive_loop_recipe_cli_receipts.py --check",
    "verify_cognitive_loop_recipe_cli_failures.py --check",
    "verify_cognitive_loop_recipe_cli_schemas.py --check",
    "verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py --check",
    "verify_cognitive_loop_schema_pack_consumer.py --check",
    "verify_commercial_readiness.py",
    "verify_adoption_telemetry.py",
    "verify_agent_gateway_hardening.py",
    "verify_external_agent_adapter_hardening.py",
    "verify_notebooklm_obsidian_bridge_hardening.py",
    "verify_learning_enrichment_bridge.py",
    "verify_plugin_quarantine.py",
    "verify_security_recovery_hardening.py",
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
    "generate_platform_public_support_status.py --check",
    "verify_platform_public_support_status.py --check",
    "generate_published_image_evidence.py --check",
    "verify_published_image_evidence.py --check",
    "generate_release_asset_adoption.py --check",
    "verify_release_asset_adoption.py",
    "generate_release_asset_bootstrap.py --check",
    "bootstrap_from_release.py",
    "generate_platform_agent_replay.py --check",
    "replay_platform_agent_from_release.py",
    "generate_adopter_evidence_archive.py --check",
    "verify_adopter_evidence_archive.py --check",
    "verify_plugin_ecosystem_adoption_kit.py",
    "verify_deployment_hardening.py",
    "verify_platform_ecosystem_packs.py",
    "generate_platform_bundle_manifest.py --check",
    "generate_platform_adoption_pack.py --check",
    "verify_external_adoption.py",
}
BANNED_TOOL_PATH_FRAGMENTS = (
    "/v1/agents/providers",
    "/v1/agents/defaults",
    "/v1/models/",
    "/v1/plugins/install",
    "/v1/sync/export",
    "/v1/sync/inspect",
    "/v1/sync/restore-preview",
    "/v1/pmf/export",
)
REQUIRED_PRIVACY_FALSE = (
    "real_model_keys_stored_by_study_anything",
    "agent_endpoints_in_submission",
    "raw_learning_data_in_submission",
    "management_endpoints_exposed_to_platform_tools",
)


class EcosystemSubmissionError(RuntimeError):
    """Readable submission-pack verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EcosystemSubmissionError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EcosystemSubmissionError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def require_file(relative_path: str, *, label: str) -> None:
    path = ROOT / relative_path
    if not path.exists() or path.is_dir():
        raise EcosystemSubmissionError(f"{label} references missing file: {relative_path}")
    if any(part in {".env", ".venv", ".git", "data", "__pycache__"} for part in path.parts):
        raise EcosystemSubmissionError(f"{label} references unsafe path: {relative_path}")


def verify_privacy(submission: dict[str, Any], tool_manifest: dict[str, Any]) -> list[str]:
    privacy = submission.get("privacy")
    if not isinstance(privacy, dict):
        raise EcosystemSubmissionError("Submission must declare privacy.")
    for key in REQUIRED_PRIVACY_FALSE:
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"privacy.{key} must be false")
    expected = tool_manifest.get("privacy_contract", {}).get("must_not_log_or_share")
    if not isinstance(expected, list) or not expected:
        raise EcosystemSubmissionError("Tool manifest privacy contract is missing.")
    actual = privacy.get("must_not_log_or_share")
    if actual != expected:
        raise EcosystemSubmissionError("Submission privacy contract drifted from platform tool manifest.")
    return [str(item) for item in actual]


def verify_tool_manifest(tool_manifest: dict[str, Any]) -> int:
    if tool_manifest.get("schema_version") != "study-anything-platform-tools-v1":
        raise EcosystemSubmissionError("Platform tool manifest schema drifted.")
    tools = tool_manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        raise EcosystemSubmissionError("Platform tool manifest must include tools.")
    for tool in tools:
        name = tool.get("name")
        path_template = tool.get("path_template")
        if not isinstance(name, str) or not isinstance(path_template, str):
            raise EcosystemSubmissionError(f"Invalid tool record: {tool}")
        banned = [fragment for fragment in BANNED_TOOL_PATH_FRAGMENTS if fragment in path_template]
        if banned:
            raise EcosystemSubmissionError(f"{name} exposes management endpoint(s): {banned}")
    return len(tools)


def verify_generated_assets(tool_count: int) -> None:
    openapi = load_json(OPENAPI_PATH)
    if openapi.get("openapi") != "3.1.0":
        raise EcosystemSubmissionError("Generated OpenAPI asset must be OpenAPI 3.1.0.")
    paths = openapi.get("paths")
    if not isinstance(paths, dict) or len(paths) < tool_count // 2:
        raise EcosystemSubmissionError("Generated OpenAPI asset has too few paths.")

    openai_tools = json.loads(OPENAI_TOOLS_PATH.read_text(encoding="utf-8"))
    if not isinstance(openai_tools, list) or len(openai_tools) != tool_count:
        raise EcosystemSubmissionError("OpenAI-compatible tools are not aligned with the source manifest.")


def verify_submission(submission: dict[str, Any]) -> dict[str, Any]:
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise EcosystemSubmissionError("Submission has invalid schema_version.")
    if submission.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Submission version must be v0.3.30-alpha.")

    project = submission.get("project")
    if not isinstance(project, dict):
        raise EcosystemSubmissionError("Submission must declare project metadata.")
    if project.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Submission must declare no standalone frontend requirement.")
    if project.get("billing_required") is not False:
        raise EcosystemSubmissionError("Submission must declare no billing requirement.")

    commercial = submission.get("commercial_readiness")
    if not isinstance(commercial, dict) or commercial.get("contract") != "commercial-readiness-v1":
        raise EcosystemSubmissionError("Submission must link commercial-readiness-v1.")
    if commercial.get("endpoint") != "/v1/commercial/readiness":
        raise EcosystemSubmissionError("Commercial readiness endpoint drifted.")
    if "hosted_paid_services" not in set(commercial.get("not_ready_paths", [])):
        raise EcosystemSubmissionError("Hosted paid services must remain not ready for this submission.")

    telemetry = submission.get("adoption_telemetry")
    if not isinstance(telemetry, dict):
        raise EcosystemSubmissionError("Submission must link adoption telemetry.")
    if telemetry.get("contract") != "adoption-telemetry-v1":
        raise EcosystemSubmissionError("Submission adoption telemetry contract drifted.")
    if telemetry.get("endpoint") != "/v1/adoption/telemetry":
        raise EcosystemSubmissionError("Submission adoption telemetry endpoint drifted.")
    if telemetry.get("readiness_contract") != "pmf-readiness-v1":
        raise EcosystemSubmissionError("Submission PMF readiness contract drifted.")
    if telemetry.get("aggregate_only") is not True or telemetry.get("automatic_upload") is not False:
        raise EcosystemSubmissionError("Submission adoption telemetry privacy boundary is unsafe.")

    shared_assets = submission.get("shared_assets")
    if not isinstance(shared_assets, list):
        raise EcosystemSubmissionError("Submission must declare shared_assets.")
    missing_shared = REQUIRED_SHARED_ASSETS - set(str(asset) for asset in shared_assets)
    if missing_shared:
        raise EcosystemSubmissionError(f"Submission shared_assets missing: {sorted(missing_shared)}")
    for asset in shared_assets:
        require_file(str(asset), label="shared_assets")

    acceptance = submission.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("schema") != "ecosystem-submission-verification-v1":
        raise EcosystemSubmissionError("Submission acceptance schema drifted.")
    command_text = "\n".join(str(command) for command in acceptance.get("minimum_commands", []))
    missing_commands = [fragment for fragment in sorted(REQUIRED_ACCEPTANCE_COMMANDS) if fragment not in command_text]
    if missing_commands:
        raise EcosystemSubmissionError(f"Acceptance commands missing: {missing_commands}")
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    for schema in (
        "public-support-status-v1",
        "public-maintainer-dashboard-v1",
        "public-status-linkage-fixture-v1",
        "published-image-evidence-v1",
        "published-image-evidence-fixture-v1",
        "release-asset-adoption-v1",
        "release-asset-adoption-fixture-v1",
        "release-asset-adoption-proof-v1",
        "release-asset-bootstrap-v1",
        "release-asset-bootstrap-transcript-v1",
        "platform-agent-release-replay-v1",
        "adopter-evidence-archive-v1",
        "adopter-evidence-fixture-v1",
        "cognitive-loop-contract-bootstrap-v1",
        "cognitive-loop-cli-artifact-verification-v1",
        "cognitive-loop-run-once-evidence-verification-v1",
        "cognitive-loop-project-snapshot-verification-v1",
        "cognitive-loop-human-gate-verification-v1",
        "cognitive-loop-evidence-bundle-verification-v1",
        "cognitive-loop-event-index-verification-v1",
        "cognitive-loop-artifact-doctor-verification-v1",
        "cognitive-loop-repair-plan-verification-v1",
        "cognitive-loop-artifact-index-verification-v1",
        "cognitive-loop-adoption-cookbook-verification-v1",
        "cognitive-loop-adoption-recipes-v1",
        "cognitive-loop-recipe-replay-verification-v1",
        "cognitive-loop-skill-entrypoint-verification-v1",
        "cognitive-loop-recipe-cli-verification-v1",
        "cognitive-loop-recipe-cli-receipts-v1",
        "cognitive-loop-recipe-cli-failures-v1",
    ):
        if schema not in prove_text:
            raise EcosystemSubmissionError(f"Submission acceptance must prove {schema}.")

    submissions = submission.get("submissions")
    if not isinstance(submissions, list) or not submissions:
        raise EcosystemSubmissionError("Submission must include platform submissions.")
    by_id = {str(item.get("platform_id")): item for item in submissions if isinstance(item, dict)}
    missing_platforms = REQUIRED_PLATFORMS - set(by_id)
    if missing_platforms:
        raise EcosystemSubmissionError(f"Missing submission platforms: {sorted(missing_platforms)}")
    return by_id


def verify_platform_submissions(by_id: dict[str, Any]) -> None:
    for platform_id, submission in sorted(by_id.items()):
        if submission.get("no_frontend_required") is not True:
            raise EcosystemSubmissionError(f"{platform_id} must declare no_frontend_required=true.")
        if not submission.get("integration_mode"):
            raise EcosystemSubmissionError(f"{platform_id} must declare integration_mode.")

        for group in ("entrypoints",):
            values = submission.get(group)
            if not isinstance(values, dict) or not values:
                raise EcosystemSubmissionError(f"{platform_id} must declare {group}.")
            for path in values.values():
                require_file(str(path), label=f"{platform_id}.{group}")

        import_assets = submission.get("import_assets")
        if not isinstance(import_assets, list) or not import_assets:
            raise EcosystemSubmissionError(f"{platform_id} must declare import_assets.")
        if "docs/cognitive-loop-adoption-cookbook.md" not in set(str(asset) for asset in import_assets):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop adoption cookbook.")
        if "platform/generated/study-anything-cognitive-loop-adoption-cookbook.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop cookbook report.")
        if "platform/generated/study-anything-cognitive-loop-adoption-recipes.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop adoption recipes.")
        if "platform/generated/study-anything-cognitive-loop-recipe-replay.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe replay report.")
        if "platform/generated/study-anything-cognitive-loop-skill-entrypoint.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop Skill entrypoint report.")
        if "platform/generated/study-anything-cognitive-loop-recipe-cli.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI report.")
        if "platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI receipts.")
        if "platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI failures.")
        if "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI schemas.")
        if "platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(
                f"{platform_id} must include the Cognitive Loop recipe CLI schema negative fixtures."
            )
        if "platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop schema pack consumer report.")
        if "scripts/cognitive_loop_recipe_cli.py" not in set(str(asset) for asset in import_assets):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI script.")
        if "scripts/verify_cognitive_loop_recipe_cli_receipts.py" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI receipt verifier.")
        if "scripts/verify_cognitive_loop_recipe_cli_failures.py" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI failure verifier.")
        if "scripts/verify_cognitive_loop_recipe_cli_schemas.py" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop recipe CLI schema verifier.")
        if "scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(
                f"{platform_id} must include the Cognitive Loop recipe CLI schema negative fixture verifier."
            )
        if "scripts/verify_cognitive_loop_schema_pack_consumer.py" not in set(
            str(asset) for asset in import_assets
        ):
            raise EcosystemSubmissionError(f"{platform_id} must include the Cognitive Loop schema pack consumer verifier.")
        for asset in import_assets:
            require_file(str(asset), label=f"{platform_id}.import_assets")

        commands = "\n".join(str(command) for command in submission.get("verification_commands", []))
        if "verify_ecosystem_submission_pack.py" not in commands:
            raise EcosystemSubmissionError(f"{platform_id} must include the submission verifier command.")
        if not submission.get("known_limits"):
            raise EcosystemSubmissionError(f"{platform_id} must declare known_limits.")

    for pack_id in ("kimi", "codex", "workbuddy"):
        pack = load_json(PACKS_DIR / pack_id / "pack.json")
        if pack.get("schema_version") != "study-anything-platform-pack-v1":
            raise EcosystemSubmissionError(f"{pack_id} pack schema drifted.")
        if pack.get("platform_id") != pack_id:
            raise EcosystemSubmissionError(f"{pack_id} pack platform_id drifted.")
        commands = "\n".join(str(item) for item in pack.get("local_verification_commands", []))
        for command in (
            "generate_platform_field_rehearsal.py --check",
            "verify_platform_field_rehearsal.py --check",
            "generate_platform_support_triage.py --check",
            "verify_platform_support_triage.py --check",
            "generate_platform_onboarding_readiness.py --check",
            "verify_platform_onboarding_readiness.py --check",
            "generate_platform_public_support_status.py --check",
            "verify_platform_public_support_status.py --check",
            "generate_published_image_evidence.py --check",
            "verify_published_image_evidence.py --check",
            "generate_release_asset_adoption.py --check",
            "verify_release_asset_adoption.py",
            "generate_release_asset_bootstrap.py --check",
            "bootstrap_from_release.py",
            "generate_release_cleanroom_bootstrap.py --check",
            "study_anything_release_bootstrap.py",
            "generate_platform_agent_replay.py --check",
            "replay_platform_agent_from_release.py",
            "generate_adopter_evidence_archive.py --check",
            "verify_adopter_evidence_archive.py --check",
        ):
            if command not in commands:
                raise EcosystemSubmissionError(f"{pack_id} pack missing platform adoption command {command}.")
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        for item in (
            "platform_field_rehearsal.schema_version == platform-field-adoption-rehearsal-v1",
            "platform_import_failure_fixture.schema_version == platform-import-failure-fixture-v1",
            "platform_support_triage.schema_version == platform-support-triage-v1",
            "platform_support_ticket_fixture.schema_version == platform-support-ticket-fixture-v1",
            "platform_onboarding_readiness.schema_version == platform-onboarding-readiness-v1",
            "platform_triage_dashboard.schema_version == platform-triage-dashboard-v1",
            "platform_release_blocker_fixture.schema_version == platform-release-blocker-fixture-v1",
            "public_support_status.schema_version == public-support-status-v1",
            "public_maintainer_dashboard.schema_version == public-maintainer-dashboard-v1",
            "public_status_linkage_fixture.schema_version == public-status-linkage-fixture-v1",
            "cognitive_loop_contracts.schema_version == cognitive-loop-contract-bootstrap-v1",
            "cognitive_loop_cli_artifact.schema_version == cognitive-loop-cli-artifact-verification-v1",
            "cognitive_loop_run_once_evidence.schema_version == cognitive-loop-run-once-evidence-verification-v1",
            "cognitive_loop_project_snapshot.schema_version == cognitive-loop-project-snapshot-verification-v1",
            "cognitive_loop_human_gate.schema_version == cognitive-loop-human-gate-verification-v1",
            "cognitive_loop_evidence_bundle.schema_version == cognitive-loop-evidence-bundle-verification-v1",
            "cognitive_loop_event_index.schema_version == cognitive-loop-event-index-verification-v1",
            "cognitive_loop_artifact_doctor.schema_version == cognitive-loop-artifact-doctor-verification-v1",
            "cognitive_loop_repair_plan.schema_version == cognitive-loop-repair-plan-verification-v1",
            "cognitive_loop_artifact_index.schema_version == cognitive-loop-artifact-index-verification-v1",
            "published_image_evidence.schema_version == published-image-evidence-v1",
            "published_image_evidence_fixture.schema_version == published-image-evidence-fixture-v1",
            "release_asset_adoption.schema_version == release-asset-adoption-v1",
            "release_asset_adoption_fixture.schema_version == release-asset-adoption-fixture-v1",
            "release_asset_adoption_proof.schema_version == release-asset-adoption-proof-v1",
            "release_asset_bootstrap.schema_version == release-asset-bootstrap-v1",
            "release_asset_bootstrap_transcript.schema_version == release-asset-bootstrap-transcript-v1",
            "release_cleanroom_bootstrap.schema_version == release-cleanroom-bootstrap-v1",
            "release_cleanroom_bootstrap_evidence.schema_version == release-cleanroom-bootstrap-evidence-v1",
            "platform_agent_release_replay.schema_version == platform-agent-release-replay-v1",
            "adopter_evidence_archive.schema_version == adopter-evidence-archive-v1",
            "adopter_evidence_fixture.schema_version == adopter-evidence-fixture-v1",
            "cognitive_loop_adoption_cookbook.schema_version == cognitive-loop-adoption-cookbook-verification-v1",
            "cognitive_loop_adoption_recipes.schema_version == cognitive-loop-adoption-recipes-v1",
            "cognitive_loop_recipe_replay.schema_version == cognitive-loop-recipe-replay-verification-v1",
            "cognitive_loop_skill_entrypoint.schema_version == cognitive-loop-skill-entrypoint-verification-v1",
            "cognitive_loop_recipe_cli.schema_version == cognitive-loop-recipe-cli-verification-v1",
            "cognitive_loop_recipe_cli_receipts.schema_version == cognitive-loop-recipe-cli-receipts-v1",
            "cognitive_loop_recipe_cli_failures.schema_version == cognitive-loop-recipe-cli-failures-v1",
            "cognitive_loop_recipe_cli_schemas.schema_version == cognitive-loop-recipe-cli-schemas-v1",
            "cognitive_loop_recipe_cli_schema_negative_fixtures.schema_version == cognitive-loop-recipe-cli-schema-negative-fixtures-v1",
            "cognitive_loop_schema_pack_consumer.schema_version == cognitive-loop-schema-pack-consumer-v1",
        ):
            if item not in evidence:
                raise EcosystemSubmissionError(f"{pack_id} pack missing platform adoption evidence {item}.")


def verify_pack_in_generated_adoption() -> None:
    manifest = load_json(ADOPTION_PACK_PATH)
    if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
        raise EcosystemSubmissionError("Generated adoption pack schema drifted.")
    if manifest.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Generated adoption pack must be updated to v0.3.30-alpha.")
    paths = {item.get("path") for item in manifest.get("files", []) if isinstance(item, dict)}
    required = {
        "platform/ecosystem-submission.json",
        "docs/ecosystem-submission.md",
        "docs/release-checklist.md",
        "docs/roadmap.md",
        "docs/cognitive-loop-contracts.md",
        "docs/cognitive-loop-adoption-cookbook.md",
        "docs/adoption-telemetry.md",
        ".cognitive-loop/config.yaml",
        ".cognitive-loop/permissions.yaml",
        ".cognitive-loop/evals.yaml",
        ".cognitive-loop/risk.yaml",
        "scripts/verify_cognitive_loop_contracts.py",
        "scripts/cognitive_loop_cli.py",
        "scripts/verify_cognitive_loop_cli.py",
        "scripts/verify_cognitive_loop_run_once.py",
        "scripts/verify_cognitive_loop_snapshot.py",
        "scripts/verify_cognitive_loop_human_gate.py",
        "scripts/verify_cognitive_loop_evidence_bundle.py",
        "scripts/verify_cognitive_loop_event_index.py",
        "scripts/verify_cognitive_loop_artifact_doctor.py",
        "scripts/verify_cognitive_loop_repair_plan.py",
        "scripts/verify_cognitive_loop_artifact_index.py",
        "scripts/verify_cognitive_loop_adoption_cookbook.py",
        "scripts/generate_cognitive_loop_adoption_recipes.py",
        "scripts/verify_cognitive_loop_recipe_replay.py",
        "scripts/verify_cognitive_loop_skill_entrypoint.py",
        "scripts/cognitive_loop_recipe_cli.py",
        "scripts/verify_cognitive_loop_recipe_cli.py",
        "scripts/verify_cognitive_loop_recipe_cli_receipts.py",
        "scripts/verify_cognitive_loop_recipe_cli_failures.py",
        "scripts/verify_cognitive_loop_recipe_cli_schemas.py",
        "scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py",
        "scripts/verify_cognitive_loop_schema_pack_consumer.py",
        "platform/generated/study-anything-cognitive-loop-contracts.json",
        "platform/generated/study-anything-cognitive-loop-cli-artifact.json",
        "platform/generated/study-anything-cognitive-loop-run-once-evidence.json",
        "platform/generated/study-anything-cognitive-loop-project-snapshot.json",
        "platform/generated/study-anything-cognitive-loop-human-gate.json",
        "platform/generated/study-anything-cognitive-loop-evidence-bundle.json",
        "platform/generated/study-anything-cognitive-loop-event-index.json",
        "platform/generated/study-anything-cognitive-loop-artifact-doctor.json",
        "platform/generated/study-anything-cognitive-loop-repair-plan.json",
        "platform/generated/study-anything-cognitive-loop-artifact-index.json",
        "platform/generated/study-anything-cognitive-loop-adoption-cookbook.json",
        "platform/generated/study-anything-cognitive-loop-adoption-recipes.json",
        "platform/generated/study-anything-cognitive-loop-recipe-replay.json",
        "platform/generated/study-anything-cognitive-loop-skill-entrypoint.json",
        "platform/generated/study-anything-cognitive-loop-recipe-cli.json",
        "platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json",
        "platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json",
        "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json",
        "platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json",
        "platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json",
        "scripts/verify_ecosystem_submission_pack.py",
        "scripts/verify_adoption_telemetry.py",
        "scripts/verify_notebooklm_obsidian_bridge_hardening.py",
        "scripts/verify_learning_enrichment_bridge.py",
        "scripts/verify_plugin_quarantine.py",
        "scripts/verify_security_recovery_hardening.py",
        "scripts/verify_platform_submission_dry_run.py",
        "scripts/verify_platform_manual_submission_rehearsal.py",
        "scripts/verify_first_lesson_authoring_kit.py",
        "scripts/verify_external_eval_marketplace_harness.py",
        "scripts/verify_agent_eval_marketplace_enforcement.py",
        "scripts/verify_platform_adoption_feedback_diagnostics.py",
        "scripts/generate_platform_feedback_package.py",
        "scripts/generate_platform_field_rehearsal.py",
        "scripts/verify_platform_field_rehearsal.py",
        "scripts/generate_platform_support_triage.py",
        "scripts/verify_platform_support_triage.py",
        "scripts/generate_platform_onboarding_readiness.py",
        "scripts/verify_platform_onboarding_readiness.py",
        "scripts/generate_platform_public_support_status.py",
        "scripts/verify_platform_public_support_status.py",
        "scripts/generate_adopter_evidence_archive.py",
        "scripts/verify_adopter_evidence_archive.py",
        "scripts/verify_plugin_ecosystem_adoption_kit.py",
        "scripts/verify_deployment_hardening.py",
        "scripts/install_local_plugin.py",
        "platform/generated/study-anything-operator-drill-transcript.json",
        "platform/generated/study-anything-platform-submission-dry-run.json",
        "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
        "platform/generated/study-anything-first-lesson-authoring-kit.json",
        "platform/generated/study-anything-external-eval-harness.json",
        "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
        "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
        "platform/generated/study-anything-platform-feedback-package.json",
        "platform/generated/study-anything-platform-feedback-package.zip",
        "platform/generated/study-anything-platform-field-rehearsal.json",
        "platform/generated/study-anything-platform-support-triage.json",
        "platform/generated/study-anything-platform-onboarding-readiness.json",
        "platform/generated/study-anything-platform-triage-dashboard.json",
        "platform/generated/study-anything-platform-triage-dashboard.md",
        "platform/generated/study-anything-public-support-status.json",
        "platform/generated/study-anything-public-maintainer-dashboard.json",
        "platform/generated/study-anything-public-maintainer-dashboard.md",
        "scripts/generate_published_image_evidence.py",
        "scripts/verify_published_image_evidence.py",
        "platform/generated/study-anything-published-image-evidence.json",
        "platform/generated/study-anything-published-image-evidence.md",
        "platform/generated/study-anything-published-image-evidence.zip",
        "platform/generated/study-anything-published-image-evidence.sha256",
        "docs/published-image-evidence.md",
        "scripts/generate_release_asset_adoption.py",
        "scripts/verify_release_asset_adoption.py",
        "platform/generated/study-anything-release-asset-adoption.json",
        "platform/generated/study-anything-release-asset-adoption.md",
        "platform/generated/study-anything-release-asset-adoption.zip",
        "platform/generated/study-anything-release-asset-adoption.sha256",
        "docs/release-asset-adoption.md",
        "scripts/bootstrap_from_release.py",
        "scripts/generate_release_asset_bootstrap.py",
        "platform/generated/study-anything-release-asset-bootstrap.json",
        "platform/generated/study-anything-release-asset-bootstrap.md",
        "platform/generated/study-anything-release-asset-bootstrap.zip",
        "platform/generated/study-anything-release-asset-bootstrap.sha256",
        "docs/release-asset-bootstrap.md",
        "platform/bootstrap/study_anything_release_bootstrap.py",
        "scripts/generate_release_cleanroom_bootstrap.py",
        "platform/generated/study-anything-release-cleanroom-bootstrap.json",
        "platform/generated/study-anything-release-cleanroom-bootstrap.md",
        "platform/generated/study-anything-release-cleanroom-bootstrap.zip",
        "platform/generated/study-anything-release-cleanroom-bootstrap.sha256",
        "docs/release-cleanroom-bootstrap.md",
        "scripts/replay_platform_agent_from_release.py",
        "scripts/generate_platform_agent_replay.py",
        "platform/generated/study-anything-platform-agent-replay.json",
        "platform/generated/study-anything-platform-agent-replay.md",
        "platform/generated/study-anything-platform-agent-replay.zip",
        "platform/generated/study-anything-platform-agent-replay.sha256",
        "docs/platform-agent-release-replay.md",
        "platform/generated/study-anything-adopter-evidence-archive.json",
        "platform/generated/study-anything-adopter-evidence-archive.md",
        "platform/generated/study-anything-adopter-evidence-archive.zip",
        "platform/generated/study-anything-adopter-evidence-archive.sha256",
        "fixtures/platform-import-failures/schema_mismatch.json",
        "fixtures/platform-import-failures/missing_local_gateway.json",
        "fixtures/platform-import-failures/unsupported_auth_mode.json",
        "fixtures/platform-import-failures/tool_naming_drift.json",
        "fixtures/platform-import-failures/timeout.json",
        "fixtures/platform-import-failures/cors_localhost.json",
        "fixtures/platform-import-failures/package_corruption.json",
        "fixtures/platform-import-failures/version_drift.json",
        ".github/ISSUE_TEMPLATE/platform_import_failure.md",
        ".github/ISSUE_TEMPLATE/local_gateway_failure.md",
        ".github/ISSUE_TEMPLATE/published_image_pull_failure.md",
        ".github/ISSUE_TEMPLATE/agent_eval_evidence_failure.md",
        ".github/ISSUE_TEMPLATE/docs_confusion.md",
        "fixtures/platform-support-tickets/platform_import_failure.json",
        "fixtures/platform-support-tickets/local_gateway_failure.json",
        "fixtures/platform-support-tickets/published_image_pull_failure.json",
        "fixtures/platform-support-tickets/agent_eval_evidence_failure.json",
        "fixtures/platform-support-tickets/docs_confusion.json",
        "fixtures/platform-release-blockers/tool_import_blocker.json",
        "fixtures/platform-release-blockers/local_gateway_blocker.json",
        "fixtures/platform-release-blockers/published_image_blocker.json",
        "fixtures/platform-release-blockers/agent_eval_blocker.json",
        "fixtures/platform-release-blockers/support_bundle_privacy_blocker.json",
        "fixtures/platform-status-links/intake.json",
        "fixtures/platform-status-links/needs-repro.json",
        "fixtures/platform-status-links/confirmed.json",
        "fixtures/platform-status-links/blocked-by-platform.json",
        "fixtures/platform-status-links/docs-fix.json",
        "fixtures/platform-status-links/release-blocker.json",
        "fixtures/platform-status-links/resolved.json",
        "fixtures/adopter-evidence-archive/successful-release.json",
        "fixtures/adopter-evidence-archive/local-ghcr-pull-timeout.json",
        "fixtures/adopter-evidence-archive/needs-repro-issue.json",
        "fixtures/adopter-evidence-archive/release-blocker.json",
        "fixtures/adopter-evidence-archive/platform-blocked.json",
        "fixtures/adopter-evidence-archive/resolved-support-case.json",
        "fixtures/published-image-evidence/manifest-pass-local-pull-timeout.json",
        "fixtures/published-image-evidence/cached-image-missing.json",
        "fixtures/published-image-evidence/compose-up-timeout.json",
        "fixtures/published-image-evidence/manifest-only-runtime-unverified.json",
        "fixtures/published-image-evidence/manifest-missing-platform.json",
        "fixtures/published-image-evidence/docker-images-failed.json",
        "fixtures/published-image-evidence/ghcr-unavailable.json",
        "fixtures/published-image-evidence/remote-smoke-pass.json",
        "fixtures/published-image-evidence/remote-smoke-failed.json",
        "fixtures/release-asset-adoption/asset-only-pass.json",
        "fixtures/release-asset-adoption/asset-missing.json",
        "fixtures/release-asset-adoption/digest-mismatch.json",
        "fixtures/release-asset-adoption/pack-corrupted.json",
        "fixtures/release-asset-adoption/published-evidence-missing.json",
        "fixtures/release-asset-adoption/network-unavailable.json",
        "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
        "platform/generated/study-anything-deployment-hardening.json",
        "platform/generated/study-anything-learning-enrichment-bridge.json",
        "docs/agent-eval.md",
        "docs/eval-frameworks.md",
        "docs/support-desk.md",
        "docs/adopter-onboarding.md",
        "docs/maintainer-rotation.md",
        "docs/public-support-status.md",
        "docs/adopter-evidence-archive.md",
        "docs/release-notes/v0.3.30-alpha.md",
        "docs/plugins.md",
        "docs/plugin-sdk.md",
        "docs/plugin-registry.md",
        "plugins/registry.json",
        "plugins/example-note-importer/plugin.json",
        "plugins/example-note-importer/plugin.py",
        "plugins/example-web-importer/plugin.json",
        "plugins/example-web-importer/plugin.py",
        "plugins/example-enrichment-importer/plugin.json",
        "plugins/example-enrichment-importer/plugin.py",
        "plugins/example-exporter/plugin.json",
        "plugins/example-exporter/plugin.py",
        "plugins/example-agent-provider/plugin.json",
        "plugins/example-agent-provider/plugin.py",
    }
    missing = required - paths
    if missing:
        raise EcosystemSubmissionError(f"Generated adoption pack missing ecosystem files: {sorted(missing)}")


def verify_docs() -> None:
    text = COMMERCIAL_DOC.read_text(encoding="utf-8")
    for needle in ("commercial-readiness-v1", "platform Agent", "hosted"):
        if needle not in text:
            raise EcosystemSubmissionError(f"docs/commercial-readiness.md missing {needle!r}")


def verify_cognitive_loop_cli_artifact_report() -> None:
    report = load_json(COGNITIVE_LOOP_CLI_ARTIFACT_PATH)
    if report.get("schema_version") != "cognitive-loop-cli-artifact-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop CLI artifact report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop CLI artifact report must pass.")
    if report.get("artifact_schema") != "cognitive-loop-cli-artifact-v1":
        raise EcosystemSubmissionError("Cognitive Loop CLI artifact schema drifted.")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_decision_card",
        "contains_contract_table",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop CLI HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop CLI artifact must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "raw_source_text_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop CLI artifact privacy.{key} must be false.")


def verify_cognitive_loop_run_once_report() -> None:
    report = load_json(COGNITIVE_LOOP_RUN_ONCE_PATH)
    if report.get("schema_version") != "cognitive-loop-run-once-evidence-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop run-once evidence report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop run-once evidence report must pass.")
    if report.get("run_once_schema") != "cognitive-loop-run-once-artifact-v1":
        raise EcosystemSubmissionError("Cognitive Loop run-once artifact schema drifted.")
    loop = report.get("loop_run") or {}
    if loop.get("created") is not True or loop.get("status") != "succeeded":
        raise EcosystemSubmissionError("Cognitive Loop run-once LoopRun must be created and succeeded.")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_decision_card",
        "contains_loop_run",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop run-once HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop run-once artifact must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "raw_source_text_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop run-once privacy.{key} must be false.")


def verify_cognitive_loop_snapshot_report() -> None:
    report = load_json(COGNITIVE_LOOP_SNAPSHOT_PATH)
    if report.get("schema_version") != "cognitive-loop-project-snapshot-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop project snapshot report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop project snapshot report must pass.")
    if report.get("snapshot_schema") != "cognitive-loop-project-snapshot-v1":
        raise EcosystemSubmissionError("Cognitive Loop project snapshot artifact schema drifted.")
    snapshot = report.get("snapshot") or {}
    if snapshot.get("created") is not True or snapshot.get("changed_path_count") != 2:
        raise EcosystemSubmissionError("Cognitive Loop project snapshot must record two test paths.")
    for key in ("diff_body_included", "file_contents_included"):
        if snapshot.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop project snapshot {key} must be false.")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_project_snapshot",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop snapshot HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop snapshot artifact must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "diff_body_included",
        "file_contents_included",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop snapshot privacy.{key} must be false.")


def verify_cognitive_loop_human_gate_report() -> None:
    report = load_json(COGNITIVE_LOOP_HUMAN_GATE_PATH)
    if report.get("schema_version") != "cognitive-loop-human-gate-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop human gate report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop human gate report must pass.")
    if report.get("artifact_json_schema") != "cognitive-loop-human-gate-v1":
        raise EcosystemSubmissionError("Cognitive Loop human gate artifact schema drifted.")
    approved = report.get("approved") or {}
    if approved.get("created") is not True or approved.get("gate_status") != "approved":
        raise EcosystemSubmissionError("Cognitive Loop human gate approval path must be created and approved.")
    if approved.get("loop_status") != "succeeded":
        raise EcosystemSubmissionError("Cognitive Loop approved gate loop must succeed.")
    rejected = report.get("rejected") or {}
    if rejected.get("created") is not True or rejected.get("gate_status") != "rejected":
        raise EcosystemSubmissionError("Cognitive Loop human gate rejection path must be created and rejected.")
    if rejected.get("loop_status") != "rejected":
        raise EcosystemSubmissionError("Cognitive Loop rejected gate loop must be rejected.")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_human_gate",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop human gate HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop human gate artifact must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "diff_body_included",
        "file_contents_included",
        "raw_source_text_included",
        "learner_answers_included",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "agent_metadata_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop human gate privacy.{key} must be false.")


def verify_cognitive_loop_evidence_bundle_report() -> None:
    report = load_json(COGNITIVE_LOOP_EVIDENCE_BUNDLE_PATH)
    if report.get("schema_version") != "cognitive-loop-evidence-bundle-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop evidence bundle report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop evidence bundle report must pass.")
    if report.get("artifact_json_schema") != "cognitive-loop-evidence-bundle-v1":
        raise EcosystemSubmissionError("Cognitive Loop evidence bundle artifact schema drifted.")
    bundle = report.get("evidence_bundle") or {}
    if bundle.get("created") is not True:
        raise EcosystemSubmissionError("Cognitive Loop evidence bundle artifact must be created.")
    if bundle.get("artifact_count", 0) < 4:
        raise EcosystemSubmissionError("Cognitive Loop evidence bundle must record at least four artifacts.")
    if bundle.get("content_included") is not False:
        raise EcosystemSubmissionError("Cognitive Loop evidence bundle must not embed artifact contents.")
    for key in ("all_items_have_hash", "all_items_exclude_content"):
        if bundle.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop evidence bundle missing {key}.")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_evidence_bundle",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop evidence bundle HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop evidence bundle artifact must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "artifact_contents_included",
        "diff_body_included",
        "file_contents_included",
        "raw_source_text_included",
        "learner_answers_included",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "agent_metadata_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop evidence bundle privacy.{key} must be false.")


def verify_cognitive_loop_event_index_report() -> None:
    report = load_json(COGNITIVE_LOOP_EVENT_INDEX_PATH)
    if report.get("schema_version") != "cognitive-loop-event-index-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop event index report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop event index report must pass.")
    if report.get("artifact_json_schema") != "cognitive-loop-event-index-v1":
        raise EcosystemSubmissionError("Cognitive Loop event index artifact schema drifted.")
    event_index = report.get("event_index") or {}
    if event_index.get("created") is not True:
        raise EcosystemSubmissionError("Cognitive Loop event index artifact must be created.")
    if event_index.get("entry_count", 0) < 4:
        raise EcosystemSubmissionError("Cognitive Loop event index must record at least four event artifacts.")
    if event_index.get("content_included") is not False:
        raise EcosystemSubmissionError("Cognitive Loop event index must not embed event contents.")
    for key in ("all_items_have_hash", "all_items_exclude_content"):
        if event_index.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop event index missing {key}.")
    kinds = set(str(item) for item in event_index.get("kinds", []))
    expected = {"loop_run", "project_snapshot", "human_gate", "evidence_bundle"}
    if not expected.issubset(kinds):
        raise EcosystemSubmissionError(f"Cognitive Loop event index kinds drifted: {sorted(kinds)}")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_event_index",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop event index HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop event index artifact must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "event_contents_included",
        "artifact_contents_included",
        "diff_body_included",
        "file_contents_included",
        "raw_source_text_included",
        "learner_answers_included",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "agent_metadata_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop event index privacy.{key} must be false.")


def verify_cognitive_loop_artifact_doctor_report() -> None:
    report = load_json(COGNITIVE_LOOP_ARTIFACT_DOCTOR_PATH)
    if report.get("schema_version") != "cognitive-loop-artifact-doctor-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor report must pass.")
    if report.get("artifact_json_schema") != "cognitive-loop-artifact-doctor-v1":
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor schema drifted.")
    doctor = report.get("artifact_doctor") or {}
    if doctor.get("created") is not True:
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor artifact must be created.")
    if doctor.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor clean fixture must pass.")
    if doctor.get("file_count", 0) < 8:
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor must inspect local artifacts.")
    if doctor.get("issue_count") != 0:
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor clean fixture must have zero issues.")
    if doctor.get("content_included") is not False:
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor must not embed artifact contents.")
    for key in ("all_records_have_hash", "all_records_exclude_content"):
        if doctor.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop artifact doctor missing {key}.")
    failures = report.get("failure_modes") or {}
    for key in (
        "missing_html_pair_detected",
        "duplicate_hash_detected",
        "stale_event_index_detected",
    ):
        if failures.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop artifact doctor failure mode missing {key}.")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_artifact_doctor",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop artifact doctor HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop artifact doctor must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "event_contents_included",
        "artifact_contents_included",
        "diff_body_included",
        "file_contents_included",
        "raw_source_text_included",
        "learner_answers_included",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "agent_metadata_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop artifact doctor privacy.{key} must be false.")


def verify_cognitive_loop_repair_plan_report() -> None:
    report = load_json(COGNITIVE_LOOP_REPAIR_PLAN_PATH)
    if report.get("schema_version") != "cognitive-loop-repair-plan-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop repair-plan report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop repair-plan report must pass.")
    if report.get("artifact_json_schema") != "cognitive-loop-repair-plan-v1":
        raise EcosystemSubmissionError("Cognitive Loop repair-plan artifact schema drifted.")
    clean = report.get("clean_repair_plan") or {}
    if clean.get("created") is not True:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan artifact must be created.")
    if clean.get("action_count") != 0:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan clean fixture must have zero actions.")
    if clean.get("manual_only") is not True:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan must be manual_only.")
    if clean.get("auto_apply") is not False:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan must not auto-apply.")
    if clean.get("content_included") is not False:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan must not embed contents.")
    bad = report.get("bad_repair_plan") or {}
    if bad.get("status") != "needs_attention":
        raise EcosystemSubmissionError("Cognitive Loop repair-plan bad fixture must need attention.")
    if bad.get("manual_only") is not True:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan bad fixture must stay manual_only.")
    if bad.get("auto_apply") is not False:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan bad fixture must not auto-apply.")
    action_codes = set(str(item) for item in bad.get("action_codes", []))
    required_codes = {
        "missing_html_pair",
        "duplicate_hash",
        "stale_event_index_hash_mismatch",
        "stale_event_index_missing_event",
    }
    missing_codes = sorted(required_codes - action_codes)
    if missing_codes:
        raise EcosystemSubmissionError(f"Cognitive Loop repair-plan missing action codes: {missing_codes}")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_repair_plan",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop repair-plan HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop repair-plan must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "repair_actions_executed",
        "event_contents_included",
        "artifact_contents_included",
        "diff_body_included",
        "file_contents_included",
        "raw_source_text_included",
        "learner_answers_included",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "agent_metadata_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop repair-plan privacy.{key} must be false.")


def verify_cognitive_loop_artifact_index_report() -> None:
    report = load_json(COGNITIVE_LOOP_ARTIFACT_INDEX_PATH)
    if report.get("schema_version") != "cognitive-loop-artifact-index-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop artifact-index report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop artifact-index report must pass.")
    if report.get("artifact_json_schema") != "cognitive-loop-artifact-index-v1":
        raise EcosystemSubmissionError("Cognitive Loop artifact-index artifact schema drifted.")
    index = report.get("artifact_index") or {}
    if index.get("created") is not True:
        raise EcosystemSubmissionError("Cognitive Loop artifact-index artifact must be created.")
    if index.get("entry_count", 0) < 12:
        raise EcosystemSubmissionError("Cognitive Loop artifact-index must include local evidence artifacts.")
    if index.get("html_count", 0) < 6 or index.get("event_json_count", 0) < 6:
        raise EcosystemSubmissionError("Cognitive Loop artifact-index must link HTML and JSON artifacts.")
    if index.get("content_included") is not False:
        raise EcosystemSubmissionError("Cognitive Loop artifact-index must not embed contents.")
    if index.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop artifact-index must not require a standalone frontend.")
    for key in ("relative_links_created", "unsafe_path_rejected"):
        if index.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop artifact-index missing {key}.")
    html = report.get("html_artifact") or {}
    for key in (
        "created",
        "contains_brand",
        "contains_artifact_index",
        "contains_run_once_link",
        "contains_event_link",
        "contains_redacted_json",
    ):
        if html.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop artifact-index HTML artifact missing {key}.")
    if html.get("standalone_frontend_required") is not False:
        raise EcosystemSubmissionError("Cognitive Loop artifact-index HTML must not require a standalone frontend.")
    privacy = report.get("privacy") or {}
    for key in (
        "forbidden_text_leaked",
        "event_contents_included",
        "artifact_contents_included",
        "diff_body_included",
        "file_contents_included",
        "raw_source_text_included",
        "learner_answers_included",
        "real_model_keys_stored",
        "agent_endpoints_included",
        "agent_metadata_included",
        "watcher_daemon_started",
        "mastra_runtime_started",
        "standalone_frontend_required",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop artifact-index privacy.{key} must be false.")


def verify_cognitive_loop_adoption_cookbook_report() -> None:
    report = load_json(COGNITIVE_LOOP_ADOPTION_COOKBOOK_PATH)
    if report.get("schema_version") != "cognitive-loop-adoption-cookbook-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop adoption cookbook report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop adoption cookbook report must pass.")
    cookbook = report.get("cookbook") or {}
    if cookbook.get("path") != "docs/cognitive-loop-adoption-cookbook.md":
        raise EcosystemSubmissionError("Cognitive Loop adoption cookbook report path drifted.")
    for key in ("bilingual", "planned_layers_not_shipped"):
        if cookbook.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook must prove {key}.")
    for key in ("standalone_frontend_required", "real_model_key_custody"):
        if cookbook.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook {key} must be false.")
    if cookbook.get("sections", 0) < 9 or cookbook.get("commands", 0) < 15:
        raise EcosystemSubmissionError("Cognitive Loop adoption cookbook report lost sections or commands.")
    pack_ids = {pack.get("platform_id") for pack in report.get("platform_packs", []) if isinstance(pack, dict)}
    if pack_ids != {"codex", "kimi", "workbuddy"}:
        raise EcosystemSubmissionError("Cognitive Loop adoption cookbook platform pack coverage drifted.")
    for pack in report.get("platform_packs", []):
        for key in ("imports_cookbook", "imports_report", "runs_verifier", "accepts_schema"):
            if pack.get(key) is not True:
                raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook pack missing {key}.")
    ecosystem = report.get("ecosystem_submission") or {}
    for key in (
        "shared_assets_registered",
        "minimum_command_registered",
        "must_prove_registered",
        "submission_imports_registered",
    ):
        if ecosystem.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook ecosystem missing {key}.")
    distribution = report.get("distribution_sources") or {}
    for key in ("bundle_manifest_source_registered", "adoption_pack_source_registered"):
        if distribution.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook distribution missing {key}.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook privacy.{key} must be false.")
    boundaries = report.get("boundaries") or {}
    for key in (
        "platform_agent_owns_browser_files_apps_video_external_data",
        "study_anything_is_learning_adapter",
        "cognitive_loop_artifacts_are_metadata_only",
    ):
        if boundaries.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook boundary {key} must be true.")
    for key in (
        "mastra_runtime_shipped",
        "watcher_daemon_shipped",
        "realtime_html_console_shipped",
        "standalone_frontend_required",
    ):
        if boundaries.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption cookbook boundary {key} must be false.")


def verify_cognitive_loop_adoption_recipes_report() -> None:
    report = load_json(COGNITIVE_LOOP_ADOPTION_RECIPES_PATH)
    if report.get("schema_version") != "cognitive-loop-adoption-recipes-v1":
        raise EcosystemSubmissionError("Cognitive Loop adoption recipes schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop adoption recipes must pass.")
    if report.get("source_doc") != "docs/cognitive-loop-adoption-cookbook.md":
        raise EcosystemSubmissionError("Cognitive Loop adoption recipes source_doc drifted.")
    if set(report.get("supported_platforms", [])) != {
        "kimi",
        "codex",
        "workbuddy",
        "private-platform-agent",
        "generic-openapi-tools",
    }:
        raise EcosystemSubmissionError("Cognitive Loop adoption recipes platform coverage drifted.")
    recipes = report.get("recipes")
    if not isinstance(recipes, list) or len(recipes) != 4:
        raise EcosystemSubmissionError("Cognitive Loop adoption recipes must include four recipes.")
    expected_ids = {"first_adoption", "daily_project_review", "risk_decision", "learning_handoff"}
    recipe_ids = {str(recipe.get("recipe_id")) for recipe in recipes if isinstance(recipe, dict)}
    if recipe_ids != expected_ids:
        raise EcosystemSubmissionError(f"Cognitive Loop adoption recipe ids drifted: {sorted(recipe_ids)}")
    for recipe in recipes:
        for key in ("title", "zh_title", "operator_goal", "platform_agent_role", "study_anything_role"):
            if not recipe.get(key):
                raise EcosystemSubmissionError(f"Cognitive Loop adoption recipe missing {key}.")
        if not recipe.get("commands") or not recipe.get("acceptance_evidence"):
            raise EcosystemSubmissionError("Cognitive Loop adoption recipe missing commands or evidence.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption recipes privacy.{key} must be false.")
    boundaries = report.get("boundaries") or {}
    for key in (
        "platform_agent_owns_browser_files_apps_video_external_data",
        "study_anything_is_learning_adapter",
        "cognitive_loop_artifacts_are_metadata_only",
    ):
        if boundaries.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption recipes boundary {key} must be true.")
    for key in (
        "mastra_runtime_shipped",
        "watcher_daemon_shipped",
        "realtime_html_console_shipped",
        "standalone_frontend_required",
    ):
        if boundaries.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop adoption recipes boundary {key} must be false.")


def verify_cognitive_loop_recipe_replay_report() -> None:
    report = load_json(COGNITIVE_LOOP_RECIPE_REPLAY_PATH)
    if report.get("schema_version") != "cognitive-loop-recipe-replay-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe replay report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop recipe replay report must pass.")
    replay = report.get("replay") or {}
    if replay.get("source_schema_version") != "cognitive-loop-adoption-recipes-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe replay source schema drifted.")
    if replay.get("source_doc") != "docs/cognitive-loop-adoption-cookbook.md":
        raise EcosystemSubmissionError("Cognitive Loop recipe replay source_doc drifted.")
    recipe_ids = {recipe.get("recipe_id") for recipe in replay.get("recipes", []) if isinstance(recipe, dict)}
    if recipe_ids != {"first_adoption", "daily_project_review", "risk_decision", "learning_handoff"}:
        raise EcosystemSubmissionError(f"Cognitive Loop recipe replay ids drifted: {sorted(recipe_ids)}")
    if replay.get("all_commands_reference_existing_scripts") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe replay must prove command scripts exist.")
    if replay.get("all_evidence_resolved") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe replay must resolve acceptance evidence.")
    if set(replay.get("runtime_required_recipe_ids", [])) != {"first_adoption", "learning_handoff"}:
        raise EcosystemSubmissionError("Cognitive Loop recipe replay runtime-required coverage drifted.")
    if set(replay.get("human_gate_recipe_ids", [])) != {"risk_decision"}:
        raise EcosystemSubmissionError("Cognitive Loop recipe replay human-gate coverage drifted.")
    policy = report.get("safe_replay_policy") or {}
    for key in ("metadata_replay_only", "requires_operator_for_runtime_commands", "requires_human_gate_for_risk_decisions"):
        if policy.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe replay policy {key} must be true.")
    for key in ("executes_recipe_commands", "starts_runtime", "applies_file_changes"):
        if policy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe replay policy {key} must be false.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe replay privacy.{key} must be false.")


def verify_cognitive_loop_skill_entrypoint_report() -> None:
    report = load_json(COGNITIVE_LOOP_SKILL_ENTRYPOINT_PATH)
    if report.get("schema_version") != "cognitive-loop-skill-entrypoint-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop Skill entrypoint report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop Skill entrypoint report must pass.")
    skill = report.get("skill") or {}
    if skill.get("path") != "skills/study-anything/SKILL.md":
        raise EcosystemSubmissionError("Cognitive Loop Skill entrypoint path drifted.")
    for key in (
        "mentions_cookbook",
        "mentions_recipe_matrix",
        "mentions_replay_report",
        "metadata_only_replay",
        "human_gate_explicit",
        "privacy_boundary_explicit",
    ):
        if skill.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint skill missing {key}.")
    if set(skill.get("recipe_ids", [])) != {"first_adoption", "daily_project_review", "risk_decision", "learning_handoff"}:
        raise EcosystemSubmissionError("Cognitive Loop Skill entrypoint recipe id coverage drifted.")

    readme_ids = {item.get("platform_id") for item in report.get("platform_pack_readmes", []) if isinstance(item, dict)}
    manifest_ids = {item.get("platform_id") for item in report.get("platform_pack_manifests", []) if isinstance(item, dict)}
    if readme_ids != {"codex", "kimi", "workbuddy"}:
        raise EcosystemSubmissionError("Cognitive Loop Skill entrypoint README coverage drifted.")
    if manifest_ids != {"codex", "kimi", "workbuddy"}:
        raise EcosystemSubmissionError("Cognitive Loop Skill entrypoint pack manifest coverage drifted.")
    for item in report.get("platform_pack_readmes", []):
        for key in ("mentions_cookbook", "mentions_recipe_matrix", "mentions_replay_report", "runs_skill_entrypoint_verifier"):
            if item.get(key) is not True:
                raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint README missing {key}.")
    for item in report.get("platform_pack_manifests", []):
        for key in ("imports_report", "runs_verifier", "accepts_schema"):
            if item.get(key) is not True:
                raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint pack manifest missing {key}.")

    index = report.get("platform_pack_index") or {}
    for key in ("mentions_report", "runs_verifier"):
        if index.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint platform pack index missing {key}.")
    ecosystem = report.get("ecosystem_submission") or {}
    for key in (
        "shared_assets_registered",
        "minimum_command_registered",
        "must_prove_registered",
        "submission_imports_registered",
    ):
        if ecosystem.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint ecosystem missing {key}.")
    distribution = report.get("distribution_sources") or {}
    for key in (
        "bundle_manifest_source_registered",
        "adoption_pack_source_registered",
        "release_check_registered",
        "platform_pack_verifier_registered",
        "ecosystem_submission_verifier_registered",
    ):
        if distribution.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint distribution missing {key}.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint privacy.{key} must be false.")
    boundaries = report.get("boundaries") or {}
    for key in (
        "platform_agent_owns_browser_files_apps_video_external_data",
        "study_anything_is_learning_adapter",
        "skill_entrypoint_is_recipe_index",
        "cognitive_loop_artifacts_are_metadata_only",
    ):
        if boundaries.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint boundary {key} must be true.")
    for key in (
        "mastra_runtime_shipped",
        "watcher_daemon_shipped",
        "realtime_html_console_shipped",
        "standalone_frontend_required",
    ):
        if boundaries.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop Skill entrypoint boundary {key} must be false.")


def verify_cognitive_loop_recipe_cli_report() -> None:
    report = load_json(COGNITIVE_LOOP_RECIPE_CLI_PATH)
    if report.get("schema_version") != "cognitive-loop-recipe-cli-verification-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI report schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI report must pass.")
    cli = report.get("cli") or {}
    if cli.get("path") != "scripts/cognitive_loop_recipe_cli.py":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI path drifted.")
    if cli.get("schema_version") != "cognitive-loop-recipe-cli-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI output schema drifted.")

    outputs = report.get("cli_outputs") or {}
    if outputs.get("list_schema_version") != "cognitive-loop-recipe-cli-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI list schema drifted.")
    if set(outputs.get("recipe_ids", [])) != {"first_adoption", "daily_project_review", "risk_decision", "learning_handoff"}:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI recipe ids drifted.")
    if outputs.get("recipe_count") != 4:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI recipe count drifted.")
    if outputs.get("all_steps_reference_existing_scripts") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI must prove command scripts exist.")
    if outputs.get("metadata_only") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI output must be metadata-only.")
    if outputs.get("executes_recipe_commands") is not False:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI must not execute recipe commands.")
    plans = {plan.get("recipe_id"): plan for plan in outputs.get("plans", []) if isinstance(plan, dict)}
    if plans.get("risk_decision", {}).get("requires_human_mastery_gate") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI risk_decision must require human mastery gate.")
    if plans.get("learning_handoff", {}).get("requires_operator_before_runtime") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI learning_handoff must require operator before runtime.")
    if plans.get("first_adoption", {}).get("requires_operator_before_runtime") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI first_adoption must require operator before runtime.")

    docs = report.get("entrypoint_docs") or {}
    if docs.get("cli_documented") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI must be documented.")
    if set(docs.get("checked_docs", [])) != {
        "skills/study-anything/SKILL.md",
        "platform/packs/codex/README.md",
        "platform/packs/kimi/README.md",
        "platform/packs/workbuddy/README.md",
    }:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI docs coverage drifted.")
    manifest_ids = {
        item.get("platform_id")
        for item in (report.get("platform_pack_manifests") or {}).get("packs", [])
        if isinstance(item, dict)
    }
    if manifest_ids != {"codex", "kimi", "workbuddy"}:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI pack manifest coverage drifted.")
    ecosystem = report.get("ecosystem_submission") or {}
    for key in (
        "shared_assets_registered",
        "minimum_command_registered",
        "must_prove_registered",
        "submission_imports_registered",
    ):
        if ecosystem.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI ecosystem missing {key}.")
    distribution = report.get("distribution_sources") or {}
    for key in (
        "bundle_manifest_source_registered",
        "adoption_pack_source_registered",
        "release_check_registered",
        "platform_pack_verifier_registered",
        "ecosystem_submission_verifier_registered",
    ):
        if distribution.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI distribution missing {key}.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI privacy.{key} must be false.")
    boundaries = report.get("boundaries") or {}
    for key in (
        "platform_agent_owns_browser_files_apps_video_external_data",
        "study_anything_is_learning_adapter",
        "recipe_cli_is_read_only",
    ):
        if boundaries.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI boundary {key} must be true.")
    for key in (
        "recipe_cli_executes_commands",
        "recipe_cli_applies_file_changes",
        "standalone_frontend_required",
    ):
        if boundaries.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI boundary {key} must be false.")


def verify_cognitive_loop_recipe_cli_receipts_report() -> None:
    report = load_json(COGNITIVE_LOOP_RECIPE_CLI_RECEIPTS_PATH)
    if report.get("schema_version") != "cognitive-loop-recipe-cli-receipts-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipts must pass.")
    cli = report.get("cli") or {}
    if cli.get("path") != "scripts/cognitive_loop_recipe_cli.py":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt path drifted.")
    if cli.get("schema_version") != "cognitive-loop-recipe-cli-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt output schema drifted.")

    coverage = report.get("coverage") or {}
    if coverage.get("receipt_count") != 5:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipts must cover list plus four show outputs.")
    if coverage.get("all_outputs_schema_version") != "cognitive-loop-recipe-cli-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt output schemas drifted.")
    if set(coverage.get("recipe_ids", [])) != {
        "first_adoption",
        "daily_project_review",
        "risk_decision",
        "learning_handoff",
    }:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt recipe ids drifted.")
    for key in (
        "includes_list",
        "includes_all_show_recipes",
        "includes_risk_decision_human_gate",
        "all_outputs_safe_to_attach_to_issue",
        "all_steps_reference_existing_scripts",
    ):
        if coverage.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI receipt coverage {key} must be true.")
    if coverage.get("all_show_outputs_safe_to_auto_execute") is not False:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI show receipts must not be safe to auto-execute.")
    if not coverage.get("list_stdout_sha256"):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI list receipt must include a stdout hash.")

    show = {item.get("recipe_id"): item for item in coverage.get("show_receipts", []) if isinstance(item, dict)}
    if show.get("risk_decision", {}).get("requires_human_mastery_gate") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI risk receipt must require Human Mastery Gate.")
    if show.get("first_adoption", {}).get("requires_operator_before_runtime") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI first adoption receipt must require operator.")
    if show.get("learning_handoff", {}).get("requires_operator_before_runtime") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI learning handoff receipt must require operator.")
    for item in show.values():
        if not item.get("stdout_sha256"):
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI show receipt missing stdout hash.")

    receipts = report.get("receipts")
    if not isinstance(receipts, list) or len(receipts) != 5:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipts must include five samples.")
    for receipt in receipts:
        if receipt.get("exit_code") != 0:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt exit_code must be zero.")
        if receipt.get("output_schema_version") != "cognitive-loop-recipe-cli-v1":
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt schema drifted.")
        if not receipt.get("stdout_sha256"):
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt missing stdout hash.")
        if receipt.get("safe_to_attach_to_issue") is not True:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipt must be safe to attach.")
    policy = report.get("safe_replay_policy") or {}
    if policy.get("invokes_recipe_cli_only") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI receipts must invoke only the read-only CLI.")
    for key in ("executes_recipe_commands", "starts_runtime", "applies_file_changes"):
        if policy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI receipt policy {key} must be false.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI receipt privacy.{key} must be false.")
    boundaries = report.get("boundaries") or {}
    for key in (
        "platform_agent_owns_browser_files_apps_video_external_data",
        "study_anything_is_learning_adapter",
        "recipe_cli_receipts_are_read_only",
    ):
        if boundaries.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI receipt boundary {key} must be true.")
    for key in (
        "recipe_cli_receipts_execute_recipe_commands",
        "recipe_cli_receipts_apply_file_changes",
        "standalone_frontend_required",
    ):
        if boundaries.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI receipt boundary {key} must be false.")


def verify_cognitive_loop_recipe_cli_failures_report() -> None:
    report = load_json(COGNITIVE_LOOP_RECIPE_CLI_FAILURES_PATH)
    if report.get("schema_version") != "cognitive-loop-recipe-cli-failures-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failures must pass.")
    cli = report.get("cli") or {}
    if cli.get("path") != "scripts/cognitive_loop_recipe_cli.py":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure path drifted.")
    if cli.get("success_schema_version") != "cognitive-loop-recipe-cli-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure success schema drifted.")
    if cli.get("failure_surface") != "nonzero_exit_with_redacted_stderr":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure surface drifted.")

    coverage = report.get("coverage") or {}
    expected_ids = {
        "unknown_recipe_id",
        "source_schema_drift",
        "source_status_failed",
        "empty_recipe_matrix",
    }
    if coverage.get("case_count") != len(expected_ids):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure case count drifted.")
    if set(coverage.get("case_ids", [])) != expected_ids:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure case ids drifted.")
    for key in (
        "all_exit_nonzero",
        "all_stdout_empty",
        "all_stderr_redacted",
        "all_safe_to_attach_to_issue",
    ):
        if coverage.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI failure coverage {key} must be true.")

    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != len(expected_ids):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure cases must include four samples.")
    for case in cases:
        if case.get("case_id") not in expected_ids:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure includes unknown case id.")
        if not isinstance(case.get("exit_code"), int) or case.get("exit_code") == 0:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure exit_code must be non-zero.")
        if case.get("stdout_empty") is not True:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure stdout must be empty.")
        if not case.get("stderr_sha256"):
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure missing stderr hash.")
        if case.get("safe_to_attach_to_issue") is not True:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure must be safe to attach.")
        stderr = str(case.get("stderr", ""))
        if "cognitive_loop_recipe_cli failed:" not in stderr:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure stderr prefix drifted.")
        if "recipe-cli-negative-" in stderr:
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI failure leaked temp fixture path.")

    policy = report.get("safe_failure_policy") or {}
    for key in (
        "invokes_recipe_cli_only",
        "writes_only_temporary_negative_fixtures",
        "temporary_negative_fixtures_removed",
    ):
        if policy.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI failure policy {key} must be true.")
    for key in ("executes_recipe_commands", "starts_runtime", "applies_file_changes"):
        if policy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI failure policy {key} must be false.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI failure privacy.{key} must be false.")


def verify_cognitive_loop_recipe_cli_schemas_report() -> None:
    report = load_json(COGNITIVE_LOOP_RECIPE_CLI_SCHEMAS_PATH)
    if report.get("schema_version") != "cognitive-loop-recipe-cli-schemas-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema bundle schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema bundle must pass.")

    json_schema = report.get("json_schema") or {}
    expected_keys = {
        "cognitive_loop_recipe_cli_verification",
        "cognitive_loop_recipe_cli_receipts",
        "cognitive_loop_recipe_cli_failures",
    }
    if json_schema.get("dialect") != "https://json-schema.org/draft/2020-12/schema":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema dialect drifted.")
    if json_schema.get("schema_count") != len(expected_keys):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema count drifted.")
    if set(json_schema.get("schema_keys", [])) != expected_keys:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema keys drifted.")
    schemas = json_schema.get("schemas")
    if not isinstance(schemas, dict) or set(schemas) != expected_keys:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema objects drifted.")

    validation = report.get("validation") or {}
    for key in ("validated_without_running_recipe_cli",):
        if validation.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI schema validation {key} must be true.")
    for key in ("recipe_cli_invoked", "runtime_started", "file_changes_applied"):
        if validation.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI schema validation {key} must be false.")
    reports = validation.get("reports")
    if not isinstance(reports, list):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema validation reports must be a list.")
    expected_reports = {
        (
            "cognitive_loop_recipe_cli_verification",
            "platform/generated/study-anything-cognitive-loop-recipe-cli.json",
            "cognitive-loop-recipe-cli-verification-v1",
        ),
        (
            "cognitive_loop_recipe_cli_receipts",
            "platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json",
            "cognitive-loop-recipe-cli-receipts-v1",
        ),
        (
            "cognitive_loop_recipe_cli_failures",
            "platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json",
            "cognitive-loop-recipe-cli-failures-v1",
        ),
    }
    actual_reports = {
        (item.get("schema_key"), item.get("path"), item.get("schema_version"))
        for item in reports
        if isinstance(item, dict) and item.get("status") == "pass"
    }
    if actual_reports != expected_reports:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema validation report set drifted.")

    distribution = report.get("distribution") or {}
    if (
        distribution.get("schema_bundle_path")
        != "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json"
    ):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema bundle path drifted.")
    if distribution.get("safe_for_platform_agent_static_import") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schemas must be safe for static import.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI schema privacy.{key} must be false.")


def verify_cognitive_loop_recipe_cli_schema_negative_fixtures_report() -> None:
    report = load_json(COGNITIVE_LOOP_RECIPE_CLI_SCHEMA_NEGATIVE_FIXTURES_PATH)
    if report.get("schema_version") != "cognitive-loop-recipe-cli-schema-negative-fixtures-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema negative fixture schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI schema negative fixture report must pass.")

    source_schema_bundle = report.get("source_schema_bundle") or {}
    if (
        source_schema_bundle.get("path")
        != "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json"
    ):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixtures source bundle path drifted.")
    if source_schema_bundle.get("schema_version") != "cognitive-loop-recipe-cli-schemas-v1":
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixtures source schema version drifted.")
    expected_schema_keys = {
        "cognitive_loop_recipe_cli_verification",
        "cognitive_loop_recipe_cli_receipts",
        "cognitive_loop_recipe_cli_failures",
    }
    if set(source_schema_bundle.get("schema_keys", [])) != expected_schema_keys:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixtures source schema keys drifted.")

    coverage = report.get("coverage") or {}
    expected_case_ids = {
        "success_wrong_schema_version",
        "success_auto_execute_true",
        "receipts_missing_privacy",
        "failures_exit_code_string",
        "private_text_probe_rejected",
    }
    if coverage.get("case_count") != len(expected_case_ids):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixture count drifted.")
    if set(coverage.get("case_ids", [])) != expected_case_ids:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixture case IDs drifted.")
    for key in (
        "all_cases_rejected",
        "all_expected_errors_matched",
        "all_errors_redacted",
        "validated_without_running_recipe_cli",
    ):
        if coverage.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI negative fixture coverage {key} must be true.")
    for key in ("mutated_payloads_persisted", "recipe_cli_invoked", "runtime_started", "file_changes_applied"):
        if coverage.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI negative fixture coverage {key} must be false.")

    canonical_reports = coverage.get("canonical_reports_validated")
    if not isinstance(canonical_reports, list):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixtures must validate canonical reports.")
    expected_reports = {
        (
            "cognitive_loop_recipe_cli_verification",
            "platform/generated/study-anything-cognitive-loop-recipe-cli.json",
            "cognitive-loop-recipe-cli-verification-v1",
        ),
        (
            "cognitive_loop_recipe_cli_receipts",
            "platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json",
            "cognitive-loop-recipe-cli-receipts-v1",
        ),
        (
            "cognitive_loop_recipe_cli_failures",
            "platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json",
            "cognitive-loop-recipe-cli-failures-v1",
        ),
    }
    actual_reports = {
        (item.get("schema_key"), item.get("path"), item.get("schema_version"))
        for item in canonical_reports
        if isinstance(item, dict) and item.get("status") == "pass"
    }
    if actual_reports != expected_reports:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixtures canonical reports drifted.")

    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != len(expected_case_ids):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixture cases must be complete.")
    for case in cases:
        if not isinstance(case, dict):
            raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixture case must be an object.")
        case_id = case.get("case_id")
        if case_id not in expected_case_ids:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI negative fixture unknown case: {case_id}")
        if case.get("rejected") is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI negative fixture {case_id} must be rejected.")
        if case.get("mutated_payload_persisted") is not False:
            raise EcosystemSubmissionError(
                f"Cognitive Loop recipe CLI negative fixture {case_id} must not persist mutated payloads."
            )
        if case.get("safe_to_attach_to_issue") is not True:
            raise EcosystemSubmissionError(
                f"Cognitive Loop recipe CLI negative fixture {case_id} must be safe to attach."
            )
        if not isinstance(case.get("error_sha256"), str) or len(case["error_sha256"]) != 64:
            raise EcosystemSubmissionError(f"Cognitive Loop recipe CLI negative fixture {case_id} must hash errors.")

    distribution = report.get("distribution") or {}
    if (
        distribution.get("negative_fixture_report_path")
        != "platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json"
    ):
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixture path drifted.")
    if distribution.get("safe_for_platform_agent_static_import") is not True:
        raise EcosystemSubmissionError("Cognitive Loop recipe CLI negative fixtures must be safe for static import.")

    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(
                f"Cognitive Loop recipe CLI negative fixture privacy.{key} must be false."
            )


def verify_cognitive_loop_schema_pack_consumer_report() -> None:
    report = load_json(COGNITIVE_LOOP_SCHEMA_PACK_CONSUMER_PATH)
    if report.get("schema_version") != "cognitive-loop-schema-pack-consumer-v1":
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer schema drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer report must pass.")

    pack = report.get("pack") or {}
    if pack.get("path") != "platform/generated/study-anything-platform-adoption-pack.zip":
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer pack path drifted.")
    if pack.get("manifest_schema_version") != "study-anything-platform-adoption-pack-v1":
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer manifest schema drifted.")
    if pack.get("no_frontend_required") is not True:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer must preserve no-frontend path.")
    if pack.get("real_model_keys_stored_by_study_anything") is not False:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer must not store real model keys.")

    zip_only = report.get("zip_only_validation") or {}
    for key in ("manifest_records_checked", "archive_asset_hashes_match"):
        if zip_only.get(key) is not True:
            raise EcosystemSubmissionError(f"Cognitive Loop schema pack consumer zip_only_validation.{key} must be true.")
    for key in ("repo_checkout_required", "recipe_cli_invoked", "runtime_started", "file_changes_applied"):
        if zip_only.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop schema pack consumer zip_only_validation.{key} must be false.")
    files_read = set(zip_only.get("files_read_from_zip", []))
    expected_files = {
        "study-anything-platform-adoption-pack/manifest.json",
        "study-anything-platform-adoption-pack/platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json",
        (
            "study-anything-platform-adoption-pack/platform/generated/"
            "study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json"
        ),
    }
    if files_read != expected_files:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer zip file set drifted.")

    schema_bundle = report.get("schema_bundle") or {}
    if schema_bundle.get("schema_version") != "cognitive-loop-recipe-cli-schemas-v1":
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer schema bundle version drifted.")
    if schema_bundle.get("schema_count") != 3:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer schema count drifted.")
    if schema_bundle.get("validated_without_running_recipe_cli") is not True:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer must validate without running recipe CLI.")

    negative_fixtures = report.get("negative_fixtures") or {}
    if negative_fixtures.get("schema_version") != "cognitive-loop-recipe-cli-schema-negative-fixtures-v1":
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer negative fixture version drifted.")
    if negative_fixtures.get("case_count") != 5:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer negative fixture count drifted.")
    if negative_fixtures.get("all_cases_rejected") is not True:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer negative fixtures must reject all cases.")

    distribution = report.get("distribution") or {}
    if distribution.get("report_path") != "platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json":
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer report path drifted.")
    if distribution.get("safe_for_platform_agent_static_import") is not True:
        raise EcosystemSubmissionError("Cognitive Loop schema pack consumer must be safe for static import.")

    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_private_insights_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "real_model_keys_stored",
        "browser_video_app_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Cognitive Loop schema pack consumer privacy.{key} must be false.")


def verify_submission_dry_run_report() -> None:
    report = load_json(SUBMISSION_DRY_RUN_PATH)
    if report.get("schema_version") != "platform-submission-dry-run-v1":
        raise EcosystemSubmissionError("Platform submission dry-run report schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform submission dry-run report version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Platform submission dry-run report must pass.")
    if report.get("blocked_platforms"):
        raise EcosystemSubmissionError("Platform submission dry-run report has blocked platforms.")
    platforms = report.get("platforms")
    if not isinstance(platforms, dict) or set(platforms) != REQUIRED_PLATFORMS:
        raise EcosystemSubmissionError("Platform submission dry-run report platform set drifted.")
    privacy = report.get("privacy") or {}
    for key in (
        "real_model_keys_stored_by_study_anything",
        "agent_endpoint_secrets_in_report",
        "raw_learning_data_in_report",
        "management_endpoints_exposed_to_platform_tools",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Platform submission dry-run privacy.{key} must be false.")


def verify_manual_rehearsal_report() -> None:
    report = load_json(MANUAL_REHEARSAL_PATH)
    if report.get("schema_version") != "platform-manual-submission-rehearsal-v1":
        raise EcosystemSubmissionError("Manual submission rehearsal report schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Manual submission rehearsal report version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Manual submission rehearsal report must pass.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_returned",
        "learner_answers_returned",
        "agent_endpoint_secrets_returned",
        "real_model_keys_stored_by_study_anything",
        "browser_video_private_context_returned",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Manual rehearsal privacy.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise EcosystemSubmissionError("Manual rehearsal report must be redacted.")


def verify_first_lesson_kit_report() -> None:
    report = load_json(FIRST_LESSON_KIT_PATH)
    if report.get("schema_version") != "first-run-lesson-authoring-kit-v1":
        raise EcosystemSubmissionError("First lesson authoring kit schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("First lesson authoring kit version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("First lesson authoring kit must pass.")
    prompts = report.get("copyable_prompts") or {}
    if set(prompts) != {"en", "zh"}:
        raise EcosystemSubmissionError("First lesson kit must include zh and en copyable prompts.")
    if len(report.get("tool_call_sequence", [])) < 10:
        raise EcosystemSubmissionError("First lesson kit tool call sequence is too short.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "copyable_prompts_include_real_model_keys",
        "context_template_contains_raw_source",
        "agent_endpoint_secrets_returned",
        "learner_answers_returned",
        "browser_video_private_context_returned",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"First lesson kit privacy.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise EcosystemSubmissionError("First lesson kit report must be redacted.")


def verify_external_eval_harness_report() -> None:
    report = load_json(EXTERNAL_EVAL_HARNESS_PATH)
    if report.get("schema_version") != "external-eval-marketplace-harness-v1":
        raise EcosystemSubmissionError("External eval marketplace harness schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("External eval marketplace harness version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("External eval marketplace harness must pass.")
    adapter_ids = {
        str(item.get("adapter_id"))
        for item in report.get("external_adapters", [])
        if isinstance(item, dict)
    }
    if adapter_ids != {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}:
        raise EcosystemSubmissionError(f"External eval harness adapter set drifted: {sorted(adapter_ids)}")
    required_gates = [
        gate
        for gate in report.get("native_fast_gates", [])
        if isinstance(gate, dict) and gate.get("required")
    ]
    if len(required_gates) < 4:
        raise EcosystemSubmissionError("External eval harness must include required native gates.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_or_judge_keys_stored_by_study_anything",
        "raw_source_text_in_eval_harness",
        "learner_answers_in_eval_harness",
        "agent_endpoint_secrets_in_eval_harness",
        "raw_agent_metadata_in_eval_harness",
        "browser_video_private_context_in_eval_harness",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"External eval harness privacy.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise EcosystemSubmissionError("External eval harness report must be redacted.")


def verify_agent_eval_marketplace_enforcement_report() -> None:
    report = load_json(AGENT_EVAL_MARKETPLACE_ENFORCEMENT_PATH)
    if report.get("schema_version") != "agent-eval-marketplace-enforcement-v1":
        raise EcosystemSubmissionError("Agent eval marketplace enforcement schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Agent eval marketplace enforcement version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Agent eval marketplace enforcement must pass.")

    runner = report.get("runner_contract") or {}
    if runner.get("required_flag_blocks_non_ok") is not True:
        raise EcosystemSubmissionError("Agent eval enforcement must prove required-mode failures block.")
    if runner.get("timeout_flag_present") is not True:
        raise EcosystemSubmissionError("Agent eval enforcement must prove timeout controls.")
    if runner.get("missing_runtime_diagnostic_present") is not True:
        raise EcosystemSubmissionError("Agent eval enforcement must prove missing-runtime diagnostics.")

    baseline = report.get("baseline_and_harness") or {}
    if baseline.get("harness_schema") != "external-eval-marketplace-harness-v1":
        raise EcosystemSubmissionError("Agent eval enforcement harness linkage drifted.")
    adapter_ids = set(str(item) for item in baseline.get("adapter_ids", []))
    expected_adapters = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
    if adapter_ids != expected_adapters:
        raise EcosystemSubmissionError(
            f"Agent eval enforcement adapter inventory drifted: {sorted(adapter_ids)}"
        )

    runtime = ((report.get("runtime_diagnostics") or {}).get("promptfoo_missing_runtime") or {})
    if runtime.get("required_exit_nonzero") is not True:
        raise EcosystemSubmissionError("Agent eval enforcement must prove required Promptfoo failure.")
    if runtime.get("optional_status") not in {"skipped", "not_run_against_pack"}:
        raise EcosystemSubmissionError("Agent eval enforcement optional Promptfoo diagnostic drifted.")

    contracts = report.get("external_judge_contracts")
    if not isinstance(contracts, list) or len(contracts) != len(expected_adapters):
        raise EcosystemSubmissionError("Agent eval enforcement external judge contracts drifted.")
    contract_ids = {str(item.get("adapter_id")) for item in contracts if isinstance(item, dict)}
    if contract_ids != expected_adapters:
        raise EcosystemSubmissionError(f"Agent eval enforcement contract IDs drifted: {sorted(contract_ids)}")
    for item in contracts:
        if not isinstance(item, dict):
            continue
        if item.get("credentials_stored_by_study_anything") is not False:
            raise EcosystemSubmissionError("Agent eval enforcement must keep judge credentials outside.")

    adoption_pack = report.get("adoption_pack") or {}
    if adoption_pack.get("included") is not True:
        raise EcosystemSubmissionError("Agent eval enforcement must be included in the adoption pack.")

    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_or_judge_keys_stored_by_study_anything",
        "judge_api_keys_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_endpoint_secrets_in_report",
        "browser_video_private_context_in_report",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Agent eval enforcement privacy.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise EcosystemSubmissionError("Agent eval enforcement report must be redacted.")


def verify_platform_adoption_feedback_diagnostics_report() -> None:
    report = load_json(PLATFORM_ADOPTION_FEEDBACK_DIAGNOSTICS_PATH)
    if report.get("schema_version") != "platform-adoption-feedback-diagnostics-v1":
        raise EcosystemSubmissionError("Platform adoption feedback diagnostics schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform adoption feedback diagnostics version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Platform adoption feedback diagnostics must pass.")

    diagnostic = report.get("diagnostic_contract") or {}
    categories = set(str(item) for item in diagnostic.get("diagnostic_categories", []))
    required = {
        "pack_schema_invalid",
        "openapi_import_missing_operation",
        "openai_tools_malformed",
        "unsupported_platform_capability",
        "localhost_api_unreachable",
        "agent_endpoint_unreachable",
        "agent_eval_evidence_missing",
        "version_drift",
        "missing_required_command",
        "privacy_contract_violation",
    }
    if required - categories:
        raise EcosystemSubmissionError(
            f"Platform adoption feedback diagnostics missing categories: {sorted(required - categories)}"
        )

    feedback = report.get("feedback_package") or {}
    if feedback.get("included") is not True:
        raise EcosystemSubmissionError("Platform adoption feedback diagnostics must include feedback package evidence.")
    adoption = report.get("adoption_pack") or {}
    if adoption.get("included") is not True:
        raise EcosystemSubmissionError("Platform adoption feedback diagnostics must be included in the adoption pack.")

    privacy = report.get("privacy_assertions") or {}
    for key in (
        "automatic_feedback_upload",
        "real_model_keys_in_feedback",
        "agent_endpoint_secrets_in_feedback",
        "raw_source_text_in_feedback",
        "learner_answers_in_feedback",
        "agent_prompts_in_feedback",
        "personal_profile_in_feedback",
        "browser_video_private_context_in_feedback",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Platform feedback diagnostics privacy.{key} must be false.")
    if privacy.get("feedback_package_is_redacted") is not True:
        raise EcosystemSubmissionError("Platform feedback diagnostics package must be redacted.")


def verify_platform_feedback_package() -> None:
    package = load_json(PLATFORM_FEEDBACK_PACKAGE_PATH)
    if package.get("schema_version") != "platform-feedback-package-v1":
        raise EcosystemSubmissionError("Platform feedback package schema drifted.")
    if package.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform feedback package version drifted.")
    if not PLATFORM_FEEDBACK_PACKAGE_ARCHIVE.is_file():
        raise EcosystemSubmissionError("Platform feedback package archive missing.")
    if len(package.get("diagnostic_categories", [])) < 8:
        raise EcosystemSubmissionError("Platform feedback package must include diagnostic categories.")
    privacy = package.get("privacy") or {}
    for key in (
        "automatic_upload",
        "raw_source_text_included",
        "learner_answers_included",
        "agent_prompts_included",
        "real_model_keys_included",
        "agent_endpoint_secrets_included",
        "personal_profile_included",
        "browser_video_private_context_included",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Platform feedback package privacy.{key} must be false.")
    if privacy.get("redacted") is not True:
        raise EcosystemSubmissionError("Platform feedback package must be redacted.")


def verify_platform_field_rehearsal_report() -> None:
    report = load_json(PLATFORM_FIELD_REHEARSAL_PATH)
    if report.get("schema_version") != "platform-field-adoption-rehearsal-v1":
        raise EcosystemSubmissionError("Platform field rehearsal schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform field rehearsal version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Platform field rehearsal report must pass.")
    platforms = report.get("platforms")
    if not isinstance(platforms, list) or len(platforms) != 4:
        raise EcosystemSubmissionError("Platform field rehearsal must cover four platform modes.")
    platform_ids = {str(item.get("platform_id")) for item in platforms if isinstance(item, dict)}
    if platform_ids != {"kimi", "codex", "workbuddy", "generic"}:
        raise EcosystemSubmissionError(f"Platform field rehearsal platform ids drifted: {sorted(platform_ids)}")
    quirks = report.get("quirks_catalog")
    if not isinstance(quirks, list) or len(quirks) < 8:
        raise EcosystemSubmissionError("Platform field rehearsal must include an import quirks catalog.")
    fixtures = report.get("failed_import_fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != len(quirks):
        raise EcosystemSubmissionError("Platform field rehearsal fixture count must match quirks catalog.")
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise EcosystemSubmissionError("Platform field rehearsal fixtures must be objects.")
        path = fixture.get("path")
        if not isinstance(path, str):
            raise EcosystemSubmissionError("Platform field rehearsal fixture path missing.")
        require_file(path, label="platform_field_rehearsal.fixture")
        payload = load_json(ROOT / path)
        if payload.get("schema_version") != "platform-import-failure-fixture-v1":
            raise EcosystemSubmissionError(f"Platform import failure fixture schema drifted: {path}")
        diagnosis = payload.get("diagnosis") or {}
        if not diagnosis.get("detection_signal") or not diagnosis.get("next_commands"):
            raise EcosystemSubmissionError(f"Platform import failure fixture is not actionable: {path}")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_in_report",
        "agent_endpoint_secrets_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "browser_video_private_context_in_report",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Platform field rehearsal privacy.{key} must be false.")
    if privacy.get("fixtures_are_mock_only") is not True:
        raise EcosystemSubmissionError("Platform import failure fixtures must be mock-only.")


def verify_platform_support_triage_report() -> None:
    report = load_json(PLATFORM_SUPPORT_TRIAGE_PATH)
    if report.get("schema_version") != "platform-support-triage-v1":
        raise EcosystemSubmissionError("Platform support triage schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform support triage version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Platform support triage report must pass.")

    categories = {
        str(item.get("category_id"))
        for item in report.get("issue_templates", [])
        if isinstance(item, dict)
    }
    expected_categories = {
        "platform_import_failure",
        "local_gateway_failure",
        "published_image_pull_failure",
        "agent_eval_evidence_failure",
        "docs_confusion",
    }
    if categories != expected_categories:
        raise EcosystemSubmissionError(f"Platform support triage categories drifted: {sorted(categories)}")
    for category in expected_categories:
        require_file(f".github/ISSUE_TEMPLATE/{category}.md", label="platform_support_triage.issue_template")
        require_file(f"fixtures/platform-support-tickets/{category}.json", label="platform_support_triage.ticket")

    contract = report.get("support_bundle_contract") or {}
    required_fields = set(str(item) for item in contract.get("required_fields", []))
    expected_fields = {
        "release_version",
        "platform_id",
        "command_ran",
        "diagnostic_code",
        "fixture_id",
        "redacted_log_excerpt",
        "next_commands_tried",
    }
    if required_fields != expected_fields:
        raise EcosystemSubmissionError("Platform support triage support-bundle fields drifted.")
    if contract.get("automatic_upload") is not False or contract.get("safe_handoff_only") is not True:
        raise EcosystemSubmissionError("Platform support triage must remain manual and safe.")

    playbook = report.get("maintainer_playbook")
    if not isinstance(playbook, list) or len(playbook) != 8:
        raise EcosystemSubmissionError("Platform support triage playbook must cover eight import quirks.")
    for item in playbook:
        if not isinstance(item, dict):
            raise EcosystemSubmissionError("Platform support triage playbook entries must be objects.")
        if not item.get("first_response") or not item.get("reproduction_steps"):
            raise EcosystemSubmissionError("Platform support triage playbook entries must be actionable.")
        if not item.get("close_when") or not item.get("escalate_when"):
            raise EcosystemSubmissionError("Platform support triage playbook entries must define closure.")

    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_in_report",
        "agent_endpoint_secrets_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "browser_video_private_context_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Platform support triage privacy.{key} must be false.")
    if privacy.get("fixtures_are_mock_only") is not True:
        raise EcosystemSubmissionError("Platform support triage fixtures must be mock-only.")


def verify_platform_onboarding_readiness_report() -> None:
    report = load_json(PLATFORM_ONBOARDING_READINESS_PATH)
    if report.get("schema_version") != "platform-onboarding-readiness-v1":
        raise EcosystemSubmissionError("Platform onboarding readiness schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform onboarding readiness version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Platform onboarding readiness report must pass.")

    walkthrough = report.get("walkthrough") or {}
    if walkthrough.get("schema_version") != "first-external-adopter-walkthrough-v1":
        raise EcosystemSubmissionError("Platform onboarding walkthrough schema drifted.")
    platforms = {
        str(item.get("platform_id"))
        for item in walkthrough.get("platforms", [])
        if isinstance(item, dict)
    }
    if platforms != {"kimi", "codex", "workbuddy", "generic"}:
        raise EcosystemSubmissionError(
            f"Platform onboarding walkthrough platforms drifted: {sorted(platforms)}"
        )

    sla = report.get("maintainer_sla") or {}
    if sla.get("schema_version") != "maintainer-sla-labels-v1":
        raise EcosystemSubmissionError("Maintainer SLA schema drifted.")
    labels = {str(item.get("label")) for item in sla.get("labels", []) if isinstance(item, dict)}
    expected_labels = {
        "intake",
        "needs-repro",
        "confirmed",
        "blocked-by-platform",
        "docs-fix",
        "release-blocker",
        "resolved",
    }
    if labels != expected_labels:
        raise EcosystemSubmissionError(f"Maintainer SLA labels drifted: {sorted(labels)}")

    dashboard = load_json(PLATFORM_TRIAGE_DASHBOARD_PATH)
    if dashboard.get("schema_version") != "platform-triage-dashboard-v1":
        raise EcosystemSubmissionError("Platform triage dashboard schema drifted.")
    if dashboard.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform triage dashboard version drifted.")
    blockers = report.get("release_blocker_fixtures")
    if not isinstance(blockers, list) or len(blockers) != 5:
        raise EcosystemSubmissionError("Platform onboarding release blocker fixture count drifted.")
    for item in blockers:
        if not isinstance(item, dict):
            raise EcosystemSubmissionError("Platform onboarding release blocker entries must be objects.")
        path = item.get("path")
        if not isinstance(path, str):
            raise EcosystemSubmissionError("Platform onboarding release blocker path missing.")
        require_file(path, label="platform_onboarding.release_blocker")
        payload = load_json(ROOT / path)
        if payload.get("schema_version") != "platform-release-blocker-fixture-v1":
            raise EcosystemSubmissionError(f"Release blocker fixture schema drifted: {path}")
        if payload.get("linked_support_category") not in {
            "platform_import_failure",
            "local_gateway_failure",
            "published_image_pull_failure",
            "agent_eval_evidence_failure",
            "docs_confusion",
        }:
            raise EcosystemSubmissionError(f"Release blocker fixture support category drifted: {path}")

    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_in_report",
        "agent_endpoint_secrets_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "browser_video_private_context_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Platform onboarding readiness privacy.{key} must be false.")
    if privacy.get("fixtures_are_mock_only") is not True:
        raise EcosystemSubmissionError("Platform onboarding readiness fixtures must be mock-only.")


def verify_public_support_status_report() -> None:
    report = load_json(PUBLIC_SUPPORT_STATUS_PATH)
    if report.get("schema_version") != "public-support-status-v1":
        raise EcosystemSubmissionError("Public support status schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Public support status version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Public support status must pass.")
    source_reports = report.get("source_reports") or {}
    expected_sources = {
        "onboarding_readiness_schema": "platform-onboarding-readiness-v1",
        "support_triage_schema": "platform-support-triage-v1",
        "triage_dashboard_schema": "platform-triage-dashboard-v1",
    }
    for key, expected in expected_sources.items():
        if source_reports.get(key) != expected:
            raise EcosystemSubmissionError(f"Public support status source {key} drifted.")
    platforms = {
        str(item.get("platform_id"))
        for item in report.get("platform_statuses", [])
        if isinstance(item, dict)
    }
    if platforms != {"kimi", "codex", "workbuddy", "generic"}:
        raise EcosystemSubmissionError(f"Public support platform coverage drifted: {sorted(platforms)}")
    blockers = {
        str(item.get("blocker_id"))
        for item in report.get("known_blockers", [])
        if isinstance(item, dict)
    }
    if blockers != {
        "tool_import_blocker",
        "local_gateway_blocker",
        "published_image_blocker",
        "agent_eval_blocker",
        "support_bundle_privacy_blocker",
    }:
        raise EcosystemSubmissionError(f"Public blocker coverage drifted: {sorted(blockers)}")
    sla = report.get("maintainer_sla") or {}
    labels = set(str(item) for item in sla.get("labels", []))
    expected_labels = {
        "intake",
        "needs-repro",
        "confirmed",
        "blocked-by-platform",
        "docs-fix",
        "release-blocker",
        "resolved",
    }
    if labels != expected_labels:
        raise EcosystemSubmissionError(f"Public status SLA labels drifted: {sorted(labels)}")
    for label in expected_labels:
        payload = load_json(ROOT / "fixtures" / "platform-status-links" / f"{label}.json")
        if payload.get("schema_version") != "public-status-linkage-fixture-v1":
            raise EcosystemSubmissionError(f"Public status linkage schema drifted: {label}")
        if payload.get("version") != "v0.3.30-alpha":
            raise EcosystemSubmissionError(f"Public status linkage version drifted: {label}")
    dashboard = load_json(PUBLIC_MAINTAINER_DASHBOARD_PATH)
    if dashboard.get("schema_version") != "public-maintainer-dashboard-v1":
        raise EcosystemSubmissionError("Public maintainer dashboard schema drifted.")
    if dashboard.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Public maintainer dashboard version drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "agent_endpoint_secrets_in_report",
        "real_model_keys_in_report",
        "browser_video_private_context_in_report",
        "personal_profile_data_in_report",
        "support_bundle_private_fields_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Public support status privacy.{key} must be false.")


def verify_adopter_evidence_archive_report() -> None:
    report = load_json(ADOPTER_EVIDENCE_ARCHIVE_PATH)
    if report.get("schema_version") != "adopter-evidence-archive-v1":
        raise EcosystemSubmissionError("Adopter evidence archive schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Adopter evidence archive version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Adopter evidence archive must pass.")
    release_identity = report.get("release_identity") or {}
    if release_identity.get("tag") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Adopter evidence archive release tag drifted.")
    source_schemas = report.get("source_schemas") or {}
    expected_sources = {
        "public_support_status": "public-support-status-v1",
        "public_maintainer_dashboard": "public-maintainer-dashboard-v1",
        "published_image_evidence": "published-image-evidence-v1",
        "platform_adoption_pack": "study-anything-platform-adoption-pack-v1",
        "ecosystem_submission": "ecosystem-submission-v1",
    }
    for key, expected in expected_sources.items():
        if (source_schemas.get(key) or {}).get("schema_version") != expected:
            raise EcosystemSubmissionError(f"Adopter evidence archive source {key} drifted.")
    fixture_ids = {
        str(item.get("fixture_id"))
        for item in report.get("fixture_refs", [])
        if isinstance(item, dict)
    }
    expected_fixtures = {
        "successful-release",
        "local-ghcr-pull-timeout",
        "needs-repro-issue",
        "release-blocker",
        "platform-blocked",
        "resolved-support-case",
    }
    if fixture_ids != expected_fixtures:
        raise EcosystemSubmissionError(f"Adopter evidence fixture coverage drifted: {sorted(fixture_ids)}")
    for fixture_id in expected_fixtures:
        payload = load_json(ROOT / "fixtures" / "adopter-evidence-archive" / f"{fixture_id}.json")
        if payload.get("schema_version") != "adopter-evidence-fixture-v1":
            raise EcosystemSubmissionError(f"Adopter evidence fixture schema drifted: {fixture_id}")
        if payload.get("version") != "v0.3.30-alpha":
            raise EcosystemSubmissionError(f"Adopter evidence fixture version drifted: {fixture_id}")
    archive = report.get("archive") or {}
    archive_path = ROOT / "platform" / "generated" / "study-anything-adopter-evidence-archive.zip"
    checksum_path = ROOT / "platform" / "generated" / "study-anything-adopter-evidence-archive.sha256"
    if not archive_path.is_file() or not checksum_path.is_file():
        raise EcosystemSubmissionError("Adopter evidence archive zip/checksum missing.")
    if archive.get("sha256") not in checksum_path.read_text(encoding="utf-8"):
        raise EcosystemSubmissionError("Adopter evidence archive checksum sidecar drifted.")
    commands = "\n".join(str(item) for item in (report.get("operator_reproduction") or {}).get("minimum_commands", []))
    for command in (
        "verify_adopter_evidence_archive.py --check",
        "generate_adopter_evidence_archive.py --check",
        "verify_published_image_evidence.py --check",
        "generate_published_image_evidence.py --check",
    ):
        if command not in commands:
            raise EcosystemSubmissionError(f"Adopter evidence archive missing command {command}.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_in_archive",
        "learner_answers_in_archive",
        "agent_prompts_in_archive",
        "agent_endpoint_secrets_in_archive",
        "real_model_keys_in_archive",
        "browser_video_private_context_in_archive",
        "personal_profile_data_in_archive",
        "support_bundle_private_payload_in_archive",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Adopter evidence archive privacy.{key} must be false.")


def verify_published_image_evidence_report() -> None:
    report = load_json(PUBLISHED_IMAGE_EVIDENCE_PATH)
    if report.get("schema_version") != "published-image-evidence-v1":
        raise EcosystemSubmissionError("Published-image evidence schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Published-image evidence version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Published-image evidence must pass.")
    release_identity = report.get("release_identity") or {}
    if release_identity.get("tag") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Published-image evidence release tag drifted.")
    manifest = report.get("manifest_evidence") or {}
    if set(str(item) for item in manifest.get("required_platforms", [])) != {"linux/amd64", "linux/arm64"}:
        raise EcosystemSubmissionError("Published-image evidence required platform coverage drifted.")
    local_smoke = report.get("local_smoke_evidence") or {}
    if local_smoke.get("timeout_status") != "blocked_by_local_ghcr_pull":
        raise EcosystemSubmissionError("Published-image evidence timeout classification drifted.")
    expected_classifications = {
        "published_image_ready",
        "local_pull_timeout_with_valid_release_evidence",
        "cached_image_missing",
        "compose_up_timeout",
        "manifest_available_runtime_unverified",
        "published_image_platform_gap",
        "ci_image_publish_failed",
        "registry_or_network_unavailable",
        "published_image_runtime_failed",
    }
    matrix = report.get("classification_matrix") or []
    matrix_classes = {str(item.get("classification")) for item in matrix if isinstance(item, dict)}
    if matrix_classes != expected_classifications:
        raise EcosystemSubmissionError(f"Published-image classification matrix drifted: {sorted(matrix_classes)}")
    fixture_ids = {
        str(item.get("fixture_id"))
        for item in report.get("fixture_refs", [])
        if isinstance(item, dict)
    }
    expected_fixtures = {
        "manifest-pass-local-pull-timeout",
        "cached-image-missing",
        "compose-up-timeout",
        "manifest-only-runtime-unverified",
        "manifest-missing-platform",
        "docker-images-failed",
        "ghcr-unavailable",
        "remote-smoke-pass",
        "remote-smoke-failed",
    }
    if fixture_ids != expected_fixtures:
        raise EcosystemSubmissionError(f"Published-image evidence fixture coverage drifted: {sorted(fixture_ids)}")
    for fixture_id in expected_fixtures:
        payload = load_json(ROOT / "fixtures" / "published-image-evidence" / f"{fixture_id}.json")
        if payload.get("schema_version") != "published-image-evidence-fixture-v1":
            raise EcosystemSubmissionError(f"Published-image fixture schema drifted: {fixture_id}")
        if payload.get("version") != "v0.3.30-alpha":
            raise EcosystemSubmissionError(f"Published-image fixture version drifted: {fixture_id}")
        if payload.get("classification") not in expected_classifications:
            raise EcosystemSubmissionError(f"Published-image fixture classification drifted: {fixture_id}")
    archive = report.get("archive") or {}
    archive_path = ROOT / "platform" / "generated" / "study-anything-published-image-evidence.zip"
    checksum_path = ROOT / "platform" / "generated" / "study-anything-published-image-evidence.sha256"
    if not archive_path.is_file() or not checksum_path.is_file():
        raise EcosystemSubmissionError("Published-image evidence zip/checksum missing.")
    if archive.get("sha256") not in checksum_path.read_text(encoding="utf-8"):
        raise EcosystemSubmissionError("Published-image evidence checksum sidecar drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "agent_endpoint_secrets_in_report",
        "real_model_keys_in_report",
        "support_bundle_private_payload_in_report",
        "local_absolute_paths_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Published-image evidence privacy.{key} must be false.")


def verify_release_asset_adoption_report() -> None:
    report = load_json(RELEASE_ASSET_ADOPTION_PATH)
    if report.get("schema_version") != "release-asset-adoption-v1":
        raise EcosystemSubmissionError("Release asset adoption schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Release asset adoption version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Release asset adoption report must pass.")
    identity = report.get("release_identity") or {}
    if identity.get("tag") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Release asset adoption tag drifted.")
    required_assets = set(str(item) for item in identity.get("required_asset_names", []))
    expected_assets = {
        "study-anything-platform-adoption-pack.zip",
        "study-anything-published-image-evidence.zip",
        "study-anything-adopter-evidence-archive.zip",
        "study-anything-platform-feedback-package.zip",
        "study-anything-release-asset-bootstrap.zip",
        "study-anything-platform-agent-replay.zip",
    }
    if required_assets != expected_assets:
        raise EcosystemSubmissionError(f"Release asset adoption required assets drifted: {sorted(required_assets)}")
    verification = report.get("verification") or {}
    if verification.get("proof_schema") != "release-asset-adoption-proof-v1":
        raise EcosystemSubmissionError("Release asset adoption proof schema drifted.")
    expected_classifications = {
        "release_asset_adoption_ready",
        "release_asset_missing",
        "release_asset_digest_mismatch",
        "release_asset_pack_corrupted",
        "release_asset_published_evidence_missing",
        "release_asset_network_unavailable",
    }
    matrix = report.get("classification_matrix") or []
    matrix_classes = {str(item.get("classification")) for item in matrix if isinstance(item, dict)}
    if matrix_classes != expected_classifications:
        raise EcosystemSubmissionError(f"Release asset classifications drifted: {sorted(matrix_classes)}")
    fixture_ids = {
        str(item.get("fixture_id"))
        for item in report.get("fixture_refs", [])
        if isinstance(item, dict)
    }
    expected_fixtures = {
        "asset-only-pass",
        "asset-missing",
        "digest-mismatch",
        "pack-corrupted",
        "published-evidence-missing",
        "network-unavailable",
    }
    if fixture_ids != expected_fixtures:
        raise EcosystemSubmissionError(f"Release asset fixture coverage drifted: {sorted(fixture_ids)}")
    for fixture_id in expected_fixtures:
        payload = load_json(ROOT / "fixtures" / "release-asset-adoption" / f"{fixture_id}.json")
        if payload.get("schema_version") != "release-asset-adoption-fixture-v1":
            raise EcosystemSubmissionError(f"Release asset fixture schema drifted: {fixture_id}")
        if payload.get("version") != "v0.3.30-alpha":
            raise EcosystemSubmissionError(f"Release asset fixture version drifted: {fixture_id}")
        if payload.get("classification") not in expected_classifications:
            raise EcosystemSubmissionError(f"Release asset fixture classification drifted: {fixture_id}")
    archive = report.get("archive") or {}
    archive_path = ROOT / "platform" / "generated" / "study-anything-release-asset-adoption.zip"
    checksum_path = ROOT / "platform" / "generated" / "study-anything-release-asset-adoption.sha256"
    if not archive_path.is_file() or not checksum_path.is_file():
        raise EcosystemSubmissionError("Release asset adoption zip/checksum missing.")
    if archive.get("sha256") not in checksum_path.read_text(encoding="utf-8"):
        raise EcosystemSubmissionError("Release asset adoption checksum sidecar drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "agent_endpoint_secrets_in_report",
        "real_model_keys_in_report",
        "support_bundle_private_payload_in_report",
        "local_absolute_paths_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Release asset adoption privacy.{key} must be false.")


def verify_release_asset_bootstrap_report() -> None:
    report = load_json(RELEASE_ASSET_BOOTSTRAP_PATH)
    if report.get("schema_version") != "release-asset-bootstrap-v1":
        raise EcosystemSubmissionError("Release asset bootstrap schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Release asset bootstrap version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Release asset bootstrap report must pass.")
    schemas = report.get("schemas") or {}
    if schemas.get("transcript") != "release-asset-bootstrap-transcript-v1":
        raise EcosystemSubmissionError("Release asset bootstrap transcript schema drifted.")
    if schemas.get("release_asset_proof") != "release-asset-adoption-proof-v1":
        raise EcosystemSubmissionError("Release asset bootstrap proof schema drifted.")
    identity = report.get("release_identity") or {}
    if identity.get("tag") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Release asset bootstrap tag drifted.")
    expected_classifications = {
        "release_asset_bootstrap_ready",
        "release_asset_missing",
        "release_asset_digest_mismatch",
        "release_asset_pack_corrupted",
        "release_asset_published_evidence_missing",
        "release_asset_network_unavailable",
        "tool_manifest_invalid",
        "local_api_unavailable",
        "published_image_unavailable",
        "non_ascii_path_risk",
        "bootstrap_failed",
    }
    matrix = report.get("classification_matrix") or []
    matrix_classes = {str(item.get("classification")) for item in matrix if isinstance(item, dict)}
    if matrix_classes != expected_classifications:
        raise EcosystemSubmissionError(f"Release asset bootstrap classifications drifted: {sorted(matrix_classes)}")
    platforms = report.get("platform_imports") or {}
    for platform_id in ("kimi", "codex", "workbuddy"):
        if platform_id not in platforms:
            raise EcosystemSubmissionError(f"Release asset bootstrap missing platform import: {platform_id}")
    commands = report.get("commands") or {}
    if "bootstrap_from_release.py" not in " ".join(str(item) for item in commands.values()):
        raise EcosystemSubmissionError("Release asset bootstrap commands must reference bootstrap_from_release.py.")
    archive = report.get("archive") or {}
    archive_path = ROOT / "platform" / "generated" / "study-anything-release-asset-bootstrap.zip"
    checksum_path = ROOT / "platform" / "generated" / "study-anything-release-asset-bootstrap.sha256"
    if not archive_path.is_file() or not checksum_path.is_file():
        raise EcosystemSubmissionError("Release asset bootstrap zip/checksum missing.")
    if archive.get("sha256") not in checksum_path.read_text(encoding="utf-8"):
        raise EcosystemSubmissionError("Release asset bootstrap checksum sidecar drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "agent_prompts_in_report",
        "agent_endpoint_secrets_in_report",
        "real_model_keys_in_report",
        "support_bundle_private_payload_in_report",
        "local_absolute_paths_in_report",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Release asset bootstrap privacy.{key} must be false.")


def verify_release_cleanroom_bootstrap_report() -> None:
    report = load_json(RELEASE_CLEANROOM_BOOTSTRAP_PATH)
    if report.get("schema_version") != "release-cleanroom-bootstrap-evidence-v1":
        raise EcosystemSubmissionError("Release cleanroom bootstrap evidence schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Release cleanroom bootstrap evidence version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Release cleanroom bootstrap evidence must pass.")
    identity = report.get("release_identity") or {}
    if identity.get("tag") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Release cleanroom bootstrap tag drifted.")
    example = report.get("example_report") or {}
    if example.get("schema_version") != "release-cleanroom-bootstrap-v1":
        raise EcosystemSubmissionError("Release cleanroom bootstrap example schema drifted.")
    if example.get("classification") != "cleanroom_bootstrap_ready":
        raise EcosystemSubmissionError("Release cleanroom bootstrap example must be ready.")
    commands = report.get("commands") or {}
    command_text = " ".join(str(item) for item in commands.values())
    for required in ("study_anything_release_bootstrap.py", "--runtime metadata-only", "--runtime skill-mode"):
        if required not in command_text:
            raise EcosystemSubmissionError(f"Release cleanroom bootstrap command missing {required}.")
    expected_classifications = {
        "cleanroom_bootstrap_ready",
        "release_asset_missing",
        "release_asset_digest_mismatch",
        "release_asset_pack_corrupted",
        "tool_import_invalid",
        "platform_entrypoint_missing",
        "source_download_failed",
        "runtime_launch_failed",
        "api_unavailable",
        "schema_mismatch",
        "privacy_leak",
        "network_unavailable",
        "cleanroom_bootstrap_failed",
    }
    matrix = report.get("classification_matrix") or []
    matrix_classes = {str(item.get("classification")) for item in matrix if isinstance(item, dict)}
    if matrix_classes != expected_classifications:
        raise EcosystemSubmissionError(f"Release cleanroom bootstrap classifications drifted: {sorted(matrix_classes)}")
    archive_path = ROOT / "platform" / "generated" / "study-anything-release-cleanroom-bootstrap.zip"
    checksum_path = ROOT / "platform" / "generated" / "study-anything-release-cleanroom-bootstrap.sha256"
    archive = report.get("archive") or {}
    if not archive_path.is_file() or not checksum_path.is_file():
        raise EcosystemSubmissionError("Release cleanroom bootstrap zip/checksum missing.")
    if archive.get("sha256") not in checksum_path.read_text(encoding="utf-8"):
        raise EcosystemSubmissionError("Release cleanroom bootstrap checksum sidecar drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_included",
        "learner_answers_included",
        "agent_prompts_included",
        "agent_endpoint_secrets_included",
        "real_model_keys_included",
        "support_bundle_private_payload_included",
        "local_absolute_paths_included",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Release cleanroom bootstrap privacy.{key} must be false.")


def verify_platform_agent_replay_report() -> None:
    report = load_json(PLATFORM_AGENT_REPLAY_PATH)
    if report.get("schema_version") != "platform-agent-release-replay-v1":
        raise EcosystemSubmissionError("Platform Agent release replay schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Platform Agent release replay version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Platform Agent release replay report must pass.")
    required_tools = set(str(item) for item in report.get("required_tools", []))
    expected_tools = {
        "study_anything_health",
        "study_anything_create_session",
        "study_anything_add_reading",
        "study_anything_teaching_layers",
        "study_anything_run",
        "study_anything_answer",
        "study_anything_mastery",
        "study_anything_agent_audit",
        "study_anything_agent_eval_artifact",
    }
    if required_tools != expected_tools:
        raise EcosystemSubmissionError(f"Platform Agent replay required tools drifted: {sorted(required_tools)}")
    platforms = set(str(item) for item in report.get("platforms", []))
    if platforms != {"kimi", "codex", "workbuddy", "generic-openapi"}:
        raise EcosystemSubmissionError(f"Platform Agent replay platforms drifted: {sorted(platforms)}")
    commands = report.get("commands") or {}
    command_text = " ".join(str(item) for item in commands.values())
    for required in ("replay_platform_agent_from_release.py", "--runtime metadata-only", "--runtime skill-mode"):
        if required not in command_text:
            raise EcosystemSubmissionError(f"Platform Agent replay command missing {required}.")
    expected_classifications = {
        "platform_agent_replay_ready",
        "platform_agent_replay_metadata_ready",
        "tool_import_invalid",
        "api_unavailable",
        "runtime_launch_failed",
        "tool_call_failed",
        "schema_mismatch",
        "privacy_leak",
        "platform_entrypoint_missing",
        "release_asset_invalid",
    }
    matrix = report.get("classification_matrix") or []
    matrix_classes = {str(item.get("classification")) for item in matrix if isinstance(item, dict)}
    if matrix_classes != expected_classifications:
        raise EcosystemSubmissionError(f"Platform Agent replay classifications drifted: {sorted(matrix_classes)}")
    archive_path = ROOT / "platform" / "generated" / "study-anything-platform-agent-replay.zip"
    checksum_path = ROOT / "platform" / "generated" / "study-anything-platform-agent-replay.sha256"
    archive = report.get("archive") or {}
    if not archive_path.is_file() or not checksum_path.is_file():
        raise EcosystemSubmissionError("Platform Agent replay zip/checksum missing.")
    if archive.get("sha256") not in checksum_path.read_text(encoding="utf-8"):
        raise EcosystemSubmissionError("Platform Agent replay checksum sidecar drifted.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "raw_source_text_included",
        "learner_answers_included",
        "agent_prompts_included",
        "agent_endpoint_secrets_included",
        "real_model_keys_included",
        "support_bundle_private_payload_included",
        "local_absolute_paths_included",
        "automatic_upload",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Platform Agent replay privacy.{key} must be false.")


def verify_plugin_ecosystem_kit_report() -> None:
    report = load_json(PLUGIN_ECOSYSTEM_KIT_PATH)
    if report.get("schema_version") != "plugin-ecosystem-adoption-kit-v1":
        raise EcosystemSubmissionError("Plugin ecosystem adoption kit schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Plugin ecosystem adoption kit version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Plugin ecosystem adoption kit must pass.")
    bundled = report.get("bundled_plugins")
    if not isinstance(bundled, list) or len(bundled) < 5:
        raise EcosystemSubmissionError("Plugin ecosystem kit must include bundled plugin evidence.")
    plugin_ids = {str(item.get("plugin_id")) for item in bundled if isinstance(item, dict)}
    expected = {
        "example-note-importer",
        "example-web-importer",
        "example-enrichment-importer",
        "example-exporter",
        "example-agent-provider",
    }
    if plugin_ids != expected:
        raise EcosystemSubmissionError(f"Plugin ecosystem kit bundled plugins drifted: {sorted(plugin_ids)}")
    registry = report.get("plugin_registry") or {}
    if registry.get("schema_version") != "plugin-registry-v1":
        raise EcosystemSubmissionError("Plugin ecosystem kit registry schema drifted.")
    if registry.get("digest_verified_count") != len(expected):
        raise EcosystemSubmissionError("Plugin ecosystem kit must verify all bundled plugin digests.")
    trust = report.get("trust_policy") or {}
    if trust.get("default_install_action") != "quarantine":
        raise EcosystemSubmissionError("Plugin ecosystem kit trust policy must quarantine by default.")
    if trust.get("entrypoints_executed_during_preview") is not False:
        raise EcosystemSubmissionError("Plugin ecosystem kit preview must not execute entrypoints.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_stored_by_study_anything",
        "agent_endpoint_secrets_in_plugin_registry",
        "raw_source_text_in_adoption_kit",
        "learner_answers_in_adoption_kit",
        "plugin_entrypoints_executed_by_verifier",
        "remote_code_downloads_allowed",
        "browser_video_private_context_in_adoption_kit",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Plugin ecosystem kit privacy.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise EcosystemSubmissionError("Plugin ecosystem kit report must be redacted.")


def verify_deployment_hardening_report() -> None:
    report = load_json(DEPLOYMENT_HARDENING_PATH)
    if report.get("schema_version") != "deployment-hardening-verification-v1":
        raise EcosystemSubmissionError("Deployment hardening report schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Deployment hardening report version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Deployment hardening report must pass.")
    modes = {str(item.get("id")) for item in report.get("deployment_modes", []) if isinstance(item, dict)}
    if modes != {"skill_mode", "published_image", "source_build"}:
        raise EcosystemSubmissionError(f"Deployment modes drifted: {sorted(modes)}")
    published = report.get("published_image_smoke") or {}
    if published.get("fallback_is_acceptance_when_ci_manifest_and_release_check_pass") is not True:
        raise EcosystemSubmissionError("Deployment hardening must document pull-timeout fallback.")
    required_platforms = set(str(item) for item in published.get("required_platforms", []))
    if {"linux/amd64", "linux/arm64"} - required_platforms:
        raise EcosystemSubmissionError("Deployment hardening must require amd64 and arm64 images.")
    commands = report.get("operator_commands") or {}
    for key in ("doctor", "skill_mode", "published_image", "published_image_smoke", "clean_clone"):
        if key not in commands:
            raise EcosystemSubmissionError(f"Deployment hardening command missing: {key}")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_stored_by_study_anything",
        "agent_endpoint_secrets_in_report",
        "raw_source_text_in_report",
        "learner_answers_in_report",
        "browser_video_private_context_in_report",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Deployment hardening privacy.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise EcosystemSubmissionError("Deployment hardening report must be redacted.")


def verify_learning_enrichment_bridge_report() -> None:
    report = load_json(LEARNING_ENRICHMENT_BRIDGE_PATH)
    if report.get("schema_version") != "learning-enrichment-bridge-verification-v1":
        raise EcosystemSubmissionError("Learning enrichment bridge report schema drifted.")
    if report.get("version") != "v0.3.30-alpha":
        raise EcosystemSubmissionError("Learning enrichment bridge report version drifted.")
    if report.get("status") != "pass":
        raise EcosystemSubmissionError("Learning enrichment bridge report must pass.")
    context = report.get("context_contract") or {}
    source_types = set(str(item) for item in context.get("source_types", []))
    required_source_types = {"app_context", "document", "markdown_note", "obsidian_note", "video_slice", "web"}
    if source_types != required_source_types:
        raise EcosystemSubmissionError(
            f"Learning enrichment bridge source type coverage drifted: {sorted(source_types)}"
        )
    exports = report.get("exports") or {}
    schemas = exports.get("schemas") or {}
    expected = {
        "context_package": "learning-context-package-v1",
        "enrichment_artifact": "learning-enrichment-artifact-v1",
        "learning_package": "learning-package-v1",
        "obsidian": "obsidian-markdown-export-v1",
        "second_brain": "second-brain-handoff-v1",
        "archive_manifest": "second-brain-archive-manifest-v1",
    }
    if schemas != expected:
        raise EcosystemSubmissionError(f"Learning enrichment bridge schemas drifted: {schemas}")
    html = exports.get("html_artifact") or {}
    if html.get("article_schema") != "learning-enrichment-artifact-v1":
        raise EcosystemSubmissionError("Learning enrichment HTML artifact schema drifted.")
    if html.get("contains_script_tag") is not False:
        raise EcosystemSubmissionError("Learning enrichment HTML artifact must not include scripts.")
    notebooklm = exports.get("notebooklm_bridge") or {}
    if notebooklm.get("official_notebooklm_api_required") is not False:
        raise EcosystemSubmissionError("NotebookLM bridge must not require official NotebookLM API.")
    privacy = report.get("privacy_assertions") or {}
    for key in (
        "real_model_keys_stored_by_study_anything",
        "raw_source_text_in_report",
        "raw_enrichment_text_in_report",
        "learner_answers_in_strict_handoff",
        "agent_endpoint_secrets_in_report",
        "browser_video_private_context_in_report",
    ):
        if privacy.get(key) is not False:
            raise EcosystemSubmissionError(f"Learning enrichment bridge privacy.{key} must be false.")
    if privacy.get("report_is_redacted") is not True:
        raise EcosystemSubmissionError("Learning enrichment bridge report must be redacted.")


def main() -> None:
    submission = load_json(SUBMISSION_PATH)
    tool_manifest = load_json(TOOL_MANIFEST_PATH)
    privacy = verify_privacy(submission, tool_manifest)
    tool_count = verify_tool_manifest(tool_manifest)
    verify_generated_assets(tool_count)
    by_id = verify_submission(submission)
    verify_platform_submissions(by_id)
    verify_pack_in_generated_adoption()
    verify_docs()
    verify_cognitive_loop_cli_artifact_report()
    verify_cognitive_loop_run_once_report()
    verify_cognitive_loop_snapshot_report()
    verify_cognitive_loop_human_gate_report()
    verify_cognitive_loop_evidence_bundle_report()
    verify_cognitive_loop_event_index_report()
    verify_cognitive_loop_artifact_doctor_report()
    verify_cognitive_loop_repair_plan_report()
    verify_cognitive_loop_artifact_index_report()
    verify_cognitive_loop_adoption_cookbook_report()
    verify_cognitive_loop_adoption_recipes_report()
    verify_cognitive_loop_recipe_replay_report()
    verify_cognitive_loop_skill_entrypoint_report()
    verify_cognitive_loop_recipe_cli_report()
    verify_cognitive_loop_recipe_cli_receipts_report()
    verify_cognitive_loop_recipe_cli_failures_report()
    verify_cognitive_loop_recipe_cli_schemas_report()
    verify_cognitive_loop_recipe_cli_schema_negative_fixtures_report()
    verify_cognitive_loop_schema_pack_consumer_report()
    verify_submission_dry_run_report()
    verify_manual_rehearsal_report()
    verify_first_lesson_kit_report()
    verify_external_eval_harness_report()
    verify_agent_eval_marketplace_enforcement_report()
    verify_platform_adoption_feedback_diagnostics_report()
    verify_platform_feedback_package()
    verify_platform_field_rehearsal_report()
    verify_platform_support_triage_report()
    verify_platform_onboarding_readiness_report()
    verify_public_support_status_report()
    verify_published_image_evidence_report()
    verify_release_asset_adoption_report()
    verify_release_asset_bootstrap_report()
    verify_release_cleanroom_bootstrap_report()
    verify_platform_agent_replay_report()
    verify_adopter_evidence_archive_report()
    verify_plugin_ecosystem_kit_report()
    verify_deployment_hardening_report()
    verify_learning_enrichment_bridge_report()
    print(
        json.dumps(
            {
                "schema_version": "ecosystem-submission-verification-v1",
                "status": "pass",
                "version": submission["version"],
                "platforms": sorted(by_id),
                "submission_count": len(by_id),
                "tool_count": tool_count,
                "privacy_items": len(privacy),
                "commercial_readiness": "commercial-readiness-v1",
                "cognitive_loop_cli_artifact": "cognitive-loop-cli-artifact-verification-v1",
                "cognitive_loop_run_once_evidence": "cognitive-loop-run-once-evidence-verification-v1",
                "cognitive_loop_project_snapshot": "cognitive-loop-project-snapshot-verification-v1",
                "cognitive_loop_human_gate": "cognitive-loop-human-gate-verification-v1",
                "cognitive_loop_evidence_bundle": "cognitive-loop-evidence-bundle-verification-v1",
                "cognitive_loop_event_index": "cognitive-loop-event-index-verification-v1",
                "cognitive_loop_artifact_doctor": "cognitive-loop-artifact-doctor-verification-v1",
                "cognitive_loop_repair_plan": "cognitive-loop-repair-plan-verification-v1",
                "cognitive_loop_artifact_index": "cognitive-loop-artifact-index-verification-v1",
                "cognitive_loop_adoption_cookbook": "cognitive-loop-adoption-cookbook-verification-v1",
                "cognitive_loop_adoption_recipes": "cognitive-loop-adoption-recipes-v1",
                "cognitive_loop_recipe_replay": "cognitive-loop-recipe-replay-verification-v1",
                "cognitive_loop_skill_entrypoint": "cognitive-loop-skill-entrypoint-verification-v1",
                "cognitive_loop_recipe_cli": "cognitive-loop-recipe-cli-verification-v1",
                "cognitive_loop_recipe_cli_receipts": "cognitive-loop-recipe-cli-receipts-v1",
                "cognitive_loop_recipe_cli_failures": "cognitive-loop-recipe-cli-failures-v1",
                "cognitive_loop_recipe_cli_schemas": "cognitive-loop-recipe-cli-schemas-v1",
                "cognitive_loop_recipe_cli_schema_negative_fixtures": "cognitive-loop-recipe-cli-schema-negative-fixtures-v1",
                "cognitive_loop_schema_pack_consumer": "cognitive-loop-schema-pack-consumer-v1",
                "external_eval_marketplace_harness": "external-eval-marketplace-harness-v1",
                "agent_eval_marketplace_enforcement": "agent-eval-marketplace-enforcement-v1",
                "platform_adoption_feedback_diagnostics": "platform-adoption-feedback-diagnostics-v1",
                "platform_feedback_package": "platform-feedback-package-v1",
                "platform_field_rehearsal": "platform-field-adoption-rehearsal-v1",
                "platform_import_failure_fixture": "platform-import-failure-fixture-v1",
                "platform_support_triage": "platform-support-triage-v1",
                "platform_support_ticket_fixture": "platform-support-ticket-fixture-v1",
                "platform_support_issue_template": "platform-support-issue-template-v1",
                "platform_onboarding_readiness": "platform-onboarding-readiness-v1",
                "platform_triage_dashboard": "platform-triage-dashboard-v1",
                "platform_release_blocker_fixture": "platform-release-blocker-fixture-v1",
                "public_support_status": "public-support-status-v1",
                "public_maintainer_dashboard": "public-maintainer-dashboard-v1",
                "public_status_linkage_fixture": "public-status-linkage-fixture-v1",
                "published_image_evidence": "published-image-evidence-v1",
                "published_image_evidence_fixture": "published-image-evidence-fixture-v1",
                "release_asset_adoption": "release-asset-adoption-v1",
                "release_asset_adoption_fixture": "release-asset-adoption-fixture-v1",
                "release_asset_adoption_proof": "release-asset-adoption-proof-v1",
                "release_asset_bootstrap": "release-asset-bootstrap-v1",
                "release_asset_bootstrap_transcript": "release-asset-bootstrap-transcript-v1",
                "release_cleanroom_bootstrap": "release-cleanroom-bootstrap-v1",
                "release_cleanroom_bootstrap_evidence": "release-cleanroom-bootstrap-evidence-v1",
                "platform_agent_release_replay": "platform-agent-release-replay-v1",
                "adopter_evidence_archive": "adopter-evidence-archive-v1",
                "adopter_evidence_fixture": "adopter-evidence-fixture-v1",
                "plugin_ecosystem_adoption_kit": "plugin-ecosystem-adoption-kit-v1",
                "deployment_hardening": "deployment-hardening-verification-v1",
                "learning_enrichment_bridge": "learning-enrichment-bridge-verification-v1",
                "no_frontend_required": True,
                "real_model_keys_stored_by_study_anything": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_ecosystem_submission_pack failed: {exc}", file=sys.stderr)
        sys.exit(1)
