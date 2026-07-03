#!/usr/bin/env python3
"""Run deterministic Product Loop Harness artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_protocol, product_loop_harness  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "product-loop-harness"


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def _run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    selected = (
        product_loop_harness.CASE_IDS
        if args.case == "all"
        else (args.case,)
    )
    cases: dict[str, dict[str, dict[str, Any]]] = {}
    for case_id in selected:
        artifacts = product_loop_harness.build_case_artifacts(case_id)
        product_loop_harness.write_artifact_set(output_dir / case_id, artifacts)
        cases[case_id] = artifacts
    report = product_loop_harness.build_harness_report(cases)
    cbb_protocol.write_json(output_dir / "product-loop-harness-report.json", report)
    print(
        cbb_protocol.dump_json(
            {
                "schema_version": "product-loop-harness-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "output_dir": str(output_dir),
                "report": "product-loop-harness-report.json",
            }
        ),
        end="",
    )
    return 0


def _build(args: argparse.Namespace) -> int:
    scenario = _load_json(args.scenario)
    run = product_loop_harness.build_product_loop_run(scenario)
    output = Path(args.output)
    cbb_protocol.write_json(output, run)
    print(cbb_protocol.dump_json(run), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Generate deterministic product-loop artifacts")
    run.add_argument(
        "--case",
        choices=("all", *product_loop_harness.CASE_IDS),
        default="all",
    )
    run.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    run.set_defaults(func=_run)

    build = sub.add_parser("build", help="Build one product-loop run from a scenario")
    build.add_argument("--scenario", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(func=_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
