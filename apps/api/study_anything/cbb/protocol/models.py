"""Strict canonical models for Cognitive Black Box Protocol v1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TRUST_POLICY_SCHEMA_VERSION: Literal["cbb.trust-policy.v1"] = "cbb.trust-policy.v1"
EVIDENCE_BUNDLE_SCHEMA_VERSION: Literal["cbb.evidence-bundle.v1"] = (
    "cbb.evidence-bundle.v1"
)
QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION: Literal[
    "cbb.qualified-reconstruction.v1"
] = "cbb.qualified-reconstruction.v1"
GATE_DECISION_SCHEMA_VERSION: Literal["cbb.gate-decision.v1"] = (
    "cbb.gate-decision.v1"
)
DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION: Literal[
    "cbb.delivery-trust-receipt.v1"
] = "cbb.delivery-trust-receipt.v1"
RECEIPT_PROVENANCE_SCHEMA_VERSION: Literal["cbb.receipt-provenance.v1"] = (
    "cbb.receipt-provenance.v1"
)

CANONICALIZATION_ALGORITHM: Literal["cbb-json-c14n-v1"] = "cbb-json-c14n-v1"
DETERMINISTIC_TIMESTAMP = "2026-06-28T00:00:00Z"
TIMESTAMP_PATTERN = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)

HARD_DENIES_REQUIRED = frozenset(
    {
        "ai_review_only_trust",
        "irreversible_external_effect",
        "production_mutation",
    }
)


class DeliveryScope(StrEnum):
    """Ordered scopes from no release authority to a production candidate."""

    BLOCKED = "blocked"
    PERSONAL_LOCAL = "personal_local"
    SANDBOX_ONLY = "sandbox_only"
    INTERNAL_HANDOFF = "internal_handoff"
    CONTROLLED_CUSTOMER_HANDOFF = "controlled_customer_handoff"
    LIMITED_BETA = "limited_beta"
    PRODUCTION_CANDIDATE = "production_candidate"


SCOPE_ORDER = {
    DeliveryScope.BLOCKED: 0,
    DeliveryScope.PERSONAL_LOCAL: 1,
    DeliveryScope.SANDBOX_ONLY: 2,
    DeliveryScope.INTERNAL_HANDOFF: 3,
    DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF: 4,
    DeliveryScope.LIMITED_BETA: 5,
    DeliveryScope.PRODUCTION_CANDIDATE: 6,
}


def scope_is_at_most(candidate: DeliveryScope, ceiling: DeliveryScope) -> bool:
    return SCOPE_ORDER[candidate] <= SCOPE_ORDER[ceiling]


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp must include a UTC offset: {value}")
    return parsed


class StrictProtocolModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class PrivacyBoundaryV1(StrictProtocolModel):
    metadata_only: Literal[True]
    raw_source_text_included: Literal[False]
    raw_report_text_included: Literal[False]
    raw_customer_payload_included: Literal[False]
    attention_stream_included: Literal[False]
    model_prompts_included: Literal[False]
    model_credentials_included: Literal[False]
    cookies_or_bearer_tokens_included: Literal[False]
    signed_urls_included: Literal[False]
    production_mutation_performed: Literal[False]
    automatic_customer_send_performed: Literal[False]


class ClaimBoundaryV1(StrictProtocolModel):
    current_claim: str = Field(min_length=1, max_length=2000)
    maximum_scope: DeliveryScope
    not_claimed: list[str] = Field(min_length=1)


class RiskBudgetV1(StrictProtocolModel):
    level: Literal["low", "medium", "high", "blocked"]
    production_mutation_allowed: Literal[False]
    real_user_exposure_allowed: Literal[False]
    irreversible_external_effects_allowed: Literal[False]


class EvidenceRequirementV1(StrictProtocolModel):
    evidence_type: str = Field(min_length=1, max_length=120)
    required_for_scope: DeliveryScope
    blocking: bool


class TrustPolicyV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": TRUST_POLICY_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.trust-policy.v1"]
    policy_id: str = Field(min_length=1, max_length=160)
    subject_ref: str = Field(min_length=1, max_length=500)
    scenario_ref: str = Field(min_length=1, max_length=500)
    maximum_scope: DeliveryScope
    hard_denies: list[str] = Field(min_length=1)
    risk_budget: RiskBudgetV1
    required_evidence: list[EvidenceRequirementV1] = Field(min_length=1)
    required_roles: list[str] = Field(min_length=1)
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1
    created_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)

    @model_validator(mode="after")
    def validate_policy_boundary(self) -> TrustPolicyV1:
        missing = HARD_DENIES_REQUIRED.difference(self.hard_denies)
        if missing:
            raise ValueError(f"trust policy missing hard denies: {sorted(missing)}")
        if not scope_is_at_most(self.claim_boundary.maximum_scope, self.maximum_scope):
            raise ValueError("claim boundary expands trust policy maximum_scope")
        parse_timestamp(self.created_at)
        return self


class EvidenceItemV1(StrictProtocolModel):
    evidence_id: str = Field(min_length=1, max_length=160)
    evidence_type: str = Field(min_length=1, max_length=120)
    status: Literal["passed", "failed", "missing", "stale", "not_applicable"]
    source_schema_version: str = Field(min_length=1, max_length=160)
    source_ref: str = Field(min_length=1, max_length=500)
    supported_scope: DeliveryScope
    metadata: dict[str, Any]


class EvidenceBundleV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": EVIDENCE_BUNDLE_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.evidence-bundle.v1"]
    bundle_id: str = Field(min_length=1, max_length=160)
    subject_ref: str = Field(min_length=1, max_length=500)
    policy_ref: str = Field(min_length=1, max_length=500)
    evidence: list[EvidenceItemV1] = Field(min_length=1)
    maximum_supported_scope: DeliveryScope
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1
    created_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)

    @model_validator(mode="after")
    def validate_bundle_boundary(self) -> EvidenceBundleV1:
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence bundle contains duplicate evidence_id values")
        if not scope_is_at_most(
            self.claim_boundary.maximum_scope,
            self.maximum_supported_scope,
        ):
            raise ValueError("claim boundary expands evidence maximum_supported_scope")
        for item in self.evidence:
            if not scope_is_at_most(item.supported_scope, self.maximum_supported_scope):
                raise ValueError("evidence item expands bundle maximum_supported_scope")
            if item.status != "passed" and item.supported_scope != DeliveryScope.BLOCKED:
                raise ValueError("non-passed evidence cannot support delivery scope")
        parse_timestamp(self.created_at)
        return self


class QualifiedReconstructionV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.qualified-reconstruction.v1"]
    reconstruction_id: str = Field(min_length=1, max_length=160)
    policy_ref: str = Field(min_length=1, max_length=500)
    reviewer_ref: str = Field(min_length=1, max_length=500)
    status: Literal["passed", "failed", "missing", "stale"]
    qualified_scope: DeliveryScope
    active_reconstruction: bool
    passive_attention_only: Literal[False]
    required_mrus_total: int = Field(ge=0)
    required_mrus_passed: int = Field(ge=0)
    missing_mru_refs: list[str]
    evidence_refs: list[str]
    observed_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    valid_until: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_reconstruction_state(self) -> QualifiedReconstructionV1:
        observed_at = parse_timestamp(self.observed_at)
        valid_until = parse_timestamp(self.valid_until)
        expired = valid_until <= observed_at
        if self.required_mrus_passed > self.required_mrus_total:
            raise ValueError("required MRUs passed cannot exceed required MRUs total")
        if self.status == "passed":
            if expired:
                raise ValueError("passed reconstruction is stale")
            if not self.active_reconstruction:
                raise ValueError("passed reconstruction must be active")
            if self.required_mrus_passed < self.required_mrus_total:
                raise ValueError("passed reconstruction must pass all required MRUs")
            if self.qualified_scope == DeliveryScope.BLOCKED:
                raise ValueError("passed reconstruction must qualify a non-blocked scope")
            if self.missing_mru_refs:
                raise ValueError("passed reconstruction cannot list missing MRUs")
            if not self.evidence_refs:
                raise ValueError("passed reconstruction requires evidence refs")
        else:
            if self.qualified_scope != DeliveryScope.BLOCKED:
                raise ValueError("non-passed reconstruction cannot qualify delivery scope")
        if self.status == "stale" and not expired:
            raise ValueError("stale reconstruction must be expired")
        if not scope_is_at_most(
            self.claim_boundary.maximum_scope,
            self.qualified_scope,
        ):
            raise ValueError("claim boundary expands qualified reconstruction scope")
        return self


class GateDecisionV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": GATE_DECISION_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.gate-decision.v1"]
    decision_id: str = Field(min_length=1, max_length=160)
    subject_ref: str = Field(min_length=1, max_length=500)
    policy_ref: str = Field(min_length=1, max_length=500)
    evidence_bundle_ref: str = Field(min_length=1, max_length=500)
    reconstruction_ref: str = Field(min_length=1, max_length=500)
    status: Literal["allow", "block", "needs_evidence"]
    approved_scope: DeliveryScope
    reasons: list[str]
    hard_denies_triggered: list[str]
    missing_evidence_types: list[str]
    source_decision_refs: list[str] = Field(min_length=1)
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1
    decided_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)

    @model_validator(mode="after")
    def validate_decision_state(self) -> GateDecisionV1:
        parse_timestamp(self.decided_at)
        if self.status == "allow":
            if self.approved_scope == DeliveryScope.BLOCKED:
                raise ValueError("allow decision requires a non-blocked scope")
            if self.reasons or self.hard_denies_triggered or self.missing_evidence_types:
                raise ValueError("allow decision cannot include blocking reasons")
        elif self.status == "block":
            if self.approved_scope != DeliveryScope.BLOCKED or not self.reasons:
                raise ValueError("block decision requires blocked scope and reasons")
        else:
            if self.approved_scope != DeliveryScope.BLOCKED:
                raise ValueError("needs_evidence decision cannot approve delivery scope")
            if not self.missing_evidence_types:
                raise ValueError("needs_evidence decision must list missing evidence")
        if self.hard_denies_triggered and self.status != "block":
            raise ValueError("triggered hard denies require a block decision")
        if not scope_is_at_most(self.claim_boundary.maximum_scope, self.approved_scope):
            raise ValueError("claim boundary expands gate approved_scope")
        return self


class VerifierIdentityV1(StrictProtocolModel):
    verifier_id: str = Field(min_length=1, max_length=160)
    verifier_version: str = Field(min_length=1, max_length=80)
    verifier_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SignerIdentityV1(StrictProtocolModel):
    signer_id: str = Field(min_length=1, max_length=160)
    key_id: str = Field(min_length=1, max_length=160)
    identity_scope: Literal["local_self_asserted"]
    public_key_encoding: Literal["ed25519-raw-base64url"]
    public_key: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    public_key_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RevocationReferenceV1(StrictProtocolModel):
    handle: str = Field(min_length=1, max_length=200)
    registry_ref: str = Field(min_length=1, max_length=500)


class ReceiptProvenanceV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": RECEIPT_PROVENANCE_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.receipt-provenance.v1"]
    provenance_id: str = Field(min_length=1, max_length=160)
    subject_digest_kind: Literal["metadata_ref_sha256"]
    subject_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reconstruction_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_envelope_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verifier: VerifierIdentityV1
    canonicalization: Literal["cbb-json-c14n-v1"]
    signing_status: Literal["unsigned_development", "locally_signed"]
    signature_algorithm: Literal["ed25519"] | None
    signature: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{86}$")
    signer: SignerIdentityV1 | None
    created_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    expires_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    replay_nonce: str = Field(min_length=16, max_length=200)
    revocation: RevocationReferenceV1
    claim_boundary: ClaimBoundaryV1

    @model_validator(mode="after")
    def validate_provenance_boundary(self) -> ReceiptProvenanceV1:
        created_at = parse_timestamp(self.created_at)
        expires_at = parse_timestamp(self.expires_at)
        if expires_at <= created_at:
            raise ValueError("receipt provenance must expire after creation")
        if self.signing_status == "unsigned_development":
            if self.signature_algorithm is not None or self.signature is not None:
                raise ValueError("unsigned provenance cannot include a signature")
            if self.signer is not None:
                raise ValueError("unsigned provenance cannot include a signer")
            if self.claim_boundary.maximum_scope != DeliveryScope.BLOCKED:
                raise ValueError("unsigned provenance cannot claim delivery authority")
            if "portable signed attestation" not in self.claim_boundary.not_claimed:
                raise ValueError("unsigned provenance must disclaim portable signed attestation")
        else:
            if self.signature_algorithm != "ed25519" or self.signature is None:
                raise ValueError("locally signed provenance requires an Ed25519 signature")
            if self.signer is None:
                raise ValueError("locally signed provenance requires signer metadata")
            if "third-party signer identity" not in self.claim_boundary.not_claimed:
                raise ValueError("local signatures must disclaim third-party signer identity")
        return self


class DeliveryTrustReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.delivery-trust-receipt.v1"]
    receipt_id: str = Field(min_length=1, max_length=160)
    subject_ref: str = Field(min_length=1, max_length=500)
    policy_ref: str = Field(min_length=1, max_length=500)
    evidence_bundle_ref: str = Field(min_length=1, max_length=500)
    reconstruction_ref: str = Field(min_length=1, max_length=500)
    decision_ref: str = Field(min_length=1, max_length=500)
    status: Literal["allow", "block", "needs_evidence"]
    approved_scope: DeliveryScope
    reasons: list[str]
    claim_boundary: ClaimBoundaryV1
    provenance: ReceiptProvenanceV1
    privacy: PrivacyBoundaryV1
    issued_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)

    @model_validator(mode="after")
    def validate_receipt_state(self) -> DeliveryTrustReceiptV1:
        parse_timestamp(self.issued_at)
        if self.status == "allow":
            if self.approved_scope == DeliveryScope.BLOCKED or self.reasons:
                raise ValueError("allow receipt requires scope and no blocking reasons")
        else:
            if self.approved_scope != DeliveryScope.BLOCKED or not self.reasons:
                raise ValueError("non-allow receipt requires blocked scope and reasons")
        if not scope_is_at_most(self.claim_boundary.maximum_scope, self.approved_scope):
            raise ValueError("claim boundary expands receipt approved_scope")
        return self


PROTOCOL_MODELS: dict[str, type[StrictProtocolModel]] = {
    TRUST_POLICY_SCHEMA_VERSION: TrustPolicyV1,
    EVIDENCE_BUNDLE_SCHEMA_VERSION: EvidenceBundleV1,
    QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION: QualifiedReconstructionV1,
    GATE_DECISION_SCHEMA_VERSION: GateDecisionV1,
    DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION: DeliveryTrustReceiptV1,
    RECEIPT_PROVENANCE_SCHEMA_VERSION: ReceiptProvenanceV1,
}
