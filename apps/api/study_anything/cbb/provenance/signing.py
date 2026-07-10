"""Local Ed25519 signing and offline verification for CBB Protocol v1.

The signature proves possession of the embedded local public key and protects the
bound canonical objects from modification. It does not prove a third-party identity,
independent audit, customer outcome, or production authority.
"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import stat
from typing import Any, Iterable, Literal, Mapping, cast

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.kernel.gate import evaluate_gate
from study_anything.cbb.protocol.canonical import (
    CanonicalProtocolError,
    assert_safe_metadata,
    canonical_json_bytes,
    canonical_sha256,
)
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    DeliveryTrustReceiptV1,
    EvidenceBundleV1,
    GateDecisionV1,
    QualifiedReconstructionV1,
    ReceiptProvenanceV1,
    SignerIdentityV1,
    StrictProtocolModel,
    TrustPolicyV1,
    parse_timestamp,
    scope_is_at_most,
)


PACKAGE_SCHEMA_VERSION: Literal["cbb.offline-provenance-package.v1"] = (
    "cbb.offline-provenance-package.v1"
)
SIGNATURE_ALGORITHM: Literal["ed25519"] = "ed25519"
PUBLIC_KEY_ENCODING: Literal["ed25519-raw-base64url"] = "ed25519-raw-base64url"
LOCAL_IDENTITY_SCOPE: Literal["local_self_asserted"] = "local_self_asserted"
SIGNATURE_CLAIM = (
    "The local signature binds this policy, evidence bundle, qualified reconstruction, "
    "and gate decision."
)
SIGNATURE_NOT_CLAIMED = [
    "production approval",
    "third-party signer identity",
    "independent security audit completion",
    "customer outcome guarantee",
    "global revocation status outside the supplied registry",
    "archive byte-for-byte integrity",
    "concurrent replay prevention across processes",
    "trusted external time authority",
    "encrypted private-key storage",
    "scope beyond the deterministic gate decision",
]


class ProvenanceDependencyError(RuntimeError):
    """Raised when the optional cryptography dependency is unavailable."""


class ProvenanceKeyError(ValueError):
    """Raised when local key material is malformed or stored unsafely."""


class OfflineProvenancePackageV1(StrictProtocolModel):
    """Portable, metadata-only package whose trust objects can be verified offline."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["cbb.offline-provenance-package.v1"]
    package_id: str = Field(min_length=1, max_length=200)
    trust_policy: TrustPolicyV1
    evidence_bundle: EvidenceBundleV1
    qualified_reconstruction: QualifiedReconstructionV1
    gate_decision: GateDecisionV1
    delivery_trust_receipt: DeliveryTrustReceiptV1
    receipt_provenance: ReceiptProvenanceV1
    archive_digest_included: Literal[False]
    private_key_material_included: Literal[False]
    claim_boundary: ClaimBoundaryV1

    @model_validator(mode="after")
    def validate_refs_and_scope(self) -> OfflineProvenancePackageV1:
        if self.delivery_trust_receipt.provenance != self.receipt_provenance:
            raise ValueError("delivery receipt provenance must match package provenance")
        if self.gate_decision.policy_ref != self.trust_policy.policy_id:
            raise ValueError("gate decision policy reference mismatch")
        if self.gate_decision.evidence_bundle_ref != self.evidence_bundle.bundle_id:
            raise ValueError("gate decision evidence reference mismatch")
        if (
            self.gate_decision.reconstruction_ref
            != self.qualified_reconstruction.reconstruction_id
        ):
            raise ValueError("gate decision reconstruction reference mismatch")
        if self.delivery_trust_receipt.decision_ref != self.gate_decision.decision_id:
            raise ValueError("delivery receipt decision reference mismatch")
        receipt = self.delivery_trust_receipt
        decision = self.gate_decision
        if receipt.subject_ref != decision.subject_ref:
            raise ValueError("delivery receipt subject reference mismatch")
        if receipt.policy_ref != decision.policy_ref:
            raise ValueError("delivery receipt policy reference mismatch")
        if receipt.evidence_bundle_ref != decision.evidence_bundle_ref:
            raise ValueError("delivery receipt evidence reference mismatch")
        if receipt.reconstruction_ref != decision.reconstruction_ref:
            raise ValueError("delivery receipt reconstruction reference mismatch")
        if receipt.status != decision.status:
            raise ValueError("delivery receipt status mismatch")
        if receipt.approved_scope != decision.approved_scope:
            raise ValueError("delivery receipt scope mismatch")
        if receipt.reasons != decision.reasons:
            raise ValueError("delivery receipt reasons mismatch")
        if not scope_is_at_most(
            self.claim_boundary.maximum_scope,
            self.gate_decision.approved_scope,
        ):
            raise ValueError("offline package claim boundary expands gate scope")
        if not scope_is_at_most(
            self.claim_boundary.maximum_scope,
            self.receipt_provenance.claim_boundary.maximum_scope,
        ):
            raise ValueError("offline package claim boundary expands signer scope")
        return self


@dataclass(frozen=True)
class ProvenanceVerification:
    status: Literal["pass", "fail"]
    checks: Mapping[str, bool]
    reasons: tuple[str, ...]
    signing_status: str
    approved_scope: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def _crypto_types() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:
        raise ProvenanceDependencyError(
            "local signing requires the optional 'crypto' dependency: "
            "python -m pip install -e '.[crypto]'"
        ) from exc
    return (
        InvalidSignature,
        serialization,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        serialization.NoEncryption,
    )


def _b64url_encode(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return urlsafe_b64decode(value + padding)
    except Exception as exc:  # noqa: BLE001 - normalize decoder failures.
        raise ValueError("invalid base64url value") from exc


def _public_key_bytes(private_key: Any) -> bytes:
    _, serialization, _, _, _ = _crypto_types()
    return cast(
        bytes,
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )


def generate_private_key(path: Path, *, overwrite: bool = False) -> None:
    """Generate a raw local Ed25519 private key with owner-only permissions."""

    _, serialization, Ed25519PrivateKey, _, NoEncryption = _crypto_types()
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing key: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    if path.exists():
        path.unlink()
    file_descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        stat.S_IRUSR | stat.S_IWUSR,
    )
    try:
        with os.fdopen(file_descriptor, "wb") as key_file:
            key_file.write(raw)
    finally:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_private_key(path: Path) -> Any:
    """Load an owner-only raw Ed25519 private key."""

    _, _, Ed25519PrivateKey, _, _ = _crypto_types()
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ProvenanceKeyError("private key permissions must be owner-only (0600)")
    raw = path.read_bytes()
    if len(raw) != 32:
        raise ProvenanceKeyError("Ed25519 private key must contain exactly 32 raw bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def package_binding(
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    decision: GateDecisionV1,
    receipt: DeliveryTrustReceiptV1,
) -> dict[str, str]:
    return {
        "policy_digest_sha256": canonical_sha256(policy),
        "evidence_digest_sha256": canonical_sha256(evidence_bundle),
        "reconstruction_digest_sha256": canonical_sha256(reconstruction),
        "decision_digest_sha256": canonical_sha256(decision),
        "receipt_envelope_digest_sha256": receipt_envelope_digest(receipt),
    }


def package_digest(binding: Mapping[str, str]) -> str:
    return canonical_sha256(dict(binding))


def receipt_envelope_digest(receipt: DeliveryTrustReceiptV1) -> str:
    payload = receipt.model_dump(mode="json")
    payload.pop("provenance")
    return canonical_sha256(payload)


def _signature_payload(provenance: ReceiptProvenanceV1 | Mapping[str, Any]) -> bytes:
    if isinstance(provenance, ReceiptProvenanceV1):
        payload = provenance.model_dump(mode="json")
    else:
        payload = dict(provenance)
    payload.pop("signature", None)
    return canonical_json_bytes(payload)


def _assert_unsigned_bindings(
    provenance: ReceiptProvenanceV1,
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    decision: GateDecisionV1,
    receipt: DeliveryTrustReceiptV1,
) -> None:
    if provenance.signing_status != "unsigned_development":
        raise ValueError("signing requires unsigned development provenance")
    binding = package_binding(
        policy,
        evidence_bundle,
        reconstruction,
        decision,
        receipt,
    )
    expected = {
        **binding,
        "package_digest_sha256": package_digest(binding),
        "subject_digest_sha256": canonical_sha256({"subject_ref": policy.subject_ref}),
    }
    actual = provenance.model_dump(mode="json")
    mismatches = sorted(key for key, value in expected.items() if actual.get(key) != value)
    if mismatches:
        raise ValueError(f"unsigned provenance digest mismatch: {mismatches}")


def sign_provenance(
    provenance: ReceiptProvenanceV1,
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    decision: GateDecisionV1,
    receipt: DeliveryTrustReceiptV1,
    private_key: Any,
    *,
    signer_id: str,
    key_id: str,
    maximum_scope: DeliveryScope | None = None,
) -> ReceiptProvenanceV1:
    """Sign canonical bindings without granting authority above the gate decision."""

    _assert_unsigned_bindings(
        provenance,
        policy,
        evidence_bundle,
        reconstruction,
        decision,
        receipt,
    )
    scope = maximum_scope or decision.approved_scope
    if not scope_is_at_most(scope, decision.approved_scope):
        raise ValueError("local signature cannot expand the deterministic gate scope")
    public_key = _public_key_bytes(private_key)
    signer = SignerIdentityV1(
        signer_id=signer_id,
        key_id=key_id,
        identity_scope=LOCAL_IDENTITY_SCOPE,
        public_key_encoding=PUBLIC_KEY_ENCODING,
        public_key=_b64url_encode(public_key),
        public_key_fingerprint_sha256=hashlib.sha256(public_key).hexdigest(),
    )
    payload = provenance.model_dump(mode="json")
    payload.update(
        {
            "signing_status": "locally_signed",
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "signature": _b64url_encode(bytes(64)),
            "signer": signer.model_dump(mode="json"),
            "claim_boundary": ClaimBoundaryV1(
                current_claim=SIGNATURE_CLAIM,
                maximum_scope=scope,
                not_claimed=SIGNATURE_NOT_CLAIMED,
            ).model_dump(mode="json"),
        }
    )
    signature = private_key.sign(_signature_payload(payload))
    payload["signature"] = _b64url_encode(signature)
    return ReceiptProvenanceV1.model_validate(payload)


def build_offline_package(
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    decision: GateDecisionV1,
    receipt: DeliveryTrustReceiptV1,
    provenance: ReceiptProvenanceV1,
) -> OfflineProvenancePackageV1:
    signed_receipt_payload = receipt.model_dump(mode="json")
    signed_receipt_payload["provenance"] = provenance.model_dump(mode="json")
    signed_receipt = DeliveryTrustReceiptV1.model_validate(signed_receipt_payload)
    portable = provenance.signing_status == "locally_signed"
    package_scope = (
        provenance.claim_boundary.maximum_scope if portable else DeliveryScope.BLOCKED
    )
    package_claim = (
        "This metadata-only package can be verified offline against its embedded "
        "local public key and deterministic CBB gate."
        if portable
        else "This unsigned development package carries no portable delivery authority."
    )
    return OfflineProvenancePackageV1(
        schema_version=PACKAGE_SCHEMA_VERSION,
        package_id=f"cbb-offline-package:{decision.decision_id}",
        trust_policy=policy,
        evidence_bundle=evidence_bundle,
        qualified_reconstruction=reconstruction,
        gate_decision=decision,
        delivery_trust_receipt=signed_receipt,
        receipt_provenance=provenance,
        archive_digest_included=False,
        private_key_material_included=False,
        claim_boundary=ClaimBoundaryV1(
            current_claim=package_claim,
            maximum_scope=package_scope,
            not_claimed=SIGNATURE_NOT_CLAIMED,
        ),
    )


def _coerce_now(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("verification time must be timezone-aware")
        return value.astimezone(timezone.utc)
    return parse_timestamp(value)


def verify_offline_package(
    package: OfflineProvenancePackageV1,
    *,
    now: datetime | str | None = None,
    revoked_handles: Iterable[str] = (),
    seen_nonces: set[str] | None = None,
    consume_nonce: bool = False,
) -> ProvenanceVerification:
    """Verify digests, gate replay, signature, time, revocation, and optional replay use."""

    provenance = package.receipt_provenance
    try:
        assert_safe_metadata(
            package.model_dump(mode="json"),
            label="OfflineProvenancePackageV1",
        )
    except CanonicalProtocolError:
        return ProvenanceVerification(
            status="fail",
            checks={"safe_metadata": False},
            reasons=("safe_metadata",),
            signing_status=provenance.signing_status,
            approved_scope=DeliveryScope.BLOCKED.value,
        )
    checks: dict[str, bool] = {}
    checks["safe_metadata"] = True
    binding = package_binding(
        package.trust_policy,
        package.evidence_bundle,
        package.qualified_reconstruction,
        package.gate_decision,
        package.delivery_trust_receipt,
    )
    checks.update(
        {
            "subject_digest": provenance.subject_digest_sha256
            == canonical_sha256({"subject_ref": package.trust_policy.subject_ref}),
            "policy_digest": provenance.policy_digest_sha256
            == binding["policy_digest_sha256"],
            "evidence_digest": provenance.evidence_digest_sha256
            == binding["evidence_digest_sha256"],
            "reconstruction_digest": provenance.reconstruction_digest_sha256
            == binding["reconstruction_digest_sha256"],
            "decision_digest": provenance.decision_digest_sha256
            == binding["decision_digest_sha256"],
            "receipt_envelope_digest": provenance.receipt_envelope_digest_sha256
            == binding["receipt_envelope_digest_sha256"],
            "package_digest": provenance.package_digest_sha256
            == package_digest(binding),
            "embedded_provenance": package.delivery_trust_receipt.provenance == provenance,
            "verifier_digest": provenance.verifier.verifier_digest_sha256
            == canonical_sha256(
                {
                    "verifier_id": provenance.verifier.verifier_id,
                    "verifier_version": provenance.verifier.verifier_version,
                }
            ),
            "receipt_status": package.delivery_trust_receipt.status
            == package.gate_decision.status,
            "receipt_scope": package.delivery_trust_receipt.approved_scope
            == package.gate_decision.approved_scope,
            "scope_not_expanded": scope_is_at_most(
                provenance.claim_boundary.maximum_scope,
                package.gate_decision.approved_scope,
            ),
        }
    )
    expected_decision = evaluate_gate(
        package.trust_policy,
        package.evidence_bundle,
        package.qualified_reconstruction,
        decided_at=package.gate_decision.decided_at,
    )
    checks["deterministic_gate"] = expected_decision == package.gate_decision

    current_time = _coerce_now(now)
    checks["not_before"] = current_time >= parse_timestamp(provenance.created_at)
    checks["not_expired"] = current_time < parse_timestamp(provenance.expires_at)
    checks["not_revoked"] = provenance.revocation.handle not in set(revoked_handles)

    checks["locally_signed"] = provenance.signing_status == "locally_signed"
    checks["public_key_fingerprint"] = False
    checks["signature"] = False
    if provenance.signer is not None and provenance.signature is not None:
        public_key_bytes = _b64url_decode(provenance.signer.public_key)
        checks["public_key_fingerprint"] = (
            hashlib.sha256(public_key_bytes).hexdigest()
            == provenance.signer.public_key_fingerprint_sha256
        )
        try:
            InvalidSignature, _, _, Ed25519PublicKey, _ = _crypto_types()
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(
                _b64url_decode(provenance.signature),
                _signature_payload(provenance),
            )
        except (ValueError, InvalidSignature):
            checks["signature"] = False
        else:
            checks["signature"] = True

    if consume_nonce:
        if seen_nonces is None:
            raise ValueError("consume_nonce requires a mutable seen_nonces set")
        checks["replay_nonce_unused"] = provenance.replay_nonce not in seen_nonces
        if checks["replay_nonce_unused"] and all(checks.values()):
            seen_nonces.add(provenance.replay_nonce)
    else:
        checks["replay_nonce_unused"] = True

    reasons = tuple(sorted(name for name, passed in checks.items() if not passed))
    return ProvenanceVerification(
        status="pass" if not reasons else "fail",
        checks=checks,
        reasons=reasons,
        signing_status=provenance.signing_status,
        approved_scope=package.claim_boundary.maximum_scope.value,
    )
