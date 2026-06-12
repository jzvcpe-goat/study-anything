#!/usr/bin/env python3
"""Verify the OpenAI-compatible Agent gateway in dry-run mode.

The verifier proves the same gateway used for Kimi/OpenAI-compatible providers can be
validated from a clean clone before the user supplies a real model key.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
GATEWAY_SCRIPT = ROOT / "scripts" / "openai_compatible_agent_gateway.py"
DEFAULT_CAPABILITIES = [
    "teach.overview",
    "teach.glossary",
    "teach.examples",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
    "note.scribe",
    "source.verify",
    "embedding.create",
]
PRIVATE_SOURCE_TEXT = "Private OpenAI-compatible gateway smoke source text must stay redacted."
PRIVATE_ANSWER = "Private OpenAI-compatible gateway smoke answer."


class GatewayVerificationError(RuntimeError):
    """Readable verification failure."""


def find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def request_json(url: str, payload: Optional[Dict[str, Any]] = None, *, timeout: int = 10) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise GatewayVerificationError(f"HTTP {exc.code} for {url}: {detail}") from exc
    except URLError as exc:
        raise GatewayVerificationError(f"Cannot reach {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GatewayVerificationError(f"{url} returned malformed JSON: {exc}") from exc


def api_request(api_base: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    return request_json(f"{api_base.rstrip('/')}{path}", payload)


def wait_for_health(gateway_base: str, *, timeout_seconds: float = 10.0) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            health = request_json(f"{gateway_base}/health", timeout=2)
            if isinstance(health, dict) and health.get("status") == "ok":
                return health
        except Exception as exc:  # pragma: no cover - depends on process startup timing
            last_error = exc
        time.sleep(0.2)
    raise GatewayVerificationError(f"Gateway did not become healthy: {last_error}")


def start_dry_run_gateway(host: str, port: int) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env["AGENT_GATEWAY_MODE"] = "dry_run"
    return subprocess.Popen(
        [sys.executable, str(GATEWAY_SCRIPT), "--host", host, "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def invoke_gateway(gateway_base: str, task: Dict[str, Any]) -> Dict[str, Any]:
    result = request_json(f"{gateway_base}/invoke", task)
    if not isinstance(result, dict) or result.get("status") != "ok":
        raise GatewayVerificationError(f"Gateway returned invalid result for {task}: {result}")
    return result


def verify_direct_gateway_contract(gateway_base: str) -> list[str]:
    health = wait_for_health(gateway_base)
    if health.get("mode") != "dry_run" or health.get("configured") is not True:
        raise GatewayVerificationError(f"Gateway health does not prove dry-run mode: {health}")
    source = {
        "reference": "demo://openai-compatible-gateway",
        "title": "OpenAI-Compatible Gateway Smoke",
        "text": PRIVATE_SOURCE_TEXT,
        "excerpt_hash": "gateway-smoke-hash",
    }
    tasks = [
        {"task_type": "teach.overview", "session_id": "gateway-direct", "source": source},
        {"task_type": "teach.glossary", "session_id": "gateway-direct", "source": source},
        {"task_type": "quiz.generate", "session_id": "gateway-direct", "source": source},
        {
            "task_type": "answer.grade",
            "session_id": "gateway-direct",
            "source": source,
            "answers": [{"item_id": "gateway", "text": PRIVATE_ANSWER}],
        },
        {
            "task_type": "insight.synthesize",
            "session_id": "gateway-direct",
            "source": source,
            "constraints": {"mastery_level": 0.8},
        },
    ]
    observed: list[str] = []
    for task in tasks:
        result = invoke_gateway(gateway_base, task)
        task_type = str(task["task_type"])
        observed.append(task_type)
        if task_type == "answer.grade" and not isinstance(result.get("score"), (int, float)):
            raise GatewayVerificationError(f"Gateway grading result missing score: {result}")
        if not result.get("citations"):
            raise GatewayVerificationError(f"Gateway result missing source citation: {result}")
    return observed


def find_existing_provider(api_base: str, endpoint: str) -> Optional[Dict[str, Any]]:
    status = api_request(api_base, "/v1/agents/status")
    for provider in status.get("providers", []):
        if (
            provider.get("kind") == "http_agent"
            and str(provider.get("endpoint", "")).rstrip("/") == endpoint.rstrip("/")
            and set(provider.get("capabilities", [])) >= set(DEFAULT_CAPABILITIES)
        ):
            return provider
    return None


def verify_api_flow(api_base: str, endpoint: str) -> Dict[str, Any]:
    provider = find_existing_provider(api_base, endpoint) or api_request(
        api_base,
        "/v1/agents/providers",
        {
            "kind": "http_agent",
            "label": "OpenAI-Compatible Dry-Run Gateway",
            "endpoint": endpoint,
            "capabilities": DEFAULT_CAPABILITIES,
            "metadata": {"source": "verify_openai_compatible_gateway"},
        },
    )
    health = api_request(api_base, "/v1/agents/test", {"provider_id": provider["provider_id"]})
    if health.get("status") != "healthy":
        raise GatewayVerificationError(f"API could not validate gateway provider: {health}")

    user_id = "openai-compatible-gateway-smoke-user"
    for capability in DEFAULT_CAPABILITIES:
        api_request(
            api_base,
            "/v1/agents/defaults",
            {
                "user_id": user_id,
                "capability": capability,
                "provider_id": provider["provider_id"],
            },
        )

    session = api_request(
        api_base,
        "/v1/sessions",
        {
            "user_id": user_id,
            "track": "ACADEMIC",
            "use_demo_agent": False,
            "use_demo_provider": False,
        },
    )
    session_id = session["session_id"]
    api_request(
        api_base,
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://openai-compatible-gateway",
            "title": "OpenAI-Compatible Gateway Smoke",
            "text": PRIVATE_SOURCE_TEXT,
        },
    )
    teaching = api_request(
        api_base,
        f"/v1/sessions/{session_id}/teaching-layers",
        {"layers": ["overview", "glossary"], "language": "zh", "level": "beginner"},
    )
    teaching_tasks = [
        layer.get("agent", {}).get("task_type")
        for layer in teaching.get("layers", [])
        if isinstance(layer, dict)
    ]
    for required_task in ["teach.overview", "teach.glossary"]:
        if required_task not in teaching_tasks:
            raise GatewayVerificationError(f"API teaching layers did not use gateway: {teaching}")
    running = api_request(api_base, f"/v1/sessions/{session_id}/run", {})
    quiz_items = running.get("quiz_items") or []
    if not quiz_items:
        raise GatewayVerificationError(f"Gateway-backed run did not create quiz: {running}")
    quiz_id = quiz_items[0]["item_id"]
    completed = api_request(
        api_base,
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: PRIVATE_ANSWER}},
    )
    if completed.get("stage") != "completed":
        raise GatewayVerificationError(f"Gateway-backed flow did not complete: {completed}")
    mastery = api_request(api_base, f"/v1/sessions/{session_id}/mastery")
    audit = api_request(api_base, f"/v1/sessions/{session_id}/agent-audit")
    artifact = api_request(api_base, f"/v1/sessions/{session_id}/agent-eval/artifact")
    if audit.get("status") != "verified" or not audit.get("used_external_agent"):
        raise GatewayVerificationError(f"Agent audit did not verify gateway use: {audit}")
    if artifact.get("status") != "ready_for_external_eval" or not artifact.get(
        "used_external_agent"
    ):
        raise GatewayVerificationError(
            f"Agent eval artifact did not verify gateway use: {artifact}"
        )
    serialized_evidence = json.dumps({"audit": audit, "artifact": artifact}, ensure_ascii=False)
    forbidden = [
        PRIVATE_SOURCE_TEXT,
        PRIVATE_ANSWER,
        endpoint,
        "AGENT_LLM_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    leaks = [fragment for fragment in forbidden if fragment in serialized_evidence]
    if leaks:
        raise GatewayVerificationError(f"Gateway audit/eval evidence leaked private data: {leaks}")
    return {
        "provider_id": provider["provider_id"],
        "session_id": session_id,
        "mastery": mastery,
        "teaching_tasks": teaching_tasks,
        "audit_status": audit["status"],
        "eval_schema": artifact["schema_version"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--api-base", default=os.getenv("API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--gateway-only", action="store_true")
    parser.add_argument("--reuse-running-gateway", action="store_true")
    parser.add_argument(
        "--api-agent-endpoint",
        help="Endpoint the Study Anything API should call. Defaults to the local dry-run gateway.",
    )
    args = parser.parse_args()

    port = args.port or find_free_port(args.host)
    gateway_base = f"http://{args.host}:{port}"
    process: Optional[subprocess.Popen[bytes]] = None
    if not args.reuse_running_gateway:
        process = start_dry_run_gateway(args.host, port)
    try:
        direct_tasks = verify_direct_gateway_contract(gateway_base)
        api_result: Optional[Dict[str, Any]] = None
        if not args.gateway_only:
            endpoint = args.api_agent_endpoint or f"{gateway_base}/invoke"
            api_result = verify_api_flow(args.api_base.rstrip("/"), endpoint)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "gateway_base": gateway_base,
                    "mode": "dry_run",
                    "direct_tasks": direct_tasks,
                    "api_flow": api_result,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
                process.kill()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_openai_compatible_gateway failed: {exc}", file=sys.stderr)
        sys.exit(1)
