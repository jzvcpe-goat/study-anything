"""Local signing and offline verification for post-delivery outcome receipts."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Iterable, Literal, Mapping, cast

from study_anything.cbb.outcomes.policy import derive_trust_update
from study_anything.cbb.protocol.canonical import (
    CanonicalProtocolError,
    assert_safe_metadata,
    canonical_json_bytes,
    canonical_sha256,
)
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryOutcomeReceiptV1,
    DeliveryScope,
    OutcomeReceiptProvenanceV1,
    RevocationReferenceV1,
    SignerIdentityV1,
    VerifierIdentityV1,
    parse_timestamp,
    scope_is_at_most,
)
from study_anything.cbb.provenance.signing import (
    OfflineProvenancePackageV1,
    verify_offline_package,
)


OUTCOME_VERIFIER_ID = "delivery-clearance-outcome-evaluator"
OUTCOME_VERIFIER_VERSION = "1"
OUTCOME_SIGNATURE_NOT_CLAIMED = [
    "third-party signer identity",
    "customer outcome guarantee",
    "production approval",
    "legal or security certification",
    "global revocation status outside the supplied registry",
    "scope beyond the deterministic outcome action",
]


@dataclass(frozen=True)
class OutcomeReceiptVerification:
    status: Literal["pass", "fail"]
    checks: Mapping[str, bool]
    reasons: tuple[str, ...]
    resulting_scope: str

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
    provenance: OutcomeReceiptProvenanceV1 | Mapping[str, Any],
) -> bytes:
    payload = (
        provenance.model_dump(mode="json")
        if isinstance(provenance, OutcomeReceiptProvenanceV1)
        else dict(provenance)
    )
    payload.pop("signature", None)
    return canonical_json_bytes(payload)


def sign_outcome_envelope(
    envelope: Mapping[str, Any],
    *,
    source_package_digest_sha256: str,
    private_key: Any,
    signer_id: str,
    key_id: str,
    created_at: str,
    expires_at: str,
    replay_nonce: str,
    outcome_receipt_id: str,
    maximum_scope: DeliveryScope,
) -> OutcomeReceiptProvenanceV1:
    """Sign the canonical outcome envelope without granting additional scope."""

    assert_safe_metadata(envelope, label="delivery outcome envelope")
    public_key = _public_key_bytes(private_key)
    verifier_digest = canonical_sha256(
        {
            "verifier_id": OUTCOME_VERIFIER_ID,
            "verifier_version": OUTCOME_VERIFIER_VERSION,
        }
    )
    payload: dict[str, Any] = {
        "outcome_envelope_digest_sha256": canonical_sha256(envelope),
        "source_package_digest_sha256": source_package_digest_sha256,
        "verifier": VerifierIdentityV1(
            verifier_id=OUTCOME_VERIFIER_ID,
            verifier_version=OUTCOME_VERIFIER_VERSION,
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
            handle=f"cbb-outcome-revocation:{outcome_receipt_id}",
            registry_ref="outcome-revocation-registry.json",
        ).model_dump(mode="json"),
        "claim_boundary": ClaimBoundaryV1(
            current_claim=(
                "The local signature binds this deterministic post-delivery outcome "
                "receipt and cannot expand its resulting scope."
            ),
            maximum_scope=maximum_scope,
            not_claimed=OUTCOME_SIGNATURE_NOT_CLAIMED,
        ).model_dump(mode="json"),
    }
    payload["signature"] = _b64url_encode(private_key.sign(_signature_payload(payload)))
    return OutcomeReceiptProvenanceV1.model_validate(payload)


def outcome_envelope_payload(receipt: DeliveryOutcomeReceiptV1) -> dict[str, Any]:
    payload = receipt.model_dump(mode="json")
    payload.pop("outcome_provenance")
    return payload


def verify_outcome_source_binding(
    package: OfflineProvenancePackageV1,
    receipt: DeliveryOutcomeReceiptV1,
) -> tuple[str, ...]:
    """Return deterministic source-binding mismatches without trusting receipt prose."""

    source_receipt = package.delivery_trust_receipt
    expected = {
        "source_delivery_receipt_ref": source_receipt.receipt_id,
        "source_delivery_receipt_digest_sha256": canonical_sha256(source_receipt),
        "source_clearance_revocation_handle": (package.receipt_provenance.revocation.handle),
        "subject_ref": source_receipt.subject_ref,
        "policy_ref": source_receipt.policy_ref,
        "scenario_ref": package.trust_policy.scenario_ref,
        "source_approved_scope": source_receipt.approved_scope,
        "package_ref": package.package_id,
        "package_digest_sha256": package.receipt_provenance.package_digest_sha256,
    }
    actual = {
        "source_delivery_receipt_ref": receipt.source_delivery_receipt_ref,
        "source_delivery_receipt_digest_sha256": (receipt.source_delivery_receipt_digest_sha256),
        "source_clearance_revocation_handle": (receipt.source_clearance_revocation_handle),
        "subject_ref": receipt.subject_ref,
        "policy_ref": receipt.policy_ref,
        "scenario_ref": receipt.scenario_ref,
        "source_approved_scope": receipt.source_approved_scope,
        "package_ref": receipt.source_verification.package_ref,
        "package_digest_sha256": (receipt.source_verification.package_digest_sha256),
    }
    return tuple(sorted(key for key, value in expected.items() if actual[key] != value))


def _coerce_now(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("outcome verification time must be timezone-aware")
        return value.astimezone(timezone.utc)
    return parse_timestamp(value)


def verify_outcome_receipt(
    package: OfflineProvenancePackageV1,
    receipt: DeliveryOutcomeReceiptV1,
    *,
    now: datetime | str | None = None,
    revoked_source_handles: Iterable[str] = (),
    revoked_outcome_handles: Iterable[str] = (),
) -> OutcomeReceiptVerification:
    """Verify source package, source binding, outcome envelope, time, and signature."""

    provenance = receipt.outcome_provenance
    checks: dict[str, bool] = {}
    try:
        assert_safe_metadata(receipt.model_dump(mode="json"), label="outcome receipt")
    except CanonicalProtocolError:
        return OutcomeReceiptVerification(
            status="fail",
            checks={"safe_metadata": False},
            reasons=("safe_metadata",),
            resulting_scope=DeliveryScope.BLOCKED.value,
        )
    checks["safe_metadata"] = True
    source = verify_offline_package(
        package,
        now=receipt.source_verification.clearance_valid_at,
        revoked_handles=revoked_source_handles,
    )
    checks["source_package"] = source.passed
    checks["source_binding"] = not verify_outcome_source_binding(package, receipt)
    checks["source_clearance_anchor"] = (
        receipt.source_verification.clearance_valid_at == package.receipt_provenance.created_at
    )
    checks["source_check_set"] = set(receipt.source_verification.checks_passed) == {
        name for name, passed in source.checks.items() if passed
    }
    checks["source_package_digest"] = (
        provenance.source_package_digest_sha256 == package.receipt_provenance.package_digest_sha256
    )
    checks["outcome_envelope_digest"] = (
        provenance.outcome_envelope_digest_sha256
        == canonical_sha256(outcome_envelope_payload(receipt))
    )
    checks["verifier_digest"] = provenance.verifier.verifier_digest_sha256 == canonical_sha256(
        {
            "verifier_id": provenance.verifier.verifier_id,
            "verifier_version": provenance.verifier.verifier_version,
        }
    )
    checks["verifier_identity"] = (
        provenance.verifier.verifier_id == OUTCOME_VERIFIER_ID
        and provenance.verifier.verifier_version == OUTCOME_VERIFIER_VERSION
    )
    expected_update, expected_status = derive_trust_update(
        receipt.source_approved_scope,
        receipt.events,
        receipt.rollback,
        recipe_ref=receipt.trust_update.recipe_ref,
        source_revocation_handle=receipt.source_clearance_revocation_handle,
    )
    checks["deterministic_trust_update"] = (
        receipt.trust_update == expected_update and receipt.status == expected_status
    )
    checks["scope_not_expanded"] = scope_is_at_most(
        provenance.claim_boundary.maximum_scope,
        receipt.trust_update.resulting_scope,
    )
    current_time = _coerce_now(now)
    checks["not_before"] = current_time >= parse_timestamp(provenance.created_at)
    checks["not_expired"] = current_time < parse_timestamp(provenance.expires_at)
    checks["not_revoked"] = provenance.revocation.handle not in set(revoked_outcome_handles)
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
    return OutcomeReceiptVerification(
        status="pass" if not reasons else "fail",
        checks=checks,
        reasons=reasons,
        resulting_scope=(
            receipt.trust_update.resulting_scope.value
            if not reasons
            else DeliveryScope.BLOCKED.value
        ),
    )
