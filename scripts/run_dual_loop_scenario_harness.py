#!/usr/bin/env python3
"""Run deterministic Dual Loop trust scenarios for customer handoff readiness."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import customer_handoff, delivery_trust, dual_loop  # noqa: E402


SCENARIO_RESULT_SCHEMA_VERSION = "dual-loop-trust-scenario-result-v1"
SCENARIO_HARNESS_REPORT_SCHEMA_VERSION = "dual-loop-trust-scenario-harness-v1"
DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "dual-loop-scenario-harness"

CASE_IDS = ("pass", "attention-missing", "risk-over-budget", "both-fail")


def _customer_delivery_contract() -> dict[str, Any]:
    contract = dual_loop.failure_contract_demo()
    contract["task_ref"] = "task:customer-delivery-readiness"
    contract["candidate_artifact_ref"] = "artifact:customer-handoff-candidate-metadata"
    contract["failure_boundaries"]["rollback_strategy_ref"] = (
        "rollback:customer-handoff-candidate-withdrawal"
    )
    contract["risk"]["score"] = 0.47
    return dual_loop.validate_failure_contract(contract)


def _sandbox_failed_receipt() -> dict[str, Any]:
    receipt = dual_loop.sandbox_receipt_demo(within_budget=False, status="failed")
    receipt["observed_failures"] = [
        {
            "failure_id": "failure-customer-delivery-boundary-001",
            "category": "sandbox_command_failed",
            "containment_status": "escaped_sandbox_boundary",
            "reversible": True,
            "propagated": True,
            "artifact_ref": "artifact:blocked-customer-delivery-boundary",
        }
    ]
    receipt["risk_budget"]["observed_level"] = "high"
    receipt["rollback"]["rollback_ref"] = "rollback:customer-handoff-candidate-withdrawal"
    return dual_loop.validate_sandbox_receipt(receipt)


def _rekey_sandbox(receipt: Mapping[str, Any]) -> dict[str, Any]:
    sandbox = dict(receipt)
    sandbox["rollback"] = dict(receipt["rollback"])
    sandbox["rollback"]["rollback_ref"] = "rollback:customer-handoff-candidate-withdrawal"
    return dual_loop.validate_sandbox_receipt(sandbox)


def _scenario_result(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    gate = dual_loop.validate_gate_receipt(artifacts["dual-loop-gate-receipt.json"])
    delivery_receipt = delivery_trust.validate_delivery_trust_receipt(
        artifacts["delivery-trust-receipt.json"]
    )
    package = artifacts.get("customer-handoff-package.json")
    customer_handoff_ready = package is not None
    if customer_handoff_ready:
        customer_handoff.validate_customer_handoff_package(package)

    expected = {
        "pass": {
            "gate": "allowed",
            "delivery": "allowed",
            "handoff_package": True,
            "required_reasons": [],
        },
        "attention-missing": {
            "gate": "blocked",
            "delivery": "blocked",
            "handoff_package": False,
            "required_reasons": ["attention_reconstruction_missing"],
        },
        "risk-over-budget": {
            "gate": "blocked",
            "delivery": "blocked",
            "handoff_package": False,
            "required_reasons": ["sandbox_risk_outside_budget"],
        },
        "both-fail": {
            "gate": "blocked",
            "delivery": "blocked",
            "handoff_package": False,
            "required_reasons": [
                "sandbox_failures_not_contained",
                "attention_reconstruction_failed",
            ],
        },
    }[case_id]

    refs = [
        {"path": path, "kind": path.removesuffix(".json")}
        for path in sorted(artifacts)
    ]
    result = {
        "schema_version": SCENARIO_RESULT_SCHEMA_VERSION,
        "case_id": case_id,
        "scenario_id": "customer_delivery_readiness",
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "trust_question": (
            "May this AI-generated customer handoff candidate be promoted inside the "
            "controlled local scope?"
        ),
        "status": "pass",
        "expected": expected,
        "observed": {
            "dual_loop_gate_status": gate["status"],
            "delivery_trust_status": delivery_receipt["status"],
            "customer_handoff_package_emitted": customer_handoff_ready,
            "gate_reasons": gate["reasons"],
            "delivery_reasons": delivery_receipt["reasons"],
            "customer_handoff_candidate_allowed": customer_handoff_ready,
        },
        "artifact_refs": refs,
        "claim_boundary": {
            "current_claim": (
                "This deterministic metadata-only scenario proves local Dual Loop "
                "promotion behavior for a controlled customer handoff candidate."
            ),
            "not_claimed": [
                "production deployment approval",
                "real customer delivery",
                "general model correctness",
                "legal compliance certification",
                "security certification",
            ],
        },
        "non_production_statement": (
            "The harness performs no model calls, starts no daemon, sends nothing to "
            "customers, and mutates no production system."
        ),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": {
            **customer_handoff.PACKAGE_PRIVACY_FLAGS,
            "metadata_only": True,
            "scenario_fixture_only": True,
        },
    }
    dual_loop.assert_metadata_only(result, label=f"scenario-result:{case_id}")
    return result


def build_scenario_cases() -> dict[str, dict[str, Any]]:
    contract = _customer_delivery_contract()
    sandbox_pass = _rekey_sandbox(dual_loop.sandbox_receipt_demo())
    attention_trace = dual_loop.attention_trace_demo()
    attention_summary = dual_loop.attention_summary_demo()
    gate_pass = dual_loop.evaluate_dual_loop_gate(contract, sandbox_pass, attention_summary)
    delivery_pass = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox_pass,
        gate_pass,
        attention_summary,
    )
    package_pass = customer_handoff.build_customer_handoff_package(
        delivery_pass,
        contract,
        sandbox_pass,
        attention_summary,
        gate_pass,
    )

    gate_attention_missing = dual_loop.evaluate_dual_loop_gate(contract, sandbox_pass, None)
    delivery_attention_missing = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox_pass,
        gate_attention_missing,
        None,
    )

    sandbox_risk = _rekey_sandbox(dual_loop.sandbox_receipt_demo(within_budget=False))
    gate_risk = dual_loop.evaluate_dual_loop_gate(contract, sandbox_risk, attention_summary)
    delivery_risk = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox_risk,
        gate_risk,
        attention_summary,
    )

    sandbox_failed = _sandbox_failed_receipt()
    attention_failed = dual_loop.attention_summary_demo(status="failed")
    gate_both_fail = dual_loop.evaluate_dual_loop_gate(
        contract,
        sandbox_failed,
        attention_failed,
    )
    delivery_both_fail = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox_failed,
        gate_both_fail,
        attention_failed,
    )

    cases = {
        "pass": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_pass,
            "attention-reconstruction-trace.json": attention_trace,
            "attention-reconstruction-summary.json": attention_summary,
            "dual-loop-gate-receipt.json": gate_pass,
            "delivery-trust-receipt.json": delivery_pass,
            "customer-handoff-package.json": package_pass,
        },
        "attention-missing": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_pass,
            "dual-loop-gate-receipt.json": gate_attention_missing,
            "delivery-trust-receipt.json": delivery_attention_missing,
        },
        "risk-over-budget": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_risk,
            "attention-reconstruction-trace.json": attention_trace,
            "attention-reconstruction-summary.json": attention_summary,
            "dual-loop-gate-receipt.json": gate_risk,
            "delivery-trust-receipt.json": delivery_risk,
        },
        "both-fail": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_failed,
            "attention-reconstruction-summary.json": attention_failed,
            "dual-loop-gate-receipt.json": gate_both_fail,
            "delivery-trust-receipt.json": delivery_both_fail,
        },
    }
    for case_id, artifacts in cases.items():
        artifacts["scenario-result.json"] = _scenario_result(case_id, artifacts)
    return cases


def _write_case(case_dir: Path, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        dual_loop.write_json(case_dir / filename, payload)


def build_harness_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in cases:
        artifacts = cases[case_id]
        result = artifacts["scenario-result.json"]
        observed = result["observed"]
        case_reports.append(
            {
                "case_id": case_id,
                "gate_status": observed["dual_loop_gate_status"],
                "delivery_trust_status": observed["delivery_trust_status"],
                "customer_handoff_package_emitted": observed[
                    "customer_handoff_package_emitted"
                ],
                "gate_reasons": observed["gate_reasons"],
                "artifact_count": len(artifacts),
            }
        )
    report = {
        "schema_version": SCENARIO_HARNESS_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "scenario_id": "customer_delivery_readiness",
        "case_reports": case_reports,
        "trust_rules": {
            "controlled_failure_loop_required": True,
            "human_attention_reconstruction_required": True,
            "dual_loop_gate_required": True,
            "pass_emits_customer_handoff_package": True,
            "blocked_cases_do_not_emit_customer_handoff_package": True,
            "neither_loop_may_dominate": True,
        },
        "privacy": {
            **customer_handoff.PACKAGE_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
            "model_calls_performed": False,
            "production_mutation_performed": False,
            "real_customer_data_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "acceptance": {
            "runner_command": "python3 scripts/run_dual_loop_scenario_harness.py run --case all",
            "minimum_command": "python3 scripts/verify_dual_loop_scenario_harness.py --check",
            "fixture_dir": "fixtures/dual-loop-scenarios",
        },
        "claim_boundary": {
            "current_claim": (
                "The deterministic harness proves local Dual Loop promotion behavior "
                "for one customer delivery scenario class."
            ),
            "not_claimed": [
                "production readiness",
                "real customer acceptance",
                "model correctness",
                "AI self-review sufficiency",
            ],
        },
    }
    dual_loop.assert_metadata_only(report, label="dual-loop-scenario-harness-report")
    return report


def write_scenarios(output_dir: Path, selected_case: str) -> dict[str, Any]:
    cases = build_scenario_cases()
    selected = CASE_IDS if selected_case == "all" else (selected_case,)
    for case_id in selected:
        _write_case(output_dir / case_id, cases[case_id])
    report = build_harness_report({case_id: cases[case_id] for case_id in selected})
    if selected_case == "all":
        dual_loop.write_json(output_dir / "dual-loop-scenario-harness-report.json", report)
    return {
        "schema_version": "dual-loop-scenario-harness-cli-result-v1",
        "status": "pass",
        "output_dir_ref": output_dir.name,
        "case_ids": list(selected),
        "case_count": len(selected),
        "report_schema_version": SCENARIO_HARNESS_REPORT_SCHEMA_VERSION,
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--case", choices=("all", *CASE_IDS), default="all")
    run_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))

    args = parser.parse_args()
    if args.command == "run":
        result = write_scenarios(Path(args.output_dir), args.case)
        print(dual_loop.dump_json(result), end="")
        return 0
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
