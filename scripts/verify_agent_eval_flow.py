#!/usr/bin/env python3
"""Verify Study Anything emits a redacted Agent eval artifact."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
AGENT_ENDPOINT = os.getenv("AGENT_ENDPOINT", "http://127.0.0.1:8787").rstrip("/")
EXPECT_EXTERNAL_AGENT = os.getenv("EXPECT_EXTERNAL_AGENT", "false").lower() in {"1", "true", "yes"}
REQUEST_TIMEOUT_SECONDS = int(os.getenv("AGENT_EVAL_REQUEST_TIMEOUT_SECONDS", "10"))
PROVIDER_TIMEOUT_SECONDS = int(os.getenv("AGENT_PROVIDER_TIMEOUT_SECONDS", "15"))
ADAPTER_IDS = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
TEACHING_CAPABILITIES = ["teach.overview", "teach.glossary"]
CORE_CAPABILITIES = ["quiz.generate", "answer.grade", "insight.synthesize"]
REQUIRED_CAPABILITIES = TEACHING_CAPABILITIES + CORE_CAPABILITIES


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{exc.code} {path}: {detail}") from exc


def session_failure_summary(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": value.get("session_id"),
        "stage": value.get("stage"),
        "source": {
            "source_type": (value.get("source") or {}).get("source_type")
            if isinstance(value.get("source"), dict)
            else None,
            "reference_present": bool((value.get("source") or {}).get("reference"))
            if isinstance(value.get("source"), dict)
            else False,
            "excerpt_hash_present": bool((value.get("source") or {}).get("excerpt_hash"))
            if isinstance(value.get("source"), dict)
            else False,
        },
        "teaching_layer_count": len(value.get("teaching_layers") or []),
        "quiz_item_count": len(value.get("quiz_items") or []),
        "grading_result_count": len(value.get("grading_results") or []),
        "insight_count": len(value.get("insights") or []),
        "open_hitl": [
            {
                "kind": item.get("kind"),
                "message": item.get("message"),
            }
            for item in value.get("hitl_interrupts", [])
            if isinstance(item, dict) and item.get("status") == "open"
        ],
        "event_count": len(value.get("events") or []),
    }


def main() -> None:
    user_id = "agent-eval-external-smoke-user" if EXPECT_EXTERNAL_AGENT else "agent-eval-smoke-user"
    if EXPECT_EXTERNAL_AGENT:
        provider = request(
            "/v1/agents/providers",
            {
                "kind": "http_agent",
                "label": "Agent Eval HTTP Smoke",
                "endpoint": AGENT_ENDPOINT,
                "capabilities": REQUIRED_CAPABILITIES,
                "timeout_seconds": PROVIDER_TIMEOUT_SECONDS,
                "metadata": {"source": "verify_agent_eval_flow"},
            },
        )
        health = request("/v1/agents/test", {"provider_id": provider["provider_id"]})
        if health.get("status") != "healthy":
            raise RuntimeError(f"HTTP Agent is not healthy for eval smoke: {health}")
        for capability in REQUIRED_CAPABILITIES:
            request(
                "/v1/agents/defaults",
                {
                    "user_id": user_id,
                    "capability": capability,
                    "provider_id": provider["provider_id"],
                },
            )

    session = request(
        "/v1/sessions",
        {
            "user_id": user_id,
            "track": "ACADEMIC",
            "use_demo_agent": not EXPECT_EXTERNAL_AGENT,
            "use_demo_provider": not EXPECT_EXTERNAL_AGENT,
        },
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://agent-eval-smoke",
            "title": "Private Agent Eval Smoke",
            "text": "Private source text for eval smoke must never appear in eval artifacts.",
        },
    )
    teaching = request(
        f"/v1/sessions/{session_id}/teaching-layers",
        {
            "layers": ["overview", "glossary"],
            "language": "zh",
            "level": "beginner",
        },
    )
    teaching_tasks = [
        layer.get("agent", {}).get("task_type")
        for layer in teaching.get("layers", [])
        if isinstance(layer, dict)
    ]
    for task_type in TEACHING_CAPABILITIES:
        if task_type not in teaching_tasks:
            raise RuntimeError(f"Teaching layers did not include {task_type}: {teaching}")

    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: "Private eval smoke answer."}},
    )
    if completed.get("stage") != "completed":
        raise RuntimeError(
            "Expected completed session, got redacted summary: "
            f"{session_failure_summary(completed)}"
        )

    audit = request(f"/v1/sessions/{session_id}/agent-audit")
    if audit.get("schema_version") != "agent-audit-v1":
        raise RuntimeError(f"Unexpected audit schema: {audit}")
    if audit.get("status") != "verified":
        raise RuntimeError(f"Agent audit did not verify required task coverage: {audit}")

    artifact = request(f"/v1/sessions/{session_id}/agent-eval/artifact")
    if artifact.get("schema_version") != "agent-eval-artifact-v1":
        raise RuntimeError(f"Unexpected eval artifact schema: {artifact}")
    if artifact.get("status") != "ready_for_external_eval":
        raise RuntimeError(f"Eval artifact is not ready for external eval: {artifact}")
    if EXPECT_EXTERNAL_AGENT and not artifact.get("used_external_agent"):
        raise RuntimeError(f"Expected a user-owned external Agent, got: {artifact}")
    required_gates = [gate for gate in artifact.get("native_gates", []) if gate.get("required")]
    failed_gates = [gate for gate in required_gates if gate.get("status") != "pass"]
    if failed_gates:
        raise RuntimeError(f"Required native eval gates failed: {failed_gates}")
    adapter_ids = {adapter.get("adapter_id") for adapter in artifact.get("adapter_strategy", [])}
    if adapter_ids != ADAPTER_IDS:
        raise RuntimeError(f"Unexpected adapter strategy: {adapter_ids}")
    trajectory_tasks = [step.get("task_type") for step in artifact.get("trajectory", [])]
    missing_trajectory_tasks = [task for task in CORE_CAPABILITIES if task not in trajectory_tasks]
    if missing_trajectory_tasks:
        raise RuntimeError(f"Unexpected Agent trajectory: {trajectory_tasks}")

    quality = request(f"/v1/sessions/{session_id}/agent-eval/quality")
    if quality.get("schema_version") != "agent-quality-eval-v1":
        raise RuntimeError(f"Unexpected quality eval schema: {quality}")
    if quality.get("status") != "pass":
        raise RuntimeError(f"Quality eval did not pass: {quality}")

    report = request(f"/v1/sessions/{session_id}/agent-eval/report")
    if report.get("schema_version") != "agent-eval-report-v1":
        raise RuntimeError(f"Unexpected Agent eval report schema: {report}")
    if (report.get("native_fast_gate") or {}).get("status") != "pass":
        raise RuntimeError(f"Agent eval report native gate failed: {report}")

    serialized = json.dumps({"artifact": artifact, "report": report}, ensure_ascii=False)
    forbidden_fragments = [
        "Private Agent Eval Smoke",
        "Private source text",
        "Private eval smoke answer",
        "127.0.0.1:8787",
        "OPENAI_API_KEY",
    ]
    leaks = [fragment for fragment in forbidden_fragments if fragment in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9]{16,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise RuntimeError(f"Eval artifact leaked private data: {leaks}")

    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "eval_schema": artifact["schema_version"],
                "artifact_status": artifact["status"],
                "agent_audit_status": audit["status"],
                "quality_schema": quality["schema_version"],
                "quality_status": quality["status"],
                "eval_report_schema": report["schema_version"],
                "eval_report_status": report["status"],
                "used_external_agent": artifact["used_external_agent"],
                "used_fake_agent": artifact["used_fake_agent"],
                "adapter_ids": sorted(adapter_ids),
                "teaching_tasks": teaching_tasks,
                "trajectory_tasks": trajectory_tasks,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_agent_eval_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
