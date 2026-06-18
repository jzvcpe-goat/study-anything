from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
RECEIPT_CLI = REPO_ROOT / "scripts" / "cognitive_loop_review_agent_receipt.py"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_ci_receipt.py"
REPORT_FIXTURES = REPO_ROOT / "fixtures" / "review-agent"
BAD_RECEIPT = REPO_ROOT / "fixtures" / "review-agent-receipts" / "raw-diff-leak.json"


class CognitiveLoopReviewAgentCiReceiptTests(unittest.TestCase):
    def test_receipt_cli_builds_metadata_only_needs_fix_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-receipt-") as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RECEIPT_CLI),
                    "build",
                    "--report",
                    str(REPORT_FIXTURES / "needs-fix.json"),
                    "--provider-id",
                    "ci-fixture-review-agent",
                    "--provider-label",
                    "CI fixture Review Agent",
                    "--execution-surface",
                    "ci",
                    "--pr-ref",
                    "PR-148",
                    "--commit-sha",
                    "9c8c0cdee6b33c7dd37115ddd0ed1101c60063f6",
                    "--base-ref",
                    "main",
                    "--head-ref",
                    "codex/review-agent-ci-receipt",
                    "--generated-at",
                    "2026-06-18T00:00:00+00:00",
                    "--output",
                    str(receipt_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertIn("cognitive-loop-review-agent-ci-receipt-v1", completed.stdout)
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["validated_report"]["decision"], "needs-fix")
        self.assertEqual(receipt["validated_report"]["critical_count"], 1)
        self.assertTrue(receipt["ci"]["should_block_merge"])
        serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("subprocess.run(user_command", serialized)
        self.assertNotIn("diff --git", serialized)
        self.assertFalse(receipt["privacy"]["raw_diff_included"])
        self.assertFalse(receipt["privacy"]["finding_evidence_included"])
        self.assertFalse(receipt["privacy"]["report_summary_included"])

    def test_receipt_cli_rejects_raw_diff_leak(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(RECEIPT_CLI),
                "validate",
                "--receipt",
                str(BAD_RECEIPT),
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("diff --git", completed.stderr)

    def test_ci_receipt_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-ci-receipt-") as tmp:
            output = Path(tmp) / "report.json"
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

        self.assertIn("cognitive-loop-review-agent-ci-receipt-verification-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["receipt_count"], 3)
        self.assertEqual(
            set(report["quality_gates"]["decision_path_coverage"]),
            {"approved", "needs-review", "needs-fix"},
        )
        self.assertEqual(report["quality_gates"]["metadata_only_receipts"], "pass")
        self.assertEqual(report["quality_gates"]["privacy_leak_rejection"], "pass")


if __name__ == "__main__":
    unittest.main()
