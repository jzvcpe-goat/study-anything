#!/usr/bin/env python3
"""Verify Patch Proposal controlled follow-up feedback Spec/Eval Authoring Gate artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate.html"
REPORT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate-v1.schema.json"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt-v1.schema.json"
BRIEF_CANDIDATE_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-product-loop-brief-candidate-v1.schema.json"

EXPECTED = {
    "pass-customer-signal": ("queued_for_product_loop_brief_candidate", "create_patch_proposal_product_loop_brief_candidate", [], True),
    "pass-operator-signal": ("queued_for_product_loop_brief_candidate", "create_patch_proposal_product_loop_brief_candidate", [], True),
    "pass-host-platform-agent-signal": (
        "queued_for_product_loop_brief_candidate",
        "create_patch_proposal_product_loop_brief_candidate",
        [],
        True,
    ),
    "blocked-missing-authoring-reconstruction": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["authoring_reconstruction_missing"],
        False,
    ),
    "blocked-raw-spec-body": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["raw_spec_body_rejected"],
        False,
    ),
    "blocked-raw-eval-body": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["raw_eval_body_rejected"],
        False,
    ),
    "blocked-automatic-execution": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["automatic_execution_rejected"],
        False,
    ),
    "blocked-skip-to-delivery-trust": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["requested_next_boundary_not_product_loop_brief_intake"],
        False,
    ),
    "blocked-customer-visible-follow-up": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["customer_visible_follow_up_rejected"],
        False,
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["source_mutation_rejected"],
        False,
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["production_mutation_rejected"],
        False,
    ),
    "blocked-invalid-product-owner-candidate": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["source_spec_eval_candidate_invalid"],
        False,
    ),
    "blocked-model-call": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
        ["model_call_rejected"],
        False,
    ),
    "blocked-secret": ("blocked", "block_patch_proposal_spec_eval_authoring_gate", ["secret_rejected"], False),
    "blocked-model-credential": (
        "blocked",
        "block_patch_proposal_spec_eval_authoring_gate",
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
    receipt = gate.validate_authoring_receipt(
        artifacts["patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons, expected_brief_candidate = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    brief_candidate_created = receipt["brief_candidate"] is not None
    if brief_candidate_created is not expected_brief_candidate:
        raise RuntimeError(f"{case_id} brief candidate creation drifted")
    if brief_candidate_created:
        brief_candidate = gate.validate_brief_candidate(
            artifacts["patch-proposal-product-loop-brief-candidate.json"]
        )
        if brief_candidate != receipt["brief_candidate"]:
            raise RuntimeError(f"{case_id} standalone brief candidate drifted")
    dual_loop.assert_metadata_only(
        receipt,
        label=f"patch-proposal-controlled-follow-up-feedback-spec-eval-authoring:{case_id}",
    )
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "brief_candidate_created": brief_candidate_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-feedback-spec-eval-") as tmp:
        output_dir = Path(tmp) / "gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py"),
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
            label="patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-cli",
        )
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Patch Proposal Spec/Eval authoring CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch Proposal Spec/Eval authoring CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal Spec/Eval authoring CLI output drifted: {case_id}/{filename}"
                    )
            brief_candidate_path = output_dir / case_id / "patch-proposal-product-loop-brief-candidate.json"
            if (
                expected_artifacts["patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt.json"]["status"]
                == "queued_for_product_loop_brief_candidate"
            ):
                if not brief_candidate_path.is_file():
                    raise RuntimeError(f"Patch Proposal Spec/Eval authoring CLI missing brief candidate: {case_id}")
            elif brief_candidate_path.exists():
                raise RuntimeError(
                    f"Patch Proposal Spec/Eval authoring CLI created brief candidate for blocked case: {case_id}"
                )

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py"),
                "--product-owner-candidate",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-product-owner-gate"
                    / "pass-customer-signal"
                    / "patch-proposal-product-spec-eval-candidate.json"
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
            raise RuntimeError("Patch Proposal Spec/Eval authoring custom CLI output drifted")
        if not (
            custom_output_dir / "custom" / "patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt.json"
        ).is_file():
            raise RuntimeError("Patch Proposal Spec/Eval authoring custom CLI missing receipt")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            gate.validate_authoring_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_product_spec_injected",
        lambda payload: payload["brief_candidate"].__setitem__("raw_product_spec", "private spec body"),
    )
    expect_rejected(
        "eval_prompt_injected",
        lambda payload: payload["brief_candidate"]["eval_plan_refs"][0].__setitem__(
            "eval_prompt",
            "private eval prompt",
        ),
    )
    expect_rejected(
        "acceptance_criteria_text_injected",
        lambda payload: payload["brief_candidate"]["acceptance_criteria_refs"][0].__setitem__(
            "acceptance_criteria_text",
            "private criterion",
        ),
    )
    expect_rejected(
        "brief_candidate_ready_for_execution",
        lambda payload: payload["brief_candidate"].__setitem__("ready_for_execution", True),
    )
    expect_rejected(
        "brief_candidate_skip_to_delivery_trust",
        lambda payload: payload["brief_candidate"].__setitem__("ready_for_delivery_trust_harness", True),
    )
    expect_rejected(
        "automatic_execution_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_automatic_execution_performed",
            True,
        ),
    )
    expect_rejected(
        "customer_follow_up_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_customer_visible_follow_up_performed",
            True,
        ),
    )
    expect_rejected(
        "source_mutation_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_repository_mutation_performed",
            True,
        ),
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
        "blocked_receipt_with_brief_candidate",
        lambda payload: (
            payload.__setitem__("status", "blocked"),
            payload.__setitem__("decision", "block_patch_proposal_spec_eval_authoring_gate"),
            payload.__setitem__("blocked_reasons", ["forced_block"]),
        ),
    )

    required = {
        "raw_product_spec_injected",
        "eval_prompt_injected",
        "acceptance_criteria_text_injected",
        "brief_candidate_ready_for_execution",
        "brief_candidate_skip_to_delivery_trust",
        "automatic_execution_effect_injected",
        "customer_follow_up_effect_injected",
        "source_mutation_effect_injected",
        "production_mutation_effect_injected",
        "model_call_effect_injected",
        "blocked_receipt_with_brief_candidate",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Patch Proposal Spec/Eval authoring negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Spec/Eval authoring case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, gate.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(BRIEF_CANDIDATE_SCHEMA_FILE, gate.BRIEF_CANDIDATE_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-customer-signal"]["patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt.json"]
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
                raise SystemExit(f"Missing patch proposal Spec/Eval authoring fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal Spec/Eval authoring fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py --write"
                )
        brief_candidate_path = case_dir / "patch-proposal-product-loop-brief-candidate.json"
        if (
            artifacts["patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt.json"]["status"] == "blocked"
            and brief_candidate_path.exists()
        ):
            raise SystemExit(
                f"Blocked patch proposal Spec/Eval authoring case must not include brief candidate: {brief_candidate_path}"
            )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate",
        "",
        "Metadata-only proof that Patch Proposal controlled follow-up feedback spec/eval candidates can become Product Loop brief candidates only after active authoring-boundary reconstruction.",
        "",
        f"- status: `{report['status']}`",
        f"- schema: `{report['schema_version']}`",
        f"- queued Product Loop brief candidates: `{report['authoring_matrix']['queued_product_loop_brief_candidates']}`",
        f"- blocked authoring transitions: `{report['authoring_matrix']['blocked_authoring_transitions']}`",
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
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / brief candidate: `{row['brief_candidate_created']}` / reasons: {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Controlled Follow-up Feedback Spec/Eval Authoring Gate</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


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
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal customer feedback Spec/Eval authoring fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch proposal customer feedback Spec/Eval authoring report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch proposal customer feedback Spec/Eval authoring markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch proposal customer feedback Spec/Eval authoring HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py --write"
            )
        print("ok    patch proposal customer feedback Spec/Eval authoring report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
