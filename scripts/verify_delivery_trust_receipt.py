#!/usr/bin/env python3
"""Verify delivery-trust receipts built from Dual-Loop evidence."""

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

from study_anything.core import delivery_trust, dual_loop  # noqa: E402


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-delivery-trust-receipt.json"
DEFAULT_HTML_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-delivery-trust-receipt.html"
)
FIXTURE_DIR = ROOT / "fixtures" / "delivery-trust"


def run_cli(
    contract_path: Path,
    sandbox_path: Path,
    gate_path: Path,
    summary_path: Path | None,
    output_path: Path,
    html_path: Path | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "delivery_trust_receipt.py"),
        "build",
        "--failure-contract",
        str(contract_path),
        "--sandbox-receipt",
        str(sandbox_path),
        "--dual-loop-gate",
        str(gate_path),
        "--output",
        str(output_path),
    ]
    if summary_path:
        command.extend(["--attention-summary", str(summary_path)])
    if html_path:
        command.extend(["--html-output", str(html_path)])
    proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    payload = json.loads(proc.stdout)
    dual_loop.assert_metadata_only(payload, label="delivery-trust-cli-stdout")
    return payload


def build_cases() -> dict[str, dict[str, Any]]:
    contract = dual_loop.failure_contract_demo()
    sandbox_pass = dual_loop.sandbox_receipt_demo()
    attention_trace = dual_loop.attention_trace_demo()
    attention_summary = dual_loop.attention_summary_demo()
    gate_pass = dual_loop.evaluate_dual_loop_gate(contract, sandbox_pass, attention_summary)
    receipt_pass = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox_pass,
        gate_pass,
        attention_summary,
    )

    gate_missing_attention = dual_loop.evaluate_dual_loop_gate(contract, sandbox_pass, None)
    receipt_missing_attention = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox_pass,
        gate_missing_attention,
        None,
    )

    sandbox_risk_blocked = dual_loop.sandbox_receipt_demo(within_budget=False)
    gate_risk_blocked = dual_loop.evaluate_dual_loop_gate(
        contract,
        sandbox_risk_blocked,
        attention_summary,
    )
    receipt_risk_blocked = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox_risk_blocked,
        gate_risk_blocked,
        attention_summary,
    )

    return {
        "pass": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_pass,
            "attention-reconstruction-trace.json": attention_trace,
            "attention-reconstruction-summary.json": attention_summary,
            "dual-loop-gate-receipt.json": gate_pass,
            "delivery-trust-receipt.json": receipt_pass,
        },
        "blocked-missing-attention": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_pass,
            "dual-loop-gate-receipt.json": gate_missing_attention,
            "delivery-trust-receipt.json": receipt_missing_attention,
        },
        "blocked-risk-budget": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_risk_blocked,
            "attention-reconstruction-summary.json": attention_summary,
            "dual-loop-gate-receipt.json": gate_risk_blocked,
            "delivery-trust-receipt.json": receipt_risk_blocked,
        },
    }


def write_fixture_set(name: str, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target_dir = FIXTURE_DIR / name
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        delivery_trust.write_json(target_dir / filename, payload)


def verify_cli_against_cases(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-delivery-trust-") as tmp:
        root = Path(tmp)
        for name, artifacts in cases.items():
            case_dir = root / name
            case_dir.mkdir(parents=True)
            for filename, payload in artifacts.items():
                if filename == "delivery-trust-receipt.json":
                    continue
                delivery_trust.write_json(case_dir / filename, payload)
            summary_path = case_dir / "attention-reconstruction-summary.json"
            run_cli(
                case_dir / "failure-contract.json",
                case_dir / "sandbox-receipt.json",
                case_dir / "dual-loop-gate-receipt.json",
                summary_path if summary_path.is_file() else None,
                case_dir / "actual-delivery-trust-receipt.json",
                html_path=case_dir / "actual-delivery-trust-receipt.html",
            )
            actual = delivery_trust.load_json(case_dir / "actual-delivery-trust-receipt.json")
            expected = artifacts["delivery-trust-receipt.json"]
            if actual != expected:
                raise RuntimeError(f"Delivery trust CLI output drifted for case {name}")
            dual_loop.assert_metadata_only(
                (case_dir / "actual-delivery-trust-receipt.html").read_text(
                    encoding="utf-8"
                ),
                label=f"delivery-trust-html:{name}",
            )


def exercise_negative_validation(receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    ai_only = json.loads(delivery_trust.dump_json(receipt))
    ai_only["checks"]["no_ai_review_black_box_as_sole_basis"] = False
    try:
        delivery_trust.validate_delivery_trust_receipt(ai_only)
    except Exception as exc:  # noqa: BLE001 - verifier records exact rejection reason.
        failures["ai_review_only_rejected"] = str(exc)

    eval_sufficient = json.loads(delivery_trust.dump_json(receipt))
    eval_sufficient["trust_basis"]["ai_eval_receipts_role"] = "sufficient"
    try:
        delivery_trust.validate_delivery_trust_receipt(eval_sufficient)
    except Exception as exc:  # noqa: BLE001
        failures["ai_eval_sufficient_rejected"] = str(exc)

    no_claim = json.loads(delivery_trust.dump_json(receipt))
    no_claim["claim_boundary"]["current_claim"] = ""
    try:
        delivery_trust.validate_delivery_trust_receipt(no_claim)
    except Exception as exc:  # noqa: BLE001
        failures["missing_claim_boundary_rejected"] = str(exc)

    required = {
        "ai_review_only_rejected",
        "ai_eval_sufficient_rejected",
        "missing_claim_boundary_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Expected delivery trust negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = build_cases()
    verify_cli_against_cases(cases)
    case_reports: list[dict[str, Any]] = []
    for name, artifacts in cases.items():
        receipt = delivery_trust.validate_delivery_trust_receipt(
            artifacts["delivery-trust-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": name,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "reasons": receipt["reasons"],
                "customer_handoff_allowed": receipt["customer_delivery_scope"][
                    "allowed_handoff"
                ],
            }
        )
    negative_checks = exercise_negative_validation(
        cases["pass"]["delivery-trust-receipt.json"]
    )
    return {
        "schema_version": delivery_trust.DELIVERY_TRUST_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "case_reports": case_reports,
        "negative_checks": negative_checks,
        "trust_rules": {
            "dual_loop_gate_required": True,
            "controlled_failure_required": True,
            "active_human_reconstruction_required": True,
            "ai_review_only_forbidden": True,
            "full_manual_re_review_not_required_for_pass": True,
            "production_mutation_blocked": True,
        },
        "privacy": {
            **delivery_trust.DELIVERY_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
            "customer_payloads_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_delivery_trust_receipt.py --check",
            "cli_command": "python3 scripts/delivery_trust_receipt.py build --failure-contract ... --sandbox-receipt ... --dual-loop-gate ... --attention-summary ...",
            "fixture_dir": "fixtures/delivery-trust",
        },
    }


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for name, artifacts in cases.items():
        for filename, expected in artifacts.items():
            path = FIXTURE_DIR / name / filename
            if not path.is_file():
                raise SystemExit(f"Missing delivery trust fixture: {path}")
            if delivery_trust.load_json(path) != expected:
                raise SystemExit(
                    f"Delivery trust fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_delivery_trust_receipt.py --write"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--html-output", default=str(DEFAULT_HTML_REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    html_output = Path(args.html_output)
    cases = build_cases()
    report = build_report()
    serialized = delivery_trust.dump_json(report)
    html = dual_loop.render_html_report("Delivery Trust Receipt Verification", report)
    if args.write:
        for name, artifacts in cases.items():
            write_fixture_set(name, artifacts)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        html_output.parent.mkdir(parents=True, exist_ok=True)
        html_output.write_text(html, encoding="utf-8")
    if args.check:
        check_fixtures(cases)
        if not output.is_file():
            raise SystemExit(f"Delivery trust report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Delivery trust report is out of date. "
                "Run: python3 scripts/verify_delivery_trust_receipt.py --write"
            )
        if not html_output.is_file():
            raise SystemExit(f"Delivery trust HTML report is missing: {html_output}")
        if html_output.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Delivery trust HTML report is out of date. "
                "Run: python3 scripts/verify_delivery_trust_receipt.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
