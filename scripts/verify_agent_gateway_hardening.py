#!/usr/bin/env python3
"""Verify user-owned Agent gateway hardening and privacy boundaries."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.api import main as api_main  # noqa: E402
from study_anything.core.agent_registry import AgentRegistry, AgentRouter  # noqa: E402
from study_anything.core.security import redact_url_secrets  # noqa: E402
from study_anything.core.store import InMemorySessionStore  # noqa: E402
from study_anything.core.workflow import LearningWorkflow  # noqa: E402


SCHEMA_VERSION = "agent-gateway-hardening-verification-v1"
GATEWAY_SCRIPT = ROOT / "scripts" / "openai_compatible_agent_gateway.py"
FORBIDDEN_VALUES = [
    "gateway-secret",
    "api_key=secret",
    "Authorization",
    "Bearer secret",
    "Private gateway verifier source text",
    "Private gateway verifier answer",
]


class GatewayHardeningError(RuntimeError):
    """Readable gateway hardening verification failure."""


class InvalidAgentHandler(BaseHTTPRequestHandler):
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


class HttpServerContext:
    def __init__(self, response: dict[str, Any] | str) -> None:
        self.response = response

    def __enter__(self) -> str:
        InvalidAgentHandler.response = self.response
        self.server = HTTPServer(("127.0.0.1", 0), InvalidAgentHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def request_json(url: str, payload: dict[str, Any] | None = None, *, timeout: int = 10) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        try:
            payload = json.loads(detail)
        except json.JSONDecodeError:
            payload = {"raw": detail}
        return exc.code, payload
    except URLError as exc:
        raise GatewayHardeningError(f"Cannot reach {url}: {exc}") from exc


def wait_for_gateway(base_url: str) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, payload = request_json(f"{base_url}/health", timeout=2)
            if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                return payload
        except Exception as exc:  # pragma: no cover - startup timing
            last_error = exc
        time.sleep(0.2)
    raise GatewayHardeningError(f"Gateway did not become healthy: {last_error}")


def start_dry_run_gateway() -> tuple[subprocess.Popen[bytes], str]:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["AGENT_GATEWAY_MODE"] = "dry_run"
    process = subprocess.Popen(
        [sys.executable, str(GATEWAY_SCRIPT), "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process, base_url


def verify_running_gateway() -> dict[str, Any]:
    process, base_url = start_dry_run_gateway()
    try:
        health = wait_for_gateway(base_url)
        if "quiz.generate" not in health.get("capabilities", []):
            raise GatewayHardeningError(f"Gateway health missing capabilities: {health}")
        privacy = health.get("privacy", {})
        if privacy.get("study_anything_stores_model_keys") is not False:
            raise GatewayHardeningError(f"Gateway privacy contract drifted: {health}")

        status, invalid = request_json(
            f"{base_url}/invoke",
            {
                "task_type": "unsupported",
                "session_id": "gateway-hardening",
                "source": {"text": "Private gateway verifier source text"},
                "answers": [{"text": "Private gateway verifier answer"}],
            },
        )
        if status != 400 or invalid.get("diagnostic_code") != "invalid_agent_task":
            raise GatewayHardeningError(f"Gateway invalid task response drifted: {invalid}")
        invalid_task_status = status
        serialized_invalid = json.dumps(invalid, ensure_ascii=False)
        if "Private gateway verifier" in serialized_invalid:
            raise GatewayHardeningError("Gateway invalid task leaked raw private payload.")

        status, valid = request_json(
            f"{base_url}/invoke",
            {
                "task_type": "quiz.generate",
                "session_id": "gateway-hardening",
                "source": {
                    "reference": "demo://gateway-hardening",
                    "title": "Gateway Hardening",
                    "text": "Private gateway verifier source text",
                    "excerpt_hash": "gateway-hardening-hash",
                },
            },
        )
        if status != 200 or valid.get("status") != "ok" or not valid.get("citations"):
            raise GatewayHardeningError(f"Gateway valid task response drifted: {valid}")
        return {
            "gateway_base": base_url,
            "health_capabilities": len(health.get("capabilities", [])),
            "invalid_task_status": invalid_task_status,
            "valid_task_status": valid.get("status"),
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
            process.kill()


def verify_registry_and_api() -> dict[str, Any]:
    redacted = redact_url_secrets("http://user:gateway-secret@127.0.0.1:8787/invoke?api_key=secret")
    if redacted != "http://127.0.0.1:8787/invoke?api_key=%5Bredacted%5D":
        raise GatewayHardeningError(f"URL redaction drifted: {redacted}")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        registry = AgentRegistry(root / "agents.json")
        try:
            registry.configure_provider(
                kind="http_agent",
                label="Unsafe Agent",
                endpoint="http://127.0.0.1:8787/invoke?api_key=secret",
                capabilities=["quiz.generate"],
            )
        except ValueError:
            rejected_secret_endpoint = True
        else:
            rejected_secret_endpoint = False
        try:
            registry.configure_provider(
                kind="http_agent",
                label="Unsafe Metadata Agent",
                endpoint="http://127.0.0.1:8787/invoke",
                capabilities=["quiz.generate"],
                metadata={"api_key": "gateway-secret"},
            )
        except ValueError:
            rejected_secret_metadata = True
        else:
            rejected_secret_metadata = False
        if not rejected_secret_endpoint or not rejected_secret_metadata:
            raise GatewayHardeningError("Registry accepted unsafe Agent provider config.")

        with HttpServerContext({"status": "maybe", "content": "bad"}) as endpoint:
            provider = registry.configure_provider(
                kind="http_agent",
                label="Invalid Agent",
                endpoint=endpoint,
                capabilities=["source.verify"],
            )
            health = registry.test_provider(provider.provider_id).public_dict()
        if health.get("diagnostic_code") != "invalid_status":
            raise GatewayHardeningError(f"Registry health diagnostic drifted: {health}")

    with tempfile.TemporaryDirectory() as tmpdir, HttpServerContext(
        {"status": "ok", "content": ""}
    ) as endpoint:
        stack = ExitStack()
        registry = AgentRegistry(Path(tmpdir) / "agents.json")
        stack.enter_context(patch_api("store", InMemorySessionStore()))
        stack.enter_context(patch_api("agent_registry", registry))
        stack.enter_context(patch_api("agent_router", AgentRouter(registry)))
        stack.enter_context(patch_api("workflow", LearningWorkflow(AgentRouter(registry))))
        with stack, TestClient(api_main.create_app()) as client:
            unsafe = client.post(
                "/v1/agents/providers",
                json={
                    "kind": "http_agent",
                    "label": "Unsafe API Agent",
                    "endpoint": "http://127.0.0.1:8787/invoke?api_key=secret",
                    "capabilities": ["quiz.generate"],
                },
            )
            provider_response = client.post(
                "/v1/agents/providers",
                json={
                    "kind": "http_agent",
                    "label": "Schema Bad API Agent",
                    "endpoint": endpoint,
                    "capabilities": ["quiz.generate"],
                },
            )
            provider = provider_response.json()
            invalid_invoke = client.post(
                f"/v1/agents/{provider['provider_id']}/invoke",
                json={"task_type": "quiz.generate", "session_id": "gateway-hardening"},
            )
        if unsafe.status_code != 400 or "api_key=secret" in unsafe.text or "gateway-secret" in unsafe.text:
            raise GatewayHardeningError(f"API unsafe provider response leaked detail: {unsafe.text}")
        if invalid_invoke.status_code != 422:
            raise GatewayHardeningError(f"API invalid invoke status drifted: {invalid_invoke.text}")
    return {
        "registry_secret_endpoint_rejected": rejected_secret_endpoint,
        "registry_secret_metadata_rejected": rejected_secret_metadata,
        "registry_health_diagnostic": health.get("diagnostic_code"),
        "api_secret_endpoint_status": unsafe.status_code,
        "api_invalid_invoke_status": invalid_invoke.status_code,
    }


def patch_api(name: str, value: Any) -> Any:
    from unittest.mock import patch

    return patch.object(api_main, name, value)


def main() -> None:
    running_gateway = verify_running_gateway()
    registry_and_api = verify_registry_and_api()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "checks": {
            "running_gateway": running_gateway,
            "registry_and_api": registry_and_api,
            "privacy": {
                "secrets_returned": False,
                "raw_task_payload_returned": False,
                "agent_endpoint_secrets_returned": False,
            },
        },
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [value for value in FORBIDDEN_VALUES if value in serialized]
    if leaks:
        raise GatewayHardeningError(f"Gateway hardening verifier leaked private values: {leaks}")
    print(serialized)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_agent_gateway_hardening failed: {exc}", file=sys.stderr)
        sys.exit(1)
