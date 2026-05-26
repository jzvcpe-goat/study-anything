from __future__ import annotations

import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, ClassVar

from _path import ROOT  # noqa: F401

from study_anything.core.agent_registry import (
    AgentCapability,
    AgentConfigurationRequired,
    AgentProviderUnavailable,
    AgentRegistry,
    AgentResultInvalid,
    AgentRouter,
    AgentTask,
)
from study_anything.core.model_registry import Capability, ModelRegistry, ModelRouter


class _AgentHandler(BaseHTTPRequestHandler):
    response: ClassVar[dict[str, Any] | str] = {
        "status": "ok",
        "content": "Focus on source evidence",
        "metadata": {"tokens": {"prompt": 5, "completion": 4}},
    }
    seen: ClassVar[list[dict[str, Any]]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.__class__.seen.append(payload)
        body = (
            self.response
            if isinstance(self.response, str)
            else json.dumps(self.response).encode("utf-8").decode("utf-8")
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


class AgentRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        _AgentHandler.response = {
            "status": "ok",
            "content": "Focus on source evidence",
            "metadata": {"tokens": {"prompt": 5, "completion": 4}},
        }
        _AgentHandler.seen = []

    def test_fake_agent_requires_explicit_user_default(self) -> None:
        registry = AgentRegistry()
        router = AgentRouter(registry)
        task = AgentTask(task_type="quiz.generate", session_id="s1", source={"text": "hello world"})

        with self.assertRaises(AgentConfigurationRequired):
            router.invoke(user_id="alice", capability=AgentCapability.QUIZ_GENERATE, task=task)

        registry.set_demo_defaults("alice")
        response = router.invoke(user_id="alice", capability=AgentCapability.QUIZ_GENERATE, task=task)

        self.assertEqual(response.provider_id, "fake-deterministic")
        self.assertEqual(response.status, "ok")
        self.assertIn("Focus on", response.content)

    def test_provider_status_redacts_secret_metadata(self) -> None:
        registry = AgentRegistry()
        provider = registry.configure_provider(
            kind="http_agent",
            label="Local Gateway",
            endpoint="http://localhost:8787",
            metadata={"api_key": "secret", "owner": "local"},
        )

        public = provider.public_dict()

        self.assertEqual(public["metadata"]["api_key"], "[redacted]")
        self.assertEqual(public["metadata"]["owner"], "local")

    def test_registry_persists_providers_and_defaults(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agents.json"
            registry = AgentRegistry(path)
            provider = registry.configure_provider(
                kind="http_agent",
                label="Local Agent",
                endpoint="http://localhost:8787",
                capabilities=["quiz.generate"],
            )
            registry.set_default("alice", AgentCapability.QUIZ_GENERATE, provider.provider_id)

            restored = AgentRegistry(path)
            status = restored.status("alice")

            self.assertEqual(status["defaults"]["quiz.generate"], provider.provider_id)
            self.assertTrue(
                any(item["provider_id"] == provider.provider_id for item in status["providers"])
            )

    def test_registry_saves_are_safe_under_concurrent_defaults(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agents.json"
            registry = AgentRegistry(path)
            provider = registry.configure_provider(
                kind="http_agent",
                label="Concurrent Agent",
                endpoint="http://localhost:8787",
                capabilities=["quiz.generate", "answer.grade", "insight.synthesize"],
            )

            def set_default(capability: str) -> None:
                registry.set_default("alice", capability, provider.provider_id)

            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(set_default, ["quiz.generate", "answer.grade", "insight.synthesize"]))

            restored = AgentRegistry(path)
            status = restored.status("alice")

            self.assertEqual(status["defaults"]["quiz.generate"], provider.provider_id)
            self.assertEqual(status["defaults"]["answer.grade"], provider.provider_id)
            self.assertEqual(status["defaults"]["insight.synthesize"], provider.provider_id)

    def test_http_agent_success_and_contract_payload(self) -> None:
        with self._server() as endpoint:
            registry = AgentRegistry()
            provider = registry.configure_provider(
                kind="http_agent",
                label="Mock Agent",
                endpoint=endpoint,
                capabilities=["quiz.generate"],
            )
            registry.set_default("alice", AgentCapability.QUIZ_GENERATE, provider.provider_id)
            task = AgentTask(
                task_type="quiz.generate",
                session_id="s1",
                source={"text": "source-bound mastery", "reference": "demo://source"},
            )

            result = AgentRouter(registry).invoke(
                user_id="alice",
                capability=AgentCapability.QUIZ_GENERATE,
                task=task,
            )

            self.assertEqual(result.content, "Focus on source evidence")
            self.assertEqual(_AgentHandler.seen[-1]["task_type"], "quiz.generate")
            self.assertNotIn("api_key", json.dumps(_AgentHandler.seen[-1]))

    def test_http_agent_malformed_json_is_invalid_result(self) -> None:
        with self._server(response="{not-json") as endpoint:
            registry = AgentRegistry()
            provider = registry.configure_provider(
                kind="http_agent",
                label="Bad Agent",
                endpoint=endpoint,
                capabilities=["quiz.generate"],
            )
            registry.set_default("alice", AgentCapability.QUIZ_GENERATE, provider.provider_id)

            with self.assertRaises(AgentResultInvalid):
                AgentRouter(registry).invoke(
                    user_id="alice",
                    capability=AgentCapability.QUIZ_GENERATE,
                    task=AgentTask(task_type="quiz.generate", session_id="s1"),
                )

    def test_http_agent_unavailable_is_reported_by_health(self) -> None:
        registry = AgentRegistry()
        provider = registry.configure_provider(
            kind="http_agent",
            label="Offline Agent",
            endpoint="http://127.0.0.1:9",
            capabilities=["source.verify"],
            timeout_seconds=1,
        )

        health = registry.test_provider(provider.provider_id)

        self.assertEqual(health.status, "unhealthy")
        self.assertIn("HTTP agent unavailable", health.message)

    def test_cli_agent_is_disabled_by_default(self) -> None:
        registry = AgentRegistry()
        provider = registry.configure_provider(
            kind="cli_agent",
            label="Local CLI Agent",
            command=["agent", "run"],
            capabilities=["quiz.generate"],
        )
        registry.set_default("alice", AgentCapability.QUIZ_GENERATE, provider.provider_id)

        with self.assertRaises(AgentProviderUnavailable):
            AgentRouter(registry).invoke(
                user_id="alice",
                capability=AgentCapability.QUIZ_GENERATE,
                task=AgentTask(task_type="quiz.generate", session_id="s1"),
            )

    def test_deprecated_model_router_uses_agent_backing(self) -> None:
        registry = ModelRegistry()
        registry.set_demo_defaults("alice")

        response = ModelRouter(registry).complete(
            user_id="alice",
            capability=Capability.CHAT,
            prompt="source-bound learning",
        )

        self.assertEqual(response.provider_id, "fake-deterministic")
        self.assertTrue(response.public_metadata()["deprecated"])

    def _server(self, response: dict[str, Any] | str | None = None):
        class ServerContext:
            def __enter__(self_inner) -> str:
                if response is not None:
                    _AgentHandler.response = response
                self_inner.server = HTTPServer(("127.0.0.1", 0), _AgentHandler)
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
