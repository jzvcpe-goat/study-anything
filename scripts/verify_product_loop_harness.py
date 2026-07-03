#!/usr/bin/env python3
"""Verify the metadata-only Product Loop Harness."""

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

from study_anything.core import cbb_protocol, dual_loop, product_loop_harness  # noqa: E402


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-product-loop-harness.json"
FIXTURE_ROOT = ROOT / "fixtures" / "product-loop-harness"
SCHEMA_FILES = [
    (
        ROOT / "platform" / "schemas" / "cbb" / "product-loop-scenario-v1.schema.json",
        product_loop_harness.PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "product-loop-run-v1.schema.json",
        product_loop_harness.PRODUCT_LOOP_RUN_SCHEMA_VERSION,
    ),
]

EXPECTED_REASONS = {
    "pass": [],
    "blocked-missing-product-spec-evals": ["product_spec_evals_missing"],
    "blocked-missing-developer-vision": ["developer_vision_missing"],
    "blocked-external-scope-expansion": ["external_feedback_scope_expansion"],
    "blocked-ai-review-only": ["ai_review_only_evidence_rejected"],
    "blocked-loop-dominance": ["loop_dominance_detected"],
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
            raise RuntimeError(f"Product Loop Harness schema missing: {path}")
        payload = _load_json(path)
        if payload.get("$id") != schema_version:
            raise RuntimeError(f"Product Loop Harness schema id drifted for {path}")
        if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
            raise RuntimeError(f"Product Loop Harness schema_version const drifted for {path}")
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "schema_version": schema_version,
                "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8")),
            }
        )
    return rows


def _expected_cases() -> dict[str, dict[str, dict[str, Any]]]:
    return product_loop_harness.build_all_case_artifacts()


def _validate_case(case_id: str, artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    scenario = product_loop_harness.validate_product_loop_scenario(
        artifacts["product-loop-scenario.json"]
    )
    run = product_loop_harness.validate_product_loop_run(artifacts["product-loop-run.json"])
    for filename, payload in artifacts.items():
        dual_loop.assert_metadata_only(payload, label=f"product-loop:{case_id}:{filename}")
    if run["case_id"] != case_id:
        raise RuntimeError(f"{case_id} product-loop case id drifted")
    if run["scenario_id"] != scenario["scenario_id"]:
        raise RuntimeError(f"{case_id} product-loop scenario id mismatch")
    if case_id == "pass":
        if run["status"] != "allowed":
            raise RuntimeError("pass case must be allowed")
        if run["decision"] != "promote_to_delivery_trust_harness":
            raise RuntimeError("pass case must promote to delivery trust harness")
    else:
        if run["status"] != "blocked":
            raise RuntimeError(f"{case_id} must be blocked")
        if run["decision"] != "block_product_loop":
            raise RuntimeError(f"{case_id} must block product loop")
    for reason in EXPECTED_REASONS[case_id]:
        if reason not in run["reasons"]:
            raise RuntimeError(f"{case_id} missing expected reason: {reason}")
    loops = scenario["loops"]
    if loops["agentic_coding_loop"]["time_scale"] != "minutes":
        raise RuntimeError("agentic loop must remain minutes scale")
    if loops["developer_feedback_loop"]["time_scale"] != "hours":
        raise RuntimeError("developer loop must remain hours scale")
    if loops["external_feedback_loop"]["time_scale"] != "days":
        raise RuntimeError("external loop must remain days scale")
    if case_id == "blocked-external-scope-expansion":
        requested = loops["external_feedback_loop"]["requested_scope"]
        if requested != "production_customer_handoff":
            raise RuntimeError("external scope expansion fixture must request production handoff")
    if case_id == "blocked-missing-product-spec-evals":
        if loops["agentic_coding_loop"]["product_spec_evals_present"] is not False:
            raise RuntimeError("missing spec/evals fixture must remove product spec/evals")
    if case_id == "blocked-missing-developer-vision":
        if loops["developer_feedback_loop"]["developer_vision_present"] is not False:
            raise RuntimeError("missing developer vision fixture must remove developer vision")
    if case_id == "blocked-ai-review-only":
        if loops["agentic_coding_loop"]["ai_review_only"] is not True:
            raise RuntimeError("AI-review-only fixture must mark agentic evidence unsafe")
    if case_id == "blocked-loop-dominance":
        if scenario["loop_contract"]["neither_loop_may_dominate"] is not False:
            raise RuntimeError("loop dominance fixture must disable parity")
    return {
        "case_id": case_id,
        "status": run["status"],
        "decision": run["decision"],
        "reasons": run["reasons"],
        "loop_statuses": run["loop_statuses"],
        "artifact_count": len(artifacts),
    }


def _verify_cli(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-product-loop-") as tmp:
        output_dir = Path(tmp) / "product-loop-harness"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_loop_harness.py"),
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
        dual_loop.assert_metadata_only(stdout, label="product-loop-harness-cli-run")
        if stdout.get("case_ids") != list(product_loop_harness.CASE_IDS):
            raise RuntimeError("Product Loop Harness CLI case order drifted")
        for case_id, artifacts in cases.items():
            for filename, expected in artifacts.items():
                path = output_dir / case_id / filename
                if not path.is_file():
                    raise RuntimeError(f"Product Loop Harness CLI missing {case_id}/{filename}")
                if _load_json(path) != expected:
                    raise RuntimeError(f"Product Loop Harness CLI output drifted for {case_id}/{filename}")

        pass_dir = output_dir / "pass"
        build_output = Path(tmp) / "built-product-loop-run.json"
        build_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "product_loop_harness.py"),
                "build",
                "--scenario",
                str(pass_dir / "product-loop-scenario.json"),
                "--output",
                str(build_output),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        stdout_build = json.loads(build_proc.stdout)
        dual_loop.assert_metadata_only(stdout_build, label="product-loop-harness-cli-build")
        if _load_json(build_output) != cases["pass"]["product-loop-run.json"]:
            raise RuntimeError("Product Loop Harness build CLI output drifted")


def build_report() -> dict[str, Any]:
    cases = _expected_cases()
    _verify_cli(cases)
    case_reports = [
        _validate_case(case_id, cases[case_id])
        for case_id in product_loop_harness.CASE_IDS
    ]
    report = product_loop_harness.build_harness_report(cases)
    if report["case_reports"] != case_reports:
        raise RuntimeError("Product Loop Harness report case summary drifted")
    report["schema_files"] = _schema_report()
    dual_loop.assert_metadata_only(report, label="product-loop-harness-report")
    return report


def _write_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        product_loop_harness.write_artifact_set(FIXTURE_ROOT / case_id, artifacts)


def check_fixtures(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            path = FIXTURE_ROOT / case_id / filename
            if not path.is_file():
                raise SystemExit(f"Missing Product Loop Harness fixture: {path}")
            if _load_json(path) != payload:
                raise SystemExit(
                    f"Product Loop Harness fixture is out of date: {path}. "
                    "Run: python3 scripts/verify_product_loop_harness.py --write"
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
            raise SystemExit(f"Product Loop Harness report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Product Loop Harness report is out of date. "
                "Run: python3 scripts/verify_product_loop_harness.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
