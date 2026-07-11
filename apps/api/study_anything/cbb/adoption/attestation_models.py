"""Strict contracts for independently signed external-adopter attestations."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.adoption.models import (
    AdoptionMode,
    AdoptionObservationKind,
)
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    StrictProtocolModel,
    parse_timestamp,
)


EXTERNAL_ADOPTION_ATTESTATION_ENVELOPE_SCHEMA_VERSION: Literal[
    "cbb.external-adoption-attestation-envelope.v1"
] = "cbb.external-adoption-attestation-envelope.v1"
EXTERNAL_ADOPTION_ATTESTATION_RECEIPT_SCHEMA_VERSION: Literal[
    "cbb.external-adoption-attestation-receipt.v1"
] = "cbb.external-adoption-attestation-receipt.v1"
Sha256Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AdoptionAttestationSourceClass(StrEnum):
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    EXTERNAL_SHAPE_FIXTURE = "external_shape_fixture"
    EXTERNAL_ATTESTATION = "external_attestation"


class AdoptionAttestationState(StrEnum):
    ATTESTATION_READY = "attestation_ready"
    REJECTED = "rejected"
    SYNTHETIC_VALIDATED = "synthetic_validated"
    EXTERNAL_ATTESTATION_VERIFIED = "external_attestation_verified"


class ExternalAdoptionAttestationBindingV1(StrictProtocolModel):
    repository: Literal["jzvcpe-goat/study-anything"]
    release_scope_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    protocol_version: Literal["1.0.0"]
    conformance_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_package_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_delivery_receipt_ref: str = Field(min_length=1, max_length=500)
    source_clearance_revocation_handle: str = Field(min_length=1, max_length=200)
    source_approved_scope: DeliveryScope
    adoption_case_id: str = Field(min_length=1, max_length=160)
    adoption_case_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExternalAdoptionObservationV1(StrictProtocolModel):
    observed_at: str = Field(min_length=1, max_length=64)
    completed_at: str = Field(min_length=1, max_length=64)
    observed_delivery_count: int = Field(ge=1)
    adverse_event_count: int = Field(ge=0)
    rollback_exercised: bool
    revocation_exercised: bool

    @model_validator(mode="after")
    def validate_observation_period(self) -> ExternalAdoptionObservationV1:
        if parse_timestamp(self.completed_at) <= parse_timestamp(self.observed_at):
            raise ValueError("external adoption completion must follow observation start")
        return self


class ExternalAdoptionAttestationV1(StrictProtocolModel):
    binding: ExternalAdoptionAttestationBindingV1
    adoption_mode: AdoptionMode
    observation_kind: AdoptionObservationKind
    requested_scope: DeliveryScope
    outcome_receipt_ref: str | None = Field(default=None, max_length=500)
    observation: ExternalAdoptionObservationV1
    signature_ref: str = Field(min_length=3, max_length=240)
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_external_observation(self) -> ExternalAdoptionAttestationV1:
        if self.adoption_mode != AdoptionMode.CANARY:
            raise ValueError("external adopter attestation is limited to bounded canary mode")
        if self.observation_kind in {
            AdoptionObservationKind.INCIDENT,
            AdoptionObservationKind.ROLLBACK,
            AdoptionObservationKind.REVOCATION,
        } and self.outcome_receipt_ref is None:
            raise ValueError("adverse external observation requires an outcome receipt ref")
        if (
            self.observation_kind == AdoptionObservationKind.PASS
            and self.observation.adverse_event_count != 0
        ):
            raise ValueError("passing external observation cannot report adverse events")
        if (
            self.observation_kind == AdoptionObservationKind.INCIDENT
            and self.observation.adverse_event_count < 1
        ):
            raise ValueError("incident observation requires an adverse event")
        if (
            self.observation_kind == AdoptionObservationKind.ROLLBACK
            and not self.observation.rollback_exercised
        ):
            raise ValueError("rollback observation must record rollback exercise")
        if (
            self.observation_kind == AdoptionObservationKind.REVOCATION
            and not self.observation.revocation_exercised
        ):
            raise ValueError("revocation observation must record revocation exercise")
        if self.privacy.production_mutation_performed:
            raise ValueError("external adoption attestation cannot record production mutation")
        if self.privacy.automatic_customer_send_performed:
            raise ValueError("external adoption attestation cannot record automatic sending")
        return self


class AdoptionDetachedSignatureV1(StrictProtocolModel):
    algorithm: Literal["ed25519"]
    public_key_encoding: Literal["ed25519-raw-base64url"]
    public_key: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    public_key_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signed_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{86}$")


class AdopterTrustRecordV1(StrictProtocolModel):
    organization_ref: str = Field(min_length=3, max_length=240)
    human_observer_ref: str = Field(min_length=3, max_length=240)
    public_key_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_status: Literal["synthetic_fixture", "externally_attested"]
    independence_attestation_ref: str = Field(min_length=3, max_length=500)
    independent_from_repository: bool
    fixture_only: bool

    @model_validator(mode="after")
    def validate_identity_state(self) -> AdopterTrustRecordV1:
        if self.identity_status == "synthetic_fixture":
            if not self.fixture_only or self.independent_from_repository:
                raise ValueError("synthetic adopter identity cannot claim external independence")
        elif self.fixture_only or not self.independent_from_repository:
            raise ValueError("external adopter identity requires independent attestation")
        return self


class TrustedAdopterIdentityV1(StrictProtocolModel):
    organization_ref: str = Field(min_length=3, max_length=240)
    human_observer_ref: str = Field(min_length=3, max_length=240)
    public_key_fingerprint_sha256: Sha256Fingerprint
    independence_attestation_ref: str = Field(min_length=3, max_length=500)


class ExternalAdoptionExpectedScopeV1(StrictProtocolModel):
    binding: ExternalAdoptionAttestationBindingV1
    trusted_adopters: list[TrustedAdopterIdentityV1] = Field(default_factory=list)
    repository_actor_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_expected_scope(self) -> ExternalAdoptionExpectedScopeV1:
        fingerprints = [
            identity.public_key_fingerprint_sha256
            for identity in self.trusted_adopters
        ]
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("trusted adopter fingerprints must be unique")
        identities = [
            (identity.organization_ref, identity.human_observer_ref)
            for identity in self.trusted_adopters
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("trusted adopter identities must be unique")
        return self


class ExternalAdoptionAttestationEnvelopeV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": EXTERNAL_ADOPTION_ATTESTATION_ENVELOPE_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.external-adoption-attestation-envelope.v1"]
    envelope_id: str = Field(min_length=1, max_length=200)
    source_class: AdoptionAttestationSourceClass
    attestation: ExternalAdoptionAttestationV1
    detached_signature: AdoptionDetachedSignatureV1
    adopter_trust: AdopterTrustRecordV1
    submitted_at: str = Field(min_length=1, max_length=64)
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_envelope(self) -> ExternalAdoptionAttestationEnvelopeV1:
        parse_timestamp(self.submitted_at)
        if (
            self.detached_signature.public_key_fingerprint_sha256
            != self.adopter_trust.public_key_fingerprint_sha256
        ):
            raise ValueError("adoption signer fingerprint does not match trust record")
        if self.attestation.signature_ref != f"detached:{self.envelope_id}":
            raise ValueError("adoption signature reference does not match envelope")
        if self.source_class in {
            AdoptionAttestationSourceClass.SYNTHETIC_FIXTURE,
            AdoptionAttestationSourceClass.EXTERNAL_SHAPE_FIXTURE,
        }:
            if self.adopter_trust.identity_status != "synthetic_fixture":
                raise ValueError("synthetic adoption intake requires a fixture-only identity")
        elif self.adopter_trust.identity_status != "externally_attested":
            raise ValueError("external adoption attestation requires attested identity")
        return self


class ExternalAdoptionAttestationReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": EXTERNAL_ADOPTION_ATTESTATION_RECEIPT_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.external-adoption-attestation-receipt.v1"]
    receipt_id: str = Field(min_length=1, max_length=200)
    state: AdoptionAttestationState
    source_class: AdoptionAttestationSourceClass | None
    binding: ExternalAdoptionAttestationBindingV1
    attestation_digest_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    signature_verified: bool
    external_identity_attested: bool
    observation_execution_completed: bool
    real_adopter_evidence_accepted: bool
    checks: dict[str, bool] = Field(min_length=1)
    blocking_reasons: list[str]
    next_required_actions: list[str] = Field(min_length=1)
    delivery_authority_granted: Literal[False]
    production_authority_granted: Literal[False]
    audit_completed: Literal[False]
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1
    evaluated_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_receipt(self) -> ExternalAdoptionAttestationReceiptV1:
        parse_timestamp(self.evaluated_at)
        if self.state == AdoptionAttestationState.EXTERNAL_ATTESTATION_VERIFIED:
            if (
                self.source_class
                != AdoptionAttestationSourceClass.EXTERNAL_ATTESTATION
                or not self.signature_verified
                or not self.external_identity_attested
                or not self.observation_execution_completed
                or not self.real_adopter_evidence_accepted
                or self.attestation_digest_sha256 is None
            ):
                raise ValueError(
                    "verified external adoption requires independently trusted evidence"
                )
        elif self.real_adopter_evidence_accepted:
            raise ValueError("non-verified attestation cannot count as real adopter evidence")
        if (
            self.state == AdoptionAttestationState.SYNTHETIC_VALIDATED
            and self.observation_execution_completed
        ):
            raise ValueError("synthetic fixture cannot claim external observation execution")
        return self
