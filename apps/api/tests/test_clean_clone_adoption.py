from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


SPEC = importlib.util.spec_from_file_location(
    "verify_clean_clone_adoption",
    REPO_ROOT / "scripts" / "verify_clean_clone_adoption.py",
)
assert SPEC is not None and SPEC.loader is not None
clean_clone = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clean_clone)


class CleanCloneAdoptionVerifierTests(unittest.TestCase):
    def test_explicit_api_port_skips_port_probe(self) -> None:
        with patch.object(clean_clone, "free_port", side_effect=AssertionError("unexpected probe")):
            self.assertEqual(clean_clone.select_api_port(8123), 8123)

    def test_invalid_explicit_api_port_is_actionable(self) -> None:
        with self.assertRaisesRegex(clean_clone.CleanCloneAdoptionError, "--api-port"):
            clean_clone.select_api_port(0)

    def test_explicit_promptfoo_api_port_skips_port_probe(self) -> None:
        with patch.object(clean_clone, "reserve_free_port", side_effect=AssertionError("unexpected probe")):
            self.assertEqual(clean_clone.select_promptfoo_api_port(9123), 9123)

    def test_invalid_explicit_promptfoo_api_port_is_actionable(self) -> None:
        with self.assertRaisesRegex(clean_clone.CleanCloneAdoptionError, "--promptfoo-api-port"):
            clean_clone.select_promptfoo_api_port(70000)

    def test_promptfoo_api_port_failure_is_classified_as_cli_input(self) -> None:
        report = clean_clone.failure_report(
            clean_clone.CleanCloneAdoptionError("--promptfoo-api-port must be between 1 and 65535.")
        )

        self.assertEqual(report["classification"], "invalid_cli_input")

    def test_cli_rejects_invalid_promptfoo_api_port_before_port_probe(self) -> None:
        completed = subprocess.run(
            [
                clean_clone.sys.executable,
                str(REPO_ROOT / "scripts" / "verify_clean_clone_adoption.py"),
                "--promptfoo-api-port",
                "70000",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["classification"], "invalid_cli_input")
        self.assertIn("--promptfoo-api-port", payload["diagnostic"])
        self.assertNotIn("localhost_socket_blocked", completed.stdout)

    def test_port_probe_failure_is_actionable(self) -> None:
        with patch.object(
            clean_clone,
            "free_port",
            side_effect=OSError(1, "Operation not permitted"),
        ):
            with self.assertRaisesRegex(clean_clone.CleanCloneAdoptionError, "normal terminal"):
                clean_clone.select_api_port(None)

    def test_permission_denied_port_probe_failure_is_actionable(self) -> None:
        with patch.object(
            clean_clone,
            "free_port",
            side_effect=OSError(13, "Permission denied"),
        ):
            with self.assertRaisesRegex(clean_clone.CleanCloneAdoptionError, "normal terminal"):
                clean_clone.select_api_port(None)

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        temp_path = "/private/" + "tmp/study-anything/adoption"
        fake_token = "sk-proj-" + "abcdefghijklmnop123456"
        message = clean_clone.format_cli_failure(
            RuntimeError(
                f"clone failed at {temp_path} "
                f"with Authorization: Bearer {fake_token}"
            )
        )

        self.assertIn("verify_clean_clone_adoption failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("run_skill_mode_demo.sh", message)
        self.assertIn("normal terminal", message)
        self.assertIn("PIP_INDEX_URL", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/" + "tmp", message)
        self.assertNotIn(fake_token, message)

    def test_failure_report_classifies_localhost_socket_blocked(self) -> None:
        report = clean_clone.failure_report(
            clean_clone.CleanCloneAdoptionError(
                "Local Skill Mode API could not bind to localhost from this runner. "
                "This usually means the current agent sandbox blocks localhost listening sockets."
            )
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"], "localhost_socket_blocked")
        self.assertIn("normal terminal", " ".join(report["next_steps"]))
        self.assertFalse(report["privacy"]["real_model_keys_included"])

    def test_failure_report_classifies_dependency_install(self) -> None:
        report = clean_clone.failure_report(
            clean_clone.CleanCloneAdoptionError(
                "Python dependency installation failed while preparing the disposable clean-clone "
                "environment. Relevant output: No matching distribution found for setuptools"
            )
        )

        self.assertEqual(report["classification"], "dependency_install_failed")
        self.assertIn("PIP_INDEX_URL", " ".join(report["next_steps"]))

    def test_failure_report_classifies_dependency_install_timeout(self) -> None:
        report = clean_clone.failure_report(
            clean_clone.CleanCloneAdoptionError(
                "Python dependency installation failed while preparing the disposable clean-clone "
                "environment. Relevant output: [study-anything] dependency installation timed out "
                "after 600s. Increase SKILL_PIP_INSTALL_TIMEOUT_SECONDS."
            )
        )

        next_steps = " ".join(report["next_steps"])
        self.assertEqual(report["classification"], "dependency_install_failed")
        self.assertIn("PIP_INSTALL_TIMEOUT_SECONDS", next_steps)
        self.assertIn("SKILL_PIP_INSTALL_TIMEOUT_SECONDS", next_steps)
        self.assertIn("PIP_DEFAULT_TIMEOUT", next_steps)

    def test_failure_report_is_redacted_for_agent_consumption(self) -> None:
        local_home = "/Users/" + "example"
        fake_token = "sk-proj-" + "abcdefghijklmnop123456"
        report = clean_clone.failure_report(
            RuntimeError(
                f"clone failed in {local_home}/repo with token=supersecret123 "
                f"and Authorization: Bearer {fake_token}"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertNotIn(local_home, serialized)
        self.assertNotIn("supersecret123", serialized)
        self.assertNotIn(fake_token, serialized)

    def test_cli_failure_path_emits_machine_json_and_human_stderr(self) -> None:
        completed = subprocess.run(
            [
                clean_clone.sys.executable,
                str(REPO_ROOT / "scripts" / "verify_clean_clone_adoption.py"),
                "--api-port",
                "0",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "invalid_cli_input")
        self.assertIn("verify_clean_clone_adoption failed:", completed.stderr)
        self.assertIn("Next steps:", completed.stderr)

    def test_local_bind_failure_is_actionable(self) -> None:
        completed = clean_clone.subprocess.CompletedProcess(
            ["sh", "scripts/run_skill_mode_demo.sh"],
            1,
            stdout="Starting Study Anything Skill API at http://127.0.0.1:18080 ...",
            stderr=(
                "ERROR: [Errno 1] error while attempting to bind on address "
                "('127.0.0.1', 18080): operation not permitted"
            ),
        )
        with patch.object(clean_clone.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(clean_clone.CleanCloneAdoptionError, "normal terminal"):
                clean_clone.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=5,
                )

    def test_local_bind_permission_denied_failure_is_actionable(self) -> None:
        completed = clean_clone.subprocess.CompletedProcess(
            ["sh", "scripts/run_skill_mode_demo.sh"],
            1,
            stdout="Starting Study Anything Skill API at http://127.0.0.1:18080 ...",
            stderr=(
                "ERROR: [Errno 13] error while attempting to bind on address "
                "('127.0.0.1', 18080): permission denied"
            ),
        )
        with patch.object(clean_clone.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(clean_clone.CleanCloneAdoptionError, "normal terminal"):
                clean_clone.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=5,
                )

    def test_launch_script_bind_preflight_message_is_actionable(self) -> None:
        completed = clean_clone.subprocess.CompletedProcess(
            ["sh", "scripts/run_skill_mode_demo.sh"],
            3,
            stdout="",
            stderr=(
                "Local Skill Mode API cannot listen on 127.0.0.1:18080 from this runner.\n"
                "This usually means the current agent sandbox blocks localhost listening sockets.\n"
            ),
        )
        with patch.object(clean_clone.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(
                clean_clone.CleanCloneAdoptionError,
                "could not bind to localhost",
            ):
                clean_clone.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=5,
                )

    def test_dependency_download_failure_is_actionable(self) -> None:
        completed = clean_clone.subprocess.CompletedProcess(
            ["sh", "scripts/run_skill_mode_demo.sh"],
            1,
            stdout="Installing backend dependencies into .venv ...",
            stderr=(
                "pip subprocess to install build dependencies did not run successfully\n"
                "WARNING: Retrying after connection broken by "
                "'NewConnectionError': Failed to establish a new connection\n"
                "Failed to establish a new connection: [Errno 8] nodename nor servname provided "
                f"path={'/private/' + 'tmp/study-anything-build'} token=supersecret123\n"
                "ERROR: Could not find a version that satisfies the requirement setuptools>=40.8.0\n"
                "ERROR: No matching distribution found for setuptools>=40.8.0\n"
            ),
        )
        with patch.object(clean_clone.subprocess, "run", return_value=completed):
            with self.assertRaises(clean_clone.CleanCloneAdoptionError) as context:
                clean_clone.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=5,
                )
        message = str(context.exception)
        self.assertIn("Python dependency installation failed", message)
        self.assertIn("PyPI", message)
        self.assertIn("PIP_INDEX_URL", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)
        self.assertIn("Command: sh scripts/run_skill_mode_demo.sh", message)
        self.assertIn("Relevant output", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("token=<redacted>", message)
        self.assertNotIn("WARNING: Retrying", message)
        self.assertNotIn("/private/" + "tmp", message)
        self.assertNotIn("supersecret123", message)

    def test_dependency_download_timeout_is_actionable(self) -> None:
        completed = clean_clone.subprocess.CompletedProcess(
            ["sh", "scripts/run_skill_mode_demo.sh"],
            1,
            stdout="Installing Study Anything API dependencies ...",
            stderr=(
                "[study-anything] dependency installation timed out after 600s.\n"
                "[study-anything] retry from a networked terminal, set PIP_INDEX_URL, "
                "or increase SKILL_PIP_INSTALL_TIMEOUT_SECONDS.\n"
            ),
        )
        with patch.object(clean_clone.subprocess, "run", return_value=completed):
            with self.assertRaises(clean_clone.CleanCloneAdoptionError) as context:
                clean_clone.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=5,
                )

        message = str(context.exception)
        self.assertIn("Python dependency installation failed", message)
        self.assertIn("bounded install timeout", message)
        self.assertIn("PIP_INSTALL_TIMEOUT_SECONDS", message)
        self.assertIn("SKILL_PIP_INSTALL_TIMEOUT_SECONDS", message)
        self.assertIn("PIP_INDEX_URL", message)

    def test_clean_clone_env_bounds_pip_install_for_new_users(self) -> None:
        with (
            patch.object(clean_clone, "find_python_311", return_value="/opt/python3.11"),
            patch.dict(
                clean_clone.os.environ,
                {
                    "PIP_DEFAULT_TIMEOUT": "90",
                    "PIP_RETRIES": "1",
                    "PIP_INSTALL_TIMEOUT_SECONDS": "777",
                },
                clear=True,
            ),
        ):
            env = clean_clone.make_env(Path("/clone"), Path("/work"), api_port=8123)

        self.assertEqual(env["PYTHON_BIN"], "/opt/python3.11")
        self.assertEqual(env["PIP_DISABLE_PIP_VERSION_CHECK"], "1")
        self.assertEqual(env["PIP_DEFAULT_TIMEOUT"], "90")
        self.assertEqual(env["PIP_RETRIES"], "1")
        self.assertEqual(env["PIP_NO_INPUT"], "1")
        self.assertEqual(env["SKILL_PIP_INSTALL_TIMEOUT_SECONDS"], "777")
        self.assertEqual(env["PIP_INSTALL_TIMEOUT_SECONDS"], "777")

    def test_generic_command_failure_is_actionable_and_redacted(self) -> None:
        completed = clean_clone.subprocess.CompletedProcess(
            ["git", "clone", "bad", "target"],
            128,
            stdout=f"using source {REPO_ROOT}\n",
            stderr="fatal: authentication token=supersecret123 failed\n",
        )
        with patch.object(clean_clone.subprocess, "run", return_value=completed):
            with self.assertRaises(clean_clone.CleanCloneAdoptionError) as context:
                clean_clone.run(
                    ["git", "clone", "bad", "target"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=5,
                )
        message = str(context.exception)
        self.assertIn("Clean-clone adoption command exited with 128", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("launch_skill_mode.sh", message)
        self.assertIn("<local-path>", message)
        self.assertIn("token=<redacted>", message)
        self.assertNotIn(str(REPO_ROOT), message)
        self.assertNotIn("supersecret123", message)

    def test_timeout_failure_is_actionable_and_redacted(self) -> None:
        timeout = subprocess.TimeoutExpired(
            ["sh", "scripts/run_skill_mode_demo.sh"],
            timeout=7,
            output=f"working in {REPO_ROOT}\n",
            stderr=b"still waiting\n",
        )
        with patch.object(clean_clone.subprocess, "run", side_effect=timeout):
            with self.assertRaises(clean_clone.CleanCloneAdoptionError) as context:
                clean_clone.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=7,
                )
        message = str(context.exception)
        self.assertIn("timed out after 7s", message)
        self.assertIn("normal terminal", message)
        self.assertIn("<local-path>", message)
        self.assertNotIn(str(REPO_ROOT), message)

    def test_skill_demo_step_failure_is_actionable(self) -> None:
        completed = clean_clone.subprocess.CompletedProcess(
            ["sh", "scripts/run_skill_mode_demo.sh"],
            42,
            stdout="Running deterministic Skill Mode CLI flow ...\n",
            stderr=(
                "Study Anything Skill Mode demo step failed: Running deterministic Skill Mode CLI flow\n"
                "Command: .venv/bin/python scripts/verify_skill_cli_flow.py\n"
                "API base: http://127.0.0.1:8012\n"
                "Try these recovery paths:\n"
                "  1. Collect a redacted report: python3 scripts/diagnose_adoption.py\n"
            ),
        )
        with patch.object(clean_clone.subprocess, "run", return_value=completed):
            with self.assertRaises(clean_clone.CleanCloneAdoptionError) as context:
                clean_clone.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=Path(REPO_ROOT),
                    timeout_seconds=5,
                )
        message = str(context.exception)
        self.assertIn("bounded Skill Mode demo verification step failed", message)
        self.assertIn("not a silent deployment failure", message)
        self.assertIn("Running deterministic Skill Mode CLI flow", message)
        self.assertIn("diagnose_adoption.py", message)

    def test_success_payload_is_redacted_for_support_sharing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stdout = StringIO()
            argv = [
                "verify_clean_clone_adoption.py",
                "--repo",
                "https://user:secret@example.test/repo.git?token=supersecret123",
                "--work-dir",
                tmp,
                "--keep",
                "--with-promptfoo",
            ]

            with (
                patch.object(clean_clone.sys, "argv", argv),
                patch.object(clean_clone, "select_api_port", return_value=8123),
                patch.object(clean_clone, "find_python_311", return_value="python3"),
                patch.object(clean_clone, "clone_repo"),
                patch.object(clean_clone, "run"),
                patch.object(
                    clean_clone,
                    "run_skill_mode_demo",
                    return_value=(
                        f"ok path={'/Users/' + 'james/private/source.txt'} "
                        f"tmp={'/private/' + 'tmp/study-anything'} token=supersecret123"
                    ),
                ),
                patch.object(
                    clean_clone,
                    "run_promptfoo",
                    return_value={
                        "status": "ok",
                        "artifact": "/private/" + "tmp/promptfoo/result.json",
                        "token": "supersecret123",
                    },
                ),
                redirect_stdout(stdout),
            ):
                clean_clone.main()

        payload = json.loads(stdout.getvalue())
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["clone_dir_retained"])
        self.assertIn("<redacted>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertIn("<temp-path>", serialized)
        self.assertNotIn("user:secret", serialized)
        self.assertNotIn("supersecret123", serialized)
        self.assertNotIn("/Users/" + "james", serialized)
        self.assertNotIn("/private/" + "tmp", serialized)


if __name__ == "__main__":
    unittest.main()
