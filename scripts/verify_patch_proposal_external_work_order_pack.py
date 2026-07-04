#!/usr/bin/env python3
"""Verify Patch Proposal External Work Order Pack artifacts."""

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
import patch_proposal_external_work_order_pack as pack  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-external-work-order-pack"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-external-work-order-pack.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-external-work-order-pack.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-external-work-order-pack.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-external-work-order-pack-v1.schema.json"


EXPECTED = {
    "pass": {
        "status": "ready",
        "decision": "emit_external_operator_work_order_pack",
        "blocked_reasons": [],
        "work_order_purpose": "continue_patch_proposal_outside_cbb_under_local_controls",
    },
    "blocked-acceptance-blocked": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["acceptance_not_allowed"],
        "work_order_purpose": None,
    },
    "blocked-missing-work-order-purpose": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["work_order_purpose_missing", "operator_reconstruction_missing"],
        "work_order_purpose": None,
    },
    "blocked-raw-patch-request": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["raw_patch_or_diff_request_rejected"],
        "work_order_purpose": None,
    },
    "blocked-apply-patch-request": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["apply_patch_request_rejected"],
        "work_order_purpose": None,
    },
    "blocked-open-pr-request": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["open_pr_request_rejected"],
        "work_order_purpose": None,
    },
    "blocked-pr-comment-request": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["pr_comment_request_rejected"],
        "work_order_purpose": None,
    },
    "blocked-customer-visible-action": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["customer_visible_action_rejected"],
        "work_order_purpose": None,
    },
    "blocked-external-publication": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["external_publication_rejected"],
        "work_order_purpose": None,
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_external_operator_work_order_pack",
        "blocked_reasons": ["production_mutation_rejected"],
        "work_order_purpose": None,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != pack.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal external work-order pack schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != pack.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal external work-order pack schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": pack.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    receipt = pack.validate_work_order_receipt(artifacts["patch-proposal-external-work-order-receipt.json"])
    expected = EXPECTED[case_id]
    if receipt["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if receipt["work_order"]["purpose"] != expected["work_order_purpose"]:
        raise RuntimeError(f"{case_id} work order purpose drifted")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-external-work-order-pack:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "work_order_purpose": receipt["work_order"]["purpose"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-work-order-") as tmp:
        output_dir = Path(tmp) / "work-order"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_external_work_order_pack.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-external-work-order-pack-cli")
        if stdout.get("case_ids") != list(pack.CASE_IDS):
            raise RuntimeError("Patch proposal external work-order pack CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch proposal external work-order pack CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Patch proposal external work-order pack CLI output drifted: {case_id}/{filename}")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            pack.validate_work_order_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected("raw_work_order_body_injected", lambda payload: payload.__setitem__("raw_work_order_body", "apply this patch"))
    expect_rejected(
        "work_order_package_type_escalated",
        lambda payload: payload["work_order"].__setitem__("package_type", "executable_patch_order"),
    )
    expect_rejected(
        "repository_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("repository_mutation_performed", True),
    )
    expect_rejected(
        "automatic_pr_opening_performed",
        lambda payload: payload["effect_boundary"].__setitem__("automatic_pr_opening_performed", True),
    )
    expect_rejected(
        "external_publication_performed",
        lambda payload: payload["effect_boundary"].__setitem__("external_publication_performed", True),
    )
    expect_rejected(
        "missing_acceptance_on_ready",
        lambda payload: payload["checks"].__setitem__("acceptance_allowed", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = pack.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in pack.CASE_IDS]
    report = pack.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch proposal external work-order pack report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_fixtures"] = negative_fixtures(cases["pass"]["patch-proposal-external-work-order-receipt.json"])
    pack._validate_privacy(report, label=pack.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            pack.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing patch proposal external work-order pack fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal external work-order pack fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_external_work_order_pack.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal External Work Order Pack",
        "",
        "Metadata-only proof that an allowed Patch Proposal Acceptance Drill can become a bounded external operator work-order package.",
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
    escaped = (
        markdown.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        "<title>Patch Proposal External Work Order Pack</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = pack.build_all_case_artifacts()
    report = build_report()
    report_text = pack.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal external work-order pack fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch proposal external work-order pack report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_external_work_order_pack.py --write"
            )
        if MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch proposal external work-order pack markdown report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_external_work_order_pack.py --write"
            )
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch proposal external work-order pack HTML report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_external_work_order_pack.py --write"
            )
        print(pack.dump_json(report))
        return 0

    print(report_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
