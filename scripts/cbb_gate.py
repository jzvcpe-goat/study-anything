#!/usr/bin/env python3
"""Evaluate the Cognitive Black Box delivery gate from structured receipts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_protocol  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT / ".cognitive-loop" / "artifacts" / "cbb-protocol" / "delivery-decision-receipt.json"
)


def evaluate(args: argparse.Namespace) -> int:
    receipt = cbb_protocol.evaluate_cbb_gate(
        cbb_protocol.load_json(args.claim_boundary),
        cbb_protocol.load_json(args.trust_root),
        cbb_protocol.load_json(args.reviewer_reconstruction),
        cbb_protocol.load_json(args.risk_owner_scope),
        decision_id=args.decision_id,
    )
    output = Path(args.output)
    cbb_protocol.write_json(output, receipt)
    if args.html_output:
        cbb_protocol.write_html_report(
            args.html_output,
            "CBB Delivery Decision Receipt",
            receipt,
        )
    print(cbb_protocol.dump_json(receipt), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--claim-boundary", required=True)
    evaluate_parser.add_argument("--trust-root", required=True)
    evaluate_parser.add_argument("--reviewer-reconstruction", required=True)
    evaluate_parser.add_argument("--risk-owner-scope", required=True)
    evaluate_parser.add_argument("--decision-id", default="delivery-decision-demo-001")
    evaluate_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    evaluate_parser.add_argument("--html-output")
    evaluate_parser.set_defaults(func=evaluate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
