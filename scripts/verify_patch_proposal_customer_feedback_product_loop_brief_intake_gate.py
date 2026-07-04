#!/usr/bin/env python3
"""Verify Patch Proposal Product Loop Brief Intake Gate artifacts."""

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
import patch_proposal_customer_feedback_product_loop_brief_intake_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-product-loop-brief-intake-gate"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-product-loop-brief-intake-gate.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-product-loop-brief-intake-gate.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-product-loop-brief-intake-gate.html"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-feedback-product-loop-brief-intake-receipt-v1.schema.json"
REPORT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-feedback-product-loop-brief-intake-gate-v1.schema.json"
SCENARIO_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-scenario-v1.schema.json"
RUN_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "product-loop-run-v1.schema.json"


EXPECTED = {
    "pass-customer-signal": (
        "created_product_loop_scenario_run_candidate",
        "create_patch_proposal_product_loop_scenario_run_candidate",
        [],
        True,
        True,
    ),
    "pass-operator-signal": (
        "created_product_loop_scenario_run_candidate",
        "create_patch_proposal_product_loop_scenario_run_candidate",
        [],
        True,
        True,
    ),
    "pass-host-platform-agent-signal": (
        "created_product_loop_scenario_run_candidate",
        "create_patch_proposal_product_loop_scenario_run_candidate",
        [],
        True,
        True,
    ),
    "blocked-missing-brief-candidate": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["patch_proposal_brief_candidate_missing"],
        False,
        False,
    ),
    "blocked-invalid-brief-candidate": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["patch_proposal_brief_candidate_invalid"],
        False,
        False,
    ),
    "blocked-missing-product-loop-reconstruction": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["product_loop_reconstruction_missing"],
        False,
        False,
    ),
    "blocked-ai-review-only": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["ai_review_only_evidence_rejected"],
        False,
        False,
    ),
    "blocked-skip-to-delivery-trust": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["requested_next_boundary_not_product_loop_harness_candidate"],
        False,
        False,
    ),
    "blocked-customer-visible-follow-up": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["customer_visible_follow_up_rejected"],
        False,
        False,
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["source_mutation_rejected"],
        False,
        False,
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["production_mutation_rejected"],
        False,
        False,
    ),
    "blocked-secret": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["secret_rejected"],
        False,
        False,
    ),
    "blocked-model-credential": (
        "blocked",
        "block_patch_proposal_product_loop_brief_intake_gate",
        ["model_credential_rejected"],
        False,
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
    receipt = gate.validate_intake_receipt(
        artifacts["patch-proposal-product-loop-brief-intake-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons, expected_scenario, expected_run = EXPECTED[case_id]
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
        if scenario["source"]["source_type"] != "patch_proposal_product_loop_brief_candidate":
            raise RuntimeError(f"{case_id} scenario source drifted")
        if run["evidence_refs"]["product_spec_evals_ref"] != "patch-proposal-product-loop-brief-candidate.json":
            raise RuntimeError(f"{case_id} run evidence ref drifted")
        if artifacts["product-loop-scenario.json"] != receipt["scenario"]:
            raise RuntimeError(f"{case_id} standalone scenario drifted")
        if artifacts["product-loop-run.json"] != receipt["run"]:
            raise RuntimeError(f"{case_id} standalone run drifted")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-product-loop-brief-intake:{case_id}")
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
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_product_loop_brief_intake_gate.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-product-loop-brief-intake-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Patch Proposal Product Loop Brief Intake CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch Proposal Product Loop Brief Intake CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal Product Loop Brief Intake CLI output drifted: {case_id}/{filename}"
                    )
            scenario_path = output_dir / case_id / "product-loop-scenario.json"
            run_path = output_dir / case_id / "product-loop-run.json"
            if expected_artifacts["patch-proposal-product-loop-brief-intake-receipt.json"]["status"] == "blocked":
                if scenario_path.exists() or run_path.exists():
                    raise RuntimeError(f"blocked case must not include scenario/run: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_product_loop_brief_intake_gate.py"),
                "--brief-candidate",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-spec-eval-authoring-gate"
                    / "pass-customer-signal"
                    / "patch-proposal-product-loop-brief-candidate.json"
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
            raise RuntimeError("Patch Proposal Product Loop Brief Intake custom CLI output drifted")
        if not (custom_output_dir / "custom" / "patch-proposal-product-loop-brief-intake-receipt.json").is_file():
            raise RuntimeError("Patch Proposal Product Loop Brief Intake custom CLI missing receipt")


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
        lambda payload: payload["requested_transition"].__setitem__(
            "customer_visible_follow_up_requested",
            True,
        ),
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
        "blocked_receipt_with_run",
        lambda payload: (
            payload.__setitem__("status", "blocked"),
            payload.__setitem__("decision", "block_patch_proposal_product_loop_brief_intake_gate"),
            payload.__setitem__("blocked_reasons", ["forced_block"]),
        ),
    )

    required = {
        "raw_brief_body_injected",
        "ai_review_only_policy_injected",
        "delivery_trust_invocation_policy_injected",
        "customer_follow_up_transition_injected",
        "source_mutation_effect_injected",
        "production_mutation_effect_injected",
        "delivery_trust_harness_invoked_effect_injected",
        "blocked_receipt_with_run",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Patch Proposal Product Loop Brief Intake negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Product Loop Brief Intake case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, gate.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
        schema_report(SCENARIO_SCHEMA_FILE, product_loop_harness.PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION),
        schema_report(RUN_SCHEMA_FILE, product_loop_harness.PRODUCT_LOOP_RUN_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-customer-signal"]["patch-proposal-product-loop-brief-intake-receipt.json"]
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
                raise SystemExit(f"Missing Patch Proposal Product Loop Brief Intake fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch Proposal Product Loop Brief Intake fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_product_loop_brief_intake_gate.py --write"
                )
        scenario_path = case_dir / "product-loop-scenario.json"
        run_path = case_dir / "product-loop-run.json"
        if (
            artifacts["patch-proposal-product-loop-brief-intake-receipt.json"]["status"] == "blocked"
            and (scenario_path.exists() or run_path.exists())
        ):
            raise SystemExit(
                f"Blocked Patch Proposal Product Loop Brief Intake case must not include scenario/run: {case_id}"
            )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Product Loop Brief Intake Gate",
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
    html = dual_loop.render_html_report("Patch Proposal Product Loop Brief Intake Gate", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote Patch Proposal Product Loop Brief Intake fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Product Loop Brief Intake report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_product_loop_brief_intake_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Product Loop Brief Intake markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_product_loop_brief_intake_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Product Loop Brief Intake HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_product_loop_brief_intake_gate.py --write"
            )
        print("ok    Patch Proposal Product Loop Brief Intake report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
