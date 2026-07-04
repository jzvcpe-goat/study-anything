#!/usr/bin/env python3
"""Verify metadata-only Product Spec/Eval Authoring Gate artifacts."""

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
import product_spec_eval_authoring_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "product-spec-eval-authoring-gate"
REPORT = ROOT / "platform" / "generated" / "study-anything-product-spec-eval-authoring-gate.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-product-spec-eval-authoring-gate.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-product-spec-eval-authoring-gate.html"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "product-spec-eval-authoring-receipt-v1.schema.json"
BRIEF_SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "product-spec-eval-brief-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "authored_spec_eval_brief",
        "decision": "create_product_spec_eval_brief",
        "brief_created": True,
        "blocked_reasons": [],
    },
    "blocked-missing-authoring-reconstruction": {
        "status": "blocked",
        "decision": "block_product_spec_eval_authoring",
        "brief_created": False,
        "blocked_reasons": ["authoring_reconstruction_missing"],
    },
    "blocked-raw-spec-body": {
        "status": "blocked",
        "decision": "block_product_spec_eval_authoring",
        "brief_created": False,
        "blocked_reasons": ["raw_spec_body_rejected"],
    },
    "blocked-automatic-execution": {
        "status": "blocked",
        "decision": "block_product_spec_eval_authoring",
        "brief_created": False,
        "blocked_reasons": ["automatic_execution_rejected"],
    },
    "blocked-skip-to-delivery-harness": {
        "status": "blocked",
        "decision": "block_product_spec_eval_authoring",
        "brief_created": False,
        "blocked_reasons": ["requested_next_boundary_not_product_loop_harness_candidate"],
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_product_spec_eval_authoring",
        "brief_created": False,
        "blocked_reasons": ["production_mutation_rejected"],
    },
    "blocked-customer-visible-action": {
        "status": "blocked",
        "decision": "block_product_spec_eval_authoring",
        "brief_created": False,
        "blocked_reasons": ["customer_visible_action_rejected"],
    },
    "blocked-invalid-candidate-source": {
        "status": "blocked",
        "decision": "block_product_spec_eval_authoring",
        "brief_created": False,
        "blocked_reasons": ["source_candidate_invalid"],
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
    brief_created = receipt["brief"] is not None
    if brief_created is not expected["brief_created"]:
        raise RuntimeError(f"{case_id} brief creation drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if case_id == "pass":
        brief = receipt["brief"]
        if not isinstance(brief, Mapping):
            raise RuntimeError("pass receipt must include brief")
        if brief["destination"] != "product_spec_eval_brief":
            raise RuntimeError("pass brief destination drifted")
        if brief["ready_for_product_loop_harness"] is not True:
            raise RuntimeError("pass brief must be ready only for product loop harness")
        if brief["ready_for_execution"] is not False:
            raise RuntimeError("pass brief must not be executable")
        if brief["ready_for_delivery_trust_harness"] is not False:
            raise RuntimeError("pass brief must not skip to delivery trust")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": list(receipt["blocked_reasons"]),
        "brief_created": brief_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-spec-eval-gate-") as tmp:
        output_dir = Path(tmp) / "spec-eval-gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_spec_eval_authoring_gate.py"),
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
        dual_loop.assert_metadata_only(stdout, label="product-spec-eval-authoring-gate-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Product Spec/Eval gate CLI case order drifted")
        for case_id, expected in cases.items():
            path = output_dir / case_id / "product-spec-eval-authoring-receipt.json"
            if not path.is_file():
                raise RuntimeError(f"Product Spec/Eval gate CLI missing fixture: {case_id}")
            if load_json(path) != expected:
                raise RuntimeError(f"Product Spec/Eval gate CLI output drifted: {case_id}")
            brief_path = output_dir / case_id / "product-spec-eval-brief.json"
            if case_id == "pass" and not brief_path.is_file():
                raise RuntimeError("Product Spec/Eval gate CLI missing pass brief")
            if case_id != "pass" and brief_path.exists():
                raise RuntimeError(f"Product Spec/Eval gate CLI created brief for blocked case: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_spec_eval_authoring_gate.py"),
                "--candidate",
                str(
                    ROOT
                    / "fixtures"
                    / "product-owner-prioritization-gate"
                    / "pass"
                    / "product-spec-eval-candidate.json"
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
            raise RuntimeError("Product Spec/Eval gate custom CLI output drifted")
        if not (custom_output_dir / "custom" / "product-spec-eval-authoring-receipt.json").is_file():
            raise RuntimeError("Product Spec/Eval gate custom CLI missing receipt")


def expect_rejected(name: str, payload: Mapping[str, Any], failures: dict[str, str]) -> None:
    try:
        gate.validate_receipt(payload)
    except Exception as exc:  # noqa: BLE001
        failures[name] = str(exc)


def negative_checks(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    raw_spec = json.loads(dual_loop.dump_json(pass_receipt))
    raw_spec["brief"]["raw_product_spec"] = "private product spec body"
    expect_rejected("raw_product_spec_rejected", raw_spec, failures)

    raw_eval = json.loads(dual_loop.dump_json(pass_receipt))
    raw_eval["brief"]["eval_plan_refs"][0]["eval_prompt"] = "private eval prompt"
    expect_rejected("eval_prompt_rejected", raw_eval, failures)

    raw_criteria = json.loads(dual_loop.dump_json(pass_receipt))
    raw_criteria["brief"]["acceptance_criteria_refs"][0]["acceptance_criteria_text"] = "private criterion"
    expect_rejected("acceptance_criteria_text_rejected", raw_criteria, failures)

    execution = json.loads(dual_loop.dump_json(pass_receipt))
    execution["brief"]["ready_for_execution"] = True
    expect_rejected("brief_ready_for_execution_rejected", execution, failures)

    delivery = json.loads(dual_loop.dump_json(pass_receipt))
    delivery["brief"]["ready_for_delivery_trust_harness"] = True
    expect_rejected("brief_delivery_trust_skip_rejected", delivery, failures)

    runtime_execution = json.loads(dual_loop.dump_json(pass_receipt))
    runtime_execution["runtime"]["automatic_execution_performed"] = True
    expect_rejected("runtime_automatic_execution_rejected", runtime_execution, failures)

    runtime_mutation = json.loads(dual_loop.dump_json(pass_receipt))
    runtime_mutation["runtime"]["production_mutation_performed"] = True
    expect_rejected("runtime_production_mutation_rejected", runtime_mutation, failures)

    blocked_with_brief = json.loads(dual_loop.dump_json(pass_receipt))
    blocked_with_brief["status"] = "blocked"
    blocked_with_brief["decision"] = "block_product_spec_eval_authoring"
    blocked_with_brief["blocked_reasons"] = ["forced_block"]
    expect_rejected("blocked_receipt_with_brief_rejected", blocked_with_brief, failures)

    required = {
        "raw_product_spec_rejected",
        "eval_prompt_rejected",
        "acceptance_criteria_text_rejected",
        "brief_ready_for_execution_rejected",
        "brief_delivery_trust_skip_rejected",
        "runtime_automatic_execution_rejected",
        "runtime_production_mutation_rejected",
        "blocked_receipt_with_brief_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Product Spec/Eval gate negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_cases()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Product Spec/Eval gate case summary drifted")
    report["schema_files"] = [
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(BRIEF_SCHEMA_FILE, gate.BRIEF_SCHEMA_VERSION),
    ]
    report["negative_checks"] = negative_checks(cases["pass"])
    dual_loop.assert_metadata_only(report, label=gate.REPORT_SCHEMA_VERSION)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Product Spec/Eval Authoring Gate",
        "",
        "Metadata-only verification that spec/eval candidates can become bounded briefs without raw spec or eval bodies.",
        "",
        f"- status: `{report['status']}`",
        f"- authored cases: `{report['authored_case_count']}`",
        f"- blocked cases: `{report['blocked_case_count']}`",
        f"- briefs: `{report['brief_count']}`",
        "- allowed next boundary: `product_loop_harness_candidate`",
        "- raw spec/eval bodies: `blocked`",
        "- automatic execution: `blocked`",
        "",
        "## Cases",
        "",
    ]
    for case in report["case_reports"]:
        reasons = ", ".join(f"`{reason}`" for reason in case["blocked_reasons"]) or "`none`"
        lines.append(
            f"- `{case['case_id']}`: `{case['status']}` / `{case['decision']}` / brief: `{case['brief_created']}` / reasons: {reasons}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "The gate creates only metadata-only spec/eval briefs. It does not store raw specs, raw eval bodies, assign priority, execute work, send customer-visible messages, publish externally, mutate production, or skip to the Delivery Trust Harness.",
            "",
        ]
    )
    return "\n".join(lines)


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    gate.write_cases(FIXTURE_ROOT, cases)


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        path = FIXTURE_ROOT / case_id / "product-spec-eval-authoring-receipt.json"
        if not path.is_file():
            raise SystemExit(f"Missing Product Spec/Eval gate fixture: {path}")
        if load_json(path) != payload:
            raise SystemExit(
                f"Product Spec/Eval gate fixture is out of date: {path}. "
                "Run: python3 scripts/verify_product_spec_eval_authoring_gate.py --write"
            )
        brief_path = FIXTURE_ROOT / case_id / "product-spec-eval-brief.json"
        if case_id == "pass":
            expected_brief = payload["brief"]
            if not brief_path.is_file():
                raise SystemExit(f"Missing Product Spec/Eval gate brief fixture: {brief_path}")
            if load_json(brief_path) != expected_brief:
                raise SystemExit(
                    f"Product Spec/Eval gate brief fixture is out of date: {brief_path}. "
                    "Run: python3 scripts/verify_product_spec_eval_authoring_gate.py --write"
                )
        elif brief_path.exists():
            raise SystemExit(f"Blocked Product Spec/Eval gate case must not include brief: {brief_path}")


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
    html = dual_loop.render_html_report("Product Spec/Eval Authoring Gate", report)

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
                "Product Spec/Eval gate report is missing or out of date. "
                "Run: python3 scripts/verify_product_spec_eval_authoring_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise SystemExit(
                "Product Spec/Eval gate markdown report is missing or out of date. "
                "Run: python3 scripts/verify_product_spec_eval_authoring_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Product Spec/Eval gate HTML report is missing or out of date. "
                "Run: python3 scripts/verify_product_spec_eval_authoring_gate.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
