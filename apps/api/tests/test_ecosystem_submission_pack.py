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
        self.assertEqual(payload["version"], "v0.3.4-alpha")
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
        self.assertEqual(submission["version"], "v0.3.4-alpha")
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


if __name__ == "__main__":
    unittest.main()
