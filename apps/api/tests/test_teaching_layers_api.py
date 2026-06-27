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


class _TeachingAgentHandler(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict[str, Any]]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        task = json.loads(self.rfile.read(length))
        self.__class__.seen.append(task)
        task_type = task.get("task_type")
        source = task.get("source") or {}
        result: dict[str, Any] = {
            "status": "ok",
            "content": {"task_type": task_type, "handled_by": self.path},
            "citations": [
                {
                    "reference": source.get("reference"),
                    "excerpt_hash": source.get("excerpt_hash"),
                }
            ],
            "confidence": 0.9,
            "metadata": {"path": self.path},
        }
        body = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TeachingLayersApiTests(unittest.TestCase):
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

    def test_demo_agent_generates_overview_and_glossary_layers(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack, _registry = self._client(Path(tmpdir))
            with stack, client:
                session = client.post("/v1/sessions", json={"user_id": "layer-demo"}).json()
                session_id = session["session_id"]
                client.post(
                    f"/v1/sessions/{session_id}/reading",
                    json={
                        "source_type": "local_text",
                        "reference": "demo://teaching-layers",
                        "title": "Retrieval Practice",
                        "text": "Retrieval practice improves durable learning through effortful recall.",
                    },
                )
                response = client.post(
                    f"/v1/sessions/{session_id}/teaching-layers",
                    json={"layers": ["overview", "glossary"], "language": "zh"},
                )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["schema_version"], "teaching-layers-v1")
        self.assertEqual(body["stage"], "teaching_layered")
        layers = {item["layer"]: item for item in body["layers"]}
        self.assertEqual(set(layers), {"overview", "glossary"})
        self.assertEqual(layers["overview"]["task_type"], "teach.overview")
        self.assertEqual(layers["glossary"]["task_type"], "teach.glossary")
        self.assertEqual(layers["overview"]["agent"]["provider_id"], "fake-deterministic")
        self.assertEqual(layers["glossary"]["agent"]["task_type"], "teach.glossary")

    def test_layers_can_route_to_different_user_owned_agent_providers(self) -> None:
        with TemporaryDirectory() as tmpdir, self._server() as endpoint:
            client, stack, _registry = self._client(Path(tmpdir))
            with stack, client:
                overview_provider = client.post(
                    "/v1/agents/providers",
                    json={
                        "kind": "http_agent",
                        "label": "Overview Agent",
                        "endpoint": f"{endpoint}/overview",
                        "capabilities": ["teach.overview"],
                    },
                ).json()
                glossary_provider = client.post(
                    "/v1/agents/providers",
                    json={
                        "kind": "http_agent",
                        "label": "Glossary Agent",
                        "endpoint": f"{endpoint}/glossary",
                        "capabilities": ["teach.glossary"],
                    },
                ).json()
                client.post(
                    "/v1/agents/defaults",
                    json={
                        "user_id": "layer-http",
                        "capability": "teach.overview",
                        "provider_id": overview_provider["provider_id"],
                    },
                )
                client.post(
                    "/v1/agents/defaults",
                    json={
                        "user_id": "layer-http",
                        "capability": "teach.glossary",
                        "provider_id": glossary_provider["provider_id"],
                    },
                )
                session = client.post(
                    "/v1/sessions",
                    json={"user_id": "layer-http", "use_demo_agent": False},
                ).json()
                session_id = session["session_id"]
                client.post(
                    f"/v1/sessions/{session_id}/reading",
                    json={
                        "source_type": "local_text",
                        "reference": "demo://layer-routing",
                        "title": "Layer Routing",
                        "text": "Layer routing lets each agent specialize in a teaching task.",
                    },
                )
                response = client.post(
                    f"/v1/sessions/{session_id}/teaching-layers",
                    json={"layers": ["overview", "glossary"]},
                )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        layers = {item["layer"]: item for item in body["layers"]}
        self.assertEqual(layers["overview"]["agent"]["provider_id"], overview_provider["provider_id"])
        self.assertEqual(layers["glossary"]["agent"]["provider_id"], glossary_provider["provider_id"])
        self.assertEqual(
            [task["task_type"] for task in _TeachingAgentHandler.seen],
            ["teach.overview", "teach.glossary"],
        )

    def _server(self):
        class ServerContext:
            def __enter__(self_inner) -> str:
                _TeachingAgentHandler.seen = []
                try:
                    self_inner.server = HTTPServer(("127.0.0.1", 0), _TeachingAgentHandler)
                except PermissionError as exc:
                    raise unittest.SkipTest(
                        "localhost listening sockets are unavailable in this runner"
                    ) from exc
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
