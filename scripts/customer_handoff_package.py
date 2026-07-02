#!/usr/bin/env python3
"""Build metadata-only CustomerHandoffPackage artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import customer_handoff  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "customer-handoff"
    / "customer-handoff-package.json"
)


def build(args: argparse.Namespace) -> int:
    external_eval_receipts = (
        customer_handoff.load_json(args.external_eval_receipts)
        if args.external_eval_receipts
        else None
    )
    package = customer_handoff.build_customer_handoff_package(
        customer_handoff.load_json(args.delivery_trust_receipt),
        customer_handoff.load_json(args.failure_contract),
        customer_handoff.load_json(args.sandbox_receipt),
        customer_handoff.load_json(args.attention_summary),
        customer_handoff.load_json(args.dual_loop_gate),
        external_eval_receipts=external_eval_receipts,
        package_id=args.package_id,
    )
    output = Path(args.output)
    customer_handoff.write_json(output, package)
    if args.html_output:
        customer_handoff.write_html_report(
            args.html_output,
            "Customer Handoff Package",
            package,
        )
    if args.zip_output:
        html = (
            Path(args.html_output).read_text(encoding="utf-8")
            if args.html_output
            else customer_handoff.render_html_report("Customer Handoff Package", package)
        )
        customer_handoff.write_zip_package(args.zip_output, package, html)
    print(customer_handoff.dump_json(package), end="")
    return 0


def validate_zip(args: argparse.Namespace) -> int:
    package = customer_handoff.validate_zip_package(args.zip)
    print(customer_handoff.dump_json(package), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--delivery-trust-receipt", required=True)
    build_parser.add_argument("--failure-contract", required=True)
    build_parser.add_argument("--sandbox-receipt", required=True)
    build_parser.add_argument("--attention-summary", required=True)
    build_parser.add_argument("--dual-loop-gate", required=True)
    build_parser.add_argument("--external-eval-receipts")
    build_parser.add_argument("--package-id", default="customer-handoff-package-demo-001")
    build_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    build_parser.add_argument("--html-output")
    build_parser.add_argument("--zip-output")
    build_parser.set_defaults(func=build)

    zip_parser = subparsers.add_parser("validate-zip")
    zip_parser.add_argument("--zip", required=True)
    zip_parser.set_defaults(func=validate_zip)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
