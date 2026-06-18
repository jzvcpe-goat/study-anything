#!/usr/bin/env python3
"""Verify platform ecosystem packs stay aligned with the public tool contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "platform" / "study-anything-platform-tools.json"
PACKS_DIR = ROOT / "platform" / "packs"
REQUIRED_PACKS = {"codex", "kimi", "workbuddy"}
REQUIRED_ACCEPTANCE = {
    "commercial_readiness.schema_version == commercial-readiness-v1",
    "adoption_telemetry.schema_version == adoption-telemetry-v1",
    "pmf_readiness.schema_version == pmf-readiness-v1",
    "agent_audit.status == verified",
    "agent_eval_artifact.schema_version == agent-eval-artifact-v1",
    "all required native gates pass",
    "agent_eval_artifact.trajectory includes quiz.generate, answer.grade, insight.synthesize",
    "agent_quality_eval.schema_version == agent-quality-eval-v1",
    "agent_quality_eval.status == pass",
    "agent_eval_policy.schema_version == agent-eval-policy-v1",
    "agent_eval_report.schema_version == agent-eval-report-v1",
    "agent_eval_report.native_fast_gate.status == pass",
    "retrieval_quality_eval.schema_version == retrieval-quality-eval-v1",
    "retrieval_quality_eval.status == pass",
    "learning_context_package.schema_version == learning-context-package-v1",
    "enrichment_artifact.schema_version == learning-enrichment-artifact-v1",
    "obsidian_export.schema_version == obsidian-markdown-export-v1",
    "learning_package.schema_version == learning-package-v1",
    "second_brain.schema_version == second-brain-handoff-v1",
    "plugin_sdk.schema_version == plugin-sdk-v1",
    "plugin_capability_index.schema_version == plugin-capability-index-v1",
    "plugin_package_validation.schema_version == plugin-package-validation-v1",
    "plugin_quarantine.schema_version == plugin-quarantine-verification-v1",
    "deployment_guide.schema_version == deployment-guide-v1",
    "ecosystem_submission.schema_version == ecosystem-submission-v1",
    "ecosystem_submission_verification.schema_version == ecosystem-submission-verification-v1",
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
    "cognitive_loop_schema_pack_consumer_failures.schema_version == cognitive-loop-schema-pack-consumer-failures-v1",
    "cognitive_loop_pack_extract_smoke.schema_version == cognitive-loop-pack-extract-smoke-v1",
    "adoption_telemetry_verification.schema_version == adoption-telemetry-verification-v1",
    "agent_gateway_hardening.schema_version == agent-gateway-hardening-verification-v1",
    "external_agent_adapter_hardening.schema_version == external-agent-adapter-hardening-v1",
    "notebooklm_obsidian_bridge_hardening.schema_version == notebooklm-obsidian-bridge-hardening-v1",
    "learning_enrichment_bridge.schema_version == learning-enrichment-bridge-verification-v1",
    "security_recovery_hardening.schema_version == security-recovery-hardening-verification-v1",
    "platform_submission_dry_run.schema_version == platform-submission-dry-run-v1",
    "platform_manual_submission_rehearsal.schema_version == platform-manual-submission-rehearsal-v1",
    "first_lesson_authoring_kit.schema_version == first-run-lesson-authoring-kit-v1",
    "external_eval_marketplace_harness.schema_version == external-eval-marketplace-harness-v1",
    "agent_eval_marketplace_enforcement.schema_version == agent-eval-marketplace-enforcement-v1",
    "platform_adoption_feedback_diagnostics.schema_version == platform-adoption-feedback-diagnostics-v1",
    "platform_feedback_package.schema_version == platform-feedback-package-v1",
    "plugin_ecosystem_adoption_kit.schema_version == plugin-ecosystem-adoption-kit-v1",
    "deployment_hardening.schema_version == deployment-hardening-verification-v1",
}
REQUIRED_COMMAND_FRAGMENTS = {
    "verify_notebooklm_obsidian_bridge_hardening.py",
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
    "verify_cognitive_loop_schema_pack_consumer_failures.py --check",
    "verify_cognitive_loop_pack_extract_smoke.py --check",
    "verify_learning_enrichment_bridge.py",
    "verify_external_agent_adapter_hardening.py",
    "verify_plugin_quarantine.py",
    "verify_security_recovery_hardening.py",
    "verify_platform_submission_dry_run.py",
    "verify_platform_manual_submission_rehearsal.py",
    "verify_first_lesson_authoring_kit.py",
    "verify_external_eval_marketplace_harness.py",
    "verify_agent_eval_marketplace_enforcement.py",
    "verify_platform_adoption_feedback_diagnostics.py",
    "generate_platform_feedback_package.py",
    "verify_plugin_ecosystem_adoption_kit.py",
    "verify_deployment_hardening.py",
    "verify_importer_lesson_flow.py",
    "verify_platform_lesson_flow.py",
    "verify_platform_ecosystem_eval_flow.py",
    "verify_platform_agent_tools.py",
    "verify_agent_eval_flow.py",
    "run_external_agent_evals.py --tool report",
    "run_external_agent_evals.py --tool deepeval",
    "run_external_agent_evals.py --tool retrieval",
}
REQUIRED_ADOPTION_COMMAND_FRAGMENTS = {
    "verify_commercial_readiness.py",
    "verify_adoption_telemetry.py",
    "verify_clean_clone_adoption.py",
    "diagnose_adoption.py",
}


class PackVerificationError(RuntimeError):
    """Readable platform pack verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PackVerificationError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PackVerificationError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc


def assert_text_contains(path: Path, *needles: str) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise PackVerificationError(f"{path.relative_to(ROOT)} is missing required text: {missing}")


def verify_pack(pack_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    pack_dir = PACKS_DIR / pack_id
    pack_path = pack_dir / "pack.json"
    readme_path = pack_dir / "README.md"
    if not pack_path.exists() or not readme_path.exists():
        raise PackVerificationError(f"{pack_id} must include pack.json and README.md")

    pack = load_json(pack_path)
    if pack.get("schema_version") != "study-anything-platform-pack-v1":
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} has invalid schema_version")
    if pack.get("platform_id") != pack_id:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} platform_id mismatch")
    if not pack.get("name") or not pack.get("integration_mode"):
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must declare name and integration_mode")

    import_assets = pack.get("import_assets")
    if not isinstance(import_assets, list) or not import_assets:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must declare import_assets")
    for asset in import_assets:
        if not isinstance(asset, str) or not (ROOT / asset).exists():
            raise PackVerificationError(f"{pack_path.relative_to(ROOT)} references missing asset: {asset}")
    if "platform/study-anything-platform-tools.json" not in import_assets:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must reference the source manifest")
    if "docs/cognitive-loop-adoption-cookbook.md" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop adoption cookbook"
        )
    if "platform/generated/study-anything-cognitive-loop-adoption-cookbook.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop adoption cookbook report"
        )
    if "platform/generated/study-anything-cognitive-loop-adoption-recipes.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop adoption recipes"
        )
    if "platform/generated/study-anything-cognitive-loop-recipe-replay.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe replay report"
        )
    if "platform/generated/study-anything-cognitive-loop-skill-entrypoint.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop Skill entrypoint report"
        )
    if "platform/generated/study-anything-cognitive-loop-recipe-cli.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI report"
        )
    if "platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI receipts"
        )
    if "platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI failures"
        )
    if "platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI schemas"
        )
    if "platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI schema negative fixtures"
        )
    if "platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop schema pack consumer report"
        )
    if "platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop schema pack consumer failure report"
        )
    if "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop extracted pack smoke report"
        )
    if "scripts/cognitive_loop_recipe_cli.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI"
        )
    if "scripts/verify_cognitive_loop_recipe_cli_receipts.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI receipt verifier"
        )
    if "scripts/verify_cognitive_loop_recipe_cli_failures.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI failure verifier"
        )
    if "scripts/verify_cognitive_loop_recipe_cli_schemas.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI schema verifier"
        )
    if "scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop recipe CLI schema negative fixture verifier"
        )
    if "scripts/verify_cognitive_loop_schema_pack_consumer.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop schema pack consumer verifier"
        )
    if "scripts/verify_cognitive_loop_schema_pack_consumer_failures.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop schema pack consumer failure verifier"
        )
    if "scripts/verify_cognitive_loop_pack_extract_smoke.py" not in import_assets:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} must reference the Cognitive Loop extracted pack smoke verifier"
        )

    commands = pack.get("local_verification_commands")
    if not isinstance(commands, list) or not commands:
        raise PackVerificationError(f"{pack_path.relative_to(ROOT)} must declare verification commands")
    command_text = "\n".join(str(command) for command in commands)
    for fragment in REQUIRED_ADOPTION_COMMAND_FRAGMENTS:
        if fragment not in command_text:
            raise PackVerificationError(
                f"{pack_path.relative_to(ROOT)} verification commands must include {fragment}"
            )
    for fragment in REQUIRED_COMMAND_FRAGMENTS:
        if fragment not in command_text and pack_id != "codex":
            raise PackVerificationError(
                f"{pack_path.relative_to(ROOT)} verification commands must include {fragment}"
            )
    if "verify_cognitive_loop_recipe_cli_receipts.py --check" not in command_text:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} verification commands must include the recipe CLI receipt verifier"
        )
    if "verify_cognitive_loop_recipe_cli_failures.py --check" not in command_text:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} verification commands must include the recipe CLI failure verifier"
        )
    if "verify_cognitive_loop_recipe_cli_schemas.py --check" not in command_text:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} verification commands must include the recipe CLI schema verifier"
        )
    if "verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py --check" not in command_text:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} verification commands must include the recipe CLI schema negative fixture verifier"
        )
    if "verify_cognitive_loop_schema_pack_consumer.py --check" not in command_text:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} verification commands must include the schema pack consumer verifier"
        )
    if "verify_cognitive_loop_schema_pack_consumer_failures.py --check" not in command_text:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} verification commands must include the schema pack consumer failure verifier"
        )
    if "verify_cognitive_loop_pack_extract_smoke.py --check" not in command_text:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} verification commands must include the extracted pack smoke verifier"
        )
    if pack_id == "codex" and "run_skill_mode_demo.sh" not in command_text:
        raise PackVerificationError("Codex pack must keep the Skill Mode demo as its primary check")
    if pack_id == "kimi" and "verify_openai_compatible_gateway.py" not in command_text:
        raise PackVerificationError("Kimi pack must verify the OpenAI-compatible gateway dry-run flow")

    acceptance = set(str(item) for item in pack.get("acceptance_evidence", []))
    missing_acceptance = REQUIRED_ACCEPTANCE - acceptance
    if missing_acceptance:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} is missing acceptance evidence: {sorted(missing_acceptance)}"
        )

    expected_privacy = set(manifest.get("privacy_contract", {}).get("must_not_log_or_share", []))
    pack_privacy = set(str(item) for item in pack.get("must_not_log_or_share", []))
    if pack_privacy != expected_privacy:
        raise PackVerificationError(
            f"{pack_path.relative_to(ROOT)} privacy contract drifted: {sorted(pack_privacy)}"
        )

    assert_text_contains(
        readme_path,
        "agent-audit",
        "agent-eval",
        "quality",
        "retrieval",
        "Obsidian",
        "Learning Context Package",
        "micro-lesson",
        "learning package",
        "Plugin SDK",
        "deployment-guide-v1",
        "commercial-readiness-v1",
        "adoption-telemetry-v1",
        "pmf-readiness-v1",
        "ecosystem-submission-v1",
        "ecosystem-submission-verification-v1",
        "cognitive-loop-adoption-cookbook.md",
        "study-anything-cognitive-loop-adoption-recipes.json",
        "study-anything-cognitive-loop-recipe-replay.json",
        "study-anything-cognitive-loop-skill-entrypoint.json",
        "study-anything-cognitive-loop-recipe-cli.json",
        "study-anything-cognitive-loop-recipe-cli-receipts.json",
        "study-anything-cognitive-loop-recipe-cli-failures.json",
        "study-anything-cognitive-loop-recipe-cli-schemas.json",
        "study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json",
        "study-anything-cognitive-loop-schema-pack-consumer.json",
        "study-anything-cognitive-loop-schema-pack-consumer-failures.json",
        "study-anything-cognitive-loop-pack-extract-smoke.json",
        "cognitive_loop_recipe_cli.py",
        "verify_cognitive_loop_recipe_cli.py",
        "verify_cognitive_loop_recipe_cli_receipts.py",
        "verify_cognitive_loop_recipe_cli_failures.py",
        "verify_cognitive_loop_recipe_cli_schemas.py",
        "verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py",
        "verify_cognitive_loop_schema_pack_consumer.py",
        "verify_cognitive_loop_schema_pack_consumer_failures.py",
        "verify_cognitive_loop_pack_extract_smoke.py",
        "verify_cognitive_loop_skill_entrypoint.py",
        "raw source",
    )
    return pack


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    if manifest.get("schema_version") != "study-anything-platform-tools-v1":
        raise PackVerificationError("Source platform manifest has an unexpected schema_version")

    found = {path.name for path in PACKS_DIR.iterdir() if path.is_dir()}
    missing = REQUIRED_PACKS - found
    if missing:
        raise PackVerificationError(f"Missing required platform packs: {sorted(missing)}")

    packs = {pack_id: verify_pack(pack_id, manifest) for pack_id in sorted(REQUIRED_PACKS)}
    assert_text_contains(
        PACKS_DIR / "README.md",
        "codex",
        "kimi",
        "workbuddy",
        "verify_platform_ecosystem_packs.py",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "schema_version": "study-anything-platform-pack-v1",
                "packs": sorted(packs),
                "import_asset_count": sum(len(pack["import_assets"]) for pack in packs.values()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_ecosystem_packs failed: {exc}", file=sys.stderr)
        sys.exit(1)
