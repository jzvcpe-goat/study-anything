#!/usr/bin/env python3
"""Create an adoption-ready receipt or evaluate a signed external attestation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.adoption.attestation_intake import (  # noqa: E402
    adoption_attestation_ready_receipt,
    evaluate_external_adoption_attestation,
)
from study_anything.cbb.adoption.attestation_models import (  # noqa: E402
    AdoptionAttestationState,
    ExternalAdoptionAttestationEnvelopeV1,
    ExternalAdoptionExpectedScopeV1,
)
from study_anything.cbb.protocol.canonical import model_payload  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _emit(value: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    ready = subparsers.add_parser("ready")
    ready.add_argument("--expected-scope", type=Path, required=True)
    ready.add_argument("--evaluated-at", required=True)
    ready.add_argument("--out", type=Path)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--expected-scope", type=Path, required=True)
    evaluate.add_argument("--envelope", type=Path, required=True)
    evaluate.add_argument("--evaluated-at", required=True)
    evaluate.add_argument("--out", type=Path)
    args = parser.parse_args()
    expected = ExternalAdoptionExpectedScopeV1.model_validate(
        _load(args.expected_scope)
    )
    if args.command == "ready":
        receipt = adoption_attestation_ready_receipt(
            expected,
            evaluated_at=args.evaluated_at,
        )
    else:
        envelope = ExternalAdoptionAttestationEnvelopeV1.model_validate(
            _load(args.envelope)
        )
        receipt = evaluate_external_adoption_attestation(
            expected,
            envelope,
            evaluated_at=args.evaluated_at,
        )
    _emit(model_payload(receipt), args.out)
    return 1 if receipt.state == AdoptionAttestationState.REJECTED else 0


if __name__ == "__main__":
    raise SystemExit(main())
