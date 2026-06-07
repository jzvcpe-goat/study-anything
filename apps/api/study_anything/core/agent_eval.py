"""Redacted Agent eval artifacts for external evaluation tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentEvalAdapter:
    adapter_id: str
    project: str
    repo: str
    license: str
    stars: int
    role: str
    first_use: str

    def public_dict(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "project": self.project,
            "repo": self.repo,
            "license": self.license,
            "github_stars_as_of": "2026-06-07",
            "stars": self.stars,
            "role": self.role,
            "first_use": self.first_use,
        }


AGENT_EVAL_ADAPTERS = [
    AgentEvalAdapter(
        adapter_id="promptfoo",
        project="Promptfoo",
        repo="https://github.com/promptfoo/promptfoo",
        license="MIT",
        stars=21980,
        role="CLI/CI regression, HTTP contract checks, red-team style assertions.",
        first_use="Run API/Skill smoke cases against local or published Study Anything endpoints.",
    ),
    AgentEvalAdapter(
        adapter_id="deepeval",
        project="DeepEval",
        repo="https://github.com/confident-ai/deepeval",
        license="Apache-2.0",
        stars=15970,
        role="Python agent-quality evals with task-completion and component-level metrics.",
        first_use="Score completed learning sessions after invocation coverage is proven.",
    ),
    AgentEvalAdapter(
        adapter_id="langchain-agentevals",
        project="LangChain AgentEvals",
        repo="https://github.com/langchain-ai/agentevals",
        license="MIT",
        stars=609,
        role="Trajectory matching for ordered Agent/tool steps.",
        first_use="Compare Study Anything workflow events with expected learning-node trajectories.",
    ),
    AgentEvalAdapter(
        adapter_id="ragas",
        project="Ragas",
        repo="https://github.com/vibrantlabsai/ragas",
        license="Apache-2.0",
        stars=14272,
        role="Citation, grounding, answer relevance, and retrieval-quality metrics.",
        first_use="Evaluate source-bound answers once enrichment/retrieval datasets are exported.",
    ),
]


def build_agent_eval_artifact(agent_audit: Mapping[str, Any]) -> dict[str, object]:
    """Build a tool-neutral, redacted eval artifact from an Agent audit report.

    The artifact is intentionally not an LLM judge. It is the stable bridge
    between Study Anything's internal invocation audit and mature external eval
    projects such as Promptfoo, DeepEval, LangChain AgentEvals, and Ragas.
    """

    evidence = [item for item in agent_audit.get("evidence", []) if isinstance(item, Mapping)]
    observed_tasks = _string_list(agent_audit.get("observed_tasks"))
    missing_tasks = _string_list(agent_audit.get("missing_tasks"))
    required_tasks = _string_list(agent_audit.get("required_tasks"))
    privacy = agent_audit.get("privacy", {})
    source_bound = agent_audit.get("source_bound", {})

    gates = [
        _gate(
            "agent_invocation_coverage",
            pass_when=agent_audit.get("status") == "verified" and not missing_tasks,
            required=True,
            summary="Required learning tasks were handled by a Study Anything Agent provider.",
        ),
        _gate(
            "source_reference_present",
            pass_when=_mapping_bool(source_bound, "source_reference_present"),
            required=True,
            summary="The learning session includes a source reference for grounding.",
        ),
        _gate(
            "excerpt_hash_present",
            pass_when=_mapping_bool(source_bound, "excerpt_hash_present"),
            required=True,
            summary="The learning session includes a source excerpt hash instead of raw source text.",
        ),
        _gate(
            "privacy_redaction",
            pass_when=_privacy_redaction_passed(privacy),
            required=True,
            summary="Audit and eval artifacts omit source text, answers, feedback, endpoints, and raw metadata.",
        ),
        _gate(
            "external_agent_used",
            pass_when=bool(agent_audit.get("used_external_agent")),
            required=False,
            summary="A user-owned Agent handled the session rather than the deterministic demo Agent.",
        ),
    ]

    required_gate_failed = any(gate["required"] and gate["status"] != "pass" for gate in gates)
    return {
        "schema_version": "agent-eval-artifact-v1",
        "session_id": agent_audit.get("session_id"),
        "stage": agent_audit.get("stage"),
        "status": "ready_for_external_eval" if not required_gate_failed else "blocked",
        "source_schema": agent_audit.get("schema_version"),
        "invocation_audit_status": agent_audit.get("status"),
        "observed_tasks": observed_tasks,
        "required_tasks": required_tasks,
        "missing_tasks": missing_tasks,
        "used_external_agent": bool(agent_audit.get("used_external_agent")),
        "used_fake_agent": bool(agent_audit.get("used_fake_agent")),
        "native_gates": gates,
        "trajectory": _trajectory(evidence),
        "adapter_strategy": [adapter.public_dict() for adapter in AGENT_EVAL_ADAPTERS],
        "external_eval_layers": [
            "contract_regression",
            "agent_task_completion",
            "trajectory_match",
            "source_grounding",
            "citation_quality",
        ],
        "privacy": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "agent_endpoints_included": False,
            "raw_agent_metadata_included": False,
        },
        "promptfoo": {
            "config": "evals/promptfoo/agent-eval-artifact.yaml",
            "recommended_gate": "all required native_gates pass and schema_version matches.",
        },
        "deepeval": {
            "recommended_metrics": ["TaskCompletionMetric", "GEval", "AnswerRelevancy", "Faithfulness"],
            "requires_judge_model": True,
        },
        "langchain_agentevals": {
            "recommended_evaluator": "create_trajectory_match_evaluator",
            "trajectory_source": "trajectory",
        },
        "ragas": {
            "recommended_metrics": ["faithfulness", "answer_relevancy", "context_relevance"],
            "requires_retrieval_or_enrichment_dataset": True,
        },
    }


def _gate(gate_id: str, *, pass_when: bool, required: bool, summary: str) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "status": "pass" if pass_when else "fail",
        "required": required,
        "summary": summary,
    }


def _trajectory(evidence: list[Mapping[str, Any]]) -> list[dict[str, object]]:
    trajectory: list[dict[str, object]] = []
    for index, item in enumerate(evidence, start=1):
        trajectory.append(
            {
                "step": index,
                "node": item.get("node"),
                "task_type": item.get("task_type"),
                "provider_id": item.get("provider_id"),
                "provider_kind": item.get("provider_kind"),
                "status": item.get("status"),
                "latency_ms": item.get("latency_ms"),
                "confidence": item.get("confidence"),
            }
        )
    return trajectory


def _privacy_redaction_passed(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    forbidden_flags = [
        "source_text_returned",
        "answers_returned",
        "feedback_returned",
        "agent_endpoint_returned",
        "raw_agent_metadata_returned",
    ]
    return not any(value.get(flag) for flag in forbidden_flags)


def _mapping_bool(value: object, key: str) -> bool:
    return bool(value.get(key)) if isinstance(value, Mapping) else False


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []
