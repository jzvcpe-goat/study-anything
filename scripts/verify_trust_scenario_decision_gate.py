#!/usr/bin/env python3
"""Verify the metadata-only Trust Scenario Decision Gate."""

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
import trust_scenario_decision_gate as decision_gate  # noqa: E402


REPORT = ROOT / "platform" / "generated" / "study-anything-trust-scenario-decision-gate.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-trust-scenario-decision-gate.html"
FIXTURE_ROOT = ROOT / "fixtures" / "trust-scenario-decision-gate"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"

SCHEMA_VERSION = "trust-scenario-decision-gate-verification-v1"
VERSION = "v0.3.31-alpha"


class TrustScenarioDecisionVerifierError(RuntimeError):
    """Readable Trust Scenario Decision Gate verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TrustScenarioDecisionVerifierError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TrustScenarioDecisionVerifierError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TrustScenarioDecisionVerifierError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def catalog() -> dict[str, Any]:
    return load_json(decision_gate.CATALOG)


def scenario_by_id(catalog_payload: Mapping[str, Any], scenario_id: str) -> Mapping[str, Any]:
    for row in catalog_payload.get("scenarios", []):
        if isinstance(row, Mapping) and row.get("id") == scenario_id:
            return row
    raise TrustScenarioDecisionVerifierError(f"Catalog scenario missing: {scenario_id}")


def decision_cases() -> dict[str, dict[str, Any]]:
    catalog_payload = catalog()
    code_review = scenario_by_id(catalog_payload, "controlled_code_review_handoff")
    client_report = scenario_by_id(catalog_payload, "controlled_client_report_handoff")
    direct_production = scenario_by_id(catalog_payload, "blocked_direct_production_mutation")
    truth_claim = scenario_by_id(catalog_payload, "blocked_certified_truth_claim")

    return {
        "allow-code-review": {
            "scenario_id": "controlled_code_review_handoff",
            "provided_artifacts": list(code_review["required_artifacts"]),
            "active_checkpoints": list(code_review["active_reconstruction_checkpoints"]),
            "requested_shortcuts": [],
            "expected_status": "allowed",
            "expected_decision": "allow_controlled_code_review_handoff",
            "expected_reasons": [],
        },
        "allow-client-report": {
            "scenario_id": "controlled_client_report_handoff",
            "provided_artifacts": list(client_report["required_artifacts"]),
            "active_checkpoints": list(client_report["active_reconstruction_checkpoints"]),
            "requested_shortcuts": [],
            "expected_status": "allowed",
            "expected_decision": "allow_controlled_client_report_handoff",
            "expected_reasons": [],
        },
        "block-missing-artifact": {
            "scenario_id": "controlled_client_report_handoff",
            "provided_artifacts": [
                item for item in client_report["required_artifacts"] if item != "customer-handoff-package-v1"
            ],
            "active_checkpoints": list(client_report["active_reconstruction_checkpoints"]),
            "requested_shortcuts": [],
            "expected_status": "blocked",
            "expected_decision": "block_controlled_client_report_handoff",
            "expected_reasons": ["required_artifacts_missing"],
        },
        "block-forbidden-shortcut": {
            "scenario_id": "controlled_code_review_handoff",
            "provided_artifacts": list(code_review["required_artifacts"]),
            "active_checkpoints": list(code_review["active_reconstruction_checkpoints"]),
            "requested_shortcuts": ["merge_approval"],
            "expected_status": "blocked",
            "expected_decision": "block_controlled_code_review_handoff",
            "expected_reasons": ["forbidden_shortcut_requested"],
        },
        "block-passive-attention": {
            "scenario_id": "controlled_code_review_handoff",
            "provided_artifacts": list(code_review["required_artifacts"]),
            "active_checkpoints": ["failure_boundary_reconstruction"],
            "requested_shortcuts": [],
            "expected_status": "blocked",
            "expected_decision": "block_controlled_code_review_handoff",
            "expected_reasons": ["active_reconstruction_missing"],
        },
        "block-production-mutation": {
            "scenario_id": "blocked_direct_production_mutation",
            "provided_artifacts": list(direct_production.get("required_artifacts", [])),
            "active_checkpoints": list(direct_production["active_reconstruction_checkpoints"]),
            "requested_shortcuts": ["production_mutation"],
            "expected_status": "blocked",
            "expected_decision": "block_direct_production_mutation",
            "expected_reasons": [
                "scenario_not_supported",
                "forbidden_shortcut_requested",
                "autonomy_ceiling_blocks_handoff",
            ],
        },
        "block-truth-certification": {
            "scenario_id": "blocked_certified_truth_claim",
            "provided_artifacts": list(truth_claim.get("required_artifacts", [])),
            "active_checkpoints": list(truth_claim["active_reconstruction_checkpoints"]),
            "requested_shortcuts": ["truth_certification"],
            "expected_status": "blocked",
            "expected_decision": "block_certified_truth_claim",
            "expected_reasons": [
                "scenario_not_supported",
                "forbidden_shortcut_requested",
                "autonomy_ceiling_blocks_handoff",
            ],
        },
    }


def receipt_for_case(case: Mapping[str, Any]) -> dict[str, Any]:
    receipt = decision_gate.evaluate(
        catalog=catalog(),
        scenario_id=str(case["scenario_id"]),
        provided_artifacts=[str(item) for item in case["provided_artifacts"]],
        active_checkpoints=[str(item) for item in case["active_checkpoints"]],
        requested_shortcuts=[str(item) for item in case["requested_shortcuts"]],
    )
    dual_loop.assert_metadata_only(receipt, label=f"trust-scenario-decision:{case['scenario_id']}")
    return receipt


def validate_receipt(case_id: str, case: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != decision_gate.SCHEMA_VERSION:
        raise TrustScenarioDecisionVerifierError(f"{case_id} schema_version drifted")
    if receipt.get("status") != case["expected_status"]:
        raise TrustScenarioDecisionVerifierError(f"{case_id} status drifted")
    if receipt.get("decision") != case["expected_decision"]:
        raise TrustScenarioDecisionVerifierError(f"{case_id} decision drifted")
    for reason in case["expected_reasons"]:
        if reason not in receipt.get("reasons", []):
            raise TrustScenarioDecisionVerifierError(f"{case_id} missing expected reason: {reason}")
    if receipt.get("status") == "allowed" and receipt.get("reasons"):
        raise TrustScenarioDecisionVerifierError(f"{case_id} allowed receipt must not include block reasons")
    privacy = receipt.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise TrustScenarioDecisionVerifierError(f"{case_id} privacy boundary drifted")
    return {
        "case_id": case_id,
        "scenario_id": receipt["scenario_id"],
        "status": receipt["status"],
        "decision": receipt["decision"],
        "reason_count": len(receipt["reasons"]),
        "missing_artifact_count": len(receipt["missing_artifacts"]),
        "blocked_shortcut_count": len(receipt["blocked_shortcuts"]),
    }


def verify_cli(case_id: str, case: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-trust-scenario-decision-") as tmp:
        output = Path(tmp) / "receipt.json"
        html_output = Path(tmp) / "receipt.html"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "trust_scenario_decision_gate.py"),
            "evaluate",
            "--scenario-id",
            str(case["scenario_id"]),
            "--output",
            str(output),
            "--html-output",
            str(html_output),
        ]
        for artifact in case["provided_artifacts"]:
            command.extend(["--provided-artifact", str(artifact)])
        for checkpoint in case["active_checkpoints"]:
            command.extend(["--active-checkpoint", str(checkpoint)])
        for shortcut in case["requested_shortcuts"]:
            command.extend(["--requested-shortcut", str(shortcut)])
        proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
        stdout = json.loads(proc.stdout)
        dual_loop.assert_metadata_only(stdout, label=f"trust-scenario-decision-cli:{case_id}")
        if stdout != expected:
            raise TrustScenarioDecisionVerifierError(f"{case_id} CLI stdout drifted")
        if load_json(output) != expected:
            raise TrustScenarioDecisionVerifierError(f"{case_id} CLI output file drifted")
        dual_loop.assert_metadata_only(
            html_output.read_text(encoding="utf-8"),
            label=f"trust-scenario-decision-html:{case_id}",
        )


def build_report() -> dict[str, Any]:
    release_check_text = RELEASE_CHECK.read_text(encoding="utf-8")
    if "scripts/verify_trust_scenario_decision_gate.py --check" not in release_check_text:
        raise TrustScenarioDecisionVerifierError("Trust Scenario Decision Gate verifier is not wired into release_check.sh")
    cases = decision_cases()
    case_reports: list[dict[str, Any]] = []
    for case_id, case in cases.items():
        receipt = receipt_for_case(case)
        verify_cli(case_id, case, receipt)
        case_reports.append(validate_receipt(case_id, case, receipt))

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "case_count": len(case_reports),
        "allowed_case_count": len([row for row in case_reports if row["status"] == "allowed"]),
        "blocked_case_count": len([row for row in case_reports if row["status"] == "blocked"]),
        "case_reports": case_reports,
        "gate_rules": {
            "supported_scenario_requires_all_artifacts": True,
            "supported_scenario_requires_active_reconstruction": True,
            "forbidden_shortcuts_block": True,
            "unsupported_scenarios_block": True,
            "production_mutation_blocks": True,
            "truth_certification_blocks": True,
            "structured_artifact_bridge_only": True,
        },
        "privacy": dict(decision_gate.PRIVACY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_trust_scenario_decision_gate.py --check",
            "cli_command": "python3 scripts/trust_scenario_decision_gate.py evaluate --scenario-id ...",
            "fixture_dir": "fixtures/trust-scenario-decision-gate",
            "report": REPORT.relative_to(ROOT).as_posix(),
        },
        "claim_boundary": {
            "current_claim": (
                "The gate turns the Trust Scenario Catalog into deterministic local "
                "handoff receipts. It does not prove adoption, factual truth, or "
                "permission to mutate production."
            ),
            "not_claimed": [
                "production approval",
                "customer sending",
                "external publication",
                "truth certification",
                "model quality proof",
            ],
        },
    }
    dual_loop.assert_metadata_only(report, label=SCHEMA_VERSION)
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, case in cases.items():
        target = FIXTURE_ROOT / case_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "input.json").write_text(dual_loop.dump_json(dict(case)), encoding="utf-8")
        (target / "trust-scenario-decision-receipt.json").write_text(
            dual_loop.dump_json(receipt_for_case(case)),
            encoding="utf-8",
        )


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, case in cases.items():
        target = FIXTURE_ROOT / case_id
        expected_input = dual_loop.dump_json(dict(case))
        expected_receipt = dual_loop.dump_json(receipt_for_case(case))
        input_path = target / "input.json"
        receipt_path = target / "trust-scenario-decision-receipt.json"
        if not input_path.is_file() or input_path.read_text(encoding="utf-8") != expected_input:
            raise TrustScenarioDecisionVerifierError(
                f"Trust Scenario Decision input fixture is stale: {input_path}. "
                "Run: python3 scripts/verify_trust_scenario_decision_gate.py --write"
            )
        if not receipt_path.is_file() or receipt_path.read_text(encoding="utf-8") != expected_receipt:
            raise TrustScenarioDecisionVerifierError(
                f"Trust Scenario Decision receipt fixture is stale: {receipt_path}. "
                "Run: python3 scripts/verify_trust_scenario_decision_gate.py --write"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = decision_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    html = dual_loop.render_html_report("Trust Scenario Decision Gate", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != serialized:
            raise TrustScenarioDecisionVerifierError(
                "Trust Scenario Decision Gate report is stale. "
                "Run: python3 scripts/verify_trust_scenario_decision_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise TrustScenarioDecisionVerifierError(
                "Trust Scenario Decision Gate HTML report is stale. "
                "Run: python3 scripts/verify_trust_scenario_decision_gate.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        raise SystemExit(f"verify_trust_scenario_decision_gate failed: {exc}") from exc
