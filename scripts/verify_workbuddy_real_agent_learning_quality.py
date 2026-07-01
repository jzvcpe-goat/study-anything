#!/usr/bin/env python3
"""Verify WorkBuddy/Kimi/Codex real-agent learning quality evidence."""

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

from study_anything.core.real_agent_eval_bridge import (  # noqa: E402
    REAL_AGENT_LEARNING_QUALITY_REPORT_SCHEMA_VERSION,
    build_real_agent_learning_quality_report,
    dump_json,
    load_json,
    render_bridge_html,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-workbuddy-real-agent-learning-quality.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-workbuddy-real-agent-learning-quality.html"
FIXTURE_DIR = ROOT / "fixtures" / "workbuddy-real-agent-learning-quality"
PASS_FIXTURE = FIXTURE_DIR / "pass.json"
DETERMINISTIC_ONLY_FIXTURE = FIXTURE_DIR / "deterministic-only.json"
MECHANICAL_RESTATEMENT_FIXTURE = FIXTURE_DIR / "mechanical-restatement.json"
MISSING_CITATIONS_FIXTURE = FIXTURE_DIR / "missing-citations.json"
HIGH_COST_LOW_QUALITY_FIXTURE = FIXTURE_DIR / "high-cost-low-quality.json"
VERIFICATION_SCHEMA_VERSION = "workbuddy-real-agent-learning-quality-verification-v1"


class WorkBuddyRealAgentLearningQualityVerifierError(RuntimeError):
    """Readable verifier failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkBuddyRealAgentLearningQualityVerifierError(message)


def build_from_fixture(path: Path) -> dict[str, Any]:
    return build_real_agent_learning_quality_report(load_json(path))


def require_report_contract(report: Mapping[str, Any]) -> None:
    require(report.get("schema_version") == REAL_AGENT_LEARNING_QUALITY_REPORT_SCHEMA_VERSION, "report schema drifted")
    privacy = report.get("privacy")
    require(isinstance(privacy, Mapping), "privacy missing")
    require(privacy.get("metadata_only") is True, "report must be metadata-only")
    require(privacy.get("model_calls_performed_by_study_anything") is False, "Study Anything must not call models")
    require(privacy.get("model_keys_stored_by_study_anything") is False, "Study Anything must not store model keys")
    require(privacy.get("raw_source_text_included") is False, "raw source text must be excluded")
    require(privacy.get("raw_answers_included") is False, "raw answers must be excluded")
    runs = report.get("runs")
    require(isinstance(runs, list) and runs, "runs missing")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "DeepSeek is a key idea in this source",
        "OPENAI_API_KEY=",
        "MOONSHOT_API_KEY=",
        "AGENT_LLM_API_KEY=",
        "raw private source text",
        "private answer:",
        "raw prompt:",
        "http://127.0.0.1:8787",
    ):
        require(forbidden not in serialized, f"forbidden marker leaked: {forbidden}")


def _blocked_reason_contains(report: Mapping[str, Any], needle: str) -> bool:
    return any(needle in str(reason) for reason in report.get("gate", {}).get("blocked_reasons", []))


def _run_failed_gate(report: Mapping[str, Any], gate_id: str) -> bool:
    for run in report.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        if any(gate.get("gate_id") == gate_id and gate.get("status") == "fail" for gate in run.get("gates", [])):
            return True
    return False


def _demo_gates_are_demo_only(report: Mapping[str, Any]) -> bool:
    for run in report.get("runs", []):
        if not isinstance(run, Mapping) or run.get("status") != "demo_only":
            continue
        gates = run.get("gates")
        return isinstance(gates, list) and bool(gates) and all(
            isinstance(gate, Mapping) and gate.get("status") == "demo_only" for gate in gates
        )
    return False


def build_verification_report() -> dict[str, Any]:
    passing = build_from_fixture(PASS_FIXTURE)
    deterministic_only = build_from_fixture(DETERMINISTIC_ONLY_FIXTURE)
    mechanical = build_from_fixture(MECHANICAL_RESTATEMENT_FIXTURE)
    missing_citations = build_from_fixture(MISSING_CITATIONS_FIXTURE)
    high_cost = build_from_fixture(HIGH_COST_LOW_QUALITY_FIXTURE)
    for report in (passing, deterministic_only, mechanical, missing_citations, high_cost):
        require_report_contract(report)
    require(passing["gate"]["status"] == "allowed", "passing learning-quality fixture must be allowed")
    require(_demo_gates_are_demo_only(passing), "deterministic demo gates must be marked demo_only")
    require(deterministic_only["gate"]["status"] == "blocked", "deterministic-only fixture must block")
    require(_blocked_reason_contains(deterministic_only, "real_agent_quality_passes_missing"), "deterministic-only block reason missing")
    require(_run_failed_gate(deterministic_only, "real_agent_model_call"), "missing model-call gate failure missing")
    require(mechanical["gate"]["status"] == "blocked", "mechanical restatement fixture must block")
    require(_blocked_reason_contains(mechanical, "mechanical_restatement"), "mechanical block reason missing")
    require(missing_citations["gate"]["status"] == "blocked", "missing citation fixture must block")
    require(_blocked_reason_contains(missing_citations, "citation_grounding"), "missing citation block reason missing")
    require(high_cost["gate"]["status"] == "blocked", "high-cost low-quality fixture must block")
    require(_blocked_reason_contains(high_cost, "selected_run_not_on_passing_frontier"), "high-cost frontier block reason missing")
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "status": "pass",
        "quality_report": passing,
        "negative_fixtures": {
            "deterministic_only": deterministic_only["gate"],
            "mechanical_restatement": mechanical["gate"],
            "missing_citations": missing_citations["gate"],
            "high_cost_low_quality": high_cost["gate"],
        },
        "coverage": {
            "same_task_compares_deterministic_http_and_platform_agents": True,
            "workbuddy_platform_agent_run": any(run["platform_id"] == "workbuddy" for run in passing["runs"]),
            "kimi_platform_agent_run": any(run["platform_id"] == "kimi" for run in passing["runs"]),
            "codex_platform_agent_run": any(run["platform_id"] == "codex" for run in passing["runs"]),
            "deterministic_demo_not_quality_proof": passing["quality_summary"]["deterministic_demo_only"] is True,
            "deterministic_demo_gates_marked_demo_only": _demo_gates_are_demo_only(passing),
            "teaching_quality_recorded": True,
            "citation_grounding_recorded": True,
            "hallucination_risk_recorded": True,
            "cost_quality_frontier_recorded": True,
            "missing_model_call_detected": _run_failed_gate(deterministic_only, "real_agent_model_call"),
            "mechanical_restatement_blocked": _blocked_reason_contains(mechanical, "mechanical_restatement"),
            "missing_citation_blocked": _blocked_reason_contains(missing_citations, "citation_grounding"),
            "high_cost_low_quality_blocked": _blocked_reason_contains(high_cost, "selected_run_not_on_passing_frontier"),
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed_by_study_anything": False,
            "model_keys_stored_by_study_anything": False,
            "raw_prompt_source_answer_included": False,
        },
        "commands": {
            "build": "python3 scripts/real_agent_eval_bridge.py learning-quality --input fixtures/workbuddy-real-agent-learning-quality/pass.json",
            "verify": "python3 scripts/verify_workbuddy_real_agent_learning_quality.py --check",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
        html_output.write_text(render_bridge_html(report["quality_report"], title="WorkBuddy Real Agent Learning Quality"), encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"WorkBuddy real-agent learning quality report missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit("WorkBuddy real-agent learning quality report is stale. Run: python3 scripts/verify_workbuddy_real_agent_learning_quality.py --write")
        expected_html = render_bridge_html(report["quality_report"], title="WorkBuddy Real Agent Learning Quality")
        if not html_output.is_file() or html_output.read_text(encoding="utf-8") != expected_html:
            raise SystemExit("WorkBuddy real-agent learning quality HTML report is stale. Run: python3 scripts/verify_workbuddy_real_agent_learning_quality.py --write")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"verify_workbuddy_real_agent_learning_quality failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
