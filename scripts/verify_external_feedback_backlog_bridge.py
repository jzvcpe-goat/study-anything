#!/usr/bin/env python3
"""Verify metadata-only External Feedback Backlog Bridge artifacts."""

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
import external_feedback_backlog_bridge as bridge  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "external-feedback-backlog-bridge"
REPORT = ROOT / "platform" / "generated" / "study-anything-external-feedback-backlog-bridge.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-external-feedback-backlog-bridge.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-external-feedback-backlog-bridge.html"
BRIDGE_SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "external-feedback-backlog-bridge-v1.schema.json"
BACKLOG_SCHEMA_FILE = ROOT / "platform" / "schemas" / "delivery-trust" / "product-loop-backlog-item-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "queued_for_product_loop",
        "decision": "create_product_loop_backlog_item",
        "backlog_item_created": True,
        "blocked_reasons": [],
    },
    "blocked-raw-feedback": {
        "status": "blocked",
        "decision": "block_backlog_item_creation",
        "backlog_item_created": False,
        "blocked_reasons": ["external_feedback_receipt_not_accepted"],
    },
    "blocked-identity": {
        "status": "blocked",
        "decision": "block_backlog_item_creation",
        "backlog_item_created": False,
        "blocked_reasons": ["external_feedback_receipt_not_accepted"],
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_backlog_item_creation",
        "backlog_item_created": False,
        "blocked_reasons": [
            "external_feedback_receipt_not_accepted",
            "external_feedback_decision_blocked",
            "requested_next_action_outside_feedback_budget",
        ],
    },
    "blocked-ai-review-only": {
        "status": "blocked",
        "decision": "block_backlog_item_creation",
        "backlog_item_created": False,
        "blocked_reasons": ["external_feedback_receipt_not_accepted"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report(path: Path, schema_version: str) -> dict[str, str]:
    payload = load_json(path)
    if payload.get("$id") != schema_version:
        raise RuntimeError(f"{path.name} id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
        raise RuntimeError(f"{path.name} schema_version const drifted")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "schema_version": schema_version,
        "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    case = bridge.validate_bridge(payload)
    expected = EXPECTED[case_id]
    if case["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} bridge status drifted")
    if case["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} bridge decision drifted")
    backlog_item_created = case["backlog_item"] is not None
    if backlog_item_created is not expected["backlog_item_created"]:
        raise RuntimeError(f"{case_id} backlog item creation drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in case["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if case_id == "pass":
        item = case["backlog_item"]
        if not isinstance(item, Mapping):
            raise RuntimeError("pass case must include backlog item")
        if item["destination"] != "product_loop_backlog":
            raise RuntimeError("pass backlog item destination drifted")
        if item["ready_for_delivery_trust_harness"] is not False:
            raise RuntimeError("pass backlog item must not skip to delivery trust harness")
    return {
        "case_id": case_id,
        "status": case["status"],
        "decision": case["decision"],
        "blocked_reasons": list(case["blocked_reasons"]),
        "backlog_item_created": backlog_item_created,
        "source_delivery_class": case["source_delivery_class"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-feedback-backlog-") as tmp:
        output_dir = Path(tmp) / "bridge"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "external_feedback_backlog_bridge.py"),
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
        dual_loop.assert_metadata_only(stdout, label="external-feedback-backlog-bridge-cli")
        if stdout.get("case_ids") != list(bridge.CASE_IDS):
            raise RuntimeError("External Feedback Backlog Bridge CLI case order drifted")
        for case_id, expected in cases.items():
            path = output_dir / case_id / "external-feedback-backlog-bridge.json"
            if not path.is_file():
                raise RuntimeError(f"Bridge CLI missing fixture: {case_id}")
            if load_json(path) != expected:
                raise RuntimeError(f"Bridge CLI output drifted: {case_id}")
            item_path = output_dir / case_id / "product-loop-backlog-item.json"
            if case_id == "pass" and not item_path.is_file():
                raise RuntimeError("Bridge CLI missing pass backlog item")
            if case_id != "pass" and item_path.exists():
                raise RuntimeError(f"Bridge CLI created backlog item for blocked case: {case_id}")


def expect_rejected(name: str, receipt: Mapping[str, Any], failures: dict[str, str]) -> None:
    try:
        bridge.build_bridge(receipt)
    except Exception as exc:  # noqa: BLE001
        failures[name] = str(exc)


def negative_checks(pass_receipt: Mapping[str, Any], pass_bridge: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    raw_feedback = json.loads(dual_loop.dump_json(pass_receipt))
    raw_feedback["feedback_ref"]["raw_feedback_text"] = "private customer complaint body"
    expect_rejected("raw_feedback_text_rejected", raw_feedback, failures)

    requester_identity = json.loads(dual_loop.dump_json(pass_receipt))
    requester_identity["feedback_ref"]["requester_identity"] = "private requester identity"
    expect_rejected("requester_identity_rejected", requester_identity, failures)

    production_payload = json.loads(dual_loop.dump_json(pass_receipt))
    production_payload["feedback_ref"]["production_payload"] = "private production payload"
    expect_rejected("production_payload_rejected", production_payload, failures)

    runtime_mutation = json.loads(dual_loop.dump_json(pass_receipt))
    runtime_mutation["runtime"]["production_mutation_performed"] = True
    expect_rejected("runtime_production_mutation_rejected", runtime_mutation, failures)

    customer_reply = json.loads(dual_loop.dump_json(pass_receipt))
    customer_reply["runtime"]["automatic_customer_reply_performed"] = True
    expect_rejected("runtime_customer_reply_rejected", customer_reply, failures)

    unsafe_bridge = json.loads(dual_loop.dump_json(pass_bridge))
    unsafe_bridge["backlog_item"]["ready_for_delivery_trust_harness"] = True
    try:
        bridge.validate_bridge(unsafe_bridge)
    except Exception as exc:  # noqa: BLE001
        failures["backlog_skip_to_delivery_harness_rejected"] = str(exc)

    blocked_with_item = json.loads(dual_loop.dump_json(pass_bridge))
    blocked_with_item["status"] = "blocked"
    blocked_with_item["decision"] = "block_backlog_item_creation"
    blocked_with_item["blocked_reasons"] = ["forced_block"]
    try:
        bridge.validate_bridge(blocked_with_item)
    except Exception as exc:  # noqa: BLE001
        failures["blocked_bridge_with_backlog_item_rejected"] = str(exc)

    required = {
        "raw_feedback_text_rejected",
        "requester_identity_rejected",
        "production_payload_rejected",
        "runtime_production_mutation_rejected",
        "runtime_customer_reply_rejected",
        "backlog_skip_to_delivery_harness_rejected",
        "blocked_bridge_with_backlog_item_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"External Feedback Backlog Bridge negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    receipts = external_feedback.build_all_cases()
    cases = bridge.build_all_cases()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in bridge.CASE_IDS]
    report = bridge.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("External Feedback Backlog Bridge case summary drifted")
    report["schema_files"] = [
        schema_report(BRIDGE_SCHEMA_FILE, bridge.BRIDGE_SCHEMA_VERSION),
        schema_report(BACKLOG_SCHEMA_FILE, bridge.BACKLOG_ITEM_SCHEMA_VERSION),
    ]
    report["negative_checks"] = negative_checks(receipts["pass"], cases["pass"])
    report["claim_boundary"]["not_claimed"] = list(bridge.CLAIM_BOUNDARY["not_claimed"])
    dual_loop.assert_metadata_only(report, label=bridge.REPORT_SCHEMA_VERSION)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# External Feedback Backlog Bridge",
        "",
        "Metadata-only verification that accepted External Feedback receipts can create Product Loop backlog items while blocked receipts cannot enter the backlog.",
        "",
        f"- status: `{report['status']}`",
        f"- queued cases: `{report['queued_case_count']}`",
        f"- blocked cases: `{report['blocked_case_count']}`",
        f"- backlog items: `{report['backlog_item_count']}`",
        "- destination: `product_loop_backlog`",
        "- next boundary: `product_owner_prioritization`",
        "",
        "## Cases",
        "",
    ]
    for case in report["case_reports"]:
        reasons = ", ".join(f"`{reason}`" for reason in case["blocked_reasons"]) or "`none`"
        lines.append(
            f"- `{case['case_id']}`: `{case['status']}` / `{case['decision']}` / backlog item: `{case['backlog_item_created']}` / reasons: {reasons}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "The bridge stops at Product Loop backlog metadata. It does not send customer replies, publish externally, mutate production, or skip product-owner prioritization.",
            "",
        ]
    )
    return "\n".join(lines)


def write_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    bridge.write_cases(FIXTURE_ROOT, cases)


def check_fixtures(cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        path = FIXTURE_ROOT / case_id / "external-feedback-backlog-bridge.json"
        if not path.is_file():
            raise SystemExit(f"Missing External Feedback Backlog Bridge fixture: {path}")
        if load_json(path) != payload:
            raise SystemExit(
                f"External Feedback Backlog Bridge fixture is out of date: {path}. "
                "Run: python3 scripts/verify_external_feedback_backlog_bridge.py --write"
            )
        item_path = FIXTURE_ROOT / case_id / "product-loop-backlog-item.json"
        if case_id == "pass":
            expected_item = payload["backlog_item"]
            if not item_path.is_file():
                raise SystemExit(f"Missing Product Loop backlog item fixture: {item_path}")
            if load_json(item_path) != expected_item:
                raise SystemExit(
                    f"Product Loop backlog item fixture is out of date: {item_path}. "
                    "Run: python3 scripts/verify_external_feedback_backlog_bridge.py --write"
                )
        elif item_path.exists():
            raise SystemExit(f"Blocked External Feedback case must not include backlog item: {item_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = bridge.build_all_cases()
    report = build_report()
    serialized = dual_loop.dump_json(report)
    markdown = render_markdown(report)
    html = dual_loop.render_html_report("External Feedback Backlog Bridge", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file():
            raise SystemExit(f"External Feedback Backlog Bridge report is missing: {REPORT}")
        if REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "External Feedback Backlog Bridge report is out of date. "
                "Run: python3 scripts/verify_external_feedback_backlog_bridge.py --write"
            )
        if not MARKDOWN_REPORT.is_file():
            raise SystemExit(f"External Feedback Backlog Bridge markdown report is missing: {MARKDOWN_REPORT}")
        if MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise SystemExit(
                "External Feedback Backlog Bridge markdown report is out of date. "
                "Run: python3 scripts/verify_external_feedback_backlog_bridge.py --write"
            )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"External Feedback Backlog Bridge HTML report is missing: {HTML_REPORT}")
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "External Feedback Backlog Bridge HTML report is out of date. "
                "Run: python3 scripts/verify_external_feedback_backlog_bridge.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
