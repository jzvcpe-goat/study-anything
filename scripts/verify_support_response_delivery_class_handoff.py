#!/usr/bin/env python3
"""Verify the metadata-only Support Response Delivery Class handoff."""

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
import support_response_delivery_class_handoff as support_response  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "support-response-delivery-class"
REPORT = ROOT / "platform" / "generated" / "study-anything-support-response-delivery-class.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-support-response-delivery-class.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "support-response-handoff-case-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "ready_for_controlled_support_response_handoff",
        "decision": "allow_controlled_support_response_handoff",
        "reasons": [],
    },
    "blocked-missing-reconstruction": {
        "status": "blocked",
        "decision": "block_support_response_handoff",
        "reasons": ["human_reconstruction_missing"],
    },
    "blocked-risk-over-budget": {
        "status": "blocked",
        "decision": "block_support_response_handoff",
        "reasons": ["sandbox_risk_outside_budget"],
    },
    "blocked-unbounded-recipient": {
        "status": "blocked",
        "decision": "block_support_response_handoff",
        "reasons": ["recipient_scope_unbounded"],
    },
    "blocked-policy-gap": {
        "status": "blocked",
        "decision": "block_support_response_handoff",
        "reasons": ["support_policy_scope_missing"],
    },
    "blocked-ai-summary-only": {
        "status": "blocked",
        "decision": "block_support_response_handoff",
        "reasons": ["product_loop_not_passed", "ai_summary_only_evidence_rejected"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != support_response.SCHEMA_VERSION:
        raise RuntimeError("Support Response handoff schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != support_response.SCHEMA_VERSION:
        raise RuntimeError("Support Response handoff schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": support_response.SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    case = support_response.validate_case(payload)
    expected = EXPECTED[case_id]
    if case["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if case["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["reasons"]:
        if reason not in case["reasons"]:
            raise RuntimeError(f"{case_id} missing reason: {reason}")
    if case_id == "pass" and case["reasons"]:
        raise RuntimeError("pass case must not include block reasons")
    return {
        "case_id": case_id,
        "status": case["status"],
        "decision": case["decision"],
        "reasons": case["reasons"],
        "recipient_class": case["recipient_context_ref"]["recipient_class"],
        "risk_observed_level": case["risk_budget"]["observed_level"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-support-response-handoff-") as tmp:
        output_dir = Path(tmp) / "support-response"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "support_response_delivery_class_handoff.py"),
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
        dual_loop.assert_metadata_only(stdout, label="support-response-delivery-class-cli")
        if stdout.get("case_ids") != list(support_response.CASE_IDS):
            raise RuntimeError("Support Response CLI case order drifted")
        for case_id, expected in cases.items():
            path = output_dir / case_id / "support-response-handoff-case.json"
            if not path.is_file():
                raise RuntimeError(f"Support Response CLI missing fixture: {case_id}")
            if load_json(path) != expected:
                raise RuntimeError(f"Support Response CLI output drifted: {case_id}")


def negative_checks(pass_case: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    raw_report = json.loads(dual_loop.dump_json(pass_case))
    raw_report["report_artifact_ref"]["raw_response_text"] = "raw support reply body"
    try:
        support_response.validate_case(raw_report)
    except Exception as exc:  # noqa: BLE001
        failures["raw_response_text_rejected"] = str(exc)

    raw_customer = json.loads(dual_loop.dump_json(pass_case))
    raw_customer["recipient_context_ref"]["raw_ticket_payload"] = "private support ticket"
    try:
        support_response.validate_case(raw_customer)
    except Exception as exc:  # noqa: BLE001
        failures["raw_ticket_payload_rejected"] = str(exc)

    user_identity = json.loads(dual_loop.dump_json(pass_case))
    user_identity["recipient_context_ref"]["requester_identity"] = "private requester identity"
    try:
        support_response.validate_case(user_identity)
    except Exception as exc:  # noqa: BLE001
        failures["requester_identity_rejected"] = str(exc)

    auto_send = json.loads(dual_loop.dump_json(pass_case))
    auto_send["checks"]["automatic_customer_sending_allowed"] = True
    try:
        support_response.validate_case(auto_send)
    except Exception as exc:  # noqa: BLE001
        failures["automatic_customer_sending_rejected"] = str(exc)

    eval_sufficient = json.loads(dual_loop.dump_json(pass_case))
    eval_sufficient["checks"]["external_eval_receipts_supporting_only"] = False
    try:
        support_response.validate_case(eval_sufficient)
    except Exception as exc:  # noqa: BLE001
        failures["eval_sufficient_alone_rejected"] = str(exc)

    publication = json.loads(dual_loop.dump_json(pass_case))
    publication["handoff_controls"]["publish_external_allowed"] = True
    try:
        support_response.validate_case(publication)
    except Exception as exc:  # noqa: BLE001
        failures["external_publication_rejected"] = str(exc)

    required = {
        "raw_response_text_rejected",
        "raw_ticket_payload_rejected",
        "requester_identity_rejected",
        "automatic_customer_sending_rejected",
        "eval_sufficient_alone_rejected",
        "external_publication_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Support Response negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = support_response.build_all_cases()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in support_response.CASE_IDS]
    report = support_response.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Support Response case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_checks"] = negative_checks(cases["pass"])
    report["claim_boundary"]["not_claimed"] = list(support_response.CLAIM_BOUNDARY["not_claimed"])
    dual_loop.assert_metadata_only(report, label=support_response.REPORT_SCHEMA_VERSION)
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    support_response.write_cases(FIXTURE_ROOT, cases)


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        path = FIXTURE_ROOT / case_id / "support-response-handoff-case.json"
        if not path.is_file():
            raise SystemExit(f"Missing Support Response fixture: {path}")
        if load_json(path) != payload:
            raise SystemExit(
                f"Support Response fixture is out of date: {path}. "
                "Run: python3 scripts/verify_support_response_delivery_class_handoff.py --write"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = support_response.build_all_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    html = dual_loop.render_html_report("Support Response Delivery Class", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file():
            raise SystemExit(f"Support Response is missing: {REPORT}")
        if REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Support Response is out of date. "
                "Run: python3 scripts/verify_support_response_delivery_class_handoff.py --write"
            )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Support Response HTML report is missing: {HTML_REPORT}")
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Support Response HTML report is out of date. "
                "Run: python3 scripts/verify_support_response_delivery_class_handoff.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
