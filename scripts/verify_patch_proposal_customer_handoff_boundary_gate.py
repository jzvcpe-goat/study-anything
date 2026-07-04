#!/usr/bin/env python3
"""Verify Patch Proposal Customer-Handoff Boundary Gate artifacts."""

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
import patch_proposal_customer_handoff_boundary_gate as gate  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-customer-handoff-boundary-gate"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-handoff-boundary-gate.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-handoff-boundary-gate.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-customer-handoff-boundary-gate.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-customer-handoff-boundary-gate-v1.schema.json"


EXPECTED = {
    "pass": ("ready", "allow_customer_handoff_preparation", []),
    "blocked-completion-blocked": ("blocked", "block_customer_handoff_boundary", ["completion_not_accepted"]),
    "blocked-missing-delivery-class-scenario": (
        "blocked",
        "block_customer_handoff_boundary",
        ["delivery_class_scenario_missing"],
    ),
    "blocked-missing-human-reconstruction": (
        "blocked",
        "block_customer_handoff_boundary",
        ["human_reconstruction_missing"],
    ),
    "blocked-missing-claim-boundary": ("blocked", "block_customer_handoff_boundary", ["claim_boundary_missing"]),
    "blocked-missing-privacy-boundary": ("blocked", "block_customer_handoff_boundary", ["privacy_boundary_missing"]),
    "blocked-missing-sandbox-receipt": ("blocked", "block_customer_handoff_boundary", ["sandbox_receipt_missing"]),
    "blocked-raw-customer-draft": ("blocked", "block_customer_handoff_boundary", ["raw_customer_draft_rejected"]),
    "blocked-raw-patch-return": ("blocked", "block_customer_handoff_boundary", ["raw_patch_return_rejected"]),
    "blocked-production-payload": ("blocked", "block_customer_handoff_boundary", ["production_payload_rejected"]),
    "blocked-auto-send": ("blocked", "block_customer_handoff_boundary", ["automatic_customer_send_rejected"]),
    "blocked-external-publication": ("blocked", "block_customer_handoff_boundary", ["external_publication_rejected"]),
    "blocked-secret-return": ("blocked", "block_customer_handoff_boundary", ["secret_return_rejected"]),
    "blocked-model-credential-return": ("blocked", "block_customer_handoff_boundary", ["model_credential_return_rejected"]),
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != gate.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal customer handoff boundary schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != gate.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal customer handoff boundary schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": gate.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    receipt = gate.validate_customer_handoff_receipt(
        artifacts["patch-proposal-customer-handoff-boundary-receipt.json"]
    )
    expected_status, expected_decision, expected_reasons = EXPECTED[case_id]
    if receipt["status"] != expected_status:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected_decision:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected_reasons:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-customer-handoff-boundary-gate:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "handoff_purpose": receipt["handoff_summary"]["purpose"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-customer-handoff-") as tmp:
        output_dir = Path(tmp) / "handoff"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_customer_handoff_boundary_gate.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-customer-handoff-boundary-gate-cli")
        if stdout.get("case_ids") != list(gate.CASE_IDS):
            raise RuntimeError("Patch proposal customer handoff boundary CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch proposal customer handoff boundary CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Patch proposal customer handoff boundary CLI output drifted: {case_id}/{filename}")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            gate.validate_customer_handoff_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_customer_draft_injected",
        lambda payload: payload.__setitem__("raw_customer_draft", "customer-facing text"),
    )
    expect_rejected(
        "handoff_package_type_escalated",
        lambda payload: payload["handoff_summary"].__setitem__("package_type", "customer_visible_message"),
    )
    expect_rejected(
        "automatic_send_performed",
        lambda payload: payload["effect_boundary"].__setitem__("automatic_customer_send_performed", True),
    )
    expect_rejected(
        "external_publication_performed",
        lambda payload: payload["effect_boundary"].__setitem__("external_publication_performed", True),
    )
    expect_rejected(
        "missing_human_reconstruction_on_ready",
        lambda payload: payload["checks"].__setitem__("human_reconstruction_present", False),
    )
    expect_rejected(
        "model_credentials_returned",
        lambda payload: payload["checks"].__setitem__("model_credentials_returned", True),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = gate.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in gate.CASE_IDS]
    report = gate.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch proposal customer handoff boundary report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_fixtures"] = negative_fixtures(cases["pass"]["patch-proposal-customer-handoff-boundary-receipt.json"])
    gate._validate_privacy(report, label=gate.REPORT_SCHEMA_VERSION)  # noqa: SLF001
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
                raise SystemExit(f"Missing patch proposal customer handoff boundary fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal customer handoff boundary fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Customer-Handoff Boundary Gate",
        "",
        "Metadata-only proof that customer-visible handoff remains blocked unless the boundary gate passes.",
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
        lines.append(f"- `{row['case_id']}`: `{row['status']}` / `{row['decision']}` / reasons: {reasons}")
    lines.append("")
    return "\n".join(lines)


def html_report(markdown: str) -> str:
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal Customer-Handoff Boundary Gate</title>\n"
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
        print("wrote patch proposal customer handoff boundary fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch proposal customer handoff boundary report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --write"
            )
        if MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch proposal customer handoff boundary markdown report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --write"
            )
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch proposal customer handoff boundary HTML report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --write"
            )
        print(gate.dump_json(report))
        return 0

    print(report_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
