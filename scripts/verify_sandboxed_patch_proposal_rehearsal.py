#!/usr/bin/env python3
"""Verify Sandboxed Patch Proposal Rehearsal artifacts."""

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
import sandboxed_patch_proposal_rehearsal as rehearsal  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "sandboxed-patch-proposal-rehearsal"
REPORT = ROOT / "platform" / "generated" / "study-anything-sandboxed-patch-proposal-rehearsal.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-sandboxed-patch-proposal-rehearsal.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-sandboxed-patch-proposal-rehearsal.html"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "sandboxed-patch-proposal-rehearsal-v1.schema.json"

EXPECTED = {
    "pass": {
        "status": "allowed",
        "decision": "prepare_sandbox_local_patch_proposal",
        "blocked_reasons": [],
        "proposal_scope": "sandbox_local_refs_only",
    },
    "blocked-missing-spec-eval-allowance": {
        "status": "blocked",
        "decision": "block_patch_proposal",
        "blocked_reasons": [
            "spec_eval_execution_not_allowed",
            "sandbox_start_not_authorized",
            "human_reconstruction_missing",
            "dual_loop_gate_not_allowed",
        ],
        "proposal_scope": None,
    },
    "blocked-missing-rollback-plan": {
        "status": "blocked",
        "decision": "block_patch_proposal",
        "blocked_reasons": ["rollback_plan_missing"],
        "proposal_scope": None,
    },
    "blocked-missing-test-plan": {
        "status": "blocked",
        "decision": "block_patch_proposal",
        "blocked_reasons": ["test_plan_missing"],
        "proposal_scope": None,
    },
    "blocked-repository-mutation": {
        "status": "blocked",
        "decision": "block_patch_proposal",
        "blocked_reasons": ["repository_mutation_rejected"],
        "proposal_scope": None,
    },
    "blocked-customer-visible-action": {
        "status": "blocked",
        "decision": "block_patch_proposal",
        "blocked_reasons": ["customer_visible_action_rejected"],
        "proposal_scope": None,
    },
    "blocked-external-publication": {
        "status": "blocked",
        "decision": "block_patch_proposal",
        "blocked_reasons": ["external_publication_rejected"],
        "proposal_scope": None,
    },
    "blocked-production-mutation": {
        "status": "blocked",
        "decision": "block_patch_proposal",
        "blocked_reasons": ["production_mutation_rejected"],
        "proposal_scope": None,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def schema_report() -> dict[str, str]:
    payload = load_json(SCHEMA_FILE)
    if payload.get("$id") != rehearsal.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Sandboxed patch proposal schema id drifted")
    if payload.get("properties", {}).get("schema_version", {}).get("const") != rehearsal.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Sandboxed patch proposal schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": rehearsal.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    envelope = rehearsal.validate_patch_proposal_envelope(artifacts["sandboxed-patch-proposal-envelope.json"])
    expected = EXPECTED[case_id]
    if envelope["status"] != expected["status"]:
        raise RuntimeError(f"{case_id} status drifted")
    if envelope["decision"] != expected["decision"]:
        raise RuntimeError(f"{case_id} decision drifted")
    for reason in expected["blocked_reasons"]:
        if reason not in envelope["blocked_reasons"]:
            raise RuntimeError(f"{case_id} missing blocked reason: {reason}")
    if envelope["patch_boundary"]["proposal_scope"] != expected["proposal_scope"]:
        raise RuntimeError(f"{case_id} proposal scope drifted")
    dual_loop.assert_metadata_only(envelope, label=f"sandboxed-patch-proposal:{case_id}")
    return {
        "case_id": case_id,
        "status": envelope["status"],
        "decision": envelope["decision"],
        "blocked_reasons": envelope["blocked_reasons"],
        "proposal_scope": envelope["patch_boundary"]["proposal_scope"],
    }


def verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-sandboxed-patch-") as tmp:
        output_dir = Path(tmp) / "rehearsal"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sandboxed_patch_proposal_rehearsal.py"),
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
        dual_loop.assert_metadata_only(stdout, label="sandboxed-patch-proposal-cli")
        if stdout.get("case_ids") != list(rehearsal.CASE_IDS):
            raise RuntimeError("Sandboxed patch proposal CLI case order drifted")
        for case_id, expected_artifacts in cases.items():
            for filename, expected in expected_artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Sandboxed patch proposal CLI missing {case_id}/{filename}")
                if load_json(path) != expected:
                    raise RuntimeError(f"Sandboxed patch proposal CLI output drifted: {case_id}/{filename}")


def negative_fixtures(pass_envelope: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(name: str, mutator: Any) -> None:
        payload = copy.deepcopy(pass_envelope)
        mutator(payload)
        try:
            rehearsal.validate_patch_proposal_envelope(payload)
        except Exception as exc:  # noqa: BLE001
            failures[name] = str(exc)
            return
        raise RuntimeError(f"Negative fixture was not rejected: {name}")

    expect_rejected(
        "raw_diff_body_injected",
        lambda payload: payload.__setitem__("raw_diff", "diff --git a/private b/private"),
    )
    expect_rejected(
        "patch_body_included",
        lambda payload: payload["patch_boundary"].__setitem__("patch_body_included", True),
    )
    expect_rejected(
        "repository_mutation_performed",
        lambda payload: payload["patch_boundary"].__setitem__("repository_mutation_performed", True),
    )
    expect_rejected(
        "customer_visible_action_performed",
        lambda payload: payload["patch_boundary"].__setitem__("customer_visible_action_performed", True),
    )
    expect_rejected(
        "missing_rollback_on_allowed",
        lambda payload: payload["checks"].__setitem__("rollback_plan_present", False),
    )
    return failures


def build_report() -> dict[str, Any]:
    cases = rehearsal.build_all_case_artifacts()
    verify_cli(cases)
    case_reports = [validate_case(case_id, cases[case_id]) for case_id in rehearsal.CASE_IDS]
    report = rehearsal.build_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Sandboxed patch proposal report case summary drifted")
    report["schema_files"] = [schema_report()]
    report["negative_fixtures"] = negative_fixtures(cases["pass"]["sandboxed-patch-proposal-envelope.json"])
    rehearsal._validate_privacy(report, label=rehearsal.REPORT_SCHEMA_VERSION)  # noqa: SLF001
    return report


def write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            rehearsal.write_json(FIXTURE_ROOT / case_id / filename, payload)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        case_dir = FIXTURE_ROOT / case_id
        for filename, payload in artifacts.items():
            path = case_dir / filename
            if not path.is_file():
                raise SystemExit(f"Missing sandboxed patch proposal fixture: {path}")
            if load_json(path) != payload:
                raise SystemExit(
                    f"Sandboxed patch proposal fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_sandboxed_patch_proposal_rehearsal.py --write"
                )


def markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Sandboxed Patch Proposal Rehearsal",
        "",
        "Metadata-only proof that an allowed Spec/Eval execution rehearsal can create only a sandbox-local patch proposal envelope before any repository mutation.",
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

    cases = rehearsal.build_all_case_artifacts()
    report = build_report()
    serialized = rehearsal.dump_json(report)

    if args.write:
        write_fixtures(cases)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown_report(report), encoding="utf-8")
        dual_loop.write_html_report(HTML_REPORT, "Sandboxed Patch Proposal Rehearsal", report)

    if args.check:
        check_fixtures(cases)
        for path, expected in (
            (REPORT, serialized),
            (MARKDOWN_REPORT, markdown_report(report)),
        ):
            if not path.is_file():
                raise SystemExit(f"Sandboxed patch proposal report missing: {path}")
            if path.read_text(encoding="utf-8") != expected:
                raise SystemExit(
                    "Sandboxed patch proposal report is out of date. "
                    "Run: python3 scripts/verify_sandboxed_patch_proposal_rehearsal.py --write"
                )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Sandboxed patch proposal HTML report missing: {HTML_REPORT}")

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
