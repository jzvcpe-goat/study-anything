#!/usr/bin/env python3
"""Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal artifacts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal as rehearsal  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal"
REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal.json"
)
MARKDOWN_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal.md"
)
HTML_REPORT = (
    ROOT
    / "platform"
    / "generated"
    / "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal.html"
)
REPORT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal-v1.schema.json"
)
RECEIPT_SCHEMA_FILE = (
    ROOT
    / "platform"
    / "schemas"
    / "cbb"
    / "patch-proposal-controlled-follow-up-feedback-rehearsal-receipt-v1.schema.json"
)


EXPECTED = {
    "pass-customer-signal": ("ready", "ready_for_local_follow_up_feedback_rehearsal_review", []),
    "pass-operator-signal": ("ready", "ready_for_local_follow_up_feedback_rehearsal_review", []),
    "pass-host-platform-agent-signal": ("ready", "ready_for_local_follow_up_feedback_rehearsal_review", []),
    "blocked-missing-envelope-refs": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["source_envelope_refs_not_ready"],
    ),
    "blocked-invalid-envelope-refs": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["source_envelope_refs_not_ready"],
    ),
    "blocked-passive-rehearsal": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["active_rehearsal_missing", "passive_rehearsal_rejected"],
    ),
    "blocked-unsupported-rehearsal-source": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["unsupported_rehearsal_source"],
    ),
    "blocked-missing-active-reconstruction-ref": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["source_envelope_refs_not_ready", "active_reconstruction_ref_missing"],
    ),
    "blocked-missing-product-loop-ref": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["product_loop_ref_missing"],
    ),
    "blocked-missing-dual-loop-ref": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["dual_loop_ref_missing"],
    ),
    "blocked-missing-delivery-trust-ref": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["delivery_trust_ref_missing"],
    ),
    "blocked-raw-follow-up-preview": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["raw_follow_up_preview_rejected"],
    ),
    "blocked-customer-visible-draft": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["customer_visible_draft_rejected"],
    ),
    "blocked-automatic-customer-send": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["automatic_customer_send_rejected"],
    ),
    "blocked-source-mutation": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["source_mutation_rejected"],
    ),
    "blocked-production-mutation": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["production_mutation_rejected"],
    ),
    "blocked-external-publication": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["external_publication_rejected"],
    ),
    "blocked-model-call": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["model_call_rejected"],
    ),
    "blocked-secret": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
        ["secret_rejected"],
    ),
    "blocked-model-credential": (
        "blocked",
        "block_controlled_follow_up_feedback_rehearsal",
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
    receipt = rehearsal.validate_controlled_follow_up_rehearsal(
        artifacts["patch-proposal-controlled-follow-up-feedback-rehearsal-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-controlled-follow-up-feedback-rehearsal:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "rehearsal_source": receipt["rehearsal_actor"]["source"],
        "rehearsal_purpose": receipt["rehearsal_summary"]["purpose"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-controlled-follow-up-feedback-rehearsal-") as tmp:
        output_dir = Path(tmp) / "rehearsal"
        proc = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "scripts"
                    / "patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal.py"
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-controlled-follow-up-feedback-rehearsal-cli")
        if stdout.get("case_ids") != list(rehearsal.CASE_IDS):
            raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Rehearsal CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch Proposal Controlled Follow-up Feedback Rehearsal CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal Controlled Follow-up Feedback Rehearsal CLI output drifted: {case_id}/{filename}"
                    )


def negative_fixtures(pass_rehearsal: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_rehearsal)
        mutator(payload)
        try:
            rehearsal.validate_controlled_follow_up_rehearsal(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_follow_up_preview_injected",
        lambda payload: payload.__setitem__("raw_follow_up_preview", "private follow-up body"),
    )
    expect_rejected(
        "customer_visible_draft_injected",
        lambda payload: payload.__setitem__("customer_visible_follow_up_draft", "customer-visible draft"),
    )
    expect_rejected(
        "rehearsal_package_type_escalated",
        lambda payload: payload["rehearsal_summary"].__setitem__("package_type", "customer_visible_follow_up"),
    )
    expect_rejected(
        "automatic_customer_send_performed",
        lambda payload: payload["effect_boundary"].__setitem__("automatic_customer_send_performed", True),
    )
    expect_rejected(
        "production_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("production_mutation_performed", True),
    )
    expect_rejected(
        "model_call_performed",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected(
        "passive_rehearsal_only",
        lambda payload: payload["rehearsal_actor"].__setitem__("passive_attention_only", True),
    )
    expect_rejected(
        "missing_dual_loop_ref_on_ready",
        lambda payload: payload["checks"].__setitem__("dual_loop_refs_present", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = rehearsal.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in rehearsal.CASE_IDS]
    report = rehearsal.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Controlled Follow-up Feedback Rehearsal report case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, rehearsal.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, rehearsal.REHEARSAL_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-operator-signal"]["patch-proposal-controlled-follow-up-feedback-rehearsal-receipt.json"]
    )
    rehearsal._validate_privacy(report, label=rehearsal.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            rehearsal.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        expected_names = set(artifacts)
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing patch proposal controlled follow-up rehearsal fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal controlled follow-up rehearsal fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal.py --write"
                )
        extra = sorted(path.name for path in case_dir.glob("*.json") if path.name not in expected_names)
        if extra:
            raise SystemExit(f"Unexpected patch proposal controlled follow-up rehearsal fixture(s): {case_dir}: {extra}")


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal",
        "",
        "Metadata-only proof that controlled follow-up envelope refs can be rehearsed locally before any customer-visible action.",
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
        lines.append(
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / "
            f"source: `{row['rehearsal_source']}` / reasons: {reasons}"
        )
    lines.append("")
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Controlled Follow-up Feedback Rehearsal</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = rehearsal.build_all_case_artifacts()
    report = build_report()
    report_text = rehearsal.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal controlled follow-up rehearsal fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Rehearsal report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Rehearsal markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Controlled Follow-up Feedback Rehearsal HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal.py --write"
            )
        print("ok    Patch Proposal Controlled Follow-up Feedback Rehearsal report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
