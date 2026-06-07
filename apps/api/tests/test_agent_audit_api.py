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
from study_anything.core.workspace import LocalWorkspaceStore


class _AuditAgentHandler(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict[str, Any]]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        task = json.loads(self.rfile.read(length))
        self.__class__.seen.append(task)
        source = task.get("source") or {}
        task_type = task.get("task_type")
        payload: dict[str, Any] = {
            "status": "ok",
            "content": "Focus on source evidence",
            "citations": [],
            "confidence": 0.91,
            "metadata": {"audit_test": True},
        }
        if source.get("reference"):
            payload["citations"].append(
                {
                    "reference": source.get("reference"),
                    "excerpt_hash": source.get("excerpt_hash"),
                }
            )
        if task_type == "answer.grade":
            payload["score"] = 0.83
            payload["feedback"] = "Grounded answer."
        elif task_type == "insight.synthesize":
            payload["content"] = "Reusable source-bound insight."
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class AgentAuditApiTests(unittest.TestCase):
    def _client(self, root: Path) -> tuple[TestClient, ExitStack, AgentRegistry]:
        stack = ExitStack()
        registry = AgentRegistry(root / "agents.json")
        workflow = LearningWorkflow(AgentRouter(registry))
        stack.enter_context(patch.object(api_main, "store", InMemorySessionStore()))
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "workflow", workflow))
        stack.enter_context(
            patch.object(api_main, "workspace_store", LocalWorkspaceStore(root / "workspaces.json"))
        )
        return TestClient(api_main.create_app()), stack, registry

    def test_agent_audit_proves_demo_agent_coverage_without_private_content(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack, _registry = self._client(Path(tmpdir))
            with stack, client:
                session = client.post("/v1/sessions", json={"user_id": "audit-demo"}).json()
                session_id = session["session_id"]
                client.post(
                    f"/v1/sessions/{session_id}/reading",
                    json={
                        "source_type": "local_text",
                        "reference": "demo://agent-audit",
                        "title": "Private title",
                        "text": "Private source prose for audit.",
                    },
                )
                running = client.post(f"/v1/sessions/{session_id}/run").json()
                quiz_id = running["quiz_items"][0]["item_id"]
                client.post(
                    f"/v1/sessions/{session_id}/answers",
                    json={"answers": {quiz_id: "Private answer text."}},
                )
                response = client.get(f"/v1/sessions/{session_id}/agent-audit")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["schema_version"], "agent-audit-v1")
        self.assertEqual(body["status"], "verified")
        self.assertTrue(body["used_study_anything_agent"])
        self.assertTrue(body["used_fake_agent"])
        self.assertFalse(body["used_external_agent"])
        self.assertFalse(body["quality_eval"]["included"])
        self.assertEqual(
            body["observed_tasks"],
            ["answer.grade", "insight.synthesize", "quiz.generate"],
        )
        self.assertEqual(body["missing_tasks"], [])
        self.assertTrue(body["source_bound"]["source_reference_present"])
        self.assertNotIn("Private", response.text)
        self.assertFalse(body["privacy"]["agent_endpoint_returned"])

    def test_agent_audit_distinguishes_user_owned_http_agent(self) -> None:
        with TemporaryDirectory() as tmpdir, self._server() as endpoint:
            client, stack, _registry = self._client(Path(tmpdir))
            with stack, client:
                provider = client.post(
                    "/v1/agents/providers",
                    json={
                        "kind": "http_agent",
                        "label": "Audit HTTP Agent",
                        "endpoint": endpoint,
                        "capabilities": [
                            "quiz.generate",
                            "answer.grade",
                            "insight.synthesize",
                        ],
                    },
                ).json()
                for capability in ["quiz.generate", "answer.grade", "insight.synthesize"]:
                    client.post(
                        "/v1/agents/defaults",
                        json={
                            "user_id": "audit-http",
                            "capability": capability,
                            "provider_id": provider["provider_id"],
                        },
                    )
                session = client.post(
                    "/v1/sessions",
                    json={"user_id": "audit-http", "use_demo_agent": False},
                ).json()
                session_id = session["session_id"]
                client.post(
                    f"/v1/sessions/{session_id}/reading",
                    json={
                        "source_type": "local_text",
                        "reference": "demo://agent-audit-http",
                        "title": "External agent audit",
                        "text": "The user-owned HTTP agent should be visible in audit.",
                    },
                )
                running = client.post(f"/v1/sessions/{session_id}/run").json()
                quiz_id = running["quiz_items"][0]["item_id"]
                client.post(
                    f"/v1/sessions/{session_id}/answers",
                    json={"answers": {quiz_id: "The HTTP agent handled the learning tasks."}},
                )
                response = client.get(f"/v1/sessions/{session_id}/agent-audit")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "verified")
        self.assertTrue(body["used_external_agent"])
        self.assertFalse(body["used_fake_agent"])
        self.assertEqual(body["provider_ids"], [provider["provider_id"]])
        self.assertEqual(body["providers"][0]["kind"], "http_agent")
        self.assertEqual(len(body["evidence"]), 3)
        self.assertNotIn(endpoint, response.text)

    def test_deprecated_agent_eval_alias_is_marked_deprecated(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack, _registry = self._client(Path(tmpdir))
            with stack, client:
                session = client.post("/v1/sessions", json={"user_id": "audit-alias"}).json()
                response = client.get(f"/v1/sessions/{session['session_id']}/agent-eval")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["schema_version"], "agent-eval-v1")
        self.assertTrue(body["deprecated"])
        self.assertEqual(body["replacement"], "/v1/sessions/{session_id}/agent-audit")

    def test_agent_audit_returns_404_for_missing_session(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack, _registry = self._client(Path(tmpdir))
            with stack, client:
                response = client.get("/v1/sessions/missing/agent-audit")

        self.assertEqual(response.status_code, 404)

    def _server(self):
        class ServerContext:
            def __enter__(self_inner) -> str:
                _AuditAgentHandler.seen = []
                self_inner.server = HTTPServer(("127.0.0.1", 0), _AuditAgentHandler)
                self_inner.thread = threading.Thread(
                    target=self_inner.server.serve_forever,
                    daemon=True,
                )
                self_inner.thread.start()
                host, port = self_inner.server.server_address
                return f"http://{host}:{port}/invoke"

            def __exit__(self_inner, exc_type: object, exc: object, tb: object) -> None:
                self_inner.server.shutdown()
                self_inner.server.server_close()
                self_inner.thread.join(timeout=2)

        return ServerContext()


if __name__ == "__main__":
    unittest.main()

