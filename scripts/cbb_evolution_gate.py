#!/usr/bin/env python3
"""Build a signed, proposal-only Delivery Clearance evolution-gate receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.agentic.evolution import (  # noqa: E402
    issue_evolution_gate_receipt,
)
from study_anything.cbb.agentic.fixtures import (  # noqa: E402
    build_agentic_evolution_cases,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    assert_safe_metadata,
    pretty_json,
)
from study_anything.cbb.protocol.models import (  # noqa: E402
    AgenticEvidenceContextV1,
    EvolutionControlSetV1,
    EvolutionProposalV1,
)
from study_anything.cbb.provenance.signing import load_private_key  # noqa: E402


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert_safe_metadata(value, label=path.name)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _build(args: argparse.Namespace) -> str:
    inputs = _read_object(Path(args.input))
    receipt = issue_evolution_gate_receipt(
        EvolutionProposalV1.model_validate(inputs["proposal"]),
        AgenticEvidenceContextV1.model_validate(inputs["agentic_evidence"]),
        EvolutionControlSetV1.model_validate(inputs["controls"]),
        issued_at=str(inputs["issued_at"]),
        private_key=load_private_key(Path(args.private_key)),
        signer_id=args.signer_id,
        key_id=args.key_id,
        expires_at=args.expires_at,
        replay_nonce=args.replay_nonce,
    )
    return pretty_json(receipt)


def _demo(args: argparse.Namespace) -> str:
    cases = build_agentic_evolution_cases()
    if args.case not in cases:
        raise ValueError(f"unknown evolution case {args.case!r}; choose from {sorted(cases)}")
    return json.dumps(
        cases[args.case]["receipt"],
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--input", required=True)
    build.add_argument("--private-key", required=True)
    build.add_argument("--signer-id", required=True)
    build.add_argument("--key-id", required=True)
    build.add_argument("--expires-at", required=True)
    build.add_argument("--replay-nonce", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(handler=_build)

    demo = subparsers.add_parser("demo")
    demo.add_argument("--case", default="approved-local-candidate")
    demo.add_argument("--output", required=True)
    demo.set_defaults(handler=_demo)

    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(args.handler(args), encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
