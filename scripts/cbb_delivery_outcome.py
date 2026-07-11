#!/usr/bin/env python3
"""Build a metadata-only Delivery Clearance post-delivery outcome receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.outcomes.evaluator import (  # noqa: E402
    evaluate_delivery_outcome,
)
from study_anything.cbb.outcomes.fixtures import build_outcome_cases  # noqa: E402
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    assert_safe_metadata,
    pretty_json,
)
from study_anything.cbb.protocol.models import (  # noqa: E402
    OutcomeEventV1,
    PostDeliverySamplingV1,
    RollbackOutcomeV1,
)
from study_anything.cbb.provenance.signing import (  # noqa: E402
    OfflineProvenancePackageV1,
    load_private_key,
)


def _read_json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert_safe_metadata(value, label=path.name)
    return value


def _read_object(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _revoked_handles(path: Path | None) -> list[str]:
    if path is None:
        return []
    value = _read_json(path)
    if isinstance(value, dict):
        value = value.get("revoked_handles")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("revocation registry must be a string list or revoked_handles object")
    return value


def _build(args: argparse.Namespace) -> str:
    package = OfflineProvenancePackageV1.model_validate(_read_object(Path(args.package)))
    inputs = _read_object(Path(args.observations))
    receipt = evaluate_delivery_outcome(
        package,
        sampling=PostDeliverySamplingV1.model_validate(inputs["sampling"]),
        events=[OutcomeEventV1.model_validate(item) for item in inputs["events"]],
        rollback=RollbackOutcomeV1.model_validate(inputs["rollback"]),
        recipe_ref=str(inputs["recipe_ref"]),
        issued_at=str(inputs["issued_at"]),
        private_key=load_private_key(Path(args.private_key)),
        signer_id=args.signer_id,
        key_id=args.key_id,
        expires_at=args.expires_at,
        replay_nonce=args.replay_nonce,
        revoked_handles=_revoked_handles(
            Path(args.revocation_registry) if args.revocation_registry else None
        ),
    )
    return pretty_json(receipt)


def _demo(args: argparse.Namespace) -> str:
    cases = build_outcome_cases()
    if args.case not in cases:
        raise ValueError(f"unknown outcome case {args.case!r}; choose from {sorted(cases)}")
    return (
        json.dumps(
            cases[args.case]["receipt"],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--package", required=True)
    build.add_argument("--observations", required=True)
    build.add_argument("--revocation-registry")
    build.add_argument("--private-key", required=True)
    build.add_argument("--signer-id", required=True)
    build.add_argument("--key-id", required=True)
    build.add_argument("--expires-at", required=True)
    build.add_argument("--replay-nonce", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(handler=_build)

    demo = subparsers.add_parser("demo")
    demo.add_argument("--case", default="monitored-no-adverse-signal")
    demo.add_argument("--output", required=True)
    demo.set_defaults(handler=_demo)

    args = parser.parse_args()
    serialized = args.handler(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
