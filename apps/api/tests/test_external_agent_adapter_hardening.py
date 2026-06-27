from __future__ import annotations

import io
import importlib.util
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from _path import ROOT  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "verify_external_agent_adapter_hardening.py"
SPEC = importlib.util.spec_from_file_location("verify_external_agent_adapter_hardening", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
adapter_hardening = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter_hardening)


class ExternalAgentAdapterHardeningTests(unittest.TestCase):
    def test_runtime_failure_payload_is_machine_readable(self) -> None:
        payload = adapter_hardening.runtime_failure_payload(
            classification="python_dependency_missing",
            diagnostic="missing module at /Users/example/project token=secretToken123456",
            details={"missing_module": "tomllib"},
        )

        self.assertEqual(payload["schema_version"], "external-agent-adapter-hardening-error-v1")
        self.assertEqual(payload["classification"], "python_dependency_missing")
        self.assertEqual(payload["details"]["missing_module"], "tomllib")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        serialized = json.dumps(payload, sort_keys=True)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("secretToken123456", serialized)

    def test_runtime_failure_prints_json(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                adapter_hardening.runtime_failure(
                    "verify_external_agent_adapter_hardening requires Python 3.11 or newer.",
                    classification="python_version_unsupported",
                    details={"python_version": "3.9.6"},
                )

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["details"]["python_version"], "3.9.6")

    def test_external_agent_adapter_hardening_report_passes_or_reports_localhost_block(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--allow-localhost-block-report",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "external-agent-adapter-hardening-v1")
        self.assertEqual(report["version"], "v0.3.29-alpha")
        if report["status"] == "blocked":
            self.assertEqual(report["classification"], "localhost_socket_blocked")
            self.assertEqual(report["runtime"]["status"], "not_started")
            self.assertIn("localhost", report["runtime"]["diagnostic"])
            self.assertTrue(report["privacy"]["redacted"])
            return
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["external_agent_eval"]["used_external_agent"])
        self.assertFalse(report["external_agent_eval"]["used_fake_agent"])
        self.assertEqual(report["external_agent_eval"]["native_fast_gate_status"], "pass")
        self.assertTrue(report["privacy"]["secret_like_metadata_values_redacted"])
        cases = {case["case_id"] for case in report["bad_agent_cases"]}
        self.assertEqual(
            cases,
            {
                "malformed_json",
                "invalid_status",
                "missing_content",
                "invalid_score",
                "invalid_confidence",
                "timeout",
                "missing_citations",
                "missing_capability",
            },
        )
        serialized = json.dumps(report)
        self.assertNotIn("Private external Agent hardening source text", serialized)
        self.assertNotIn("Private external Agent hardening answer", serialized)
        self.assertNotIn("sk-proj-agentVerifierSecretToken000000", serialized)

    def test_external_agent_adapter_contract_only_needs_no_socket(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--contract-only",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
        self.assertEqual(report["schema_version"], "external-agent-adapter-hardening-v1")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["runtime"], "in_process_contract")
        self.assertFalse(report["socket_required"])
        self.assertFalse(report["release_gate"]["replaces_http_adapter_gate"])
        self.assertTrue(report["external_agent_eval"]["used_external_agent"])
        self.assertFalse(report["external_agent_eval"]["used_fake_agent"])
        self.assertEqual(report["bad_agent_cases"][0]["case_id"], "missing_capability")
        self.assertNotIn("Private external Agent hardening source text", serialized)
        self.assertNotIn("Private external Agent hardening answer", serialized)
        self.assertNotIn("sk-proj-agentVerifierSecretToken000000", serialized)

    def test_localhost_block_report_is_machine_readable_when_allowed(self) -> None:
        stdout = io.StringIO()
        with patch.object(
            adapter_hardening,
            "run_verification",
            side_effect=adapter_hardening.ExternalAgentAdapterHardeningError(
                "External Agent adapter hardening could not start its local mock HTTP Agent "
                "on 127.0.0.1:0: [Errno 1] Operation not permitted."
            ),
        ):
            with patch("sys.stdout", stdout):
                adapter_hardening.main(["--allow-localhost-block-report"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["schema_version"], "external-agent-adapter-hardening-v1")
        self.assertEqual(payload["version"], "v0.3.29-alpha")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "localhost_socket_blocked")
        self.assertEqual(payload["runtime"]["status"], "not_started")
        self.assertIn("local mock HTTP Agent", payload["runtime"]["reason"])
        commands = " ".join(payload["recovery"]["copyable_commands"])
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", commands)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", commands)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", commands)
        self.assertIn("verify_external_adoption.py", commands)
        self.assertTrue(payload["privacy"]["redacted"])

    def test_localhost_block_report_is_strict_by_default(self) -> None:
        with patch.object(
            adapter_hardening,
            "run_verification",
            side_effect=adapter_hardening.ExternalAgentAdapterHardeningError(
                "External Agent adapter hardening could not start on localhost."
            ),
        ):
            with self.assertRaises(adapter_hardening.ExternalAgentAdapterHardeningError):
                adapter_hardening.main([])

    def test_cli_failure_formatter_redacts_private_context(self) -> None:
        message = adapter_hardening.format_cli_failure(
            adapter_hardening.ExternalAgentAdapterHardeningError(
                "adapter failed for /Users/james/private/project with "
                "https://user:secret@localhost:8787/invoke?api_key=plainSecret123456 "
                "Authorization: Bearer bearerSecret123456 sk-proj-secretToken123456"
            )
        )

        self.assertIn("verify_external_agent_adapter_hardening failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn(".venv/bin/python", message)
        self.assertIn("<local-path>", message)
        self.assertIn("https://<redacted>@localhost", message)
        self.assertIn("api_key=<redacted>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertIn("sk-<redacted>", message)
        self.assertNotIn("/Users/james", message)
        self.assertNotIn("plainSecret123456", message)
        self.assertNotIn("bearerSecret123456", message)
        self.assertNotIn("sk-proj-secretToken123456", message)

    def test_cli_failure_formatter_points_localhost_block_to_report_mode(self) -> None:
        message = adapter_hardening.format_cli_failure(
            adapter_hardening.ExternalAgentAdapterHardeningError(
                "External Agent adapter hardening could not start its local mock HTTP Agent "
                "on 127.0.0.1:0: [Errno 1] Operation not permitted."
            )
        )

        self.assertIn("--allow-localhost-block-report", message)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", message)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", message)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", message)
        self.assertIn("normal terminal or host shell", message)


if __name__ == "__main__":
    unittest.main()
