#!/usr/bin/env python3
"""Verify controlled follow-up feedback reopen-intake Product Owner gate artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate"
REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.json"
)
MARKDOWN_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.md"
)
HTML_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.html"
)
REPORT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate-v1.schema.json"
)
RECEIPT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt-v1.schema.json"
)
CANDIDATE_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-product-spec-eval-candidate-v1.schema.json"

EXPECTED = {
    "pass": ("queued_for_spec_eval_candidate", "create_patch_proposal_spec_eval_candidate", [], True),
    "blocked-missing-backlog-bridge-receipt": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_missing", "source_backlog_signal_missing"],
        False,
    ),
    "blocked-bridge-blocked": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "source_reopen_intake_gate_not_allowed"],
        False,
    ),
    "blocked-missing-gate-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "reopen_intake_gate_receipt_missing"],
        False,
    ),
    "blocked-missing-bridge-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "reopen_intake_bridge_ref_missing"],
        False,
    ),
    "blocked-missing-closure-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "closure_ref_missing"],
        False,
    ),
    "blocked-missing-outcome-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "outcome_ref_missing"],
        False,
    ),
    "blocked-missing-action-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "action_ref_missing"],
        False,
    ),
    "blocked-missing-actor-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "external_actor_ref_missing"],
        False,
    ),
    "blocked-missing-intake-candidate-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "intake_candidate_ref_missing"],
        False,
    ),
    "blocked-missing-intake-item-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "product_loop_intake_item_ref_missing"],
        False,
    ),
    "blocked-missing-backlog-signal-ref": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["backlog_signal_ref_missing"],
        False,
    ),
    "blocked-missing-owner-reconstruction": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["product_owner_reconstruction_missing"],
        False,
    ),
    "blocked-missing-claim-boundary": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "claim_boundary_missing"],
        False,
    ),
    "blocked-missing-privacy-boundary": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "privacy_boundary_missing"],
        False,
    ),
    "blocked-raw-follow-up-data": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "raw_follow_up_data_rejected"],
        False,
    ),
    "blocked-raw-customer-data": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "raw_customer_data_rejected"],
        False,
    ),
    "blocked-raw-backlog-data": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["raw_backlog_data_rejected"],
        False,
    ),
    "blocked-customer-identity": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "customer_identity_rejected"],
        False,
    ),
    "blocked-automatic-customer-contact": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "automatic_customer_contact_rejected"],
        False,
    ),
    "blocked-automatic-backlog-creation": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "automatic_backlog_creation_rejected"],
        False,
    ),
    "blocked-automatic-priority-assignment": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["automatic_priority_assignment_rejected"],
        False,
    ),
    "blocked-skip-to-delivery-harness": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["requested_next_boundary_not_product_spec_eval_candidate_queue"],
        False,
    ),
    "blocked-automatic-execution": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["automatic_execution_rejected"],
        False,
    ),
    "blocked-product-loop-backlog-mutation": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "product_loop_backlog_mutation_rejected"],
        False,
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_mutation_rejected"],
        False,
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["production_mutation_rejected"],
        False,
    ),
    "blocked-external-publication-payload": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["source_reopen_intake_backlog_bridge_not_allowed", "external_publication_payload_rejected"],
        False,
    ),
    "blocked-model-call": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
        ["model_call_rejected"],
        False,
    ),
    "blocked-secret": ("blocked", "block_patch_proposal_product_owner_gate", ["secret_rejected"], False),
    "blocked-model-credential": (
        "blocked",
        "block_patch_proposal_product_owner_gate",
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
    receipt = gate.validate_product_owner_receipt(
        artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons, expected_candidate = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    candidate_created = receipt["candidate"] is not None
    if candidate_created is not expected_candidate:
        raise RuntimeError(f"{case_id} candidate creation drifted")
    if candidate_created:
        candidate = gate.validate_candidate(artifacts["patch-proposal-product-spec-eval-candidate.json"])
        if candidate != receipt["candidate"]:
            raise RuntimeError(f"{case_id} standalone candidate drifted")
    dual_loop.assert_metadata_only(
        receipt,
        label=f"patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-gate:{case_id}",
    )
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "candidate_created": candidate_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-controlled-follow-up-feedback-reopen-intake-owner-") as tmp:
        output_dir = Path(tmp) / "gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "scripts"
                    / "patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate.py"
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
        dual_loop.assert_metadata_only(
            stdout,
            label="patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-gate-cli",
        )
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Controlled follow-up reopen-intake Product Owner gate CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Controlled follow-up reopen-intake Product Owner gate CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Controlled follow-up reopen-intake Product Owner gate CLI output drifted: {case_id}/{filename}")
            candidate_path = output_dir / case_id / "patch-proposal-product-spec-eval-candidate.json"
            if (
                expected_artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]["status"]
                == "queued_for_spec_eval_candidate"
            ):
                if not candidate_path.is_file():
                    raise RuntimeError(f"Controlled follow-up reopen-intake Product Owner gate CLI missing candidate: {case_id}")
            elif candidate_path.exists():
                raise RuntimeError(f"Controlled follow-up reopen-intake Product Owner gate CLI created candidate for blocked case: {case_id}")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            gate.validate_product_owner_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "product_owner_identity_injected",
        lambda payload: payload["product_owner_reconstruction"].__setitem__("product_owner_identity", "private owner"),
    )
    expect_rejected("priority_score_injected", lambda payload: payload["candidate"].__setitem__("priority_score", 99))
    expect_rejected(
        "raw_product_spec_injected",
        lambda payload: payload["candidate"].__setitem__("raw_product_spec", "private spec body"),
    )
    expect_rejected(
        "raw_eval_body_injected",
        lambda payload: payload["candidate"].__setitem__("raw_eval_body", "private eval prompt"),
    )
    expect_rejected(
        "raw_backlog_data_injected",
        lambda payload: payload["candidate"].__setitem__("raw_backlog_data", "private backlog body"),
    )
    expect_rejected(
        "automatic_backlog_creation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_backlog_item_created", True),
    )
    expect_rejected(
        "automatic_priority_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_priority_assignment_performed", True
        ),
    )
    expect_rejected(
        "automatic_execution_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_automatic_execution_performed", True
        ),
    )
    expect_rejected(
        "automatic_customer_contact_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_customer_visible_follow_up_performed", True
        ),
    )
    expect_rejected(
        "product_loop_backlog_mutation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_product_loop_backlog_mutation_performed", True
        ),
    )
    expect_rejected(
        "source_mutation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_repository_mutation_performed", True
        ),
    )
    expect_rejected(
        "production_mutation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_production_mutation_performed", True
        ),
    )
    expect_rejected(
        "external_publication_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_external_publication_performed", True
        ),
    )
    expect_rejected(
        "model_call_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected("candidate_ready_for_execution", lambda payload: payload["candidate"].__setitem__("ready_for_execution", True))
    expect_rejected(
        "candidate_skip_to_delivery_trust",
        lambda payload: payload["candidate"].__setitem__("ready_for_delivery_trust_harness", True),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Controlled follow-up reopen-intake Product Owner gate case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, gate.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(CANDIDATE_SCHEMA_FILE, gate.CANDIDATE_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass"]["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]
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
                raise SystemExit(
                    f"Missing controlled follow-up reopen-intake Product Owner gate fixture: {path}"
                )
            if load_json(path) != payload:
                raise SystemExit(
                    f"Controlled follow-up reopen-intake Product Owner gate fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate.py --write"
                )
        candidate_path = case_dir / "patch-proposal-product-spec-eval-candidate.json"
        if (
            artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]["status"] == "blocked"
            and candidate_path.exists()
        ):
            raise SystemExit(
                "Blocked controlled follow-up reopen-intake Product Owner gate case must not include "
                f"candidate: {candidate_path}"
            )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate",
        "",
        "Metadata-only proof that controlled follow-up feedback reopen-intake backlog signals can become spec/eval candidates only after active Product Owner boundary reconstruction.",
        "",
        f"- status: `{report['status']}`",
        f"- schema: `{report['schema_version']}`",
        f"- queued spec/eval candidates: `{report['product_owner_matrix']['queued_spec_eval_candidates']}`",
        f"- blocked transitions: `{report['product_owner_matrix']['blocked_product_owner_transitions']}`",
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


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Controlled Follow-up Feedback Reopen Intake Product Owner Gate</title>\n"
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
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote controlled follow-up reopen-intake Product Owner gate fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Controlled follow-up reopen-intake Product Owner gate report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Controlled follow-up reopen-intake Product Owner gate markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Controlled follow-up reopen-intake Product Owner gate HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate.py --write"
            )
        print("ok    controlled follow-up reopen-intake Product Owner gate report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
