#!/usr/bin/env python3
"""Verify metadata-only External Feedback Receipt artifacts."""

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
import external_feedback_receipt as external_feedback  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "external-feedback-receipt"
REPORT = ROOT / "platform" / "generated" / "study-anything-external-feedback-receipt.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-external-feedback-receipt.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-external-feedback-receipt.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "external-feedback-receipt-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "accepted_for_product_loop",
        "decision": "accept_external_feedback_into_product_loop",
        "reasons": [],
    },
    "blocked-raw-feedback": {
        "status": "blocked",
        "decision": "block_external_feedback_propagation",
        "reasons": ["missing_no_raw_payload_attached"],
    },
    "blocked-identity": {
        "status": "blocked",
        "decision": "block_external_feedback_propagation",
        "reasons": ["missing_feedback_source_bounded"],
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_external_feedback_propagation",
        "reasons": [
            "automatic_production_mutation_allowed",
            "requested_next_action_outside_feedback_budget",
        ],
    },
    "blocked-ai-review-only": {
        "status": "blocked",
        "decision": "block_external_feedback_propagation",
        "reasons": [
            "missing_active_human_triage_recorded",
            "ai_review_only_basis",
            "passive_attention_only",
        ],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != external_feedback.SCHEMA_VERSION:
        raise RuntimeError("External Feedback Receipt schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != external_feedback.SCHEMA_VERSION:
        raise RuntimeError("External Feedback Receipt schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": external_feedback.SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    case = external_feedback.validate_case(payload)
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
        "reason_count": case["reason_count"],
        "reasons": case["reasons"],
        "source_delivery_class": case["source_delivery_class"],
        "requested_next_action": case["propagation"]["requested_next_action"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-external-feedback-") as tmp:
        output_dir = Path(tmp) / "external-feedback"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "external_feedback_receipt.py"),
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
        dual_loop.assert_metadata_only(stdout, label="external-feedback-receipt-cli")
        if stdout.get("case_ids") != list(external_feedback.CASE_IDS):
            raise RuntimeError("External Feedback CLI case order drifted")
        for case_id, expected in cases.items():
            path = output_dir / case_id / "external-feedback-receipt.json"
            if not path.is_file():
                raise RuntimeError(f"External Feedback CLI missing fixture: {case_id}")
            if load_json(path) != expected:
                raise RuntimeError(f"External Feedback CLI output drifted: {case_id}")


def expect_rejected(name: str, payload: Mapping[str, Any], failures: dict[str, str]) -> None:
    try:
        external_feedback.validate_case(payload)
    except Exception as exc:  # noqa: BLE001
        failures[name] = str(exc)


def negative_checks(pass_case: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    raw_feedback = json.loads(dual_loop.dump_json(pass_case))
    raw_feedback["feedback_ref"]["raw_feedback_text"] = "private customer complaint body"
    expect_rejected("raw_feedback_text_rejected", raw_feedback, failures)

    raw_message = json.loads(dual_loop.dump_json(pass_case))
    raw_message["feedback_ref"]["raw_customer_message"] = "private customer message body"
    expect_rejected("raw_customer_message_rejected", raw_message, failures)

    requester_identity = json.loads(dual_loop.dump_json(pass_case))
    requester_identity["feedback_ref"]["requester_identity"] = "private requester identity"
    expect_rejected("requester_identity_rejected", requester_identity, failures)

    customer_identity = json.loads(dual_loop.dump_json(pass_case))
    customer_identity["feedback_ref"]["customer_identity"] = "private customer identity"
    expect_rejected("customer_identity_rejected", customer_identity, failures)

    production_payload = json.loads(dual_loop.dump_json(pass_case))
    production_payload["feedback_ref"]["production_payload"] = "private production payload"
    expect_rejected("production_payload_rejected", production_payload, failures)

    runtime_mutation = json.loads(dual_loop.dump_json(pass_case))
    runtime_mutation["runtime"]["production_mutation_performed"] = True
    expect_rejected("runtime_production_mutation_rejected", runtime_mutation, failures)

    privacy_raw = json.loads(dual_loop.dump_json(pass_case))
    privacy_raw["privacy"]["raw_feedback_text_included"] = True
    expect_rejected("privacy_raw_feedback_text_rejected", privacy_raw, failures)

    privacy_identity = json.loads(dual_loop.dump_json(pass_case))
    privacy_identity["privacy"]["requester_identity_included"] = True
    expect_rejected("privacy_requester_identity_rejected", privacy_identity, failures)

    required = {
        "raw_feedback_text_rejected",
        "raw_customer_message_rejected",
        "requester_identity_rejected",
        "customer_identity_rejected",
        "production_payload_rejected",
        "runtime_production_mutation_rejected",
        "privacy_raw_feedback_text_rejected",
        "privacy_requester_identity_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"External Feedback negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = external_feedback.build_all_cases()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in external_feedback.CASE_IDS]
    report = external_feedback.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("External Feedback case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_checks"] = negative_checks(cases["pass"])
    report["claim_boundary"]["not_claimed"] = list(external_feedback.CLAIM_BOUNDARY["not_claimed"])
    dual_loop.assert_metadata_only(report, label=external_feedback.REPORT_SCHEMA_VERSION)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# External Feedback Receipt",
        "",
        "Metadata-only verification that external feedback can re-enter the Product Loop without raw customer content, customer identity, automatic replies, or production mutation.",
        "",
        f"- status: `{report['status']}`",
        f"- accepted cases: `{report['accepted_case_count']}`",
        f"- blocked cases: `{report['blocked_case_count']}`",
        "- next boundary: `product_loop_backlog_only_not_production`",
        "",
        "## Cases",
        "",
    ]
    for case in report["case_reports"]:
        reasons = ", ".join(f"`{reason}`" for reason in case["reasons"]) or "`none`"
        lines.append(
            f"- `{case['case_id']}`: `{case['status']}` / `{case['decision']}` / reasons: {reasons}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "The accepted path is product-loop backlog evidence only. This artifact does not permit customer-visible replies, external publication, model retraining payloads, or production mutation.",
            "",
        ]
    )
    return "\n".join(lines)


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    external_feedback.write_cases(FIXTURE_ROOT, cases)


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        path = FIXTURE_ROOT / case_id / "external-feedback-receipt.json"
        if not path.is_file():
            raise SystemExit(f"Missing External Feedback fixture: {path}")
        if load_json(path) != payload:
            raise SystemExit(
                f"External Feedback fixture is out of date: {path}. "
                "Run: python3 scripts/verify_external_feedback_receipt.py --write"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = external_feedback.build_all_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    markdown = render_markdown(report)
    html = dual_loop.render_html_report("External Feedback Receipt", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file():
            raise SystemExit(f"External Feedback report is missing: {REPORT}")
        if REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "External Feedback report is out of date. "
                "Run: python3 scripts/verify_external_feedback_receipt.py --write"
            )
        if not MARKDOWN_REPORT.is_file():
            raise SystemExit(f"External Feedback markdown report is missing: {MARKDOWN_REPORT}")
        if MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise SystemExit(
                "External Feedback markdown report is out of date. "
                "Run: python3 scripts/verify_external_feedback_receipt.py --write"
            )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"External Feedback HTML report is missing: {HTML_REPORT}")
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "External Feedback HTML report is out of date. "
                "Run: python3 scripts/verify_external_feedback_receipt.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
