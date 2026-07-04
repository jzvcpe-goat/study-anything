#!/usr/bin/env python3
"""Verify Spec/Eval Scenario Execution Rehearsal artifacts."""

from __future__ import annotations

import argparse
import copy
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
import spec_eval_scenario_execution_rehearsal as rehearsal  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "spec-eval-scenario-execution-rehearsal"
REPORT = ROOT / "platform" / "generated" / "study-anything-spec-eval-scenario-execution-rehearsal.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-spec-eval-scenario-execution-rehearsal.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-spec-eval-scenario-execution-rehearsal.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "spec-eval-scenario-execution-rehearsal-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "allowed",
        "decision": "start_sandboxed_implementation_rehearsal",
        "blocked_reasons": [],
        "sandbox_start_authorized": True,
    },
    "blocked-missing-sandbox": {
        "status": "blocked",
        "decision": "block_spec_eval_execution",
        "blocked_reasons": ["controlled_failure_sandbox_missing"],
        "sandbox_start_authorized": False,
    },
    "blocked-missing-human-reconstruction": {
        "status": "blocked",
        "decision": "block_spec_eval_execution",
        "blocked_reasons": ["human_reconstruction_missing", "attention_reconstruction_missing"],
        "sandbox_start_authorized": False,
    },
    "blocked-ai-review-only": {
        "status": "blocked",
        "decision": "block_spec_eval_execution",
        "blocked_reasons": ["ai_review_only_evidence_rejected"],
        "sandbox_start_authorized": False,
    },
    "blocked-customer-visible-action": {
        "status": "blocked",
        "decision": "block_spec_eval_execution",
        "blocked_reasons": ["customer_visible_action_rejected"],
        "sandbox_start_authorized": False,
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_spec_eval_execution",
        "blocked_reasons": ["production_mutation_rejected"],
        "sandbox_start_authorized": False,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != rehearsal.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Spec/Eval rehearsal schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != rehearsal.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Spec/Eval rehearsal schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": rehearsal.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    acceptance = rehearsal.validate_acceptance_receipt(artifacts["spec-eval-acceptance-receipt.json"])
    execution = rehearsal.validate_execution_receipt(artifacts["spec-eval-execution-rehearsal-receipt.json"])
    expected = EXPECTED[case_id]
    if execution["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if execution["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in execution["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if execution["execution_boundary"]["sandbox_start_authorized"] is not expected["sandbox_start_authorized"]:
        raise RuntimeError(f"{case_id} sandbox authorization drifted")
    if case_id == "pass":
        if acceptance["status"] != "passed":
            raise RuntimeError("pass acceptance receipt must pass")
        required = [
            "failure-contract.json",
            "sandbox-receipt.json",
            "attention-reconstruction-trace.json",
            "attention-reconstruction-summary.json",
            "dual-loop-gate-receipt.json",
        ]
        for name in required:
            if name not in artifacts:
                raise RuntimeError(f"pass case missing {name}")
        gate = artifacts["dual-loop-gate-receipt.json"]
        if gate["status"] != "allowed":
            raise RuntimeError("pass Dual Loop gate must allow sandbox promotion")
    if case_id == "blocked-missing-sandbox" and "sandbox-receipt.json" in artifacts:
        raise RuntimeError("missing-sandbox case must not write sandbox receipt")
    for payload in artifacts.values():
        dual_loop.assert_metadata_only(payload, label=f"spec-eval-rehearsal:{case_id}")
    return {
        "case_id": case_id,
        "status": execution["status"],
        "decision": execution["decision"],
        "blocked_reasons": execution["blocked_reasons"],
        "artifact_count": len(artifacts),
        "sandbox_start_authorized": execution["execution_boundary"]["sandbox_start_authorized"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-spec-eval-rehearsal-") as tmp:
        output_dir = Path(tmp) / "rehearsal"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "spec_eval_scenario_execution_rehearsal.py"),
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
        dual_loop.assert_metadata_only(stdout, label="spec-eval-rehearsal-cli")
        if stdout.get("case_ids") != list(rehearsal.CASE_IDS):
            raise RuntimeError("Spec/Eval rehearsal CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Spec/Eval rehearsal CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Spec/Eval rehearsal CLI output drifted: {case_id}/{filename}")


def negative_fixtures(pass_execution: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_execution)
        mutator(payload)
        try:
            rehearsal.validate_execution_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "implementation_execution_performed",
        lambda payload: payload["execution_boundary"].__setitem__("implementation_execution_performed", True),
    )
    expect_rejected(
        "customer_visible_action_performed",
        lambda payload: payload["execution_boundary"].__setitem__("customer_visible_action_performed", True),
    )
    expect_rejected(
        "production_mutation_performed",
        lambda payload: payload["execution_boundary"].__setitem__("production_mutation_performed", True),
    )
    expect_rejected(
        "missing_sandbox_gate_on_allowed",
        lambda payload: payload["checks"].__setitem__("controlled_failure_sandbox_present", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = rehearsal.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in rehearsal.CASE_IDS]
    report = rehearsal.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Spec/Eval rehearsal report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass"]["spec-eval-execution-rehearsal-receipt.json"]
    )
    rehearsal._validate_privacy(report, label=rehearsal.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        rehearsal.write_artifact_set(FIXTURE_ROOT / case_id, artifacts)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing Spec/Eval rehearsal fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Spec/Eval rehearsal fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_spec_eval_scenario_execution_rehearsal.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Spec/Eval Scenario Execution Rehearsal",
        "",
        "Metadata-only proof that Product Spec/Eval execution can start only inside a controlled failure sandbox after active human boundary reconstruction.",
        "",
        f"- status: `{report['status']}`",
        f"- schema: `{report['schema_version']}`",
        f"- cases: `{len(report['case_reports'])}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"]["current_claim"],
        "",
        "Not claimed:",
    ]
    lines.extend(f"- {item}" for item in report["claim_boundary"]["not_claimed"])
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    for row in report["case_reports"]:
        reasons = ", ".join(row["blocked_reasons"]) or "none"
        lines.append(f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / reasons: {reasons}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = rehearsal.build_all_case_artifacts()
    report = build_report()
    serialized = rehearsal.dump_json(report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown_report(report), encoding="utf-8")
        dual_loop.write_html_report(HTML_REPORT, "Spec/Eval Scenario Execution Rehearsal", report)

    if args.check:
        check_fixtures(cases)
        for path, expected in (
            (REPORT, serialized),
            (MARKDOWN_REPORT, markdown_report(report)),
        ):
            if not path.is_file():
                raise SystemExit(f"Spec/Eval rehearsal report missing: {path}")
            if path.read_text(encoding="utf-8") != expected:
                raise SystemExit(
                    "Spec/Eval rehearsal report is out of date. "
                    "Run: python3 scripts/verify_spec_eval_scenario_execution_rehearsal.py --write"
                )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Spec/Eval rehearsal HTML report missing: {HTML_REPORT}")

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
