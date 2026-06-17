#!/usr/bin/env python3
"""Verify multi-teacher Agent attribution and eval boundaries."""

from __future__ import annotations

import json
import re
import sys
import threading
from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything import __version__  # noqa: E402
from study_anything.core.agent_audit import build_agent_audit  # noqa: E402
from study_anything.core.agent_eval import (  # noqa: E402
    AGENT_EVAL_ADAPTERS,
    build_agent_eval_artifact,
    build_agent_eval_report,
)
from study_anything.core.agent_registry import (  # noqa: E402
    AgentCapability,
    AgentProviderConfig,
    AgentProviderKind,
    AgentRegistry,
    AgentRouter,
)
from study_anything.core.quality_eval import build_agent_quality_eval  # noqa: E402
from study_anything.core.workflow import (  # noqa: E402
    Answer,
    LearningState,
    LearningWorkflow,
    append_event,
    new_session,
    submit_answers,
    submit_reading,
)


SCHEMA_VERSION = "multiteacher-agent-eval-hardening-v1"
EXTERNAL_PROVIDER_ID = "mock-multiteacher-http-agent"
USER_ID = "multiteacher-eval-user"
PRIVATE_SOURCE = "Private multi-teacher source text that must never appear in eval output."
PRIVATE_ANSWER = "Private multi-teacher learner answer that must never appear in eval output."
SECRET_FRAGMENT = "sk-proj-multiteacherVerifierSecret000000"
REQUIRED_MULTI_TEACHER_TASKS = [
    AgentCapability.TEACH_OVERVIEW.value,
    AgentCapability.TEACH_GLOSSARY.value,
    AgentCapability.QUIZ_GENERATE.value,
    AgentCapability.ANSWER_GRADE.value,
    AgentCapability.INSIGHT_SYNTHESIZE.value,
]
FORBIDDEN_PATTERNS = [
    re.compile(re.escape(PRIVATE_SOURCE)),
    re.compile(re.escape(PRIVATE_ANSWER)),
    re.compile(re.escape(SECRET_FRAGMENT)),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
]


class MultiTeacherAgentEvalHardeningError(RuntimeError):
    """Readable multi-teacher Agent eval verification failure."""


class MultiTeacherAgentHandler(BaseHTTPRequestHandler):
    calls: ClassVar[list[str]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            task = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send({"status": "error", "content": "Malformed task."}, status=400)
            return
        task_type = str(task.get("task_type") or "")
        self.calls.append(task_type)
        source = task.get("source") if isinstance(task.get("source"), Mapping) else {}
        citation = {
            "reference": source.get("reference"),
            "excerpt_hash": source.get("excerpt_hash"),
        }
        payload: dict[str, Any] = {
            "status": "ok",
            "content": "Source-bound multi-teacher response.",
            "citations": [citation],
            "confidence": 0.91,
            "metadata": {
                "teacher_layer": task_type,
                "debug_token": SECRET_FRAGMENT,
                "nested": {"authorization": f"Bearer {SECRET_FRAGMENT}"},
                "tokens": {"prompt": 19, "completion": 11},
            },
        }
        if task_type == AgentCapability.TEACH_OVERVIEW.value:
            payload["content"] = {
                "summary": "The source describes how learning loops use evidence.",
                "key_points": ["source binding", "Agent attribution", "quality gate"],
            }
        elif task_type == AgentCapability.TEACH_GLOSSARY.value:
            payload["content"] = [
                {
                    "term": "Agent attribution",
                    "plain_language": "A record of which Agent handled a learning task.",
                    "technical_definition": "Provider/task/status metadata emitted by a workflow node.",
                    "example": "The glossary layer records teach.glossary from the HTTP Agent.",
                }
            ]
        elif task_type == AgentCapability.QUIZ_GENERATE.value:
            payload["content"] = "Agent attribution"
        elif task_type == AgentCapability.ANSWER_GRADE.value:
            payload["score"] = 0.88
            payload["feedback"] = "Grounded answer with a source-bound claim."
        elif task_type == AgentCapability.INSIGHT_SYNTHESIZE.value:
            payload["content"] = "Use multi-teacher evidence before trusting platform submissions."
        elif task_type == AgentCapability.SOURCE_VERIFY.value:
            payload["content"] = "Source verified."
            payload["score"] = 1.0
        self._send(payload)

    def _send(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MultiTeacherAgentServer(AbstractContextManager[str]):
    def __enter__(self) -> str:
        MultiTeacherAgentHandler.calls = []
        self.server = HTTPServer(("127.0.0.1", 0), MultiTeacherAgentHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def configure_registry(*, endpoint: str | None = None) -> AgentRegistry:
    registry = AgentRegistry()
    if endpoint is None:
        registry.set_demo_defaults(USER_ID)
        return registry
    provider = registry.register_provider(
        AgentProviderConfig(
            provider_id=EXTERNAL_PROVIDER_ID,
            kind=AgentProviderKind.HTTP_AGENT,
            label="Mock Multi-Teacher HTTP Agent",
            endpoint=endpoint,
            capabilities=[AgentCapability(value) for value in REQUIRED_MULTI_TEACHER_TASKS]
            + [AgentCapability.SOURCE_VERIFY],
            timeout_seconds=3,
            metadata={"verifier": "multiteacher-agent-eval-hardening"},
        )
    )
    for task_type in REQUIRED_MULTI_TEACHER_TASKS:
        registry.set_default(USER_ID, AgentCapability(task_type), provider.provider_id)
    return registry


def run_learning_loop(registry: AgentRegistry) -> tuple[LearningState, dict[str, Any]]:
    workflow = LearningWorkflow(AgentRouter(registry))
    state = new_session(USER_ID, track="AI_PRODUCT")
    state = submit_reading(
        state,
        source_type="document",
        reference="demo://multiteacher-agent-eval",
        title="Multi-Teacher Agent Eval",
        text=PRIVATE_SOURCE,
    )
    state = workflow.teaching_layers(state, layers=("overview", "glossary"))
    state = workflow.run(state)
    if not state.quiz_items:
        raise MultiTeacherAgentEvalHardeningError("Learning loop did not generate a quiz item.")
    state = submit_answers(
        state,
        [Answer(item_id=state.quiz_items[0].item_id, text=PRIVATE_ANSWER)],
    )
    state = workflow.run(state)
    audit = build_agent_audit(state, agent_status=registry.status(USER_ID))
    artifact = build_agent_eval_artifact(audit)
    quality = build_agent_quality_eval(state, agent_audit=audit, agent_eval_artifact=artifact)
    report = build_agent_eval_report(
        agent_audit=audit,
        agent_eval_artifact=artifact,
        quality_eval=quality,
    )
    return state, {
        "audit": audit,
        "artifact": artifact,
        "quality": quality,
        "report": report,
        "matrix": attribution_matrix(state),
    }


def attribution_matrix(state: LearningState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in state.events:
        agents = []
        payload = event.payload
        if isinstance(payload.get("agent"), Mapping):
            agents.append(payload["agent"])
        if isinstance(payload.get("agents"), list):
            agents.extend(item for item in payload["agents"] if isinstance(item, Mapping))
        for agent in agents:
            rows.append(
                {
                    "event_type": event.type,
                    "node": event.node,
                    "task_type": agent.get("task_type"),
                    "provider_id": agent.get("provider_id"),
                    "status": agent.get("status"),
                    "latency_ms": agent.get("latency_ms"),
                    "confidence": agent.get("confidence"),
                    "metadata": agent.get("metadata"),
                }
            )
    return rows


def assert_agent_report(
    label: str,
    evidence: Mapping[str, Any],
    *,
    expected_provider_id: str,
    used_external_agent: bool,
    used_fake_agent: bool,
) -> dict[str, Any]:
    audit = require_mapping(evidence.get("audit"), f"{label}.audit")
    artifact = require_mapping(evidence.get("artifact"), f"{label}.artifact")
    quality = require_mapping(evidence.get("quality"), f"{label}.quality")
    report = require_mapping(evidence.get("report"), f"{label}.report")
    matrix = evidence.get("matrix")
    if not isinstance(matrix, list):
        raise MultiTeacherAgentEvalHardeningError(f"{label} attribution matrix is missing.")

    observed_tasks = set(audit.get("observed_tasks") or [])
    missing = [task for task in REQUIRED_MULTI_TEACHER_TASKS if task not in observed_tasks]
    if missing:
        raise MultiTeacherAgentEvalHardeningError(f"{label} missing task attribution: {missing}")
    if audit.get("status") != "verified":
        raise MultiTeacherAgentEvalHardeningError(f"{label} audit did not verify: {audit.get('status')}")
    if artifact.get("status") != "ready_for_external_eval":
        raise MultiTeacherAgentEvalHardeningError(f"{label} eval artifact is not ready.")
    if quality.get("status") != "pass":
        raise MultiTeacherAgentEvalHardeningError(f"{label} quality gate did not pass.")
    if (report.get("native_fast_gate") or {}).get("status") != "pass":
        raise MultiTeacherAgentEvalHardeningError(f"{label} native fast gate did not pass.")
    if bool(artifact.get("used_external_agent")) is not used_external_agent:
        raise MultiTeacherAgentEvalHardeningError(f"{label} external-agent flag drifted.")
    if bool(artifact.get("used_fake_agent")) is not used_fake_agent:
        raise MultiTeacherAgentEvalHardeningError(f"{label} fake-agent flag drifted.")

    by_task = {str(row.get("task_type")): row for row in matrix if isinstance(row, Mapping)}
    for task_type in REQUIRED_MULTI_TEACHER_TASKS:
        row = by_task.get(task_type)
        if not row:
            raise MultiTeacherAgentEvalHardeningError(f"{label} missing matrix row for {task_type}.")
        if row.get("provider_id") != expected_provider_id:
            raise MultiTeacherAgentEvalHardeningError(
                f"{label} expected {expected_provider_id} for {task_type}, got {row.get('provider_id')}."
            )
        if row.get("status") != "ok":
            raise MultiTeacherAgentEvalHardeningError(f"{label} non-ok status for {task_type}.")
        if not isinstance(row.get("latency_ms"), int):
            raise MultiTeacherAgentEvalHardeningError(f"{label} missing latency for {task_type}.")
        confidence = row.get("confidence")
        if confidence is not None and not isinstance(confidence, (int, float)):
            raise MultiTeacherAgentEvalHardeningError(
                f"{label} invalid confidence for {task_type}: {confidence!r}"
            )

    return {
        "audit_status": audit.get("status"),
        "artifact_status": artifact.get("status"),
        "quality_status": quality.get("status"),
        "quality_score": quality.get("quality_score"),
        "native_fast_gate_status": (report.get("native_fast_gate") or {}).get("status"),
        "observed_tasks": sorted(observed_tasks),
        "provider_ids": audit.get("provider_ids"),
        "used_external_agent": artifact.get("used_external_agent"),
        "used_fake_agent": artifact.get("used_fake_agent"),
        "matrix_rows": len(matrix),
    }


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MultiTeacherAgentEvalHardeningError(f"{label} must be an object.")
    return value


def assert_no_leaks(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized)]
    if leaks:
        raise MultiTeacherAgentEvalHardeningError(
            f"Multi-teacher Agent eval report leaked private data: {leaks}"
        )


def assert_failure_modes(
    *,
    external_state: LearningState,
    external_registry: AgentRegistry,
) -> dict[str, Any]:
    missing_teaching_state = run_learning_without_teaching(configure_registry())
    missing_audit = build_agent_audit(
        missing_teaching_state,
        agent_status=configure_registry().status(USER_ID),
    )
    missing_artifact = build_agent_eval_artifact(missing_audit)
    if missing_audit.get("status") != "partial":
        raise MultiTeacherAgentEvalHardeningError(
            f"Missing teaching attribution should produce partial audit: {missing_audit}"
        )
    if set(missing_audit.get("missing_tasks") or []) != {
        AgentCapability.TEACH_OVERVIEW.value,
        AgentCapability.TEACH_GLOSSARY.value,
    }:
        raise MultiTeacherAgentEvalHardeningError(
            f"Missing teaching attribution did not report the missing teaching tasks: {missing_audit}"
        )
    if missing_artifact.get("status") != "blocked":
        raise MultiTeacherAgentEvalHardeningError(
            f"Missing attribution should block external eval artifact: {missing_artifact}"
        )

    forged_state = append_event(
        external_state,
        event_type="agent.invocation.forged",
        node="agent_audit_negative_case",
        payload={
            "agent": {
                "provider_id": "forged-provider",
                "task_type": AgentCapability.TEACH_OVERVIEW.value,
                "status": "ok",
                "latency_ms": 1,
            }
        },
    )
    forged_audit = build_agent_audit(
        forged_state,
        agent_status=external_registry.status(USER_ID),
    )
    if forged_audit.get("status") != "invalid_provider_evidence":
        raise MultiTeacherAgentEvalHardeningError(
            f"Forged provider attribution should be invalid: {forged_audit}"
        )
    if forged_audit.get("unregistered_provider_ids") != ["forged-provider"]:
        raise MultiTeacherAgentEvalHardeningError(
            f"Forged provider id was not reported: {forged_audit}"
        )

    try:
        assert_no_leaks({"leak": SECRET_FRAGMENT})
    except MultiTeacherAgentEvalHardeningError:
        redaction_failure_detected = True
    else:
        redaction_failure_detected = False
    if not redaction_failure_detected:
        raise MultiTeacherAgentEvalHardeningError("Secret-like payload was not rejected.")

    return {
        "missing_attribution": {
            "audit_status": missing_audit.get("status"),
            "artifact_status": missing_artifact.get("status"),
            "missing_tasks": missing_audit.get("missing_tasks"),
        },
        "forged_attribution": {
            "audit_status": forged_audit.get("status"),
            "unregistered_provider_ids": forged_audit.get("unregistered_provider_ids"),
        },
        "privacy_redaction_failure_detected": redaction_failure_detected,
        "external_judge_missing_runtime": {
            "optional_mode": "skipped",
            "required_mode": "non_zero_exit",
            "keys_owned_by": "user_or_platform_agent_environment",
        },
    }


def run_learning_without_teaching(registry: AgentRegistry) -> LearningState:
    workflow = LearningWorkflow(AgentRouter(registry))
    state = new_session(USER_ID, track="AI_PRODUCT")
    state = submit_reading(
        state,
        source_type="document",
        reference="demo://multiteacher-missing-attribution",
        title="Multi-Teacher Missing Attribution",
        text=PRIVATE_SOURCE,
    )
    state = workflow.run(state)
    if not state.quiz_items:
        raise MultiTeacherAgentEvalHardeningError("Negative case did not generate a quiz item.")
    state = submit_answers(
        state,
        [Answer(item_id=state.quiz_items[0].item_id, text=PRIVATE_ANSWER)],
    )
    return workflow.run(state)


def main() -> int:
    fake_state, fake_evidence = run_learning_loop(configure_registry())
    with MultiTeacherAgentServer() as endpoint:
        external_registry = configure_registry(endpoint=endpoint)
        external_state, external_evidence = run_learning_loop(external_registry)
        called_tasks = sorted(set(MultiTeacherAgentHandler.calls))

    fake_summary = assert_agent_report(
        "fake",
        fake_evidence,
        expected_provider_id="fake-deterministic",
        used_external_agent=False,
        used_fake_agent=True,
    )
    external_summary = assert_agent_report(
        "external",
        external_evidence,
        expected_provider_id=EXTERNAL_PROVIDER_ID,
        used_external_agent=True,
        used_fake_agent=False,
    )
    missing_http_calls = [task for task in REQUIRED_MULTI_TEACHER_TASKS if task not in called_tasks]
    if missing_http_calls:
        raise MultiTeacherAgentEvalHardeningError(
            f"HTTP Agent did not receive all multi-teacher tasks: {missing_http_calls}"
        )
    failure_modes = assert_failure_modes(
        external_state=external_state,
        external_registry=external_registry,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "version": __version__,
        "status": "pass",
        "contract": {
            "required_multi_teacher_tasks": REQUIRED_MULTI_TEACHER_TASKS,
            "task_layers": {
                "whole_topic": AgentCapability.TEACH_OVERVIEW.value,
                "term_explanation": AgentCapability.TEACH_GLOSSARY.value,
                "active_recall": AgentCapability.QUIZ_GENERATE.value,
                "feedback_loop": AgentCapability.ANSWER_GRADE.value,
                "transfer": AgentCapability.INSIGHT_SYNTHESIZE.value,
            },
            "required_attribution_fields": [
                "provider_id",
                "task_type",
                "status",
                "latency_ms",
                "confidence",
            ],
        },
        "fake_agent": fake_summary,
        "external_agent": {
            **external_summary,
            "http_agent_received_tasks": called_tasks,
        },
        "external_eval_boundaries": {
            "adapter_ids": [adapter.adapter_id for adapter in AGENT_EVAL_ADAPTERS],
            "real_model_or_judge_keys_stored_by_study_anything": False,
            "required_mode_owned_by_operator": True,
            "optional_mode_missing_runtime_can_skip": True,
        },
        "failure_modes": failure_modes,
        "privacy": {
            "raw_source_text_returned": False,
            "learner_answers_returned": False,
            "agent_endpoint_returned": False,
            "raw_agent_metadata_returned": False,
            "secrets_returned": False,
            "fake_session_id": fake_state.session_id,
            "external_session_id": external_state.session_id,
        },
    }
    assert_no_leaks(payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MultiTeacherAgentEvalHardeningError as exc:
        print(f"verify_multiteacher_agent_eval_hardening failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
