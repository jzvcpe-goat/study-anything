"""Redacted quality gates for retrieval and context-package handoff."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .learning_context import validate_learning_context_package
from .retrieval import RetrievalSearchResultSet


RETRIEVAL_QUALITY_CASES = [
    {
        "case_id": "retrieval_available",
        "category": "runtime",
        "minimum": "retrieval adapter is enabled and reports healthy before scoring context",
    },
    {
        "case_id": "result_count",
        "category": "coverage",
        "minimum": "at least one result is returned for the query",
    },
    {
        "case_id": "source_binding",
        "category": "grounding",
        "minimum": "each result includes document id, reference, source type, and excerpt hash",
    },
    {
        "case_id": "snippet_minimality",
        "category": "privacy",
        "minimum": "retrieval output exposes only short snippets and no secret-like text",
    },
    {
        "case_id": "query_relevance",
        "category": "retrieval_quality",
        "minimum": "top result score is positive and the average score is non-zero",
    },
    {
        "case_id": "context_package_valid",
        "category": "handoff_contract",
        "minimum": "retrieval results can be converted into learning-context-package-v1",
    },
]


@dataclass(frozen=True)
class RetrievalQualityInput:
    """Input bundle used by the API and external eval adapters."""

    session_id: str
    query: str
    retrieval_status: Mapping[str, Any]
    result_set: RetrievalSearchResultSet
    context_package: Mapping[str, Any] | None = None


def build_retrieval_quality_eval(values: RetrievalQualityInput) -> dict[str, object]:
    """Build a redacted retrieval quality report.

    This report is deliberately deterministic. It is meant to be consumed by
    Ragas, DeepEval, or other external suites later, while the default release
    gate stays local-first and does not require a judge model or package install.
    """

    result_public = values.result_set.public_dict()
    context_package = values.context_package
    context_error_code = None
    if context_package is None:
        try:
            context_package = values.result_set.context_package(
                title=f"Retrieval eval: {values.query}",
                reference=f"retrieval://{values.session_id}",
            )
        except Exception:  # pragma: no cover - exercised through gate status
            context_error_code = "context_package_build_failed"

    context_valid = False
    if context_package is not None:
        try:
            validate_learning_context_package(context_package)
            context_valid = True
        except Exception:
            context_error_code = "context_package_validation_failed"

    results = values.result_set.results
    top_score = max((result.score for result in results), default=0.0)
    average_score = (
        round(sum(result.score for result in results) / len(results), 6) if results else 0.0
    )
    snippet_lengths = [len(result.snippet or "") for result in results]
    secret_like_results = [
        result.document_id
        for result in results
        if _contains_secret_like_text(result.snippet)
    ]
    source_binding_missing = [
        result.document_id or f"result-{index}"
        for index, result in enumerate(results, start=1)
        if not (result.document_id and result.session_id and result.source_type and result.reference and result.excerpt_hash)
    ]
    gates = [
        _gate(
            "retrieval_available",
            pass_when=values.retrieval_status.get("status") == "healthy",
            required=True,
            score=1.0,
            category="runtime",
            metadata={
                "adapter_status": values.retrieval_status.get("status"),
                "index_name": values.retrieval_status.get("index_name"),
            },
        ),
        _gate(
            "result_count",
            pass_when=len(results) > 0 and result_public.get("status") == "ready",
            required=True,
            score=0.85,
            category="coverage",
            metadata={"result_count": len(results), "search_status": result_public.get("status")},
        ),
        _gate(
            "source_binding",
            pass_when=not source_binding_missing and bool(results),
            required=True,
            score=1.0,
            category="grounding",
            metadata={"missing": source_binding_missing[:5]},
        ),
        _gate(
            "snippet_minimality",
            pass_when=bool(results)
            and all(length <= 480 for length in snippet_lengths)
            and not secret_like_results,
            required=True,
            score=0.9,
            category="privacy",
            metadata={
                "max_snippet_chars": max(snippet_lengths, default=0),
                "secret_like_result_count": len(secret_like_results),
            },
        ),
        _gate(
            "query_relevance",
            pass_when=top_score > 0 and average_score > 0,
            required=True,
            score=0.8,
            category="retrieval_quality",
            metadata={"top_score": top_score, "average_score": average_score},
        ),
        _gate(
            "context_package_valid",
            pass_when=context_valid,
            required=True,
            score=0.85,
            category="handoff_contract",
            metadata={"error_code": context_error_code},
        ),
    ]
    failed_required = [
        gate for gate in gates if gate["required"] and gate["status"] != "pass"
    ]
    score = round(sum(float(gate["score"]) for gate in gates) / len(gates), 3) if gates else 0.0
    return {
        "schema_version": "retrieval-quality-eval-v1",
        "session_id": values.session_id,
        "query": values.query,
        "status": "pass" if not failed_required and score >= 0.72 else "needs_review",
        "quality_score": score,
        "threshold": 0.72,
        "fixed_cases": [dict(item) for item in RETRIEVAL_QUALITY_CASES],
        "gates": gates,
        "retrieval": {
            "search_schema": result_public.get("schema_version"),
            "search_status": result_public.get("status"),
            "result_count": len(results),
            "top_score": top_score,
            "average_score": average_score,
            "result_summaries": [
                {
                    "document_id": result.document_id,
                    "source_type": result.source_type,
                    "reference": result.reference,
                    "excerpt_hash": result.excerpt_hash,
                    "locator": result.locator,
                    "snippet_chars": len(result.snippet or ""),
                    "score": result.score,
                }
                for result in results
            ],
        },
        "external_eval": {
            "framework_paths": [
                {
                    "adapter_id": "ragas",
                    "mode": "context_precision_recall_grounding",
                    "claim": "Can consume this redacted report plus user-owned source fixtures without Study Anything storing judge keys.",
                },
                {
                    "adapter_id": "deepeval",
                    "mode": "custom_non_llm_metric",
                    "claim": "Can gate the deterministic retrieval report before judge-model scoring.",
                },
                {
                    "adapter_id": "promptfoo",
                    "mode": "http_contract_regression",
                    "claim": "Can assert retrieval eval schema and privacy invariants.",
                },
            ],
            "native_runner": "scripts/run_external_agent_evals.py --tool retrieval",
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "agent_endpoints_included": False,
            "agent_secrets_allowed": False,
            "full_source_text_returned": False,
            "result_snippets_included": False,
            "canonical_source": "session_state",
        },
        "limitations": [
            "This deterministic report checks context handoff quality, not semantic pedagogy by itself.",
            "Ragas or judge-model scoring should run outside Study Anything with user-owned evaluator credentials.",
        ],
    }


def retrieval_quality_case_export() -> dict[str, object]:
    return {
        "schema_version": "study-anything-retrieval-quality-cases-v1",
        "cases": [dict(item) for item in RETRIEVAL_QUALITY_CASES],
    }


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


def _contains_secret_like_text(text: str) -> bool:
    return bool(
        re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", text)
        or re.search(
            r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}",
            text,
        )
    )
