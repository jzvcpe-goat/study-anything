"""Agent invocation audit evidence derived from session events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .workflow import LearningState


REQUIRED_AGENT_TASKS = [
    "teach.overview",
    "teach.glossary",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
]


@dataclass(frozen=True)
class AgentProviderSummary:
    provider_id: str
    kind: str | None
    label: str | None
    capabilities: list[str]

    def public_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "kind": self.kind,
            "label": self.label,
            "capabilities": self.capabilities,
        }


def build_agent_audit(
    state: LearningState,
    *,
    agent_status: Mapping[str, Any] | None = None,
    deprecated_alias: bool = False,
) -> dict[str, object]:
    """Build a redacted proof report for agent usage in a learning session.

    This is an invocation audit, not a quality evaluation framework. It derives
    from workflow events instead of raw task payloads, proving which provider
    handled each learning step without returning source prose, answers,
    feedback bodies, endpoints, or secrets.
    """

    provider_map = _provider_map(agent_status)
    evidence: list[dict[str, object]] = []
    observed_tasks: set[str] = set()
    provider_ids: set[str] = set()
    unregistered_provider_ids: set[str] = set()
    enforce_provider_registration = agent_status is not None

    for event in state.events:
        for metadata in _agent_metadata_items(event.payload):
            provider_id = _string(metadata.get("provider_id"))
            task_type = _string(metadata.get("task_type"))
            if not provider_id or not task_type:
                continue
            observed_tasks.add(task_type)
            provider_ids.add(provider_id)
            provider = provider_map.get(provider_id)
            provider_registered = provider is not None or (
                provider_id == "fake-deterministic" and not enforce_provider_registration
            )
            if enforce_provider_registration and not provider_registered:
                unregistered_provider_ids.add(provider_id)
            evidence.append(
                {
                    "event_id": event.event_id,
                    "event_type": event.type,
                    "node": event.node,
                    "created_at": event.created_at,
                    "provider_id": provider_id,
                    "provider_kind": provider.kind if provider else _infer_provider_kind(provider_id),
                    "provider_label": provider.label if provider else None,
                    "task_type": task_type,
                    "status": _string(metadata.get("status")),
                    "latency_ms": _int_or_none(metadata.get("latency_ms")),
                    "confidence": _float_or_none(metadata.get("confidence")),
                    "provider_registered": provider_registered,
                }
            )

    missing_tasks = [task for task in REQUIRED_AGENT_TASKS if task not in observed_tasks]
    used_fake_agent = "fake-deterministic" in provider_ids
    used_external_agent = any(provider_id != "fake-deterministic" for provider_id in provider_ids)
    if not evidence:
        status = "no_agent_evidence"
    elif unregistered_provider_ids:
        status = "invalid_provider_evidence"
    elif missing_tasks:
        status = "partial"
    else:
        status = "verified"

    providers = [
        (provider_map.get(provider_id) or AgentProviderSummary(
            provider_id=provider_id,
            kind=_infer_provider_kind(provider_id),
            label=None,
            capabilities=[],
        )).public_dict()
        for provider_id in sorted(provider_ids)
    ]

    values: dict[str, object] = {
        "schema_version": "agent-audit-v1",
        "session_id": state.session_id,
        "stage": state.stage,
        "status": status,
        "required_tasks": REQUIRED_AGENT_TASKS,
        "observed_tasks": sorted(observed_tasks),
        "missing_tasks": missing_tasks,
        "unregistered_provider_ids": sorted(unregistered_provider_ids),
        "provider_ids": sorted(provider_ids),
        "providers": providers,
        "used_study_anything_agent": bool(evidence),
        "used_external_agent": used_external_agent,
        "used_fake_agent": used_fake_agent,
        "quality_eval": {
            "included": False,
            "planned_adapters": ["deepeval", "langchain-agentevals", "ragas"],
        },
        "source_bound": {
            "source_reference_present": bool(state.source and state.source.reference),
            "excerpt_hash_present": bool(state.source and state.source.excerpt_hash),
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
    if deprecated_alias:
        values["schema_version"] = "agent-eval-v1"
        values["deprecated"] = True
        values["replacement"] = "/v1/sessions/{session_id}/agent-audit"
        values["note"] = "This endpoint is an invocation audit, not a quality eval framework."
    return values


def _agent_metadata_items(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    agent = payload.get("agent")
    if isinstance(agent, Mapping):
        yield agent
    agents = payload.get("agents")
    if isinstance(agents, list):
        for item in agents:
            if isinstance(item, Mapping):
                yield item


def _provider_map(agent_status: Mapping[str, Any] | None) -> dict[str, AgentProviderSummary]:
    providers: dict[str, AgentProviderSummary] = {}
    if not isinstance(agent_status, Mapping):
        return providers
    for item in agent_status.get("providers", []):
        if not isinstance(item, Mapping):
            continue
        provider_id = _string(item.get("provider_id"))
        if not provider_id:
            continue
        capabilities = item.get("capabilities", [])
        providers[provider_id] = AgentProviderSummary(
            provider_id=provider_id,
            kind=_string(item.get("kind")) or None,
            label=_string(item.get("label")) or None,
            capabilities=[str(value) for value in capabilities] if isinstance(capabilities, list) else [],
        )
    return providers


def _infer_provider_kind(provider_id: str) -> str | None:
    if provider_id == "fake-deterministic":
        return "fake_agent"
    return None


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _float_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None
