from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from _path import ROOT


REPO_ROOT = ROOT.parents[1]
PROMPT_PATH = REPO_ROOT / "platform" / "prompts" / "cognitive-loop-review-agent.json"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_cognitive_loop_review_agent_prompt.py"


class CognitiveLoopReviewAgentPromptTests(unittest.TestCase):
    def test_prompt_contract_keeps_review_agent_out_of_learning_product(self) -> None:
        payload = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))

        boundary = payload["product_boundary"]
        self.assertTrue(boundary["delivery_assurance_tooling"])
        self.assertFalse(boundary["end_user_learning_feature"])
        self.assertFalse(boundary["generates_business_feature_code"])
        self.assertEqual(boundary["study_anything_learning_adapter"], "out_of_scope")
        self.assertEqual(boundary["model_key_custody"], "external_only")
        self.assertEqual(boundary["diff_storage_in_study_anything"], "forbidden")
        self.assertEqual(payload["output_discipline"]["format"], "json_only")
        self.assertEqual(payload["output_discipline"]["max_findings"], 8)
        self.assertEqual(payload["confidence_rules"]["final_report_confidence"], ["high", "medium"])
        self.assertEqual(payload["confidence_rules"]["suppressed_confidence"], ["low"])

    def test_prompt_verifier_generates_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-review-agent-prompt-") as tmp:
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

        self.assertIn("cognitive-loop-review-agent-prompt-verification-v1", completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["privacy"]["study_anything_stores_diff"])
        self.assertFalse(report["privacy"]["study_anything_stores_model_keys"])
        self.assertEqual(report["checks"]["external_max_findings"], 8)


if __name__ == "__main__":
    unittest.main()
