#!/usr/bin/env python3
"""Build tamper-evident Cognitive Black Box receipt chains."""

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
    chain = cbb_receipt_chain.build_receipt_chain(receipts)
    output = Path(args.output)
    cbb_protocol.write_json(output, chain)
    result = {
        "schema_version": "cbb-receipt-chain-cli-result-v1",
        "status": "pass",
        "chain_id": chain["chain_id"],
        "chain_digest": chain["chain_digest"],
        "receipt_count": len(chain["receipts"]),
        "output_name": output.name,
        "privacy": dict(cbb_protocol.CBB_PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }
    dual_loop.assert_metadata_only(result, label="cbb-receipt-chain-cli-result")
    print(cbb_protocol.dump_json(result), end="")
    return 0


def demo(args: argparse.Namespace) -> int:
    artifacts = cbb_receipt_chain.build_pr_285_self_intake_artifacts()
    output_dir = Path(args.output_dir)
    cbb_receipt_chain.write_artifact_set(output_dir, artifacts)
    result = {
        "schema_version": "cbb-receipt-chain-cli-result-v1",
        "status": "pass",
        "chain_id": artifacts["receipt-chain.json"]["chain_id"],
        "chain_digest": artifacts["receipt-chain.json"]["chain_digest"],
        "receipt_count": len(artifacts["receipt-chain.json"]["receipts"]),
        "output_dir_name": output_dir.name,
        "privacy": dict(cbb_protocol.CBB_PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }
    dual_loop.assert_metadata_only(result, label="cbb-receipt-chain-demo-result")
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
    build_parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_DIR / "receipt-chain.json"),
    )
    build_parser.set_defaults(func=build)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "pr-285"))
    demo_parser.set_defaults(func=demo)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
