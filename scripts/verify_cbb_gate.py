#!/usr/bin/env python3
"""Verify the Cognitive Black Box deterministic delivery gate."""

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

from study_anything.core import cbb_protocol, dual_loop  # noqa: E402


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-gate.json"
FIXTURE_DIR = ROOT / "fixtures" / "cbb-protocol"
CASE_IDS = (
    "safe-controlled-handoff",
    "missing-claim-boundary",
    "reviewer-not-qualified",
    "recipient-risk-unknown",
    "ai-review-only-rejected",
)
EXPECTED = {
    "safe-controlled-handoff": {
        "status": "allowed",
        "decision": "allow_controlled_customer_handoff",
        "required_reasons": [],
    },
    "missing-claim-boundary": {
        "status": "blocked",
        "decision": "block_delivery",
        "required_reasons": ["claim_boundary_missing"],
    },
    "reviewer-not-qualified": {
        "status": "blocked",
        "decision": "block_delivery",
        "required_reasons": ["reviewer_not_qualified"],
    },
    "recipient-risk-unknown": {
        "status": "blocked",
        "decision": "block_delivery",
        "required_reasons": ["recipient_risk_unknown"],
    },
    "ai-review-only-rejected": {
        "status": "blocked",
        "decision": "block_delivery",
        "required_reasons": ["ai_review_only_trust_basis"],
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _write_fixture_set(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target = FIXTURE_DIR / case_id
    target.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        cbb_protocol.write_json(target / filename, payload)


def build_cases() -> dict[str, dict[str, Any]]:
    return {case_id: cbb_protocol.build_case_artifacts(case_id) for case_id in CASE_IDS}


def _validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    for filename, payload in artifacts.items():
        dual_loop.assert_metadata_only(payload, label=f"cbb:{case_id}:{filename}")

    decision = cbb_protocol.validate_delivery_decision_receipt(
        artifacts["delivery-decision-receipt.json"]
    )
    expected = EXPECTED[case_id]
    if decision["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if decision["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["required_reasons"]:
        if reason not in decision["reasons"]:
            raise RuntimeError(f"{case_id} missing expected reason: {reason}")
    if case_id == "safe-controlled-handoff":
        cbb_protocol.validate_claim_boundary(artifacts["claim-boundary.json"])
        cbb_protocol.validate_trust_root(artifacts["trust-root.json"])
        cbb_protocol.validate_reviewer_reconstruction_receipt(
            artifacts["reviewer-reconstruction-receipt.json"]
        )
        cbb_protocol.validate_risk_owner_scope(artifacts["risk-owner-scope.json"])
    return {
        "case_id": case_id,
        "status": decision["status"],
        "decision": decision["decision"],
        "reasons": decision["reasons"],
        "artifact_count": len(artifacts),
        "customer_handoff_allowed": decision["status"] == "allowed",
    }


def _verify_gate_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-cbb-gate-") as tmp:
        root = Path(tmp)
        for case_id, artifacts in cases.items():
            case_dir = root / case_id
            case_dir.mkdir(parents=True)
            for filename, payload in artifacts.items():
                if filename == "delivery-decision-receipt.json":
                    continue
                cbb_protocol.write_json(case_dir / filename, payload)
            output_path = case_dir / "actual-delivery-decision-receipt.json"
            html_path = case_dir / "actual-delivery-decision-receipt.html"
            command = [
                sys.executable,
                str(ROOT / "scripts" / "cbb_gate.py"),
                "evaluate",
                "--claim-boundary",
                str(case_dir / "claim-boundary.json"),
                "--trust-root",
                str(case_dir / "trust-root.json"),
                "--reviewer-reconstruction",
                str(case_dir / "reviewer-reconstruction-receipt.json"),
                "--risk-owner-scope",
                str(case_dir / "risk-owner-scope.json"),
                "--output",
                str(output_path),
                "--html-output",
                str(html_path),
            ]
            proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
            stdout = json.loads(proc.stdout)
            dual_loop.assert_metadata_only(stdout, label=f"cbb-gate-cli:{case_id}")
            actual = _load_json(output_path)
            if actual != artifacts["delivery-decision-receipt.json"]:
                raise RuntimeError(f"CBB gate CLI output drifted for {case_id}")
            dual_loop.assert_metadata_only(
                html_path.read_text(encoding="utf-8"),
                label=f"cbb-gate-html:{case_id}",
            )


def _verify_protocol_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-cbb-protocol-") as tmp:
        output_dir = Path(tmp) / "protocol-output"
        for case_id, artifacts in cases.items():
            command = [
                sys.executable,
                str(ROOT / "scripts" / "cbb_protocol_cli.py"),
                "demo",
                "--case",
                case_id,
                "--output-dir",
                str(output_dir),
                "--html",
            ]
            proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
            stdout = json.loads(proc.stdout)
            dual_loop.assert_metadata_only(stdout, label=f"cbb-protocol-cli:{case_id}")
            case_dir = output_dir / case_id
            for filename, expected in artifacts.items():
                actual = _load_json(case_dir / filename)
                if actual != expected:
                    raise RuntimeError(f"CBB protocol CLI output drifted for {case_id}")


def build_report() -> dict[str, Any]:
    cases = build_cases()
    _verify_gate_cli(cases)
    _verify_protocol_cli(cases)
    case_reports = [_validate_case(case_id, cases[case_id]) for case_id in CASE_IDS]
    report = {
        "schema_version": cbb_protocol.CBB_GATE_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "case_reports": case_reports,
        "trust_rules": {
            "claim_boundary_required": True,
            "trust_root_required": True,
            "reviewer_reconstruction_required": True,
            "risk_owner_scope_required": True,
            "ai_review_only_blocks": True,
            "recipient_risk_unknown_blocks": True,
            "neither_ai_review_nor_manual_recheck_is_sufficient_alone": True,
        },
        "privacy": {
            **cbb_protocol.CBB_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
            "real_customer_data_included": False,
            "raw_customer_payload_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "claim_boundary": {
            "current_claim": (
                "The deterministic CBB gate permits controlled handoff only when "
                "all protocol receipts satisfy the local reference kernel."
            ),
            "not_claimed": [
                "production readiness",
                "real customer acceptance",
                "legal certification",
                "general model correctness",
            ],
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cbb_gate.py --check",
            "cli_command": "python3 scripts/cbb_gate.py evaluate --claim-boundary ... --trust-root ... --reviewer-reconstruction ... --risk-owner-scope ...",
            "fixture_dir": "fixtures/cbb-protocol",
        },
    }
    dual_loop.assert_metadata_only(report, label="cbb-gate-report")
    return report


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, expected in artifacts.items():
            path = FIXTURE_DIR / case_id / filename
            if not path.is_file():
                raise SystemExit(f"Missing CBB fixture: {path}")
            if _load_json(path) != expected:
                raise SystemExit(
                    f"CBB fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_cbb_gate.py --write"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = build_cases()
    report = build_report()
    serialized = cbb_protocol.dump_json(report)
    output = Path(args.output)
    if args.write:
        for case_id, artifacts in cases.items():
            _write_fixture_set(case_id, artifacts)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        check_fixtures(cases)
        if not output.is_file():
            raise SystemExit(f"CBB gate report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "CBB gate report is out of date. "
                "Run: python3 scripts/verify_cbb_gate.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
