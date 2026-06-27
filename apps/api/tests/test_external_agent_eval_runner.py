from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, ClassVar

from _path import ROOT  # noqa: F401


class _QualityEvalHandler(BaseHTTPRequestHandler):
    seen: ClassVar[list[str]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self.__class__.seen.append(self.path)
        body = json.dumps(
            {
                "schema_version": "agent-quality-eval-v1",
                "session_id": "session-for-quality",
                "status": "pass",
                "quality_score": 0.91,
                "threshold": 0.72,
                "gates": [
                    {
                        "gate_id": "agent_invocation_proof",
                        "status": "pass",
                        "required": True,
                        "score": 1.0,
                    }
                ],
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _RetrievalEvalHandler(BaseHTTPRequestHandler):
    seen: ClassVar[list[str]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self.__class__.seen.append(self.path)
        body = json.dumps(
            {
                "schema_version": "retrieval-quality-eval-v1",
                "session_id": "session-for-retrieval",
                "query": "active recall",
                "status": "pass",
                "quality_score": 0.9,
                "threshold": 0.72,
                "gates": [
                    {
                        "gate_id": "retrieval_available",
                        "status": "pass",
                        "required": True,
                        "score": 1.0,
                    }
                ],
                "privacy": {
                    "raw_source_text_included": False,
                    "result_snippets_included": False,
                },
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _AgentEvalReportHandler(BaseHTTPRequestHandler):
    seen: ClassVar[list[str]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self.__class__.seen.append(self.path)
        body = json.dumps(
            {
                "schema_version": "agent-eval-report-v1",
                "policy_schema_version": "agent-eval-policy-v1",
                "session_id": "session-for-report",
                "status": "pass_with_optional_external_evals",
                "native_fast_gate": {
                    "status": "pass",
                    "blocking": True,
                    "failed_dimensions": [],
                },
                "privacy": {
                    "raw_source_text_returned": False,
                    "learner_answers_returned": False,
                    "secrets_returned": False,
                },
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _MalformedJsonHandler(BaseHTTPRequestHandler):
    seen: ClassVar[list[str]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self.__class__.seen.append(self.path)
        body = b"{not-json"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _HttpErrorWithSecretsHandler(BaseHTTPRequestHandler):
    seen: ClassVar[list[str]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self.__class__.seen.append(self.path)
        body = (
            b'{"detail":"upstream failed with Authorization: Bearer '
            b'sk-proj-abcdefghijklmnop123456 at '
            b'http://user:secret@example.test/v1?token=sk-proj-abcdefghijklmnop123456 '
            b'from /Users/james/private/source.txt"}'
        )
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ExternalAgentEvalRunnerTests(unittest.TestCase):
    def _server(self, handler: type[BaseHTTPRequestHandler]) -> HTTPServer:
        try:
            return HTTPServer(("127.0.0.1", 0), handler)
        except PermissionError as exc:
            if getattr(exc, "errno", None) == 1:
                raise unittest.SkipTest("localhost sockets are blocked in this runner") from exc
            raise

    def test_promptfoo_runner_invokes_pinned_external_tool(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            log_path = tmp / "npx-args.json"
            fake_npx = tmp / "npx"
            fake_npx.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                f"open({str(log_path)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
                "print('fake promptfoo ok')\n",
                encoding="utf-8",
            )
            fake_npx.chmod(fake_npx.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{tmp}{os.pathsep}{env.get('PATH', '')}"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "promptfoo",
                    "--api-base",
                    "http://127.0.0.1:8000",
                    "--session-id",
                    "session-for-promptfoo",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["status"], "ok")
            args = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertIn("promptfoo@0.121.15", args)
            self.assertIn("evals/promptfoo/agent-eval-artifact.yaml", args)
            self.assertIn("apiBase=http://127.0.0.1:8000", args)
            self.assertIn("sessionId=session-for-promptfoo", args)

    def test_promptfoo_failure_redacts_subprocess_output_and_command(self) -> None:
        secret = "sk-proj-abcdefghijklmnop123456"
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            fake_npx = tmp / "npx"
            fake_npx.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "print('stdout Authorization: Bearer sk-proj-abcdefghijklmnop123456 "
                "path=/Users/james/private/source.txt')\n"
                "print('stderr http://user:secret@example.test/v1?token="
                "sk-proj-abcdefghijklmnop123456', file=sys.stderr)\n"
                "sys.exit(2)\n",
                encoding="utf-8",
            )
            fake_npx.chmod(fake_npx.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env["PATH"] = f"{tmp}{os.pathsep}{env.get('PATH', '')}"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "promptfoo",
                    "--api-base",
                    f"http://user:secret@127.0.0.1:8000?api_key={secret}",
                    "--session-id",
                    "session-for-promptfoo",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 1)
        result = json.loads(completed.stdout)
        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tool"], "promptfoo")
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertIn("http://<redacted>@127.0.0.1:8000?api_key=<redacted>", serialized)
        self.assertIn("http://<redacted>@example.test/v1?token=<redacted>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("user:secret", serialized)
        self.assertNotIn("/Users/james", serialized)

    def test_deepeval_runner_invokes_quality_adapter(self) -> None:
        _QualityEvalHandler.seen = []
        server = self._server(_QualityEvalHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "deepeval",
                    "--api-base",
                    f"http://{host}:{port}",
                    "--session-id",
                    "session-for-quality",
                    "--required",
                    "--allow-native-quality-fallback",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertIn(
            "/v1/sessions/session-for-quality/agent-eval/quality",
            _QualityEvalHandler.seen,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertIn(result["tool"], {"deepeval", "deepeval-compatible-native"})
        self.assertEqual(result["session_id"], "session-for-quality")

    def test_retrieval_runner_invokes_retrieval_eval_adapter(self) -> None:
        _RetrievalEvalHandler.seen = []
        server = self._server(_RetrievalEvalHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "retrieval",
                    "--api-base",
                    f"http://{host}:{port}",
                    "--session-id",
                    "session-for-retrieval",
                    "--query",
                    "active recall",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(
            any(
                path.startswith("/v1/sessions/session-for-retrieval/retrieval/eval")
                for path in _RetrievalEvalHandler.seen
            )
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "retrieval")
        self.assertEqual(result["framework"], "ragas-compatible-native")
        self.assertEqual(result["session_id"], "session-for-retrieval")

    def test_report_runner_invokes_agent_eval_report(self) -> None:
        _AgentEvalReportHandler.seen = []
        server = self._server(_AgentEvalReportHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "report",
                    "--api-base",
                    f"http://{host}:{port}",
                    "--session-id",
                    "session-for-report",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertIn(
            "/v1/sessions/session-for-report/agent-eval/report",
            _AgentEvalReportHandler.seen,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["tool"], "report")
        self.assertEqual(result["framework"], "study-anything-native-maturity-report")
        self.assertEqual(result["session_id"], "session-for-report")

    def test_report_runner_failure_is_structured_and_actionable(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    Path(__file__).resolve().parents[3]
                    / "scripts"
                    / "run_external_agent_evals.py"
                ),
                "--tool",
                "report",
                "--api-base",
                "http://127.0.0.1:9",
                "--session-id",
                "missing-session",
                "--required",
                "--timeout-seconds",
                "2",
            ],
            cwd=Path(__file__).resolve().parents[3],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertNotIn("Traceback", completed.stderr + completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tool"], "report")
        self.assertIn("cannot reach Study Anything", result["reason"])
        self.assertIn("API_BASE=http://host:port", result["reason"])

    def test_retrieval_runner_malformed_json_is_tool_named(self) -> None:
        _MalformedJsonHandler.seen = []
        server = self._server(_MalformedJsonHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "retrieval",
                    "--api-base",
                    f"http://{host}:{port}",
                    "--session-id",
                    "session-with-bad-retrieval-json",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(completed.returncode, 1)
        self.assertNotIn("Traceback", completed.stderr + completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tool"], "retrieval")
        self.assertEqual(result["diagnostic_code"], "retrieval_parse_error")
        self.assertIn("Could not parse retrieval eval output", result["reason"])

    def test_report_runner_malformed_json_is_tool_named(self) -> None:
        _MalformedJsonHandler.seen = []
        server = self._server(_MalformedJsonHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "report",
                    "--api-base",
                    f"http://{host}:{port}",
                    "--session-id",
                    "session-with-bad-agent-eval-report-json",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(completed.returncode, 1)
        self.assertNotIn("Traceback", completed.stderr + completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tool"], "report")
        self.assertEqual(result["diagnostic_code"], "agent_eval_report_parse_error")
        self.assertIn("Could not parse Agent eval report output", result["reason"])

    def test_report_runner_http_error_is_redacted(self) -> None:
        _HttpErrorWithSecretsHandler.seen = []
        server = self._server(_HttpErrorWithSecretsHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[3]
                        / "scripts"
                        / "run_external_agent_evals.py"
                    ),
                    "--tool",
                    "report",
                    "--api-base",
                    f"http://{host}:{port}",
                    "--session-id",
                    "session-with-http-error",
                    "--required",
                    "--timeout-seconds",
                    "10",
                ],
                cwd=Path(__file__).resolve().parents[3],
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(completed.returncode, 1)
        result = json.loads(completed.stdout)
        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["diagnostic_code"], "agent_eval_report_request_failed")
        self.assertIn("API returned HTTP 500", result["reason"])
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertIn("http://<redacted>@example.test/v1?token=<redacted>", serialized)
        self.assertIn("<local-path>", serialized)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", serialized)
        self.assertNotIn("user:secret", serialized)
        self.assertNotIn("/Users/james", serialized)

    def test_create_session_failure_is_structured_json(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    Path(__file__).resolve().parents[3]
                    / "scripts"
                    / "run_external_agent_evals.py"
                ),
                "--tool",
                "report",
                "--api-base",
                "http://127.0.0.1:9",
                "--create-session",
                "--required",
                "--timeout-seconds",
                "2",
            ],
            cwd=Path(__file__).resolve().parents[3],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertNotIn("Traceback", completed.stderr + completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tool"], "report")
        self.assertIn("./scripts/launch_skill_mode.sh", result["recovery_hint"])
        self.assertIn("verify_agent_eval_flow failed", result["reason"])


if __name__ == "__main__":
    unittest.main()
