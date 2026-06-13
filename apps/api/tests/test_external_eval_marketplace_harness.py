from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


class ExternalEvalMarketplaceHarnessTests(unittest.TestCase):
    def test_external_eval_marketplace_harness_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "verify_external_eval_marketplace_harness.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_external_eval_marketplace_harness_privacy_and_adapters(self) -> None:
        root = Path(__file__).resolve().parents[3]
        report = json.loads(
            (
                root
                / "platform"
                / "generated"
                / "study-anything-external-eval-harness.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "external-eval-marketplace-harness-v1")
        self.assertEqual(report["version"], "v0.3.12-alpha")
        self.assertEqual(report["status"], "pass")
        adapter_ids = {item["adapter_id"] for item in report["external_adapters"]}
        self.assertEqual(adapter_ids, {"promptfoo", "deepeval", "langchain-agentevals", "ragas"})
        self.assertGreaterEqual(len(report["native_fast_gates"]), 4)
        self.assertGreaterEqual(len(report["sample_eval_cases"]), 4)
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        self.assertFalse(
            report["privacy_assertions"]["real_model_or_judge_keys_stored_by_study_anything"]
        )
        self.assertFalse(report["privacy_assertions"]["raw_source_text_in_eval_harness"])
        self.assertFalse(report["privacy_assertions"]["learner_answers_in_eval_harness"])
        self.assertFalse(report["privacy_assertions"]["agent_endpoint_secrets_in_eval_harness"])
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("Private answer:", serialized)
        self.assertNotIn("http://127.0.0.1:8787", serialized)


if __name__ == "__main__":
    unittest.main()
