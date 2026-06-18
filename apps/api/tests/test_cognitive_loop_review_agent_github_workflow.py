from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_github_workflow.py"
WORKFLOW = REPO_ROOT / "platform" / "workflows" / "cognitive-loop-review-agent-manual.yml"
UNSAFE_WORKFLOW = REPO_ROOT / "fixtures" / "review-agent-github-workflows" / "unsafe-auto-pr.yml"


class CognitiveLoopReviewAgentGithubWorkflowTests(unittest.TestCase):
    def test_workflow_template_is_manual_and_metadata_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", text)
        self.assertIn("scripts/cognitive_loop_review_agent_acceptance_bundle.py build", text)
        self.assertIn("GITHUB_STEP_SUMMARY", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertNotIn("path: REVIEW_AGENT_REPORT.json", text)

    def test_unsafe_workflow_fixture_contains_expected_risks(self) -> None:
        text = UNSAFE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request:", text)
        self.assertIn("diff --git", text)
        self.assertIn("OPENAI_API_KEY", text)
        self.assertIn("raw-review-agent-report", text)

    def test_github_workflow_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-github-workflow-report-") as tmp_name:
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

        self.assertIn("cognitive-loop-review-agent-github-workflow-verification-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["quality_gates"]["manual_only_trigger"], "pass")
        self.assertEqual(report["quality_gates"]["metadata_only_artifact_upload"], "pass")
        self.assertEqual(report["quality_gates"]["unsafe_workflow_rejection"], "pass")
        self.assertFalse(report["privacy"]["raw_report_uploaded"])
        self.assertEqual(
            set(report["quality_gates"]["decision_path_coverage"]),
            {"approved", "needs-review", "needs-fix"},
        )


if __name__ == "__main__":
    unittest.main()
