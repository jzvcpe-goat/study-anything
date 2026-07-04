#!/usr/bin/env python3
"""Verify Patch Proposal Acceptance Drill artifacts."""

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
import patch_proposal_acceptance_drill as drill  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-acceptance-drill"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-acceptance-drill.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-acceptance-drill.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-acceptance-drill.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-acceptance-drill-v1.schema.json"


EXPECTED = {
    "pass": {
        "status": "allowed",
        "decision": "allow_external_operator_continuation",
        "blocked_reasons": [],
        "next_allowed_action": "prepare_external_operator_work_order",
    },
    "blocked-bridge-blocked": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["bridge_not_ready"],
        "next_allowed_action": None,
    },
    "blocked-missing-operator-decision": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["operator_decision_missing", "operator_active_reconstruction_missing"],
        "next_allowed_action": None,
    },
    "blocked-raw-patch-evidence-request": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["raw_patch_or_diff_evidence_request_rejected"],
        "next_allowed_action": None,
    },
    "blocked-apply-patch-request": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["apply_patch_request_rejected"],
        "next_allowed_action": None,
    },
    "blocked-open-pr-request": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["open_pr_request_rejected"],
        "next_allowed_action": None,
    },
    "blocked-customer-visible-action": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["customer_visible_action_rejected"],
        "next_allowed_action": None,
    },
    "blocked-external-publication": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["external_publication_rejected"],
        "next_allowed_action": None,
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_external_operator_continuation",
        "blocked_reasons": ["production_mutation_rejected"],
        "next_allowed_action": None,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != drill.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal acceptance drill schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != drill.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal acceptance drill schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": drill.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    receipt = drill.validate_acceptance_receipt(artifacts["patch-proposal-acceptance-drill-receipt.json"])
    expected = EXPECTED[case_id]
    if receipt["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if receipt["acceptance_boundary"]["next_allowed_action"] != expected["next_allowed_action"]:
        raise RuntimeError(f"{case_id} next action drifted")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-acceptance-drill:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "next_allowed_action": receipt["acceptance_boundary"]["next_allowed_action"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-acceptance-") as tmp:
        output_dir = Path(tmp) / "acceptance"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_acceptance_drill.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-acceptance-drill-cli")
        if stdout.get("case_ids") != list(drill.CASE_IDS):
            raise RuntimeError("Patch proposal acceptance drill CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch proposal acceptance drill CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Patch proposal acceptance drill CLI output drifted: {case_id}/{filename}")


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            drill.validate_acceptance_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected("raw_patch_body_injected", lambda payload: payload.__setitem__("raw_patch_body", "diff --git"))
    expect_rejected(
        "acceptance_mode_escalated",
        lambda payload: payload["acceptance_boundary"].__setitem__("mode", "apply_patch"),
    )
    expect_rejected(
        "repository_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("repository_mutation_performed", True),
    )
    expect_rejected(
        "automatic_pr_commenting_performed",
        lambda payload: payload["effect_boundary"].__setitem__("automatic_pr_commenting_performed", True),
    )
    expect_rejected(
        "external_publication_performed",
        lambda payload: payload["effect_boundary"].__setitem__("external_publication_performed", True),
    )
    expect_rejected(
        "missing_operator_decision_on_allowed",
        lambda payload: payload["checks"].__setitem__("operator_decision_present", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = drill.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in drill.CASE_IDS]
    report = drill.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch proposal acceptance drill report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_fixtures"] = negative_fixtures(cases["pass"]["patch-proposal-acceptance-drill-receipt.json"])
    drill._validate_privacy(report, label=drill.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            drill.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing patch proposal acceptance drill fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal acceptance drill fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_acceptance_drill.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Acceptance Drill",
        "",
        "Metadata-only proof that an external operator can derive allow/block continuation decisions from the Patch Proposal Operator Handoff Bridge package alone.",
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
        "<title>Patch Proposal Acceptance Drill</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = drill.build_all_case_artifacts()
    report = build_report()
    report_text = drill.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal acceptance drill fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch proposal acceptance drill report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_acceptance_drill.py --write"
            )
        if MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch proposal acceptance drill markdown report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_acceptance_drill.py --write"
            )
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch proposal acceptance drill HTML report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_acceptance_drill.py --write"
            )
        print(drill.dump_json(report))
        return 0

    print(report_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
