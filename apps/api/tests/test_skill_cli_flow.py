from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_skill_cli_flow",
    REPO_ROOT / "scripts" / "verify_skill_cli_flow.py",
)
assert SPEC is not None and SPEC.loader is not None
skill_cli_flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill_cli_flow)


class SkillCliFlowVerifierTests(unittest.TestCase):
    def test_api_base_reads_env_file_api_port_when_no_explicit_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text('export API_PORT="18080" # local override\n', encoding="utf-8")

            with patch.dict(
                os.environ,
                {"STUDY_ANYTHING_ENV_FILE": str(env_file)},
                clear=True,
            ):
                self.assertEqual(skill_cli_flow.api_base(), "http://127.0.0.1:18080")

    def test_api_base_explicit_env_wins_over_env_file_api_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("API_PORT=18080\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "STUDY_ANYTHING_ENV_FILE": str(env_file),
                    "API_BASE": "http://127.0.0.1:19090",
                },
                clear=True,
            ):
                self.assertEqual(skill_cli_flow.api_base(), "http://127.0.0.1:19090")

    def test_cli_failure_is_actionable_and_redacted(self) -> None:
        completed = subprocess.CompletedProcess(
            ["python", str(REPO_ROOT / "scripts" / "study_anything_cli.py"), "--json", "teach", "--session", "abc"],
            2,
            stdout=f"debug path {REPO_ROOT}\n",
            stderr="error: unrecognized arguments: --session\n",
        )
        with patch.object(skill_cli_flow.subprocess, "run", return_value=completed):
            with patch.dict(os.environ, {"API_BASE": "http://127.0.0.1:8123"}, clear=False):
                with self.assertRaises(skill_cli_flow.SkillCliFlowError) as context:
                    skill_cli_flow.run_cli("teach", "--session", "abc")

        message = str(context.exception)
        self.assertIn("Skill Mode CLI verification step failed", message)
        self.assertIn("Command: python3 scripts/study_anything_cli.py --json teach --session abc", message)
        self.assertIn("API base: http://127.0.0.1:8123", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("real session id printed by `start`, `demo`, or `sessions`", message)
        self.assertNotIn("positional SESSION_ID", message)
        self.assertIn("<local-path>", message)
        self.assertNotIn(str(REPO_ROOT), message)

    def test_non_json_output_is_actionable(self) -> None:
        completed = subprocess.CompletedProcess(
            ["python", str(REPO_ROOT / "scripts" / "study_anything_cli.py"), "--json", "health"],
            0,
            stdout="not json\n",
            stderr="",
        )
        with patch.object(skill_cli_flow, "run_cli", return_value=completed):
            with self.assertRaises(skill_cli_flow.SkillCliFlowError) as context:
                skill_cli_flow.parsed("health")

        message = str(context.exception)
        self.assertIn("returned non-JSON output", message)
        self.assertIn("Confirm the API and CLI versions", message)
        self.assertIn("not json", message)

    def test_failure_report_classifies_cli_argument_error(self) -> None:
        report = skill_cli_flow.failure_report(
            skill_cli_flow.SkillCliFlowError(
                "Skill Mode CLI verification step failed.\n"
                "stderr:\nerror: unrecognized arguments: --session\n"
            )
        )

        self.assertEqual(report["classification"], "cli_argument_error")
        next_steps = " ".join(report["next_steps"])
        self.assertIn("real session id printed by `start`, `demo`, or `sessions`", next_steps)
        self.assertNotIn("SESSION_ID", next_steps)

    def test_discard_guard_accepts_json_error_on_stdout(self) -> None:
        refused = subprocess.CompletedProcess(
            ["python", str(REPO_ROOT / "scripts" / "study_anything_cli.py"), "--json", "discard", "session-1"],
            1,
            stdout='{"diagnostic":"Discard requires explicit approval. Re-run with --yes."}\n',
            stderr="",
        )
        refused_output = f"{refused.stdout}\n{refused.stderr}"

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("explicit approval", refused_output)

    def test_failure_report_redacts_demo_private_data(self) -> None:
        report = skill_cli_flow.failure_report(
            skill_cli_flow.SkillCliFlowError(
                "Expected completed CLI demo for skill-smoke-user with "
                "A learning loop should bind a question to its source, grade a grounded answer, update mastery, and synthesize a reusable insight. "
                "The learning loop uses source evidence to grade an answer and update mastery. "
                "path=/Users/example/project token=supersecret123"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertEqual(report["classification"], "learning_flow_incomplete")
        self.assertIn("<private-user>", serialized)
        self.assertIn("<private-source-text>", serialized)
        self.assertIn("<private-answer>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("skill-smoke-user", serialized)
        self.assertNotIn("A learning loop should bind", serialized)
        self.assertNotIn("The learning loop uses source evidence", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("supersecret123", serialized)


if __name__ == "__main__":
    unittest.main()
