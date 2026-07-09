#!/usr/bin/env python3
"""Verify the optional FalkorDB projection through public API endpoints."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import format_api_unreachable, resolve_api_base, verifier_name_from_file


API_BASE = resolve_api_base()
VERIFIER_NAME = verifier_name_from_file(__file__)
PRIVATE_SOURCE_TEXT = "Private reading prose must stay outside the graph projection."
PRIVATE_ANSWER = "The source is projected only through an allowlisted DTO."
PRIVATE_USER = "graph-smoke-user"
PRIVATE_TITLE = "FalkorDB Smoke"
PRIVATE_REFERENCE = "demo://falkordb-smoke"
FORBIDDEN_LITERALS = (
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ANSWER,
    PRIVATE_USER,
    PRIVATE_TITLE,
    PRIVATE_REFERENCE,
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
        PRIVATE_TITLE: "<private-title>",
        PRIVATE_REFERENCE: "<private-reference>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)private reading prose[^\"'\n.]*\.?", "<private-source-text>", text)
    text = re.sub(r"(?i)source is projected only[^\"'\n.]*\.?", "<private-answer>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", text)
    text = re.sub(r"/Users/[^\s\"'?&]+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/tmp/[^\s\"'?&]+", "<temp-path>", text)
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
    if "cannot reach study anything" in lowered or "connection refused" in lowered or "urlopen error" in lowered:
        return "api_unreachable"
    if "falkordb did not become healthy" in lowered:
        if "disabled" in lowered:
            return "graph_disabled"
        return "graph_unhealthy"
    if "503" in lowered or "unavailable" in lowered:
        return "graph_unavailable"
    if "409" in lowered or "data" in lowered and "insufficient" in lowered:
        return "topology_data_insufficient"
    if "expected completed stage" in lowered:
        return "learning_flow_incomplete"
    if "topology is not ready" in lowered or "unexpected topology" in lowered or "projection is not idempotent" in lowered:
        return "topology_contract_failed"
    if "leaked" in lowered or "private source prose" in lowered:
        return "privacy_leak"
    return "falkordb_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "docker compose --profile full up -d",
        f"API_BASE={API_BASE} python3 scripts/verify_falkordb_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the API first, then pass the running URL with `API_BASE=http://127.0.0.1:<port>`.",
            "For the full Docker profile, ensure the API container is healthy before running this verifier.",
        ],
        "graph_disabled": [
            "Enable FalkorDB for this smoke with `FALKORDB_ENABLED=true`.",
            "Start the full Compose profile that includes FalkorDB before running the verifier.",
        ],
        "graph_unhealthy": [
            "Check `/v1/graph/status` and the FalkorDB container logs.",
            "Confirm `FALKORDB_HOST`, `FALKORDB_PORT`, and `FALKORDB_GRAPH` point to the Compose service.",
        ],
        "graph_unavailable": [
            "The graph API is unavailable; confirm FalkorDB is enabled and reachable.",
            "Rerun after the full stack reports healthy containers.",
        ],
        "topology_data_insufficient": [
            "Complete a learning session before rebuilding topology.",
            "Rerun this verifier from a clean full-stack smoke so it creates its own source-bound session.",
        ],
        "learning_flow_incomplete": [
            "Run `python3 scripts/verify_full_api_flow.py` first to isolate core learning-loop failures.",
            "Check session events locally for the first failed workflow stage.",
        ],
        "topology_contract_failed": [
            "Inspect topology DTOs; the public API must expose only Learner, Session, Source and STUDIED/USES_SOURCE/MASTERY.",
            "Check FalkorDB projection idempotency before publishing full-stack evidence.",
        ],
        "privacy_leak": [
            "Do not share the raw topology response publicly.",
            "Fix graph projection privacy before using this run as release evidence.",
        ],
    }
    return matrix.get(classification, ["Rerun after the full Docker stack and FalkorDB are healthy."]) + common


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
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "graph_connection_details_included": False,
            "real_model_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"/tmp/[^\s\"']+", serialized):
        leaks.append("tmp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise RuntimeError(f"FalkorDB verifier failure report leaked private data: {leaks}")


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
    session = request(
        "/v1/sessions",
        {"user_id": PRIVATE_USER, "track": "ACADEMIC", "use_demo_agent": True},
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": PRIVATE_REFERENCE,
            "title": PRIVATE_TITLE,
            "text": PRIVATE_SOURCE_TEXT,
        },
    )
    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: PRIVATE_ANSWER}},
    )
    if completed["stage"] != "completed":
        raise RuntimeError(f"Expected completed stage, got {completed['stage']}")

    topology = request(f"/v1/sessions/{session_id}/topology")
    assert_topology(topology)
    rebuilt = request(f"/v1/sessions/{session_id}/topology/rebuild", {})
    assert_topology(rebuilt["topology"])
    serialized = json.dumps(rebuilt, ensure_ascii=False)
    if PRIVATE_SOURCE_TEXT in serialized or PRIVATE_TITLE in serialized:
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
        print(json.dumps(failure_report(exc), ensure_ascii=False, sort_keys=True))
        print(f"verify_falkordb_flow failed: {sanitize_text(str(exc))}", file=sys.stderr)
        sys.exit(1)
