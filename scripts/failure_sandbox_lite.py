#!/usr/bin/env python3
"""Generate deterministic metadata-only Failure Sandbox Lite artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
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


DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "dual-loop" / "failure-sandbox-lite"


def build(output_dir: Path, *, html: bool) -> dict[str, Any]:
    contract = dual_loop.failure_contract_demo()
    receipt = dual_loop.sandbox_receipt_demo()
    dual_loop.validate_failure_contract(contract)
    dual_loop.validate_sandbox_receipt(receipt)

    output_dir.mkdir(parents=True, exist_ok=True)
    contract_path = output_dir / "failure-contract.json"
    receipt_path = output_dir / "sandbox-receipt.json"
    dual_loop.write_json(contract_path, contract)
    dual_loop.write_json(receipt_path, receipt)

    html_path = None
    if html:
        html_path = output_dir / "failure-sandbox-report.html"
        dual_loop.write_html_report(
            html_path,
            "Failure Sandbox Lite",
            {
                "schema_version": "failure-sandbox-lite-report-v1",
                "status": "pass",
                "contract": contract,
                "sandbox_receipt": receipt,
                "privacy": dict(dual_loop.PRIVACY_FLAGS),
                "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
            },
        )

    summary = {
        "schema_version": "failure-sandbox-lite-cli-result-v1",
        "status": "ok",
        "failure_contract_path": dual_loop.output_ref(contract_path),
        "sandbox_receipt_path": dual_loop.output_ref(receipt_path),
        "html_report_path": dual_loop.output_ref(html_path) if html_path else None,
        "artifact_schemas": [
            dual_loop.FAILURE_CONTRACT_SCHEMA_VERSION,
            dual_loop.SANDBOX_RECEIPT_SCHEMA_VERSION,
        ],
        "privacy": dict(dual_loop.PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }
    dual_loop.assert_metadata_only(summary, label="failure-sandbox-lite-cli-result")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo")
    demo.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    demo.add_argument("--html", action="store_true")
    args = parser.parse_args()

    if args.command == "demo":
        result = build(Path(args.output_dir), html=args.html)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
