#!/usr/bin/env python3
"""Verify Agent eval adapter assets stay aligned with the API artifact."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
EXPECTED_ADAPTER_IDS = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
EXPECTED_TRAJECTORY = ["quiz.generate", "answer.grade", "insight.synthesize"]


def fail(message: str) -> None:
    raise RuntimeError(message)


def assert_contains(path: Path, *needles: str) -> str:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        fail(f"{path.relative_to(ROOT)} is missing required text: {missing}")
    return text


def sample_audit() -> dict[str, Any]:
    return {
        "schema_version": "agent-audit-v1",
        "session_id": "eval-asset-session",
        "stage": "completed",
        "status": "verified",
        "required_tasks": EXPECTED_TRAJECTORY,
        "observed_tasks": sorted(EXPECTED_TRAJECTORY),
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
                "node": "quiz",
                "task_type": "quiz.generate",
                "provider_id": "http-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 12,
                "confidence": 0.91,
            },
            {
                "node": "grading",
                "task_type": "answer.grade",
                "provider_id": "http-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 13,
                "confidence": 0.92,
            },
            {
                "node": "synthesis",
                "task_type": "insight.synthesize",
                "provider_id": "http-agent-redacted",
                "provider_kind": "http_agent",
                "status": "ok",
                "latency_ms": 14,
                "confidence": 0.93,
            },
        ],
    }


def main() -> None:
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from study_anything.core.agent_eval import (  # noqa: PLC0415
        AGENT_EVAL_ADAPTERS,
        agent_eval_policy,
        build_agent_eval_artifact,
        build_agent_eval_report,
    )

    adapter_ids = {adapter.adapter_id for adapter in AGENT_EVAL_ADAPTERS}
    if adapter_ids != EXPECTED_ADAPTER_IDS:
        fail(f"Agent eval adapter ids drifted: {sorted(adapter_ids)}")

    artifact = build_agent_eval_artifact(sample_audit())
    if artifact.get("schema_version") != "agent-eval-artifact-v1":
        fail(f"Unexpected artifact schema: {artifact}")
    if artifact.get("status") != "ready_for_external_eval":
        fail(f"Sample artifact is not externally evaluable: {artifact}")
    if {item.get("adapter_id") for item in artifact.get("adapter_strategy", [])} != EXPECTED_ADAPTER_IDS:
        fail(f"Artifact adapter strategy drifted: {artifact.get('adapter_strategy')}")
    if [step.get("task_type") for step in artifact.get("trajectory", [])] != EXPECTED_TRAJECTORY:
        fail(f"Artifact trajectory drifted: {artifact.get('trajectory')}")
    failed_required = [
        gate
        for gate in artifact.get("native_gates", [])
        if gate.get("required") and gate.get("status") != "pass"
    ]
    if failed_required:
        fail(f"Required native gates failed for sample artifact: {failed_required}")

    policy = agent_eval_policy()
    if policy.get("schema_version") != "agent-eval-policy-v1":
        fail(f"Unexpected eval policy schema: {policy}")
    if (policy.get("native_fast_gate") or {}).get("required_for_release") is not True:
        fail(f"Eval policy native fast gate must be release-blocking: {policy}")
    if {
        item.get("adapter_id")
        for item in policy.get("external_adapters", [])
        if isinstance(item, dict)
    } != EXPECTED_ADAPTER_IDS:
        fail(f"Eval policy adapter strategy drifted: {policy.get('external_adapters')}")

    sample_quality = {
        "schema_version": "agent-quality-eval-v1",
        "status": "pass",
        "quality_score": 0.93,
        "threshold": 0.72,
        "gates": [
            {"gate_id": "agent_invocation_proof", "status": "pass", "required": True},
            {"gate_id": "overview_quality", "status": "pass", "required": True},
            {"gate_id": "glossary_quality", "status": "pass", "required": True},
        ],
        "privacy": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "agent_endpoints_included": False,
            "raw_agent_metadata_included": False,
        },
    }
    report = build_agent_eval_report(
        agent_audit=sample_audit(),
        agent_eval_artifact=artifact,
        quality_eval=sample_quality,
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
    if report.get("schema_version") != "agent-eval-report-v1":
        fail(f"Unexpected eval report schema: {report}")
    if (report.get("native_fast_gate") or {}).get("status") != "pass":
        fail(f"Sample eval report native gate did not pass: {report}")

    serialized = json.dumps(artifact, ensure_ascii=False)
    forbidden = [
        "Private source",
        "Private answer",
        "Private feedback",
        "sk-proj",
        "http://127.0.0.1",
        "OPENAI_API_KEY",
    ]
    leaks = [fragment for fragment in forbidden if fragment in serialized]
    if leaks or re.search(r"sk-(?:proj-)?[A-Za-z0-9]{16,}", serialized):
        fail(f"Sample eval artifact leaked forbidden data: {leaks}")

    promptfoo_config = ROOT / "evals" / "promptfoo" / "agent-eval-artifact.yaml"
    assert_contains(
        promptfoo_config,
        "/v1/sessions/{{sessionId}}/agent-eval/artifact",
        "type: is-json",
        "const: agent-eval-artifact-v1",
        "const: ready_for_external_eval",
        "agent_invocation_coverage",
        "quiz.generate",
        "answer.grade",
        "insight.synthesize",
        "raw_source_text_included",
        "raw_answers_included",
        "raw_feedback_included",
        "agent_endpoints_included",
        "raw_agent_metadata_included",
    )
    for adapter_id in EXPECTED_ADAPTER_IDS:
        assert_contains(promptfoo_config, adapter_id)

    assert_contains(
        ROOT / "evals" / "README.md",
        "Promptfoo",
        "Retrieval Context Quality",
        "Agent Eval Baseline",
        "scripts/run_external_agent_evals.py",
        "scripts/verify_agent_eval_baseline.py",
        "scripts/verify_agent_eval_flow.py",
        "--tool retrieval",
        "retrieval-quality-eval-v1",
    )
    assert_contains(
        ROOT / "docs" / "agent-eval.md",
        "Promptfoo",
        "DeepEval",
        "Ragas",
        "LangChain AgentEvals",
        "scripts/run_external_agent_evals.py",
        "scripts/verify_agent_eval_baseline.py",
        "scripts/verify_platform_ecosystem_eval_flow.py",
        "--tool retrieval",
        "retrieval-quality-eval-v1",
        "agent-eval-policy-v1",
        "agent-eval-report-v1",
    )
    assert_contains(
        ROOT / "docs" / "eval-frameworks.md",
        "Promptfoo",
        "DeepEval",
        "LangChain AgentEvals",
        "Ragas",
        "external-eval-marketplace-harness-v1",
        "Study Anything must not store judge or model keys",
    )
    assert_contains(
        ROOT / "scripts" / "run_external_agent_evals.py",
        'choices=["promptfoo", "deepeval", "retrieval", "report"]',
        "ragas-compatible-native",
        "study-anything-native-maturity-report",
        "study-anything-retrieval-eval-result-v1",
    )
    assert_contains(
        ROOT / "scripts" / "verify_agent_eval_baseline.py",
        "study-anything-agent-eval-baseline-v1",
        "study-anything-agent-eval-regression-report-v1",
        "promptfoo",
        "deepeval",
        "langchain-agentevals",
        "ragas",
    )
    assert_contains(
        ROOT / "scripts" / "verify_external_eval_marketplace_harness.py",
        "external-eval-marketplace-harness-v1",
        "promptfoo",
        "deepeval",
        "langchain-agentevals",
        "ragas",
    )
    baseline = json.loads(
        (ROOT / "evals" / "baselines" / "study-anything-agent-eval-baseline.json").read_text(
            encoding="utf-8"
        )
    )
    if baseline.get("schema_version") != "study-anything-agent-eval-baseline-v1":
        fail(f"Agent eval baseline schema drifted: {baseline.get('schema_version')}")
    if baseline.get("status") != "pass":
        fail(f"Agent eval baseline does not pass: {baseline.get('status')}")

    for fixture_name in [
        "fake-agent-learning-loop.json",
        "mock-http-agent-learning-loop.json",
    ]:
        fixture_path = ROOT / "evals" / "fixtures" / fixture_name
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        if fixture.get("schema_version") != "study-anything-agent-eval-fixture-v1":
            fail(f"Agent eval fixture has invalid schema: {fixture_path}")
        tasks = [
            item.get("task_type")
            for item in fixture.get("agent_tasks", [])
            if isinstance(item, dict)
        ]
        if tasks != EXPECTED_TRAJECTORY:
            fail(f"Agent eval fixture task trajectory drifted: {fixture_path}: {tasks}")
        if any(bool(value) for value in (fixture.get("privacy") or {}).values()):
            fail(f"Agent eval fixture privacy flags are unsafe: {fixture_path}")

    print(
        json.dumps(
            {
                "status": "ok",
                "schema_version": artifact["schema_version"],
                "policy_schema_version": policy["schema_version"],
                "report_schema_version": report["schema_version"],
                "adapter_ids": sorted(EXPECTED_ADAPTER_IDS),
                "trajectory": EXPECTED_TRAJECTORY,
                "retrieval_eval_schema": "retrieval-quality-eval-v1",
                "baseline_schema": baseline["schema_version"],
                "fixture_count": 2,
                "promptfoo_config": str(promptfoo_config.relative_to(ROOT)),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_agent_eval_assets failed: {exc}", file=sys.stderr)
        sys.exit(1)
