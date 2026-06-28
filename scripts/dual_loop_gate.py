#!/usr/bin/env python3
"""Evaluate the Dual-Loop Propagation Gate from structured artifacts only."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DUAL_LOOP_MODULE_PATH = ROOT / "apps" / "api" / "study_anything" / "core" / "dual_loop.py"


def _load_dual_loop():
    spec = importlib.util.spec_from_file_location("study_anything_dual_loop", DUAL_LOOP_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Dual-Loop module: {DUAL_LOOP_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dual_loop = _load_dual_loop()


DEFAULT_OUTPUT = ROOT / ".cognitive-loop" / "artifacts" / "dual-loop" / "gate" / "dual-loop-gate-receipt.json"


def evaluate(
    failure_contract_path: Path,
    sandbox_receipt_path: Path,
    attention_summary_path: Path | None,
    output_path: Path,
    *,
    html_path: Path | None,
) -> dict[str, object]:
    contract = dual_loop.load_json(failure_contract_path)
    sandbox = dual_loop.load_json(sandbox_receipt_path)
    attention = dual_loop.load_json(attention_summary_path) if attention_summary_path else None
    receipt = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention)
    dual_loop.write_json(output_path, receipt)
    if html_path:
        dual_loop.write_html_report(html_path, "Dual-Loop Propagation Gate", receipt)
    return {
        "schema_version": "dual-loop-gate-cli-result-v1",
        "status": receipt["status"],
        "decision": receipt["decision"],
        "gate_receipt_path": dual_loop.output_ref(output_path),
        "html_report_path": dual_loop.output_ref(html_path) if html_path else None,
        "reasons": receipt["reasons"],
        "privacy": dict(dual_loop.PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--failure-contract", required=True)
    evaluate_parser.add_argument("--sandbox-receipt", required=True)
    evaluate_parser.add_argument("--attention-summary")
    evaluate_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    evaluate_parser.add_argument("--html-output")
    args = parser.parse_args()

    if args.command == "evaluate":
        result = evaluate(
            Path(args.failure_contract),
            Path(args.sandbox_receipt),
            Path(args.attention_summary) if args.attention_summary else None,
            Path(args.output),
            html_path=Path(args.html_output) if args.html_output else None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
