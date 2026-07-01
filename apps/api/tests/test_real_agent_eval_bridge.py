from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

REPO = Path(__file__).resolve().parents[3]


class RealAgentEvalBridgeTests(unittest.TestCase):
    def test_eval_bridge_report_is_current(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "verify_real_agent_eval_bridge.py"), "--check"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_eval_bridge_covers_required_adapters_and_privacy(self) -> None:
        report = json.loads(
            (REPO / "platform" / "generated" / "study-anything-real-agent-eval-bridge.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report["schema_version"], "real-agent-eval-bridge-verification-v1")
        self.assertEqual(report["status"], "pass")
        coverage = report["coverage"]
        self.assertTrue(coverage["promptfoo_adapter_receipt"])
        self.assertTrue(coverage["ragas_adapter_receipt"])
        self.assertTrue(coverage["deepeval_adapter_receipt"])
        self.assertTrue(coverage["langchain_agentevals_adapter_receipt"])
        self.assertTrue(coverage["user_owned_eval_environment_required"])
        self.assertTrue(coverage["missing_model_call_blocks"])
        self.assertTrue(coverage["adapter_failure_blocks"])
        bridge = report["bridge_report"]
        self.assertEqual(bridge["gate"]["status"], "allowed")
        self.assertFalse(bridge["privacy"]["model_calls_performed_by_study_anything"])
        self.assertFalse(bridge["privacy"]["model_keys_stored_by_study_anything"])

    def test_workbuddy_real_agent_learning_quality_report_is_current(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "verify_workbuddy_real_agent_learning_quality.py"),
                "--check",
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_workbuddy_quality_harness_blocks_low_quality_cases(self) -> None:
        report = json.loads(
            (
                REPO
                / "platform"
                / "generated"
                / "study-anything-workbuddy-real-agent-learning-quality.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "workbuddy-real-agent-learning-quality-verification-v1")
        self.assertEqual(report["status"], "pass")
        coverage = report["coverage"]
        self.assertTrue(coverage["same_task_compares_deterministic_http_and_platform_agents"])
        self.assertTrue(coverage["workbuddy_platform_agent_run"])
        self.assertTrue(coverage["kimi_platform_agent_run"])
        self.assertTrue(coverage["codex_platform_agent_run"])
        self.assertTrue(coverage["deterministic_demo_not_quality_proof"])
        self.assertTrue(coverage["deterministic_demo_gates_marked_demo_only"])
        self.assertTrue(coverage["missing_model_call_detected"])
        self.assertTrue(coverage["mechanical_restatement_blocked"])
        self.assertTrue(coverage["missing_citation_blocked"])
        self.assertTrue(coverage["high_cost_low_quality_blocked"])
        quality = report["quality_report"]
        self.assertEqual(quality["gate"]["status"], "allowed")
        self.assertEqual(quality["cost_quality_frontier"]["selected_run_id"], "workbuddy-platform-agent")
        demo_run = next(run for run in quality["runs"] if run["status"] == "demo_only")
        self.assertTrue(all(gate["status"] == "demo_only" for gate in demo_run["gates"]))

    def test_reports_do_not_include_private_payloads(self) -> None:
        for path in (
            REPO / "platform" / "generated" / "study-anything-real-agent-eval-bridge.json",
            REPO / "platform" / "generated" / "study-anything-workbuddy-real-agent-learning-quality.json",
        ):
            serialized = path.read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY=", serialized)
            self.assertNotIn("MOONSHOT_API_KEY=", serialized)
            self.assertNotIn("AGENT_LLM_API_KEY=", serialized)
            self.assertNotIn("raw private source text", serialized)
            self.assertNotIn("private answer:", serialized)
            self.assertNotIn("DeepSeek is a key idea in this source", serialized)


if __name__ == "__main__":
    unittest.main()
