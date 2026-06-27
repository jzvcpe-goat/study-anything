from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "verify_agent_eval_baseline.py"

sys.path.insert(0, str(REPO / "scripts"))
SPEC = importlib.util.spec_from_file_location("verify_agent_eval_baseline", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
agent_eval_baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_eval_baseline)


class AgentEvalBaselineTests(unittest.TestCase):
    def test_runtime_failure_payload_classifies_missing_dependency(self) -> None:
        payload = agent_eval_baseline.runtime_failure_payload(
            classification="python_dependency_missing",
            diagnostic=(
                "Python dependencies are missing at /private/tmp/study-anything "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            ),
            details={"missing_module": "tomllib"},
        )
        serialized = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["schema_version"], "agent-eval-baseline-error-v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "python_dependency_missing")
        self.assertIn(
            ".venv/bin/python scripts/verify_agent_eval_baseline.py --check",
            payload["next_steps"],
        )
        self.assertFalse(payload["privacy"]["local_absolute_paths_included"])
        self.assertFalse(payload["privacy"]["secrets_recorded"])
        self.assertIn("<temp-path>", serialized)
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertNotIn("/private/tmp", serialized)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", serialized)

    def test_agent_eval_baseline_is_current(self) -> None:
        root = REPO
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

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = agent_eval_baseline.format_cli_failure(
            RuntimeError(
                "baseline failed at /private/tmp/study-anything/baseline.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("verify_agent_eval_baseline failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("verify_agent_eval_baseline.py --check", message)
        self.assertIn("verify_agent_eval_baseline.py --write", message)
        self.assertIn("verify_agent_eval_assets.py", message)
        self.assertIn("docs/agent-eval.md", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)

    def test_agent_eval_baseline_payload_is_redacted(self) -> None:
        root = REPO
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
        root = REPO
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
