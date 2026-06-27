#!/usr/bin/env python3
"""Verify the OpenAI-compatible Agent gateway in dry-run mode.

The verifier proves the same gateway used for Kimi/OpenAI-compatible providers can be
validated from a clean clone before the user supplies a real model key.
"""

from __future__ import annotations

import argparse
import errno
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import resolve_api_base


GATEWAY_SCRIPT = ROOT / "scripts" / "openai_compatible_agent_gateway.py"
DEFAULT_GATEWAY_PORT = 8787
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
CONTRACT_ONLY_RECOVERY_STEPS = [
    "python3 scripts/verify_openai_compatible_gateway.py --contract-only",
    "python3 scripts/verify_agent_gateway_hardening.py --contract-only",
    "python3 scripts/verify_external_agent_adapter_hardening.py --contract-only",
]


class GatewayVerificationError(RuntimeError):
    """Readable verification failure."""


FORBIDDEN_LITERALS = (
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ANSWER,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "AGENT_ENDPOINT=http",
)


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = re.sub(r"/Users/[^\s\"'?&]+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", text)
    text = re.sub(r"([?&](?:api[_-]?key|token|secret)=)[^&\s\"']+", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text.strip()[:1600]


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if (
        "localhost gateway socket cannot listen" in lowered
        or "localhost gateway health cannot be reached" in lowered
        or "blocks localhost" in lowered
        or "blocks local sockets" in lowered
        or "permits localhost sockets" in lowered
        or "operation not permitted" in lowered
        or "permission denied" in lowered
        or "listening sockets" in lowered
    ):
        return "localhost_socket_blocked"
    if "already in use" in lowered:
        return "gateway_port_in_use"
    if "did not become healthy" in lowered:
        return "gateway_health_timeout"
    if "cannot reach" in lowered or "connection refused" in lowered or "urlopen error" in lowered:
        return "api_or_gateway_unreachable"
    if "http 5" in lowered or "configuration_required" in lowered or "bad gateway" in lowered:
        return "gateway_upstream_configuration_required"
    if "malformed json" in lowered:
        return "gateway_malformed_json"
    if "leaked private data" in lowered or "audit/eval evidence leaked" in lowered:
        return "privacy_leak"
    return "gateway_verification_failed"


def next_steps_for(classification: str) -> list[str]:
    common = [
        "python3 scripts/diagnose_adoption.py",
        "python3 scripts/verify_openai_compatible_gateway.py --gateway-only",
        "./scripts/launch_skill_mode.sh",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run this verifier from a normal terminal or host shell that permits localhost sockets.",
            "If you are inside a platform sandbox, collect the blocked report and rerun on the host.",
            "To prove no-socket gateway/adapter contracts before leaving this sandbox, run:",
            *CONTRACT_ONLY_RECOVERY_STEPS,
            "These contract-only checks do not replace the runtime gateway smoke on a host terminal.",
        ],
        "gateway_port_in_use": [
            "Pass `--port` with a free port, for example `--port 8788`.",
            "Stop the process already using the gateway port.",
        ],
        "gateway_health_timeout": [
            "Start the gateway directly with `AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --port 8787`.",
            "Check whether the port is blocked or already in use.",
        ],
        "api_or_gateway_unreachable": [
            "For gateway-only checks, verify `GET /health` on the gateway port.",
            "For API flow checks, start Skill Mode first and set `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "gateway_upstream_configuration_required": [
            "Use dry-run mode for zero-key verification.",
            "For real upstream mode, keep model keys inside your own gateway environment.",
        ],
        "gateway_malformed_json": [
            "Retry with dry-run mode to isolate upstream model formatting.",
            "If using a real upstream model, ensure it returns the AgentResult JSON contract.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript.",
            "Fix the leaking gateway/API response before filing public evidence.",
        ],
    }
    return matrix.get(classification, ["Run the gateway verifier with --gateway-only to isolate gateway startup."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": next_steps_for(classification),
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def format_failure_for_human(report: dict[str, Any]) -> str:
    steps = [
        f"- {sanitize_text(str(step))}"
        for step in report.get("next_steps", [])
        if isinstance(step, str) and step.strip()
    ]
    return "\n".join(
        [
            "verify_openai_compatible_gateway failed:",
            f"classification: {sanitize_text(str(report.get('classification') or 'gateway_verification_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Run the gateway verifier with --gateway-only to isolate gateway startup."]),
        ]
    )


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise GatewayVerificationError(f"Gateway verifier failure report leaked private data: {leaks}")


def local_socket_blocked_text(host: str, port: int | str) -> str:
    return (
        f"Localhost gateway socket cannot listen on {host}:{port} from this runner. "
        "This usually means the current agent sandbox blocks localhost listening sockets. "
        "Run this verifier from a normal terminal or host shell that permits localhost sockets."
    )


def is_local_socket_blocked_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "operation not permitted" in text
        or "errno 1" in text
        or "permission denied" in text
        or "errno 13" in text
        or "permissionerror" in text
    )


def find_free_port(host: str) -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])
    except OSError as exc:
        if exc.errno in {errno.EPERM, errno.EACCES} or is_local_socket_blocked_error(exc):
            raise GatewayVerificationError(local_socket_blocked_text(host, "auto")) from exc
        raise GatewayVerificationError(f"Cannot reserve a gateway port on {host}: {exc}") from exc


def check_bind_preflight(host: str, port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise GatewayVerificationError(
                f"Gateway port is already in use: {host}:{port}. "
                "Pass --port with a free port, or stop the process using this port."
            ) from exc
        if exc.errno in {errno.EPERM, errno.EACCES} or is_local_socket_blocked_error(exc):
            raise GatewayVerificationError(local_socket_blocked_text(host, port)) from exc
        raise GatewayVerificationError(f"Gateway bind preflight failed for {host}:{port}: {exc}") from exc


def resolve_gateway_port(host: str, port: int | None, *, reuse_running_gateway: bool) -> int:
    if port is not None:
        return port
    if reuse_running_gateway:
        return DEFAULT_GATEWAY_PORT
    return find_free_port(host)


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
        if is_local_socket_blocked_error(exc):
            raise GatewayVerificationError(
                "Localhost gateway health cannot be reached from this runner. "
                "Run this verifier from a normal terminal or host shell that permits "
                f"localhost sockets. URL: {url}"
            ) from exc
        raise GatewayVerificationError(f"Cannot reach {url}: {exc}") from exc
    except OSError as exc:
        if is_local_socket_blocked_error(exc):
            raise GatewayVerificationError(
                "Localhost gateway health cannot be reached from this runner. "
                "Run this verifier from a normal terminal or host shell that permits "
                f"localhost sockets. URL: {url}"
            ) from exc
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


def gateway_contract_tasks() -> list[Dict[str, Any]]:
    source = {
        "reference": "demo://openai-compatible-gateway",
        "title": "OpenAI-Compatible Gateway Smoke",
        "text": PRIVATE_SOURCE_TEXT,
        "excerpt_hash": "gateway-smoke-hash",
    }
    return [
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


def validate_gateway_task_result(task: Dict[str, Any], result: Dict[str, Any]) -> None:
    task_type = str(task["task_type"])
    if result.get("status") != "ok":
        raise GatewayVerificationError(f"Gateway returned invalid status for {task_type}: {result}")
    if task_type == "answer.grade" and not isinstance(result.get("score"), (int, float)):
        raise GatewayVerificationError(f"Gateway grading result missing score: {result}")
    if not result.get("citations"):
        raise GatewayVerificationError(f"Gateway result missing source citation: {result}")


def verify_direct_gateway_contract(gateway_base: str) -> list[str]:
    health = wait_for_health(gateway_base)
    if health.get("mode") != "dry_run" or health.get("configured") is not True:
        raise GatewayVerificationError(f"Gateway health does not prove dry-run mode: {health}")
    observed: list[str] = []
    for task in gateway_contract_tasks():
        result = invoke_gateway(gateway_base, task)
        task_type = str(task["task_type"])
        observed.append(task_type)
        validate_gateway_task_result(task, result)
    return observed


def load_gateway_module() -> Any:
    spec = importlib.util.spec_from_file_location("openai_compatible_agent_gateway_contract", GATEWAY_SCRIPT)
    if spec is None or spec.loader is None:
        raise GatewayVerificationError("Could not load openai_compatible_agent_gateway.py for contract-only verification.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_inprocess_gateway_contract() -> list[str]:
    gateway = load_gateway_module()
    previous_mode = os.environ.get("AGENT_GATEWAY_MODE")
    os.environ["AGENT_GATEWAY_MODE"] = "dry_run"
    try:
        health = gateway._dry_run_health_payload()
        if health.get("mode") != "dry_run" or health.get("configured") is not True:
            raise GatewayVerificationError(f"In-process gateway health does not prove dry-run mode: {health}")
        observed: list[str] = []
        for task in gateway_contract_tasks():
            result = gateway._invoke_agent(task)
            if not isinstance(result, dict):
                raise GatewayVerificationError(f"In-process gateway returned non-object result for {task['task_type']}: {result}")
            observed.append(str(task["task_type"]))
            validate_gateway_task_result(task, result)
        return observed
    finally:
        if previous_mode is None:
            os.environ.pop("AGENT_GATEWAY_MODE", None)
        else:
            os.environ["AGENT_GATEWAY_MODE"] = previous_mode


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
    parser.add_argument(
        "--port",
        type=int,
        help=(
            "Gateway port. Defaults to 8787 with --reuse-running-gateway; otherwise an "
            "ephemeral free port is selected for the verifier-owned dry-run gateway."
        ),
    )
    parser.add_argument("--api-base", default=resolve_api_base())
    parser.add_argument("--gateway-only", action="store_true")
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help="Validate the dry-run gateway contract in-process without opening localhost sockets.",
    )
    parser.add_argument("--reuse-running-gateway", action="store_true")
    parser.add_argument(
        "--api-agent-endpoint",
        help="Endpoint the Study Anything API should call. Defaults to the local dry-run gateway.",
    )
    args = parser.parse_args()

    if args.contract_only:
        direct_tasks = verify_inprocess_gateway_contract()
        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": "dry_run",
                    "runtime": "in_process_contract",
                    "direct_tasks": direct_tasks,
                    "socket_required": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return

    port = resolve_gateway_port(
        args.host,
        args.port,
        reuse_running_gateway=bool(args.reuse_running_gateway),
    )
    gateway_base = f"http://{args.host}:{port}"
    process: Optional[subprocess.Popen[bytes]] = None
    if not args.reuse_running_gateway:
        check_bind_preflight(args.host, port)
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
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
