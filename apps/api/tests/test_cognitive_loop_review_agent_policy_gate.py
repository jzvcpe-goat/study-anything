from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
BUNDLE_CLI = REPO_ROOT / "scripts" / "cognitive_loop_review_agent_acceptance_bundle.py"
POLICY_GATE_CLI = REPO_ROOT / "scripts" / "cognitive_loop_review_agent_policy_gate.py"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_policy_gate.py"
FIXTURES = REPO_ROOT / "fixtures" / "review-agent"


class CognitiveLoopReviewAgentPolicyGateTests(unittest.TestCase):
    def build_bundle(self, fixture_name: str, output_dir: Path) -> None:
        subprocess.run(
            [
                sys.executable,
                str(BUNDLE_CLI),
                "build",
                "--report",
                str(FIXTURES / fixture_name),
                "--output-dir",
                str(output_dir),
                "--provider-id",
                "unit-test-review-agent",
                "--provider-label",
                "Unit test Review Agent",
                "--execution-surface",
                "ci",
                "--pr-ref",
                "PR-unit",
                "--commit-sha",
                "sha-unit",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )

    def test_soft_policy_blocks_needs_fix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-policy-gate-test-") as tmp_name:
            bundle_dir = Path(tmp_name) / "bundle"
            output = Path(tmp_name) / "gate.json"
            self.build_bundle("needs-fix.json", bundle_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(POLICY_GATE_CLI),
                    "--bundle-dir",
                    str(bundle_dir),
                    "--policy",
                    "soft",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(payload["schema_version"], "cognitive-loop-review-agent-policy-gate-v1")
        self.assertEqual(payload["policy"], "soft")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["decision_summary"]["decision"], "needs-fix")
        self.assertFalse(payload["privacy"]["raw_diff_included"])
        self.assertFalse(payload["privacy"]["real_model_keys_included"])

    def test_strict_policy_blocks_needs_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-policy-gate-test-") as tmp_name:
            bundle_dir = Path(tmp_name) / "bundle"
            output = Path(tmp_name) / "gate.json"
            self.build_bundle("needs-review.json", bundle_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(POLICY_GATE_CLI),
                    "--bundle-dir",
                    str(bundle_dir),
                    "--policy",
                    "strict",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(payload["policy"], "strict")
        self.assertEqual(payload["decision_summary"]["decision"], "needs-review")
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["policy_result"]["failed"])

    def test_policy_gate_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-policy-gate-report-") as tmp_name:
            output = Path(tmp_name) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY_SCRIPT),
                    "--write",
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertIn("cognitive-loop-review-agent-policy-gate-verification-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["policy_matrix"]["advisory"]["needs-fix"], 0)
        self.assertEqual(report["policy_matrix"]["soft"]["needs-fix"], 2)
        self.assertEqual(report["policy_matrix"]["strict"]["needs-review"], 2)
        self.assertEqual(report["quality_gates"]["bundle_and_receipt_parity"], "pass")


if __name__ == "__main__":
    unittest.main()
