from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
EVAL_DIR = REPO_ROOT / "evals" / "review-agent"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_eval_harness.py"


class CognitiveLoopReviewAgentEvalHarnessTests(unittest.TestCase):
    def test_eval_cases_cover_review_decision_paths(self) -> None:
        decisions = set()
        case_ids = set()
        for path in sorted((EVAL_DIR / "cases").glob("*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(case["schema_version"], "cognitive-loop-review-agent-eval-case-v1")
            self.assertIn("diff --git", case["input"]["git_diff"])
            self.assertTrue(case["input"]["pr_id"].startswith("eval-"))
            case_ids.add(case["case_id"])
            decisions.add(case["expected"]["decision"])

        self.assertEqual(
            case_ids,
            {"approved-docs", "needs-review-test-gap", "needs-fix-command-injection"},
        )
        self.assertEqual(decisions, {"approved", "needs-review", "needs-fix"})

    def test_golden_reports_include_security_cwe_and_suppression(self) -> None:
        needs_fix = json.loads((EVAL_DIR / "golden" / "needs-fix-command-injection.json").read_text(encoding="utf-8"))
        needs_review = json.loads((EVAL_DIR / "golden" / "needs-review-test-gap.json").read_text(encoding="utf-8"))
        privacy_leak = json.loads((EVAL_DIR / "bad" / "privacy-leak.json").read_text(encoding="utf-8"))

        self.assertEqual(needs_fix["decision"], "needs-fix")
        self.assertEqual(needs_fix["findings"][0]["severity"], "critical")
        self.assertIn("CWE-78", needs_fix["findings"][0]["cwe_references"])
        self.assertEqual(needs_review["decision"], "needs-review")
        self.assertEqual(needs_review["suppressed_low_confidence"][0]["confidence"], "low")
        self.assertIn("diff --git", privacy_leak["summary"])

    def test_eval_harness_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-eval-") as tmp:
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

        self.assertIn("cognitive-loop-review-agent-eval-harness-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["case_count"], 3)
        self.assertEqual(
            set(report["quality_gates"]["decision_path_coverage"]),
            {"approved", "needs-review", "needs-fix"},
        )
        self.assertEqual(report["quality_gates"]["critical_security_cwe"], "pass")
        self.assertEqual(report["quality_gates"]["privacy_leak_rejection"], "pass")


if __name__ == "__main__":
    unittest.main()
