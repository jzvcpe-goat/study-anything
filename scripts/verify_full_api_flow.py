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
    metrics = request("/v1/metrics/pmf")
    if metrics.get("schema_version") != "pmf-v1":
        raise RuntimeError(f"PMF metrics schema is not pmf-v1: {metrics}")
    if metrics.get("sessions", {}).get("completed", 0) < 1:
        raise RuntimeError(f"PMF metrics did not count the completed smoke session: {metrics}")
    intent = request(
        "/v1/pmf/interest",
        {
            "user_id": "smoke-user",
            "services": ["hosted_alpha"],
            "source": "verify_full_api_flow",
        },
    )
    if not intent.get("local_only"):
        raise RuntimeError(f"PMF interest should be local-only: {intent}")
    try:
        request("/v1/pmf/export", {"destination": "self_archive"})
    except RuntimeError as exc:
        if "409" not in str(exc):
            raise
    else:
        raise RuntimeError("PMF export should require explicit consent.")
    export = request(
        "/v1/pmf/export",
        {
            "consent_to_share": True,
            "destination": "self_archive",
            "note": "Smoke export note must not be included.",
        },
    )
    if export.get("schema_version") != "pmf-export-v1":
        raise RuntimeError(f"PMF export schema is not pmf-export-v1: {export}")
    serialized_export = json.dumps(export, ensure_ascii=False)
    if "Smoke export note" in serialized_export or "smoke-user" in serialized_export:
        raise RuntimeError(f"PMF export leaked private smoke data: {export}")
    pmf_summary = request("/v1/pmf/summary")
    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "stage": completed["stage"],
                "mastery": completed["mastery"],
                "agent_schema": agents["schema_version"],
                "plugins": len(plugins),
                "pmf_completed_sessions": metrics["sessions"]["completed"],
                "pmf_interest_total": pmf_summary["total"],
                "pmf_export_schema": export["schema_version"],
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
