#!/usr/bin/env python3
"""Verify the metadata-only Code Review Delivery Class handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import dual_loop  # noqa: E402
import code_review_delivery_class_handoff as code_review  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "code-review-delivery-class"
REPORT = ROOT / "platform" / "generated" / "study-anything-code-review-delivery-class.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-code-review-delivery-class.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "code-review-handoff-case-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "ready_for_controlled_code_review_handoff",
        "decision": "allow_controlled_code_review_handoff",
        "reasons": [],
    },
    "blocked-missing-reconstruction": {
        "status": "blocked",
        "decision": "block_code_review_handoff",
        "reasons": ["human_reconstruction_missing"],
    },
    "blocked-unsafe-diff-scope": {
        "status": "blocked",
        "decision": "block_code_review_handoff",
        "reasons": ["sandbox_risk_outside_budget", "diff_scope_expansion"],
    },
    "blocked-ai-review-only": {
        "status": "blocked",
        "decision": "block_code_review_handoff",
        "reasons": ["product_loop_not_passed", "ai_review_only_evidence_rejected"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != code_review.SCHEMA_VERSION:
        raise RuntimeError("Code Review handoff schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != code_review.SCHEMA_VERSION:
        raise RuntimeError("Code Review handoff schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": code_review.SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    case = code_review.validate_case(payload)
    expected = EXPECTED[case_id]
    if case["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if case["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["reasons"]:
        if reason not in case["reasons"]:
            raise RuntimeError(f"{case_id} missing reason: {reason}")
    if case_id == "pass" and case["reasons"]:
        raise RuntimeError("pass case must not include block reasons")
    return {
        "case_id": case_id,
        "status": case["status"],
        "decision": case["decision"],
        "reasons": case["reasons"],
        "source_scope": case["source_change_ref"]["scope_class"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-code-review-handoff-") as tmp:
        output_dir = Path(tmp) / "code-review"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "code_review_delivery_class_handoff.py"),
                "--case",
                "all",
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        stdout = json.loads(proc.stdout)
        dual_loop.assert_metadata_only(stdout, label="code-review-delivery-class-cli")
        if stdout.get("case_ids") != list(code_review.CASE_IDS):
            raise RuntimeError("Code Review CLI case order drifted")
        for case_id, expected in cases.items():
            path = output_dir / case_id / "code-review-handoff-case.json"
            if not path.is_file():
                raise RuntimeError(f"Code Review CLI missing fixture: {case_id}")
            if load_json(path) != expected:
                raise RuntimeError(f"Code Review CLI output drifted: {case_id}")


def negative_checks(pass_case: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    raw_diff = json.loads(dual_loop.dump_json(pass_case))
    raw_diff["source_change_ref"]["raw_diff"] = "diff --git private"
    try:
        code_review.validate_case(raw_diff)
    except Exception as exc:  # noqa: BLE001
        failures["raw_diff_rejected"] = str(exc)

    auto_comment = json.loads(dual_loop.dump_json(pass_case))
    auto_comment["checks"]["automatic_pr_commenting_allowed"] = True
    try:
        code_review.validate_case(auto_comment)
    except Exception as exc:  # noqa: BLE001
        failures["automatic_pr_commenting_rejected"] = str(exc)

    eval_sufficient = json.loads(dual_loop.dump_json(pass_case))
    eval_sufficient["checks"]["external_eval_receipts_supporting_only"] = False
    try:
        code_review.validate_case(eval_sufficient)
    except Exception as exc:  # noqa: BLE001
        failures["eval_sufficient_alone_rejected"] = str(exc)

    mutation = json.loads(dual_loop.dump_json(pass_case))
    mutation["checks"]["production_mutation_allowed"] = True
    try:
        code_review.validate_case(mutation)
    except Exception as exc:  # noqa: BLE001
        failures["production_mutation_rejected"] = str(exc)

    required = {
        "raw_diff_rejected",
        "automatic_pr_commenting_rejected",
        "eval_sufficient_alone_rejected",
        "production_mutation_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Code Review negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = code_review.build_all_cases()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in code_review.CASE_IDS]
    report = code_review.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Code Review report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_checks"] = negative_checks(cases["pass"])
    report["claim_boundary"]["not_claimed"] = list(code_review.CLAIM_BOUNDARY["not_claimed"])
    dual_loop.assert_metadata_only(report, label=code_review.REPORT_SCHEMA_VERSION)
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    code_review.write_cases(FIXTURE_ROOT, cases)


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        path = FIXTURE_ROOT / case_id / "code-review-handoff-case.json"
        if not path.is_file():
            raise SystemExit(f"Missing Code Review fixture: {path}")
        if load_json(path) != payload:
            raise SystemExit(
                f"Code Review fixture is out of date: {path}. "
                "Run: python3 scripts/verify_code_review_delivery_class_handoff.py --write"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = code_review.build_all_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    html = dual_loop.render_html_report("Code Review Delivery Class", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file():
            raise SystemExit(f"Code Review report is missing: {REPORT}")
        if REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Code Review report is out of date. "
                "Run: python3 scripts/verify_code_review_delivery_class_handoff.py --write"
            )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Code Review HTML report is missing: {HTML_REPORT}")
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Code Review HTML report is out of date. "
                "Run: python3 scripts/verify_code_review_delivery_class_handoff.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
