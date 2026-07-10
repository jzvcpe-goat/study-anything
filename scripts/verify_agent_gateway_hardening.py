#!/usr/bin/env python3
"""Verify user-owned Agent gateway hardening and privacy boundaries."""

from __future__ import annotations

import argparse
import errno
import importlib.util
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


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from localhost_diagnostics import redact_diagnostic  # noqa: E402


MIN_PYTHON = (3, 11)
CONTRACT_ONLY_RECOVERY_STEPS = [
    ".venv/bin/python scripts/verify_openai_compatible_gateway.py --contract-only",
    ".venv/bin/python scripts/verify_agent_gateway_hardening.py --contract-only",
    ".venv/bin/python scripts/verify_external_agent_adapter_hardening.py --contract-only",
]


def runtime_failure_payload(
    *,
    classification: str,
    diagnostic: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "agent-gateway-hardening-error-v1",
        "status": "blocked",
        "classification": classification,
        "diagnostic": redact_diagnostic(diagnostic),
        "details": details or {},
        "next_steps": [
            ".venv/bin/python scripts/verify_agent_gateway_hardening.py --contract-only",
            ".venv/bin/python scripts/verify_agent_gateway_hardening.py --allow-localhost-block-report",
            "python3 scripts/setup_env.py",
            "./scripts/launch_skill_mode.sh",
            "./scripts/run_skill_mode_demo.sh",
        ],
        "privacy": {
            "local_absolute_paths_included": False,
            "secrets_recorded": False,
        },
    }


def runtime_failure(
    *,
    classification: str,
    diagnostic: str,
    details: dict[str, Any] | None = None,
) -> None:
    print(
        json.dumps(
            runtime_failure_payload(
                classification=classification,
                diagnostic=diagnostic,
                details=details,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    sys.exit(1)


def ensure_supported_python() -> None:
    if sys.version_info >= MIN_PYTHON:
        return
    runtime_failure(
        classification="python_version_unsupported",
        diagnostic="verify_agent_gateway_hardening requires Python 3.11 or newer.",
        details={"python_version": sys.version.split()[0]},
    )


def dependency_failure(module_name: str) -> None:
    runtime_failure(
        classification="python_dependency_missing",
        diagnostic=(
            "verify_agent_gateway_hardening dependencies are not installed "
            f"for this interpreter (missing {module_name})."
        ),
        details={"missing_module": redact_diagnostic(module_name)},
    )


ensure_supported_python()

TestClient: Any = None
api_main: Any = None
AgentRegistry: Any = None
AgentRouter: Any = None
redact_url_secrets: Any = None
InMemorySessionStore: Any = None
LearningWorkflow: Any = None


def load_runtime_dependencies() -> None:
    global TestClient, api_main, AgentRegistry, AgentRouter
    global redact_url_secrets, InMemorySessionStore, LearningWorkflow
    try:
        from fastapi.testclient import TestClient as FastApiTestClient

        from study_anything.api import main as loaded_api_main
        from study_anything.core.agent_registry import AgentRegistry as LoadedAgentRegistry
        from study_anything.core.agent_registry import AgentRouter as LoadedAgentRouter
        from study_anything.core.security import redact_url_secrets as loaded_redact_url_secrets
        from study_anything.core.store import InMemorySessionStore as LoadedInMemorySessionStore
        from study_anything.core.workflow import LearningWorkflow as LoadedLearningWorkflow
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local interpreter
        dependency_failure(exc.name or "required module")
        return
    TestClient = FastApiTestClient
    api_main = loaded_api_main
    AgentRegistry = LoadedAgentRegistry
    AgentRouter = LoadedAgentRouter
    redact_url_secrets = loaded_redact_url_secrets
    InMemorySessionStore = LoadedInMemorySessionStore
    LearningWorkflow = LoadedLearningWorkflow


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


def is_localhost_bind_error(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and exc.errno in {errno.EPERM, errno.EACCES, errno.EADDRINUSE}:
        return True
    text = str(exc).lower()
    return (
        "operation not permitted" in text
        or "permission denied" in text
        or "address already in use" in text
    )


def localhost_blocked_message(exc: BaseException) -> str:
    return (
        "Agent gateway hardening could not allocate or start a local gateway on "
        f"127.0.0.1:0: {exc}. This usually means the current runner blocks localhost "
        "listening sockets, or the host port range is unavailable. Run this verifier "
        "from a normal terminal or host shell that permits localhost sockets. If you "
        "are running the broader adoption proof from a platform sandbox, use "
        "`python3 scripts/verify_external_adoption.py --allow-localhost-block-report` "
        "to emit a machine-readable environment-blocked report."
    )


def is_localhost_blocker_message(message: str) -> bool:
    lowered = message.lower()
    return (
        ("localhost" in lowered or "127.0.0.1" in lowered)
        and (
            "operation not permitted" in lowered
            or "permission denied" in lowered
            or "blocks localhost" in lowered
            or "blocks listening sockets" in lowered
            or "could not allocate" in lowered
            or "could not start" in lowered
            or "could not bind" in lowered
        )
    )


def build_localhost_block_report(message: str) -> dict[str, Any]:
    del message
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked",
        "classification": "localhost_socket_blocked",
        "runtime": {
            "status": "not_started",
            "reason": (
                "The current runner cannot start the verifier's local dry-run Agent "
                "gateway or mock HTTP Agent, so gateway hardening cannot be executed here."
            ),
            "diagnostic": "Localhost socket allocation failed; runtime detail is withheld.",
        },
        "recovery": {
            "copyable_commands": [
                ".venv/bin/python scripts/verify_agent_gateway_hardening.py",
                *CONTRACT_ONLY_RECOVERY_STEPS,
                "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --current-worktree --allow-localhost-block-report",
                "python3 scripts/diagnose_adoption.py",
            ],
            "notes": [
                "Run from a normal terminal or host shell that permits localhost listening sockets.",
                "Use the three --contract-only checks to prove no-socket gateway and adapter contracts before leaving this sandbox.",
                "Use .venv/bin/python if system Python is older than 3.11.",
                "Contract-only checks and this blocked report do not replace runtime gateway behavior on a host terminal.",
            ],
        },
        "privacy": {
            "redacted": True,
            "secrets_returned": False,
            "raw_task_payload_returned": False,
            "agent_endpoint_secrets_returned": False,
            "real_model_keys_stored_by_study_anything": False,
        },
    }


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"verify_agent_gateway_hardening failed: {diagnostic}",
            "",
            "Next steps:",
            "  1. If this runner blocks localhost sockets, prove no-socket contracts first:",
            *[f"     {step}" for step in CONTRACT_ONLY_RECOVERY_STEPS],
            "  2. For a normal local machine, run: .venv/bin/python scripts/verify_agent_gateway_hardening.py",
            "  3. If this is an AI platform sandbox, collect a machine-readable report with:",
            "     .venv/bin/python scripts/verify_agent_gateway_hardening.py --allow-localhost-block-report",
            "  4. For the full adoption path, run:",
            "     python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --current-worktree --allow-localhost-block-report",
            "  5. For redacted environment diagnostics, run: python3 scripts/diagnose_adoption.py",
            "  6. See docs/kimi-agent-gateway.md and docs/skill-mode.md for Gateway and zero-key Skill Mode setup.",
        ]
    )


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
        try:
            self.server = HTTPServer(("127.0.0.1", 0), InvalidAgentHandler)
        except OSError as exc:
            if is_localhost_bind_error(exc):
                raise GatewayHardeningError(localhost_blocked_message(exc)) from exc
            raise
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
        try:
            sock.bind((host, 0))
        except OSError as exc:
            if is_localhost_bind_error(exc):
                raise GatewayHardeningError(localhost_blocked_message(exc)) from exc
            raise
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


def load_gateway_module() -> Any:
    spec = importlib.util.spec_from_file_location("openai_compatible_agent_gateway_hardening", GATEWAY_SCRIPT)
    if spec is None or spec.loader is None:
        raise GatewayHardeningError("Could not load openai_compatible_agent_gateway.py for contract-only verification.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_gateway_contract_only() -> dict[str, Any]:
    gateway = load_gateway_module()
    previous_mode = os.environ.get("AGENT_GATEWAY_MODE")
    os.environ["AGENT_GATEWAY_MODE"] = "dry_run"
    try:
        health = gateway._dry_run_health_payload()
        if "quiz.generate" not in health.get("capabilities", []):
            raise GatewayHardeningError(f"Gateway contract health missing capabilities: {health}")
        privacy = health.get("privacy", {})
        if privacy.get("study_anything_stores_model_keys") is not False:
            raise GatewayHardeningError(f"Gateway contract privacy drifted: {health}")

        invalid_task = {
            "task_type": "unsupported",
            "session_id": "gateway-hardening",
            "source": {"text": "Private gateway verifier source text"},
            "answers": [{"text": "Private gateway verifier answer"}],
        }
        try:
            gateway._invoke_agent(invalid_task)
        except ValueError as exc:
            invalid_error = redact_diagnostic(str(exc))
        else:
            raise GatewayHardeningError("Gateway contract accepted an unsupported task type.")
        if "Private gateway verifier" in invalid_error:
            raise GatewayHardeningError("Gateway invalid task contract leaked raw private payload.")

        valid = gateway._invoke_agent(
            {
                "task_type": "quiz.generate",
                "session_id": "gateway-hardening",
                "source": {
                    "reference": "demo://gateway-hardening",
                    "title": "Gateway Hardening",
                    "text": "Private gateway verifier source text",
                    "excerpt_hash": "gateway-hardening-hash",
                },
            }
        )
        grade = gateway._invoke_agent(
            {
                "task_type": "answer.grade",
                "session_id": "gateway-hardening",
                "source": {
                    "reference": "demo://gateway-hardening",
                    "excerpt_hash": "gateway-hardening-hash",
                },
                "answers": [{"item_id": "q1", "text": "Private gateway verifier answer"}],
            }
        )
        if valid.get("status") != "ok" or not valid.get("citations"):
            raise GatewayHardeningError(f"Gateway contract valid task drifted: {valid}")
        if grade.get("status") != "ok" or not isinstance(grade.get("score"), (int, float)):
            raise GatewayHardeningError(f"Gateway contract grade task drifted: {grade}")
        return {
            "runtime": "in_process_contract",
            "socket_required": False,
            "health_capabilities": len(health.get("capabilities", [])),
            "invalid_task_error_redacted": True,
            "valid_task_status": valid.get("status"),
            "grade_score_present": True,
        }
    finally:
        if previous_mode is None:
            os.environ.pop("AGENT_GATEWAY_MODE", None)
        else:
            os.environ["AGENT_GATEWAY_MODE"] = previous_mode


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


def build_pass_report() -> dict[str, Any]:
    load_runtime_dependencies()
    running_gateway = verify_running_gateway()
    registry_and_api = verify_registry_and_api()
    return {
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


def build_contract_report() -> dict[str, Any]:
    contract = verify_gateway_contract_only()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "runtime": "in_process_contract",
        "socket_required": False,
        "checks": {
            "contract_only": contract,
            "privacy": {
                "secrets_returned": False,
                "raw_task_payload_returned": False,
                "agent_endpoint_secrets_returned": False,
            },
        },
        "release_gate": {
            "blocking": False,
            "replaces_runtime_gateway_check": False,
            "next_runtime_gate": ".venv/bin/python scripts/verify_agent_gateway_hardening.py",
        },
    }


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--allow-localhost-block-report",
        action="store_true",
        help=(
            "When the current runner blocks localhost listening sockets, emit a "
            "machine-readable blocked report and exit 0 instead of failing. Default CI "
            "behavior remains strict."
        ),
    )
    cli.add_argument(
        "--contract-only",
        action="store_true",
        help="Validate gateway hardening contract in-process without opening localhost sockets.",
    )
    return cli


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        payload = build_contract_report() if args.contract_only else build_pass_report()
    except Exception as exc:
        if args.allow_localhost_block_report and is_localhost_blocker_message(str(exc)):
            payload = build_localhost_block_report(str(exc))
        else:
            raise
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [value for value in FORBIDDEN_VALUES if value in serialized]
    if leaks:
        raise GatewayHardeningError(f"Gateway hardening verifier leaked private values: {leaks}")
    print(serialized)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(format_cli_failure(exc), file=sys.stderr)
        sys.exit(1)
