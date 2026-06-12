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


class ExternalAgentEvalRunnerTests(unittest.TestCase):
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

    def test_deepeval_runner_invokes_quality_adapter(self) -> None:
        _QualityEvalHandler.seen = []
        server = HTTPServer(("127.0.0.1", 0), _QualityEvalHandler)
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
        server = HTTPServer(("127.0.0.1", 0), _RetrievalEvalHandler)
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


if __name__ == "__main__":
    unittest.main()
