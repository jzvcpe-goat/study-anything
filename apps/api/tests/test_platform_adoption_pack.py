from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

from _path import ROOT  # noqa: F401


class PlatformAdoptionPackTests(unittest.TestCase):
    def test_platform_adoption_pack_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "generate_platform_adoption_pack.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_platform_adoption_pack_contains_external_operator_assets(self) -> None:
        root = Path(__file__).resolve().parents[3]
        manifest_path = root / "platform" / "generated" / "study-anything-platform-adoption-pack.json"
        archive_path = root / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["schema_version"], "study-anything-platform-adoption-pack-v1")
        self.assertEqual(manifest["version"], "v0.3.31-alpha")
        self.assertIs(manifest["no_frontend_required"], True)
        self.assertIs(manifest["real_model_keys_stored_by_study_anything"], False)
        self.assertEqual(
            manifest["archive_sha256"],
            hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        )
        self.assertIn("kimi-work", manifest["supported_platforms"])
        self.assertIn("codex", manifest["supported_platforms"])
        self.assertIn("workbuddy-style-http", manifest["supported_platforms"])

        required_paths = {
            "manifest.json",
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-openai-tools.json",
            "platform/packs/kimi/README.md",
            "platform/packs/codex/README.md",
            "platform/packs/workbuddy/README.md",
            "docs/second-brain-handoff.md",
            "docs/obsidian-export.md",
            "docs/notebooklm-bridge.md",
            "docs/okf-alignment.md",
            "docs/commercial-readiness.md",
            "docs/adoption-telemetry.md",
            "docs/plugin-sdk.md",
            "docs/plugin-registry.md",
            "docs/ecosystem-submission.md",
            "docs/eval-frameworks.md",
            "docs/real-agent-eval-bridge.md",
            "docs/trust-model.md",
            "docs/delivery-trust-receipt.md",
            "docs/release-checklist.md",
            "docs/roadmap.md",
            "docs/release-notes/v0.3.31-alpha.md",
            "platform/ecosystem-submission.json",
            "platform/generated/study-anything-operator-drill-transcript.json",
            "platform/generated/study-anything-platform-submission-dry-run.json",
            "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
            "platform/generated/study-anything-first-lesson-authoring-kit.json",
            "platform/generated/study-anything-external-eval-harness.json",
            "platform/generated/study-anything-real-agent-eval-bridge.json",
            "platform/generated/study-anything-workbuddy-real-agent-learning-quality.json",
            "platform/generated/study-anything-delivery-trust-receipt.json",
            "platform/generated/study-anything-delivery-trust-receipt.html",
            "platform/schemas/delivery-trust/delivery-trust-receipt-v1.schema.json",
            "fixtures/delivery-trust/pass/delivery-trust-receipt.json",
            "fixtures/delivery-trust/blocked-missing-attention/delivery-trust-receipt.json",
            "fixtures/delivery-trust/blocked-risk-budget/delivery-trust-receipt.json",
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            "platform/generated/study-anything-platform-feedback-package.json",
            "platform/generated/study-anything-platform-feedback-package.zip",
            "platform/generated/study-anything-codex-plugin-pack.json",
            "platform/generated/study-anything-codex-plugin-pack.zip",
            "platform/generated/study-anything-codex-plugin-pack.sha256",
            "platform/generated/study-anything-kimi-plugin-pack.json",
            "platform/generated/study-anything-kimi-plugin-pack.zip",
            "platform/generated/study-anything-kimi-plugin-pack.sha256",
            "platform/generated/study-anything-workbuddy-plugin-pack.json",
            "platform/generated/study-anything-workbuddy-plugin-pack.zip",
            "platform/generated/study-anything-workbuddy-plugin-pack.sha256",
            "platform/generated/study-anything-platform-field-rehearsal.json",
            "platform/generated/study-anything-platform-support-triage.json",
            "platform/generated/study-anything-platform-onboarding-readiness.json",
            "platform/generated/study-anything-platform-triage-dashboard.json",
            "platform/generated/study-anything-platform-triage-dashboard.md",
            "platform/generated/study-anything-public-support-status.json",
            "platform/generated/study-anything-public-maintainer-dashboard.json",
            "platform/generated/study-anything-public-maintainer-dashboard.md",
            "platform/generated/study-anything-learning-enrichment-bridge.json",
            "platform/generated/study-anything-okf-alignment.json",
            "platform/okf/examples/demo-session.json",
            "platform/okf/examples/demo-okf-bundle/manifest.json",
            "platform/okf/examples/demo-okf-bundle/overview.md",
            "platform/okf/examples/demo-okf-bundle/sources.md",
            "platform/okf/examples/demo-okf-bundle/mastery.md",
            "platform/okf/examples/demo-okf-bundle/decisions.md",
            "platform/okf/examples/demo-okf-bundle/concepts/overview.md",
            "platform/okf/examples/demo-okf-bundle/concepts/glossary.md",
            "platform/okf/examples/demo-okf-bundle/questions/review.md",
            "scripts/export_okf_bundle.py",
            "scripts/verify_okf_bundle.py",
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
            "docs/support-desk.md",
            "docs/adopter-onboarding.md",
            "docs/maintainer-rotation.md",
            "docs/public-support-status.md",
            "docs/release-asset-adoption.md",
            "docs/release-asset-bootstrap.md",
            "docs/platform-agent-release-replay.md",
            "scripts/generate_release_asset_adoption.py",
            "scripts/verify_release_asset_adoption.py",
            "scripts/bootstrap_from_release.py",
            "scripts/generate_release_asset_bootstrap.py",
            "scripts/replay_platform_agent_from_release.py",
            "scripts/generate_platform_agent_replay.py",
            "platform/generated/study-anything-release-asset-adoption.json",
            "platform/generated/study-anything-release-asset-adoption.md",
            "platform/generated/study-anything-release-asset-adoption.zip",
            "platform/generated/study-anything-release-asset-adoption.sha256",
            "platform/generated/study-anything-release-asset-bootstrap.json",
            "platform/generated/study-anything-release-asset-bootstrap.md",
            "platform/generated/study-anything-release-asset-bootstrap.zip",
            "platform/generated/study-anything-release-asset-bootstrap.sha256",
            "platform/generated/study-anything-platform-agent-replay.json",
            "platform/generated/study-anything-platform-agent-replay.md",
            "platform/generated/study-anything-platform-agent-replay.zip",
            "platform/generated/study-anything-platform-agent-replay.sha256",
            "fixtures/release-asset-adoption/asset-only-pass.json",
            "fixtures/release-asset-adoption/asset-missing.json",
            "fixtures/release-asset-adoption/digest-mismatch.json",
            "fixtures/release-asset-adoption/pack-corrupted.json",
            "fixtures/release-asset-adoption/published-evidence-missing.json",
            "fixtures/release-asset-adoption/network-unavailable.json",
            "skills/study-anything/SKILL.md",
            "scripts/doctor.sh",
            "scripts/launch_self_host.sh",
            "scripts/stop_self_host.sh",
            "scripts/verify_published_image_launch.py",
            "scripts/verify_ecosystem_submission_pack.py",
            "scripts/verify_adoption_telemetry.py",
            "scripts/verify_external_agent_adapter_hardening.py",
            "scripts/verify_plugin_quarantine.py",
            "scripts/verify_security_recovery_hardening.py",
            "scripts/verify_platform_submission_dry_run.py",
            "scripts/verify_platform_manual_submission_rehearsal.py",
            "scripts/verify_first_lesson_authoring_kit.py",
            "scripts/verify_external_eval_marketplace_harness.py",
            "scripts/verify_agent_eval_marketplace_enforcement.py",
            "scripts/delivery_trust_receipt.py",
            "scripts/verify_delivery_trust_receipt.py",
            "scripts/verify_platform_adoption_feedback_diagnostics.py",
            "scripts/generate_platform_plugin_packs.py",
            "scripts/verify_platform_plugin_packs.py",
            "scripts/generate_platform_feedback_package.py",
            "scripts/generate_platform_field_rehearsal.py",
            "scripts/verify_platform_field_rehearsal.py",
            "scripts/generate_platform_support_triage.py",
            "scripts/verify_platform_support_triage.py",
            "scripts/generate_platform_onboarding_readiness.py",
            "scripts/verify_platform_onboarding_readiness.py",
            "scripts/generate_platform_public_support_status.py",
            "scripts/verify_platform_public_support_status.py",
            "scripts/verify_learning_enrichment_bridge.py",
            "scripts/verify_agent_eval_assets.py",
            "scripts/verify_external_adoption.py",
            "scripts/verify_platform_operator_drill.py",
            "evals/README.md",
            "evals/fixtures/fake-agent-learning-loop.json",
            "evals/fixtures/mock-http-agent-learning-loop.json",
            "fixtures/notebooklm/notebooklm-style-context-package.json",
        }
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            roots = {name.split("/", 1)[0] for name in names if "/" in name}
            self.assertEqual(roots, {"study-anything-platform-adoption-pack"})
            archive_root = "study-anything-platform-adoption-pack"
            for path in required_paths:
                self.assertIn(f"{archive_root}/{path}", names)
            internal_manifest = json.loads(
                archive.read(f"{archive_root}/manifest.json").decode("utf-8")
            )
            archive_paths = {item["archive_path"] for item in internal_manifest["files"]}
            for item in internal_manifest["files"]:
                self.assertRegex(item["sha256"], r"^[a-f0-9]{64}$")
                self.assertGreater(item["bytes"], 0)
            self.assertTrue(
                all(f"{archive_root}/{path}" in archive_paths for path in required_paths if path != "manifest.json")
            )

        self.assertIn("study_anything_deployment_guide", manifest["required_tool_names"])
        self.assertIn("study_anything_commercial_readiness", manifest["required_tool_names"])
        self.assertIn("study_anything_adoption_telemetry", manifest["required_tool_names"])
        self.assertIn("study_anything_pmf_readiness", manifest["required_tool_names"])
        self.assertIn("study_anything_eval_policy", manifest["required_tool_names"])
        self.assertIn("study_anything_agent_eval_report", manifest["required_tool_names"])
        self.assertIn("study_anything_retrieval_quality_eval", manifest["required_tool_names"])
        self.assertIn("study_anything_obsidian_export", manifest["required_tool_names"])
        self.assertIn("study_anything_enrichment_artifact_export", manifest["required_tool_names"])
        self.assertIn("study_anything_learning_package_export", manifest["required_tool_names"])
        self.assertIn("study_anything_second_brain_handoff_export", manifest["required_tool_names"])
        self.assertIn("learning-enrichment-bridge-verification-v1", manifest["acceptance"]["must_verify"])
        self.assertIn(
            "cognitive-black-box-okf-alignment-verification-v1",
            manifest["acceptance"]["must_verify"],
        )
        self.assertIn("cognitive-black-box-okf-bundle-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("agent-eval-marketplace-enforcement-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-adoption-feedback-diagnostics-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("study-anything-platform-plugin-pack-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-onboarding-readiness-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-triage-dashboard-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-release-blocker-fixture-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-feedback-package-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-field-adoption-rehearsal-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-import-failure-fixture-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-support-triage-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-support-ticket-fixture-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("platform-support-issue-template-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("public-support-status-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("public-maintainer-dashboard-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("public-status-linkage-fixture-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("release-asset-adoption-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("release-asset-adoption-fixture-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("release-asset-adoption-proof-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("release-asset-bootstrap-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("release-asset-bootstrap-transcript-v1", manifest["acceptance"]["must_verify"])
        self.assertIn("study_anything_plugin_sdk", manifest["required_tool_names"])
        self.assertIn("study_anything_plugin_capabilities", manifest["required_tool_names"])
        self.assertIn("study_anything_validate_plugin_package", manifest["required_tool_names"])


if __name__ == "__main__":
    unittest.main()
