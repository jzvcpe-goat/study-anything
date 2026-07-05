#!/usr/bin/env python3
"""Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate.html"
REPORT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate-v1.schema.json"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt-v1.schema.json"
CANDIDATE_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-delivery-trust-case-candidate-v1.schema.json"


EXPECTED = {
    "pass": ("queued_for_delivery_trust_case_candidate", [], True),
    "blocked-missing-product-loop-intake-receipt": ("blocked", ["product_loop_intake_receipt_missing"], False),
    "blocked-product-loop-intake-blocked": ("blocked", ["product_loop_intake_blocked"], False),
    "blocked-missing-product-loop-run": ("blocked", ["product_loop_run_missing"], False),
    "blocked-product-loop-run-blocked": ("blocked", ["product_loop_run_invalid"], False),
    "blocked-missing-product-loop-scenario": ("blocked", ["product_loop_scenario_missing"], False),
    "blocked-missing-authoring-receipt-ref": ("blocked", ["source_authoring_receipt_missing"], False),
    "blocked-missing-spec-eval-candidate-ref": ("blocked", ["source_brief_candidate_ref_missing"], False),
    "blocked-missing-brief-candidate-ref": ("blocked", ["source_brief_candidate_ref_missing"], False),
    "blocked-missing-gate-ref": ("blocked", ["reopen_intake_gate_receipt_missing"], False),
    "blocked-missing-bridge-ref": ("blocked", ["reopen_intake_bridge_ref_missing"], False),
    "blocked-missing-closure-ref": ("blocked", ["closure_ref_missing"], False),
    "blocked-missing-outcome-ref": ("blocked", ["outcome_ref_missing"], False),
    "blocked-missing-action-ref": ("blocked", ["action_ref_missing"], False),
    "blocked-missing-actor-ref": ("blocked", ["external_actor_ref_missing"], False),
    "blocked-missing-intake-candidate-ref": ("blocked", ["intake_candidate_ref_missing"], False),
    "blocked-missing-intake-item-ref": ("blocked", ["product_loop_intake_item_ref_missing"], False),
    "blocked-missing-backlog-signal-ref": ("blocked", ["backlog_signal_ref_missing"], False),
    "blocked-missing-product-owner-ref": ("blocked", ["product_owner_reconstruction_missing"], False),
    "blocked-missing-failure-contract": ("blocked", ["failure_contract_missing"], False),
    "blocked-missing-sandbox-receipt": ("blocked", ["sandbox_receipt_missing"], False),
    "blocked-missing-attention-summary": ("blocked", ["attention_reconstruction_missing"], False),
    "blocked-missing-dual-loop-gate": ("blocked", ["dual_loop_gate_missing"], False),
    "blocked-dual-loop-blocked": (
        "blocked",
        ["dual_loop_gate_blocked", "sandbox_risk_outside_budget"],
        False,
    ),
    "blocked-sandbox-risk": (
        "blocked",
        ["dual_loop_gate_blocked", "sandbox_risk_outside_budget"],
        False,
    ),
    "blocked-attention-missing": ("blocked", ["attention_reconstruction_missing"], False),
    "blocked-missing-claim-boundary": ("blocked", ["claim_boundary_missing"], False),
    "blocked-missing-privacy-boundary": ("blocked", ["privacy_boundary_missing"], False),
    "blocked-missing-attention-reconstruction": ("blocked", ["attention_reconstruction_missing"], False),
    "blocked-ai-review-only": ("blocked", ["ai_review_only_evidence_rejected"], False),
    "blocked-raw-brief-body": ("blocked", ["raw_brief_body_rejected"], False),
    "blocked-raw-spec-body": ("blocked", ["raw_spec_body_rejected"], False),
    "blocked-raw-eval-body": ("blocked", ["raw_eval_body_rejected"], False),
    "blocked-raw-follow-up-data": ("blocked", ["raw_follow_up_data_rejected"], False),
    "blocked-raw-customer-data": ("blocked", ["raw_customer_data_rejected"], False),
    "blocked-raw-backlog-data": ("blocked", ["raw_backlog_data_rejected"], False),
    "blocked-customer-identity": ("blocked", ["customer_identity_rejected"], False),
    "blocked-delivery-trust-harness-invocation": (
        "blocked",
        ["delivery_trust_harness_invocation_rejected"],
        False,
    ),
    "blocked-customer-handoff-package": ("blocked", ["customer_handoff_package_rejected"], False),
    "blocked-automatic-execution": ("blocked", ["automatic_execution_rejected"], False),
    "blocked-customer-contact": ("blocked", ["customer_contact_rejected"], False),
    "blocked-product-loop-backlog-mutation": ("blocked", ["product_loop_backlog_mutation_rejected"], False),
    "blocked-source-mutation": ("blocked", ["source_mutation_rejected"], False),
    "blocked-production-mutation": ("blocked", ["production_mutation_rejected"], False),
    "blocked-external-publication-payload": ("blocked", ["external_publication_payload_rejected"], False),
    "blocked-model-call": ("blocked", ["model_call_rejected"], False),
    "blocked-secret": ("blocked", ["secret_rejected"], False),
    "blocked-model-credential": ("blocked", ["model_credential_rejected"], False),
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
    receipt = gate.validate_intake_receipt(artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt.json"])
    expected_status, expected_reasons, expected_candidate = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    candidate_created = receipt["candidate"] is not None
    if candidate_created is not expected_candidate:
        raise RuntimeError(f"{case_id} candidate creation drifted")
    if candidate_created:
        candidate = gate.validate_candidate(artifacts["patch-proposal-delivery-trust-case-candidate.json"])
        if candidate != receipt["candidate"]:
            raise RuntimeError(f"{case_id} standalone candidate drifted")
        if candidate["ready_for_customer_handoff"] is not False:
            raise RuntimeError(f"{case_id} candidate must not allow customer handoff")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "candidate_created": candidate_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-delivery-trust-intake-") as tmp:
        output_dir = Path(tmp) / "gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake CLI output drifted: {case_id}/{filename}")
            candidate_path = output_dir / case_id / "patch-proposal-delivery-trust-case-candidate.json"
            if expected_artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt.json"]["status"] == "blocked":
                if candidate_path.exists():
                    raise RuntimeError(f"blocked case must not include candidate: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py"),
                "--product-loop-run",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate"
                    / "pass"
                    / "product-loop-run.json"
                ),
                "--output-dir",
                str(custom_output_dir),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        custom_stdout = json.loads(custom_proc.stdout)
        if custom_stdout.get("case_ids") != ["custom"]:
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake custom CLI output drifted")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            gate.validate_intake_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_delivery_case_injected",
        lambda payload: payload["candidate"].__setitem__("raw_delivery_case", "private case body"),
    )
    expect_rejected(
        "customer_handoff_package_injected",
        lambda payload: payload["candidate"].__setitem__("customer_handoff_package", {"raw": "private"}),
    )
    expect_rejected(
        "customer_handoff_ready_injected",
        lambda payload: payload["candidate"].__setitem__("ready_for_customer_handoff", True),
    )
    expect_rejected(
        "delivery_harness_invoked_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_delivery_trust_case_harness_invoked",
            True,
        ),
    )
    expect_rejected(
        "delivery_harness_invocation_policy_injected",
        lambda payload: payload["intake_policy"].__setitem__(
            "delivery_trust_case_harness_invocation_allowed",
            True,
        ),
    )
    expect_rejected(
        "customer_handoff_package_policy_injected",
        lambda payload: payload["intake_policy"].__setitem__(
            "customer_handoff_package_creation_allowed",
            True,
        ),
    )
    expect_rejected(
        "automatic_execution_transition_injected",
        lambda payload: payload["requested_transition"].__setitem__("automatic_execution_requested", True),
    )
    expect_rejected(
        "customer_follow_up_policy_injected",
        lambda payload: payload["intake_policy"].__setitem__("customer_visible_follow_up_allowed", True),
    )
    expect_rejected(
        "external_publication_transition_injected",
        lambda payload: payload["requested_transition"].__setitem__("external_publication_requested", True),
    )
    expect_rejected(
        "model_call_transition_injected",
        lambda payload: payload["requested_transition"].__setitem__("model_call_requested", True),
    )
    expect_rejected(
        "production_mutation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_production_mutation_performed",
            True,
        ),
    )
    expect_rejected(
        "model_call_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected(
        "blocked_receipt_with_candidate",
        lambda payload: (
            payload.__setitem__("status", "blocked"),
            payload.__setitem__("decision", "block_patch_proposal_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate"),
            payload.__setitem__("blocked_reasons", ["forced_block"]),
        ),
    )
    required = {
        "raw_delivery_case_injected",
        "customer_handoff_package_injected",
        "customer_handoff_ready_injected",
        "delivery_harness_invoked_effect_injected",
        "delivery_harness_invocation_policy_injected",
        "customer_handoff_package_policy_injected",
        "automatic_execution_transition_injected",
        "customer_follow_up_policy_injected",
        "external_publication_transition_injected",
        "model_call_transition_injected",
        "production_mutation_effect_injected",
        "model_call_effect_injected",
        "blocked_receipt_with_candidate",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, gate.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(CANDIDATE_SCHEMA_FILE, gate.CANDIDATE_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass"]["patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt.json"]
    )
    gate._validate_privacy(report, label=gate.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    gate._validate_effect_boundary(report, label=gate.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            gate.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py --write"
                )
        candidate_path = case_dir / "patch-proposal-delivery-trust-case-candidate.json"
        if (
            artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt.json"]["status"] == "blocked"
            and candidate_path.exists()
        ):
            raise SystemExit(f"Blocked Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake case must not include candidate: {case_id}")


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate",
        "",
        "Metadata-only proof that Patch Proposal Product Loop runs can become Delivery Trust case candidates only after controlled-failure and attention-reconstruction evidence pass.",
        "",
        f"- status: `{report['status']}`",
        f"- queued candidates: `{report['intake_matrix']['queued_delivery_trust_case_candidates']}`",
        f"- blocked transitions: `{report['intake_matrix']['blocked_intake_transitions']}`",
        "- Delivery Trust Case Harness invocation: `blocked`",
        "- customer handoff package creation: `blocked`",
        "- customer-visible follow-up: `blocked`",
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
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / candidate: `{row['candidate_created']}` / reasons: {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = gate.build_all_case_artifacts()
    report = build_report()
    report_text = gate.dump_json(report)
    md = markdown_report(report)
    html = dual_loop.render_html_report("Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py --write"
            )
        print("ok    Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
