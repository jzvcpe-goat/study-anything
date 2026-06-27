from __future__ import annotations

import io
import importlib.util
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


SPEC = importlib.util.spec_from_file_location(
    "verify_external_adoption",
    REPO_ROOT / "scripts" / "verify_external_adoption.py",
)
assert SPEC is not None and SPEC.loader is not None
external_adoption = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(external_adoption)


class ExternalAdoptionVerifierTests(unittest.TestCase):
    def test_explicit_api_port_skips_port_probe(self) -> None:
        with patch.object(external_adoption, "free_port", side_effect=AssertionError("probe")):
            self.assertEqual(external_adoption.select_api_port(8124), 8124)

    def test_invalid_api_port_is_actionable(self) -> None:
        with self.assertRaisesRegex(external_adoption.AdoptionProofError, "--api-port"):
            external_adoption.select_api_port(70000)

    def test_port_probe_failure_is_actionable(self) -> None:
        with patch.object(
            external_adoption,
            "free_port",
            side_effect=OSError(1, "Operation not permitted"),
        ):
            with self.assertRaisesRegex(external_adoption.AdoptionProofError, "normal terminal"):
                external_adoption.select_api_port(None)

    def test_permission_denied_port_probe_failure_is_actionable(self) -> None:
        with patch.object(
            external_adoption,
            "free_port",
            side_effect=OSError(13, "Permission denied"),
        ):
            with self.assertRaisesRegex(external_adoption.AdoptionProofError, "normal terminal"):
                external_adoption.select_api_port(None)

    def test_allow_localhost_block_report_emits_blocked_proof(self) -> None:
        stdout = io.StringIO()
        argv = [
            "verify_external_adoption.py",
            "--current-worktree",
            "--allow-localhost-block-report",
        ]
        with patch.object(sys, "argv", argv):
            with patch.object(
                external_adoption,
                "validate_adoption_pack",
                return_value={
                    "schema_version": "study-anything-platform-adoption-pack-v1",
                    "version": "v0.3.29-alpha",
                },
            ):
                with patch.object(external_adoption, "prepare_workspace", return_value=REPO_ROOT):
                    with patch.object(
                        external_adoption,
                        "free_port",
                        side_effect=OSError(1, "Operation not permitted"),
                    ):
                        with patch("sys.stdout", stdout):
                            external_adoption.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["schema_version"], "adoption-proof-v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "localhost_socket_blocked")
        self.assertEqual(payload["runtime"]["status"], "not_started")
        self.assertIn("localhost sockets", payload["runtime"]["reason"])
        self.assertIn("--api-port PORT", payload["recovery"]["notes"][1])
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", payload["recovery"]["copyable_commands"][0])
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", payload["recovery"]["copyable_commands"][1])
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", payload["recovery"]["copyable_commands"][2])
        self.assertIn("diagnose_adoption.py", payload["recovery"]["copyable_commands"][5])
        self.assertIn("Contract-only commands", payload["recovery"]["notes"][2])
        self.assertTrue(payload["privacy"]["redacted"])
        self.assertEqual(payload["source"]["repo"], "<current-worktree>")
        self.assertNotIn("/Users/", stdout.getvalue())

    def test_allow_localhost_block_report_handles_permission_denied(self) -> None:
        stdout = io.StringIO()
        argv = [
            "verify_external_adoption.py",
            "--current-worktree",
            "--allow-localhost-block-report",
        ]
        with patch.object(sys, "argv", argv):
            with patch.object(
                external_adoption,
                "validate_adoption_pack",
                return_value={
                    "schema_version": "study-anything-platform-adoption-pack-v1",
                    "version": "v0.3.29-alpha",
                },
            ):
                with patch.object(external_adoption, "prepare_workspace", return_value=REPO_ROOT):
                    with patch.object(
                        external_adoption,
                        "free_port",
                        side_effect=OSError(13, "Permission denied"),
                    ):
                        with patch("sys.stdout", stdout):
                            external_adoption.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "localhost_socket_blocked")
        self.assertIn("--contract-only", " ".join(payload["recovery"]["copyable_commands"]))
        self.assertTrue(payload["privacy"]["redacted"])
        self.assertEqual(payload["source"]["repo"], "<current-worktree>")
        self.assertNotIn("/Users/", stdout.getvalue())

    def test_redaction_rejects_local_absolute_paths(self) -> None:
        with self.assertRaisesRegex(external_adoption.AdoptionProofError, "local absolute path"):
            external_adoption.assert_redacted({"source": {"repo": str(REPO_ROOT)}})

    def test_cli_failure_formatter_redacts_private_context(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        local_home = "/Users/" + "james/private/source.txt"
        message = external_adoption.format_cli_failure(
            RuntimeError(
                f"failed with Authorization: Bearer {secret} "
                f"at http://user:pass@example.test/v1?api_key={secret} "
                f"from {local_home}"
            )
        )

        self.assertIn("verify_external_adoption failed:", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertIn("http://<redacted>@example.test/v1?api_key=<redacted>", message)
        self.assertIn("python3 scripts/diagnose_adoption.py", message)
        self.assertIn("--allow-localhost-block-report", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("/Users/" + "james", message)

    def test_failure_report_localhost_block_points_to_contract_only(self) -> None:
        report = external_adoption.failure_report(
            external_adoption.AdoptionProofError(
                "Cannot reserve a localhost port for external adoption Skill Mode API: "
                "[Errno 1] Operation not permitted."
            )
        )

        self.assertEqual(report["classification"], "localhost_socket_blocked")
        steps = " ".join(report["next_steps"])
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", steps)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", steps)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", steps)

    def test_failure_report_classifies_pack_invalid(self) -> None:
        report = external_adoption.failure_report(
            external_adoption.AdoptionProofError(
                "Adoption pack archive missing required files: ['manifest.json']"
            )
        )

        self.assertEqual(report["schema_version"], "external-adoption-failure-v1")
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"], "adoption_pack_invalid")
        self.assertIn("generate_platform_adoption_pack.py", " ".join(report["next_steps"]))
        self.assertTrue(report["privacy"]["redacted"])

    def test_failure_report_redacts_private_context(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        local_home = "/Users/" + "example/private/source.txt"
        report = external_adoption.failure_report(
            RuntimeError(
                f"failed with Authorization: Bearer {secret} "
                f"at http://user:pass@example.test/v1?api_key={secret} "
                f"from {local_home}"
            )
        )
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertIn("http://<redacted>@example.test/v1?api_key=<redacted>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(local_home, serialized)

    def test_cli_failure_path_emits_machine_json_and_human_stderr(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "verify_external_adoption.py"),
                "--api-port",
                "70000",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "external-adoption-failure-v1")
        self.assertEqual(payload["classification"], "invalid_cli_input")
        self.assertIn("verify_external_adoption failed:", completed.stderr)
        self.assertIn("classification: invalid_cli_input", completed.stderr)

    def test_redact_local_paths_uses_shared_secret_redaction(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        message = external_adoption.redact_local_paths(
            f"token={secret} path={'/private/' + 'tmp/study-anything/log'}"
        )

        self.assertIn("token=<redacted>", message)
        self.assertNotIn(secret, message)
        self.assertNotIn("/private/" + "tmp", message)

    def test_source_descriptor_redacts_local_repos(self) -> None:
        args = external_adoption.argparse.Namespace(
            current_worktree=False,
            copy_worktree=False,
            repo=str(REPO_ROOT),
            ref=None,
        )
        self.assertEqual(external_adoption.source_descriptor(args)["repo"], "<local-repo>")

    def test_local_bind_failure_is_actionable(self) -> None:
        completed = external_adoption.subprocess.CompletedProcess(
            ["sh", "scripts/launch_skill_mode.sh"],
            1,
            stdout="Starting Study Anything Skill API at http://127.0.0.1:18080 ...",
            stderr=(
                "ERROR: [Errno 1] error while attempting to bind on address "
                "('127.0.0.1', 18080): operation not permitted"
            ),
        )
        with patch.object(external_adoption.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(
                external_adoption.AdoptionProofError,
                "normal terminal",
            ):
                external_adoption.run(
                    ["sh", "scripts/launch_skill_mode.sh"],
                    cwd=REPO_ROOT,
                    timeout_seconds=5,
                )

    def test_local_bind_permission_denied_failure_is_actionable(self) -> None:
        completed = external_adoption.subprocess.CompletedProcess(
            ["sh", "scripts/launch_skill_mode.sh"],
            1,
            stdout="Starting Study Anything Skill API at http://127.0.0.1:18080 ...",
            stderr=(
                "ERROR: [Errno 13] error while attempting to bind on address "
                "('127.0.0.1', 18080): permission denied"
            ),
        )
        with patch.object(external_adoption.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(
                external_adoption.AdoptionProofError,
                "normal terminal",
            ):
                external_adoption.run(
                    ["sh", "scripts/launch_skill_mode.sh"],
                    cwd=REPO_ROOT,
                    timeout_seconds=5,
                )

    def test_launch_script_bind_preflight_message_is_actionable(self) -> None:
        completed = external_adoption.subprocess.CompletedProcess(
            ["sh", "scripts/launch_skill_mode.sh"],
            3,
            stdout="",
            stderr=(
                "Local Skill Mode API cannot listen on 127.0.0.1:18080 from this runner.\n"
                "This usually means the current agent sandbox blocks localhost listening sockets.\n"
            ),
        )
        with patch.object(external_adoption.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(
                external_adoption.AdoptionProofError,
                "could not bind to localhost",
            ):
                external_adoption.run(
                    ["sh", "scripts/launch_skill_mode.sh"],
                    cwd=REPO_ROOT,
                    timeout_seconds=5,
                )

    def test_dependency_download_failure_is_actionable(self) -> None:
        completed = external_adoption.subprocess.CompletedProcess(
            ["sh", "scripts/launch_skill_mode.sh"],
            1,
            stdout="Installing backend dependencies into .venv ...",
            stderr=(
                "pip subprocess to install build dependencies did not run successfully\n"
                "WARNING: Retrying after connection broken by "
                "'NewConnectionError': Failed to establish a new connection\n"
                "Failed to establish a new connection: [Errno 8] nodename nor servname provided\n"
                "ERROR: Could not find a version that satisfies the requirement setuptools>=40.8.0\n"
                "ERROR: No matching distribution found for setuptools>=40.8.0\n"
            ),
        )
        with patch.object(external_adoption.subprocess, "run", return_value=completed):
            with self.assertRaises(external_adoption.AdoptionProofError) as context:
                external_adoption.run(
                    ["sh", "scripts/launch_skill_mode.sh"],
                    cwd=REPO_ROOT,
                    timeout_seconds=5,
                )
        message = str(context.exception)
        self.assertIn("Python dependency installation failed", message)
        self.assertIn("PyPI", message)
        self.assertIn("PIP_INDEX_URL", message)
        self.assertIn("./scripts/launch_skill_mode.sh", message)
        self.assertIn("Command: sh scripts/launch_skill_mode.sh", message)
        self.assertIn("Relevant output", message)
        self.assertNotIn("WARNING: Retrying", message)

    def test_skill_demo_step_failure_is_actionable(self) -> None:
        completed = external_adoption.subprocess.CompletedProcess(
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
        with patch.object(external_adoption.subprocess, "run", return_value=completed):
            with self.assertRaises(external_adoption.AdoptionProofError) as context:
                external_adoption.run(
                    ["sh", "scripts/run_skill_mode_demo.sh"],
                    cwd=REPO_ROOT,
                    timeout_seconds=5,
                )
        message = str(context.exception)
        self.assertIn("bounded Skill Mode verification step failed", message)
        self.assertIn("not a silent deployment failure", message)
        self.assertIn("Running deterministic Skill Mode CLI flow", message)
        self.assertIn("diagnose_adoption.py", message)


if __name__ == "__main__":
    unittest.main()
