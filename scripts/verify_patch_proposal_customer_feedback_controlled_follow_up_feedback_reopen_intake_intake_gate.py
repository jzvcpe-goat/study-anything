#!/usr/bin/env python3
"""Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate"
REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.json"
)
MARKDOWN_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.md"
)
HTML_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.html"
)
REPORT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate-v1.schema.json"
)
RECEIPT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt-v1.schema.json"
)


EXPECTED = {
    "pass": ("allowed", "allow_reopen_intake_item_gate", []),
    "blocked-missing-bridge-receipt": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["bridge_receipt_missing"],
    ),
    "blocked-bridge-blocked": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["source_bridge_not_ready"],
    ),
    "blocked-missing-closure-ref": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["closure_ref_missing"],
    ),
    "blocked-missing-outcome-ref": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["outcome_ref_missing"],
    ),
    "blocked-missing-action-ref": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["action_ref_missing"],
    ),
    "blocked-missing-actor-ref": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["external_actor_ref_missing"],
    ),
    "blocked-missing-claim-boundary": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["claim_boundary_missing"],
    ),
    "blocked-missing-privacy-boundary": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["privacy_boundary_missing"],
    ),
    "blocked-raw-follow-up-data": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["raw_follow_up_data_rejected"],
    ),
    "blocked-raw-customer-data": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["raw_customer_data_rejected"],
    ),
    "blocked-customer-identity": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["customer_identity_rejected"],
    ),
    "blocked-send-payload": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["send_payload_rejected"],
    ),
    "blocked-automatic-contact": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["automatic_customer_contact_rejected"],
    ),
    "blocked-automatic-intake-creation": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["automatic_intake_creation_rejected"],
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["source_mutation_rejected"],
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["production_mutation_rejected"],
    ),
    "blocked-external-publication-payload": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["external_publication_payload_rejected"],
    ),
    "blocked-model-call": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["model_call_rejected"],
    ),
    "blocked-secret": (
        "blocked",
        "block_reopen_intake_item_gate",
        ["secret_rejected"],
    ),
    "blocked-model-credential": (
        "blocked",
        "block_reopen_intake_item_gate",
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
    receipt = gate.validate_controlled_follow_up_feedback_reopen_intake_gate(
        artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-controlled-follow-up-feedback-reopen-intake-gate:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "gate_action": receipt["reopen_intake_gate"]["gate_action"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-controlled-follow-up-feedback-reopen-intake-gate-") as tmp:
        output_dir = Path(tmp) / "reopen-intake-gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "scripts"
                    / "patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate.py"
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(
                        f"Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate CLI missing {case_id}/{filename}"
                    )
                if load_json(path) != expected:
                    raise RuntimeError(
                        "Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate CLI output drifted: "
                        f"{case_id}/{filename}"
                    )


def negative_fixtures(pass_gate: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_gate)
        mutator(payload)
        try:
            gate.validate_controlled_follow_up_feedback_reopen_intake_gate(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_follow_up_data_injected",
        lambda payload: payload.__setitem__("raw_follow_up_data", "customer follow-up material"),
    )
    expect_rejected(
        "raw_customer_data_injected",
        lambda payload: payload.__setitem__("raw_customer_data", "private customer data"),
    )
    expect_rejected(
        "customer_identity_injected",
        lambda payload: payload.__setitem__("customer_email", "customer@example.test"),
    )
    expect_rejected(
        "send_payload_included",
        lambda payload: payload["reopen_intake_gate"].__setitem__("send_payload_included", True),
    )
    expect_rejected(
        "automatic_contact_performed",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_automatic_customer_contact_performed", True
        ),
    )
    expect_rejected(
        "automatic_intake_payload_included",
        lambda payload: payload["reopen_intake_gate"].__setitem__(
            "automatic_intake_creation_payload_included", True
        ),
    )
    expect_rejected(
        "new_intake_created",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_new_feedback_intake_created", True),
    )
    expect_rejected(
        "source_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_source_mutation_performed", True),
    )
    expect_rejected(
        "production_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_production_mutation_performed", True),
    )
    expect_rejected(
        "external_publication_performed",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_external_publication_performed", True),
    )
    expect_rejected(
        "model_call_performed",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected(
        "dual_loop_ref_missing_on_allowed",
        lambda payload: payload["checks"].__setitem__("dual_loop_refs_preserved", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate report case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, gate.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, gate.GATE_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass"]["patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"]
    )
    gate._validate_privacy(report, label=gate.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            gate.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        expected_names = set(artifacts)
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing patch proposal controlled follow-up feedback reopen intake gate fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal controlled follow-up feedback reopen intake gate fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate.py --write"
                )
        extra = sorted(path.name for path in case_dir.glob("*.json") if path.name not in expected_names)
        if extra:
            raise SystemExit(
                f"Unexpected patch proposal controlled follow-up feedback reopen intake gate fixture(s): {case_dir}: {extra}"
            )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate",
        "",
        (
            "Metadata-only proof that a prepared reopen-intake bridge can pass into the next "
            "Product Loop intake decision point without Study Anything creating the intake, "
            "contacting customers, mutating systems, publishing, or calling models."
        ),
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
        action = row["gate_action"] or "none"
        lines.append(
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / "
            f"gate action: `{action}` / reasons: {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = gate.build_all_case_artifacts()
    report = build_report()
    report_text = gate.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal controlled follow-up feedback reopen intake gate fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate.py --write"
            )
        print("ok    Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
