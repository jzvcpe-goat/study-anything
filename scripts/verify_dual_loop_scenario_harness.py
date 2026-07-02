#!/usr/bin/env python3
"""Verify the Dual Loop Trust Scenario Harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import customer_handoff, delivery_trust, dual_loop  # noqa: E402


RUNNER_PATH = ROOT / "scripts" / "run_dual_loop_scenario_harness.py"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-dual-loop-scenario-harness.json"
FIXTURE_DIR = ROOT / "fixtures" / "dual-loop-scenarios"
CASE_IDS = ("pass", "attention-missing", "risk-over-budget", "both-fail")


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_dual_loop_scenario", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load scenario harness runner: {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _write_fixture_set(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target = FIXTURE_DIR / case_id
    target.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        dual_loop.write_json(target / filename, payload)


def _expected_cases() -> dict[str, dict[str, Any]]:
    cases = runner.build_scenario_cases()
    missing = sorted(set(CASE_IDS) - set(cases))
    if missing:
        raise RuntimeError(f"Scenario harness is missing cases: {missing}")
    return {case_id: cases[case_id] for case_id in CASE_IDS}


def _validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    for filename, payload in artifacts.items():
        dual_loop.assert_metadata_only(payload, label=f"scenario:{case_id}:{filename}")

    contract = dual_loop.validate_failure_contract(artifacts["failure-contract.json"])
    sandbox = dual_loop.validate_sandbox_receipt(artifacts["sandbox-receipt.json"])
    gate = dual_loop.validate_gate_receipt(artifacts["dual-loop-gate-receipt.json"])
    delivery = delivery_trust.validate_delivery_trust_receipt(
        artifacts["delivery-trust-receipt.json"]
    )
    result = artifacts["scenario-result.json"]

    if result.get("schema_version") != runner.SCENARIO_RESULT_SCHEMA_VERSION:
        raise RuntimeError(f"{case_id} scenario result schema drifted")
    if contract["candidate_artifact_ref"] != delivery["candidate_artifact_ref"]:
        raise RuntimeError(f"{case_id} candidate artifact ref mismatch")
    if sandbox["contract_id"] != contract["contract_id"]:
        raise RuntimeError(f"{case_id} sandbox contract mismatch")
    if gate["contract_id"] != contract["contract_id"]:
        raise RuntimeError(f"{case_id} gate contract mismatch")

    observed = result["observed"]
    expected = result["expected"]
    if observed["dual_loop_gate_status"] != expected["gate"]:
        raise RuntimeError(f"{case_id} gate status mismatch")
    if observed["delivery_trust_status"] != expected["delivery"]:
        raise RuntimeError(f"{case_id} delivery trust status mismatch")
    if observed["customer_handoff_package_emitted"] is not expected["handoff_package"]:
        raise RuntimeError(f"{case_id} handoff package emission mismatch")
    for reason in expected["required_reasons"]:
        if reason not in gate["reasons"] and reason not in delivery["reasons"]:
            raise RuntimeError(f"{case_id} missing expected reason: {reason}")

    has_package = "customer-handoff-package.json" in artifacts
    if case_id == "pass":
        if gate["status"] != "allowed" or delivery["status"] != "allowed":
            raise RuntimeError("pass case must allow gate and delivery trust")
        if not has_package:
            raise RuntimeError("pass case must emit a customer handoff package")
        package = customer_handoff.validate_customer_handoff_package(
            artifacts["customer-handoff-package.json"]
        )
        if package["status"] != customer_handoff.PACKAGE_STATUS:
            raise RuntimeError("pass package status drifted")
    else:
        if gate["status"] != "blocked" or delivery["status"] != "blocked":
            raise RuntimeError(f"{case_id} must block gate and delivery trust")
        if has_package:
            raise RuntimeError(f"{case_id} must not emit a customer handoff package")

    if case_id == "attention-missing" and "attention-reconstruction-summary.json" in artifacts:
        raise RuntimeError("attention-missing case must omit attention summary")
    if case_id == "risk-over-budget" and sandbox["risk_budget"]["within_budget"] is not False:
        raise RuntimeError("risk-over-budget case must exceed sandbox risk budget")
    if case_id == "both-fail":
        attention = dual_loop.validate_attention_summary(
            artifacts["attention-reconstruction-summary.json"]
        )
        if attention["status"] != "failed":
            raise RuntimeError("both-fail case must include failed reconstruction")
        if sandbox["status"] == "passed":
            raise RuntimeError("both-fail case must include failed sandbox")

    return {
        "case_id": case_id,
        "gate_status": gate["status"],
        "delivery_trust_status": delivery["status"],
        "customer_handoff_package_emitted": has_package,
        "artifact_count": len(artifacts),
        "gate_reasons": gate["reasons"],
        "delivery_reasons": delivery["reasons"],
    }


def _verify_runner_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-dual-loop-scenario-") as tmp:
        output_dir = Path(tmp) / "scenario-output"
        command = [
            sys.executable,
            str(RUNNER_PATH),
            "run",
            "--case",
            "all",
            "--output-dir",
            str(output_dir),
        ]
        proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
        stdout = json.loads(proc.stdout)
        dual_loop.assert_metadata_only(stdout, label="dual-loop-scenario-runner-stdout")
        if stdout.get("case_ids") != list(CASE_IDS):
            raise RuntimeError(f"runner stdout case order drifted: {stdout.get('case_ids')}")
        for case_id, artifacts in cases.items():
            case_dir = output_dir / case_id
            for filename, expected in artifacts.items():
                actual_path = case_dir / filename
                if not actual_path.is_file():
                    raise RuntimeError(f"runner did not write {case_id}/{filename}")
                actual = _load_json(actual_path)
                if actual != expected:
                    raise RuntimeError(f"runner output drifted for {case_id}/{filename}")
        report_path = output_dir / "dual-loop-scenario-harness-report.json"
        report = _load_json(report_path)
        dual_loop.assert_metadata_only(report, label="dual-loop-scenario-runner-report")
        if report.get("schema_version") != runner.SCENARIO_HARNESS_REPORT_SCHEMA_VERSION:
            raise RuntimeError("runner report schema drifted")


def build_report() -> dict[str, Any]:
    cases = _expected_cases()
    _verify_runner_cli(cases)
    case_reports = [_validate_case(case_id, cases[case_id]) for case_id in CASE_IDS]
    report = runner.build_harness_report(cases)
    if report["case_reports"] != [
        {
            "case_id": item["case_id"],
            "gate_status": item["gate_status"],
            "delivery_trust_status": item["delivery_trust_status"],
            "customer_handoff_package_emitted": item[
                "customer_handoff_package_emitted"
            ],
            "gate_reasons": item["gate_reasons"],
            "artifact_count": item["artifact_count"],
        }
        for item in case_reports
    ]:
        raise RuntimeError("scenario harness report case summary drifted")
    return report


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, expected in artifacts.items():
            path = FIXTURE_DIR / case_id / filename
            if not path.is_file():
                raise SystemExit(f"Missing Dual Loop scenario fixture: {path}")
            if _load_json(path) != expected:
                raise SystemExit(
                    f"Dual Loop scenario fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_dual_loop_scenario_harness.py --write"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    output = Path(args.output)
    cases = _expected_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)

    if args.write:
        for case_id, artifacts in cases.items():
            _write_fixture_set(case_id, artifacts)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not output.is_file():
            raise SystemExit(f"Dual Loop scenario harness report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Dual Loop scenario harness report is out of date. "
                "Run: python3 scripts/verify_dual_loop_scenario_harness.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
