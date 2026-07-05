#!/usr/bin/env python3
"""Verify controlled follow-up feedback reopen-intake backlog bridge artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge as bridge  # noqa: E402


FIXTURE_ROOT = (
    ROOT
    / "fixtures"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge"
)
REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"
)
MARKDOWN_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.md"
)
HTML_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.html"
)
BRIDGE_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge-v1.schema.json"
)
SIGNAL_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-backlog-signal-v1.schema.json"


EXPECTED = {
    "pass": ("queued_for_product_loop", "emit_reopen_intake_product_loop_backlog_signal", [], True),
    "blocked-missing-gate-receipt": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["reopen_intake_gate_receipt_missing"],
        False,
    ),
    "blocked-gate-blocked": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["source_reopen_intake_gate_not_allowed"],
        False,
    ),
    "blocked-missing-bridge-ref": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["reopen_intake_bridge_ref_missing"],
        False,
    ),
    "blocked-missing-closure-ref": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["closure_ref_missing"],
        False,
    ),
    "blocked-missing-outcome-ref": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["outcome_ref_missing"],
        False,
    ),
    "blocked-missing-action-ref": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["action_ref_missing"],
        False,
    ),
    "blocked-missing-actor-ref": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["external_actor_ref_missing"],
        False,
    ),
    "blocked-missing-intake-candidate-ref": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["intake_candidate_ref_missing"],
        False,
    ),
    "blocked-missing-intake-item-ref": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["product_loop_intake_item_ref_missing"],
        False,
    ),
    "blocked-missing-product-loop-target": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["product_loop_target_missing"],
        False,
    ),
    "blocked-missing-claim-boundary": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["claim_boundary_missing"],
        False,
    ),
    "blocked-missing-privacy-boundary": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["privacy_boundary_missing"],
        False,
    ),
    "blocked-raw-follow-up-data": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["raw_follow_up_data_rejected"],
        False,
    ),
    "blocked-raw-customer-data": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["raw_customer_data_rejected"],
        False,
    ),
    "blocked-customer-identity": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["customer_identity_rejected"],
        False,
    ),
    "blocked-automatic-customer-contact": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["automatic_customer_contact_rejected"],
        False,
    ),
    "blocked-automatic-backlog-creation": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["automatic_backlog_creation_rejected"],
        False,
    ),
    "blocked-automatic-prioritization": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["automatic_prioritization_rejected"],
        False,
    ),
    "blocked-automatic-execution": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["automatic_execution_rejected"],
        False,
    ),
    "blocked-product-loop-backlog-mutation": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["product_loop_backlog_mutation_rejected"],
        False,
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["source_mutation_rejected"],
        False,
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["production_mutation_rejected"],
        False,
    ),
    "blocked-external-publication-payload": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["external_publication_payload_rejected"],
        False,
    ),
    "blocked-model-call": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["model_call_rejected"],
        False,
    ),
    "blocked-secret": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
        ["secret_rejected"],
        False,
    ),
    "blocked-model-credential": (
        "blocked",
        "block_reopen_intake_product_loop_backlog_signal",
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
    payload = bridge.validate_controlled_follow_up_feedback_reopen_intake_backlog_bridge(
        artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"]
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
    dual_loop.assert_metadata_only(
        payload,
        label=f"patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge:{case_id}",
    )
    return {
        "case_id": case_id,
        "status": payload["status"],
        "decision": payload["decision"],
        "blocked_reasons": payload["blocked_reasons"],
        "backlog_signal_created": signal_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-reopen-intake-backlog-") as tmp:
        output_dir = Path(tmp) / "bridge"
        proc = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "scripts"
                    / "patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py"
                ),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-reopen-intake-backlog-bridge-cli")
        if stdout.get("case_ids") != list(bridge.CASE_IDS):
            raise RuntimeError("Reopen-intake backlog bridge CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Reopen-intake backlog bridge CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Reopen-intake backlog bridge CLI output drifted: {case_id}/{filename}")
            signal_path = output_dir / case_id / "product-loop-backlog-signal.json"
            bridge_payload = expected_artifacts[
                "patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"
            ]
            if bridge_payload["status"] == "queued_for_product_loop":
                if not signal_path.is_file():
                    raise RuntimeError(f"Reopen-intake backlog bridge CLI missing signal: {case_id}")
            elif signal_path.exists():
                raise RuntimeError(f"Reopen-intake backlog bridge CLI created signal for blocked case: {case_id}")


def negative_fixtures(pass_bridge: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_bridge)
        mutator(payload)
        try:
            bridge.validate_controlled_follow_up_feedback_reopen_intake_backlog_bridge(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_follow_up_data_injected",
        lambda payload: payload.__setitem__("raw_follow_up_data", "private follow-up body"),
    )
    expect_rejected(
        "raw_customer_data_injected",
        lambda payload: payload.__setitem__("raw_customer_data", "private customer body"),
    )
    expect_rejected(
        "customer_identity_injected",
        lambda payload: payload.__setitem__("customer_identity", "customer@example.test"),
    )
    expect_rejected(
        "automatic_customer_contact_performed",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_automatic_customer_contact_performed", True
        ),
    )
    expect_rejected(
        "automatic_backlog_creation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_backlog_item_created", True),
    )
    expect_rejected(
        "automatic_prioritization_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_priority_assignment_performed", True),
    )
    expect_rejected(
        "automatic_execution_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_patch_execution_performed", True),
    )
    expect_rejected(
        "backlog_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_product_loop_backlog_mutation_performed", True
        ),
    )
    expect_rejected(
        "source_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_repository_mutation_performed", True),
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
        "backlog_signal_allows_backlog_creation",
        lambda payload: payload["backlog_signal"].__setitem__(
            "blocked_destinations",
            [
                item
                for item in payload["backlog_signal"]["blocked_destinations"]
                if item != "automatic_backlog_creation"
            ],
        ),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = bridge.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in bridge.CASE_IDS]
    report = bridge.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Reopen-intake backlog bridge case summary drifted")
    report["schema_files"] = [
        schema_report(BRIDGE_SCHEMA_FILE, bridge.BRIDGE_SCHEMA_VERSION),
        schema_report(SIGNAL_SCHEMA_FILE, bridge.BACKLOG_SIGNAL_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass"]["patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"]
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
                raise SystemExit(f"Missing reopen-intake backlog bridge fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Reopen-intake backlog bridge fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py --write"
                )
        signal_path = case_dir / "product-loop-backlog-signal.json"
        bridge_payload = artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"]
        if bridge_payload["status"] == "blocked" and signal_path.exists():
            raise SystemExit(f"Blocked reopen-intake backlog case must not include signal: {signal_path}")


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge",
        "",
        "Metadata-only proof that allowed reopen-intake gate receipts can emit Product Loop backlog signal refs without creating live backlog items, assigning priority, executing work, or contacting customers.",
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
        "<title>Patch Proposal Controlled Follow-up Feedback Reopen Intake Backlog Bridge</title>\n"
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
        print("wrote reopen-intake backlog bridge fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Reopen-intake backlog bridge report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Reopen-intake backlog bridge markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Reopen-intake backlog bridge HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py --write"
            )
        print("ok    reopen-intake backlog bridge report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
