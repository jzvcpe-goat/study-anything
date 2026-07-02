#!/usr/bin/env python3
"""Build CBB self-intake receipts and delivery evidence packs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_protocol, cbb_receipt_chain, dual_loop  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "cbb-self-intake"


def _load_receipts(args: argparse.Namespace) -> dict[str, dict]:
    return {
        "claim-boundary.json": cbb_protocol.load_json(args.claim_boundary),
        "trust-root.json": cbb_protocol.load_json(args.trust_root),
        "reviewer-reconstruction-receipt.json": cbb_protocol.load_json(
            args.reviewer_reconstruction
        ),
        "risk-owner-scope.json": cbb_protocol.load_json(args.risk_owner_scope),
        "delivery-decision-receipt.json": cbb_protocol.load_json(args.delivery_decision),
    }


def build(args: argparse.Namespace) -> int:
    receipts = _load_receipts(args)
    chain = cbb_protocol.load_json(args.receipt_chain)
    self_intake = cbb_receipt_chain.build_self_intake_receipt(receipts, chain)
    evidence_pack = cbb_receipt_chain.build_delivery_evidence_pack(receipts, chain, self_intake)
    output = Path(args.output)
    pack_output = Path(args.pack_output)
    cbb_protocol.write_json(output, self_intake)
    cbb_protocol.write_json(pack_output, evidence_pack)
    if args.html_output:
        cbb_protocol.write_html_report(
            args.html_output,
            "CBB Self-Intake Receipt",
            self_intake,
        )
    result = {
        "schema_version": "cbb-self-intake-cli-result-v1",
        "status": self_intake["status"],
        "decision": self_intake["decision"],
        "self_intake_id": self_intake["self_intake_id"],
        "chain_digest": self_intake["receipt_chain"]["chain_digest"],
        "output_name": output.name,
        "pack_output_name": pack_output.name,
        "privacy": dict(cbb_protocol.CBB_PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }
    dual_loop.assert_metadata_only(result, label="cbb-self-intake-cli-result")
    print(cbb_protocol.dump_json(result), end="")
    return 0


def demo(args: argparse.Namespace) -> int:
    artifacts = cbb_receipt_chain.build_pr_285_self_intake_artifacts()
    output_dir = Path(args.output_dir)
    cbb_receipt_chain.write_artifact_set(output_dir, artifacts)
    if args.html:
        cbb_protocol.write_html_report(
            output_dir / "self-intake-receipt.html",
            "CBB Self-Intake Receipt",
            artifacts["self-intake-receipt.json"],
        )
    result = {
        "schema_version": "cbb-self-intake-cli-result-v1",
        "status": artifacts["self-intake-receipt.json"]["status"],
        "decision": artifacts["self-intake-receipt.json"]["decision"],
        "self_intake_id": artifacts["self-intake-receipt.json"]["self_intake_id"],
        "chain_digest": artifacts["receipt-chain.json"]["chain_digest"],
        "output_dir_name": output_dir.name,
        "privacy": dict(cbb_protocol.CBB_PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }
    dual_loop.assert_metadata_only(result, label="cbb-self-intake-demo-result")
    print(cbb_protocol.dump_json(result), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--claim-boundary", required=True)
    build_parser.add_argument("--trust-root", required=True)
    build_parser.add_argument("--reviewer-reconstruction", required=True)
    build_parser.add_argument("--risk-owner-scope", required=True)
    build_parser.add_argument("--delivery-decision", required=True)
    build_parser.add_argument("--receipt-chain", required=True)
    build_parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_DIR / "self-intake-receipt.json"),
    )
    build_parser.add_argument(
        "--pack-output",
        default=str(DEFAULT_OUTPUT_DIR / "delivery-evidence-pack.json"),
    )
    build_parser.add_argument("--html-output")
    build_parser.set_defaults(func=build)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "pr-285"))
    demo_parser.add_argument("--html", action="store_true")
    demo_parser.set_defaults(func=demo)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
