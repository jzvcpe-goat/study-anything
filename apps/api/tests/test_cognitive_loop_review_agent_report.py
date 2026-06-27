from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
SCHEMA_PATH = REPO_ROOT / "platform" / "schemas" / "cognitive-loop-review-agent-report.schema.json"
FIXTURE_DIR = REPO_ROOT / "fixtures" / "review-agent"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_report.py"


class CognitiveLoopReviewAgentReportTests(unittest.TestCase):
    def test_report_schema_caps_findings_and_suppresses_low_confidence(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["$id"],
            "https://study-anything.local/schemas/cognitive-loop-review-agent-report-v1.json",
        )
        self.assertEqual(schema["properties"]["findings"]["maxItems"], 8)
        self.assertEqual(
            schema["$defs"]["finding"]["properties"]["confidence"]["enum"],
            ["medium", "high"],
        )
        self.assertEqual(
            schema["$defs"]["suppressedFinding"]["properties"]["confidence"]["const"],
            "low",
        )

    def test_report_fixtures_cover_decision_paths(self) -> None:
        approved = json.loads((FIXTURE_DIR / "approved.json").read_text(encoding="utf-8"))
        needs_review = json.loads((FIXTURE_DIR / "needs-review.json").read_text(encoding="utf-8"))
        needs_fix = json.loads((FIXTURE_DIR / "needs-fix.json").read_text(encoding="utf-8"))
        invalid = json.loads((FIXTURE_DIR / "invalid-low-confidence-final.json").read_text(encoding="utf-8"))

        self.assertEqual(approved["decision"], "approved")
        self.assertEqual(needs_review["decision"], "needs-review")
        self.assertEqual(needs_fix["decision"], "needs-fix")
        self.assertTrue(needs_fix["ci_instructions"]["should_block_merge"])
        self.assertEqual(needs_review["suppressed_low_confidence"][0]["confidence"], "low")
        self.assertEqual(invalid["findings"][0]["confidence"], "low")

    def test_report_verifier_generates_handoff_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-report-") as tmp:
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

        self.assertIn("cognitive-loop-review-agent-report-handoff-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["acceptance"]["max_findings"], 8)
        self.assertFalse(report["privacy"]["raw_diff_stored_by_study_anything"])
        self.assertIn("invalid-low-confidence-final.json", report["negative_fixtures"])


if __name__ == "__main__":
    unittest.main()
