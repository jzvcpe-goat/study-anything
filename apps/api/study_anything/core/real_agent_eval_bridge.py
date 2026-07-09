"""User-owned real-agent eval bridge and learning-quality evidence.

The bridge imports receipts produced in the user's own Agent/eval environment.
Study Anything validates and summarizes those receipts, but does not call real
models, store model keys, or persist raw prompts, sources, answers, browser
state, or evaluator outputs.
"""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any, Mapping

from .llm_depth_risk import assert_metadata_only, dump_json as _dump_json, sha256_text, stable_id


RELEASE_VERSION = "v0.3.31-alpha"

ADAPTER_RECEIPT_SCHEMA_VERSION = "external-eval-adapter-receipt-v1"
REAL_AGENT_EVAL_BRIDGE_INPUT_SCHEMA_VERSION = "real-agent-eval-bridge-input-v1"
REAL_AGENT_EVAL_BRIDGE_REPORT_SCHEMA_VERSION = "real-agent-eval-bridge-report-v1"
REAL_AGENT_EVAL_BRIDGE_GATE_SCHEMA_VERSION = "real-agent-eval-bridge-gate-v1"

REAL_AGENT_LEARNING_QUALITY_INPUT_SCHEMA_VERSION = "workbuddy-real-agent-learning-quality-input-v1"
REAL_AGENT_LEARNING_QUALITY_REPORT_SCHEMA_VERSION = "workbuddy-real-agent-learning-quality-report-v1"
REAL_AGENT_LEARNING_QUALITY_GATE_SCHEMA_VERSION = "workbuddy-real-agent-learning-quality-gate-v1"

ADAPTER_IDS = ("promptfoo", "ragas", "deepeval", "langchain-agentevals")
REQUIRED_PLATFORMS = ("workbuddy", "kimi", "codex")


class RealAgentEvalBridgeError(ValueError):
    """Raised when imported real-agent eval evidence is unsafe or invalid."""


def dump_json(payload: Any) -> str:
    """Compatibility export used by the standalone eval verifier scripts."""

    return _dump_json(payload)


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RealAgentEvalBridgeError(f"Expected JSON object: {path}")
    return payload


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


def _gate(gate_id: str, passed: bool, threshold: str, observed: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "pass" if passed else "fail",
        "threshold": threshold,
        "observed": observed,
    }


def _demo_gate(gate_id: str, threshold: str, observed: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "demo_only",
        "threshold": f"{threshold} (not evaluated for deterministic demo)",
        "observed": observed,
    }


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _adapter_metric_gates(adapter_id: str, metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    if adapter_id == "promptfoo":
        return [
            _gate("prompt_contract_passed", metrics.get("prompt_contract_passed") is True, "true", metrics.get("prompt_contract_passed")),
            _gate("injection_pass_rate", _float(metrics.get("injection_pass_rate")) >= 1.0, ">=1.0", _float(metrics.get("injection_pass_rate"))),
            _gate("citation_fabrication_pass_rate", _float(metrics.get("citation_fabrication_pass_rate")) >= 1.0, ">=1.0", _float(metrics.get("citation_fabrication_pass_rate"))),
        ]
    if adapter_id == "ragas":
        return [
            _gate("context_precision", _float(metrics.get("context_precision")) >= 0.7, ">=0.7", _float(metrics.get("context_precision"))),
            _gate("context_recall", _float(metrics.get("context_recall")) >= 0.7, ">=0.7", _float(metrics.get("context_recall"))),
            _gate("faithfulness", _float(metrics.get("faithfulness")) >= 0.85, ">=0.85", _float(metrics.get("faithfulness"))),
            _gate("answer_relevancy", _float(metrics.get("answer_relevancy")) >= 0.75, ">=0.75", _float(metrics.get("answer_relevancy"))),
            _gate("citation_accuracy", _float(metrics.get("citation_accuracy")) >= 0.8, ">=0.8", _float(metrics.get("citation_accuracy"))),
        ]
    if adapter_id == "deepeval":
        return [
            _gate("teaching_quality_score", _float(metrics.get("teaching_quality_score")) >= 0.82, ">=0.82", _float(metrics.get("teaching_quality_score"))),
            _gate("hallucination_score", _float(metrics.get("hallucination_score")) <= 0.1, "<=0.1", _float(metrics.get("hallucination_score"))),
            _gate("answer_relevancy", _float(metrics.get("answer_relevancy")) >= 0.75, ">=0.75", _float(metrics.get("answer_relevancy"))),
        ]
    if adapter_id == "langchain-agentevals":
        return [
            _gate("trajectory_match_score", _float(metrics.get("trajectory_match_score")) >= 0.85, ">=0.85", _float(metrics.get("trajectory_match_score"))),
            _gate("tool_call_coverage", _float(metrics.get("tool_call_coverage")) >= 0.8, ">=0.8", _float(metrics.get("tool_call_coverage"))),
            _gate("invalid_tool_call_count", _int(metrics.get("invalid_tool_call_count")) == 0, "0", _int(metrics.get("invalid_tool_call_count"))),
        ]
    return [_gate("known_adapter", False, "known adapter id", adapter_id)]


def validate_adapter_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(receipt, label=ADAPTER_RECEIPT_SCHEMA_VERSION)
    if receipt.get("schema_version") != ADAPTER_RECEIPT_SCHEMA_VERSION:
        raise RealAgentEvalBridgeError(f"Expected {ADAPTER_RECEIPT_SCHEMA_VERSION}")
    adapter_id = str(receipt.get("adapter_id") or "")
    if adapter_id not in ADAPTER_IDS:
        raise RealAgentEvalBridgeError(f"Unknown adapter_id: {adapter_id}")
    boundary = _mapping(receipt.get("execution_boundary"))
    privacy = _mapping(receipt.get("privacy"))
    metrics = _mapping(receipt.get("metrics"))
    metric_gates = _adapter_metric_gates(adapter_id, metrics)
    boundary_gates = [
        _gate("ran_in_user_owned_environment", boundary.get("ran_in_user_owned_environment") is True, "true", boundary.get("ran_in_user_owned_environment")),
        _gate("external_model_called", boundary.get("external_model_called") is True, "true", boundary.get("external_model_called")),
        _gate("study_anything_model_calls", boundary.get("model_calls_performed_by_study_anything") is False, "false", boundary.get("model_calls_performed_by_study_anything")),
        _gate("study_anything_model_keys", boundary.get("model_keys_stored_by_study_anything") is False, "false", boundary.get("model_keys_stored_by_study_anything")),
        _gate("raw_inputs_excluded", privacy.get("raw_inputs_included") is False, "false", privacy.get("raw_inputs_included")),
        _gate("raw_outputs_excluded", privacy.get("raw_outputs_included") is False, "false", privacy.get("raw_outputs_included")),
    ]
    gates = [*boundary_gates, *metric_gates]
    status = "pass" if receipt.get("status") == "pass" and all(gate["status"] == "pass" for gate in gates) else "fail"
    artifact_refs = []
    for index, item in enumerate(_list(receipt.get("artifact_refs")), start=1):
        artifact = _mapping(item)
        artifact_refs.append(
            {
                "artifact_id": str(artifact.get("artifact_id") or f"{adapter_id}-{index}"),
                "kind": str(artifact.get("kind") or adapter_id),
                "sha256": str(artifact.get("sha256") or sha256_text(str(artifact.get("artifact_id") or index))),
                "raw_artifact_included": False,
            }
        )
    normalized = {
        "schema_version": ADAPTER_RECEIPT_SCHEMA_VERSION,
        "adapter_id": adapter_id,
        "receipt_id": str(receipt.get("receipt_id") or stable_id(adapter_id, receipt.get("created_at_utc"))),
        "status": status,
        "reported_status": str(receipt.get("status") or "missing"),
        "created_at_utc": str(receipt.get("created_at_utc") or "unknown"),
        "platform_id": str(receipt.get("platform_id") or "private-platform-agent"),
        "task_ref": str(receipt.get("task_ref") or "unknown-task"),
        "metric_summary": {key: metrics[key] for key in sorted(metrics)},
        "gates": gates,
        "artifact_refs": artifact_refs,
        "execution_boundary": {
            "ran_in_user_owned_environment": boundary.get("ran_in_user_owned_environment") is True,
            "external_model_called": boundary.get("external_model_called") is True,
            "model_calls_performed_by_study_anything": False,
            "model_keys_stored_by_study_anything": False,
            "credentials_stay_in_user_eval_environment": True,
        },
        "privacy": {
            "metadata_only": True,
            "raw_inputs_included": False,
            "raw_outputs_included": False,
            "raw_prompts_included": False,
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "real_model_or_eval_keys_stored": False,
        },
    }
    assert_metadata_only(normalized, label=ADAPTER_RECEIPT_SCHEMA_VERSION)
    return normalized


def build_real_agent_eval_bridge_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=REAL_AGENT_EVAL_BRIDGE_INPUT_SCHEMA_VERSION)
    if payload.get("schema_version") != REAL_AGENT_EVAL_BRIDGE_INPUT_SCHEMA_VERSION:
        raise RealAgentEvalBridgeError(f"Expected {REAL_AGENT_EVAL_BRIDGE_INPUT_SCHEMA_VERSION}")
    receipts = [validate_adapter_receipt(_mapping(item)) for item in _list(payload.get("adapter_receipts"))]
    by_adapter = {receipt["adapter_id"]: receipt for receipt in receipts}
    missing = [adapter_id for adapter_id in ADAPTER_IDS if adapter_id not in by_adapter]
    failed = [adapter_id for adapter_id, receipt in by_adapter.items() if receipt["status"] != "pass"]
    missing_model_call = [
        adapter_id
        for adapter_id, receipt in by_adapter.items()
        if receipt["execution_boundary"]["external_model_called"] is not True
    ]
    blocked_reasons = [f"missing_adapter:{adapter_id}" for adapter_id in missing]
    blocked_reasons.extend(f"adapter_failed:{adapter_id}" for adapter_id in failed)
    blocked_reasons.extend(f"external_model_call_missing:{adapter_id}" for adapter_id in missing_model_call)
    gate = {
        "schema_version": REAL_AGENT_EVAL_BRIDGE_GATE_SCHEMA_VERSION,
        "status": "allowed" if not blocked_reasons else "blocked",
        "required_adapters": list(ADAPTER_IDS),
        "blocked_reasons": blocked_reasons,
        "rule": "all required user-owned external eval receipts must pass without importing raw model data",
    }
    report = {
        "schema_version": REAL_AGENT_EVAL_BRIDGE_REPORT_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass" if gate["status"] == "allowed" else "blocked",
        "task_ref": str(payload.get("task_ref") or "unknown-task"),
        "adapter_receipts": receipts,
        "adapter_statuses": {adapter_id: by_adapter.get(adapter_id, {}).get("status", "missing") for adapter_id in ADAPTER_IDS},
        "gate": gate,
        "import_contract": {
            "receipt_schema": ADAPTER_RECEIPT_SCHEMA_VERSION,
            "user_runs_eval_in_own_environment": True,
            "study_anything_imports_metadata_receipts_only": True,
            "raw_artifacts_allowed": False,
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed_by_study_anything": False,
            "model_keys_stored_by_study_anything": False,
            "external_eval_credentials_owned_by_user": True,
            "raw_prompts_included": False,
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_evaluator_outputs_included": False,
        },
    }
    assert_metadata_only(report, label=REAL_AGENT_EVAL_BRIDGE_REPORT_SCHEMA_VERSION)
    return report


def _quality_run_report(run: Mapping[str, Any]) -> dict[str, Any]:
    run_id = str(run.get("run_id") or stable_id(run.get("run_type"), run.get("platform_id")))
    run_type = str(run.get("run_type") or "unknown")
    quality = _mapping(run.get("quality"))
    cost = _mapping(run.get("cost"))
    agent = _mapping(run.get("agent_evidence"))
    teaching_quality = _float(quality.get("teaching_quality"))
    citation_grounding = _float(quality.get("citation_grounding"))
    hallucination_risk = _float(quality.get("hallucination_risk"))
    unsupported_claim_ratio = _float(quality.get("unsupported_claim_ratio"))
    mechanical_restatement_score = _float(quality.get("mechanical_restatement_score"))
    external_model_called = agent.get("external_model_called") is True
    demo_only = run_type == "deterministic_demo"
    if demo_only:
        gates = [
            _demo_gate("real_agent_model_call", "true for real runs", external_model_called),
            _demo_gate("teaching_quality", ">=0.8", teaching_quality),
            _demo_gate("citation_grounding", ">=0.8", citation_grounding),
            _demo_gate("hallucination_risk", "<=0.1", hallucination_risk),
            _demo_gate("unsupported_claim_ratio", "<=0.1", unsupported_claim_ratio),
            _demo_gate("mechanical_restatement", "<=0.25", mechanical_restatement_score),
        ]
    else:
        gates = [
            _gate("real_agent_model_call", external_model_called, "true for real runs", external_model_called),
            _gate("teaching_quality", teaching_quality >= 0.8, ">=0.8", teaching_quality),
            _gate("citation_grounding", citation_grounding >= 0.8, ">=0.8", citation_grounding),
            _gate("hallucination_risk", hallucination_risk <= 0.1, "<=0.1", hallucination_risk),
            _gate("unsupported_claim_ratio", unsupported_claim_ratio <= 0.1, "<=0.1", unsupported_claim_ratio),
            _gate("mechanical_restatement", mechanical_restatement_score <= 0.25, "<=0.25", mechanical_restatement_score),
        ]
    return {
        "run_id": run_id,
        "run_type": run_type,
        "platform_id": str(run.get("platform_id") or "generic"),
        "status": "demo_only" if demo_only else ("pass" if all(gate["status"] == "pass" for gate in gates) else "fail"),
        "deterministic_demo_only": demo_only,
        "output_ref_hash": str(run.get("output_ref_hash") or sha256_text(run_id)),
        "agent_evidence": {
            "external_model_called": external_model_called,
            "platform_agent_used": agent.get("platform_agent_used") is True,
            "user_owned_http_agent_used": agent.get("user_owned_http_agent_used") is True,
            "receipt_ids": [str(value) for value in _list(agent.get("receipt_ids"))],
            "raw_agent_trace_included": False,
        },
        "quality": {
            "teaching_quality": teaching_quality,
            "citation_grounding": citation_grounding,
            "hallucination_risk": hallucination_risk,
            "unsupported_claim_ratio": unsupported_claim_ratio,
            "mechanical_restatement_score": mechanical_restatement_score,
        },
        "cost_quality": {
            "latency_ms": _int(cost.get("latency_ms")),
            "input_tokens": _int(cost.get("input_tokens")),
            "output_tokens": _int(cost.get("output_tokens")),
            "cost_usd": _float(cost.get("cost_usd")),
            "quality_score": teaching_quality,
        },
        "gates": gates,
    }


def _dominated(run: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    quality = _float(_mapping(run.get("cost_quality")).get("quality_score"))
    cost = _float(_mapping(run.get("cost_quality")).get("cost_usd"))
    latency = _float(_mapping(run.get("cost_quality")).get("latency_ms"))
    other_quality = _float(_mapping(other.get("cost_quality")).get("quality_score"))
    other_cost = _float(_mapping(other.get("cost_quality")).get("cost_usd"))
    other_latency = _float(_mapping(other.get("cost_quality")).get("latency_ms"))
    no_worse = other_quality >= quality and other_cost <= cost and other_latency <= latency
    strictly_better = other_quality > quality or other_cost < cost or other_latency < latency
    return no_worse and strictly_better


def build_real_agent_learning_quality_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=REAL_AGENT_LEARNING_QUALITY_INPUT_SCHEMA_VERSION)
    if payload.get("schema_version") != REAL_AGENT_LEARNING_QUALITY_INPUT_SCHEMA_VERSION:
        raise RealAgentEvalBridgeError(f"Expected {REAL_AGENT_LEARNING_QUALITY_INPUT_SCHEMA_VERSION}")
    runs = [_quality_run_report(_mapping(item)) for item in _list(payload.get("runs"))]
    real_runs = [run for run in runs if not run["deterministic_demo_only"]]
    pass_real_runs = [run for run in real_runs if run["status"] == "pass"]
    platforms = {run["platform_id"] for run in runs}
    missing_platforms = [platform for platform in REQUIRED_PLATFORMS if platform not in platforms]
    frontier = []
    dominated = []
    for run in real_runs:
        target = dominated if any(_dominated(run, other) for other in real_runs if other is not run) else frontier
        target.append(run["run_id"])
    selected_run_id = str(payload.get("selected_run_id") or "")
    selected = next((run for run in real_runs if run["run_id"] == selected_run_id), None)
    selected_valid = bool(selected and selected["run_id"] in frontier and selected["status"] == "pass")
    blocked_reasons = []
    blocked_reasons.extend(f"missing_platform:{platform}" for platform in missing_platforms)
    if not any(run["deterministic_demo_only"] for run in runs):
        blocked_reasons.append("deterministic_demo_comparison_missing")
    if len(pass_real_runs) < 2:
        blocked_reasons.append("real_agent_quality_passes_missing")
    if not selected_valid:
        blocked_reasons.append("selected_run_not_on_passing_frontier")
    for run in real_runs:
        if run["status"] != "pass":
            failed_gates = [gate["gate_id"] for gate in run["gates"] if gate["status"] != "pass"]
            blocked_reasons.append(f"run_failed:{run['run_id']}:{','.join(failed_gates)}")
    gate = {
        "schema_version": REAL_AGENT_LEARNING_QUALITY_GATE_SCHEMA_VERSION,
        "status": "allowed" if not blocked_reasons else "blocked",
        "blocked_reasons": blocked_reasons,
        "rule": "deterministic demo is comparison-only; at least two real user-owned/platform Agent runs must pass quality, grounding, hallucination, and cost-quality gates",
    }
    report = {
        "schema_version": REAL_AGENT_LEARNING_QUALITY_REPORT_SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass" if gate["status"] == "allowed" else "blocked",
        "task_ref": str(payload.get("task_ref") or "unknown-task"),
        "runs": runs,
        "gate": gate,
        "quality_summary": {
            "real_run_count": len(real_runs),
            "passing_real_run_count": len(pass_real_runs),
            "average_teaching_quality": _avg([run["quality"]["teaching_quality"] for run in real_runs]),
            "average_citation_grounding": _avg([run["quality"]["citation_grounding"] for run in real_runs]),
            "average_hallucination_risk": _avg([run["quality"]["hallucination_risk"] for run in real_runs]),
            "deterministic_demo_only": True,
        },
        "cost_quality_frontier": {
            "selected_run_id": selected_run_id,
            "efficient_frontier_run_ids": frontier,
            "dominated_run_ids": dominated,
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed_by_study_anything": False,
            "model_keys_stored_by_study_anything": False,
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_prompts_included": False,
            "raw_agent_trace_included": False,
        },
    }
    assert_metadata_only(report, label=REAL_AGENT_LEARNING_QUALITY_REPORT_SCHEMA_VERSION)
    return report


def render_bridge_html(report: Mapping[str, Any], *, title: str) -> str:
    rows = []
    source = report.get("adapter_receipts") or report.get("runs") or []
    for item in _list(source):
        if not isinstance(item, Mapping):
            continue
        label = item.get("adapter_id") or item.get("run_id")
        schema = item.get("schema_version") or item.get("run_type")
        rows.append(
            "<tr>"
            f"<td>{escape(str(label))}</td>"
            f"<td>{escape(str(schema))}</td>"
            f"<td>{escape(str(item.get('status')))}</td>"
            "</tr>"
        )
    gate = _mapping(report.get("gate"))
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 32px; color: #17202a; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d5dde5; padding: 8px 10px; text-align: left; }}
    th {{ background: #eef3f8; }}
    .status {{ font-size: 24px; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p class=\"status\">Gate: {escape(str(gate.get('status')))}</p>
  <p>{escape(str(gate.get('rule')))}</p>
  <table>
    <thead><tr><th>Evidence</th><th>Type</th><th>Status</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""
