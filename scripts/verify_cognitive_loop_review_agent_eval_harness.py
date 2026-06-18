#!/usr/bin/env python3
"""Verify the offline Cognitive Loop Review Agent eval harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evals" / "review-agent"
CASE_DIR = EVAL_DIR / "cases"
GOLDEN_DIR = EVAL_DIR / "golden"
BAD_DIR = EVAL_DIR / "bad"
REPORT_VERIFIER_PATH = ROOT / "scripts" / "verify_cognitive_loop_review_agent_report.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-eval-harness.json"

SCHEMA_VERSION = "cognitive-loop-review-agent-eval-harness-v1"
CASE_SCHEMA_VERSION = "cognitive-loop-review-agent-eval-case-v1"
CASE_IDS = ("approved-docs", "needs-review-test-gap", "needs-fix-command-injection")
NEGATIVE_REPORTS = ("privacy-leak.json",)


class ReviewAgentEvalHarnessError(RuntimeError):
    """Readable Review Agent eval harness failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentEvalHarnessError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentEvalHarnessError(f"JSON object expected: {path.relative_to(ROOT)}")
    return value


def load_report_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_review_agent_report_verifier",
        REPORT_VERIFIER_PATH,
    )
    if spec is None or spec.loader is None:
        raise ReviewAgentEvalHarnessError(f"Cannot load report verifier: {REPORT_VERIFIER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentEvalHarnessError(message)


def validate_case(case: Mapping[str, Any], *, case_id: str) -> dict[str, Any]:
    require(case.get("schema_version") == CASE_SCHEMA_VERSION, f"{case_id} case schema drifted.")
    require(case.get("case_id") == case_id, f"{case_id} case id drifted.")
    review_input = case.get("input")
    expected = case.get("expected")
    require(isinstance(review_input, Mapping), f"{case_id} input must be an object.")
    require(isinstance(expected, Mapping), f"{case_id} expected must be an object.")
    diff_text = str(review_input.get("git_diff", ""))
    require("diff --git" in diff_text, f"{case_id} must include a synthetic git diff.")
    require("OPENAI_API_KEY" not in diff_text and "MOONSHOT_API_KEY" not in diff_text, f"{case_id} fixture contains model key text.")
    require(str(review_input.get("pr_id", "")).startswith("eval-"), f"{case_id} pr_id must be an eval id.")
    required_findings = expected.get("required_findings")
    require(isinstance(required_findings, list), f"{case_id} expected.required_findings must be a list.")
    return {
        "case_id": case_id,
        "decision": expected.get("decision"),
        "overall_risk": expected.get("overall_risk"),
        "required_finding_count": len(required_findings),
        "synthetic_diff": True,
    }


def finding_matches(finding: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    for key in ("dimension", "severity", "file"):
        if expected.get(key) and finding.get(key) != expected.get(key):
            return False
    evidence_contains = expected.get("evidence_contains")
    if evidence_contains and evidence_contains not in str(finding.get("evidence", "")):
        return False
    expected_cwes = set(str(item) for item in expected.get("cwe_references", []))
    if expected_cwes:
        actual_cwes = set(str(item) for item in finding.get("cwe_references", []))
        if not expected_cwes.issubset(actual_cwes):
            return False
    return True


def validate_golden(
    verifier: Any,
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    case_id: str,
) -> dict[str, Any]:
    expected = case["expected"]
    summary = verifier.validate_report(report, fixture_name=f"{case_id}.golden")
    require(report.get("decision") == expected.get("decision"), f"{case_id} decision mismatch.")
    require(report.get("overall_risk") == expected.get("overall_risk"), f"{case_id} risk mismatch.")
    findings = report.get("findings")
    suppressed = report.get("suppressed_low_confidence")
    require(isinstance(findings, list), f"{case_id} findings must be a list.")
    require(isinstance(suppressed, list), f"{case_id} suppressed findings must be a list.")
    for expected_finding in expected.get("required_findings", []):
        require(
            any(isinstance(finding, Mapping) and finding_matches(finding, expected_finding) for finding in findings),
            f"{case_id} missing expected finding: {expected_finding}",
        )
    minimum_suppressed = int(expected.get("minimum_suppressed_low_confidence", 0))
    require(len(suppressed) >= minimum_suppressed, f"{case_id} suppressed count below expected minimum.")
    return {
        "decision": summary["decision"],
        "overall_risk": summary["overall_risk"],
        "finding_count": summary["finding_count"],
        "suppressed_count": summary["suppressed_count"],
    }


def validate_negative_report(verifier: Any, path: Path) -> str:
    payload = read_json(path)
    try:
        verifier.validate_report(payload, fixture_name=path.name)
    except Exception as exc:
        return str(exc)
    raise ReviewAgentEvalHarnessError(f"Negative eval report unexpectedly passed: {path.relative_to(ROOT)}")


def validate_docs() -> dict[str, str]:
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "verify_cognitive_loop_review_agent_eval_harness.py --check",
            "evals/review-agent",
        ],
        "docs/eval-frameworks.md": [
            "cognitive-loop-review-agent-eval-harness-v1",
            "verify_cognitive_loop_review_agent_eval_harness.py --check",
        ],
        "evals/README.md": [
            "Review Agent Eval",
            "verify_cognitive_loop_review_agent_eval_harness.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-eval-harness",
            "python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_eval_harness.py --check",
        ],
        "platform/packs/kimi/README.md": [
            "verify_cognitive_loop_review_agent_eval_harness.py --check",
        ],
        "platform/packs/codex/README.md": [
            "verify_cognitive_loop_review_agent_eval_harness.py --check",
        ],
        "platform/packs/workbuddy/README.md": [
            "verify_cognitive_loop_review_agent_eval_harness.py --check",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing Review Agent eval references: {missing}")
        checked[relative] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    verifier = load_report_verifier()
    cases: dict[str, Any] = {}
    golden: dict[str, Any] = {}
    for case_id in CASE_IDS:
        case = read_json(CASE_DIR / f"{case_id}.json")
        report = read_json(GOLDEN_DIR / f"{case_id}.json")
        cases[case_id] = validate_case(case, case_id=case_id)
        golden[case_id] = validate_golden(verifier, case, report, case_id=case_id)
    negative = {
        name: validate_negative_report(verifier, BAD_DIR / name)
        for name in NEGATIVE_REPORTS
    }
    docs = validate_docs()
    decisions = {item["decision"] for item in golden.values()}
    require(decisions == {"approved", "needs-review", "needs-fix"}, f"Decision coverage drifted: {sorted(decisions)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "case_count": len(cases),
        "cases": cases,
        "golden_reports": golden,
        "negative_reports": negative,
        "docs": docs,
        "quality_gates": {
            "decision_path_coverage": sorted(decisions),
            "critical_security_cwe": "pass",
            "low_confidence_suppression": "pass",
            "privacy_leak_rejection": "pass",
            "synthetic_diff_only": True,
        },
        "privacy": {
            "raw_real_diff_stored_by_study_anything": False,
            "eval_diffs_are_synthetic": True,
            "file_bodies_stored_by_study_anything": False,
            "real_model_keys_stored_by_study_anything": False,
            "private_agent_endpoints_stored_by_study_anything": False,
            "hidden_chain_of_thought_allowed": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check",
            "eval_dir": "evals/review-agent",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-eval-harness.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent eval harness report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent eval harness report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentEvalHarnessError as exc:
        raise SystemExit(f"error: {exc}") from exc
