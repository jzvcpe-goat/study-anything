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
        self.assertEqual(payload["version"], "v0.3.12-alpha")
        self.assertTrue(payload["no_frontend_required"])
        self.assertFalse(payload["real_model_keys_stored_by_study_anything"])
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
        self.assertEqual(submission["version"], "v0.3.12-alpha")
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
        self.assertIn("docs/eval-frameworks.md", submission["shared_assets"])
        self.assertIn("scripts/verify_external_agent_adapter_hardening.py", submission["shared_assets"])
        self.assertIn("scripts/verify_platform_manual_submission_rehearsal.py", submission["shared_assets"])
        self.assertIn("scripts/verify_first_lesson_authoring_kit.py", submission["shared_assets"])
        self.assertIn("scripts/verify_external_eval_marketplace_harness.py", submission["shared_assets"])
        commands = "\n".join(submission["acceptance"]["minimum_commands"])
        self.assertIn("verify_platform_submission_dry_run.py", commands)
        self.assertIn("verify_platform_manual_submission_rehearsal.py", commands)
        self.assertIn("verify_first_lesson_authoring_kit.py", commands)
        self.assertIn("verify_external_eval_marketplace_harness.py", commands)
        self.assertIn("verify_external_agent_adapter_hardening.py", commands)


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
        self.assertEqual(report["version"], "v0.3.12-alpha")
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
        self.assertEqual(report["version"], "v0.3.12-alpha")
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
        self.assertEqual(report["version"], "v0.3.12-alpha")
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
        self.assertEqual(report["version"], "v0.3.12-alpha")
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
