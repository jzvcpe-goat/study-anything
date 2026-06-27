#!/usr/bin/env python3
"""Verify a running API against a user-owned HTTP agent endpoint."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import format_api_unreachable, resolve_api_base, verifier_name_from_file
from study_anything_cli import normalise_http_agent_endpoint


API_BASE = resolve_api_base()
AGENT_ENDPOINT = normalise_http_agent_endpoint(
    os.getenv("AGENT_ENDPOINT")
    or os.getenv("STUDY_ANYTHING_TEST_AGENT_ENDPOINT")
    or "http://127.0.0.1:8787/invoke"
)
VERIFIER_NAME = verifier_name_from_file(__file__)
PRIVATE_SOURCE_TEXT = (
    "A user-owned agent should generate a quiz, grade an answer, "
    "and synthesize an insight."
)
PRIVATE_ANSWER = "The agent follows the source-bound task contract."
PRIVATE_USER = "http-agent-smoke-user"
PRIVATE_REFERENCE = "demo://mock-http-agent"
PRIVATE_TITLE = "Mock HTTP Agent Flow"
CAPABILITIES = [
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
FORBIDDEN_LITERALS = (
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ANSWER,
    PRIVATE_USER,
    PRIVATE_REFERENCE,
    PRIVATE_TITLE,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    replacements = {
        PRIVATE_SOURCE_TEXT: "<private-source-text>",
        PRIVATE_ANSWER: "<private-answer>",
        PRIVATE_USER: "<private-user>",
        PRIVATE_REFERENCE: "<private-reference>",
        PRIVATE_TITLE: "<private-title>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)user-owned agent should generate a quiz[^\"'.]*", "<private-source-text>", text)
    text = re.sub(r"(?i)source-bound task contract", "<private-answer>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", text)
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
        "runner appears to block localhost sockets" in lowered
        or "blocks localhost" in lowered
        or "operation not permitted" in lowered
        or "permission denied" in lowered
        or "localhost_socket_blocked" in lowered
    ):
        return "localhost_socket_blocked"
    if "cannot reach study anything" in lowered or "urlopen error" in lowered:
        return "api_unreachable"
    if "mock http agent is not healthy" in lowered:
        return "agent_health_failed"
    if "connection refused" in lowered or "bad gateway" in lowered or "502" in lowered:
        return "agent_gateway_unreachable"
    if "teaching layer" in lowered:
        return "teaching_layer_failed"
    if "agent eval required gates failed" in lowered or "agent eval artifact is not ready" in lowered:
        return "agent_eval_failed"
    if "agent audit did not verify" in lowered or "external agent proof" in lowered:
        return "external_agent_proof_failed"
    if "schema is not" in lowered or "schema mismatch" in lowered:
        return "response_schema_invalid"
    if "expected completed stage" in lowered:
        return "learning_flow_incomplete"
    if "leaked private" in lowered:
        return "privacy_leak"
    return "mock_http_agent_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        "AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --host 127.0.0.1 --port 8787",
        f"API_BASE={API_BASE} AGENT_ENDPOINT={AGENT_ENDPOINT} python3 scripts/verify_mock_http_agent_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run this verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the Study Anything API first with `./scripts/launch_skill_mode.sh`.",
            "If the API is already running elsewhere, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "agent_health_failed": [
            "Check the agent endpoint health or start the local dry-run gateway.",
            "For zero-key verification, use `AGENT_GATEWAY_MODE=dry_run` and do not configure real model keys.",
        ],
        "agent_gateway_unreachable": [
            "Start the configured HTTP Agent endpoint before running this verifier.",
            "If using the local gateway, verify `curl http://127.0.0.1:8787/health` first.",
        ],
        "teaching_layer_failed": [
            "Confirm the agent declares `teach.overview` and `teach.glossary` capabilities.",
            "Retry with the bundled dry-run gateway to isolate custom agent behavior.",
        ],
        "agent_eval_failed": [
            "The external-agent run must pass required native eval gates before release evidence is valid.",
            "Inspect the local agent-eval artifact; do not publish raw source or answers.",
        ],
        "external_agent_proof_failed": [
            "Confirm the session was created with `use_demo_agent=false` and the HTTP provider set as default.",
            "Check the session agent-audit endpoint locally for observed task coverage.",
        ],
        "response_schema_invalid": [
            "Confirm the API server and verifier come from the same checkout.",
            "Rerun setup with `python3 scripts/setup_env.py` if the generated API surface is stale.",
        ],
        "learning_flow_incomplete": [
            "Check session events locally for the first failed workflow stage.",
            "Retry with the dry-run gateway before testing a custom agent.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking API or agent response before using this run as evidence.",
        ],
    }
    return matrix.get(classification, ["Rerun after starting the local API and HTTP Agent endpoint."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": VERIFIER_NAME,
            "api_base": sanitize_text(API_BASE),
            "agent_endpoint": sanitize_text(AGENT_ENDPOINT),
        },
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
            f"{VERIFIER_NAME} failed:",
            f"classification: {sanitize_text(str(report.get('classification') or 'mock_http_agent_flow_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Start the local API and HTTP Agent endpoint, then rerun this verifier."]),
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
        raise RuntimeError(f"Mock HTTP Agent verifier failure report leaked private data: {leaks}")


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{exc.code} {path}: {detail}") from exc
    except (URLError, OSError) as exc:
        raise RuntimeError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
        ) from exc


def find_existing_provider() -> Optional[Dict[str, Any]]:
    status = request("/v1/agents/status")
    for provider in status.get("providers", []):
        if (
            provider.get("kind") == "http_agent"
            and provider.get("endpoint", "").rstrip("/") == AGENT_ENDPOINT
            and set(provider.get("capabilities", [])) >= set(CAPABILITIES)
        ):
            return provider
    return None


def main() -> None:
    provider = find_existing_provider() or request(
        "/v1/agents/providers",
        {
            "kind": "http_agent",
            "label": "Smoke HTTP Agent",
            "endpoint": AGENT_ENDPOINT,
            "capabilities": CAPABILITIES,
            "metadata": {"source": "verify_mock_http_agent_flow"},
        },
    )
    health = request("/v1/agents/test", {"provider_id": provider["provider_id"]})
    if health["status"] != "healthy":
        raise RuntimeError(f"Mock HTTP agent is not healthy: {health}")

    for capability in CAPABILITIES:
        request(
            "/v1/agents/defaults",
            {
                "user_id": "http-agent-smoke-user",
                "capability": capability,
                "provider_id": provider["provider_id"],
            },
        )

    session = request(
        "/v1/sessions",
        {
            "user_id": "http-agent-smoke-user",
            "track": "ACADEMIC",
            "use_demo_agent": False,
            "use_demo_provider": False,
        },
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://mock-http-agent",
            "title": "Mock HTTP Agent Flow",
            "text": (
                "A user-owned agent should generate a quiz, grade an answer, "
                "and synthesize an insight."
            ),
        },
    )
    teaching = request(
        f"/v1/sessions/{session_id}/teaching-layers",
        {"layers": ["overview", "glossary"], "language": "zh", "level": "beginner"},
    )
    if teaching.get("schema_version") != "teaching-layers-v1":
        raise RuntimeError(f"Teaching layer schema mismatch: {teaching}")
    teaching_tasks = [
        layer.get("agent", {}).get("task_type")
        for layer in teaching.get("layers", [])
        if isinstance(layer, dict)
    ]
    for required_task in ["teach.overview", "teach.glossary"]:
        if required_task not in teaching_tasks:
            raise RuntimeError(f"Teaching layer missing {required_task}: {teaching}")
    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: "The agent follows the source-bound task contract."}},
    )
    if completed["stage"] != "completed":
        raise RuntimeError(f"Expected completed stage, got {completed['stage']}")
    events = request(f"/v1/sessions/{session_id}/events")
    handled_by_agent = [
        event
        for event in events
        if (event.get("payload") or {}).get("agent", {}).get("provider_id")
    ]
    if len(handled_by_agent) < 2:
        raise RuntimeError("Expected agent metadata in workflow events.")
    agent_audit = request(f"/v1/sessions/{session_id}/agent-audit")
    if agent_audit.get("schema_version") != "agent-audit-v1":
        raise RuntimeError(f"Agent audit schema is not agent-audit-v1: {agent_audit}")
    if agent_audit.get("status") != "verified":
        raise RuntimeError(f"Agent audit did not verify full coverage: {agent_audit}")
    if not agent_audit.get("used_external_agent"):
        raise RuntimeError(f"Agent audit did not identify the user-owned HTTP agent: {agent_audit}")
    agent_eval_artifact = request(f"/v1/sessions/{session_id}/agent-eval/artifact")
    if agent_eval_artifact.get("schema_version") != "agent-eval-artifact-v1":
        raise RuntimeError(
            f"Agent eval artifact schema is not agent-eval-artifact-v1: {agent_eval_artifact}"
        )
    if agent_eval_artifact.get("status") != "ready_for_external_eval":
        raise RuntimeError(
            f"Agent eval artifact is not ready for external eval: {agent_eval_artifact}"
        )
    if not agent_eval_artifact.get("used_external_agent"):
        raise RuntimeError(
            f"Agent eval artifact did not preserve external Agent proof: {agent_eval_artifact}"
        )
    required_eval_gates = [
        gate for gate in agent_eval_artifact.get("native_gates", []) if gate.get("required")
    ]
    failed_eval_gates = [gate for gate in required_eval_gates if gate.get("status") != "pass"]
    if failed_eval_gates:
        raise RuntimeError(f"Agent eval required gates failed: {failed_eval_gates}")
    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "stage": completed["stage"],
                "mastery": completed["mastery"],
                "agent_provider": provider["provider_id"],
                "agent_events": len(handled_by_agent),
                "agent_audit_status": agent_audit["status"],
                "agent_audit_observed_tasks": agent_audit["observed_tasks"],
                "agent_audit_used_external_agent": agent_audit["used_external_agent"],
                "agent_eval_schema": agent_eval_artifact["schema_version"],
                "agent_eval_used_external_agent": agent_eval_artifact["used_external_agent"],
                "teaching_tasks": teaching_tasks,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
