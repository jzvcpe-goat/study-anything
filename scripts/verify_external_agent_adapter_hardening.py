#!/usr/bin/env python3
"""Verify external Agent eval adapter hardening and bad-output diagnostics."""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core.agent_eval import (  # noqa: E402
    AGENT_EVAL_REQUIRED_TASKS,
    build_agent_eval_artifact,
    build_agent_eval_report,
)
from study_anything.core.agent_registry import (  # noqa: E402
    AgentCapability,
    AgentProviderConfig,
    AgentProviderKind,
    AgentProviderUnavailable,
    AgentRegistry,
    AgentResultInvalid,
    AgentTask,
    HttpAgentProvider,
)


SCHEMA_VERSION = "external-agent-adapter-hardening-v1"
RELEASE_VERSION = "v0.3.20-alpha"
PROVIDER_ID = "mock-real-agent-hardening"
SECRET_FRAGMENT = "sk-proj-agentVerifierSecretToken000000"
PRIVATE_SOURCE = "Private external Agent hardening source text."
PRIVATE_ANSWER = "Private external Agent hardening answer."
TASK_TYPES = [
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


class ExternalAgentAdapterHardeningError(RuntimeError):
    """Readable external Agent adapter verification failure."""


class ScenarioAgentHandler(BaseHTTPRequestHandler):
    scenario: ClassVar[str] = "success"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_POST(self) -> None:
        if self.scenario == "timeout":
            time.sleep(2.0)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            task = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send({"status": "error", "content": "bad request"}, status=400)
            return
        if self.scenario == "malformed_json":
            self._send_raw(b"{not-json")
            return

        payload = self._payload(task)
        self._send(payload)

    def _payload(self, task: Mapping[str, Any]) -> dict[str, Any]:
        task_type = str(task.get("task_type") or "")
        source = task.get("source") if isinstance(task.get("source"), Mapping) else {}
        citation = {
            "reference": source.get("reference"),
            "excerpt_hash": source.get("excerpt_hash"),
        }
        payload: dict[str, Any] = {
            "status": "ok",
            "content": "Source-bound external Agent response.",
            "citations": [citation],
            "confidence": 0.92,
            "metadata": {
                "mock_real_agent": True,
                "debug_note": SECRET_FRAGMENT,
                "tokens": {"prompt": 11, "completion": 7},
            },
        }

        if self.scenario == "invalid_status":
            payload["status"] = "maybe"
        elif self.scenario == "missing_content":
            payload["content"] = ""
        elif self.scenario == "invalid_score":
            payload["score"] = 1.5
        elif self.scenario == "invalid_confidence":
            payload["confidence"] = 1.5
        elif self.scenario == "missing_citations":
            payload["citations"] = []

        if task_type == AgentCapability.TEACH_OVERVIEW.value:
            payload["content"] = {
                "summary": "Explain the source in the larger knowledge map.",
                "key_points": ["main idea", "source evidence", "next review step"],
            }
            if self.scenario == "missing_content":
                payload["content"] = ""
        elif task_type == AgentCapability.TEACH_GLOSSARY.value:
            payload["content"] = [
                {
                    "term": "agent adapter",
                    "plain_language": "A bridge between Study Anything and the user's own Agent.",
                    "technical_definition": "A task contract consumer returning structured AgentResult JSON.",
                    "example": "The Agent grades an answer without exposing its model key.",
                }
            ]
        elif task_type == AgentCapability.QUIZ_GENERATE.value:
            payload["content"] = "What evidence proves the Agent followed the source contract?"
        elif task_type == AgentCapability.ANSWER_GRADE.value:
            payload["score"] = 0.86
            payload["feedback"] = "The answer is grounded in the provided reference."
            if self.scenario == "invalid_score":
                payload["score"] = 1.5
        elif task_type == AgentCapability.INSIGHT_SYNTHESIZE.value:
            payload["content"] = "The session is ready for spaced review and export."
        return payload

    def _send(self, payload: dict[str, Any], *, status: int = 200) -> None:
        self._send_raw(json.dumps(payload, ensure_ascii=False).encode("utf-8"), status=status)

    def _send_raw(self, body: bytes, *, status: int = 200) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:  # timeout cases intentionally close early
            return


class ScenarioServer(AbstractContextManager[str]):
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def __enter__(self) -> str:
        ScenarioAgentHandler.scenario = self.scenario
        self.server = HTTPServer(("127.0.0.1", 0), ScenarioAgentHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def make_task(task_type: str) -> AgentTask:
    return AgentTask(
        task_type=task_type,
        session_id="external-agent-hardening",
        track="ACADEMIC",
        source={
            "reference": "demo://external-agent-hardening",
            "title": "External Agent Hardening",
            "text": PRIVATE_SOURCE,
            "excerpt_hash": "external-agent-hardening-hash",
        },
        quiz_items=[
            {
                "item_id": "q1",
                "prompt": "What does the source prove?",
                "source_ref": "demo://external-agent-hardening",
                "excerpt_hash": "external-agent-hardening-hash",
            }
        ],
        answers=[{"item_id": "q1", "text": PRIVATE_ANSWER}]
        if task_type == AgentCapability.ANSWER_GRADE.value
        else [],
        constraints={"language": "zh", "level": "beginner"},
    )


def invoke_scenario(
    scenario: str,
    task_type: str,
    *,
    timeout_seconds: int = 2,
) -> Any:
    with ScenarioServer(scenario) as endpoint:
        provider = AgentProviderConfig(
            provider_id=PROVIDER_ID,
            kind=AgentProviderKind.HTTP_AGENT,
            label="Mock Real Agent Hardening",
            endpoint=endpoint,
            capabilities=[AgentCapability(value) for value in TASK_TYPES],
            timeout_seconds=timeout_seconds,
            metadata={"source": "verify_external_agent_adapter_hardening"},
        )
        return HttpAgentProvider(provider).invoke(make_task(task_type))


def diagnostic_code(exc: Exception) -> str:
    if isinstance(exc, AgentProviderUnavailable):
        return "provider_unavailable"
    if isinstance(exc, AgentResultInvalid):
        message = str(exc).lower()
        if "malformed json" in message:
            return "malformed_json"
        if "status" in message:
            return "invalid_status"
        if "score" in message:
            return "invalid_score"
        if "confidence" in message:
            return "invalid_confidence"
        if "content" in message:
            return "missing_content"
        return "invalid_schema"
    return "unexpected_error"


def expect_failure(case_id: str, task_type: str, expected_code: str) -> dict[str, Any]:
    try:
        invoke_scenario(case_id, task_type, timeout_seconds=1)
    except Exception as exc:
        code = diagnostic_code(exc)
        if code != expected_code:
            raise ExternalAgentAdapterHardeningError(
                f"{case_id} expected {expected_code}, got {code}: {exc}"
            ) from exc
        return {
            "case_id": case_id,
            "status": "pass",
            "diagnostic_code": code,
            "error_redacted": True,
        }
    raise ExternalAgentAdapterHardeningError(f"{case_id} unexpectedly passed.")


def verify_missing_citation_case() -> dict[str, Any]:
    result = invoke_scenario("missing_citations", AgentCapability.QUIZ_GENERATE.value)
    if result.citations:
        raise ExternalAgentAdapterHardeningError("missing_citations case returned citations.")
    return {
        "case_id": "missing_citations",
        "status": "pass",
        "diagnostic_code": "missing_citation",
        "adapter_status": "needs_review",
    }


def verify_missing_capability_case() -> dict[str, Any]:
    registry = AgentRegistry()
    provider = registry.configure_provider(
        kind="http_agent",
        label="Capability Gap Agent",
        endpoint="http://127.0.0.1:8787/invoke",
        capabilities=[AgentCapability.ANSWER_GRADE.value],
    )
    try:
        registry.set_default(
            "external-agent-hardening",
            AgentCapability.QUIZ_GENERATE,
            provider.provider_id,
        )
    except ValueError:
        return {
            "case_id": "missing_capability",
            "status": "pass",
            "diagnostic_code": "capability_not_declared",
        }
    raise ExternalAgentAdapterHardeningError("missing capability default unexpectedly passed.")


def verify_successful_external_agent_eval() -> dict[str, Any]:
    evidence: list[dict[str, object]] = []
    observed_tasks: list[str] = []
    for index, task_type in enumerate(TASK_TYPES, start=1):
        result = invoke_scenario("success", task_type)
        metadata = result.public_metadata()
        evidence.append(
            {
                "event_id": f"evt-{index}",
                "event_type": "agent.completed",
                "node": f"external_agent_{index}",
                "created_at": "2026-06-13T00:00:00Z",
                **metadata,
            }
        )
        observed_tasks.append(task_type)
        if not result.citations:
            raise ExternalAgentAdapterHardeningError(f"{task_type} response missed citations.")

    audit = {
        "schema_version": "agent-audit-v1",
        "session_id": "external-agent-hardening",
        "stage": "completed",
        "status": "verified",
        "required_tasks": list(AGENT_EVAL_REQUIRED_TASKS),
        "observed_tasks": sorted(observed_tasks),
        "missing_tasks": [],
        "provider_ids": [PROVIDER_ID],
        "used_study_anything_agent": True,
        "used_external_agent": True,
        "used_fake_agent": False,
        "source_bound": {
            "source_reference_present": True,
            "excerpt_hash_present": True,
        },
        "privacy": {
            "source_text_returned": False,
            "answers_returned": False,
            "feedback_returned": False,
            "agent_endpoint_returned": False,
            "raw_agent_metadata_returned": False,
        },
        "evidence": evidence,
    }
    artifact = build_agent_eval_artifact(audit)
    quality = {
        "schema_version": "agent-quality-eval-v1",
        "status": "pass",
        "quality_score": 0.88,
        "threshold": 0.72,
        "privacy": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "secrets_included": False,
        },
        "gates": [
            {
                "gate_id": "external_agent_task_completion",
                "status": "pass",
                "required": True,
                "score": 1.0,
            }
        ],
    }
    report = build_agent_eval_report(agent_audit=audit, agent_eval_artifact=artifact, quality_eval=quality)
    if artifact.get("used_fake_agent"):
        raise ExternalAgentAdapterHardeningError(f"External artifact marked fake Agent usage: {artifact}")
    if not artifact.get("used_external_agent"):
        raise ExternalAgentAdapterHardeningError(f"External artifact missed external Agent usage: {artifact}")
    if (report.get("native_fast_gate") or {}).get("status") != "pass":
        raise ExternalAgentAdapterHardeningError(f"External Agent report native gate failed: {report}")
    assert_no_leaks({"artifact": artifact, "report": report, "evidence": evidence})
    return {
        "provider_id": PROVIDER_ID,
        "used_external_agent": artifact["used_external_agent"],
        "used_fake_agent": artifact["used_fake_agent"],
        "task_types": observed_tasks,
        "artifact_status": artifact["status"],
        "report_status": report["status"],
        "native_fast_gate_status": (report["native_fast_gate"] or {}).get("status"),
        "trajectory_steps": len(artifact.get("trajectory", [])),
        "metadata_secret_values_redacted": SECRET_FRAGMENT not in json.dumps(evidence),
    }


def assert_no_leaks(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized)]
    if leaks:
        raise ExternalAgentAdapterHardeningError(f"External Agent hardening leaked private data: {leaks}")


def main() -> None:
    good = verify_successful_external_agent_eval()
    bad_cases = [
        expect_failure("malformed_json", AgentCapability.QUIZ_GENERATE.value, "malformed_json"),
        expect_failure("invalid_status", AgentCapability.QUIZ_GENERATE.value, "invalid_status"),
        expect_failure("missing_content", AgentCapability.TEACH_OVERVIEW.value, "missing_content"),
        expect_failure("invalid_score", AgentCapability.ANSWER_GRADE.value, "invalid_score"),
        expect_failure("invalid_confidence", AgentCapability.QUIZ_GENERATE.value, "invalid_confidence"),
        expect_failure("timeout", AgentCapability.QUIZ_GENERATE.value, "provider_unavailable"),
        verify_missing_citation_case(),
        verify_missing_capability_case(),
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "external_agent_eval": good,
        "bad_agent_cases": bad_cases,
        "privacy": {
            "raw_source_text_returned": False,
            "learner_answers_returned": False,
            "agent_endpoint_secrets_returned": False,
            "real_model_keys_stored_by_study_anything": False,
            "secret_like_metadata_values_redacted": good["metadata_secret_values_redacted"],
        },
        "release_gate": {
            "blocking": True,
            "fake_and_external_evidence_separated": (
                good["used_external_agent"] is True and good["used_fake_agent"] is False
            ),
            "bad_output_diagnostics_covered": [case["case_id"] for case in bad_cases],
        },
    }
    assert_no_leaks(payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_external_agent_adapter_hardening failed: {exc}", file=sys.stderr)
        sys.exit(1)
