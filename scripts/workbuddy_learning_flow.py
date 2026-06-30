#!/usr/bin/env python3
"""Run the WorkBuddy inline Study Anything learning flow."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.adapters.workbuddy_inline import (  # noqa: E402
    INPUT_SCHEMA_VERSION,
    WorkBuddyInlineError,
    build_workbuddy_learning_package,
    dump_json,
)


DEMO_CASES = {
    "deepseek-pm-interview": ROOT
    / "fixtures"
    / "workbuddy-learning-flow"
    / "deepseek-pm-interview"
    / "input.json"
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WorkBuddyInlineError(f"Cannot read JSON input {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkBuddyInlineError(f"JSON object expected: {path}")
    return payload


def write_optional(path_value: str | None, content: str) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run from a WorkBuddy learning input JSON file.")
    run.add_argument("--input", required=True, help=f"Path to {INPUT_SCHEMA_VERSION} JSON.")
    run.add_argument("--output", help="Optional JSON output path.")
    run.add_argument("--markdown", help="Optional Markdown output path.")
    run.add_argument("--data-dir", help="Optional data-dir hint; the inline flow does not create it.")

    demo = subparsers.add_parser("demo", help="Run a deterministic WorkBuddy inline demo case.")
    demo.add_argument("--case", choices=sorted(DEMO_CASES), default="deepseek-pm-interview")
    demo.add_argument("--output", help="Optional JSON output path.")
    demo.add_argument("--markdown", help="Optional Markdown output path.")
    demo.add_argument("--data-dir", help="Optional data-dir hint; the inline flow does not create it.")
    return parser


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_json(Path(args.input))
    return build_workbuddy_learning_package(payload, data_dir=args.data_dir, env=os.environ)


def demo_command(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_json(DEMO_CASES[args.case])
    return build_workbuddy_learning_package(payload, data_dir=args.data_dir, env=os.environ)


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.command == "run":
        output = run_command(args)
    elif args.command == "demo":
        output = demo_command(args)
    else:  # pragma: no cover - argparse prevents this
        raise WorkBuddyInlineError(f"Unsupported command: {args.command}")

    serialized = dump_json(output)
    write_optional(args.output, serialized)
    write_optional(args.markdown, str(output["exports"]["markdown_text"]))
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"workbuddy_learning_flow failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
