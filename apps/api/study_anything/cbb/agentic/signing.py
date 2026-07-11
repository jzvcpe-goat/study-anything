"""Local signing and deterministic verification for evolution-gate receipts."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable, Literal, Mapping, cast

from study_anything.cbb.agentic.policy import evaluate_evolution_gate
from study_anything.cbb.protocol.canonical import (
    CanonicalProtocolError,
    assert_safe_metadata,
    canonical_json_bytes,
    canonical_sha256,
)
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    EvolutionDecisionStatus,
    EvolutionGateDecisionV1,
    EvolutionGateReceiptV1,
    EvolutionReceiptProvenanceV1,
    RevocationReferenceV1,
    SignerIdentityV1,
    VerifierIdentityV1,
    parse_timestamp,
)


EVOLUTION_VERIFIER_ID = "delivery-clearance-evolution-gate"
EVOLUTION_VERIFIER_VERSION = "1"
EVOLUTION_NOT_CLAIMED = [
    "third-party signer identity",
    "automatic policy application",
    "production authorization",
    "global protocol conformance",
    "independent security audit completion",
    "model or memory output as a trust root",
]


@dataclass(frozen=True)
class EvolutionReceiptVerification:
    status: Literal["pass", "fail"]
    checks: Mapping[str, bool]
    reasons: tuple[str, ...]
    candidate_state: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _b64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return urlsafe_b64decode(value + padding)


def _public_key_bytes(private_key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization

    return cast(
        bytes,
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )


def _signature_payload(
    provenance: EvolutionReceiptProvenanceV1 | Mapping[str, Any],
) -> bytes:
    payload = (
        provenance.model_dump(mode="json")
        if isinstance(provenance, EvolutionReceiptProvenanceV1)
        else dict(provenance)
    )
    payload.pop("signature", None)
    return canonical_json_bytes(payload)


def sign_evolution_envelope(
    envelope: Mapping[str, Any],
    decision: EvolutionGateDecisionV1,
    *,
    private_key: Any,
    signer_id: str,
    key_id: str,
    created_at: str,
    expires_at: str,
    replay_nonce: str,
    evolution_receipt_id: str,
) -> EvolutionReceiptProvenanceV1:
    """Sign a decision that carries no delivery or automatic-apply authority."""

    assert_safe_metadata(envelope, label="evolution gate envelope")
    public_key = _public_key_bytes(private_key)
    verifier_digest = canonical_sha256(
        {
            "verifier_id": EVOLUTION_VERIFIER_ID,
            "verifier_version": EVOLUTION_VERIFIER_VERSION,
        }
    )
    payload: dict[str, Any] = {
        "envelope_digest_sha256": canonical_sha256(envelope),
        "decision_digest_sha256": canonical_sha256(decision),
        "verifier": VerifierIdentityV1(
            verifier_id=EVOLUTION_VERIFIER_ID,
            verifier_version=EVOLUTION_VERIFIER_VERSION,
            verifier_digest_sha256=verifier_digest,
        ).model_dump(mode="json"),
        "canonicalization": "cbb-json-c14n-v1",
        "signing_status": "locally_signed",
        "signature_algorithm": "ed25519",
        "signature": _b64url_encode(bytes(64)),
        "signer": SignerIdentityV1(
            signer_id=signer_id,
            key_id=key_id,
            identity_scope="local_self_asserted",
            public_key_encoding="ed25519-raw-base64url",
            public_key=_b64url_encode(public_key),
            public_key_fingerprint_sha256=hashlib.sha256(public_key).hexdigest(),
        ).model_dump(mode="json"),
        "created_at": created_at,
        "expires_at": expires_at,
        "replay_nonce": replay_nonce,
        "revocation": RevocationReferenceV1(
            handle=f"cbb-evolution-revocation:{evolution_receipt_id}",
            registry_ref="evolution-revocation-registry.json",
        ).model_dump(mode="json"),
        "claim_boundary": ClaimBoundaryV1(
            current_claim=(
                "The local signature binds this deterministic evolution-gate receipt. "
                "The receipt does not apply the candidate."
            ),
            maximum_scope=DeliveryScope.BLOCKED,
            not_claimed=EVOLUTION_NOT_CLAIMED,
        ).model_dump(mode="json"),
    }
    payload["signature"] = _b64url_encode(private_key.sign(_signature_payload(payload)))
    return EvolutionReceiptProvenanceV1.model_validate(payload)


def evolution_envelope_payload(receipt: EvolutionGateReceiptV1) -> dict[str, Any]:
    payload = receipt.model_dump(mode="json")
    payload.pop("provenance")
    return payload


def _coerce_now(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evolution verification time must be timezone-aware")
        return value.astimezone(timezone.utc)
    return parse_timestamp(value)


def verify_evolution_receipt(
    receipt: EvolutionGateReceiptV1,
    *,
    now: datetime | str | None = None,
    revoked_handles: Iterable[str] = (),
) -> EvolutionReceiptVerification:
    """Verify signature and replay the deterministic gate over embedded evidence."""

    provenance = receipt.provenance
    checks: dict[str, bool] = {}
    try:
        assert_safe_metadata(receipt.model_dump(mode="json"), label="evolution receipt")
    except CanonicalProtocolError:
        return EvolutionReceiptVerification(
            status="fail",
            checks={"safe_metadata": False},
            reasons=("safe_metadata",),
            candidate_state="rejected",
        )
    checks["safe_metadata"] = True
    checks["envelope_digest"] = (
        provenance.envelope_digest_sha256
        == canonical_sha256(evolution_envelope_payload(receipt))
    )
    checks["decision_digest"] = (
        provenance.decision_digest_sha256 == canonical_sha256(receipt.decision)
    )
    checks["verifier_digest"] = provenance.verifier.verifier_digest_sha256 == canonical_sha256(
        {
            "verifier_id": provenance.verifier.verifier_id,
            "verifier_version": provenance.verifier.verifier_version,
        }
    )
    checks["verifier_identity"] = (
        provenance.verifier.verifier_id == EVOLUTION_VERIFIER_ID
        and provenance.verifier.verifier_version == EVOLUTION_VERIFIER_VERSION
    )
    expected_decision = evaluate_evolution_gate(
        receipt.proposal,
        receipt.agentic_evidence,
        receipt.controls,
    )
    checks["deterministic_gate"] = expected_decision == receipt.decision
    checks["proposal_not_final_authority"] = (
        receipt.agentic_evidence.agentic_output_authority == "supporting_evidence_only"
        and not receipt.decision.tool_or_memory_authority_used_as_final_basis
    )
    checks["no_self_authorization"] = (
        receipt.decision.status != EvolutionDecisionStatus.APPROVED_FOR_LOCAL_CANDIDATE
        or receipt.provenance.signer.signer_id != receipt.proposal.proposer_ref
    )
    current_time = _coerce_now(now)
    checks["not_before"] = current_time >= parse_timestamp(provenance.created_at)
    checks["not_expired"] = current_time < parse_timestamp(provenance.expires_at)
    checks["not_revoked"] = provenance.revocation.handle not in set(revoked_handles)
    public_key_bytes = _b64url_decode(provenance.signer.public_key)
    checks["public_key_fingerprint"] = (
        hashlib.sha256(public_key_bytes).hexdigest()
        == provenance.signer.public_key_fingerprint_sha256
    )
    checks["signature"] = False
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
            _b64url_decode(provenance.signature),
            _signature_payload(provenance),
        )
    except (InvalidSignature, ValueError):
        checks["signature"] = False
    else:
        checks["signature"] = True
    reasons = tuple(sorted(name for name, passed in checks.items() if not passed))
    return EvolutionReceiptVerification(
        status="pass" if not reasons else "fail",
        checks=checks,
        reasons=reasons,
        candidate_state=receipt.decision.candidate_state if not reasons else "rejected",
    )
