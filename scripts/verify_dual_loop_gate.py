#!/usr/bin/env python3
"""Verify Dual-Loop Propagation Gate pass/fail fixtures."""

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
DUAL_LOOP_MODULE_PATH = ROOT / "apps" / "api" / "study_anything" / "core" / "dual_loop.py"


def _load_dual_loop() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_dual_loop", DUAL_LOOP_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Dual-Loop module: {DUAL_LOOP_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dual_loop = _load_dual_loop()


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-dual-loop-gate.json"
FIXTURE_DIR = ROOT / "fixtures" / "dual-loop"


def run_gate_cli(
    contract_path: Path,
    sandbox_path: Path,
    summary_path: Path | None,
    output_path: Path,
    html_path: Path | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "dual_loop_gate.py"),
        "evaluate",
        "--failure-contract",
        str(contract_path),
        "--sandbox-receipt",
        str(sandbox_path),
        "--output",
        str(output_path),
    ]
    if summary_path:
        command.extend(["--attention-summary", str(summary_path)])
    if html_path:
        command.extend(["--html-output", str(html_path)])
    proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    payload = json.loads(proc.stdout)
    dual_loop.assert_metadata_only(payload, label="dual-loop-gate-cli-stdout")
    return payload


def write_fixture_set(name: str, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target_dir = FIXTURE_DIR / name
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        dual_loop.write_json(target_dir / filename, payload)


def build_gate_cases() -> dict[str, dict[str, Any]]:
    contract = dual_loop.failure_contract_demo()
    sandbox_pass = dual_loop.sandbox_receipt_demo()
    attention_trace = dual_loop.attention_trace_demo()
    attention_summary = dual_loop.attention_summary_demo()
    gate_pass = dual_loop.evaluate_dual_loop_gate(contract, sandbox_pass, attention_summary)

    gate_missing_attention = dual_loop.evaluate_dual_loop_gate(contract, sandbox_pass, None)

    sandbox_risk_blocked = dual_loop.sandbox_receipt_demo(within_budget=False)
    gate_risk_blocked = dual_loop.evaluate_dual_loop_gate(
        contract,
        sandbox_risk_blocked,
        attention_summary,
    )

    return {
        "pass": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_pass,
            "attention-reconstruction-trace.json": attention_trace,
            "attention-reconstruction-summary.json": attention_summary,
            "dual-loop-gate-receipt.json": gate_pass,
        },
        "blocked-missing-attention": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_pass,
            "dual-loop-gate-receipt.json": gate_missing_attention,
        },
        "blocked-risk-budget": {
            "failure-contract.json": contract,
            "sandbox-receipt.json": sandbox_risk_blocked,
            "attention-reconstruction-summary.json": attention_summary,
            "dual-loop-gate-receipt.json": gate_risk_blocked,
        },
    }


def verify_cli_against_cases(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-dual-loop-") as tmp:
        root = Path(tmp)
        for name, artifacts in cases.items():
            case_dir = root / name
            case_dir.mkdir(parents=True)
            for filename, payload in artifacts.items():
                if filename == "dual-loop-gate-receipt.json":
                    continue
                dual_loop.write_json(case_dir / filename, payload)
            summary_path = case_dir / "attention-reconstruction-summary.json"
            run_gate_cli(
                case_dir / "failure-contract.json",
                case_dir / "sandbox-receipt.json",
                summary_path if summary_path.is_file() else None,
                case_dir / "actual-gate.json",
                html_path=case_dir / "actual-gate.html",
            )
            actual = dual_loop.load_json(case_dir / "actual-gate.json")
            expected = artifacts["dual-loop-gate-receipt.json"]
            if actual != expected:
                raise RuntimeError(f"Gate CLI output drifted for case {name}")
            dual_loop.assert_metadata_only(
                (case_dir / "actual-gate.html").read_text(encoding="utf-8"),
                label=f"dual-loop-gate-html:{name}",
            )


def build_report() -> dict[str, Any]:
    cases = build_gate_cases()
    verify_cli_against_cases(cases)
    case_reports: list[dict[str, Any]] = []
    for name, artifacts in cases.items():
        gate = dual_loop.validate_gate_receipt(artifacts["dual-loop-gate-receipt.json"])
        case_reports.append(
            {
                "case_id": name,
                "status": gate["status"],
                "decision": gate["decision"],
                "reasons": gate["reasons"],
                "artifact_count": len(artifacts),
            }
        )
    return {
        "schema_version": dual_loop.DUAL_LOOP_GATE_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "case_reports": case_reports,
        "gate_rules": {
            "sandbox_pass_attention_missing_blocks": True,
            "attention_pass_sandbox_risk_outside_budget_blocks": True,
            "both_loops_equal_weight": True,
            "structured_artifact_bridge_only": True,
        },
        "privacy": {
            **dual_loop.PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
            "raw_failure_or_attention_payloads_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_dual_loop_gate.py --check",
            "cli_command": "python3 scripts/dual_loop_gate.py evaluate --failure-contract ... --sandbox-receipt ... --attention-summary ...",
            "fixture_dir": "fixtures/dual-loop",
        },
    }


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for name, artifacts in cases.items():
        for filename, expected in artifacts.items():
            path = FIXTURE_DIR / name / filename
            if not path.is_file():
                raise SystemExit(f"Missing Dual-Loop gate fixture: {path}")
            if dual_loop.load_json(path) != expected:
                raise SystemExit(
                    f"Dual-Loop gate fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_dual_loop_gate.py --write"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    output = Path(args.output)
    cases = build_gate_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    if args.write:
        for name, artifacts in cases.items():
            write_fixture_set(name, artifacts)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        check_fixtures(cases)
        if not output.is_file():
            raise SystemExit(f"Dual-Loop gate report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Dual-Loop gate report is out of date. "
                "Run: python3 scripts/verify_dual_loop_gate.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
