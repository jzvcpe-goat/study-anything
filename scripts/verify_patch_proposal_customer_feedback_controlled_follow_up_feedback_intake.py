#!/usr/bin/env python3
"""Verify controlled follow-up feedback intake receipts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_intake as feedback  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-intake"
REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.json"
)
MARKDOWN_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.md"
)
HTML_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.html"
)
REPORT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-intake-v1.schema.json"
)
RECEIPT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-controlled-follow-up-feedback-intake-receipt-v1.schema.json"
)


EXPECTED = {
    "pass-customer-signal": ("accepted", "record_controlled_follow_up_feedback_intake", []),
    "pass-operator-signal": ("accepted", "record_controlled_follow_up_feedback_intake", []),
    "pass-host-platform-agent-signal": ("accepted", "record_controlled_follow_up_feedback_intake", []),
    "blocked-outcome-blocked": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["source_outcome_not_recorded"],
    ),
    "blocked-missing-response-signal": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["feedback_signal_missing"],
    ),
    "blocked-missing-signal-reference": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["feedback_signal_reference_hash_missing"],
    ),
    "blocked-missing-product-loop-target": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["product_loop_target_missing"],
    ),
    "blocked-missing-claim-boundary": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["claim_boundary_missing"],
    ),
    "blocked-missing-privacy-boundary": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["privacy_boundary_missing"],
    ),
    "blocked-raw-customer-reply": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["raw_customer_reply_rejected"],
    ),
    "blocked-customer-identity": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["customer_identity_rejected"],
    ),
    "blocked-private-customer-data": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["private_customer_data_rejected"],
    ),
    "blocked-pr-comment-body": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["pr_comment_body_rejected"],
    ),
    "blocked-external-publication-payload": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["external_publication_payload_rejected"],
    ),
    "blocked-automatic-follow-up": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["automatic_follow_up_rejected"],
    ),
    "blocked-product-loop-backlog-mutation": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["product_loop_backlog_mutation_rejected"],
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["source_mutation_rejected"],
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["production_mutation_rejected"],
    ),
    "blocked-model-call": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["model_call_rejected"],
    ),
    "blocked-secret": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["secret_rejected"],
    ),
    "blocked-model-credential": (
        "blocked",
        "block_controlled_follow_up_feedback_intake",
        ["model_credential_rejected"],
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
    receipt = feedback.validate_controlled_follow_up_feedback_intake(
        artifacts["patch-proposal-controlled-follow-up-feedback-intake-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-controlled-follow-up-feedback-intake:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "signal_type": receipt["feedback_signal_summary"]["signal_type"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-controlled-follow-up-feedback-intake-") as tmp:
        output_dir = Path(tmp) / "feedback-intake"
        proc = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "scripts"
                    / "patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py"
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-controlled-follow-up-feedback-intake-cli")
        if stdout.get("case_ids") != list(feedback.CASE_IDS):
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Intake CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(
                        f"Patch Proposal Controlled Follow-up Feedback Intake CLI missing {case_id}/{filename}"
                    )
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal Controlled Follow-up Feedback Intake CLI output drifted: {case_id}/{filename}"
                    )


def negative_fixtures(pass_intake: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_intake)
        mutator(payload)
        try:
            feedback.validate_controlled_follow_up_feedback_intake(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_customer_reply_injected",
        lambda payload: payload.__setitem__("raw_customer_reply", "private customer reply"),
    )
    expect_rejected(
        "customer_identity_injected",
        lambda payload: payload.__setitem__("customer_identity", "customer@example.test"),
    )
    expect_rejected(
        "private_customer_data_injected",
        lambda payload: payload.__setitem__("private_customer_data", "customer account data"),
    )
    expect_rejected(
        "raw_feedback_included_escalated",
        lambda payload: payload["feedback_signal_summary"].__setitem__("raw_feedback_included", True),
    )
    expect_rejected(
        "product_loop_storage_mutated",
        lambda payload: payload["product_loop_destination"].__setitem__("product_loop_storage_mutated", True),
    )
    expect_rejected(
        "automatic_follow_up_performed",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_automatic_follow_up_performed", True
        ),
    )
    expect_rejected(
        "pr_commenting_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_pr_commenting_performed", True),
    )
    expect_rejected(
        "source_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_repository_mutation_performed", True
        ),
    )
    expect_rejected(
        "model_call_performed",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = feedback.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in feedback.CASE_IDS]
    report = feedback.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Intake report case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, feedback.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, feedback.INTAKE_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-customer-signal"]["patch-proposal-controlled-follow-up-feedback-intake-receipt.json"]
    )
    feedback._validate_privacy(report, label=feedback.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            feedback.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing Patch Proposal Controlled Follow-up Feedback Intake fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch Proposal Controlled Follow-up Feedback Intake fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake",
        "",
        "Metadata-only proof that response signals after controlled follow-up outcomes can enter the Product Loop backlog candidate path without storing raw replies, identity, or mutation payloads.",
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
        signal = row["signal_type"] or "none"
        lines.append(
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / signal: `{signal}` / reasons: {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Controlled Follow-up Feedback Intake</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = feedback.build_all_case_artifacts()
    report = build_report()
    report_text = feedback.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote Patch Proposal Controlled Follow-up Feedback Intake fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Intake report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Intake markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Intake HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py --write"
            )
        print("ok    Patch Proposal Controlled Follow-up Feedback Intake report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
