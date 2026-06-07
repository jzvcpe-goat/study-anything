#!/usr/bin/env python3
"""Verify a running API against a user-owned HTTP agent endpoint."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT", "http://127.0.0.1:8787").rstrip("/")
CAPABILITIES = [
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
    "source.verify",
    "memory.retrieve",
    "embedding.create",
]


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
            "text": "A user-owned agent should generate a quiz, grade an answer, and synthesize an insight.",
        },
    )
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
        event for event in events if (event.get("payload") or {}).get("agent", {}).get("provider_id")
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
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_mock_http_agent_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
