#!/usr/bin/env python3
"""Verify metadata-only Product Loop Brief Intake Gate artifacts."""

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

from study_anything.core import dual_loop, product_loop_harness  # noqa: E402
import product_loop_brief_intake as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "product-loop-brief-intake"
REPORT = ROOT / "platform" / "generated" / "study-anything-product-loop-brief-intake.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-product-loop-brief-intake.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-product-loop-brief-intake.html"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-brief-intake-receipt-v1.schema.json"
SCENARIO_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-scenario-v1.schema.json"
RUN_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-run-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "created_product_loop_candidate",
        "decision": "create_product_loop_harness_candidate",
        "scenario_created": True,
        "run_created": True,
        "blocked_reasons": [],
    },
    "blocked-missing-brief": {
        "status": "blocked",
        "decision": "block_product_loop_brief_intake",
        "scenario_created": False,
        "run_created": False,
        "blocked_reasons": ["product_spec_eval_brief_missing"],
    },
    "blocked-invalid-brief": {
        "status": "blocked",
        "decision": "block_product_loop_brief_intake",
        "scenario_created": False,
        "run_created": False,
        "blocked_reasons": ["product_spec_eval_brief_invalid"],
    },
    "blocked-missing-developer-vision": {
        "status": "blocked",
        "decision": "block_product_loop_brief_intake",
        "scenario_created": False,
        "run_created": False,
        "blocked_reasons": ["developer_vision_missing"],
    },
    "blocked-external-scope-expansion": {
        "status": "blocked",
        "decision": "block_product_loop_brief_intake",
        "scenario_created": False,
        "run_created": False,
        "blocked_reasons": ["external_feedback_scope_expansion"],
    },
    "blocked-ai-review-only": {
        "status": "blocked",
        "decision": "block_product_loop_brief_intake",
        "scenario_created": False,
        "run_created": False,
        "blocked_reasons": ["ai_review_only_evidence_rejected"],
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_product_loop_brief_intake",
        "scenario_created": False,
        "run_created": False,
        "blocked_reasons": ["production_mutation_rejected"],
    },
    "blocked-skip-to-delivery-harness": {
        "status": "blocked",
        "decision": "block_product_loop_brief_intake",
        "scenario_created": False,
        "run_created": False,
        "blocked_reasons": ["requested_next_boundary_not_product_loop_harness"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report(path: Path, schema_version: str) -> dict[str, str]:
    payload = load_json(path)
    if payload.get("$id") != schema_version:
        raise RuntimeError(f"{path.name} id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
        raise RuntimeError(f"{path.name} schema_version const drifted")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "schema_version": schema_version,
        "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    receipt = gate.validate_receipt(payload)
    expected = EXPECTED[case_id]
    if receipt["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} receipt status drifted")
    if receipt["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} receipt decision drifted")
    scenario_created = receipt["scenario"] is not None
    run_created = receipt["run"] is not None
    if scenario_created is not expected["scenario_created"]:
        raise RuntimeError(f"{case_id} scenario creation drifted")
    if run_created is not expected["run_created"]:
        raise RuntimeError(f"{case_id} run creation drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if case_id == "pass":
        scenario = receipt["scenario"]
        run = receipt["run"]
        if not isinstance(scenario, Mapping) or not isinstance(run, Mapping):
            raise RuntimeError("pass receipt must include Product Loop scenario and run")
        scenario_payload = product_loop_harness.validate_product_loop_scenario(scenario)
        run_payload = product_loop_harness.validate_product_loop_run(run)
        if scenario_payload["source"]["source_type"] != "product_spec_eval_brief":
            raise RuntimeError("pass scenario source must be the Product Spec/Eval brief")
        if run_payload["evidence_refs"]["product_spec_evals_ref"] != "product-spec-eval-brief.json":
            raise RuntimeError("pass run must reference Product Spec/Eval brief as agentic input")
        if run_payload["status"] != "allowed":
            raise RuntimeError("pass Product Loop run must be allowed")
        if run_payload["promotion"]["allowed_next_layer"] != "delivery_trust_harness":
            raise RuntimeError("pass Product Loop run must stop at Delivery Trust Harness")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": list(receipt["blocked_reasons"]),
        "scenario_created": scenario_created,
        "run_created": run_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-product-loop-brief-intake-") as tmp:
        output_dir = Path(tmp) / "brief-intake"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_loop_brief_intake.py"),
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
        dual_loop.assert_metadata_only(stdout, label="product-loop-brief-intake-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Product Loop Brief Intake CLI case order drifted")
        for case_id, expected in cases.items():
            path = output_dir / case_id / "product-loop-brief-intake-receipt.json"
            if not path.is_file():
                raise RuntimeError(f"Product Loop Brief Intake CLI missing fixture: {case_id}")
            if load_json(path) != expected:
                raise RuntimeError(f"Product Loop Brief Intake CLI output drifted: {case_id}")
            scenario_path = output_dir / case_id / "product-loop-scenario.json"
            run_path = output_dir / case_id / "product-loop-run.json"
            if case_id == "pass":
                if not scenario_path.is_file() or not run_path.is_file():
                    raise RuntimeError("Product Loop Brief Intake CLI missing pass scenario/run")
            else:
                if scenario_path.exists() or run_path.exists():
                    raise RuntimeError(f"blocked case must not include scenario/run: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_loop_brief_intake.py"),
                "--brief",
                str(
                    ROOT
                    / "fixtures"
                    / "product-spec-eval-authoring-gate"
                    / "pass"
                    / "product-spec-eval-brief.json"
                ),
                "--output-dir",
                str(custom_output_dir),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        custom_stdout = json.loads(custom_proc.stdout)
        if custom_stdout.get("case_ids") != ["custom"]:
            raise RuntimeError("Product Loop Brief Intake custom CLI output drifted")
        if not (custom_output_dir / "custom" / "product-loop-brief-intake-receipt.json").is_file():
            raise RuntimeError("Product Loop Brief Intake custom CLI missing receipt")


def expect_rejected(name: str, payload: Mapping[str, Any], failures: dict[str, str]) -> None:
    try:
        gate.validate_receipt(payload)
    except Exception as exc:  # noqa: BLE001
        failures[name] = str(exc)


def negative_checks(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    raw_spec = json.loads(dual_loop.dump_json(pass_receipt))
    raw_spec["requested_transition"]["raw_spec_body_requested"] = True
    expect_rejected("raw_spec_body_requested_rejected", raw_spec, failures)

    raw_eval = json.loads(dual_loop.dump_json(pass_receipt))
    raw_eval["scenario"]["loops"]["agentic_coding_loop"]["product_spec_eval_brief_ref"][
        "raw_eval_body"
    ] = "private eval body"
    expect_rejected("raw_eval_body_rejected", raw_eval, failures)

    missing_ref = json.loads(dual_loop.dump_json(pass_receipt))
    missing_ref["scenario"]["loops"]["agentic_coding_loop"]["input_ref"] = "product-spec-evals.json"
    expect_rejected("non_brief_input_ref_rejected", missing_ref, failures)

    production = json.loads(dual_loop.dump_json(pass_receipt))
    production["runtime"]["production_mutation_performed"] = True
    expect_rejected("production_mutation_runtime_rejected", production, failures)

    delivery_skip = json.loads(dual_loop.dump_json(pass_receipt))
    delivery_skip["intake_policy"]["delivery_trust_harness_skip_allowed"] = True
    expect_rejected("delivery_trust_skip_policy_rejected", delivery_skip, failures)

    blocked_with_run = json.loads(dual_loop.dump_json(pass_receipt))
    blocked_with_run["status"] = "blocked"
    blocked_with_run["decision"] = "block_product_loop_brief_intake"
    blocked_with_run["blocked_reasons"] = ["forced_block"]
    expect_rejected("blocked_receipt_with_run_rejected", blocked_with_run, failures)

    ai_review = json.loads(dual_loop.dump_json(pass_receipt))
    ai_review["intake_policy"]["ai_review_only_allowed"] = True
    expect_rejected("ai_review_only_policy_rejected", ai_review, failures)

    required = {
        "raw_spec_body_requested_rejected",
        "raw_eval_body_rejected",
        "non_brief_input_ref_rejected",
        "production_mutation_runtime_rejected",
        "delivery_trust_skip_policy_rejected",
        "blocked_receipt_with_run_rejected",
        "ai_review_only_policy_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Product Loop Brief Intake negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_cases()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Product Loop Brief Intake case summary drifted")
    report["schema_files"] = [
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(SCENARIO_SCHEMA_FILE, product_loop_harness.PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION),
        schema_report(RUN_SCHEMA_FILE, product_loop_harness.PRODUCT_LOOP_RUN_SCHEMA_VERSION),
    ]
    report["negative_checks"] = negative_checks(cases["pass"])
    dual_loop.assert_metadata_only(report, label=gate.REPORT_SCHEMA_VERSION)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Product Loop Brief Intake Gate",
        "",
        "Metadata-only verification that Product Spec/Eval briefs enter the Product Loop Harness without raw spec/eval bodies or executable work.",
        "",
        f"- status: `{report['status']}`",
        f"- created cases: `{report['created_case_count']}`",
        f"- blocked cases: `{report['blocked_case_count']}`",
        f"- scenarios: `{report['scenario_count']}`",
        f"- runs: `{report['run_count']}`",
        "- allowed next boundary: `product_loop_harness`",
        "- Delivery Trust Harness skip: `blocked`",
        "- production mutation: `blocked`",
        "",
        "## Cases",
        "",
    ]
    for case in report["case_reports"]:
        reasons = ", ".join(f"`{reason}`" for reason in case["blocked_reasons"]) or "`none`"
        lines.append(
            f"- `{case['case_id']}`: `{case['status']}` / `{case['decision']}` / scenario: `{case['scenario_created']}` / run: `{case['run_created']}` / reasons: {reasons}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "The gate consumes only a metadata-only brief ID/hash/ref and creates Product Loop Harness candidate artifacts. It does not store raw specs, raw eval bodies, execute work, send customer-visible messages, mutate production, or skip directly to the Delivery Trust Harness.",
            "",
        ]
    )
    return "\n".join(lines)


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    gate.write_cases(FIXTURE_ROOT, cases)


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        path = FIXTURE_ROOT / case_id / "product-loop-brief-intake-receipt.json"
        if not path.is_file():
            raise SystemExit(f"Missing Product Loop Brief Intake fixture: {path}")
        if load_json(path) != payload:
            raise SystemExit(
                f"Product Loop Brief Intake fixture is out of date: {path}. "
                "Run: python3 scripts/verify_product_loop_brief_intake.py --write"
            )
        scenario_path = FIXTURE_ROOT / case_id / "product-loop-scenario.json"
        run_path = FIXTURE_ROOT / case_id / "product-loop-run.json"
        if case_id == "pass":
            if not scenario_path.is_file():
                raise SystemExit(f"Missing Product Loop Brief Intake scenario: {scenario_path}")
            if load_json(scenario_path) != payload["scenario"]:
                raise SystemExit(
                    f"Product Loop Brief Intake scenario is out of date: {scenario_path}. "
                    "Run: python3 scripts/verify_product_loop_brief_intake.py --write"
                )
            if not run_path.is_file():
                raise SystemExit(f"Missing Product Loop Brief Intake run: {run_path}")
            if load_json(run_path) != payload["run"]:
                raise SystemExit(
                    f"Product Loop Brief Intake run is out of date: {run_path}. "
                    "Run: python3 scripts/verify_product_loop_brief_intake.py --write"
                )
        else:
            if scenario_path.exists() or run_path.exists():
                raise SystemExit(f"Blocked Product Loop Brief Intake case must not include scenario/run: {case_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = gate.build_all_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    markdown = render_markdown(report)
    html = dual_loop.render_html_report("Product Loop Brief Intake Gate", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Product Loop Brief Intake report is missing or out of date. "
                "Run: python3 scripts/verify_product_loop_brief_intake.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise SystemExit(
                "Product Loop Brief Intake markdown report is missing or out of date. "
                "Run: python3 scripts/verify_product_loop_brief_intake.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Product Loop Brief Intake HTML report is missing or out of date. "
                "Run: python3 scripts/verify_product_loop_brief_intake.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
