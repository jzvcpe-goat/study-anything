#!/usr/bin/env python3
"""Run deterministic Delivery Trust Case Harness artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import delivery_trust_case, dual_loop  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "delivery-trust-case"


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def _run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    selected = (
        delivery_trust_case.CASE_IDS
        if args.case == "all"
        else (args.case,)
    )
    cases: dict[str, dict[str, dict[str, Any]]] = {}
    for case_id in selected:
        artifacts = delivery_trust_case.build_case_artifacts(case_id)
        delivery_trust_case.write_artifact_set(output_dir / case_id, artifacts)
        cases[case_id] = artifacts
    report = delivery_trust_case.build_harness_report(cases)
    dual_loop.write_json(output_dir / "delivery-trust-case-harness-report.json", report)
    print(
        dual_loop.dump_json(
            {
                "schema_version": "delivery-trust-case-harness-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "output_dir": str(output_dir),
                "report": "delivery-trust-case-harness-report.json",
            }
        ),
        end="",
    )
    return 0


def _build(args: argparse.Namespace) -> int:
    package = _load_json(args.customer_handoff_package) if args.customer_handoff_package else None
    case = delivery_trust_case.build_delivery_trust_case(
        _load_json(args.product_loop_run),
        _load_json(args.dual_loop_gate),
        _load_json(args.delivery_trust_receipt),
        package,
        case_id=args.case_id,
    )
    output = Path(args.output)
    dual_loop.write_json(output, case)
    if args.html_output:
        dual_loop.write_html_report(args.html_output, "Delivery Trust Case", case)
    print(dual_loop.dump_json(case), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Generate deterministic delivery-trust cases")
    run.add_argument("--case", choices=("all", *delivery_trust_case.CASE_IDS), default="all")
    run.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    run.set_defaults(func=_run)

    build = sub.add_parser("build", help="Build one Delivery Trust Case from artifacts")
    build.add_argument("--product-loop-run", required=True)
    build.add_argument("--dual-loop-gate", required=True)
    build.add_argument("--delivery-trust-receipt", required=True)
    build.add_argument("--customer-handoff-package")
    build.add_argument("--case-id", default="custom")
    build.add_argument("--output", required=True)
    build.add_argument("--html-output")
    build.set_defaults(func=_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
