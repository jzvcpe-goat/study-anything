#!/usr/bin/env python3
"""Verify Patch Proposal Operator Handoff Bridge artifacts."""

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
import patch_proposal_operator_handoff_bridge as bridge  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "patch-proposal-operator-handoff-bridge"
REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-operator-handoff-bridge.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-operator-handoff-bridge.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-patch-proposal-operator-handoff-bridge.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "patch-proposal-operator-handoff-bridge-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "ready",
        "decision": "prepare_operator_handoff_bridge",
        "blocked_reasons": [],
        "next_allowed_action": "prepare_operator_handoff_in_host_agent",
    },
    "blocked-sandboxed-proposal-blocked": {
        "status": "blocked",
        "decision": "block_operator_handoff_bridge",
        "blocked_reasons": [
            "sandboxed_patch_proposal_not_allowed",
            "sandbox_local_scope_missing",
            "test_plan_ref_missing",
        ],
        "next_allowed_action": None,
    },
    "blocked-missing-operator-confirmation": {
        "status": "blocked",
        "decision": "block_operator_handoff_bridge",
        "blocked_reasons": ["operator_active_reconstruction_missing"],
        "next_allowed_action": None,
    },
    "blocked-raw-patch-request": {
        "status": "blocked",
        "decision": "block_operator_handoff_bridge",
        "blocked_reasons": ["raw_patch_or_diff_request_rejected"],
        "next_allowed_action": None,
    },
    "blocked-repository-mutation": {
        "status": "blocked",
        "decision": "block_operator_handoff_bridge",
        "blocked_reasons": ["repository_mutation_rejected"],
        "next_allowed_action": None,
    },
    "blocked-customer-visible-action": {
        "status": "blocked",
        "decision": "block_operator_handoff_bridge",
        "blocked_reasons": ["customer_visible_action_rejected"],
        "next_allowed_action": None,
    },
    "blocked-external-publication": {
        "status": "blocked",
        "decision": "block_operator_handoff_bridge",
        "blocked_reasons": ["external_publication_rejected"],
        "next_allowed_action": None,
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_operator_handoff_bridge",
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
    if payload.get("$id") != bridge.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal operator handoff bridge schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != bridge.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Patch proposal operator handoff bridge schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": bridge.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    receipt = bridge.validate_bridge_receipt(artifacts["patch-proposal-operator-handoff-bridge-receipt.json"])
    expected = EXPECTED[case_id]
    if receipt["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if receipt["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in receipt["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if receipt["handoff_bridge"]["next_allowed_action"] != expected["next_allowed_action"]:
        raise RuntimeError(f"{case_id} next action drifted")
    dual_loop.assert_metadata_only(receipt, label=f"patch-proposal-operator-handoff-bridge:{case_id}")
    return {
        "case_id": case_id,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "blocked_reasons": receipt["blocked_reasons"],
        "next_allowed_action": receipt["handoff_bridge"]["next_allowed_action"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-patch-operator-handoff-") as tmp:
        output_dir = Path(tmp) / "bridge"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "patch_proposal_operator_handoff_bridge.py"),
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
        dual_loop.assert_metadata_only(stdout, label="patch-proposal-operator-handoff-bridge-cli")
        if stdout.get("case_ids") != list(bridge.CASE_IDS):
            raise RuntimeError("Patch proposal operator handoff bridge CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Patch proposal operator handoff bridge CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Patch proposal operator handoff bridge CLI output drifted: {case_id}/{filename}")


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
        "raw_patch_body_injected",
        lambda payload: payload.__setitem__("raw_patch_body", "diff --git a/private b/private"),
    )
    expect_rejected(
        "bridge_mode_escalated",
        lambda payload: payload["handoff_bridge"].__setitem__("mode", "apply_patch"),
    )
    expect_rejected(
        "repository_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("repository_mutation_performed", True),
    )
    expect_rejected(
        "customer_visible_action_performed",
        lambda payload: payload["effect_boundary"].__setitem__("customer_visible_action_performed", True),
    )
    expect_rejected(
        "production_mutation_performed",
        lambda payload: payload["effect_boundary"].__setitem__("production_mutation_performed", True),
    )
    expect_rejected(
        "missing_operator_confirmation_on_ready",
        lambda payload: payload["checks"].__setitem__("operator_active_confirmations_present", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = bridge.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in bridge.CASE_IDS]
    report = bridge.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Patch proposal operator handoff bridge report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_fixtures"] = negative_fixtures(cases["pass"]["patch-proposal-operator-handoff-bridge-receipt.json"])
    bridge._validate_privacy(report, label=bridge.REPORT_SCHEMA_VERSION)  # noqa: SLF001
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
                raise SystemExit(f"Missing patch proposal operator handoff bridge fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Patch proposal operator handoff bridge fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_patch_proposal_operator_handoff_bridge.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Patch Proposal Operator Handoff Bridge",
        "",
        "Metadata-only proof that a sandbox-local patch proposal envelope can become only an operator handoff bridge, not a repository mutation or customer-visible action.",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = bridge.build_all_case_artifacts()
    report = build_report()
    serialized = bridge.dump_json(report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown_report(report), encoding="utf-8")
        dual_loop.write_html_report(HTML_REPORT, "Patch Proposal Operator Handoff Bridge", report)

    if args.check:
        check_fixtures(cases)
        for path, expected in (
            (REPORT, serialized),
            (MARKDOWN_REPORT, markdown_report(report)),
        ):
            if not path.is_file():
                raise SystemExit(f"Patch proposal operator handoff bridge report missing: {path}")
            if path.read_text(encoding="utf-8") != expected:
                raise SystemExit(
                    "Patch proposal operator handoff bridge report is out of date. "
                    "Run: python3 scripts/verify_patch_proposal_operator_handoff_bridge.py --write"
                )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Patch proposal operator handoff bridge HTML report missing: {HTML_REPORT}")

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
