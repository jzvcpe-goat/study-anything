#!/usr/bin/env python3
"""Generate deterministic metadata-only Attention Reconstruction Lite artifacts."""

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


DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "dual-loop" / "attention-reconstruction-lite"


def build(output_dir: Path, *, failure_contract: Path | None, html: bool) -> dict[str, Any]:
    if failure_contract:
        contract = dual_loop.load_json(failure_contract)
        dual_loop.validate_failure_contract(contract)
    else:
        contract = dual_loop.failure_contract_demo()

    trace = dual_loop.attention_trace_demo()
    summary = dual_loop.attention_summary_demo()
    if trace["contract_id"] != contract["contract_id"]:
        raise dual_loop.DualLoopContractError("attention trace must match failure contract")
    dual_loop.validate_attention_trace(trace)
    dual_loop.validate_attention_summary(summary)

    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / "attention-reconstruction-trace.json"
    summary_path = output_dir / "attention-reconstruction-summary.json"
    dual_loop.write_json(trace_path, trace)
    dual_loop.write_json(summary_path, summary)

    html_path = None
    if html:
        html_path = output_dir / "attention-reconstruction-report.html"
        dual_loop.write_html_report(
            html_path,
            "Attention Reconstruction Lite",
            {
                "schema_version": "attention-reconstruction-lite-report-v1",
                "status": "pass",
                "trace": trace,
                "summary": summary,
                "privacy": dict(dual_loop.PRIVACY_FLAGS),
                "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
            },
        )

    result = {
        "schema_version": "attention-reconstruction-lite-cli-result-v1",
        "status": "ok",
        "trace_path": dual_loop.output_ref(trace_path),
        "summary_path": dual_loop.output_ref(summary_path),
        "html_report_path": dual_loop.output_ref(html_path) if html_path else None,
        "artifact_schemas": [
            dual_loop.ATTENTION_TRACE_SCHEMA_VERSION,
            dual_loop.ATTENTION_SUMMARY_SCHEMA_VERSION,
        ],
        "privacy": dict(dual_loop.PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }
    dual_loop.assert_metadata_only(result, label="attention-reconstruction-lite-cli-result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    demo = subparsers.add_parser("demo")
    demo.add_argument("--failure-contract")
    demo.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    demo.add_argument("--html", action="store_true")
    args = parser.parse_args()

    if args.command == "demo":
        contract = Path(args.failure_contract) if args.failure_contract else None
        result = build(Path(args.output_dir), failure_contract=contract, html=args.html)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
