"""Strict metadata-only contracts for bounded shadow and dogfood evidence."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryOutcomeReceiptV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    StrictProtocolModel,
    parse_timestamp,
    scope_is_at_most,
)


CONTROLLED_ADOPTION_CASE_SCHEMA_VERSION: Literal[
    "cbb.controlled-adoption-case.v1"
] = "cbb.controlled-adoption-case.v1"
CONTROLLED_ADOPTION_RECEIPT_SCHEMA_VERSION: Literal[
    "cbb.controlled-adoption-receipt.v1"
] = "cbb.controlled-adoption-receipt.v1"


class AdoptionEvidenceClass(StrEnum):
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    LOCAL_SHADOW = "local_shadow"
    LOCAL_DOGFOOD = "local_dogfood"
    EXTERNAL_ADOPTER = "external_adopter"


class AdoptionMode(StrEnum):
    SHADOW = "shadow"
    DOGFOOD = "dogfood"
    CANARY = "canary"


class AdoptionObservationKind(StrEnum):
    PASS = "pass"
    BLOCK = "block"
    INCIDENT = "incident"
    ROLLBACK = "rollback"
    REVOCATION = "revocation"
    REOPEN = "reopen"


class ControlledAdoptionStatus(StrEnum):
    OBSERVED = "observed"
    BLOCKED = "blocked"
    INCIDENT_RECORDED = "incident_recorded"
    ROLLED_BACK = "rolled_back"
    REVOKED = "revoked"
    REOPEN_REQUIRED = "reopen_required"


class AdoptionBindingV1(StrictProtocolModel):
    release_scope_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    protocol_version: Literal["1.0.0"]
    source_package_ref: str = Field(min_length=1, max_length=500)
    source_package_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_delivery_receipt_ref: str = Field(min_length=1, max_length=500)
    source_clearance_revocation_handle: str = Field(min_length=1, max_length=200)
    source_approved_scope: DeliveryScope
    conformance_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdoptionEffectBoundaryV1(StrictProtocolModel):
    requested_scope: DeliveryScope
    real_user_exposure_observed: bool
    external_effect_observed: bool
    production_mutation_performed: Literal[False]
    automatic_customer_send_performed: Literal[False]


class ControlledAdoptionCaseV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": CONTROLLED_ADOPTION_CASE_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.controlled-adoption-case.v1"]
    case_id: str = Field(min_length=1, max_length=160)
    evidence_class: AdoptionEvidenceClass
    adoption_mode: AdoptionMode
    observation_kind: AdoptionObservationKind
    binding: AdoptionBindingV1
    effect_boundary: AdoptionEffectBoundaryV1
    operator_reconstruction_present: bool
    risk_owner_reacceptance_present: bool
    source_revoked_before_observation: bool
    reopen_requested: bool
    real_adopter_evidence_claimed: bool
    outcome_receipt: DeliveryOutcomeReceiptV1 | None
    observed_at: str = Field(min_length=1, max_length=64)
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_case(self) -> ControlledAdoptionCaseV1:
        parse_timestamp(self.observed_at)
        if (
            self.real_adopter_evidence_claimed
            and self.evidence_class != AdoptionEvidenceClass.EXTERNAL_ADOPTER
        ):
            raise ValueError(
                "real adopter evidence can be claimed only by an external-adopter input"
            )
        if self.observation_kind in {
            AdoptionObservationKind.INCIDENT,
            AdoptionObservationKind.ROLLBACK,
            AdoptionObservationKind.REVOCATION,
        } and self.outcome_receipt is None:
            raise ValueError("adverse adoption observation requires an outcome receipt")
        if self.reopen_requested != (
            self.observation_kind == AdoptionObservationKind.REOPEN
        ):
            raise ValueError("reopen_requested must match the reopen observation kind")
        if self.outcome_receipt is not None:
            outcome = self.outcome_receipt
            if (
                outcome.source_verification.package_digest_sha256
                != self.binding.source_package_digest_sha256
            ):
                raise ValueError("outcome receipt package digest does not match adoption binding")
            if outcome.source_approved_scope != self.binding.source_approved_scope:
                raise ValueError("outcome receipt source scope does not match adoption binding")
        return self


class ControlledAdoptionReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": CONTROLLED_ADOPTION_RECEIPT_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.controlled-adoption-receipt.v1"]
    receipt_id: str = Field(min_length=1, max_length=200)
    case_id: str = Field(min_length=1, max_length=160)
    evidence_class: AdoptionEvidenceClass
    adoption_mode: AdoptionMode
    observation_kind: AdoptionObservationKind
    status: ControlledAdoptionStatus
    binding: AdoptionBindingV1
    requested_scope: DeliveryScope
    resulting_scope: DeliveryScope
    outcome_receipt_ref: str | None = Field(default=None, max_length=500)
    outcome_status: Literal["monitored", "degraded", "frozen", "revoked"] | None
    trust_action: str | None = Field(default=None, max_length=120)
    authorization_delta: Literal["none", "narrowed", "blocked"]
    checks: dict[str, bool] = Field(min_length=1)
    reasons: list[str] = Field(min_length=1)
    real_adopter_evidence: bool
    customer_delivery_authorized: Literal[False]
    production_authorized: Literal[False]
    audit_completed: Literal[False]
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1
    observed_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_receipt(self) -> ControlledAdoptionReceiptV1:
        parse_timestamp(self.observed_at)
        if (
            self.real_adopter_evidence
            and self.evidence_class != AdoptionEvidenceClass.EXTERNAL_ADOPTER
        ):
            raise ValueError("only external-adopter evidence may carry a real-evidence claim")
        if not scope_is_at_most(self.resulting_scope, self.binding.source_approved_scope):
            raise ValueError("adoption evidence cannot expand source clearance scope")
        if not scope_is_at_most(
            self.claim_boundary.maximum_scope,
            self.resulting_scope,
        ):
            raise ValueError("adoption claim boundary expands resulting scope")
        if self.status == ControlledAdoptionStatus.OBSERVED:
            if self.authorization_delta != "none":
                raise ValueError("clean observation cannot claim an authorization change")
            if self.resulting_scope != self.requested_scope:
                raise ValueError("clean observation must remain inside its requested scope")
        elif self.status == ControlledAdoptionStatus.ROLLED_BACK:
            if self.authorization_delta != "narrowed":
                raise ValueError("rollback must narrow the observed scope")
            if not scope_is_at_most(self.resulting_scope, self.requested_scope):
                raise ValueError("rollback cannot expand requested scope")
        elif self.resulting_scope != DeliveryScope.BLOCKED:
            raise ValueError("blocked, incident, revoked, and reopen states grant no scope")
        return self
