#!/usr/bin/env python3
"""Verify Patch Proposal Customer Feedback Delivery Trust Case Bridge artifacts."""

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
import patch_proposal_customer_feedback_delivery_trust_case_bridge as bridge  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-feedback-delivery-trust-case-bridge"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-delivery-trust-case-bridge.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-delivery-trust-case-bridge.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-feedback-delivery-trust-case-bridge.html"
REPORT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-feedback-delivery-trust-case-bridge-v1.schema.json"
RECEIPT_SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-delivery-trust-case-bridge-receipt-v1.schema.json"


EXPECTED = {
    "pass-customer-signal": ("delivery_trust_case_refs_ready", [], True),
    "pass-operator-signal": ("delivery_trust_case_refs_ready", [], True),
    "pass-host-platform-agent-signal": ("delivery_trust_case_refs_ready", [], True),
    "blocked-missing-candidate": ("blocked", ["candidate_missing"], False),
    "blocked-invalid-candidate": ("blocked", ["candidate_invalid"], False),
    "blocked-missing-product-loop-run": ("blocked", ["product_loop_run_missing"], False),
    "blocked-product-loop-hash-mismatch": (
        "blocked",
        ["product_loop_run_hash_mismatch", "product_loop_run_id_mismatch"],
        False,
    ),
    "blocked-missing-dual-loop-evidence": ("blocked", ["sandbox_receipt_missing"], False),
    "blocked-dual-loop-evidence-mismatch": ("blocked", ["dual_loop_evidence_ref_mismatch"], False),
    "blocked-dual-loop-gate-blocked": (
        "blocked",
        ["dual_loop_evidence_ref_mismatch", "dual_loop_gate_blocked", "sandbox_risk_outside_budget"],
        False,
    ),
    "blocked-ai-review-only": ("blocked", ["product_loop_run_invalid"], False),
    "blocked-customer-visible-send": ("blocked", ["customer_visible_send_rejected"], False),
    "blocked-source-mutation": ("blocked", ["source_mutation_rejected"], False),
    "blocked-production-mutation": ("blocked", ["production_mutation_rejected"], False),
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
    receipt = bridge.validate_bridge_receipt(artifacts["patch-proposal-delivery-trust-case-bridge-receipt.json"])
    expected_status, expected_reasons, expected_refs = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    refs_created = receipt["handoff_refs"] is not None
    if refs_created is not expected_refs:
        raise RuntimeError(f"{case_id} handoff ref creation drifted")
    if refs_created:
        refs = bridge.validate_handoff_refs(artifacts["patch-proposal-delivery-trust-case-handoff-refs.json"])
        if refs != receipt["handoff_refs"]:
            raise RuntimeError(f"{case_id} standalone handoff refs drifted")
        if refs["harness_summary"]["customer_visible_send_performed"] is not False:
            raise RuntimeError(f"{case_id} must not perform customer-visible sends")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-delivery-trust-case-bridge:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "handoff_refs_created": refs_created,
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-delivery-trust-case-bridge-") as tmp:
        output_dir = Path(tmp) / "bridge"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_delivery_trust_case_bridge.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-delivery-trust-case-bridge-cli")
        if stdout.get("case_ids") != list(bridge.CASE_IDS):
            raise RuntimeError("Patch Proposal Delivery Trust Case Bridge CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch Proposal Delivery Trust Case Bridge CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch Proposal Delivery Trust Case Bridge CLI output drifted: {case_id}/{filename}"
                    )
            refs_path = output_dir / case_id / "patch-proposal-delivery-trust-case-handoff-refs.json"
            if expected_artifacts["patch-proposal-delivery-trust-case-bridge-receipt.json"]["status"] == "blocked":
                if refs_path.exists():
                    raise RuntimeError(f"blocked case must not include handoff refs: {case_id}")

        custom_output_dir = Path(tmp) / "custom"
        custom_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_feedback_delivery_trust_case_bridge.py"),
                "--candidate",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-delivery-trust-intake-gate"
                    / "pass-customer-signal"
                    / "patch-proposal-delivery-trust-case-candidate.json"
                ),
                "--product-loop-run",
                str(
                    ROOT
                    / "fixtures"
                    / "patch-proposal-customer-feedback-product-loop-brief-intake-gate"
                    / "pass-customer-signal"
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
            raise RuntimeError("Patch Proposal Delivery Trust Case Bridge custom CLI output drifted")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            bridge.validate_bridge_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_customer_payload_injected",
        lambda payload: payload.__setitem__("raw_customer_payload", "private customer payload"),
    )
    expect_rejected(
        "customer_handoff_package_body_injected",
        lambda payload: payload["handoff_refs"].__setitem__(
            "customer_handoff_package",
            {"body": "private"},
        ),
    )
    expect_rejected(
        "delivery_trust_case_body_injected",
        lambda payload: payload["handoff_refs"].__setitem__("delivery_trust_case", {"body": "private"}),
    )
    expect_rejected(
        "customer_send_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__(
            "study_anything_customer_visible_send_performed",
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
        "model_call_effect_injected",
        lambda payload: payload["effect_boundary"].__setitem__("model_calls_performed", True),
    )
    expect_rejected(
        "customer_send_policy_injected",
        lambda payload: payload["harness_policy"].__setitem__("customer_visible_send_allowed", True),
    )
    expect_rejected(
        "ready_receipt_without_handoff_refs",
        lambda payload: payload.__setitem__("handoff_refs", None),
    )
    expect_rejected(
        "blocked_receipt_with_handoff_refs",
        lambda payload: (
            payload.__setitem__("status", "blocked"),
            payload.__setitem__("decision", "block_patch_proposal_delivery_trust_case_bridge"),
            payload.__setitem__("blocked_reasons", ["forced_block"]),
        ),
    )
    required = {
        "raw_customer_payload_injected",
        "customer_handoff_package_body_injected",
        "delivery_trust_case_body_injected",
        "customer_send_effect_injected",
        "source_mutation_effect_injected",
        "production_mutation_effect_injected",
        "model_call_effect_injected",
        "customer_send_policy_injected",
        "ready_receipt_without_handoff_refs",
        "blocked_receipt_with_handoff_refs",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Patch Proposal Delivery Trust Case Bridge negative checks missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    cases = bridge.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in bridge.CASE_IDS]
    report = bridge.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch Proposal Delivery Trust Case Bridge case summary drifted")
    report["schema_files"] = [
        schema_report(REPORT_SCHEMA_FILE, bridge.REPORT_SCHEMA_VERSION),
        schema_report(RECEIPT_SCHEMA_FILE, bridge.RECEIPT_SCHEMA_VERSION),
    ]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass-customer-signal"]["patch-proposal-delivery-trust-case-bridge-receipt.json"]
    )
    bridge._validate_privacy(report, label=bridge.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    bridge._validate_effect_boundary(report, label=bridge.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            bridge.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing Patch Proposal Delivery Trust Case Bridge fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch Proposal Delivery Trust Case Bridge fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_feedback_delivery_trust_case_bridge.py --write"
                )
        refs_path = case_dir / "patch-proposal-delivery-trust-case-handoff-refs.json"
        if (
            artifacts["patch-proposal-delivery-trust-case-bridge-receipt.json"]["status"] == "blocked"
            and refs_path.exists()
        ):
            raise SystemExit(f"Blocked Patch Proposal Delivery Trust Case Bridge case must not include refs: {case_id}")


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer Feedback Delivery Trust Case Bridge",
        "",
        "Metadata-only proof that Patch Proposal Delivery Trust case candidates can run the local deterministic Delivery Trust Case Harness and emit only handoff refs.",
        "",
        f"- status: `{report['status']}`",
        f"- ready ref sets: `{report['bridge_matrix']['ready_delivery_trust_case_ref_sets']}`",
        f"- blocked transitions: `{report['bridge_matrix']['blocked_bridge_transitions']}`",
        "- raw customer payloads: `blocked`",
        "- customer-visible sends: `blocked`",
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
            f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / refs: `{row['handoff_refs_created']}` / reasons: {reasons}"
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

    cases = bridge.build_all_case_artifacts()
    report = build_report()
    report_text = bridge.dump_json(report)
    md = markdown_report(report)
    html = dual_loop.render_html_report("Patch Proposal Delivery Trust Case Bridge", report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote Patch Proposal Delivery Trust Case Bridge fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch Proposal Delivery Trust Case Bridge report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_delivery_trust_case_bridge.py --write"
            )
        if not MARKDOWN_REPORT.is_file() or MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch Proposal Delivery Trust Case Bridge markdown is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_delivery_trust_case_bridge.py --write"
            )
        if not HTML_REPORT.is_file() or HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch Proposal Delivery Trust Case Bridge HTML is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_feedback_delivery_trust_case_bridge.py --write"
            )
        print("ok    Patch Proposal Delivery Trust Case Bridge report is up to date")
        return 0

    print(report_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
