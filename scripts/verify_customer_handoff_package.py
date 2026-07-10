#!/usr/bin/env python3
"""Verify CustomerHandoffPackage contracts, fixtures, and portable zip output."""

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

from study_anything.core import customer_handoff, delivery_trust, dual_loop  # noqa: E402


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-customer-handoff-package.json"
DEFAULT_HTML_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-customer-handoff-package.html"
)
DEFAULT_ZIP = ROOT / "platform" / "generated" / "study-anything-customer-handoff-package.zip"
FIXTURE_DIR = ROOT / "fixtures" / "customer-handoff"


def _deepcopy(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(customer_handoff.dump_json(payload))


def write_fixture_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # This verifier intentionally writes rejected synthetic fixtures under test-only paths.
    # codeql[py/clear-text-storage-sensitive-data]
    path.write_text(customer_handoff.dump_json(payload), encoding="utf-8")


def _dual_loop_pass_artifacts() -> dict[str, dict[str, Any]]:
    contract = dual_loop.failure_contract_demo()
    sandbox = dual_loop.sandbox_receipt_demo()
    attention_trace = dual_loop.attention_trace_demo()
    attention_summary = dual_loop.attention_summary_demo()
    gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention_summary)
    delivery_receipt = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox,
        gate,
        attention_summary,
    )
    package = customer_handoff.build_customer_handoff_package(
        delivery_receipt,
        contract,
        sandbox,
        attention_summary,
        gate,
    )
    return {
        "failure-contract.json": contract,
        "sandbox-receipt.json": sandbox,
        "attention-reconstruction-trace.json": attention_trace,
        "attention-reconstruction-summary.json": attention_summary,
        "dual-loop-gate-receipt.json": gate,
        "delivery-trust-receipt.json": delivery_receipt,
        "customer-handoff-package.json": package,
    }


def build_cases() -> dict[str, dict[str, Any]]:
    pass_case = _dual_loop_pass_artifacts()
    package = pass_case["customer-handoff-package.json"]

    missing_delivery = _deepcopy(package)
    missing_delivery.pop("delivery_trust_receipt")

    scope_expansion = _deepcopy(package)
    scope_expansion["customer_delivery_scope"]["allowed_material_refs"].append(
        "production_deployment_approval"
    )

    missing_claim = _deepcopy(package)
    missing_claim["claim_boundary"]["current_claim"] = ""

    secret_like = _deepcopy(package)
    secret_like["provenance"]["operator_note"] = "api_key: fakefixture"

    return {
        "pass": pass_case,
        "block-missing-delivery-trust": {
            "customer-handoff-package.json": missing_delivery,
            "expected-error.json": {
                "case_id": "block-missing-delivery-trust",
                "expected_error": "customer handoff package missing delivery_trust_receipt",
            },
        },
        "block-scope-expansion": {
            "customer-handoff-package.json": scope_expansion,
            "expected-error.json": {
                "case_id": "block-scope-expansion",
                "expected_error": "customer handoff package scope exceeds delivery trust scope",
            },
        },
        "block-missing-claim-boundary": {
            "customer-handoff-package.json": missing_claim,
            "expected-error.json": {
                "case_id": "block-missing-claim-boundary",
                "expected_error": "customer handoff package must state a current claim",
            },
        },
        "block-secret-like-content": {
            "customer-handoff-package.json": secret_like,
            "expected-error.json": {
                "case_id": "block-secret-like-content",
                "expected_error": "private-looking data",
            },
        },
    }


def write_fixture_set(name: str, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target_dir = FIXTURE_DIR / name
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        write_fixture_json(target_dir / filename, payload)


def run_cli(case_dir: Path, output_path: Path, html_path: Path, zip_path: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "customer_handoff_package.py"),
        "build",
        "--delivery-trust-receipt",
        str(case_dir / "delivery-trust-receipt.json"),
        "--failure-contract",
        str(case_dir / "failure-contract.json"),
        "--sandbox-receipt",
        str(case_dir / "sandbox-receipt.json"),
        "--attention-summary",
        str(case_dir / "attention-reconstruction-summary.json"),
        "--dual-loop-gate",
        str(case_dir / "dual-loop-gate-receipt.json"),
        "--output",
        str(output_path),
        "--html-output",
        str(html_path),
        "--zip-output",
        str(zip_path),
    ]
    proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    payload = json.loads(proc.stdout)
    dual_loop.assert_metadata_only(payload, label="customer-handoff-cli-stdout")
    return payload


def verify_cli_and_zip(pass_case: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-customer-handoff-") as tmp:
        root = Path(tmp)
        case_dir = root / "pass"
        case_dir.mkdir(parents=True)
        for filename, payload in pass_case.items():
            write_fixture_json(case_dir / filename, payload)
        output_path = case_dir / "actual-customer-handoff-package.json"
        html_path = case_dir / "actual-customer-handoff-package.html"
        zip_path = case_dir / "actual-customer-handoff-package.zip"
        actual = run_cli(case_dir, output_path, html_path, zip_path)
        expected = pass_case["customer-handoff-package.json"]
        if actual != expected:
            raise RuntimeError("Customer handoff CLI output drifted")
        html = html_path.read_text(encoding="utf-8")
        dual_loop.assert_metadata_only(html, label="customer-handoff-html")
        offline = customer_handoff.validate_zip_package(zip_path)
        if offline != expected:
            raise RuntimeError("Customer handoff zip offline validation drifted")
        return {
            "json_matches_fixture": True,
            "html_metadata_only": True,
            "zip_validates_offline": True,
            "zip_bytes": zip_path.stat().st_size,
        }


def exercise_negative_validation(package: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    blocked_receipt = _deepcopy(package)
    blocked_receipt["delivery_trust_receipt"]["status"] = "blocked"
    blocked_receipt["delivery_trust_receipt"]["decision"] = "block_customer_handoff"
    blocked_receipt["delivery_trust_receipt"]["customer_delivery_scope"][
        "allowed_handoff"
    ] = False
    try:
        customer_handoff.validate_customer_handoff_package(blocked_receipt)
    except Exception as exc:  # noqa: BLE001 - verifier records the rejection reason.
        failures["blocked_delivery_trust_rejected"] = str(exc)

    missing_delivery = _deepcopy(package)
    missing_delivery.pop("delivery_trust_receipt")
    try:
        customer_handoff.validate_customer_handoff_package(missing_delivery)
    except Exception as exc:  # noqa: BLE001
        failures["missing_delivery_trust_rejected"] = str(exc)

    scope = _deepcopy(package)
    scope["customer_delivery_scope"]["allowed_material_refs"].append(
        "production_deployment_approval"
    )
    try:
        customer_handoff.validate_customer_handoff_package(scope)
    except Exception as exc:  # noqa: BLE001
        failures["scope_expansion_rejected"] = str(exc)

    eval_sufficient = _deepcopy(package)
    eval_sufficient["external_eval_receipts"]["role"] = "sufficient"
    eval_sufficient["external_eval_receipts"]["trust_sufficient"] = True
    try:
        customer_handoff.validate_customer_handoff_package(eval_sufficient)
    except Exception as exc:  # noqa: BLE001
        failures["eval_receipts_sufficient_rejected"] = str(exc)

    no_rollback_high_risk = _deepcopy(package)
    no_rollback_high_risk["provenance"]["risk_level"] = "high"
    no_rollback_high_risk["rollback_strategy"]["available"] = False
    no_rollback_high_risk["rollback_strategy"]["rehearsed"] = False
    try:
        customer_handoff.validate_customer_handoff_package(no_rollback_high_risk)
    except Exception as exc:  # noqa: BLE001
        failures["missing_rollback_high_risk_rejected"] = str(exc)

    no_claim = _deepcopy(package)
    no_claim["claim_boundary"]["current_claim"] = ""
    try:
        customer_handoff.validate_customer_handoff_package(no_claim)
    except Exception as exc:  # noqa: BLE001
        failures["missing_claim_boundary_rejected"] = str(exc)

    secret_like = _deepcopy(package)
    secret_like["provenance"]["operator_note"] = "api_key: fakefixture"
    try:
        customer_handoff.validate_customer_handoff_package(secret_like)
    except Exception as exc:  # noqa: BLE001
        failures["secret_like_content_rejected"] = str(exc)

    digest_mismatch = _deepcopy(package)
    digest_mismatch["limitations"]["not_ai_review_black_box"] = False
    try:
        customer_handoff.validate_customer_handoff_package(digest_mismatch)
    except Exception as exc:  # noqa: BLE001
        failures["artifact_digest_mismatch_rejected"] = str(exc)

    agent_instruction = _deepcopy(package)
    agent_instruction["agent_handoff_instructions"][0]["production_mutation_allowed"] = True
    agent_instruction["agent_handoff_instructions"][0]["scope_escalation_allowed"] = True
    try:
        customer_handoff.validate_customer_handoff_package(agent_instruction)
    except Exception as exc:  # noqa: BLE001
        failures["agent_handoff_scope_escalation_rejected"] = str(exc)

    required = {
        "blocked_delivery_trust_rejected",
        "missing_delivery_trust_rejected",
        "scope_expansion_rejected",
        "eval_receipts_sufficient_rejected",
        "missing_rollback_high_risk_rejected",
        "missing_claim_boundary_rejected",
        "secret_like_content_rejected",
        "artifact_digest_mismatch_rejected",
        "agent_handoff_scope_escalation_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Expected customer handoff negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = build_cases()
    package = customer_handoff.validate_customer_handoff_package(
        cases["pass"]["customer-handoff-package.json"]
    )
    cli_zip = verify_cli_and_zip(cases["pass"])
    negative_checks = exercise_negative_validation(package)
    fixture_reports: list[dict[str, Any]] = []
    for case_id, artifacts in cases.items():
        fixture_package = artifacts["customer-handoff-package.json"]
        if case_id == "pass":
            validated = customer_handoff.validate_customer_handoff_package(fixture_package)
            fixture_reports.append(
                {
                    "case_id": case_id,
                    "status": "pass",
                    "package_status": validated["status"],
                    "customer_handoff_ready": True,
                }
            )
            continue
        expected = artifacts["expected-error.json"]["expected_error"]
        try:
            customer_handoff.validate_customer_handoff_package(fixture_package)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        else:
            raise RuntimeError(f"Expected fixture to fail: {case_id}")
        if expected not in error:
            raise RuntimeError(f"Unexpected error for {case_id}: {error}")
        fixture_reports.append(
            {
                "case_id": case_id,
                "status": "blocked_as_expected",
                "expected_error": expected,
            }
        )
    return {
        "schema_version": customer_handoff.CUSTOMER_HANDOFF_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "package_schema_version": customer_handoff.CUSTOMER_HANDOFF_PACKAGE_SCHEMA_VERSION,
        "package_summary": {
            "package_id": package["package_id"],
            "package_status": package["status"],
            "artifact_count": len(package["manifest"]["artifacts"]),
            "platform_instructions": [
                item["platform_id"] for item in package["agent_handoff_instructions"]
            ],
            "external_eval_role": package["external_eval_receipts"]["role"],
            "customer_delivery_scope": package["customer_delivery_scope"]["scope_id"],
        },
        "fixture_reports": fixture_reports,
        "negative_checks": negative_checks,
        "zip": cli_zip,
        "trust_rules": {
            "delivery_trust_required": True,
            "delivery_trust_must_be_allowed": True,
            "cannot_expand_customer_scope": True,
            "external_eval_receipts_supporting_only": True,
            "claim_boundary_required": True,
            "rollback_required_for_high_risk": True,
            "agent_handoff_cannot_mutate_or_escalate": True,
            "automatic_customer_sending_forbidden": True,
        },
        "privacy": {
            **customer_handoff.PACKAGE_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_customer_handoff_package.py --check",
            "cli_command": "python3 scripts/customer_handoff_package.py build --delivery-trust-receipt ... --zip-output ...",
            "fixture_dir": "fixtures/customer-handoff",
            "zip_output": "platform/generated/study-anything-customer-handoff-package.zip",
        },
        "claim_boundary": {
            "current_claim": (
                "This package is consistent with the scoped local deterministic "
                "DeliveryTrustReceipt and referenced Dual Loop evidence."
            ),
            "not_claimed": [
                "production approval",
                "legal certification",
                "compliance certification",
                "security certification",
                "general model correctness",
            ],
        },
    }


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for name, artifacts in cases.items():
        for filename, expected in artifacts.items():
            path = FIXTURE_DIR / name / filename
            if not path.is_file():
                raise SystemExit(f"Missing customer handoff fixture: {path}")
            if customer_handoff.load_json(path) != expected:
                raise SystemExit(
                    f"Customer handoff fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_customer_handoff_package.py --write"
                )


def write_outputs(
    report_path: Path,
    html_path: Path,
    zip_path: Path,
    report: Mapping[str, Any],
    package: Mapping[str, Any],
) -> None:
    serialized = customer_handoff.dump_json(report)
    html = dual_loop.render_html_report("Customer Handoff Package Verification", report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(serialized, encoding="utf-8")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    customer_handoff.write_zip_package(
        zip_path,
        package,
        customer_handoff.render_html_report("Customer Handoff Package", package),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--html-output", default=str(DEFAULT_HTML_REPORT))
    parser.add_argument("--zip-output", default=str(DEFAULT_ZIP))
    args = parser.parse_args()

    output = Path(args.output)
    html_output = Path(args.html_output)
    zip_output = Path(args.zip_output)
    cases = build_cases()
    report = build_report()
    package = cases["pass"]["customer-handoff-package.json"]
    serialized = customer_handoff.dump_json(report)
    html = dual_loop.render_html_report("Customer Handoff Package Verification", report)

    if args.write:
        for name, artifacts in cases.items():
            write_fixture_set(name, artifacts)
        write_outputs(output, html_output, zip_output, report, package)
    if args.check:
        check_fixtures(cases)
        if not output.is_file():
            raise SystemExit(f"Customer handoff report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Customer handoff report is out of date. "
                "Run: python3 scripts/verify_customer_handoff_package.py --write"
            )
        if not html_output.is_file():
            raise SystemExit(f"Customer handoff HTML report is missing: {html_output}")
        if html_output.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Customer handoff HTML report is out of date. "
                "Run: python3 scripts/verify_customer_handoff_package.py --write"
            )
        if not zip_output.is_file():
            raise SystemExit(f"Customer handoff zip is missing: {zip_output}")
        customer_handoff.validate_zip_package(zip_output)
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
