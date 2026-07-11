"""Deterministic, public-only fixtures for CBB v1 provenance verification."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from study_anything.cbb.protocol.canonical import model_payload
from study_anything.cbb.protocol.fixtures import build_fixture_payloads
from study_anything.cbb.protocol.models import (
    DeliveryTrustReceiptV1,
    EvidenceBundleV1,
    GateDecisionV1,
    QualifiedReconstructionV1,
    ReceiptProvenanceV1,
    TrustPolicyV1,
)
from study_anything.cbb.provenance.signing import (
    OfflineProvenancePackageV1,
    build_offline_package,
    sign_provenance,
)


FIXTURE_ROOT = Path("fixtures") / "cbb-v1-provenance"
FIXTURE_NOW = "2026-07-10T00:00:00Z"
EXPIRED_NOW = "2026-09-27T00:00:00Z"
FIXTURE_SIGNER_ID = "fixture-local-signer"
FIXTURE_KEY_ID = "fixture-ed25519-key-1"


def _fixture_private_key(seed: bytes = b"cbb-v1-public-fixture-key") -> Any:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed).digest())


def _canonical_models() -> tuple[
    TrustPolicyV1,
    EvidenceBundleV1,
    QualifiedReconstructionV1,
    GateDecisionV1,
    DeliveryTrustReceiptV1,
    ReceiptProvenanceV1,
]:
    canonical = build_fixture_payloads()["pass.json"]["canonical"]
    return (
        TrustPolicyV1.model_validate(canonical["trust_policy"]),
        EvidenceBundleV1.model_validate(canonical["evidence_bundle"]),
        QualifiedReconstructionV1.model_validate(canonical["qualified_reconstruction"]),
        GateDecisionV1.model_validate(canonical["gate_decision"]),
        DeliveryTrustReceiptV1.model_validate(canonical["delivery_trust_receipt"]),
        ReceiptProvenanceV1.model_validate(canonical["receipt_provenance"]),
    )


def signed_package() -> OfflineProvenancePackageV1:
    policy, evidence, reconstruction, decision, receipt, unsigned = _canonical_models()
    signed = sign_provenance(
        unsigned,
        policy,
        evidence,
        reconstruction,
        decision,
        receipt,
        _fixture_private_key(),
        signer_id=FIXTURE_SIGNER_ID,
        key_id=FIXTURE_KEY_ID,
    )
    return build_offline_package(
        policy,
        evidence,
        reconstruction,
        decision,
        receipt,
        signed,
    )


def unsigned_package() -> OfflineProvenancePackageV1:
    policy, evidence, reconstruction, decision, receipt, unsigned = _canonical_models()
    return build_offline_package(
        policy,
        evidence,
        reconstruction,
        decision,
        receipt,
        unsigned,
    )


def _replace_provenance(
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    payload["receipt_provenance"] = provenance
    payload["delivery_trust_receipt"]["provenance"] = deepcopy(provenance)


def _tamper_package(
    base: dict[str, Any],
    case_id: str,
) -> dict[str, Any]:
    payload = deepcopy(base)
    if case_id == "tampered-policy":
        payload["trust_policy"]["scenario"]["recipient"]["recipient_ref"] = (
            "recipient:tampered"
        )
    elif case_id == "tampered-evidence":
        payload["evidence_bundle"]["evidence"][0]["metadata"]["tampered"] = True
    elif case_id == "tampered-reconstruction":
        payload["qualified_reconstruction"]["evidence_refs"].append(
            "tampered-reconstruction-ref.json"
        )
    elif case_id == "tampered-decision":
        payload["gate_decision"]["source_decision_refs"].append(
            "tampered-decision-ref.json"
        )
    elif case_id == "tampered-receipt":
        payload["delivery_trust_receipt"]["receipt_id"] = "cbb-receipt:tampered"
    elif case_id == "tampered-signature":
        provenance = deepcopy(payload["receipt_provenance"])
        signature = provenance["signature"]
        provenance["signature"] = signature[:-1] + ("A" if signature[-1] != "A" else "B")
        _replace_provenance(payload, provenance)
    elif case_id == "wrong-public-key":
        replacement = _fixture_private_key(b"cbb-v1-second-public-fixture-key")
        from cryptography.hazmat.primitives import serialization

        raw_public = replacement.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        from base64 import urlsafe_b64encode

        provenance = deepcopy(payload["receipt_provenance"])
        provenance["signer"]["public_key"] = (
            urlsafe_b64encode(raw_public).rstrip(b"=").decode("ascii")
        )
        provenance["signer"]["public_key_fingerprint_sha256"] = hashlib.sha256(
            raw_public
        ).hexdigest()
        _replace_provenance(payload, provenance)
    else:
        raise ValueError(f"unknown provenance fixture case: {case_id}")
    return payload


def build_provenance_cases() -> dict[str, dict[str, Any]]:
    passing_package = model_payload(signed_package())
    unsigned = model_payload(unsigned_package())
    cases: dict[str, dict[str, Any]] = {
        "pass-signed": {
            "case_id": "pass-signed",
            "expected_status": "pass",
            "verification_context": {"now": FIXTURE_NOW},
            "package": passing_package,
        },
        "unsigned-development": {
            "case_id": "unsigned-development",
            "expected_status": "fail",
            "expected_reasons": ["locally_signed", "public_key_fingerprint", "signature"],
            "verification_context": {"now": FIXTURE_NOW},
            "package": unsigned,
        },
        "expired": {
            "case_id": "expired",
            "expected_status": "fail",
            "expected_reasons": ["not_expired"],
            "verification_context": {"now": EXPIRED_NOW},
            "package": passing_package,
        },
        "revoked": {
            "case_id": "revoked",
            "expected_status": "fail",
            "expected_reasons": ["not_revoked"],
            "verification_context": {
                "now": FIXTURE_NOW,
                "revoked_handles": [
                    passing_package["receipt_provenance"]["revocation"]["handle"]
                ],
            },
            "package": passing_package,
        },
        "replay": {
            "case_id": "replay",
            "expected_first_status": "pass",
            "expected_second_status": "fail",
            "expected_second_reasons": ["replay_nonce_unused"],
            "verification_context": {"now": FIXTURE_NOW, "consume_nonce": True},
            "package": passing_package,
        },
    }
    for case_id in (
        "tampered-policy",
        "tampered-evidence",
        "tampered-reconstruction",
        "tampered-decision",
        "tampered-receipt",
        "tampered-signature",
        "wrong-public-key",
    ):
        cases[case_id] = {
            "case_id": case_id,
            "expected_status": "fail",
            "verification_context": {"now": FIXTURE_NOW},
            "package": _tamper_package(passing_package, case_id),
        }
    return cases


def fixture_outputs(root: Path) -> dict[Path, str]:
    fixture_dir = root / FIXTURE_ROOT
    return {
        fixture_dir / f"{case_id}.json": json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
        for case_id, payload in build_provenance_cases().items()
    }
