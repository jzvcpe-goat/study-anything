#!/usr/bin/env python3
"""Verify Patch Proposal Customer Feedback Backlog Bridge artifacts."""

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
import patch_proposal_customer_feedback_backlog_bridge as bridge  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-backlog-bridge"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-backlog-bridge.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-backlog-bridge.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-backlog-bridge.html"
BRIDGE_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-feedback-backlog-bridge-v1.schema.json"
SIGNAL_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-backlog-signal-v1.schema.json"

EXPECTED = {
    "pass-customer-signal": ("queued_for_product_loop", "emit_product_loop_backlog_signal", [], True),
    "pass-operator-signal": ("queued_for_product_loop", "emit_product_loop_backlog_signal", [], True),
    "pass-host-platform-agent-signal": ("queued_for_product_loop", "emit_product_loop_backlog_signal", [], True),
    "blocked-intake-blocked": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["source_feedback_intake_not_accepted"],
        False,
    ),
    "blocked-missing-product-loop-target": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["product_loop_target_missing"],
        False,
    ),
    "blocked-automatic-priority-assignment": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["automatic_priority_assignment_rejected"],
        False,
    ),
    "blocked-automatic-follow-up": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["automatic_follow_up_rejected"],
        False,
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["source_mutation_rejected"],
        False,
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["production_mutation_rejected"],
        False,
    ),
    "blocked-raw-customer-reply": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["raw_customer_reply_rejected"],
        False,
    ),
    "blocked-private-customer-data": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["private_customer_data_rejected"],
        False,
    ),
    "blocked-secret": ("blocked", "block_product_loop_backlog_signal", ["secret_rejected"], False),
    "blocked-model-credential": (
        "blocked",
        "block_product_loop_backlog_signal",
        ["model_credential_rejected"],
        False,
    ),
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


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    payload = bridge.validate_customer_feedback_backlog_bridge(
        artifacts["patch-proposal-customer-feedback-backlog-bridge.json"]
    )
    expected_status, expected_decision, expected_reasons, expected_signal = EXPECTED[case_id]
    if payload["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if payload["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in payload["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    signal_created = payload["backlog_signal"] is not None
    if signal_created is not expected_signal:
        raise RuntimeError(f"{case_id} backlog signal creation drifted")
    if signal_created:
        signal = bridge.validate_backlog_signal(artifacts["product-loop-backlog-signal.json"])
        if signal != payload["backlog_signal"]:
            raise RuntimeError(f"{case_id} standalone backlog signal drifted")
    dual_loop.assert_metadata_only(payload, label=f"patch-proposal-customer-feedback-backlog-bridge:{case_id}")
    return {
        "case_id": case_id,
        "status": payload["status"],
        "decision": payload["decision"],
        "blocked_reasons": payload["blocked_reasons"],
        "backlog_signal_created": signal_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-feedback-backlog-") as tmp:
        output_dir = Path(tmp) / "bridge"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_backlog_bridge.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-customer-feedback-backlog-bridge-cli")
        if stdout.get("case_ids") != list(bridge.CASE_IDS):
            raise RuntimeError("Patch proposal customer feedback backlog bridge CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch proposal customer feedback backlog bridge CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Patch proposal customer feedback backlog bridge CLI output drifted: {case_id}/{filename}")
            signal_path = output_dir / case_id / "product-loop-backlog-signal.json"
            if expected_artifacts["patch-proposal-customer-feedback-backlog-bridge.json"]["status"] == "queued_for_product_loop":
                if not signal_path.is_file():
                    raise RuntimeError(f"Patch proposal feedback backlog bridge CLI missing signal: {case_id}")
            elif signal_path.exists():
                raise RuntimeError(f"Patch proposal feedback backlog bridge CLI created signal for blocked case: {case_id}")


def negative_fixtures(pass_bridge: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_bridge)
        mutator(payload)
        try:
            bridge.validate_customer_feedback_backlog_bridge(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_customer_reply_injected",
        lambda payload: payload.__setitem__("raw_customer_reply", "private customer reply body"),
    )
    expect_rejected(
        "private_customer_data_injected",
        lambda payload: payload.__setitem__("private_customer_data", "customer@example.test"),
    )
    expect_rejected(
        "automatic_priority_assignment_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_priority_assignment_performed", True),
    )
    expect_rejected(
        "automatic_follow_up_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_automatic_follow_up_performed", True),
    )
    expect_rejected(
        "source_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_repository_mutation_performed", True),
    )
    expect_rejected(
        "production_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_production_mutation_performed", True),
    )
    expect_rejected(
        "model_call_performed",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected(
        "backlog_signal_priority_assigned",
        lambda payload: payload["backlog_signal"].__setitem__("priority_assignment", "p0"),
    )
    expect_rejected(
        "backlog_signal_ready_for_execution",
        lambda payload: payload["backlog_signal"].__setitem__("ready_for_execution", True),
    )
    expect_rejected(
        "blocked_bridge_with_signal",
        lambda payload: (
            payload.__setitem__("status", "blocked"),
            payload.__setitem__("decision", "block_product_loop_backlog_signal"),
            payload.__setitem__("blocked_reasons", ["forced_block"]),
        ),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = bridge.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in bridge.CASE_IDS]
    report = bridge.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch proposal customer feedback backlog bridge case summary drifted")
    report["schema_files"] = [
        schema_report(BRIDGE_SCHEMA_FILE, bridge.BRIDGE_SCHEMA_VERSION),
        schema_report(SIGNAL_SCHEMA_FILE, bridge.BACKLOG_SIGNAL_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-customer-signal"]["patch-proposal-customer-feedback-backlog-bridge.json"]
    )
    bridge._validate_privacy(report, label=bridge.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            bridge.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing patch proposal customer feedback backlog bridge fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal customer feedback backlog bridge fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py --write"
                )
        signal_path = case_dir / "product-loop-backlog-signal.json"
        if artifacts["patch-proposal-customer-feedback-backlog-bridge.json"]["status"] == "blocked" and signal_path.exists():
            raise SystemExit(f"Blocked patch proposal customer feedback backlog case must not include signal: {signal_path}")


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Backlog Bridge",
        "",
        "Metadata-only proof that accepted customer-feedback intake receipts can emit Product Loop backlog signals without assigning priority or triggering follow-up/execution.",
        "",
        f"- status: `{report['status']}`",
        f"- schema: `{report['schema_version']}`",
        f"- queued backlog signals: `{report['backlog_matrix']['queued_backlog_signals']}`",
        f"- blocked backlog signals: `{report['backlog_matrix']['blocked_backlog_signals']}`",
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
        lines.append(
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / signal: `{row['backlog_signal_created']}` / reasons: {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Customer Feedback Backlog Bridge</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = bridge.build_all_case_artifacts()
    report = build_report()
    report_text = bridge.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal customer feedback backlog bridge fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch proposal customer feedback backlog bridge report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch proposal customer feedback backlog bridge markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch proposal customer feedback backlog bridge HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py --write"
            )
        print("ok    patch proposal customer feedback backlog bridge report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
