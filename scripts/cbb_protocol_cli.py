#!/usr/bin/env python3
"""Build deterministic Cognitive Black Box protocol artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_protocol, dual_loop  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "cbb-protocol"


def demo(args: argparse.Namespace) -> int:
    artifacts = cbb_protocol.build_case_artifacts(args.case)
    output_dir = Path(args.output_dir)
    case_dir = output_dir / args.case
    case_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        cbb_protocol.write_json(case_dir / filename, payload)
    if args.html:
        cbb_protocol.write_html_report(
            case_dir / "delivery-decision-receipt.html",
            "CBB Delivery Decision Receipt",
            artifacts["delivery-decision-receipt.json"],
        )
    result = {
        "schema_version": "cbb-protocol-cli-result-v1",
        "status": artifacts["delivery-decision-receipt.json"]["status"],
        "decision": artifacts["delivery-decision-receipt.json"]["decision"],
        "case_id": args.case,
        "artifact_count": len(artifacts),
        "output_dir_name": output_dir.name,
        "privacy": dict(cbb_protocol.CBB_PRIVACY_FLAGS),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
    }
    dual_loop.assert_metadata_only(result, label="cbb-protocol-cli-result")
    print(cbb_protocol.dump_json(result), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo")
    demo_parser.add_argument(
        "--case",
        default="safe-controlled-handoff",
        choices=[
            "safe-controlled-handoff",
            "missing-claim-boundary",
            "reviewer-not-qualified",
            "recipient-risk-unknown",
            "ai-review-only-rejected",
        ],
    )
    demo_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    demo_parser.add_argument("--html", action="store_true")
    demo_parser.set_defaults(func=demo)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
