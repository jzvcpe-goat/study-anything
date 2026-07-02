#!/usr/bin/env python3
"""Verify the Cognitive Black Box delivery scenario harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_delivery_harness, cbb_protocol, dual_loop  # noqa: E402


DEFAULT_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-cbb-delivery-scenario-harness.json"
)
FIXTURE_ROOT = ROOT / "fixtures" / "cbb-delivery-harness"
SCHEMA_FILES = [
    (
        ROOT / "platform" / "schemas" / "cbb" / "cbb-delivery-scenario-v1.schema.json",
        cbb_delivery_harness.CBB_DELIVERY_SCENARIO_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "cbb-external-feedback-intake-v1.schema.json",
        cbb_delivery_harness.CBB_EXTERNAL_FEEDBACK_INTAKE_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "cbb-tri-loop-run-v1.schema.json",
        cbb_delivery_harness.CBB_TRI_LOOP_RUN_SCHEMA_VERSION,
    ),
]

EXPECTED_REASONS = {
    "pass": [],
    "blocked-missing-developer-reconstruction": ["developer_reconstruction_missing"],
    "blocked-risk-over-budget": ["sandbox_risk_outside_budget"],
    "blocked-external-scope-expansion": ["external_scope_expansion"],
    "blocked-stale-receipt-chain": ["stale_receipt_chain"],
    "blocked-ai-review-only": ["ai_review_only_evidence_rejected"],
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _schema_report() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path, schema_version in SCHEMA_FILES:
        if not path.is_file():
            raise RuntimeError(f"CBB delivery harness schema missing: {path}")
        payload = _load_json(path)
        if payload.get("$id") != schema_version:
            raise RuntimeError(f"CBB delivery harness schema id drifted for {path}")
        if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
            raise RuntimeError(f"CBB delivery harness schema_version const drifted for {path}")
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "schema_version": schema_version,
                "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8")),
            }
        )
    return rows


def _expected_cases() -> dict[str, dict[str, dict[str, Any]]]:
    return cbb_delivery_harness.build_all_case_artifacts()


def _validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    scenario = cbb_delivery_harness.validate_delivery_scenario(
        artifacts["delivery-scenario.json"]
    )
    external = cbb_delivery_harness.validate_external_feedback_intake(
        artifacts["external-feedback-intake.json"]
    )
    tri_loop = cbb_delivery_harness.validate_tri_loop_run(artifacts["tri-loop-run.json"])
    for filename, payload in artifacts.items():
        dual_loop.assert_metadata_only(payload, label=f"cbb-delivery:{case_id}:{filename}")
    if tri_loop["case_id"] != case_id:
        raise RuntimeError(f"{case_id} tri-loop case id drifted")
    if tri_loop["scenario_id"] != scenario["scenario_id"]:
        raise RuntimeError(f"{case_id} tri-loop scenario id mismatch")
    if case_id == "pass":
        if tri_loop["status"] != "allowed":
            raise RuntimeError("pass case must be allowed")
        if tri_loop["decision"] != "promote_next_sandbox_level":
            raise RuntimeError("pass case must promote next sandbox level")
    else:
        if tri_loop["status"] != "blocked":
            raise RuntimeError(f"{case_id} must be blocked")
        if tri_loop["decision"] != "block_delivery_scenario":
            raise RuntimeError(f"{case_id} must block delivery scenario")
    for reason in EXPECTED_REASONS[case_id]:
        if reason not in tri_loop["reasons"]:
            raise RuntimeError(f"{case_id} missing expected reason: {reason}")
    if case_id == "blocked-external-scope-expansion":
        requested = external["classification"]["requested_scope"]
        if requested != "production_customer_handoff":
            raise RuntimeError("external scope expansion fixture must request production handoff")
    if case_id == "blocked-risk-over-budget":
        if scenario["risk_budget"]["within_budget"] is not False:
            raise RuntimeError("risk-over-budget fixture must exceed risk budget")
    if case_id == "blocked-missing-developer-reconstruction":
        developer = scenario["loops"]["developer_feedback_loop"]
        if developer["developer_reconstruction_present"] is not False:
            raise RuntimeError("missing-developer fixture must remove reconstruction")
    if case_id == "blocked-ai-review-only":
        agentic = scenario["loops"]["agentic_coding_loop"]
        if agentic["ai_review_only"] is not True:
            raise RuntimeError("AI-review-only fixture must mark agentic evidence unsafe")
    return {
        "case_id": case_id,
        "status": tri_loop["status"],
        "decision": tri_loop["decision"],
        "reasons": tri_loop["reasons"],
        "loop_statuses": tri_loop["loop_statuses"],
        "artifact_count": len(artifacts),
    }


def _verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-cbb-delivery-") as tmp:
        output_dir = Path(tmp) / "delivery-harness"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "cbb_delivery_harness.py"),
                "run",
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
        dual_loop.assert_metadata_only(stdout, label="cbb-delivery-harness-cli-run")
        if stdout.get("case_ids") != list(cbb_delivery_harness.CASE_IDS):
            raise RuntimeError("CBB delivery harness CLI case order drifted")
        for case_id, artifacts in cases.items():
            for filename, expected in artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"CBB delivery harness CLI missing {case_id}/{filename}")
                if _load_json(path) != expected:
                    raise RuntimeError(f"CBB delivery harness CLI output drifted for {case_id}/{filename}")

        pass_dir = output_dir / "pass"
        build_output = Path(tmp) / "built-tri-loop-run.json"
        build_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "cbb_delivery_harness.py"),
                "build",
                "--delivery-scenario",
                str(pass_dir / "delivery-scenario.json"),
                "--external-feedback",
                str(pass_dir / "external-feedback-intake.json"),
                "--receipt-chain",
                str(pass_dir / "receipt-chain.json"),
                "--self-intake",
                str(pass_dir / "self-intake-receipt.json"),
                "--output",
                str(build_output),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        stdout_build = json.loads(build_proc.stdout)
        dual_loop.assert_metadata_only(stdout_build, label="cbb-delivery-harness-cli-build")
        if _load_json(build_output) != cases["pass"]["tri-loop-run.json"]:
            raise RuntimeError("CBB delivery harness build CLI output drifted")


def build_report() -> dict[str, Any]:
    cases = _expected_cases()
    _verify_cli(cases)
    case_reports = [_validate_case(case_id, cases[case_id]) for case_id in cbb_delivery_harness.CASE_IDS]
    report = cbb_delivery_harness.build_harness_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("CBB delivery harness report case summary drifted")
    report["schema_files"] = _schema_report()
    dual_loop.assert_metadata_only(report, label="cbb-delivery-harness-report")
    return report


def _write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        cbb_delivery_harness.write_artifact_set(FIXTURE_ROOT / case_id, artifacts)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            path = FIXTURE_ROOT / case_id / filename
            if not path.is_file():
                raise SystemExit(f"Missing CBB delivery harness fixture: {path}")
            if _load_json(path) != payload:
                raise SystemExit(
                    f"CBB delivery harness fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_cbb_delivery_harness.py --write"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    cases = _expected_cases()
    report = build_report()
    serialized = cbb_protocol.dump_json(report)
    output = Path(args.output)

    if args.write:
        _write_fixtures(cases)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")

    if args.check:
        check_fixtures(cases)
        if not output.is_file():
            raise SystemExit(f"CBB delivery harness report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "CBB delivery harness report is out of date. "
                "Run: python3 scripts/verify_cbb_delivery_harness.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
