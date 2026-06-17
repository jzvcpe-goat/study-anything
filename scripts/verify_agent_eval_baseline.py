#!/usr/bin/env python3
"""Generate and verify the deterministic Agent eval regression baseline."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "evals" / "baselines" / "study-anything-agent-eval-baseline.json"
BASELINE_SCHEMA = "study-anything-agent-eval-baseline-v1"
REGRESSION_SCHEMA = "study-anything-agent-eval-regression-report-v1"
BASELINE_VERSION = "v0.3.30-alpha"
EXPECTED_ADAPTERS = ["deepeval", "langchain-agentevals", "promptfoo", "ragas"]
EXPECTED_TRAJECTORY = [
    "teach.overview",
    "teach.glossary",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
]


class AgentEvalBaselineError(RuntimeError):
    """Readable baseline failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sample_audit() -> dict[str, Any]:
    return {
        "schema_version": "agent-audit-v1",
        "session_id": "baseline-eval-session",
        "stage": "completed",
        "status": "verified",
        "required_tasks": EXPECTED_TRAJECTORY,
        "observed_tasks": EXPECTED_TRAJECTORY,
        "missing_tasks": [],
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
        "evidence": [
            {
                "node": "teaching_layers",
                "task_type": "teach.overview",
                "provider_id": "external-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 9,
                "confidence": 0.9,
            },
            {
                "node": "teaching_layers",
                "task_type": "teach.glossary",
                "provider_id": "external-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 10,
                "confidence": 0.9,
            },
            {
                "node": "quiz",
                "task_type": "quiz.generate",
                "provider_id": "external-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 11,
                "confidence": 0.91,
            },
            {
                "node": "grading",
                "task_type": "answer.grade",
                "provider_id": "external-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 13,
                "confidence": 0.92,
            },
            {
                "node": "synthesis",
                "task_type": "insight.synthesize",
                "provider_id": "external-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 17,
                "confidence": 0.93,
            },
        ],
    }


def build_current_baseline() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from study_anything.core.agent_eval import (  # noqa: PLC0415
        AGENT_EVAL_ADAPTERS,
        build_agent_eval_artifact,
        build_agent_eval_report,
    )
    from study_anything.core.quality_eval import build_agent_quality_eval  # noqa: PLC0415
    from study_anything.core.retrieval import (  # noqa: PLC0415
        RetrievalResult,
        RetrievalSearchResultSet,
        RetrievalStatus,
    )
    from study_anything.core.retrieval_eval import (  # noqa: PLC0415
        RetrievalQualityInput,
        build_retrieval_quality_eval,
    )
    from study_anything.core.security import hash_user_id, sha256_text  # noqa: PLC0415
    from study_anything.core.workflow import (  # noqa: PLC0415
        Answer,
        EnrichmentItem,
        GradingResult,
        LearningState,
        Mastery,
        QuizItem,
        ReadingSource,
    )

    audit = sample_audit()
    artifact = build_agent_eval_artifact(audit)
    state = LearningState(
        session_id="baseline-eval-session",
        user_id="baseline-user",
        user_hash=hash_user_id("baseline-user"),
        stage="completed",
        source=ReadingSource(
            source_type="local_text",
            reference="baseline://source",
            title="Baseline Source",
            text="Baseline source text for deterministic eval construction.",
            excerpt_hash=sha256_text("baseline source"),
            verified=True,
        ),
        enrichment_items=[
            EnrichmentItem(
                source_type="web",
                reference="https://example.com/baseline",
                title="Baseline enrichment",
                text="Bounded enrichment excerpt for deterministic eval construction.",
                excerpt_hash=sha256_text("baseline enrichment"),
            )
        ],
        teaching_layers=[
            {
                "layer": "overview",
                "content": {"summary": "A concise source-bound overview."},
                "agent": {"task_type": "teach.overview"},
            },
            {
                "layer": "glossary",
                "content": [{"term": "active recall", "explanation": "Retrieve before rereading."}],
                "agent": {"task_type": "teach.glossary"},
            },
        ],
        quiz_items=[
            QuizItem(
                item_id="baseline-q1",
                prompt="What does active recall require?",
                source_ref="baseline://source",
                excerpt_hash=sha256_text("baseline source"),
                rubric="Mentions retrieval before rereading.",
            )
        ],
        answers=[Answer(item_id="baseline-q1", text="Baseline answer text not emitted.")],
        grading_results=[
            GradingResult(
                item_id="baseline-q1",
                score=0.86,
                feedback="Feedback text is not emitted in the baseline scorecard.",
                reward=0.86,
            )
        ],
        mastery=Mastery(level=0.62, bloom="understand"),
        insights=["A reusable insight exists for the quality gate."],
        scribe_log=["A short scribe note exists for Obsidian readiness."],
    )
    quality = build_agent_quality_eval(state, agent_audit=audit, agent_eval_artifact=artifact)
    result_set = RetrievalSearchResultSet(
        session_id="baseline-eval-session",
        query="active recall study habits",
        status="ready",
        results=[
            RetrievalResult(
                document_id="doc-1",
                session_id="baseline-eval-session",
                source_type="web",
                reference="https://example.com/active-recall",
                excerpt_hash=sha256_text("retrieval result one"),
                locator="p1",
                snippet="Active recall asks learners to retrieve before rereading.",
                score=0.93,
            ),
            RetrievalResult(
                document_id="doc-2",
                session_id="baseline-eval-session",
                source_type="local_text",
                reference="baseline://source",
                excerpt_hash=sha256_text("retrieval result two"),
                locator="p2",
                snippet="Spacing and retrieval strengthen later review.",
                score=0.81,
            ),
        ],
    )
    retrieval = build_retrieval_quality_eval(
        RetrievalQualityInput(
            session_id="baseline-eval-session",
            query="active recall study habits",
            retrieval_status=RetrievalStatus(
                enabled=True,
                status="healthy",
                index_name="study_anything_baseline",
                message="Baseline retrieval projection is healthy.",
                document_count=2,
            ).public_dict(),
            result_set=result_set,
        )
    )
    report = build_agent_eval_report(
        agent_audit=audit,
        agent_eval_artifact=artifact,
        quality_eval=quality,
        retrieval_eval=retrieval,
        export_status={
            "obsidian_ready": True,
            "learning_package_ready": True,
            "second_brain_ready": True,
            "privacy": {
                "raw_source_text_included": False,
                "raw_enrichment_text_included": False,
                "learner_answers_included": False,
                "grading_feedback_included": False,
                "generated_insights_included": False,
                "agent_metadata_included": False,
                "secrets_included": False,
            },
        },
    )
    scorecard = build_scorecard(
        artifact=artifact,
        quality=quality,
        retrieval=retrieval,
        report=report,
        adapters=[adapter.public_dict() for adapter in AGENT_EVAL_ADAPTERS],
    )
    payload = {
        "schema_version": BASELINE_SCHEMA,
        "version": BASELINE_VERSION,
        "status": scorecard["status"],
        "generated_by": "scripts/verify_agent_eval_baseline.py",
        "scorecard": scorecard,
        "reports": {
            "agent_eval_artifact": summarize_agent_eval_artifact(artifact),
            "agent_quality_eval": summarize_quality_eval(quality),
            "retrieval_quality_eval": summarize_quality_eval(retrieval),
            "agent_eval_report": summarize_agent_eval_report(report),
        },
        "frameworks": {
            "promptfoo": {
                "mode": "optional_external",
                "config": "evals/promptfoo/agent-eval-artifact.yaml",
                "timeout_control": "scripts/run_external_agent_evals.py --timeout-seconds",
            },
            "deepeval": {
                "mode": "native_fast_gate_or_optional_external",
                "adapter": "evals/deepeval/study_anything_quality_eval.py",
                "timeout_control": "scripts/run_external_agent_evals.py --timeout-seconds",
            },
            "langchain-agentevals": {
                "mode": "trajectory_contract",
                "trajectory_source": "agent_eval_artifact.trajectory",
            },
            "ragas": {
                "mode": "ragas-compatible-native",
                "report_schema": "retrieval-quality-eval-v1",
            },
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "agent_endpoints_included": False,
            "model_or_judge_keys_included": False,
        },
    }
    assert_redacted(payload)
    return payload


def summarize_agent_eval_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": artifact.get("schema_version"),
        "status": artifact.get("status"),
        "invocation_audit_status": artifact.get("invocation_audit_status"),
        "adapter_ids": sorted(
            str(item.get("adapter_id"))
            for item in artifact.get("adapter_strategy", [])
            if isinstance(item, Mapping)
        ),
        "trajectory_tasks": [
            str(item.get("task_type"))
            for item in artifact.get("trajectory", [])
            if isinstance(item, Mapping)
        ],
        "native_gates": summarize_gates(artifact.get("native_gates", [])),
        "used_external_agent": artifact.get("used_external_agent"),
        "used_fake_agent": artifact.get("used_fake_agent"),
    }


def summarize_quality_eval(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "quality_score": report.get("quality_score"),
        "threshold": report.get("threshold"),
        "gates": summarize_gates(report.get("gates", [])),
        "privacy": report.get("privacy"),
    }


def summarize_agent_eval_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "native_fast_gate_status": (report.get("native_fast_gate") or {}).get("status"),
        "dimension_statuses": {
            item.get("dimension_id"): item.get("status")
            for item in report.get("dimensions", [])
            if isinstance(item, Mapping)
        },
        "adapter_ids": sorted(
            str(item.get("adapter_id"))
            for item in report.get("adapter_readiness", [])
            if isinstance(item, Mapping)
        ),
    }


def summarize_gates(gates: object) -> list[dict[str, Any]]:
    if not isinstance(gates, list):
        return []
    return [
        {
            "gate_id": gate.get("gate_id"),
            "category": gate.get("category"),
            "status": gate.get("status"),
            "required": gate.get("required"),
            "score": gate.get("score"),
        }
        for gate in gates
        if isinstance(gate, Mapping)
    ]


def build_scorecard(
    *,
    artifact: Mapping[str, Any],
    quality: Mapping[str, Any],
    retrieval: Mapping[str, Any],
    report: Mapping[str, Any],
    adapters: list[Mapping[str, Any]],
) -> dict[str, Any]:
    trajectory = [
        str(item.get("task_type"))
        for item in artifact.get("trajectory", [])
        if isinstance(item, Mapping)
    ]
    adapter_ids = sorted(str(item.get("adapter_id")) for item in adapters)
    required_native_failed = [
        gate
        for gate in artifact.get("native_gates", [])
        if isinstance(gate, Mapping) and gate.get("required") and gate.get("status") != "pass"
    ]
    required_quality_failed = [
        gate
        for gate in quality.get("gates", [])
        if isinstance(gate, Mapping) and gate.get("required") and gate.get("status") != "pass"
    ]
    required_retrieval_failed = [
        gate
        for gate in retrieval.get("gates", [])
        if isinstance(gate, Mapping) and gate.get("required") and gate.get("status") != "pass"
    ]
    checks = [
        _check(
            "adapter_matrix",
            adapter_ids == EXPECTED_ADAPTERS,
            {"expected": EXPECTED_ADAPTERS, "actual": adapter_ids},
        ),
        _check(
            "trajectory_coverage",
            trajectory == EXPECTED_TRAJECTORY,
            {"expected": EXPECTED_TRAJECTORY, "actual": trajectory},
        ),
        _check("native_required_gates", not required_native_failed, {"failed": required_native_failed}),
        _check(
            "quality_required_gates",
            quality.get("status") == "pass" and not required_quality_failed,
            {
                "status": quality.get("status"),
                "score": quality.get("quality_score"),
                "threshold": quality.get("threshold"),
                "failed": required_quality_failed,
            },
        ),
        _check(
            "retrieval_required_gates",
            retrieval.get("status") == "pass" and not required_retrieval_failed,
            {
                "status": retrieval.get("status"),
                "score": retrieval.get("quality_score"),
                "threshold": retrieval.get("threshold"),
                "failed": required_retrieval_failed,
            },
        ),
        _check(
            "privacy_redaction",
            _privacy_passed(artifact) and _privacy_passed(quality) and _privacy_passed(retrieval),
            {
                "artifact": artifact.get("privacy"),
                "quality": quality.get("privacy"),
                "retrieval": retrieval.get("privacy"),
            },
        ),
        _check(
            "agent_eval_report",
            report.get("schema_version") == "agent-eval-report-v1"
            and (report.get("native_fast_gate") or {}).get("status") == "pass"
            and str(report.get("status") or "").startswith("pass"),
            {
                "schema_version": report.get("schema_version"),
                "status": report.get("status"),
                "native_fast_gate": report.get("native_fast_gate"),
            },
        ),
    ]
    status = "pass" if all(check["status"] == "pass" for check in checks) else "fail"
    return {
        "status": status,
        "checks": checks,
        "quality_score": quality.get("quality_score"),
        "retrieval_quality_score": retrieval.get("quality_score"),
        "agent_eval_report_status": report.get("status"),
        "trajectory_coverage": round(len(set(trajectory) & set(EXPECTED_TRAJECTORY)) / len(EXPECTED_TRAJECTORY), 3),
        "adapter_ids": adapter_ids,
    }


def _check(check_id: str, pass_when: bool, details: Mapping[str, Any]) -> dict[str, Any]:
    return {"check_id": check_id, "status": "pass" if pass_when else "fail", "details": dict(details)}


def _privacy_passed(report: Mapping[str, Any]) -> bool:
    privacy = report.get("privacy", {})
    if not isinstance(privacy, Mapping):
        return False
    forbidden_flags = [
        "raw_source_text_included",
        "raw_answers_included",
        "raw_feedback_included",
        "agent_endpoints_included",
        "raw_agent_metadata_included",
        "agent_secrets_allowed",
        "full_source_text_returned",
        "result_snippets_included",
    ]
    return not any(bool(privacy.get(flag)) for flag in forbidden_flags)


def compare_to_baseline(current: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    checks = [
        _check(
            "baseline_schema",
            baseline.get("schema_version") == BASELINE_SCHEMA,
            {"baseline_schema": baseline.get("schema_version")},
        ),
        _check(
            "current_schema",
            current.get("schema_version") == BASELINE_SCHEMA,
            {"current_schema": current.get("schema_version")},
        ),
        _check(
            "scorecard_passes",
            current.get("scorecard", {}).get("status") == "pass",
            {"current_status": current.get("scorecard", {}).get("status")},
        ),
        _check(
            "adapter_ids_not_regressed",
            current.get("scorecard", {}).get("adapter_ids")
            == baseline.get("scorecard", {}).get("adapter_ids")
            == EXPECTED_ADAPTERS,
            {
                "baseline": baseline.get("scorecard", {}).get("adapter_ids"),
                "current": current.get("scorecard", {}).get("adapter_ids"),
            },
        ),
        _check(
            "trajectory_not_regressed",
            current.get("reports", {}).get("agent_eval_artifact", {}).get("trajectory_tasks")
            == baseline.get("reports", {}).get("agent_eval_artifact", {}).get("trajectory_tasks")
            == EXPECTED_TRAJECTORY,
            {
                "baseline": baseline.get("reports", {}).get("agent_eval_artifact", {}).get("trajectory_tasks"),
                "current": current.get("reports", {}).get("agent_eval_artifact", {}).get("trajectory_tasks"),
            },
        ),
        _check(
            "quality_score_not_regressed",
            float(current.get("scorecard", {}).get("quality_score", 0.0))
            >= float(baseline.get("scorecard", {}).get("quality_score", 1.0)),
            {
                "baseline": baseline.get("scorecard", {}).get("quality_score"),
                "current": current.get("scorecard", {}).get("quality_score"),
            },
        ),
        _check(
            "retrieval_score_not_regressed",
            float(current.get("scorecard", {}).get("retrieval_quality_score", 0.0))
            >= float(baseline.get("scorecard", {}).get("retrieval_quality_score", 1.0)),
            {
                "baseline": baseline.get("scorecard", {}).get("retrieval_quality_score"),
                "current": current.get("scorecard", {}).get("retrieval_quality_score"),
            },
        ),
        _check(
            "agent_eval_report_not_regressed",
            current.get("reports", {}).get("agent_eval_report", {}).get("schema_version")
            == baseline.get("reports", {}).get("agent_eval_report", {}).get("schema_version")
            == "agent-eval-report-v1"
            and current.get("reports", {}).get("agent_eval_report", {}).get("native_fast_gate_status")
            == baseline.get("reports", {}).get("agent_eval_report", {}).get("native_fast_gate_status")
            == "pass",
            {
                "baseline": baseline.get("reports", {}).get("agent_eval_report"),
                "current": current.get("reports", {}).get("agent_eval_report"),
            },
        ),
        _check(
            "privacy_contract_stable",
            current.get("privacy") == baseline.get("privacy"),
            {"current": current.get("privacy"), "baseline": baseline.get("privacy")},
        ),
    ]
    status = "pass" if all(check["status"] == "pass" for check in checks) else "fail"
    return {
        "schema_version": REGRESSION_SCHEMA,
        "status": status,
        "baseline_version": baseline.get("version"),
        "current_version": current.get("version"),
        "checks": checks,
        "external_eval_policy": {
            "fast_native_gate_required": True,
            "promptfoo_deepeval_ragas_native_or_external": "optional unless explicitly required",
            "timeouts_required": True,
            "real_model_or_judge_keys_stored_by_study_anything": False,
        },
    }


def assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    forbidden_literals = [
        "Baseline source text",
        "Baseline answer text",
        "Feedback text is not emitted",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    leaks = [item for item in forbidden_literals if item in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if re.search(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", serialized):
        leaks.append("secret-looking key/value")
    if leaks:
        raise AgentEvalBaselineError(f"Agent eval baseline leaked private data: {leaks}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=str(BASELINE_PATH))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    current = build_current_baseline()
    text = dump_json(current)
    if args.write:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(text, encoding="utf-8")
        print(f"wrote {baseline_path.relative_to(ROOT)}")
        return
    if args.check:
        if not baseline_path.exists():
            raise AgentEvalBaselineError(f"Missing Agent eval baseline: {baseline_path}")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        report = compare_to_baseline(current, baseline)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report["status"] != "pass":
            raise SystemExit(1)
        return
    print(json.dumps(current, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_agent_eval_baseline failed: {exc}", file=sys.stderr)
        sys.exit(1)
