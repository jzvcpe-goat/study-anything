#!/usr/bin/env python3
"""Build metadata-only real-agent eval bridge reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.core.real_agent_eval_bridge import (  # noqa: E402
    RealAgentEvalBridgeError,
    build_real_agent_eval_bridge_report,
    build_real_agent_learning_quality_report,
    dump_json,
    load_json,
    render_bridge_html,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser("eval-bridge")
    eval_parser.add_argument("--input", required=True)
    eval_parser.add_argument("--output")
    eval_parser.add_argument("--html")

    quality_parser = subparsers.add_parser("learning-quality")
    quality_parser.add_argument("--input", required=True)
    quality_parser.add_argument("--output")
    quality_parser.add_argument("--html")

    args = parser.parse_args()
    payload = load_json(args.input)
    if args.command == "eval-bridge":
        report = build_real_agent_eval_bridge_report(payload)
        title = "Real Agent Eval Bridge"
    else:
        report = build_real_agent_learning_quality_report(payload)
        title = "WorkBuddy Real Agent Learning Quality"
    serialized = dump_json(report)
    if args.output:
        Path(args.output).write_text(serialized, encoding="utf-8")
    if args.html:
        Path(args.html).write_text(render_bridge_html(report, title=title), encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RealAgentEvalBridgeError as exc:
        print(f"real_agent_eval_bridge failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
