"""Deterministic intake for independently signed external-adopter attestations."""

from __future__ import annotations

from base64 import urlsafe_b64decode
import hashlib
from typing import Any

from study_anything.cbb.adoption.attestation_models import (
    AdoptionAttestationSourceClass,
    AdoptionAttestationState,
    ExternalAdoptionAttestationEnvelopeV1,
    ExternalAdoptionAttestationReceiptV1,
    ExternalAdoptionAttestationV1,
    ExternalAdoptionExpectedScopeV1,
)
from study_anything.cbb.protocol.canonical import canonical_json_bytes, canonical_sha256
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    parse_timestamp,
)


ADOPTION_ATTESTATION_NOT_CLAIMED = [
    "new delivery authority",
    "production approval",
    "automatic customer sending",
    "general customer outcome",
    "independent security audit completion",
    "model correctness",
    "external identity from signature possession alone",
    "real adopter evidence from a synthetic fixture",
]

# Public deterministic keys are useful for repeatable fixtures but can never be an
# external trust root. Keep this denylist in the verifier kernel, not in caller policy.
KNOWN_FIXTURE_PUBLIC_KEY_FINGERPRINTS = frozenset(
    {"a557e81b372a9ef9946de099c7f5470eb0826376e50e68fe153173f4ef09ae6f"}
)


def _privacy() -> PrivacyBoundaryV1:
    return PrivacyBoundaryV1(
        metadata_only=True,
        raw_source_text_included=False,
        raw_report_text_included=False,
        raw_customer_payload_included=False,
        attention_stream_included=False,
        model_prompts_included=False,
        model_credentials_included=False,
        cookies_or_bearer_tokens_included=False,
        signed_urls_included=False,
        production_mutation_performed=False,
        automatic_customer_send_performed=False,
    )


def _decode_base64url(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return urlsafe_b64decode(value + padding)
    except Exception as exc:  # noqa: BLE001 - normalize signature input failure.
        raise ValueError("invalid adoption-attestation signature encoding") from exc


def adoption_attestation_payload(attestation: ExternalAdoptionAttestationV1) -> bytes:
    return canonical_json_bytes(attestation.model_dump(mode="json"))


def adoption_attestation_digest(attestation: ExternalAdoptionAttestationV1) -> str:
    return canonical_sha256(attestation.model_dump(mode="json"))


def _verify_detached_signature(
    envelope: ExternalAdoptionAttestationEnvelopeV1,
) -> bool:
    signature = envelope.detached_signature
    payload = adoption_attestation_payload(envelope.attestation)
    digest = adoption_attestation_digest(envelope.attestation)
    if signature.signed_payload_sha256 != digest:
        return False
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        public_key_bytes = _decode_base64url(signature.public_key)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(_decode_base64url(signature.signature), payload)
    except (ImportError, InvalidSignature, ValueError):
        return False
    return True


def _public_key_fingerprint_valid(
    envelope: ExternalAdoptionAttestationEnvelopeV1,
) -> bool:
    try:
        public_key = _decode_base64url(envelope.detached_signature.public_key)
    except ValueError:
        return False
    return (
        hashlib.sha256(public_key).hexdigest()
        == envelope.detached_signature.public_key_fingerprint_sha256
    )


def _normalized_actor(value: Any) -> str:
    return str(value).strip().casefold()


def _trusted_identity_match(
    expected_scope: ExternalAdoptionExpectedScopeV1,
    envelope: ExternalAdoptionAttestationEnvelopeV1,
) -> bool:
    trust = envelope.adopter_trust
    return any(
        identity.organization_ref == trust.organization_ref
        and identity.human_observer_ref == trust.human_observer_ref
        and identity.public_key_fingerprint_sha256
        == trust.public_key_fingerprint_sha256
        and identity.independence_attestation_ref
        == trust.independence_attestation_ref
        for identity in expected_scope.trusted_adopters
    )


def adoption_attestation_ready_receipt(
    expected_scope: ExternalAdoptionExpectedScopeV1,
    *,
    evaluated_at: str,
) -> ExternalAdoptionAttestationReceiptV1:
    parse_timestamp(evaluated_at)
    digest = canonical_sha256(
        {
            "state": AdoptionAttestationState.ATTESTATION_READY.value,
            "expected_scope": expected_scope.model_dump(mode="json"),
            "evaluated_at": evaluated_at,
        }
    )
    return ExternalAdoptionAttestationReceiptV1(
        schema_version="cbb.external-adoption-attestation-receipt.v1",
        receipt_id=f"external-adoption-attestation:{digest[:32]}",
        state=AdoptionAttestationState.ATTESTATION_READY,
        source_class=None,
        binding=expected_scope.binding,
        attestation_digest_sha256=None,
        signature_verified=False,
        external_identity_attested=False,
        observation_execution_completed=False,
        real_adopter_evidence_accepted=False,
        checks={
            "pinned_scope_ready": True,
            "trusted_external_adopter_present": bool(
                expected_scope.trusted_adopters
            ),
            "external_attestation_present": False,
        },
        blocking_reasons=["external_signed_adoption_attestation_not_received"],
        next_required_actions=[
            "identify an independent external adopter",
            "pin the independently verified adopter identity and public-key fingerprint",
            "return a signed attestation bound to the exact adoption case and release scope",
        ],
        delivery_authority_granted=False,
        production_authority_granted=False,
        audit_completed=False,
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "The exact controlled-adoption case is ready to receive an external "
                "adopter attestation."
            ),
            maximum_scope=DeliveryScope.BLOCKED,
            not_claimed=ADOPTION_ATTESTATION_NOT_CLAIMED,
        ),
        privacy=_privacy(),
        evaluated_at=evaluated_at,
    )


def evaluate_external_adoption_attestation(
    expected_scope: ExternalAdoptionExpectedScopeV1,
    envelope: ExternalAdoptionAttestationEnvelopeV1,
    *,
    evaluated_at: str,
) -> ExternalAdoptionAttestationReceiptV1:
    """Validate signed observation evidence without granting release authority."""

    evaluated = parse_timestamp(evaluated_at)
    attestation = envelope.attestation
    expected_binding = expected_scope.binding
    observed_binding = attestation.binding
    submitted = parse_timestamp(envelope.submitted_at)
    completed = parse_timestamp(attestation.observation.completed_at)
    signature_verified = _verify_detached_signature(envelope)
    public_key_fingerprint_valid = _public_key_fingerprint_valid(envelope)
    trusted_identity_match = _trusted_identity_match(expected_scope, envelope)
    actors = {
        _normalized_actor(actor) for actor in expected_scope.repository_actor_refs
    }
    organization = _normalized_actor(envelope.adopter_trust.organization_ref)
    observer = _normalized_actor(envelope.adopter_trust.human_observer_ref)
    known_fixture_key = (
        envelope.detached_signature.public_key_fingerprint_sha256
        in KNOWN_FIXTURE_PUBLIC_KEY_FINGERPRINTS
    )
    external_identity_attested = (
        envelope.source_class
        == AdoptionAttestationSourceClass.EXTERNAL_ATTESTATION
        and envelope.adopter_trust.identity_status == "externally_attested"
        and envelope.adopter_trust.independent_from_repository
        and not envelope.adopter_trust.fixture_only
        and public_key_fingerprint_valid
        and trusted_identity_match
        and not known_fixture_key
    )
    checks = {
        "repository_matches": (
            observed_binding.repository == expected_binding.repository
        ),
        "release_scope_commit_matches": (
            observed_binding.release_scope_commit
            == expected_binding.release_scope_commit
        ),
        "protocol_version_matches": (
            observed_binding.protocol_version == expected_binding.protocol_version
        ),
        "conformance_pack_digest_matches": (
            observed_binding.conformance_pack_sha256
            == expected_binding.conformance_pack_sha256
        ),
        "source_package_digest_matches": (
            observed_binding.source_package_digest_sha256
            == expected_binding.source_package_digest_sha256
        ),
        "source_delivery_receipt_matches": (
            observed_binding.source_delivery_receipt_ref
            == expected_binding.source_delivery_receipt_ref
        ),
        "source_revocation_handle_matches": (
            observed_binding.source_clearance_revocation_handle
            == expected_binding.source_clearance_revocation_handle
        ),
        "source_approved_scope_matches": (
            observed_binding.source_approved_scope
            == expected_binding.source_approved_scope
        ),
        "adoption_case_id_matches": (
            observed_binding.adoption_case_id
            == expected_binding.adoption_case_id
        ),
        "adoption_case_digest_matches": (
            observed_binding.adoption_case_sha256
            == expected_binding.adoption_case_sha256
        ),
        "signature_reference_matches": (
            attestation.signature_ref == f"detached:{envelope.envelope_id}"
        ),
        "detached_signature_verified": signature_verified,
        "public_key_fingerprint_valid": public_key_fingerprint_valid,
        "signer_fingerprint_matches": (
            envelope.detached_signature.public_key_fingerprint_sha256
            == envelope.adopter_trust.public_key_fingerprint_sha256
        ),
        "source_identity_class_consistent": (
            envelope.source_class
            in {
                AdoptionAttestationSourceClass.SYNTHETIC_FIXTURE,
                AdoptionAttestationSourceClass.EXTERNAL_SHAPE_FIXTURE,
            }
            and envelope.adopter_trust.fixture_only
        )
        or external_identity_attested,
        "signer_trusted_for_source_class": (
            envelope.source_class
            != AdoptionAttestationSourceClass.EXTERNAL_ATTESTATION
            or trusted_identity_match
        ),
        "known_fixture_public_key_rejected": (
            envelope.source_class
            != AdoptionAttestationSourceClass.EXTERNAL_ATTESTATION
            or not known_fixture_key
        ),
        "repository_self_attestation_rejected": (
            organization not in actors and observer not in actors
        ),
        "submitted_after_observation": submitted >= completed,
        "evaluated_after_submission": evaluated >= submitted,
        "metadata_only": (
            envelope.privacy.metadata_only and attestation.privacy.metadata_only
        ),
        "no_production_mutation": (
            not envelope.privacy.production_mutation_performed
            and not attestation.privacy.production_mutation_performed
        ),
        "no_automatic_customer_send": (
            not envelope.privacy.automatic_customer_send_performed
            and not attestation.privacy.automatic_customer_send_performed
        ),
    }
    hard_failures = sorted(name for name, passed in checks.items() if not passed)

    if hard_failures:
        state = AdoptionAttestationState.REJECTED
        observation_completed = False
        real_evidence = False
        next_actions = ["correct rejected adoption-attestation evidence and resubmit"]
    elif envelope.source_class in {
        AdoptionAttestationSourceClass.SYNTHETIC_FIXTURE,
        AdoptionAttestationSourceClass.EXTERNAL_SHAPE_FIXTURE,
    }:
        state = AdoptionAttestationState.SYNTHETIC_VALIDATED
        observation_completed = False
        real_evidence = False
        next_actions = [
            "replace fixture-shaped evidence with an independently signed adopter attestation"
        ]
    else:
        state = AdoptionAttestationState.EXTERNAL_ATTESTATION_VERIFIED
        observation_completed = True
        real_evidence = True
        next_actions = [
            "submit this receipt with the exact matching case to the controlled-adoption evaluator"
        ]

    attestation_digest = adoption_attestation_digest(attestation)
    receipt_digest = canonical_sha256(
        {
            "expected_scope": expected_scope.model_dump(mode="json"),
            "envelope_id": envelope.envelope_id,
            "attestation_digest_sha256": attestation_digest,
            "state": state.value,
            "checks": checks,
            "evaluated_at": evaluated_at,
        }
    )
    return ExternalAdoptionAttestationReceiptV1(
        schema_version="cbb.external-adoption-attestation-receipt.v1",
        receipt_id=f"external-adoption-attestation:{receipt_digest[:32]}",
        state=state,
        source_class=envelope.source_class,
        binding=observed_binding,
        attestation_digest_sha256=attestation_digest,
        signature_verified=signature_verified,
        external_identity_attested=external_identity_attested,
        observation_execution_completed=observation_completed,
        real_adopter_evidence_accepted=real_evidence,
        checks=checks,
        blocking_reasons=hard_failures,
        next_required_actions=next_actions,
        delivery_authority_granted=False,
        production_authority_granted=False,
        audit_completed=False,
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "This receipt records whether a signed external-adopter observation can "
                "enter Controlled Adoption as identity- and case-bound evidence."
            ),
            maximum_scope=DeliveryScope.BLOCKED,
            not_claimed=ADOPTION_ATTESTATION_NOT_CLAIMED,
        ),
        privacy=_privacy(),
        evaluated_at=evaluated_at,
    )
