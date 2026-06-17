from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "verify_multiteacher_agent_eval_hardening.py"


class MultiTeacherAgentEvalHardeningTest(unittest.TestCase):
    def test_verifier_proves_fake_and_external_agent_attribution(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "multiteacher-agent-eval-hardening-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertTrue(payload["fake_agent"]["used_fake_agent"])
        self.assertFalse(payload["fake_agent"]["used_external_agent"])
        self.assertTrue(payload["external_agent"]["used_external_agent"])
        self.assertFalse(payload["external_agent"]["used_fake_agent"])
        self.assertEqual(
            set(payload["contract"]["required_multi_teacher_tasks"]),
            set(payload["external_agent"]["http_agent_received_tasks"]),
        )
        self.assertFalse(payload["privacy"]["raw_source_text_returned"])
        self.assertFalse(payload["privacy"]["learner_answers_returned"])
        self.assertFalse(payload["privacy"]["secrets_returned"])
        self.assertEqual(
            payload["failure_modes"]["missing_attribution"]["audit_status"],
            "partial",
        )
        self.assertEqual(
            payload["failure_modes"]["missing_attribution"]["artifact_status"],
            "blocked",
        )
        self.assertEqual(
            set(payload["failure_modes"]["missing_attribution"]["missing_tasks"]),
            {"teach.overview", "teach.glossary"},
        )
        self.assertEqual(
            payload["failure_modes"]["forged_attribution"]["audit_status"],
            "invalid_provider_evidence",
        )
        self.assertEqual(
            payload["failure_modes"]["forged_attribution"]["unregistered_provider_ids"],
            ["forged-provider"],
        )
        self.assertTrue(payload["failure_modes"]["privacy_redaction_failure_detected"])
        self.assertEqual(
            payload["failure_modes"]["external_judge_missing_runtime"]["required_mode"],
            "non_zero_exit",
        )


if __name__ == "__main__":
    unittest.main()
