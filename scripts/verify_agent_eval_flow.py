#!/usr/bin/env python3
"""Verify Study Anything emits a redacted Agent eval artifact."""

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
    os.getenv("AGENT_ENDPOINT", "http://127.0.0.1:8787/invoke")
)
EXPECT_EXTERNAL_AGENT = os.getenv("EXPECT_EXTERNAL_AGENT", "false").lower() in {"1", "true", "yes"}
REQUEST_TIMEOUT_SECONDS = int(os.getenv("AGENT_EVAL_REQUEST_TIMEOUT_SECONDS", "10"))
PROVIDER_TIMEOUT_SECONDS = int(os.getenv("AGENT_PROVIDER_TIMEOUT_SECONDS", "15"))
VERIFIER_NAME = verifier_name_from_file(__file__)
ADAPTER_IDS = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
TEACHING_CAPABILITIES = ["teach.overview", "teach.glossary"]
CORE_CAPABILITIES = ["quiz.generate", "answer.grade", "insight.synthesize"]
REQUIRED_CAPABILITIES = TEACHING_CAPABILITIES + CORE_CAPABILITIES
PRIVATE_TITLE = "Private Agent Eval Smoke"
PRIVATE_SOURCE_TEXT = "Private source text for eval smoke must never appear in eval artifacts."
PRIVATE_ANSWER = "Private eval smoke answer."
PRIVATE_REFERENCE = "demo://agent-eval-smoke"
PRIVATE_USERS = ("agent-eval-smoke-user", "agent-eval-external-smoke-user")
FORBIDDEN_LITERALS = (
    PRIVATE_TITLE,
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ANSWER,
    PRIVATE_REFERENCE,
    *PRIVATE_USERS,
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
        PRIVATE_TITLE: "<private-title>",
        PRIVATE_SOURCE_TEXT: "<private-source-text>",
        PRIVATE_ANSWER: "<private-answer>",
        PRIVATE_REFERENCE: "<private-reference>",
        PRIVATE_USERS[0]: "<private-user>",
        PRIVATE_USERS[1]: "<private-user>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)private source text[^\"'.]*", "<private-source-text>", text)
    text = re.sub(r"(?i)private eval smoke answer", "<private-answer>", text)
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
    if "cannot reach study anything" in lowered or "connection refused" in lowered or "urlopen error" in lowered:
        return "api_unreachable"
    if "http agent is not healthy" in lowered or "bad gateway" in lowered or "502" in lowered:
        return "agent_gateway_unhealthy"
    if "teaching layers did not include" in lowered:
        return "teaching_layer_failed"
    if "required native eval gates failed" in lowered or "quality eval did not pass" in lowered:
        return "agent_eval_failed"
    if "agent eval report native gate failed" in lowered or "eval artifact is not ready" in lowered:
        return "agent_eval_failed"
    if "agent audit did not verify" in lowered:
        return "agent_audit_failed"
    if "expected a user-owned external agent" in lowered:
        return "external_agent_proof_failed"
    if "leaked private data" in lowered:
        return "privacy_leak"
    if "unexpected" in lowered and "schema" in lowered:
        return "response_schema_invalid"
    if "expected completed session" in lowered:
        return "learning_flow_incomplete"
    return "agent_eval_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        f"API_BASE={API_BASE} python3 scripts/verify_agent_eval_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the Study Anything API first with `./scripts/launch_skill_mode.sh`.",
            "If the API is already running on another port, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "agent_gateway_unhealthy": [
            "For external-agent mode, start the HTTP Agent gateway and verify its `/health` endpoint first.",
            "For zero-key verification, unset EXPECT_EXTERNAL_AGENT and use the bundled fake agent path.",
        ],
        "teaching_layer_failed": [
            "Confirm the selected Agent declares `teach.overview` and `teach.glossary`.",
            "Retry without EXPECT_EXTERNAL_AGENT to isolate custom Agent behavior.",
        ],
        "agent_eval_failed": [
            "Inspect the local agent-eval artifact/report; required native gates must pass before release evidence is valid.",
            "Do not publish raw source, answers, or provider traces while debugging.",
        ],
        "agent_audit_failed": [
            "Confirm the Agent covered teaching, quiz generation, grading, and synthesis tasks.",
            "Inspect `/v1/sessions/<session_id>/agent-audit` locally for observed task coverage.",
        ],
        "external_agent_proof_failed": [
            "If validating a user-owned Agent, run with `EXPECT_EXTERNAL_AGENT=true AGENT_ENDPOINT=<agent>/invoke`.",
            "If validating the fake-agent path, leave EXPECT_EXTERNAL_AGENT unset.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking artifact/report before using this run as release evidence.",
        ],
        "response_schema_invalid": [
            "Confirm the API server and verifier come from the same checkout.",
            "Rerun setup with `python3 scripts/setup_env.py` if the API surface is stale.",
        ],
        "learning_flow_incomplete": [
            "Check session events locally for the first failed workflow stage.",
            "Retry the fake-agent flow before testing an external Agent gateway.",
        ],
    }
    return matrix.get(classification, ["Rerun after starting the local API."]) + common


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
            "expect_external_agent": EXPECT_EXTERNAL_AGENT,
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
            f"classification: {sanitize_text(str(report.get('classification') or 'agent_eval_flow_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Run ./scripts/launch_skill_mode.sh, then rerun this verifier."]),
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
        raise RuntimeError(f"Agent eval verifier failure report leaked private data: {leaks}")


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
    except (URLError, OSError) as exc:
        raise RuntimeError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
        ) from exc


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
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
