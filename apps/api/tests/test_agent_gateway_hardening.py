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
SCRIPT = REPO_ROOT / "scripts" / "verify_agent_gateway_hardening.py"
SPEC = importlib.util.spec_from_file_location("verify_agent_gateway_hardening", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
gateway_hardening = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway_hardening)


class AgentGatewayHardeningTests(unittest.TestCase):
    def test_runtime_failure_payload_is_machine_readable(self) -> None:
        payload = gateway_hardening.runtime_failure_payload(
            classification="python_dependency_missing",
            diagnostic="missing module at /Users/example/project token=secretToken123456",
            details={"missing_module": "tomllib"},
        )

        self.assertEqual(payload["schema_version"], "agent-gateway-hardening-error-v1")
        self.assertEqual(payload["classification"], "python_dependency_missing")
        self.assertEqual(payload["details"]["missing_module"], "tomllib")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        serialized = json.dumps(payload, sort_keys=True)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("secretToken123456", serialized)

    def test_python_version_preflight_prints_json_before_api_imports(self) -> None:
        stderr = io.StringIO()

        with (
            patch.object(gateway_hardening.sys, "version_info", (3, 9, 6)),
            patch.object(gateway_hardening.sys, "version", "3.9.6 test"),
            redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as raised:
                gateway_hardening.ensure_supported_python()

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["details"]["python_version"], "3.9.6")

    def test_gateway_hardening_passes_or_reports_localhost_block(self) -> None:
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
        self.assertEqual(report["schema_version"], "agent-gateway-hardening-verification-v1")
        if report["status"] == "blocked":
            self.assertEqual(report["classification"], "localhost_socket_blocked")
            self.assertEqual(report["runtime"]["status"], "not_started")
            self.assertIn("localhost", report["runtime"]["diagnostic"])
            self.assertTrue(report["privacy"]["redacted"])
            return
        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["checks"]["privacy"]["secrets_returned"])
        self.assertFalse(report["checks"]["privacy"]["raw_task_payload_returned"])
        self.assertFalse(report["checks"]["privacy"]["agent_endpoint_secrets_returned"])

    def test_gateway_hardening_contract_only_needs_no_socket(self) -> None:
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
        self.assertEqual(report["schema_version"], "agent-gateway-hardening-verification-v1")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["runtime"], "in_process_contract")
        self.assertFalse(report["socket_required"])
        self.assertFalse(report["release_gate"]["replaces_runtime_gateway_check"])
        self.assertTrue(report["checks"]["contract_only"]["grade_score_present"])
        self.assertNotIn("Private gateway verifier source text", serialized)
        self.assertNotIn("Private gateway verifier answer", serialized)

    def test_localhost_block_report_is_machine_readable_when_allowed(self) -> None:
        stdout = io.StringIO()
        with patch.object(
            gateway_hardening,
            "build_pass_report",
            side_effect=gateway_hardening.GatewayHardeningError(
                "Agent gateway hardening could not allocate a local gateway on "
                "127.0.0.1:0: [Errno 1] Operation not permitted."
            ),
        ):
            with patch("sys.stdout", stdout):
                gateway_hardening.main(["--allow-localhost-block-report"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["schema_version"], "agent-gateway-hardening-verification-v1")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["classification"], "localhost_socket_blocked")
        self.assertEqual(payload["runtime"]["status"], "not_started")
        self.assertIn("local dry-run Agent gateway", payload["runtime"]["reason"])
        commands = " ".join(payload["recovery"]["copyable_commands"])
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", commands)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", commands)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", commands)
        self.assertIn("verify_external_adoption.py", commands)
        self.assertTrue(payload["privacy"]["redacted"])

    def test_localhost_block_report_is_strict_by_default(self) -> None:
        with patch.object(
            gateway_hardening,
            "build_pass_report",
            side_effect=gateway_hardening.GatewayHardeningError(
                "Agent gateway hardening could not allocate a local gateway on localhost."
            ),
        ):
            with self.assertRaises(gateway_hardening.GatewayHardeningError):
                gateway_hardening.main([])

    def test_cli_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = gateway_hardening.format_cli_failure(
            RuntimeError(
                "gateway hardening failed at /private/tmp/study-anything/gateway.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("verify_agent_gateway_hardening failed", message)
        self.assertIn("Next steps:", message)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", message)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", message)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", message)
        self.assertIn("verify_agent_gateway_hardening.py --allow-localhost-block-report", message)
        self.assertIn("verify_external_adoption.py", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("docs/kimi-agent-gateway.md", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)


if __name__ == "__main__":
    unittest.main()
