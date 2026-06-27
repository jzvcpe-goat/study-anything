from __future__ import annotations

import errno
import importlib.util
import json
import os
import subprocess
import unittest
from unittest.mock import patch

from _path import ROOT as API_ROOT


REPO_ROOT = API_ROOT.parents[1]


SPEC = importlib.util.spec_from_file_location(
    "verify_openai_compatible_gateway",
    REPO_ROOT / "scripts" / "verify_openai_compatible_gateway.py",
)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class FakeSocket:
    def __init__(self, error: OSError | None = None) -> None:
        self.error = error

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def setsockopt(self, *_args: object) -> None:
        return None

    def bind(self, _address: tuple[str, int]) -> None:
        if self.error is not None:
            raise self.error

    def getsockname(self) -> tuple[str, int]:
        return ("127.0.0.1", 18444)


class OpenAICompatibleGatewayVerifierTests(unittest.TestCase):
    def test_free_port_permission_failure_is_actionable(self) -> None:
        with patch.object(
            verifier.socket,
            "socket",
            return_value=FakeSocket(OSError(errno.EPERM, "Operation not permitted")),
        ):
            with self.assertRaisesRegex(verifier.GatewayVerificationError, "normal terminal"):
                verifier.find_free_port("127.0.0.1")

    def test_free_port_permission_denied_failure_is_actionable(self) -> None:
        with patch.object(
            verifier.socket,
            "socket",
            return_value=FakeSocket(OSError(errno.EACCES, "Permission denied")),
        ):
            with self.assertRaisesRegex(verifier.GatewayVerificationError, "normal terminal"):
                verifier.find_free_port("127.0.0.1")

    def test_bind_preflight_permission_failure_is_actionable(self) -> None:
        with patch.object(
            verifier.socket,
            "socket",
            return_value=FakeSocket(OSError(errno.EPERM, "Operation not permitted")),
        ):
            with self.assertRaisesRegex(verifier.GatewayVerificationError, "localhost"):
                verifier.check_bind_preflight("127.0.0.1", 8787)

    def test_bind_preflight_port_in_use_is_actionable(self) -> None:
        with patch.object(
            verifier.socket,
            "socket",
            return_value=FakeSocket(OSError(errno.EADDRINUSE, "Address already in use")),
        ):
            with self.assertRaisesRegex(verifier.GatewayVerificationError, "--port"):
                verifier.check_bind_preflight("127.0.0.1", 8787)

    def test_reuse_running_gateway_defaults_to_documented_port(self) -> None:
        with patch.object(verifier, "find_free_port") as find_free_port:
            port = verifier.resolve_gateway_port(
                "127.0.0.1",
                None,
                reuse_running_gateway=True,
            )

        self.assertEqual(port, 8787)
        find_free_port.assert_not_called()

    def test_verifier_owned_gateway_uses_ephemeral_port_by_default(self) -> None:
        with patch.object(verifier, "find_free_port", return_value=18444) as find_free_port:
            port = verifier.resolve_gateway_port(
                "127.0.0.1",
                None,
                reuse_running_gateway=False,
            )

        self.assertEqual(port, 18444)
        find_free_port.assert_called_once_with("127.0.0.1")

    def test_explicit_port_wins_for_reuse_mode(self) -> None:
        with patch.object(verifier, "find_free_port") as find_free_port:
            port = verifier.resolve_gateway_port(
                "127.0.0.1",
                8788,
                reuse_running_gateway=True,
            )

        self.assertEqual(port, 8788)
        find_free_port.assert_not_called()

    def test_failure_report_classifies_localhost_socket_block(self) -> None:
        report = verifier.failure_report(
            verifier.GatewayVerificationError(
                "Localhost gateway socket cannot listen on 127.0.0.1:auto from this runner."
            )
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"], "localhost_socket_blocked")
        next_steps = " ".join(report["next_steps"])
        self.assertIn("normal terminal", next_steps)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", next_steps)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", next_steps)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", next_steps)
        self.assertIn("do not replace the runtime gateway smoke", next_steps)
        self.assertFalse(report["privacy"]["real_model_keys_included"])

    def test_human_failure_report_names_classification_and_next_steps(self) -> None:
        report = verifier.failure_report(
            verifier.GatewayVerificationError(
                "Localhost gateway socket cannot listen on 127.0.0.1:auto from this runner."
            )
        )

        message = verifier.format_failure_for_human(report)

        self.assertIn("verify_openai_compatible_gateway failed:", message)
        self.assertIn("classification: localhost_socket_blocked", message)
        self.assertIn("Diagnostic:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("normal terminal", message)
        self.assertIn("verify_openai_compatible_gateway.py --contract-only", message)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", message)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", message)

    def test_wrapped_gateway_health_localhost_limit_stays_actionable(self) -> None:
        report = verifier.failure_report(
            verifier.GatewayVerificationError(
                "Gateway did not become healthy: Localhost gateway health cannot be reached "
                "from this runner. Run this verifier from a normal terminal or host shell "
                "that permits localhost sockets. URL: http://127.0.0.1:8787/health"
            )
        )

        self.assertEqual(report["classification"], "localhost_socket_blocked")
        next_steps = " ".join(report["next_steps"])
        self.assertIn("normal terminal", next_steps)
        self.assertIn("verify_agent_gateway_hardening.py --contract-only", next_steps)
        self.assertIn("verify_external_agent_adapter_hardening.py --contract-only", next_steps)
        self.assertNotIn("Start the gateway directly", next_steps)

    def test_failure_report_classifies_port_in_use(self) -> None:
        report = verifier.failure_report(
            verifier.GatewayVerificationError(
                "Gateway port is already in use: 127.0.0.1:8787."
            )
        )

        self.assertEqual(report["classification"], "gateway_port_in_use")
        self.assertIn("--port 8788", " ".join(report["next_steps"]))

    def test_failure_report_redacts_paths_and_secrets(self) -> None:
        local_home = "/Users/" + "example"
        api_query_name = "api_" + "key"
        report = verifier.failure_report(
            verifier.GatewayVerificationError(
                f"Cannot reach {local_home}/project?{api_query_name}=supersecret123 token=othersecret456"
            )
        )
        serialized = json.dumps(report)

        self.assertEqual(report["classification"], "api_or_gateway_unreachable")
        self.assertIn("<local-path>", serialized)
        self.assertIn("api_key=<redacted>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn(local_home, serialized)
        self.assertNotIn("supersecret123", serialized)
        self.assertNotIn("othersecret456", serialized)

    def test_inprocess_contract_restores_gateway_mode(self) -> None:
        old_mode = os.environ.get("AGENT_GATEWAY_MODE")
        os.environ["AGENT_GATEWAY_MODE"] = "upstream"
        try:
            tasks = verifier.verify_inprocess_gateway_contract()
            self.assertEqual(os.environ.get("AGENT_GATEWAY_MODE"), "upstream")
        finally:
            if old_mode is None:
                os.environ.pop("AGENT_GATEWAY_MODE", None)
            else:
                os.environ["AGENT_GATEWAY_MODE"] = old_mode

        self.assertIn("teach.overview", tasks)
        self.assertIn("answer.grade", tasks)

    def test_contract_only_cli_outputs_ok_without_socket(self) -> None:
        completed = subprocess.run(
            [
                verifier.sys.executable,
                str(REPO_ROOT / "scripts" / "verify_openai_compatible_gateway.py"),
                "--contract-only",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["runtime"], "in_process_contract")
        self.assertFalse(payload["socket_required"])
        self.assertIn("teach.overview", payload["direct_tasks"])
        self.assertNotIn(verifier.PRIVATE_SOURCE_TEXT, serialized)
        self.assertNotIn(verifier.PRIVATE_ANSWER, serialized)


if __name__ == "__main__":
    unittest.main()
