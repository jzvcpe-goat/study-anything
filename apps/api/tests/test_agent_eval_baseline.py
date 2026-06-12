from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


class AgentEvalBaselineTests(unittest.TestCase):
    def test_agent_eval_baseline_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "verify_agent_eval_baseline.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "study-anything-agent-eval-regression-report-v1")
        self.assertEqual(report["status"], "pass")

    def test_agent_eval_baseline_payload_is_redacted(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "verify_agent_eval_baseline.py")],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "study-anything-agent-eval-baseline-v1")
        self.assertEqual(payload["scorecard"]["status"], "pass")
        serialized = json.dumps(payload)
        self.assertNotIn("Baseline source text", serialized)
        self.assertNotIn("Baseline answer text", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_agent_eval_baseline_compare_fails_on_score_regression(self) -> None:
        root = Path(__file__).resolve().parents[3]
        baseline_path = root / "evals" / "baselines" / "study-anything-agent-eval-baseline.json"
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        payload["scorecard"]["quality_score"] = 0.999
        with tempfile.TemporaryDirectory(prefix="study-anything-bad-baseline-") as tmp:
            bad = Path(tmp) / "baseline.json"
            bad.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "verify_agent_eval_baseline.py"),
                    "--baseline",
                    str(bad),
                    "--check",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "fail")
        failed = [check["check_id"] for check in report["checks"] if check["status"] != "pass"]
        self.assertIn("quality_score_not_regressed", failed)


if __name__ == "__main__":
    unittest.main()
