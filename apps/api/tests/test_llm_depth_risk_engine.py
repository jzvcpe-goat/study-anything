from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

REPO = Path(__file__).resolve().parents[3]


class LLMDepthRiskEngineTests(unittest.TestCase):
    def test_verifier_report_is_current(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "verify_llm_depth_risk_engine.py"),
                "--check",
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_generated_report_covers_llm_depth_dimensions(self) -> None:
        report = json.loads(
            (REPO / "platform" / "generated" / "study-anything-llm-depth-risk-engine.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report["schema_version"], "llm-depth-risk-engine-verification-v1")
        self.assertEqual(report["status"], "pass")
        coverage = report["coverage"]
        self.assertTrue(coverage["prompt_evidence"])
        self.assertTrue(coverage["hallucination_evidence"])
        self.assertTrue(coverage["rag_evidence"])
        self.assertTrue(coverage["context_budget_evidence"])
        self.assertTrue(coverage["cost_quality_evidence"])
        self.assertTrue(coverage["risk_engine_summary_gate"])
        self.assertTrue(coverage["engineering_and_model_risk_both_required"])

        engine = report["engine_report"]
        self.assertEqual(engine["risk_gate"]["schema_version"], "llm-depth-risk-gate-v1")
        self.assertEqual(engine["risk_gate"]["status"], "allowed")
        self.assertEqual(engine["evidence"]["prompt"]["schema_version"], "prompt-evidence-v1")
        self.assertEqual(engine["evidence"]["hallucination"]["schema_version"], "hallucination-evidence-v1")
        self.assertEqual(engine["evidence"]["rag"]["schema_version"], "rag-evidence-v1")
        self.assertEqual(
            engine["evidence"]["context_budget"]["schema_version"],
            "context-budget-evidence-v1",
        )
        self.assertEqual(engine["evidence"]["cost_quality"]["schema_version"], "cost-quality-evidence-v1")

        self.assertEqual(report["negative_fixtures"]["blocked_model_risk"]["risk_gate"], "blocked")
        self.assertEqual(report["negative_fixtures"]["blocked_engineering_risk"]["risk_gate"], "blocked")

    def test_report_privacy_boundaries(self) -> None:
        serialized = (
            REPO / "platform" / "generated" / "study-anything-llm-depth-risk-engine.json"
        ).read_text(encoding="utf-8")
        self.assertNotIn("OPENAI_API_KEY=", serialized)
        self.assertNotIn("MOONSHOT_API_KEY=", serialized)
        self.assertNotIn("AGENT_LLM_API_KEY=", serialized)
        self.assertNotIn("raw private source text", serialized)
        self.assertNotIn("private answer:", serialized)
        self.assertNotIn("http://127.0.0.1:8787", serialized)


if __name__ == "__main__":
    unittest.main()
