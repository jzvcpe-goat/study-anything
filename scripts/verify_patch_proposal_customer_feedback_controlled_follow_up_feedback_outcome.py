#!/usr/bin/env python3
"""Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome Receipt artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome as outcome  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome"
REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome.json"
)
MARKDOWN_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome.md"
)
HTML_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome.html"
)
REPORT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome-v1.schema.json"
)
RECEIPT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-controlled-follow-up-feedback-outcome-receipt-v1.schema.json"
)


EXPECTED = {
    "pass-human-operator": ("recorded", "record_external_controlled_follow_up_feedback_outcome", []),
    "pass-host-platform-agent": ("recorded", "record_external_controlled_follow_up_feedback_outcome", []),
    "blocked-rehearsal-blocked": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["source_rehearsal_not_ready"],
    ),
    "blocked-missing-external-actor": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["external_actor_missing"],
    ),
    "blocked-missing-action-reference": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["action_reference_hash_missing"],
    ),
    "blocked-missing-claim-boundary": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["claim_boundary_missing"],
    ),
    "blocked-missing-privacy-boundary": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["privacy_boundary_missing"],
    ),
    "blocked-raw-follow-up-body": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["raw_follow_up_body_rejected"],
    ),
    "blocked-raw-customer-reply": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["raw_customer_reply_rejected"],
    ),
    "blocked-customer-identity": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["customer_identity_rejected"],
    ),
    "blocked-send-payload": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["send_payload_rejected"],
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["source_mutation_rejected"],
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["production_mutation_rejected"],
    ),
    "blocked-external-publication-payload": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["external_publication_payload_rejected"],
    ),
    "blocked-model-call": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["model_call_rejected"],
    ),
    "blocked-secret": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
        ["secret_rejected"],
    ),
    "blocked-model-credential": (
        "blocked",
        "block_controlled_follow_up_feedback_outcome",
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
    receipt = outcome.validate_controlled_follow_up_feedback_outcome(
        artifacts["patch-proposal-controlled-follow-up-feedback-outcome-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-controlled-follow-up-feedback-outcome:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "actor_type": receipt["external_follow_up_outcome"]["actor_type"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-controlled-follow-up-feedback-outcome-") as tmp:
        output_dir = Path(tmp) / "outcome"
        proc = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "scripts"
                    / "patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome.py"
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-controlled-follow-up-feedback-outcome-cli")
        if stdout.get("case_ids") != list(outcome.CASE_IDS):
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Outcome CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch Proposal Controlled Follow-up Feedback Outcome CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal Controlled Follow-up Feedback Outcome CLI output drifted: {case_id}/{filename}"
                    )


def negative_fixtures(pass_outcome: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_outcome)
        mutator(payload)
        try:
            outcome.validate_controlled_follow_up_feedback_outcome(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_follow_up_body_injected",
        lambda payload: payload.__setitem__("raw_follow_up_body", "customer-facing follow-up"),
    )
    expect_rejected(
        "raw_customer_reply_injected",
        lambda payload: payload.__setitem__("raw_customer_reply", "private customer reply"),
    )
    expect_rejected(
        "customer_identity_injected",
        lambda payload: payload.__setitem__("customer_email", "customer@example.test"),
    )
    expect_rejected(
        "send_payload_included",
        lambda payload: payload["external_follow_up_outcome"].__setitem__("send_payload_included", True),
    )
    expect_rejected(
        "study_anything_send_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_customer_follow_up_send_performed", True),
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
        "dual_loop_ref_missing_on_recorded",
        lambda payload: payload["checks"].__setitem__("dual_loop_refs_preserved", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = outcome.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in outcome.CASE_IDS]
    report = outcome.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Outcome report case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, outcome.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, outcome.OUTCOME_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-human-operator"]["patch-proposal-controlled-follow-up-feedback-outcome-receipt.json"]
    )
    outcome._validate_privacy(report, label=outcome.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            outcome.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        expected_names = set(artifacts)
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing patch proposal controlled follow-up feedback outcome fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal controlled follow-up feedback outcome fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome.py --write"
                )
        extra = sorted(path.name for path in case_dir.glob("*.json") if path.name not in expected_names)
        if extra:
            raise SystemExit(f"Unexpected patch proposal controlled follow-up feedback outcome fixture(s): {case_dir}: {extra}")


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome Receipt",
        "",
        "Metadata-only proof that external follow-up outcomes can be recorded without Study Anything sending, storing customer content, or mutating systems.",
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
        actor = row["actor_type"] or "none"
        lines.append(
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / "
            f"actor: `{actor}` / reasons: {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Controlled Follow-up Feedback Outcome Receipt</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = outcome.build_all_case_artifacts()
    report = build_report()
    report_text = outcome.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal controlled follow-up feedback outcome fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Outcome report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Outcome markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Outcome HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome.py --write"
            )
        print("ok    Patch Proposal Controlled Follow-up Feedback Outcome report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
