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
PLUGIN_ECOSYSTEM_KIT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-plugin-ecosystem-adoption-kit.json"
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
    "docs/platform-agent-integrations.md",
    "docs/use-with-kimi.md",
    "docs/commercial-readiness.md",
    "docs/security.md",
    "docs/adoption.md",
    "docs/adoption-telemetry.md",
    "docs/eval-frameworks.md",
    "scripts/verify_adoption_telemetry.py",
    "scripts/verify_agent_gateway_hardening.py",
    "scripts/verify_external_agent_adapter_hardening.py",
    "scripts/verify_notebooklm_obsidian_bridge_hardening.py",
    "scripts/verify_plugin_quarantine.py",
    "scripts/verify_security_recovery_hardening.py",
    "scripts/verify_platform_submission_dry_run.py",
    "scripts/verify_platform_manual_submission_rehearsal.py",
    "scripts/verify_first_lesson_authoring_kit.py",
    "scripts/verify_external_eval_marketplace_harness.py",
    "scripts/verify_plugin_ecosystem_adoption_kit.py",
    "scripts/install_local_plugin.py",
    "platform/generated/study-anything-platform-submission-dry-run.json",
    "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
    "platform/generated/study-anything-first-lesson-authoring-kit.json",
    "platform/generated/study-anything-external-eval-harness.json",
    "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
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
REQUIRED_ACCEPTANCE_COMMANDS = {
    "verify_ecosystem_submission_pack.py",
    "verify_commercial_readiness.py",
    "verify_adoption_telemetry.py",
    "verify_agent_gateway_hardening.py",
    "verify_external_agent_adapter_hardening.py",
    "verify_notebooklm_obsidian_bridge_hardening.py",
    "verify_plugin_quarantine.py",
    "verify_security_recovery_hardening.py",
    "verify_platform_submission_dry_run.py",
    "verify_platform_manual_submission_rehearsal.py",
    "verify_first_lesson_authoring_kit.py",
    "verify_external_eval_marketplace_harness.py",
    "verify_plugin_ecosystem_adoption_kit.py",
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
    if submission.get("version") != "v0.3.12-alpha":
        raise EcosystemSubmissionError("Submission version must be v0.3.12-alpha.")

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


def verify_pack_in_generated_adoption() -> None:
    manifest = load_json(ADOPTION_PACK_PATH)
    if manifest.get("schema_version") != "study-anything-platform-adoption-pack-v1":
        raise EcosystemSubmissionError("Generated adoption pack schema drifted.")
    if manifest.get("version") != "v0.3.12-alpha":
        raise EcosystemSubmissionError("Generated adoption pack must be updated to v0.3.12-alpha.")
    paths = {item.get("path") for item in manifest.get("files", []) if isinstance(item, dict)}
    required = {
        "platform/ecosystem-submission.json",
        "docs/ecosystem-submission.md",
        "docs/adoption-telemetry.md",
        "scripts/verify_ecosystem_submission_pack.py",
        "scripts/verify_adoption_telemetry.py",
        "scripts/verify_notebooklm_obsidian_bridge_hardening.py",
        "scripts/verify_plugin_quarantine.py",
        "scripts/verify_security_recovery_hardening.py",
        "scripts/verify_platform_submission_dry_run.py",
        "scripts/verify_platform_manual_submission_rehearsal.py",
        "scripts/verify_first_lesson_authoring_kit.py",
        "scripts/verify_external_eval_marketplace_harness.py",
        "scripts/verify_plugin_ecosystem_adoption_kit.py",
        "scripts/install_local_plugin.py",
        "platform/generated/study-anything-operator-drill-transcript.json",
        "platform/generated/study-anything-platform-submission-dry-run.json",
        "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
        "platform/generated/study-anything-first-lesson-authoring-kit.json",
        "platform/generated/study-anything-external-eval-harness.json",
        "platform/generated/study-anything-plugin-ecosystem-adoption-kit.json",
        "docs/eval-frameworks.md",
        "docs/release-notes/v0.3.12-alpha.md",
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


def verify_submission_dry_run_report() -> None:
    report = load_json(SUBMISSION_DRY_RUN_PATH)
    if report.get("schema_version") != "platform-submission-dry-run-v1":
        raise EcosystemSubmissionError("Platform submission dry-run report schema drifted.")
    if report.get("version") != "v0.3.12-alpha":
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
    if report.get("version") != "v0.3.12-alpha":
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
    if report.get("version") != "v0.3.12-alpha":
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
    if report.get("version") != "v0.3.12-alpha":
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


def verify_plugin_ecosystem_kit_report() -> None:
    report = load_json(PLUGIN_ECOSYSTEM_KIT_PATH)
    if report.get("schema_version") != "plugin-ecosystem-adoption-kit-v1":
        raise EcosystemSubmissionError("Plugin ecosystem adoption kit schema drifted.")
    if report.get("version") != "v0.3.12-alpha":
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
    verify_submission_dry_run_report()
    verify_manual_rehearsal_report()
    verify_first_lesson_kit_report()
    verify_external_eval_harness_report()
    verify_plugin_ecosystem_kit_report()
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
                "external_eval_marketplace_harness": "external-eval-marketplace-harness-v1",
                "plugin_ecosystem_adoption_kit": "plugin-ecosystem-adoption-kit-v1",
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
