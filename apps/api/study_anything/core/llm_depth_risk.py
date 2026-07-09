"""Metadata-only LLM depth risk evidence.

This module upgrades the path-level Cognitive Loop risk model with model-quality
evidence while preserving the local-first boundary: no model calls, no stored
model keys, no raw source text, no raw learner answers, and no external network
requirement.
"""

from __future__ import annotations

from html import escape
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


INPUT_SCHEMA_VERSION = "llm-depth-risk-input-v1"
REPORT_SCHEMA_VERSION = "llm-depth-risk-engine-report-v1"
PROMPT_EVIDENCE_SCHEMA_VERSION = "prompt-evidence-v1"
HALLUCINATION_EVIDENCE_SCHEMA_VERSION = "hallucination-evidence-v1"
RAG_EVIDENCE_SCHEMA_VERSION = "rag-evidence-v1"
CONTEXT_BUDGET_EVIDENCE_SCHEMA_VERSION = "context-budget-evidence-v1"
COST_QUALITY_EVIDENCE_SCHEMA_VERSION = "cost-quality-evidence-v1"
GATE_SCHEMA_VERSION = "llm-depth-risk-gate-v1"

RELEASE_VERSION = "v0.3.31-alpha"

SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"https?://[^\s?]+[?&](?:X-Amz-Signature|signature|sig|token)="),
    re.compile(r"/Users/[^\s\"']+"),
)

FORBIDDEN_KEYS = {
    "api_key",
    "apikey",
    "answer_text",
    "bearer_token",
    "cookie",
    "credential",
    "credentials",
    "learner_answer",
    "model_api_key",
    "password",
    "raw_answer",
    "raw_context",
    "raw_diff",
    "raw_prompt",
    "raw_source",
    "raw_source_text",
    "secret",
    "signed_url",
    "source_text",
    "token",
    "user_owned_agent_credentials",
}

FORBIDDEN_TEXT = (
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "AGENT_LLM_API_KEY=",
    "raw private source text",
    "private answer:",
    "learner answer:",
    "raw source text:",
    "raw prompt:",
)


class LLMDepthRiskError(ValueError):
    """Raised when LLM depth evidence is unsafe or malformed."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LLMDepthRiskError(f"Expected JSON object: {path}")
    return payload


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(*parts: object) -> str:
    return sha256_text(":".join(str(part) for part in parts))[:16]


def _normal_key(value: object) -> str:
    return str(value).strip().lower().replace("-", "_")


def assert_metadata_only(value: Any, *, label: str = "llm-depth-risk") -> None:
    """Reject raw private content, secrets, local paths, and unsafe keys."""

    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                normalized = _normal_key(key)
                if normalized in FORBIDDEN_KEYS and child not in (False, None, "", []):
                    raise LLMDepthRiskError(f"{label}:{path}.{key} uses forbidden field")
                walk(child, f"{path}.{key}")
            return
        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(node, str):
            lowered = node.lower()
            forbidden = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
            forbidden.extend(pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(node))
            if forbidden:
                raise LLMDepthRiskError(f"{label}:{path} contains private-looking data: {forbidden}")

    walk(value, "$")


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _gate(gate_id: str, passed: bool, threshold: float | str, observed: float | str) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "pass" if passed else "fail",
        "threshold": threshold,
        "observed": observed,
    }


def build_prompt_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    prompts = []
    gates = []
    for item in _list(payload.get("prompts")):
        prompt = _mapping(item)
        prompt_id = str(prompt.get("prompt_id") or "prompt")
        current_template = str(prompt.get("current_template") or "")
        previous_template = str(prompt.get("previous_template") or "")
        variables = [str(value) for value in _list(prompt.get("variables"))]
        injection_tests = [_mapping(value) for value in _list(prompt.get("injection_tests"))]
        injection_passed = sum(1 for value in injection_tests if value.get("status") == "pass")
        prompt_gates = [
            _gate("version_present", bool(prompt.get("version")), "non-empty", str(prompt.get("version") or "")),
            _gate("template_non_empty", bool(current_template.strip()), "non-empty", str(bool(current_template.strip()))),
            _gate("variables_declared", bool(variables), ">=1", len(variables)),
            _gate(
                "injection_tests_pass",
                bool(injection_tests) and injection_passed == len(injection_tests),
                "all",
                f"{injection_passed}/{len(injection_tests)}",
            ),
        ]
        prompts.append(
            {
                "prompt_id": prompt_id,
                "version": str(prompt.get("version") or "unversioned"),
                "role": str(prompt.get("role") or "unknown"),
                "current_template_sha256": sha256_text(current_template),
                "previous_template_sha256": sha256_text(previous_template) if previous_template else None,
                "diff": {
                    "changed": bool(previous_template and previous_template != current_template),
                    "char_delta": len(current_template) - len(previous_template),
                    "line_delta": len(current_template.splitlines()) - len(previous_template.splitlines()),
                    "raw_prompt_included": False,
                },
                "lint": {
                    "variable_count": len(variables),
                    "variables": variables,
                    "forbidden_secret_patterns_found": 0,
                    "json_output_required": bool(prompt.get("json_output_required", True)),
                    "source_grounding_required": bool(prompt.get("source_grounding_required", True)),
                },
                "red_team": {
                    "promptfoo_compatible": True,
                    "injection_case_count": len(injection_tests),
                    "injection_pass_count": injection_passed,
                    "cases": [
                        {
                            "case_id": str(case.get("case_id") or f"injection-{index}"),
                            "attack_class": str(case.get("attack_class") or "unknown"),
                            "status": str(case.get("status") or "missing"),
                            "raw_attack_text_included": False,
                        }
                        for index, case in enumerate(injection_tests, start=1)
                    ],
                },
                "gates": prompt_gates,
            }
        )
        gates.extend(prompt_gates)
    failed = [gate for gate in gates if gate["status"] != "pass"]
    return {
        "schema_version": PROMPT_EVIDENCE_SCHEMA_VERSION,
        "status": "pass" if prompts and not failed else "fail",
        "prompt_count": len(prompts),
        "prompts": prompts,
        "promptfoo_red_team": {
            "adapter_id": "promptfoo",
            "mode": "red_team_and_prompt_contract",
            "credentials_stored_by_study_anything": False,
            "raw_prompts_exported": False,
        },
    }


def build_hallucination_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    case_reports = []
    total_claims = 0
    cited_claims = 0
    supported_claims = 0
    unsupported_claims = 0
    contradictions = 0
    for item in _list(payload.get("hallucination_cases")):
        case = _mapping(item)
        claims = [_mapping(value) for value in _list(case.get("claims"))]
        claim_reports = []
        for claim in claims:
            total_claims += 1
            citations = [str(value) for value in _list(claim.get("citation_ids"))]
            supported = claim.get("supported") is True
            contradicted = claim.get("contradicted") is True
            cited_claims += 1 if citations else 0
            supported_claims += 1 if supported and not contradicted else 0
            unsupported_claims += 1 if not supported else 0
            contradictions += 1 if contradicted else 0
            claim_ref = str(claim.get("claim_ref") or claim.get("claim_id") or "claim")
            claim_reports.append(
                {
                    "claim_id": str(claim.get("claim_id") or stable_id(claim_ref)),
                    "claim_hash": str(claim.get("claim_hash") or sha256_text(claim_ref)),
                    "citation_ids": citations,
                    "supported": supported,
                    "contradicted": contradicted,
                    "raw_claim_text_included": False,
                }
            )
        case_reports.append(
            {
                "case_id": str(case.get("case_id") or "case"),
                "answer_ref": str(case.get("answer_ref") or "answer"),
                "claim_count": len(claims),
                "claims": claim_reports,
            }
        )
    citation_coverage = _ratio(cited_claims, total_claims)
    unsupported_ratio = _ratio(unsupported_claims, total_claims)
    faithfulness = _ratio(supported_claims, total_claims)
    gates = [
        _gate("citation_coverage", citation_coverage >= 0.8, ">=0.8", citation_coverage),
        _gate("faithfulness", faithfulness >= 0.85, ">=0.85", faithfulness),
        _gate("unsupported_claim_ratio", unsupported_ratio <= 0.1, "<=0.1", unsupported_ratio),
        _gate("answer_source_contradiction", contradictions == 0, "0", contradictions),
    ]
    return {
        "schema_version": HALLUCINATION_EVIDENCE_SCHEMA_VERSION,
        "status": "pass" if total_claims and all(gate["status"] == "pass" for gate in gates) else "fail",
        "claim_count": total_claims,
        "citation_coverage": citation_coverage,
        "faithfulness": faithfulness,
        "unsupported_claim_ratio": unsupported_ratio,
        "answer_source_contradiction_count": contradictions,
        "cases": case_reports,
        "gates": gates,
    }


def build_rag_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    case_reports = []
    precision_scores = []
    recall_scores = []
    faithfulness_scores = []
    relevancy_scores = []
    citation_scores = []
    for item in _list(payload.get("rag_cases")):
        case = _mapping(item)
        contexts = [_mapping(value) for value in _list(case.get("retrieved_contexts"))]
        expected_context_ids = {str(value) for value in _list(case.get("expected_context_ids"))}
        relevant = [ctx for ctx in contexts if ctx.get("relevant") is True]
        cited = [ctx for ctx in contexts if ctx.get("cited") is True]
        expected_present = expected_context_ids.intersection({str(ctx.get("context_id")) for ctx in contexts})
        precision = _ratio(len(relevant), len(contexts))
        recall = _ratio(len(expected_present), len(expected_context_ids))
        citation_accuracy = _ratio(sum(1 for ctx in cited if ctx.get("relevant") is True), len(cited))
        faithfulness = _float(case.get("faithfulness"), min(precision, recall))
        answer_relevancy = _float(case.get("answer_relevancy"), (precision + recall) / 2 if contexts else 0.0)
        precision_scores.append(precision)
        recall_scores.append(recall)
        faithfulness_scores.append(faithfulness)
        relevancy_scores.append(answer_relevancy)
        citation_scores.append(citation_accuracy)
        case_reports.append(
            {
                "case_id": str(case.get("case_id") or "rag-case"),
                "question_hash": sha256_text(str(case.get("question_ref") or "question")),
                "answer_hash": sha256_text(str(case.get("answer_ref") or "answer")),
                "context_precision": precision,
                "context_recall": recall,
                "faithfulness": faithfulness,
                "answer_relevancy": answer_relevancy,
                "citation_accuracy": citation_accuracy,
                "ragas_compatible_row": {
                    "question": "<redacted-question-ref>",
                    "answer": "<redacted-answer-ref>",
                    "contexts": [f"<context:{ctx.get('context_id')}>" for ctx in contexts],
                    "ground_truth": "<materialize-in-user-eval-env>",
                    "metadata_only": True,
                },
            }
        )
    metrics = {
        "context_precision": _ratio(sum(precision_scores), len(precision_scores)),
        "context_recall": _ratio(sum(recall_scores), len(recall_scores)),
        "faithfulness": _ratio(sum(faithfulness_scores), len(faithfulness_scores)),
        "answer_relevancy": _ratio(sum(relevancy_scores), len(relevancy_scores)),
        "citation_accuracy": _ratio(sum(citation_scores), len(citation_scores)),
    }
    gates = [
        _gate("context_precision", metrics["context_precision"] >= 0.7, ">=0.7", metrics["context_precision"]),
        _gate("context_recall", metrics["context_recall"] >= 0.7, ">=0.7", metrics["context_recall"]),
        _gate("faithfulness", metrics["faithfulness"] >= 0.85, ">=0.85", metrics["faithfulness"]),
        _gate("answer_relevancy", metrics["answer_relevancy"] >= 0.75, ">=0.75", metrics["answer_relevancy"]),
        _gate("citation_accuracy", metrics["citation_accuracy"] >= 0.8, ">=0.8", metrics["citation_accuracy"]),
    ]
    return {
        "schema_version": RAG_EVIDENCE_SCHEMA_VERSION,
        "status": "pass" if case_reports and all(gate["status"] == "pass" for gate in gates) else "fail",
        "ragas_dataset_export": {
            "schema": "ragas-compatible-redacted-dataset-v1",
            "rows": [case["ragas_compatible_row"] for case in case_reports],
            "raw_contexts_included": False,
            "materialization_boundary": "user_owned_eval_environment",
        },
        "metrics": metrics,
        "cases": case_reports,
        "gates": gates,
    }


def build_context_budget_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    cases = []
    budget_passes = 0
    middle_passes = 0
    for item in _list(payload.get("context_cases")):
        case = _mapping(item)
        max_tokens = _int(case.get("max_context_tokens"))
        source_tokens = _int(case.get("source_tokens"))
        packed_tokens = _int(case.get("packed_tokens"))
        probe = _mapping(case.get("lost_in_middle_probe"))
        edge_supported = probe.get("edge_supported") is True
        middle_supported = probe.get("middle_supported") is True
        budget_ok = packed_tokens <= max_tokens if max_tokens else False
        budget_passes += 1 if budget_ok else 0
        middle_passes += 1 if middle_supported else 0
        cases.append(
            {
                "case_id": str(case.get("case_id") or "context-case"),
                "max_context_tokens": max_tokens,
                "source_tokens": source_tokens,
                "packed_tokens": packed_tokens,
                "compression_ratio": _ratio(packed_tokens, source_tokens),
                "budget_ok": budget_ok,
                "selected_chunk_count": len(_list(case.get("selected_chunks"))),
                "lost_in_middle_probe": {
                    "edge_supported": edge_supported,
                    "middle_supported": middle_supported,
                    "degradation_detected": edge_supported and not middle_supported,
                    "raw_probe_text_included": False,
                },
            }
        )
    budget_pass_rate = _ratio(budget_passes, len(cases))
    middle_pass_rate = _ratio(middle_passes, len(cases))
    gates = [
        _gate("context_token_budget", budget_pass_rate == 1.0, "1.0", budget_pass_rate),
        _gate("lost_in_middle", middle_pass_rate >= 0.8, ">=0.8", middle_pass_rate),
    ]
    return {
        "schema_version": CONTEXT_BUDGET_EVIDENCE_SCHEMA_VERSION,
        "status": "pass" if cases and all(gate["status"] == "pass" for gate in gates) else "fail",
        "context_packing_receipts": cases,
        "metrics": {
            "budget_pass_rate": budget_pass_rate,
            "lost_in_middle_pass_rate": middle_pass_rate,
        },
        "gates": gates,
    }


def _dominated(run: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    quality = _float(run.get("quality_score"))
    cost = _float(run.get("cost_usd"))
    latency = _float(run.get("latency_ms"))
    other_quality = _float(other.get("quality_score"))
    other_cost = _float(other.get("cost_usd"))
    other_latency = _float(other.get("latency_ms"))
    no_worse = other_quality >= quality and other_cost <= cost and other_latency <= latency
    strictly_better = other_quality > quality or other_cost < cost or other_latency < latency
    return no_worse and strictly_better


def build_cost_quality_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    runs = [_mapping(value) for value in _list(payload.get("cost_quality_runs"))]
    selected_run_id = str(payload.get("selected_run_id") or "")
    run_reports = []
    frontier = []
    dominated = []
    for run in runs:
        run_id = str(run.get("run_id") or stable_id(run.get("model_label"), run.get("quality_score")))
        is_dominated = any(_dominated(run, other) for other in runs if other is not run)
        target = dominated if is_dominated else frontier
        target.append(run_id)
        run_reports.append(
            {
                "run_id": run_id,
                "provider_class": str(run.get("provider_class") or "external_agent"),
                "model_label_hash": sha256_text(str(run.get("model_label") or "model")),
                "latency_ms": _int(run.get("latency_ms")),
                "input_tokens": _int(run.get("input_tokens")),
                "output_tokens": _int(run.get("output_tokens")),
                "cost_usd": _float(run.get("cost_usd")),
                "quality_score": _float(run.get("quality_score")),
                "task_success": run.get("task_success") is True,
                "dominated": is_dominated,
            }
        )
    selected = next((item for item in run_reports if item["run_id"] == selected_run_id), None)
    selected_not_dominated = bool(selected and not selected["dominated"])
    best_quality = max((_float(item.get("quality_score")) for item in run_reports), default=0.0)
    gates = [
        _gate("quality_floor", best_quality >= 0.82, ">=0.82", best_quality),
        _gate("selected_on_frontier", selected_not_dominated, "true", str(selected_not_dominated).lower()),
        _gate("cost_metadata_present", all("cost_usd" in item for item in run_reports), "all", len(run_reports)),
    ]
    return {
        "schema_version": COST_QUALITY_EVIDENCE_SCHEMA_VERSION,
        "status": "pass" if run_reports and all(gate["status"] == "pass" for gate in gates) else "fail",
        "selected_run_id": selected_run_id,
        "efficient_frontier_run_ids": frontier,
        "dominated_run_ids": dominated,
        "runs": run_reports,
        "gates": gates,
        "policy": {
            "avoid_expensive_model_by_default": True,
            "model_keys_stored_by_study_anything": False,
            "cost_quality_frontier_required": True,
        },
    }


def build_llm_depth_risk_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=INPUT_SCHEMA_VERSION)
    if payload.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise LLMDepthRiskError(f"Expected {INPUT_SCHEMA_VERSION}")
    prompt = build_prompt_evidence(payload)
    hallucination = build_hallucination_evidence(payload)
    rag = build_rag_evidence(payload)
    context_budget = build_context_budget_evidence(payload)
    cost_quality = build_cost_quality_evidence(payload)
    evidence_sections = {
        "prompt": prompt,
        "hallucination": hallucination,
        "rag": rag,
        "context_budget": context_budget,
        "cost_quality": cost_quality,
    }
    model_failures = [
        name for name, evidence in evidence_sections.items() if evidence.get("status") != "pass"
    ]
    engineering = dict(_mapping(payload.get("engineering_risk")))
    engineering_status = str(engineering.get("status") or "missing")
    engineering_passed = engineering_status == "pass"
    model_passed = not model_failures
    gate = {
        "schema_version": GATE_SCHEMA_VERSION,
        "status": "allowed" if engineering_passed and model_passed else "blocked",
        "engineering_risk_status": engineering_status,
        "model_risk_status": "pass" if model_passed else "fail",
        "blocked_reasons": ([] if engineering_passed else ["engineering_risk_failed"])
        + [f"model_risk_failed:{name}" for name in model_failures],
        "rule": "engineering risk and model risk must both pass before promotion",
        "neither_loop_dominates": True,
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass" if gate["status"] == "allowed" else "blocked",
        "input_ref": str(payload.get("input_ref") or "fixture"),
        "evidence": evidence_sections,
        "risk_gate": gate,
        "external_adapters": {
            "promptfoo": "prompt red-team and injection tests",
            "deepeval": "judge-model quality metrics in user-owned eval environment",
            "ragas": "RAG dataset materialization and grounding metrics in user-owned eval environment",
            "langchain-agentevals": "trajectory and tool-step quality comparison",
        },
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_prompts_included": False,
            "model_keys_stored_by_study_anything": False,
            "model_calls_performed_by_study_anything": False,
            "external_eval_credentials_owned_by_user": True,
        },
    }
    assert_metadata_only(report, label=REPORT_SCHEMA_VERSION)
    return report


def validate_llm_depth_risk_report(report: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(report, label=REPORT_SCHEMA_VERSION)
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise LLMDepthRiskError("Invalid LLM depth risk report schema_version")
    evidence = _mapping(report.get("evidence"))
    required = {
        "prompt": PROMPT_EVIDENCE_SCHEMA_VERSION,
        "hallucination": HALLUCINATION_EVIDENCE_SCHEMA_VERSION,
        "rag": RAG_EVIDENCE_SCHEMA_VERSION,
        "context_budget": CONTEXT_BUDGET_EVIDENCE_SCHEMA_VERSION,
        "cost_quality": COST_QUALITY_EVIDENCE_SCHEMA_VERSION,
    }
    for key, schema in required.items():
        section = _mapping(evidence.get(key))
        if section.get("schema_version") != schema:
            raise LLMDepthRiskError(f"{key} evidence must use {schema}")
    gate = _mapping(report.get("risk_gate"))
    if gate.get("schema_version") != GATE_SCHEMA_VERSION:
        raise LLMDepthRiskError("risk_gate schema_version drifted")
    if gate.get("status") not in {"allowed", "blocked"}:
        raise LLMDepthRiskError("risk_gate status is invalid")
    privacy = _mapping(report.get("privacy"))
    for key in (
        "metadata_only",
        "external_eval_credentials_owned_by_user",
    ):
        if privacy.get(key) is not True:
            raise LLMDepthRiskError(f"privacy.{key} must be true")
    for key in (
        "raw_source_text_included",
        "raw_answers_included",
        "raw_prompts_included",
        "model_keys_stored_by_study_anything",
        "model_calls_performed_by_study_anything",
    ):
        if privacy.get(key) is not False:
            raise LLMDepthRiskError(f"privacy.{key} must be false")
    return dict(report)


def render_html(report: Mapping[str, Any]) -> str:
    evidence = _mapping(report.get("evidence"))
    rows = []
    for name, section in evidence.items():
        if isinstance(section, Mapping):
            rows.append(
                "<tr>"
                f"<td>{escape(str(name))}</td>"
                f"<td>{escape(str(section.get('schema_version')))}</td>"
                f"<td>{escape(str(section.get('status')))}</td>"
                "</tr>"
            )
    gate = _mapping(report.get("risk_gate"))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>LLM Depth Risk Engine</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 32px; color: #17202a; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d5dde5; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef3f8; }}
    .status {{ font-size: 24px; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>LLM Depth Risk Engine</h1>
  <p class=\"status\">Gate: {escape(str(gate.get('status')))}</p>
  <p>{escape(str(gate.get('rule')))}</p>
  <table>
    <thead><tr><th>Evidence</th><th>Schema</th><th>Status</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""


def summarize_report(report: Mapping[str, Any]) -> dict[str, Any]:
    evidence = _mapping(report.get("evidence"))
    return {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "risk_gate": _mapping(report.get("risk_gate")).get("status"),
        "evidence_statuses": {
            key: _mapping(value).get("status") for key, value in evidence.items()
        },
        "privacy": report.get("privacy"),
    }
