#!/usr/bin/env python3
"""Verify controlled follow-up feedback reopen-intake Product Loop brief intake artifacts."""

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

from study_anything.core import dual_loop, product_loop_harness  # noqa: E402
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate.html"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt-v1.schema.json"
REPORT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate-v1.schema.json"
SCENARIO_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-scenario-v1.schema.json"
RUN_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-run-v1.schema.json"


CREATE_DECISION = "create_patch_proposal_reopen_intake_product_loop_scenario_run_candidate"
BLOCK_DECISION = "block_patch_proposal_reopen_intake_product_loop_brief_intake_gate"

EXPECTED_REASON_BY_CASE = {
    "blocked-missing-authoring-receipt": "source_authoring_receipt_missing",
    "blocked-authoring-blocked": "source_authoring_receipt_not_allowed",
    "blocked-missing-brief-candidate-ref": "source_brief_candidate_ref_missing",
    "blocked-missing-gate-ref": "reopen_intake_gate_receipt_missing",
    "blocked-missing-bridge-ref": "reopen_intake_bridge_ref_missing",
    "blocked-missing-closure-ref": "closure_ref_missing",
    "blocked-missing-outcome-ref": "outcome_ref_missing",
    "blocked-missing-action-ref": "action_ref_missing",
    "blocked-missing-actor-ref": "external_actor_ref_missing",
    "blocked-missing-intake-candidate-ref": "intake_candidate_ref_missing",
    "blocked-missing-intake-item-ref": "product_loop_intake_item_ref_missing",
    "blocked-missing-backlog-signal-ref": "backlog_signal_ref_missing",
    "blocked-missing-product-owner-ref": "product_owner_reconstruction_missing",
    "blocked-missing-product-loop-reconstruction": "product_loop_reconstruction_missing",
    "blocked-missing-claim-boundary": "claim_boundary_missing",
    "blocked-missing-privacy-boundary": "privacy_boundary_missing",
    "blocked-raw-brief-body": "raw_brief_body_rejected",
    "blocked-raw-spec-body": "raw_spec_body_rejected",
    "blocked-raw-eval-body": "raw_eval_body_rejected",
    "blocked-raw-follow-up-data": "raw_follow_up_data_rejected",
    "blocked-raw-customer-data": "raw_customer_data_rejected",
    "blocked-raw-backlog-data": "raw_backlog_data_rejected",
    "blocked-customer-identity": "customer_identity_rejected",
    "blocked-automatic-backlog-creation": "automatic_backlog_creation_rejected",
    "blocked-automatic-priority-assignment": "automatic_priority_assignment_rejected",
    "blocked-ai-review-only": "ai_review_only_evidence_rejected",
    "blocked-skip-to-delivery-trust": "requested_next_boundary_not_product_loop_harness_candidate",
    "blocked-delivery-trust-invocation": "delivery_trust_harness_invocation_rejected",
    "blocked-automatic-execution": "automatic_execution_rejected",
    "blocked-customer-contact": "customer_contact_rejected",
    "blocked-product-loop-backlog-mutation": "product_loop_backlog_mutation_rejected",
    "blocked-source-mutation": "source_mutation_rejected",
    "blocked-production-mutation": "production_mutation_rejected",
    "blocked-external-publication-payload": "external_publication_payload_rejected",
    "blocked-model-call": "model_call_rejected",
    "blocked-secret": "secret_rejected",
    "blocked-model-credential": "model_credential_rejected",
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
    receipt = gate.validate_intake_receipt(
        artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"]
    )
    expected_status = "created_product_loop_scenario_run_candidate" if case_id == "pass" else "blocked"
    expected_decision = CREATE_DECISION if case_id == "pass" else BLOCK_DECISION
    expected_reasons = [] if case_id == "pass" else [EXPECTED_REASON_BY_CASE[case_id]]
    expected_scenario = case_id == "pass"
    expected_run = case_id == "pass"
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    scenario_created = receipt["scenario"] is not None
    run_created = receipt["run"] is not None
    if scenario_created is not expected_scenario:
        raise RuntimeError(f"{case_id} scenario creation drifted")
    if run_created is not expected_run:
        raise RuntimeError(f"{case_id} run creation drifted")
    if scenario_created:
        scenario = product_loop_harness.validate_product_loop_scenario(receipt["scenario"])
        run = product_loop_harness.validate_product_loop_run(receipt["run"])
        if scenario["source"]["source_type"] != "patch_proposal_reopen_intake_product_loop_brief_candidate":
            raise RuntimeError(f"{case_id} scenario source drifted")
        if run["evidence_refs"]["product_spec_evals_ref"] != "patch-proposal-product-loop-brief-candidate.json":
            raise RuntimeError(f"{case_id} run evidence ref drifted")
        brief_ref = scenario["loops"]["agentic_coding_loop"].get("patch_proposal_brief_candidate_ref")
        if not isinstance(brief_ref, Mapping):
            raise RuntimeError(f"{case_id} missing brief candidate ref")
        for key in (
            "source_reopen_intake_gate_ref",
            "source_reopen_intake_bridge_ref",
            "closure_receipt_hash",
            "outcome_receipt_hash",
            "action_ref_hash",
            "external_actor_ref_hash",
            "intake_candidate_ref_hash",
            "product_loop_intake_item_ref_hash",
        ):
            if not isinstance(brief_ref.get(key), str) or not brief_ref.get(key):
                raise RuntimeError(f"{case_id} missing reopen-intake ref: {key}")
        if artifacts["product-loop-scenario.json"] != receipt["scenario"]:
            raise RuntimeError(f"{case_id} standalone scenario drifted")
        if artifacts["product-loop-run.json"] != receipt["run"]:
            raise RuntimeError(f"{case_id} standalone run drifted")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "scenario_created": scenario_created,
        "run_created": run_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-product-loop-intake-") as tmp:
        output_dir = Path(tmp) / "gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py"),
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
        dual_loop.assert_metadata_only(
            stdout,
            label="patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-cli",
        )
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Patch Proposal reopen-intake Product Loop brief intake CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(
                        f"Patch Proposal reopen-intake Product Loop brief intake CLI missing {case_id}/{filename}"
                    )
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal reopen-intake Product Loop brief intake CLI output drifted: {case_id}/{filename}"
                    )
            scenario_path = output_dir / case_id / "product-loop-scenario.json"
            run_path = output_dir / case_id / "product-loop-run.json"
            if expected_artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"]["status"] == "blocked":
                if scenario_path.exists() or run_path.exists():
                    raise RuntimeError(f"blocked case must not include scenario/run: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py"),
                "--brief-candidate",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate"
                    / "pass"
                    / "patch-proposal-product-loop-brief-candidate.json"
                ),
                "--authoring-receipt",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate"
                    / "pass"
                    / "patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"
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
            raise RuntimeError("Patch Proposal reopen-intake Product Loop brief intake custom CLI output drifted")
        if not (
            custom_output_dir
            / "custom"
            / "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"
        ).is_file():
            raise RuntimeError("Patch Proposal reopen-intake Product Loop brief intake custom CLI missing receipt")


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
        "raw_brief_body_injected",
        lambda payload: payload["scenario"]["loops"]["agentic_coding_loop"][
            "patch_proposal_brief_candidate_ref"
        ].__setitem__("raw_brief_body", "private brief body"),
    )
    expect_rejected(
        "ai_review_only_policy_injected",
        lambda payload: payload["intake_policy"].__setitem__("ai_review_only_allowed", True),
    )
    expect_rejected(
        "delivery_trust_invocation_policy_injected",
        lambda payload: payload["intake_policy"].__setitem__("delivery_trust_harness_invocation_allowed", True),
    )
    expect_rejected(
        "customer_follow_up_transition_injected",
        lambda payload: payload["requested_transition"].__setitem__("customer_contact_requested", True),
    )
    expect_rejected(
        "automatic_execution_transition_injected",
        lambda payload: payload["requested_transition"].__setitem__("automatic_execution_requested", True),
    )
    expect_rejected(
        "external_publication_transition_injected",
        lambda payload: payload["requested_transition"].__setitem__("external_publication_payload_attached", True),
    )
    expect_rejected(
        "model_call_transition_injected",
        lambda payload: payload["requested_transition"].__setitem__("model_call_requested", True),
    )
    expect_rejected(
        "source_mutation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_source_mutation_performed", True),
    )
    expect_rejected(
        "production_mutation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_production_mutation_performed",
            True,
        ),
    )
    expect_rejected(
        "delivery_trust_harness_invoked_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_delivery_trust_harness_invoked", True),
    )
    expect_rejected(
        "model_call_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected(
        "blocked_receipt_with_run",
        lambda payload: (
            payload.__setitem__("status", "blocked"),
            payload.__setitem__("decision", BLOCK_DECISION),
            payload.__setitem__("blocked_reasons", ["forced_block"]),
        ),
    )

    required = {
        "raw_brief_body_injected",
        "ai_review_only_policy_injected",
        "delivery_trust_invocation_policy_injected",
        "customer_follow_up_transition_injected",
        "automatic_execution_transition_injected",
        "external_publication_transition_injected",
        "model_call_transition_injected",
        "source_mutation_effect_injected",
        "production_mutation_effect_injected",
        "delivery_trust_harness_invoked_effect_injected",
        "model_call_effect_injected",
        "blocked_receipt_with_run",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Patch Proposal reopen-intake Product Loop brief intake negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal reopen-intake Product Loop brief intake case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, gate.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(SCENARIO_SCHEMA_FILE, product_loop_harness.PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION),
        schema_report(RUN_SCHEMA_FILE, product_loop_harness.PRODUCT_LOOP_RUN_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass"]["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"]
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
                raise SystemExit(f"Missing Patch Proposal reopen-intake Product Loop brief intake fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                f"Patch Proposal reopen-intake Product Loop brief intake fixture is out of date: {path}. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py --write"
            )
        scenario_path = case_dir / "product-loop-scenario.json"
        run_path = case_dir / "product-loop-run.json"
        if (
            artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"]["status"] == "blocked"
            and (scenario_path.exists() or run_path.exists())
        ):
            raise SystemExit(
                f"Blocked Patch Proposal reopen-intake Product Loop brief intake case must not include scenario/run: {case_id}"
            )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate",
        "",
        "Metadata-only proof that Patch Proposal Product Loop brief candidates can become Product Loop scenario/run candidates only after active developer/product-loop reconstruction.",
        "",
        f"- status: `{report['status']}`",
        f"- schema: `{report['schema_version']}`",
        f"- created Product Loop candidates: `{report['intake_matrix']['created_product_loop_candidates']}`",
        f"- blocked intake transitions: `{report['intake_matrix']['blocked_intake_transitions']}`",
        "- Delivery Trust Harness invocation: `blocked`",
        "- customer-visible follow-up: `blocked`",
        "- source and production mutation: `blocked`",
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
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / scenario: `{row['scenario_created']}` / run: `{row['run_created']}` / reasons: {reasons}"
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
    html = dual_loop.render_html_report("Patch Proposal Reopen Intake Product Loop Brief Intake Gate", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote Patch Proposal reopen-intake Product Loop brief intake fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal reopen-intake Product Loop brief intake report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal reopen-intake Product Loop brief intake markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal reopen-intake Product Loop brief intake HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py --write"
            )
        print("ok    Patch Proposal reopen-intake Product Loop brief intake report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
