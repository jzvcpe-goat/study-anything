#!/usr/bin/env python3
"""Verify a running Study Anything API with the public learning flow."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")


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


def main() -> None:
    health = request("/v1/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"API health is not ok: {health}")

    plugins = request("/v1/plugins")
    if not isinstance(plugins, list):
        raise RuntimeError("Plugin endpoint did not return a list.")

    agents = request("/v1/agents/status")
    if agents.get("schema_version") != "agent-v1":
        raise RuntimeError(f"Agent status is not agent-v1: {agents}")

    session = request(
        "/v1/sessions",
        {"user_id": "smoke-user", "track": "ACADEMIC", "use_demo_agent": True},
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://full-api-flow",
            "title": "Full API Flow",
            "text": "A launch smoke test should create a quiz, grade an answer, and update mastery.",
        },
    )
    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: "The system uses source evidence to update mastery."}},
    )
    if completed["stage"] != "completed":
        raise RuntimeError(f"Expected completed stage, got {completed['stage']}")
    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "stage": completed["stage"],
                "mastery": completed["mastery"],
                "agent_schema": agents["schema_version"],
                "plugins": len(plugins),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_full_api_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
