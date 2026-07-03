#!/usr/bin/env python3
"""Verify the metadata-only Delivery Trust Case Harness."""

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

from study_anything.core import delivery_trust_case, dual_loop  # noqa: E402


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-delivery-trust-case-harness.json"
DEFAULT_HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-delivery-trust-case-harness.html"
FIXTURE_ROOT = ROOT / "fixtures" / "delivery-trust-case"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "delivery-trust-case-v1.schema.json"

EXPECTED_REASONS = {
    "pass": [],
    "blocked-product-loop": ["product_loop_not_passed", "developer_vision_missing"],
    "blocked-dual-loop": [
        "dual_loop_gate_blocked",
        "sandbox_risk_outside_budget",
        "delivery_trust_not_allowed",
        "customer_handoff_not_ready",
    ],
    "blocked-customer-handoff": [
        "customer_handoff_not_ready",
        "customer_handoff_scope_expansion",
    ],
    "blocked-ai-review-only": [
        "product_loop_not_passed",
        "ai_review_only_evidence_rejected",
    ],
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _expected_cases() -> dict[str, dict[str, dict[str, Any]]]:
    return delivery_trust_case.build_all_case_artifacts()


def _schema_report() -> dict[str, str]:
    if not SCHEMA_FILE.is_file():
        raise RuntimeError(f"Delivery Trust Case schema missing: {SCHEMA_FILE}")
    payload = _load_json(SCHEMA_FILE)
    if payload.get("$id") != delivery_trust_case.DELIVERY_TRUST_CASE_SCHEMA_VERSION:
        raise RuntimeError("Delivery Trust Case schema id drifted")
    if (
        payload.get("properties", {})
        .get("schema_version", {})
        .get("const")
        != delivery_trust_case.DELIVERY_TRUST_CASE_SCHEMA_VERSION
    ):
        raise RuntimeError("Delivery Trust Case schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": delivery_trust_case.DELIVERY_TRUST_CASE_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def _validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    for filename, payload in artifacts.items():
        dual_loop.assert_metadata_only(payload, label=f"delivery-trust-case:{case_id}:{filename}")
    case = delivery_trust_case.validate_delivery_trust_case(
        artifacts["delivery-trust-case.json"]
    )
    if case_id == "pass":
        if case["status"] != "ready_for_controlled_customer_handoff":
            raise RuntimeError("pass case must be ready")
        if case["decision"] != "allow_controlled_customer_handoff":
            raise RuntimeError("pass case must allow controlled handoff")
        if case["reasons"]:
            raise RuntimeError("pass case must have no blocking reasons")
    else:
        if case["status"] != "blocked":
            raise RuntimeError(f"{case_id} must be blocked")
        if case["decision"] != "block_customer_handoff":
            raise RuntimeError(f"{case_id} must block customer handoff")
    for reason in EXPECTED_REASONS[case_id]:
        if reason not in case["reasons"]:
            raise RuntimeError(f"{case_id} missing expected reason: {reason}")
    if case_id == "blocked-customer-handoff":
        summary = case["customer_handoff_summary"]
        if summary.get("error_code") != "customer_handoff_scope_expansion":
            raise RuntimeError("customer handoff negative fixture must block scope expansion")
    if case_id == "blocked-dual-loop":
        if "customer-handoff-package.json" in artifacts:
            raise RuntimeError("blocked dual-loop case must not emit customer handoff package")
    return {
        "case_id": case_id,
        "status": case["status"],
        "decision": case["decision"],
        "reasons": case["reasons"],
        "layer_statuses": case["layer_statuses"],
        "artifact_count": len(artifacts),
    }


def _verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-delivery-trust-case-") as tmp:
        output_dir = Path(tmp) / "case-harness"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "delivery_trust_case_harness.py"),
                "run",
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
        dual_loop.assert_metadata_only(stdout, label="delivery-trust-case-cli-run")
        if stdout.get("case_ids") != list(delivery_trust_case.CASE_IDS):
            raise RuntimeError("Delivery Trust Case CLI case order drifted")
        for case_id, artifacts in cases.items():
            for filename, expected in artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Delivery Trust Case CLI missing {case_id}/{filename}")
                if _load_json(path) != expected:
                    raise RuntimeError(f"Delivery Trust Case CLI output drifted for {case_id}/{filename}")

        pass_dir = output_dir / "pass"
        build_output = Path(tmp) / "built-delivery-trust-case.json"
        html_output = Path(tmp) / "built-delivery-trust-case.html"
        build_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "delivery_trust_case_harness.py"),
                "build",
                "--product-loop-run",
                str(pass_dir / "product-loop-run.json"),
                "--dual-loop-gate",
                str(pass_dir / "dual-loop-gate-receipt.json"),
                "--delivery-trust-receipt",
                str(pass_dir / "delivery-trust-receipt.json"),
                "--customer-handoff-package",
                str(pass_dir / "customer-handoff-package.json"),
                "--case-id",
                "pass",
                "--output",
                str(build_output),
                "--html-output",
                str(html_output),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        stdout_build = json.loads(build_proc.stdout)
        dual_loop.assert_metadata_only(stdout_build, label="delivery-trust-case-cli-build")
        if _load_json(build_output) != cases["pass"]["delivery-trust-case.json"]:
            raise RuntimeError("Delivery Trust Case build CLI output drifted")
        dual_loop.assert_metadata_only(
            html_output.read_text(encoding="utf-8"),
            label="delivery-trust-case-html",
        )


def _exercise_negative_validation(case: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    ai_only = json.loads(dual_loop.dump_json(case))
    ai_only["checks"]["no_ai_review_black_box_as_sole_basis"] = False
    try:
        delivery_trust_case.validate_delivery_trust_case(ai_only)
    except Exception as exc:  # noqa: BLE001
        failures["ai_review_only_rejected"] = str(exc)

    eval_sufficient = json.loads(dual_loop.dump_json(case))
    eval_sufficient["checks"]["external_eval_receipts_supporting_only"] = False
    try:
        delivery_trust_case.validate_delivery_trust_case(eval_sufficient)
    except Exception as exc:  # noqa: BLE001
        failures["eval_sufficiency_rejected"] = str(exc)

    auto_send = json.loads(dual_loop.dump_json(case))
    auto_send["customer_delivery_scope"]["automatic_customer_sending_allowed"] = True
    try:
        delivery_trust_case.validate_delivery_trust_case(auto_send)
    except Exception as exc:  # noqa: BLE001
        failures["automatic_customer_sending_rejected"] = str(exc)

    no_claim = json.loads(dual_loop.dump_json(case))
    no_claim["claim_boundary"]["current_claim"] = ""
    try:
        delivery_trust_case.validate_delivery_trust_case(no_claim)
    except Exception as exc:  # noqa: BLE001
        failures["missing_claim_boundary_rejected"] = str(exc)

    required = {
        "ai_review_only_rejected",
        "eval_sufficiency_rejected",
        "automatic_customer_sending_rejected",
        "missing_claim_boundary_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Expected delivery trust case negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = _expected_cases()
    _verify_cli(cases)
    case_reports = [
        _validate_case(case_id, cases[case_id])
        for case_id in delivery_trust_case.CASE_IDS
    ]
    report = delivery_trust_case.build_harness_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Delivery Trust Case report case summary drifted")
    report["schema_files"] = [_schema_report()]
    report["negative_checks"] = _exercise_negative_validation(
        cases["pass"]["delivery-trust-case.json"]
    )
    dual_loop.assert_metadata_only(report, label="delivery-trust-case-harness-report")
    return report


def _write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        delivery_trust_case.write_artifact_set(FIXTURE_ROOT / case_id, artifacts)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            path = FIXTURE_ROOT / case_id / filename
            if not path.is_file():
                raise SystemExit(f"Missing Delivery Trust Case fixture: {path}")
            if _load_json(path) != payload:
                raise SystemExit(
                    f"Delivery Trust Case fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_delivery_trust_case_harness.py --write"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--html-output", default=str(DEFAULT_HTML_REPORT))
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = _expected_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    html = dual_loop.render_html_report("Delivery Trust Case Harness", report)
    output = Path(args.output)
    html_output = Path(args.html_output)

    if args.write:
        _write_fixtures(cases)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        html_output.parent.mkdir(parents=True, exist_ok=True)
        html_output.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not output.is_file():
            raise SystemExit(f"Delivery Trust Case report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Delivery Trust Case report is out of date. "
                "Run: python3 scripts/verify_delivery_trust_case_harness.py --write"
            )
        if not html_output.is_file():
            raise SystemExit(f"Delivery Trust Case HTML report is missing: {html_output}")
        if html_output.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Delivery Trust Case HTML report is out of date. "
                "Run: python3 scripts/verify_delivery_trust_case_harness.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
