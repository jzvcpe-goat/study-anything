#!/usr/bin/env python3
"""Verify the optional FalkorDB projection through public API endpoints."""

from __future__ import annotations

import json
import os
import sys
import time
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


def wait_for_graph() -> None:
    last_status: Any = None
    for _attempt in range(30):
        last_status = request("/v1/graph/status")
        if last_status.get("status") == "healthy":
            return
        time.sleep(2)
    raise RuntimeError(f"FalkorDB did not become healthy: {last_status}")


def assert_topology(topology: Dict[str, Any]) -> None:
    if topology.get("status") != "ready":
        raise RuntimeError(f"Topology is not ready: {topology}")
    node_types = {node["node_type"] for node in topology["nodes"]}
    edge_types = {edge["edge_type"] for edge in topology["edges"]}
    if node_types != {"Learner", "Session", "Source"}:
        raise RuntimeError(f"Unexpected topology node types: {node_types}")
    if edge_types != {"STUDIED", "USES_SOURCE", "MASTERY"}:
        raise RuntimeError(f"Unexpected topology edge types: {edge_types}")
    if len(topology["nodes"]) != 3 or len(topology["edges"]) != 3:
        raise RuntimeError(f"Projection is not idempotent: {topology}")


def main() -> None:
    wait_for_graph()
    private_text = "Private reading prose must stay outside the graph projection."
    session = request(
        "/v1/sessions",
        {"user_id": "graph-smoke-user", "track": "ACADEMIC", "use_demo_agent": True},
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://falkordb-smoke",
            "title": "FalkorDB Smoke",
            "text": private_text,
        },
    )
    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: "The source is projected only through an allowlisted DTO."}},
    )
    if completed["stage"] != "completed":
        raise RuntimeError(f"Expected completed stage, got {completed['stage']}")

    topology = request(f"/v1/sessions/{session_id}/topology")
    assert_topology(topology)
    rebuilt = request(f"/v1/sessions/{session_id}/topology/rebuild", {})
    assert_topology(rebuilt["topology"])
    serialized = json.dumps(rebuilt, ensure_ascii=False)
    if private_text in serialized or "FalkorDB Smoke" in serialized:
        raise RuntimeError("Private source prose leaked into the topology response.")
    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "nodes": len(topology["nodes"]),
                "edges": len(topology["edges"]),
                "rebuild": rebuilt["status"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_falkordb_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
