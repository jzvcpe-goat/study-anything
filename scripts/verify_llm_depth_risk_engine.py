#!/usr/bin/env python3
"""Verify LLM Depth Risk Engine evidence and promotion gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.core.llm_depth_risk import (  # noqa: E402
    CONTEXT_BUDGET_EVIDENCE_SCHEMA_VERSION,
    COST_QUALITY_EVIDENCE_SCHEMA_VERSION,
    GATE_SCHEMA_VERSION,
    HALLUCINATION_EVIDENCE_SCHEMA_VERSION,
    PROMPT_EVIDENCE_SCHEMA_VERSION,
    RAG_EVIDENCE_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    assert_metadata_only,
    build_llm_depth_risk_report,
    dump_json,
    load_json,
    render_html,
    summarize_report,
    validate_llm_depth_risk_report,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-llm-depth-risk-engine.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-llm-depth-risk-engine.html"
PASS_FIXTURE = ROOT / "fixtures" / "llm-depth-risk" / "pass.json"
BLOCKED_MODEL_FIXTURE = ROOT / "fixtures" / "llm-depth-risk" / "blocked-model-risk.json"
BLOCKED_ENGINEERING_FIXTURE = ROOT / "fixtures" / "llm-depth-risk" / "blocked-engineering-risk.json"
VERIFICATION_SCHEMA_VERSION = "llm-depth-risk-engine-verification-v1"


class LLMDepthRiskVerifierError(RuntimeError):
    """Raised when LLM depth risk evidence does not satisfy the contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LLMDepthRiskVerifierError(message)


def build_from_fixture(path: Path) -> dict[str, Any]:
    report = build_llm_depth_risk_report(load_json(path))
    validate_llm_depth_risk_report(report)
    return report


def require_evidence_contract(report: Mapping[str, Any]) -> None:
    require(report.get("schema_version") == REPORT_SCHEMA_VERSION, "report schema drifted")
    evidence = report.get("evidence")
    require(isinstance(evidence, Mapping), "report must include evidence object")
    expected = {
        "prompt": PROMPT_EVIDENCE_SCHEMA_VERSION,
        "hallucination": HALLUCINATION_EVIDENCE_SCHEMA_VERSION,
        "rag": RAG_EVIDENCE_SCHEMA_VERSION,
        "context_budget": CONTEXT_BUDGET_EVIDENCE_SCHEMA_VERSION,
        "cost_quality": COST_QUALITY_EVIDENCE_SCHEMA_VERSION,
    }
    for key, schema in expected.items():
        section = evidence.get(key)
        require(isinstance(section, Mapping), f"missing evidence section: {key}")
        require(section.get("schema_version") == schema, f"{key} schema drifted")
    gate = report.get("risk_gate")
    require(isinstance(gate, Mapping), "risk gate missing")
    require(gate.get("schema_version") == GATE_SCHEMA_VERSION, "risk gate schema drifted")
    privacy = report.get("privacy")
    require(isinstance(privacy, Mapping), "privacy object missing")
    require(privacy.get("metadata_only") is True, "report must be metadata-only")
    require(privacy.get("raw_source_text_included") is False, "raw source text must be excluded")
    require(privacy.get("raw_answers_included") is False, "raw answers must be excluded")
    require(privacy.get("raw_prompts_included") is False, "raw prompts must be excluded")
    require(privacy.get("model_keys_stored_by_study_anything") is False, "model keys must stay external")
    require(privacy.get("model_calls_performed_by_study_anything") is False, "verifier must not call models")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "OPENAI_API_KEY=",
        "MOONSHOT_API_KEY=",
        "AGENT_LLM_API_KEY=",
        "raw private source text",
        "private answer:",
        "http://127.0.0.1:8787",
    ):
        require(forbidden not in serialized, f"report leaked forbidden marker: {forbidden}")
    assert_metadata_only(report, label="llm-depth-risk-verifier")


def build_verification_report() -> dict[str, Any]:
    passing = build_from_fixture(PASS_FIXTURE)
    blocked_model = build_from_fixture(BLOCKED_MODEL_FIXTURE)
    blocked_engineering = build_from_fixture(BLOCKED_ENGINEERING_FIXTURE)
    for report in (passing, blocked_model, blocked_engineering):
        require_evidence_contract(report)
    require(passing["risk_gate"]["status"] == "allowed", "passing fixture must be allowed")
    require(passing["status"] == "pass", "passing fixture report must pass")
    require(blocked_model["risk_gate"]["status"] == "blocked", "model-risk fixture must block")
    require(
        any(str(reason).startswith("model_risk_failed:") for reason in blocked_model["risk_gate"]["blocked_reasons"]),
        "model-risk fixture must name model failure",
    )
    require(
        blocked_engineering["risk_gate"]["status"] == "blocked",
        "engineering-risk fixture must block",
    )
    require(
        "engineering_risk_failed" in blocked_engineering["risk_gate"]["blocked_reasons"],
        "engineering-risk fixture must name engineering failure",
    )
    evidence = passing["evidence"]
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "status": "pass",
        "engine_report": passing,
        "summary": summarize_report(passing),
        "negative_fixtures": {
            "blocked_model_risk": summarize_report(blocked_model),
            "blocked_engineering_risk": summarize_report(blocked_engineering),
        },
        "coverage": {
            "prompt_evidence": evidence["prompt"]["status"] == "pass",
            "hallucination_evidence": evidence["hallucination"]["status"] == "pass",
            "rag_evidence": evidence["rag"]["status"] == "pass",
            "context_budget_evidence": evidence["context_budget"]["status"] == "pass",
            "cost_quality_evidence": evidence["cost_quality"]["status"] == "pass",
            "risk_engine_summary_gate": passing["risk_gate"]["status"] == "allowed",
            "engineering_and_model_risk_both_required": True,
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "real_model_or_eval_keys_stored": False,
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_prompts_included": False,
        },
        "commands": {
            "build": "python3 scripts/llm_depth_risk_engine.py build --input fixtures/llm-depth-risk/pass.json",
            "verify": "python3 scripts/verify_llm_depth_risk_engine.py --check",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    parser.add_argument("--html-output", default=str(HTML_REPORT))
    args = parser.parse_args()

    report = build_verification_report()
    serialized = dump_json(report)
    output = Path(args.output)
    html_output = Path(args.html_output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        html_output.write_text(render_html(report["engine_report"]), encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"LLM depth risk report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "LLM depth risk report is out of date. "
                "Run: python3 scripts/verify_llm_depth_risk_engine.py --write"
            )
        if not html_output.is_file():
            raise SystemExit(f"LLM depth risk HTML report is missing: {html_output}")
        expected_html = render_html(report["engine_report"])
        if html_output.read_text(encoding="utf-8") != expected_html:
            raise SystemExit(
                "LLM depth risk HTML report is out of date. "
                "Run: python3 scripts/verify_llm_depth_risk_engine.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
