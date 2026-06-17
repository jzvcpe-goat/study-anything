from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


class EcosystemSubmissionPackTests(unittest.TestCase):
    def test_ecosystem_submission_verifier_passes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "verify_ecosystem_submission_pack.py")],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "ecosystem-submission-verification-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["version"], "v0.3.30-alpha")
        self.assertTrue(payload["no_frontend_required"])
        self.assertFalse(payload["real_model_keys_stored_by_study_anything"])
        self.assertEqual(
            payload["agent_eval_marketplace_enforcement"],
            "agent-eval-marketplace-enforcement-v1",
        )
        self.assertEqual(
            payload["platform_adoption_feedback_diagnostics"],
            "platform-adoption-feedback-diagnostics-v1",
        )
        self.assertEqual(payload["platform_feedback_package"], "platform-feedback-package-v1")
        self.assertEqual(
            payload["platform_field_rehearsal"],
            "platform-field-adoption-rehearsal-v1",
        )
        self.assertEqual(
            payload["platform_import_failure_fixture"],
            "platform-import-failure-fixture-v1",
        )
        self.assertEqual(payload["platform_support_triage"], "platform-support-triage-v1")
        self.assertEqual(
            payload["platform_support_ticket_fixture"],
            "platform-support-ticket-fixture-v1",
        )
        self.assertEqual(
            payload["platform_support_issue_template"],
            "platform-support-issue-template-v1",
        )
        self.assertEqual(payload["platform_onboarding_readiness"], "platform-onboarding-readiness-v1")
        self.assertEqual(payload["platform_triage_dashboard"], "platform-triage-dashboard-v1")
        self.assertEqual(
            payload["platform_release_blocker_fixture"],
            "platform-release-blocker-fixture-v1",
        )
        self.assertEqual(payload["public_support_status"], "public-support-status-v1")
        self.assertEqual(payload["public_maintainer_dashboard"], "public-maintainer-dashboard-v1")
        self.assertEqual(payload["public_status_linkage_fixture"], "public-status-linkage-fixture-v1")
        self.assertEqual(payload["adopter_evidence_archive"], "adopter-evidence-archive-v1")
        self.assertEqual(payload["adopter_evidence_fixture"], "adopter-evidence-fixture-v1")
        self.assertEqual(payload["release_asset_adoption"], "release-asset-adoption-v1")
        self.assertEqual(
            payload["release_asset_adoption_fixture"],
            "release-asset-adoption-fixture-v1",
        )
        self.assertEqual(
            payload["release_asset_adoption_proof"],
            "release-asset-adoption-proof-v1",
        )
        self.assertEqual(payload["release_asset_bootstrap"], "release-asset-bootstrap-v1")
        self.assertEqual(
            payload["release_asset_bootstrap_transcript"],
            "release-asset-bootstrap-transcript-v1",
        )
        self.assertEqual(payload["platform_agent_release_replay"], "platform-agent-release-replay-v1")
        self.assertIn("kimi-compatible", payload["platforms"])
        self.assertIn("codex-skill", payload["platforms"])
        self.assertIn("workbuddy-style-http", payload["platforms"])
        self.assertIn("generic-openapi-tools", payload["platforms"])

    def test_ecosystem_submission_privacy_and_commercial_boundary(self) -> None:
        root = Path(__file__).resolve().parents[3]
        submission = json.loads((root / "platform" / "ecosystem-submission.json").read_text(encoding="utf-8"))
        tool_manifest = json.loads(
            (root / "platform" / "study-anything-platform-tools.json").read_text(encoding="utf-8")
        )
        self.assertEqual(submission["schema_version"], "ecosystem-submission-v1")
        self.assertEqual(submission["version"], "v0.3.30-alpha")
        self.assertIs(submission["project"]["standalone_frontend_required"], False)
        self.assertIs(submission["project"]["billing_required"], False)
        self.assertIs(submission["project"]["hosted_services_in_mvp"], False)
        self.assertIs(submission["privacy"]["real_model_keys_stored_by_study_anything"], False)
        self.assertIs(submission["privacy"]["raw_learning_data_in_submission"], False)
        self.assertIs(submission["privacy"]["agent_endpoints_in_submission"], False)
        self.assertEqual(
            submission["privacy"]["must_not_log_or_share"],
            tool_manifest["privacy_contract"]["must_not_log_or_share"],
        )
        self.assertEqual(submission["commercial_readiness"]["contract"], "commercial-readiness-v1")
        self.assertIn("platform_agent_distribution", submission["commercial_readiness"]["ready_paths"])
        self.assertIn("hosted_paid_services", submission["commercial_readiness"]["not_ready_paths"])
        self.assertEqual(submission["adoption_telemetry"]["contract"], "adoption-telemetry-v1")
        self.assertEqual(submission["adoption_telemetry"]["readiness_contract"], "pmf-readiness-v1")
        self.assertIs(submission["adoption_telemetry"]["aggregate_only"], True)
        self.assertIs(submission["adoption_telemetry"]["automatic_upload"], False)
        self.assertIn("platform/generated/study-anything-platform-submission-dry-run.json", submission["shared_assets"])
        self.assertIn(
            "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-first-lesson-authoring-kit.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-external-eval-harness.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-feedback-package.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-feedback-package.zip",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-field-rehearsal.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-support-triage.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-onboarding-readiness.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-triage-dashboard.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-triage-dashboard.md",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-public-support-status.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-public-maintainer-dashboard.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-public-maintainer-dashboard.md",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-adopter-evidence-archive.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-adopter-evidence-archive.md",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-adopter-evidence-archive.zip",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-adopter-evidence-archive.sha256",
            submission["shared_assets"],
        )
        self.assertIn("docs/adopter-evidence-archive.md", submission["shared_assets"])
        self.assertIn("scripts/generate_adopter_evidence_archive.py", submission["shared_assets"])
        self.assertIn("scripts/verify_adopter_evidence_archive.py", submission["shared_assets"])
        self.assertIn("docs/release-asset-adoption.md", submission["shared_assets"])
        self.assertIn("scripts/generate_release_asset_adoption.py", submission["shared_assets"])
        self.assertIn("scripts/verify_release_asset_adoption.py", submission["shared_assets"])
        self.assertIn(
            "platform/generated/study-anything-release-asset-adoption.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-release-asset-adoption.md",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-release-asset-adoption.zip",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-release-asset-adoption.sha256",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/release-asset-adoption/asset-only-pass.json",
            submission["shared_assets"],
        )
        self.assertIn("docs/release-asset-bootstrap.md", submission["shared_assets"])
        self.assertIn("scripts/bootstrap_from_release.py", submission["shared_assets"])
        self.assertIn("scripts/generate_release_asset_bootstrap.py", submission["shared_assets"])
        self.assertIn(
            "platform/generated/study-anything-release-asset-bootstrap.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-release-asset-bootstrap.md",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-release-asset-bootstrap.zip",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-release-asset-bootstrap.sha256",
            submission["shared_assets"],
        )
        self.assertIn("docs/platform-agent-release-replay.md", submission["shared_assets"])
        self.assertIn("scripts/replay_platform_agent_from_release.py", submission["shared_assets"])
        self.assertIn("scripts/generate_platform_agent_replay.py", submission["shared_assets"])
        self.assertIn(
            "platform/generated/study-anything-platform-agent-replay.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-agent-replay.md",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-agent-replay.zip",
            submission["shared_assets"],
        )
        self.assertIn(
            "platform/generated/study-anything-platform-agent-replay.sha256",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/adopter-evidence-archive/successful-release.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/adopter-evidence-archive/local-ghcr-pull-timeout.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/adopter-evidence-archive/needs-repro-issue.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/adopter-evidence-archive/release-blocker.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/adopter-evidence-archive/platform-blocked.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/adopter-evidence-archive/resolved-support-case.json",
            submission["shared_assets"],
        )
        self.assertIn("docs/public-support-status.md", submission["shared_assets"])
        self.assertIn("fixtures/platform-status-links/intake.json", submission["shared_assets"])
        self.assertIn("fixtures/platform-status-links/release-blocker.json", submission["shared_assets"])
        self.assertIn("docs/support-desk.md", submission["shared_assets"])
        self.assertIn("docs/adopter-onboarding.md", submission["shared_assets"])
        self.assertIn("docs/maintainer-rotation.md", submission["shared_assets"])
        self.assertIn(
            ".github/ISSUE_TEMPLATE/platform_import_failure.md",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/platform-support-tickets/platform_import_failure.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/platform-release-blockers/tool_import_blocker.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/platform-import-failures/schema_mismatch.json",
            submission["shared_assets"],
        )
        self.assertIn(
            "fixtures/platform-import-failures/version_drift.json",
            submission["shared_assets"],
        )
        self.assertIn("docs/agent-eval.md", submission["shared_assets"])
        self.assertIn("docs/eval-frameworks.md", submission["shared_assets"])
        self.assertIn("scripts/verify_external_agent_adapter_hardening.py", submission["shared_assets"])
        self.assertIn("scripts/verify_platform_manual_submission_rehearsal.py", submission["shared_assets"])
        self.assertIn("scripts/verify_first_lesson_authoring_kit.py", submission["shared_assets"])
        self.assertIn("scripts/verify_external_eval_marketplace_harness.py", submission["shared_assets"])
        self.assertIn("scripts/verify_agent_eval_marketplace_enforcement.py", submission["shared_assets"])
        self.assertIn(
            "scripts/verify_platform_adoption_feedback_diagnostics.py",
            submission["shared_assets"],
        )
        self.assertIn("scripts/generate_platform_feedback_package.py", submission["shared_assets"])
        self.assertIn("scripts/generate_platform_field_rehearsal.py", submission["shared_assets"])
        self.assertIn("scripts/verify_platform_field_rehearsal.py", submission["shared_assets"])
        self.assertIn("scripts/verify_learning_enrichment_bridge.py", submission["shared_assets"])
        self.assertIn(
            "platform/generated/study-anything-learning-enrichment-bridge.json",
            submission["shared_assets"],
        )
        commands = "\n".join(submission["acceptance"]["minimum_commands"])
        self.assertIn("verify_platform_submission_dry_run.py", commands)
        self.assertIn("verify_platform_manual_submission_rehearsal.py", commands)
        self.assertIn("verify_first_lesson_authoring_kit.py", commands)
        self.assertIn("verify_external_eval_marketplace_harness.py", commands)
        self.assertIn("verify_agent_eval_marketplace_enforcement.py", commands)
        self.assertIn("verify_platform_adoption_feedback_diagnostics.py", commands)
        self.assertIn("generate_platform_feedback_package.py", commands)
        self.assertIn("generate_platform_field_rehearsal.py", commands)
        self.assertIn("verify_platform_field_rehearsal.py", commands)
        self.assertIn("generate_platform_support_triage.py", commands)
        self.assertIn("verify_platform_support_triage.py", commands)
        self.assertIn("generate_platform_onboarding_readiness.py", commands)
        self.assertIn("verify_platform_onboarding_readiness.py", commands)
        self.assertIn("generate_platform_public_support_status.py", commands)
        self.assertIn("verify_platform_public_support_status.py", commands)
        self.assertIn("generate_adopter_evidence_archive.py", commands)
        self.assertIn("verify_adopter_evidence_archive.py", commands)
        self.assertIn("generate_release_asset_adoption.py", commands)
        self.assertIn("verify_release_asset_adoption.py", commands)
        self.assertIn("generate_release_asset_bootstrap.py", commands)
        self.assertIn("bootstrap_from_release.py", commands)
        self.assertIn("verify_external_agent_adapter_hardening.py", commands)
        self.assertIn("verify_learning_enrichment_bridge.py", commands)
        prove = "\n".join(submission["acceptance"]["must_prove"])
        self.assertIn("public-support-status-v1", prove)
        self.assertIn("public-maintainer-dashboard-v1", prove)
        self.assertIn("public-status-linkage-fixture-v1", prove)
        self.assertIn("adopter-evidence-archive-v1", prove)
        self.assertIn("adopter-evidence-fixture-v1", prove)
        self.assertIn("release-asset-adoption-v1", prove)
        self.assertIn("release-asset-adoption-fixture-v1", prove)
        self.assertIn("release-asset-adoption-proof-v1", prove)
        self.assertIn("release-asset-bootstrap-v1", prove)
        self.assertIn("release-asset-bootstrap-transcript-v1", prove)
        self.assertIn("platform-agent-release-replay-v1", prove)


class PlatformSubmissionDryRunTests(unittest.TestCase):
    def test_platform_submission_dry_run_report_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "verify_platform_submission_dry_run.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_platform_submission_dry_run_report_privacy(self) -> None:
        root = Path(__file__).resolve().parents[3]
        report = json.loads(
            (
                root / "platform" / "generated" / "study-anything-platform-submission-dry-run.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "platform-submission-dry-run-v1")
        self.assertEqual(report["version"], "v0.3.30-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocked_platforms"], [])
        self.assertFalse(report["privacy"]["real_model_keys_stored_by_study_anything"])
        self.assertFalse(report["privacy"]["agent_endpoint_secrets_in_report"])
        self.assertFalse(report["privacy"]["raw_learning_data_in_report"])
        self.assertTrue(report["privacy"]["report_is_redacted"])
        self.assertIn("kimi-compatible", report["platforms"])
        self.assertIn("codex-skill", report["platforms"])
        self.assertIn("workbuddy-style-http", report["platforms"])
        self.assertIn("generic-openapi-tools", report["platforms"])
        for platform in report["platforms"].values():
            command_text = "\n".join(platform["acceptance_commands"])
            self.assertIn("verify_agent_eval_marketplace_enforcement.py", command_text)
            self.assertIn("verify_platform_adoption_feedback_diagnostics.py", command_text)
            self.assertIn("generate_platform_feedback_package.py", command_text)
            self.assertIn("generate_platform_field_rehearsal.py", command_text)
            self.assertIn("verify_platform_field_rehearsal.py", command_text)
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("Private answer:", serialized)


class PlatformManualSubmissionRehearsalReportTests(unittest.TestCase):
    def test_manual_submission_rehearsal_report_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "verify_platform_manual_submission_rehearsal.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_manual_submission_rehearsal_report_privacy(self) -> None:
        root = Path(__file__).resolve().parents[3]
        report = json.loads(
            (
                root
                / "platform"
                / "generated"
                / "study-anything-platform-manual-submission-rehearsal.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "platform-manual-submission-rehearsal-v1")
        self.assertEqual(report["version"], "v0.3.30-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        self.assertFalse(report["privacy_assertions"]["raw_source_text_returned"])
        self.assertFalse(report["privacy_assertions"]["learner_answers_returned"])
        self.assertFalse(report["privacy_assertions"]["agent_endpoint_secrets_returned"])
        self.assertIn("runtime_unreachable", report["failure_remediation"])
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("Private answer:", serialized)
        self.assertNotIn("http://127.0.0.1:8787", serialized)


class FirstLessonAuthoringKitReportTests(unittest.TestCase):
    def test_first_lesson_authoring_kit_report_privacy(self) -> None:
        root = Path(__file__).resolve().parents[3]
        report = json.loads(
            (
                root / "platform" / "generated" / "study-anything-first-lesson-authoring-kit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "first-run-lesson-authoring-kit-v1")
        self.assertEqual(report["version"], "v0.3.30-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(set(report["copyable_prompts"]), {"en", "zh"})
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        self.assertFalse(report["privacy_assertions"]["learner_answers_returned"])
        self.assertFalse(report["privacy_assertions"]["agent_endpoint_secrets_returned"])
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("Private answer:", serialized)


class ExternalEvalHarnessReportTests(unittest.TestCase):
    def test_external_eval_harness_report_privacy(self) -> None:
        root = Path(__file__).resolve().parents[3]
        report = json.loads(
            (
                root / "platform" / "generated" / "study-anything-external-eval-harness.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "external-eval-marketplace-harness-v1")
        self.assertEqual(report["version"], "v0.3.30-alpha")
        self.assertEqual(report["status"], "pass")
        adapter_ids = {item["adapter_id"] for item in report["external_adapters"]}
        self.assertEqual(adapter_ids, {"promptfoo", "deepeval", "langchain-agentevals", "ragas"})
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        self.assertFalse(report["privacy_assertions"]["raw_source_text_in_eval_harness"])
        self.assertFalse(report["privacy_assertions"]["learner_answers_in_eval_harness"])
        self.assertFalse(report["privacy_assertions"]["agent_endpoint_secrets_in_eval_harness"])
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("Private answer:", serialized)


if __name__ == "__main__":
    unittest.main()
