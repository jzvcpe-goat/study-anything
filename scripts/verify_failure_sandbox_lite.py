#!/usr/bin/env python3
"""Verify Failure Sandbox Lite CLI output and privacy boundaries."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DUAL_LOOP_MODULE_PATH = ROOT / "apps" / "api" / "study_anything" / "core" / "dual_loop.py"


def _load_dual_loop() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_dual_loop", DUAL_LOOP_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Dual-Loop module: {DUAL_LOOP_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dual_loop = _load_dual_loop()


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-failure-sandbox-lite.json"


def run_cli(output_dir: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "failure_sandbox_lite.py"),
            "demo",
            "--output-dir",
            str(output_dir),
            "--html",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(proc.stdout)
    dual_loop.assert_metadata_only(payload, label="failure-sandbox-lite-cli-stdout")
    return payload


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-dual-loop-") as tmp:
        output_dir = Path(tmp) / "failure-sandbox"
        result = run_cli(output_dir)
        contract = dual_loop.validate_failure_contract(
            dual_loop.load_json(output_dir / "failure-contract.json")
        )
        receipt = dual_loop.validate_sandbox_receipt(
            dual_loop.load_json(output_dir / "sandbox-receipt.json")
        )
        html_path = output_dir / "failure-sandbox-report.html"
        if not html_path.is_file():
            raise RuntimeError("Failure Sandbox Lite HTML report was not generated")
        html_text = html_path.read_text(encoding="utf-8")
        dual_loop.assert_metadata_only(html_text, label="failure-sandbox-lite-html")
    return {
        "schema_version": dual_loop.FAILURE_SANDBOX_LITE_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "cli_result_schema": result["schema_version"],
        "artifact_contracts": [contract["schema_version"], receipt["schema_version"]],
        "sandbox": {
            "status": receipt["status"],
            "risk_within_budget": receipt["risk_budget"]["within_budget"],
            "production_mutation": receipt["mutation_summary"]["production_mutation"],
            "contained_failure_count": len(receipt["observed_failures"]),
        },
        "privacy": {
            **dual_loop.PRIVACY_FLAGS,
            "metadata_only_html": True,
            "raw_failure_payloads_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_failure_sandbox_lite.py --check",
            "demo_command": "python3 scripts/failure_sandbox_lite.py demo --html",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    output = Path(args.output)
    report = build_report()
    serialized = dual_loop.dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Failure Sandbox Lite report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Failure Sandbox Lite report is out of date. "
                "Run: python3 scripts/verify_failure_sandbox_lite.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
