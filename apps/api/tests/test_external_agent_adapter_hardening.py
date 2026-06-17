from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


class ExternalAgentAdapterHardeningTests(unittest.TestCase):
    def test_external_agent_adapter_hardening_report_passes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "verify_external_agent_adapter_hardening.py")],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "external-agent-adapter-hardening-v1")
        self.assertEqual(report["version"], "v0.3.30-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["external_agent_eval"]["used_external_agent"])
        self.assertFalse(report["external_agent_eval"]["used_fake_agent"])
        self.assertEqual(report["external_agent_eval"]["native_fast_gate_status"], "pass")
        self.assertTrue(report["privacy"]["secret_like_metadata_values_redacted"])
        cases = {case["case_id"] for case in report["bad_agent_cases"]}
        self.assertEqual(
            cases,
            {
                "malformed_json",
                "invalid_status",
                "missing_content",
                "invalid_score",
                "invalid_confidence",
                "timeout",
                "missing_citations",
                "missing_capability",
            },
        )
        serialized = json.dumps(report)
        self.assertNotIn("Private external Agent hardening source text", serialized)
        self.assertNotIn("Private external Agent hardening answer", serialized)
        self.assertNotIn("sk-proj-agentVerifierSecretToken000000", serialized)


if __name__ == "__main__":
    unittest.main()
