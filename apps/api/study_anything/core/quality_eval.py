"""Deterministic quality gates for Study Anything learning sessions."""

from __future__ import annotations

from typing import Any, Mapping

from .workflow import LearningState


FIXED_QUALITY_CASES = [
    {
        "case_id": "overview_layer",
        "category": "whole_topic_teaching",
        "minimum": "overview layer exists and was agent generated",
    },
    {
        "case_id": "glossary_layer",
        "category": "term_explanation",
        "minimum": "glossary layer exists and contains structured terms or explanations",
    },
    {
        "case_id": "quiz_generation",
        "category": "active_recall",
        "minimum": "at least one source-bound quiz item exists",
    },
    {
        "case_id": "answer_grading",
        "category": "feedback_loop",
        "minimum": "grading includes a score between 0 and 1",
    },
    {
        "case_id": "synthesis",
        "category": "transfer",
        "minimum": "session includes a reusable insight after grading",
    },
    {
        "case_id": "source_binding",
        "category": "grounding",
        "minimum": "source reference and excerpt hash are present",
    },
]


def build_agent_quality_eval(
    state: LearningState,
    *,
    agent_audit: Mapping[str, Any],
    agent_eval_artifact: Mapping[str, Any],
) -> dict[str, object]:
    """Build a redacted quality-eval report from session state and audit evidence.

    This is not a judge-model score. It is a deterministic first quality gate that
    external frameworks such as DeepEval can consume before LLM-as-judge suites are
    introduced.
    """

    gates = _quality_gates(state, agent_audit=agent_audit, agent_eval_artifact=agent_eval_artifact)
    required_failed = [gate for gate in gates if gate["required"] and gate["status"] != "pass"]
    score = round(sum(float(gate["score"]) for gate in gates) / len(gates), 3) if gates else 0.0
    status = "pass" if not required_failed and score >= 0.72 else "needs_review"
    return {
        "schema_version": "agent-quality-eval-v1",
        "session_id": state.session_id,
        "status": status,
        "quality_score": score,
        "threshold": 0.72,
        "fixed_cases": FIXED_QUALITY_CASES,
        "gates": gates,
        "external_eval": {
            "invocation_proof": {
                "status": agent_eval_artifact.get("status"),
                "used_external_agent": bool(agent_eval_artifact.get("used_external_agent")),
                "used_fake_agent": bool(agent_eval_artifact.get("used_fake_agent")),
            },
            "contract_schema": {
                "artifact_schema": agent_eval_artifact.get("schema_version"),
                "audit_schema": agent_audit.get("schema_version"),
                "required_native_gates_passed": not _failed_required_native_gates(
                    agent_eval_artifact
                ),
            },
            "framework_paths": [
                {
                    "adapter_id": "deepeval",
                    "path": "evals/deepeval/study_anything_quality_eval.py",
                    "mode": "custom_non_llm_metric",
                    "claim": "Consumes this quality report inside DeepEval's metric interface.",
                },
                {
                    "adapter_id": "promptfoo",
                    "path": "evals/promptfoo/agent-eval-artifact.yaml",
                    "mode": "http_contract_regression",
                    "claim": "Proves invocation and contract gates.",
                },
            ],
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "agent_endpoints_included": False,
            "raw_agent_metadata_included": False,
        },
        "limitations": [
            "This deterministic report is a minimum quality gate, not a full pedagogy benchmark.",
            "LLM-as-judge suites may be layered on top using user-owned evaluator credentials.",
        ],
    }


def _quality_gates(
    state: LearningState,
    *,
    agent_audit: Mapping[str, Any],
    agent_eval_artifact: Mapping[str, Any],
) -> list[dict[str, object]]:
    layers = {
        str(item.get("layer")): item for item in state.teaching_layers if isinstance(item, dict)
    }
    source = state.source
    return [
        _gate(
            "agent_invocation_proof",
            pass_when=agent_audit.get("status") == "verified"
            and agent_eval_artifact.get("status") == "ready_for_external_eval",
            required=True,
            score=1.0,
            category="invocation",
        ),
        _gate(
            "overview_quality",
            pass_when=_layer_has_content(layers.get("overview")),
            required=True,
            score=0.85,
            category="whole_topic_teaching",
        ),
        _gate(
            "glossary_quality",
            pass_when=_layer_has_content(layers.get("glossary")),
            required=True,
            score=0.85,
            category="term_explanation",
        ),
        _gate(
            "quiz_quality",
            pass_when=bool(state.quiz_items)
            and all(
                item.source_ref and item.excerpt_hash and item.rubric
                for item in state.quiz_items
            ),
            required=True,
            score=0.9,
            category="active_recall",
        ),
        _gate(
            "grading_quality",
            pass_when=bool(state.grading_results)
            and all(0.0 <= result.score <= 1.0 for result in state.grading_results),
            required=True,
            score=0.9,
            category="feedback_loop",
        ),
        _gate(
            "synthesis_quality",
            pass_when=bool(state.insights),
            required=True,
            score=0.8,
            category="transfer",
        ),
        _gate(
            "source_binding",
            pass_when=bool(source and source.reference and source.excerpt_hash),
            required=True,
            score=1.0,
            category="grounding",
        ),
        _gate(
            "enrichment_ready",
            pass_when=bool(state.enrichment_items),
            required=False,
            score=0.75,
            category="learning_enrichment",
            metadata={"item_count": len(state.enrichment_items)},
        ),
        _gate(
            "obsidian_ready",
            pass_when=state.stage == "completed" and bool(state.scribe_log or state.insights),
            required=False,
            score=0.75,
            category="knowledge_deposit",
        ),
    ]


def _gate(
    gate_id: str,
    *,
    pass_when: bool,
    required: bool,
    score: float,
    category: str,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "category": category,
        "status": "pass" if pass_when else "fail",
        "required": required,
        "score": score if pass_when else 0.0,
        "metadata": dict(metadata or {}),
    }


def _layer_has_content(layer: object) -> bool:
    if not isinstance(layer, Mapping):
        return False
    content = layer.get("content")
    if isinstance(content, (list, tuple, dict)):
        return bool(content)
    return bool(str(content or "").strip())


def _failed_required_native_gates(artifact: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        gate
        for gate in artifact.get("native_gates", [])
        if isinstance(gate, Mapping) and gate.get("required") and gate.get("status") != "pass"
    ]


def quality_eval_case_export() -> dict[str, object]:
    return {
        "schema_version": "study-anything-quality-cases-v1",
        "cases": [dict(item) for item in FIXED_QUALITY_CASES],
    }
