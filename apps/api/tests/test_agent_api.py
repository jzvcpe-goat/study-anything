from __future__ import annotations

import json
import threading
import unittest
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import LearningWorkflow


class _InvalidAgentHandler(BaseHTTPRequestHandler):
    response: ClassVar[dict[str, Any] | str] = {"status": "maybe", "content": "bad"}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = (
            self.response
            if isinstance(self.response, str)
            else json.dumps(self.response).encode("utf-8").decode("utf-8")
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


class AgentApiTests(unittest.TestCase):
    def _client(self, root: Path) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        registry = AgentRegistry(root / "agents.json")
        stack.enter_context(patch.object(api_main, "store", InMemorySessionStore()))
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "agent_router", AgentRouter(registry)))
        stack.enter_context(patch.object(api_main, "workflow", LearningWorkflow(AgentRouter(registry))))
        return TestClient(api_main.create_app()), stack

    def test_agent_provider_status_redacts_endpoint_query_secrets(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                created = client.post(
                    "/v1/agents/providers",
                    json={
                        "kind": "http_agent",
                        "label": "Safe HTTP Agent",
                        "endpoint": "http://127.0.0.1:8787/invoke?mode=local",
                        "capabilities": ["quiz.generate"],
                    },
                )
                status = client.get("/v1/agents/status")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(status.status_code, 200)
        self.assertIn("http://127.0.0.1:8787/invoke?mode=local", status.text)
        self.assertNotIn("Authorization", status.text)

    def test_agent_provider_rejects_inline_endpoint_secret(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                response = client.post(
                    "/v1/agents/providers",
                    json={
                        "kind": "http_agent",
                        "label": "Unsafe HTTP Agent",
                        "endpoint": "http://127.0.0.1:8787/invoke?api_key=secret",
                        "capabilities": ["quiz.generate"],
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("api_key=secret", response.text)
        self.assertIn("endpoint must not contain", response.text)

    def test_agent_test_returns_diagnostic_without_raw_payload(self) -> None:
        with TemporaryDirectory() as tmpdir, self._server({"status": "maybe"}) as endpoint:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                provider = client.post(
                    "/v1/agents/providers",
                    json={
                        "kind": "http_agent",
                        "label": "Invalid HTTP Agent",
                        "endpoint": endpoint,
                        "capabilities": ["source.verify"],
                    },
                ).json()
                response = client.post("/v1/agents/test", json={"provider_id": provider["provider_id"]})

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "unhealthy")
        self.assertEqual(body["diagnostic_code"], "invalid_status")
        self.assertFalse(body["privacy"]["raw_task_payload_returned"])
        self.assertNotIn("health_check", response.text)

    def test_agent_invoke_invalid_schema_returns_422(self) -> None:
        with TemporaryDirectory() as tmpdir, self._server({"status": "ok", "content": ""}) as endpoint:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                provider = client.post(
                    "/v1/agents/providers",
                    json={
                        "kind": "http_agent",
                        "label": "Schema Bad HTTP Agent",
                        "endpoint": endpoint,
                        "capabilities": ["quiz.generate"],
                    },
                ).json()
                response = client.post(
                    f"/v1/agents/{provider['provider_id']}/invoke",
                    json={"task_type": "quiz.generate", "session_id": "manual"},
                )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(endpoint, response.text)

    def _server(self, response: dict[str, Any] | str):
        class ServerContext:
            def __enter__(self_inner) -> str:
                _InvalidAgentHandler.response = response
                self_inner.server = HTTPServer(("127.0.0.1", 0), _InvalidAgentHandler)
                self_inner.thread = threading.Thread(
                    target=self_inner.server.serve_forever,
                    daemon=True,
                )
                self_inner.thread.start()
                host, port = self_inner.server.server_address
                return f"http://{host}:{port}"

            def __exit__(self_inner, exc_type: object, exc: object, tb: object) -> None:
                self_inner.server.shutdown()
                self_inner.server.server_close()
                self_inner.thread.join(timeout=2)

        return ServerContext()


if __name__ == "__main__":
    unittest.main()
