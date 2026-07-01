#!/usr/bin/env python3
"""Build metadata-only delivery trust receipts from Dual-Loop evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import delivery_trust  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT / ".cognitive-loop" / "artifacts" / "delivery-trust" / "delivery-trust-receipt.json"
)


def build(args: argparse.Namespace) -> int:
    attention_summary = (
        delivery_trust.load_json(args.attention_summary) if args.attention_summary else None
    )
    receipt = delivery_trust.build_delivery_trust_receipt(
        delivery_trust.load_json(args.failure_contract),
        delivery_trust.load_json(args.sandbox_receipt),
        delivery_trust.load_json(args.dual_loop_gate),
        attention_summary,
        receipt_id=args.receipt_id,
    )
    output = Path(args.output)
    delivery_trust.write_json(output, receipt)
    if args.html_output:
        delivery_trust.write_html_report(
            args.html_output,
            "Delivery Trust Receipt",
            receipt,
        )
    print(delivery_trust.dump_json(receipt), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--failure-contract", required=True)
    build_parser.add_argument("--sandbox-receipt", required=True)
    build_parser.add_argument("--dual-loop-gate", required=True)
    build_parser.add_argument("--attention-summary")
    build_parser.add_argument("--receipt-id", default="delivery-trust-receipt-demo-001")
    build_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    build_parser.add_argument("--html-output")
    build_parser.set_defaults(func=build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
