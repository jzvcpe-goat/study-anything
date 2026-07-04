#!/usr/bin/env python3
"""Verify Patch Proposal External Operator Completion artifacts."""

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
import patch_proposal_external_operator_completion as completion  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-external-operator-completion"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-external-operator-completion.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-external-operator-completion.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-external-operator-completion.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-external-operator-completion-v1.schema.json"


EXPECTED = {
    "pass": {
        "status": "accepted",
        "decision": "accept_metadata_only_external_operator_completion",
        "blocked_reasons": [],
        "completion_purpose": "record_external_operator_completion_without_raw_payloads",
    },
    "blocked-work-order-blocked": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["work_order_not_ready"],
        "completion_purpose": None,
    },
    "blocked-missing-completion-purpose": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["completion_purpose_missing"],
        "completion_purpose": None,
    },
    "blocked-missing-reconstruction": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["operator_reconstruction_missing"],
        "completion_purpose": None,
    },
    "blocked-raw-patch-return": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["raw_patch_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-raw-diff-return": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["raw_diff_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-repository-file-body-return": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["repository_file_body_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-pr-comment-return": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["pr_comment_payload_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-customer-visible-payload": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["customer_visible_payload_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-external-publication-payload": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["external_publication_payload_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-production-payload": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["production_payload_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-secret-return": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["secret_return_rejected"],
        "completion_purpose": None,
    },
    "blocked-model-credential-return": {
        "status": "blocked",
        "decision": "block_external_operator_completion",
        "blocked_reasons": ["model_credential_return_rejected"],
        "completion_purpose": None,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != completion.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal external operator completion schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != completion.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal external operator completion schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": completion.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    receipt = completion.validate_completion_receipt(
        artifacts["patch-proposal-external-operator-completion-receipt.json"]
    )
    expected = EXPECTED[case_id]
    if receipt["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if receipt["completion_summary"]["purpose"] != expected["completion_purpose"]:
        raise RuntimeError(f"{case_id} completion purpose drifted")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-external-operator-completion:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "completion_purpose": receipt["completion_summary"]["purpose"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-completion-") as tmp:
        output_dir = Path(tmp) / "completion"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_external_operator_completion.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-external-operator-completion-cli")
        if stdout.get("case_ids") != list(completion.CASE_IDS):
            raise RuntimeError("Patch proposal external operator completion CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch proposal external operator completion CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(
                        f"Patch proposal external operator completion CLI output drifted: {case_id}/{filename}"
                    )


def negative_fixtures(pass_receipt: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_receipt)
        mutator(payload)
        try:
            completion.validate_completion_receipt(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_completion_body_injected",
        lambda payload: payload.__setitem__("raw_completion_body", "patch applied and comment body follows"),
    )
    expect_rejected(
        "completion_package_type_escalated",
        lambda payload: payload["completion_summary"].__setitem__("package_type", "raw_patch_completion"),
    )
    expect_rejected(
        "repository_mutation_by_study_anything",
        lambda payload: payload["effect_boundary"].__setitem__("study_anything_repository_mutation_performed", True),
    )
    expect_rejected(
        "raw_patch_flag_returned",
        lambda payload: payload["checks"].__setitem__("raw_patch_returned", True),
    )
    expect_rejected(
        "model_credentials_returned",
        lambda payload: payload["checks"].__setitem__("model_credentials_returned", True),
    )
    expect_rejected(
        "missing_work_order_ready_on_accepted",
        lambda payload: payload["checks"].__setitem__("work_order_ready", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = completion.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in completion.CASE_IDS]
    report = completion.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch proposal external operator completion report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_fixtures"] = negative_fixtures(
        cases["pass"]["patch-proposal-external-operator-completion-receipt.json"]
    )
    completion._validate_privacy(report, label=completion.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            completion.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing patch proposal external operator completion fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal external operator completion fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_external_operator_completion.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal External Operator Completion",
        "",
        "Metadata-only proof that a host-operator completion can re-enter the system only as bounded evidence.",
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
        "<title>Patch Proposal External Operator Completion</title>\n"
        "<body><pre>"
        + escaped
        + "</pre></body></html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    cases = completion.build_all_case_artifacts()
    report = build_report()
    report_text = completion.dump_json(report)
    md = markdown_report(report)
    html = html_report(md)

    if args.write:
        write_fixtures(cases)
        REPORT.write_text(report_text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(md, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")
        print("wrote patch proposal external operator completion fixtures and reports")
        return 0

    if args.check:
        check_fixtures(cases)
        if REPORT.read_text(encoding="utf-8") != report_text:
            raise SystemExit(
                "Patch proposal external operator completion report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_external_operator_completion.py --write"
            )
        if MARKDOWN_REPORT.read_text(encoding="utf-8") != md:
            raise SystemExit(
                "Patch proposal external operator completion markdown report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_external_operator_completion.py --write"
            )
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Patch proposal external operator completion HTML report is out of date. "
                "Run: python3 scripts/verify_patch_proposal_external_operator_completion.py --write"
            )
        print(completion.dump_json(report))
        return 0

    print(report_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
