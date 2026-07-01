#!/usr/bin/env python3
"""Build metadata-only LLM Depth Risk Engine evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.core.llm_depth_risk import (  # noqa: E402
    LLMDepthRiskError,
    build_llm_depth_risk_report,
    dump_json,
    load_json,
    render_html,
    validate_llm_depth_risk_report,
)


DEFAULT_FIXTURE = ROOT / "fixtures" / "llm-depth-risk" / "pass.json"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build LLM depth risk evidence.")
    build.add_argument("--input", default=str(DEFAULT_FIXTURE), help="Input fixture JSON.")
    build.add_argument("--output", help="Optional JSON output path.")
    build.add_argument("--html", help="Optional static HTML output path.")
    build.add_argument("--summary", action="store_true", help="Print compact summary instead of full JSON.")
    return parser


def write_optional(path_value: str | None, content: str) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    payload = load_json(args.input)
    report = build_llm_depth_risk_report(payload)
    validate_llm_depth_risk_report(report)
    write_optional(args.output, dump_json(report))
    if args.html:
        write_optional(args.html, render_html(report))
    if args.summary:
        from study_anything.core.llm_depth_risk import summarize_report

        print(dump_json(summarize_report(report)), end="")
    else:
        print(dump_json(report), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LLMDepthRiskError as exc:
        print(f"llm_depth_risk_engine failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
