#!/usr/bin/env python3
"""Evaluate one operator-supplied controlled-adoption observation offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.adoption.evaluator import (  # noqa: E402
    evaluate_controlled_adoption,
)
from study_anything.cbb.adoption.attestation_models import (  # noqa: E402
    ExternalAdoptionAttestationEnvelopeV1,
    ExternalAdoptionExpectedScopeV1,
)
from study_anything.cbb.adoption.models import ControlledAdoptionCaseV1  # noqa: E402
from study_anything.cbb.protocol.canonical import model_payload  # noqa: E402
from study_anything.cbb.provenance.signing import (  # noqa: E402
    OfflineProvenancePackageV1,
)


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
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--expected-release-commit", required=True)
    parser.add_argument("--conformance-pack-sha256", required=True)
    parser.add_argument("--external-attestation-expected-scope", type=Path)
    parser.add_argument("--external-attestation-envelope", type=Path)
    parser.add_argument("--revoked-handle", action="append", default=[])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    package = OfflineProvenancePackageV1.model_validate(_load(args.package))
    case = ControlledAdoptionCaseV1.model_validate(_load(args.case))
    attestation_expected_scope = (
        ExternalAdoptionExpectedScopeV1.model_validate(
            _load(args.external_attestation_expected_scope)
        )
        if args.external_attestation_expected_scope is not None
        else None
    )
    attestation_envelope = (
        ExternalAdoptionAttestationEnvelopeV1.model_validate(
            _load(args.external_attestation_envelope)
        )
        if args.external_attestation_envelope is not None
        else None
    )
    receipt = evaluate_controlled_adoption(
        package,
        case,
        expected_release_scope_commit=args.expected_release_commit,
        expected_conformance_pack_sha256=args.conformance_pack_sha256,
        revoked_source_handles=set(args.revoked_handle),
        external_attestation_expected_scope=attestation_expected_scope,
        external_attestation_envelope=attestation_envelope,
    )
    _emit(model_payload(receipt), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
