#!/usr/bin/env python3
"""Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate"
REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.json"
)
MARKDOWN_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.md"
)
HTML_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.html"
)
REPORT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate-v1.schema.json"
)
RECEIPT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-controlled-follow-up-feedback-boundary-receipt-v1.schema.json"
)


EXPECTED = {
    "pass-customer-signal": ("follow_up_envelope_refs_ready", [], True),
    "pass-operator-signal": ("follow_up_envelope_refs_ready", [], True),
    "pass-host-platform-agent-signal": ("follow_up_envelope_refs_ready", [], True),
    "blocked-missing-bridge-receipt": ("blocked", ["bridge_receipt_missing"], False),
    "blocked-invalid-bridge-receipt": ("blocked", ["bridge_receipt_invalid"], False),
    "blocked-missing-handoff-refs": ("blocked", ["handoff_refs_missing"], False),
    "blocked-handoff-refs-mismatch": ("blocked", ["handoff_refs_mismatch"], False),
    "blocked-missing-reconstruction": ("blocked", ["active_reconstruction_missing"], False),
    "blocked-passive-reconstruction": ("blocked", ["passive_reconstruction_rejected"], False),
    "blocked-unsupported-reconstruction-source": ("blocked", ["unsupported_reconstruction_source"], False),
    "blocked-missing-product-loop-ref": (
        "blocked",
        ["handoff_refs_mismatch", "product_loop_ref_missing"],
        False,
    ),
    "blocked-missing-dual-loop-ref": (
        "blocked",
        ["handoff_refs_mismatch", "dual_loop_ref_missing"],
        False,
    ),
    "blocked-missing-delivery-trust-case-ref": (
        "blocked",
        ["handoff_refs_mismatch", "delivery_trust_case_ref_missing"],
        False,
    ),
    "blocked-raw-follow-up-body": ("blocked", ["raw_follow_up_body_rejected"], False),
    "blocked-automatic-customer-send": ("blocked", ["automatic_customer_send_rejected"], False),
    "blocked-customer-visible-follow-up": ("blocked", ["customer_visible_follow_up_rejected"], False),
    "blocked-source-mutation": ("blocked", ["source_mutation_rejected"], False),
    "blocked-production-mutation": ("blocked", ["production_mutation_rejected"], False),
    "blocked-external-publication": ("blocked", ["external_publication_rejected"], False),
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
    receipt = gate.validate_boundary_receipt(
        artifacts["patch-proposal-controlled-follow-up-feedback-boundary-receipt.json"]
    )
    expected_status, expected_reasons, expected_refs = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    refs_created = receipt["envelope_refs"] is not None
    if refs_created is not expected_refs:
        raise RuntimeError(f"{case_id} envelope ref creation drifted")
    if refs_created:
        refs = gate.validate_envelope_refs(
            artifacts["patch-proposal-controlled-follow-up-feedback-envelope-refs.json"]
        )
        if refs != receipt["envelope_refs"]:
            raise RuntimeError(f"{case_id} standalone envelope refs drifted")
        summary = refs["harness_summary"]
        if summary["raw_follow_up_body_included"] is not False:
            raise RuntimeError(f"{case_id} must not include raw follow-up bodies")
        if summary["customer_visible_send_performed"] is not False:
            raise RuntimeError(f"{case_id} must not perform customer-visible sends")
    dual_loop.assert_metadata_only(
        receipt,
        label=f"patch-proposal-controlled-follow-up-feedback-boundary:{case_id}",
    )
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "envelope_refs_created": refs_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-controlled-follow-up-gate-") as tmp:
        output_dir = Path(tmp) / "gate"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-controlled-follow-up-feedback-boundary-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Boundary Gate CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch Proposal Controlled Follow-up Feedback Boundary Gate CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal Controlled Follow-up Feedback Boundary Gate CLI output drifted: {case_id}/{filename}"
                    )
            refs_path = output_dir / case_id / "patch-proposal-controlled-follow-up-feedback-envelope-refs.json"
            if expected_artifacts["patch-proposal-controlled-follow-up-feedback-boundary-receipt.json"]["status"] == "blocked":
                if refs_path.exists():
                    raise RuntimeError(f"blocked case must not include envelope refs: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        reconstruction_path = Path(tmp) / "reconstruction.json"
        gate.write_json(reconstruction_path, gate.default_reconstruction("pass-customer-signal"))
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py"),
                "--bridge-receipt",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge"
                    / "pass-customer-signal"
                    / "patch-proposal-controlled-follow-up-feedback-delivery-trust-case-bridge-receipt.json"
                ),
                "--handoff-refs",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge"
                    / "pass-customer-signal"
                    / "patch-proposal-controlled-follow-up-feedback-delivery-trust-case-handoff-refs.json"
                ),
                "--reconstruction",
                str(reconstruction_path),
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
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Boundary Gate custom CLI output drifted")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            gate.validate_boundary_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_follow_up_body_injected",
        lambda payload: payload.__setitem__("raw_follow_up_body", "private follow-up body"),
    )
    expect_rejected(
        "follow_up_body_injected",
        lambda payload: payload["envelope_refs"].__setitem__("follow_up_body", "private follow-up body"),
    )
    expect_rejected(
        "customer_send_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_customer_visible_send_performed",
            True,
        ),
    )
    expect_rejected(
        "automatic_customer_send_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_automatic_customer_send_performed",
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
            "study_anything_source_mutation_performed",
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
        "external_publication_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_external_publication_performed",
            True,
        ),
    )
    expect_rejected(
        "model_call_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected(
        "customer_send_policy_injected",
        lambda payload: payload["harness_policy"].__setitem__("customer_visible_send_allowed", True),
    )
    expect_rejected(
        "automatic_customer_send_policy_injected",
        lambda payload: payload["harness_policy"].__setitem__("automatic_customer_send_allowed", True),
    )
    expect_rejected(
        "customer_follow_up_policy_injected",
        lambda payload: payload["harness_policy"].__setitem__("customer_visible_follow_up_allowed", True),
    )
    expect_rejected(
        "model_call_policy_injected",
        lambda payload: payload["harness_policy"].__setitem__("model_call_allowed", True),
    )
    expect_rejected(
        "ready_receipt_without_envelope_refs",
        lambda payload: payload.__setitem__("envelope_refs", None),
    )
    expect_rejected(
        "blocked_receipt_with_envelope_refs",
        lambda payload: (
            payload.__setitem__("status", "blocked"),
            payload.__setitem__("decision", "block_controlled_follow_up_boundary"),
            payload.__setitem__("blocked_reasons", ["forced_block"]),
        ),
    )
    required = {
        "raw_follow_up_body_injected",
        "follow_up_body_injected",
        "customer_send_effect_injected",
        "automatic_customer_send_effect_injected",
        "customer_follow_up_effect_injected",
        "source_mutation_effect_injected",
        "production_mutation_effect_injected",
        "external_publication_effect_injected",
        "model_call_effect_injected",
        "customer_send_policy_injected",
        "automatic_customer_send_policy_injected",
        "customer_follow_up_policy_injected",
        "model_call_policy_injected",
        "ready_receipt_without_envelope_refs",
        "blocked_receipt_with_envelope_refs",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Patch Proposal Controlled Follow-up Feedback Boundary Gate negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Boundary Gate case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, gate.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, gate.RECEIPT_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-customer-signal"]["patch-proposal-controlled-follow-up-feedback-boundary-receipt.json"]
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
        actual_files = {path.name for path in case_dir.glob("*.json")}
        expected_files = set(artifacts)
        extra_files = sorted(actual_files - expected_files)
        if extra_files:
            raise SystemExit(
                f"Patch Proposal Controlled Follow-up Feedback Boundary Gate fixture has stale files: "
                f"{case_id}: {extra_files}"
            )
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing Patch Proposal Controlled Follow-up Feedback Boundary Gate fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch Proposal Controlled Follow-up Feedback Boundary Gate fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py --write"
                )
        refs_path = case_dir / "patch-proposal-controlled-follow-up-feedback-envelope-refs.json"
        if (
            artifacts["patch-proposal-controlled-follow-up-feedback-boundary-receipt.json"]["status"] == "blocked"
            and refs_path.exists()
        ):
            raise SystemExit(f"Blocked Patch Proposal Controlled Follow-up Feedback Boundary Gate case must not include refs: {case_id}")


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate",
        "",
        "Metadata-only proof that Delivery Trust case/handoff refs prepare only follow-up envelope refs after active boundary reconstruction.",
        "",
        f"- status: `{report['status']}`",
        f"- ready envelope ref sets: `{report['boundary_matrix']['ready_follow_up_envelope_ref_sets']}`",
        f"- blocked transitions: `{report['boundary_matrix']['blocked_follow_up_transitions']}`",
        "- raw follow-up bodies: `blocked`",
        "- automatic customer sends and customer-visible follow-up: `blocked`",
        "- source, production, and external publication effects: `blocked`",
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
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / refs: `{row['envelope_refs_created']}` / reasons: {reasons}"
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
    html = dual_loop.render_html_report("Patch Proposal Controlled Follow-up Feedback Boundary Gate", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote Patch Proposal Controlled Follow-up Feedback Boundary Gate fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Boundary Gate report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Boundary Gate markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Boundary Gate HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py --write"
            )
        print("ok    Patch Proposal Controlled Follow-up Feedback Boundary Gate report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
