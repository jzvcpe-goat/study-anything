#!/usr/bin/env python3
"""Create and verify local CBB Protocol v1 provenance packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.protocol.canonical import model_payload  # noqa: E402
from study_anything.cbb.protocol.models import (  # noqa: E402
    DeliveryScope,
    DeliveryTrustReceiptV1,
    EvidenceBundleV1,
    GateDecisionV1,
    QualifiedReconstructionV1,
    ReceiptProvenanceV1,
    TrustPolicyV1,
)
from study_anything.cbb.provenance.signing import (  # noqa: E402
    OfflineProvenancePackageV1,
    ProvenanceDependencyError,
    ProvenanceKeyError,
    build_offline_package,
    generate_private_key,
    load_private_key,
    sign_provenance,
    verify_offline_package,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path.name}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _canonical_set(payload: dict[str, Any]) -> dict[str, Any]:
    canonical = payload.get("canonical", payload)
    if not isinstance(canonical, dict):
        raise ValueError("input canonical set must be a JSON object")
    return canonical


def _sign(args: argparse.Namespace) -> int:
    canonical = _canonical_set(_load_json(Path(args.input)))
    policy = TrustPolicyV1.model_validate(canonical["trust_policy"])
    evidence = EvidenceBundleV1.model_validate(canonical["evidence_bundle"])
    reconstruction = QualifiedReconstructionV1.model_validate(
        canonical["qualified_reconstruction"]
    )
    decision = GateDecisionV1.model_validate(canonical["gate_decision"])
    receipt = DeliveryTrustReceiptV1.model_validate(canonical["delivery_trust_receipt"])
    provenance = ReceiptProvenanceV1.model_validate(canonical["receipt_provenance"])
    scope = DeliveryScope(args.maximum_scope) if args.maximum_scope else None
    signed = sign_provenance(
        provenance,
        policy,
        evidence,
        reconstruction,
        decision,
        receipt,
        load_private_key(Path(args.private_key)),
        signer_id=args.signer_id,
        key_id=args.key_id,
        maximum_scope=scope,
    )
    package = build_offline_package(
        policy,
        evidence,
        reconstruction,
        decision,
        receipt,
        signed,
    )
    _write_json(Path(args.output), model_payload(package))
    print(json.dumps({"status": "signed", "package_id": package.package_id}, sort_keys=True))
    return 0


def _verify(args: argparse.Namespace) -> int:
    package = OfflineProvenancePackageV1.model_validate(_load_json(Path(args.input)))
    revoked_handles: list[str] = []
    if args.revocations:
        registry = _load_json(Path(args.revocations))
        values = registry.get("revoked_handles", [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError("revocation registry must contain a revoked_handles string list")
        revoked_handles = values
    seen_nonces: set[str] | None = None
    ledger_path = Path(args.replay_ledger) if args.replay_ledger else None
    if args.consume:
        seen_nonces = set()
        if ledger_path and ledger_path.is_file():
            ledger = _load_json(ledger_path)
            values = ledger.get("seen_nonces", [])
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError("replay ledger must contain a seen_nonces string list")
            seen_nonces.update(values)
    result = verify_offline_package(
        package,
        now=args.now,
        revoked_handles=revoked_handles,
        seen_nonces=seen_nonces,
        consume_nonce=args.consume,
    )
    if args.consume and ledger_path is not None and seen_nonces is not None:
        _write_json(ledger_path, {"seen_nonces": sorted(seen_nonces)})
    print(
        json.dumps(
            {
                "status": result.status,
                "checks": dict(result.checks),
                "reasons": list(result.reasons),
                "signing_status": result.signing_status,
                "approved_scope": result.approved_scope,
            },
            sort_keys=True,
        )
    )
    return 0 if result.passed else 1


def _keygen(args: argparse.Namespace) -> int:
    if not args.acknowledge_local_identity_only:
        raise ValueError("key generation requires --acknowledge-local-identity-only")
    generate_private_key(Path(args.private_key), overwrite=args.overwrite)
    print(json.dumps({"status": "generated", "identity_scope": "local_self_asserted"}))
    return 0


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    keygen = commands.add_parser("keygen", help="generate an owner-only local Ed25519 key")
    keygen.add_argument("--private-key", required=True)
    keygen.add_argument("--overwrite", action="store_true")
    keygen.add_argument("--acknowledge-local-identity-only", action="store_true")
    keygen.set_defaults(handler=_keygen)

    sign = commands.add_parser("sign", help="sign a canonical v1 receipt set")
    sign.add_argument("--input", required=True)
    sign.add_argument("--private-key", required=True)
    sign.add_argument("--signer-id", required=True)
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--maximum-scope", choices=[scope.value for scope in DeliveryScope])
    sign.add_argument("--output", required=True)
    sign.set_defaults(handler=_sign)

    verify = commands.add_parser("verify", help="verify a metadata-only package offline")
    verify.add_argument("--input", required=True)
    verify.add_argument("--now")
    verify.add_argument("--revocations")
    verify.add_argument("--consume", action="store_true")
    verify.add_argument("--replay-ledger")
    verify.set_defaults(handler=_verify)

    args = parser.parse_args()
    return int(args.handler(args))


def main() -> int:
    try:
        return _main()
    except ProvenanceDependencyError as exc:
        print(str(exc), file=sys.stderr)
    except ProvenanceKeyError as exc:
        print(f"cbb_provenance failed: {exc}", file=sys.stderr)
    except FileExistsError:
        print("cbb_provenance failed: key_target_exists", file=sys.stderr)
    except (KeyError, OSError, ValueError):
        print("cbb_provenance failed: invalid_or_unreadable_input", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
