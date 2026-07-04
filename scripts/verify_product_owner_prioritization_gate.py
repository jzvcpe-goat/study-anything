#!/usr/bin/env python3
"""Verify metadata-only Product Owner Prioritization Gate artifacts."""

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
import external_feedback_backlog_bridge as backlog_bridge  # noqa: E402
import product_owner_prioritization_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "product-owner-prioritization-gate"
REPORT = ROOT / "platform" / "generated" / "study-anything-product-owner-prioritization-gate.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-product-owner-prioritization-gate.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-product-owner-prioritization-gate.html"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "product-owner-prioritization-receipt-v1.schema.json"
CANDIDATE_SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "product-spec-eval-candidate-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "queued_for_spec_eval_candidate",
        "decision": "create_product_spec_eval_candidate",
        "candidate_created": True,
        "blocked_reasons": [],
    },
    "blocked-missing-owner-reconstruction": {
        "status": "blocked",
        "decision": "block_product_owner_prioritization",
        "candidate_created": False,
        "blocked_reasons": ["product_owner_reconstruction_missing"],
    },
    "blocked-automatic-priority": {
        "status": "blocked",
        "decision": "block_product_owner_prioritization",
        "candidate_created": False,
        "blocked_reasons": ["automatic_priority_assignment_rejected"],
    },
    "blocked-skip-to-delivery-harness": {
        "status": "blocked",
        "decision": "block_product_owner_prioritization",
        "candidate_created": False,
        "blocked_reasons": ["requested_next_boundary_not_spec_eval_candidate_queue"],
    },
    "blocked-automatic-execution": {
        "status": "blocked",
        "decision": "block_product_owner_prioritization",
        "candidate_created": False,
        "blocked_reasons": ["automatic_execution_rejected"],
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_product_owner_prioritization",
        "candidate_created": False,
        "blocked_reasons": ["production_mutation_rejected"],
    },
    "blocked-customer-visible-action": {
        "status": "blocked",
        "decision": "block_product_owner_prioritization",
        "candidate_created": False,
        "blocked_reasons": ["customer_visible_action_rejected"],
    },
    "blocked-blocked-backlog-source": {
        "status": "blocked",
        "decision": "block_product_owner_prioritization",
        "candidate_created": False,
        "blocked_reasons": ["source_backlog_item_missing"],
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
    candidate_created = receipt["candidate"] is not None
    if candidate_created is not expected["candidate_created"]:
        raise RuntimeError(f"{case_id} candidate creation drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if case_id == "pass":
        candidate = receipt["candidate"]
        if not isinstance(candidate, Mapping):
            raise RuntimeError("pass receipt must include candidate")
        if candidate["destination"] != "product_spec_eval_candidate_queue":
            raise RuntimeError("pass candidate destination drifted")
        if candidate["priority_state"] != "unassigned":
            raise RuntimeError("pass candidate must keep priority unassigned")
        if candidate["ready_for_execution"] is not False:
            raise RuntimeError("pass candidate must not be executable")
        if candidate["ready_for_delivery_trust_harness"] is not False:
            raise RuntimeError("pass candidate must not skip to delivery trust")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": list(receipt["blocked_reasons"]),
        "candidate_created": candidate_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-product-owner-gate-") as tmp:
        output_dir = Path(tmp) / "product-owner-gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_owner_prioritization_gate.py"),
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
        dual_loop.assert_metadata_only(stdout, label="product-owner-prioritization-gate-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Product Owner gate CLI case order drifted")
        for case_id, expected in cases.items():
            path = output_dir / case_id / "product-owner-prioritization-receipt.json"
            if not path.is_file():
                raise RuntimeError(f"Product Owner gate CLI missing fixture: {case_id}")
            if load_json(path) != expected:
                raise RuntimeError(f"Product Owner gate CLI output drifted: {case_id}")
            candidate_path = output_dir / case_id / "product-spec-eval-candidate.json"
            if case_id == "pass" and not candidate_path.is_file():
                raise RuntimeError("Product Owner gate CLI missing pass candidate")
            if case_id != "pass" and candidate_path.exists():
                raise RuntimeError(f"Product Owner gate CLI created candidate for blocked case: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_owner_prioritization_gate.py"),
                "--backlog-item",
                str(ROOT / "fixtures" / "external-feedback-backlog-bridge" / "pass" / "product-loop-backlog-item.json"),
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
            raise RuntimeError("Product Owner gate custom CLI output drifted")
        if not (custom_output_dir / "custom" / "product-owner-prioritization-receipt.json").is_file():
            raise RuntimeError("Product Owner gate custom CLI missing receipt")


def expect_rejected(name: str, payload: Mapping[str, Any], failures: dict[str, str]) -> None:
    try:
        gate.validate_receipt(payload)
    except Exception as exc:  # noqa: BLE001
        failures[name] = str(exc)


def negative_checks(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    identity = json.loads(dual_loop.dump_json(pass_receipt))
    identity["product_owner_reconstruction"]["product_owner_identity"] = "private owner identity"
    expect_rejected("product_owner_identity_rejected", identity, failures)

    priority_score = json.loads(dual_loop.dump_json(pass_receipt))
    priority_score["candidate"]["priority_score"] = 98
    expect_rejected("priority_score_rejected", priority_score, failures)

    raw_spec = json.loads(dual_loop.dump_json(pass_receipt))
    raw_spec["candidate"]["raw_product_spec"] = "private product spec body"
    expect_rejected("raw_product_spec_rejected", raw_spec, failures)

    runtime_priority = json.loads(dual_loop.dump_json(pass_receipt))
    runtime_priority["runtime"]["automatic_priority_assignment_performed"] = True
    expect_rejected("runtime_automatic_priority_rejected", runtime_priority, failures)

    runtime_execution = json.loads(dual_loop.dump_json(pass_receipt))
    runtime_execution["runtime"]["automatic_execution_performed"] = True
    expect_rejected("runtime_automatic_execution_rejected", runtime_execution, failures)

    runtime_mutation = json.loads(dual_loop.dump_json(pass_receipt))
    runtime_mutation["runtime"]["production_mutation_performed"] = True
    expect_rejected("runtime_production_mutation_rejected", runtime_mutation, failures)

    unsafe_candidate = json.loads(dual_loop.dump_json(pass_receipt))
    unsafe_candidate["candidate"]["ready_for_execution"] = True
    expect_rejected("candidate_ready_for_execution_rejected", unsafe_candidate, failures)

    blocked_with_candidate = json.loads(dual_loop.dump_json(pass_receipt))
    blocked_with_candidate["status"] = "blocked"
    blocked_with_candidate["decision"] = "block_product_owner_prioritization"
    blocked_with_candidate["blocked_reasons"] = ["forced_block"]
    expect_rejected("blocked_receipt_with_candidate_rejected", blocked_with_candidate, failures)

    required = {
        "product_owner_identity_rejected",
        "priority_score_rejected",
        "raw_product_spec_rejected",
        "runtime_automatic_priority_rejected",
        "runtime_automatic_execution_rejected",
        "runtime_production_mutation_rejected",
        "candidate_ready_for_execution_rejected",
        "blocked_receipt_with_candidate_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Product Owner gate negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_cases()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Product Owner gate case summary drifted")
    report["schema_files"] = [
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(CANDIDATE_SCHEMA_FILE, gate.CANDIDATE_SCHEMA_VERSION),
    ]
    report["negative_checks"] = negative_checks(cases["pass"])
    report["claim_boundary"]["not_claimed"] = list(gate.CLAIM_BOUNDARY["not_claimed"])
    dual_loop.assert_metadata_only(report, label=gate.REPORT_SCHEMA_VERSION)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Product Owner Prioritization Gate",
        "",
        "Metadata-only verification that Product Loop backlog items stop at Product Owner reconstruction before entering the spec/eval candidate queue.",
        "",
        f"- status: `{report['status']}`",
        f"- queued cases: `{report['queued_case_count']}`",
        f"- blocked cases: `{report['blocked_case_count']}`",
        f"- candidates: `{report['candidate_count']}`",
        "- allowed next boundary: `product_spec_eval_candidate_queue`",
        "- automatic priority assignment: `blocked`",
        "- automatic execution: `blocked`",
        "",
        "## Cases",
        "",
    ]
    for case in report["case_reports"]:
        reasons = ", ".join(f"`{reason}`" for reason in case["blocked_reasons"]) or "`none`"
        lines.append(
            f"- `{case['case_id']}`: `{case['status']}` / `{case['decision']}` / candidate: `{case['candidate_created']}` / reasons: {reasons}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "The gate creates only metadata-only spec/eval candidates. It does not assign priority, execute work, send customer-visible messages, publish externally, mutate production, or skip to the Delivery Trust Harness.",
            "",
        ]
    )
    return "\n".join(lines)


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    gate.write_cases(FIXTURE_ROOT, cases)


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        path = FIXTURE_ROOT / case_id / "product-owner-prioritization-receipt.json"
        if not path.is_file():
            raise SystemExit(f"Missing Product Owner gate fixture: {path}")
        if load_json(path) != payload:
            raise SystemExit(
                f"Product Owner gate fixture is out of date: {path}. "
                "Run: python3 scripts/verify_product_owner_prioritization_gate.py --write"
            )
        candidate_path = FIXTURE_ROOT / case_id / "product-spec-eval-candidate.json"
        if case_id == "pass":
            expected_candidate = payload["candidate"]
            if not candidate_path.is_file():
                raise SystemExit(f"Missing Product Owner gate candidate fixture: {candidate_path}")
            if load_json(candidate_path) != expected_candidate:
                raise SystemExit(
                    f"Product Owner gate candidate fixture is out of date: {candidate_path}. "
                    "Run: python3 scripts/verify_product_owner_prioritization_gate.py --write"
                )
        elif candidate_path.exists():
            raise SystemExit(f"Blocked Product Owner gate case must not include candidate: {candidate_path}")


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
    html = dual_loop.render_html_report("Product Owner Prioritization Gate", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file():
            raise SystemExit(f"Product Owner gate report is missing: {REPORT}")
        if REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Product Owner gate report is out of date. "
                "Run: python3 scripts/verify_product_owner_prioritization_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file():
            raise SystemExit(f"Product Owner gate markdown report is missing: {MARKDOWN_REPORT}")
        if MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise SystemExit(
                "Product Owner gate markdown report is out of date. "
                "Run: python3 scripts/verify_product_owner_prioritization_gate.py --write"
            )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Product Owner gate HTML report is missing: {HTML_REPORT}")
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Product Owner gate HTML report is out of date. "
                "Run: python3 scripts/verify_product_owner_prioritization_gate.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
