"""Strict canonical models for Cognitive Black Box Protocol v1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TRUST_POLICY_SCHEMA_VERSION: Literal["cbb.trust-policy.v1"] = "cbb.trust-policy.v1"
EVIDENCE_BUNDLE_SCHEMA_VERSION: Literal["cbb.evidence-bundle.v1"] = "cbb.evidence-bundle.v1"
QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION: Literal["cbb.qualified-reconstruction.v1"] = (
    "cbb.qualified-reconstruction.v1"
)
GATE_DECISION_SCHEMA_VERSION: Literal["cbb.gate-decision.v1"] = "cbb.gate-decision.v1"
DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION: Literal["cbb.delivery-trust-receipt.v1"] = (
    "cbb.delivery-trust-receipt.v1"
)
RECEIPT_PROVENANCE_SCHEMA_VERSION: Literal["cbb.receipt-provenance.v1"] = (
    "cbb.receipt-provenance.v1"
)
DELIVERY_OUTCOME_RECEIPT_SCHEMA_VERSION: Literal["cbb.delivery-outcome-receipt.v1"] = (
    "cbb.delivery-outcome-receipt.v1"
)
EVOLUTION_GATE_RECEIPT_SCHEMA_VERSION: Literal["cbb.evolution-gate-receipt.v1"] = (
    "cbb.evolution-gate-receipt.v1"
)

CANONICALIZATION_ALGORITHM: Literal["cbb-json-c14n-v1"] = "cbb-json-c14n-v1"
DETERMINISTIC_TIMESTAMP = "2026-06-28T00:00:00Z"
TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"

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
    PUBLIC_DEMO = "public_demo"
    INTERNAL_HANDOFF = "internal_handoff"
    CONTROLLED_CUSTOMER_HANDOFF = "controlled_customer_handoff"
    LIMITED_BETA = "limited_beta"
    PRODUCTION_CANDIDATE = "production_candidate"


SCOPE_ORDER = {
    DeliveryScope.BLOCKED: 0,
    DeliveryScope.PERSONAL_LOCAL: 1,
    DeliveryScope.SANDBOX_ONLY: 2,
    DeliveryScope.PUBLIC_DEMO: 3,
    DeliveryScope.INTERNAL_HANDOFF: 4,
    DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF: 5,
    DeliveryScope.LIMITED_BETA: 6,
    DeliveryScope.PRODUCTION_CANDIDATE: 7,
}


class DeliveryScenarioClass(StrEnum):
    PERSONAL_LOCAL_PROTOTYPE = "personal_local_prototype"
    PUBLIC_FAKE_DATA_DEMO = "public_fake_data_demo"
    INTERNAL_HANDOFF_CANDIDATE = "internal_handoff_candidate"
    LIMITED_BETA = "limited_beta"
    PAID_CUSTOMER_CANDIDATE = "paid_customer_candidate"
    PRODUCTION_CANDIDATE = "production_candidate"
    REGULATED_OR_IRREVERSIBLE = "regulated_or_irreversible"


class ReconstructionBoundaryType(StrEnum):
    INTENT_AND_NON_GOALS = "intent_and_non_goals"
    CRITICAL_FAILURE_PATH = "critical_failure_path"
    AFFECTED_PARTIES_AND_RECIPIENT = "affected_parties_and_recipient"
    ROLLBACK_TRIGGER = "rollback_trigger"
    EVIDENCE_WEAKNESS_AND_LIMITATIONS = "evidence_weakness_and_limitations"
    RESIDUAL_RISK = "residual_risk"


class OutcomeEventType(StrEnum):
    DELIVERY_OBSERVATION = "delivery_observation"
    NEAR_MISS = "near_miss"
    INCIDENT = "incident"
    COMPLAINT = "complaint"
    CLAIM_VIOLATION = "claim_violation"
    AFFECTED_PARTY_CHALLENGE = "affected_party_challenge"
    EVIDENCE_INVALIDATED = "evidence_invalidated"


class OutcomeSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrustDegradationAction(StrEnum):
    MAINTAIN_CURRENT_CEILING = "maintain_current_ceiling"
    NARROW_SCOPE = "narrow_scope"
    FREEZE_RECIPE = "freeze_recipe"
    REVOKE_CLEARANCE = "revoke_clearance"


class AgenticToolEffect(StrEnum):
    READ_METADATA = "read_metadata"
    QUERY_QUARANTINE = "query_quarantine"
    PROPOSE_CANDIDATE = "propose_candidate"


class AgenticPlannerKind(StrEnum):
    DETERMINISTIC_FIXTURE = "deterministic_fixture"
    MODEL_ASSISTED = "model_assisted"


class MemorySourceTrust(StrEnum):
    UNTRUSTED = "untrusted"
    LOCAL_VERIFIED = "local_verified"
    SIGNED_EXTERNAL = "signed_external"


class EvolutionChangeKind(StrEnum):
    TRUST_RECIPE = "trust_recipe"
    POLICY = "policy"
    RUNTIME = "runtime"
    TOOL_REGISTRY = "tool_registry"
    MEMORY_POLICY = "memory_policy"


class EvolutionControlType(StrEnum):
    DETERMINISTIC_REPLAY = "deterministic_replay"
    CANARY = "canary"
    ROLLBACK = "rollback"
    HUMAN_RECONSTRUCTION = "human_reconstruction"
    RISK_OWNER_ACCEPTANCE = "risk_owner_acceptance"
    MAINTAINER_APPROVAL = "maintainer_approval"


class EvolutionControlStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    MISSING = "missing"


class EvolutionDecisionStatus(StrEnum):
    BLOCK = "block"
    NEEDS_EVIDENCE = "needs_evidence"
    APPROVED_FOR_LOCAL_CANDIDATE = "approved_for_local_candidate"


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


class RecipientContractV1(StrictProtocolModel):
    recipient_ref: str = Field(min_length=1, max_length=500)
    recipient_kind: Literal[
        "self",
        "internal_operator",
        "public_demo_audience",
        "limited_beta_user",
        "paid_customer_operator",
        "production_operator",
        "regulated_subject",
    ]
    external: bool
    automatic_execution_authority: Literal[False]


class RiskOwnerContractV1(StrictProtocolModel):
    required: bool
    risk_owner_ref: str | None = Field(default=None, min_length=1, max_length=500)
    accepted_scope_ceiling: DeliveryScope
    acceptance_evidence_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    @model_validator(mode="after")
    def validate_risk_owner_requirement(self) -> RiskOwnerContractV1:
        if self.required:
            if self.risk_owner_ref is None or self.acceptance_evidence_type is None:
                raise ValueError("required risk owner needs an actor and evidence type")
            if self.accepted_scope_ceiling == DeliveryScope.BLOCKED:
                raise ValueError("required risk owner needs a non-blocked scope ceiling")
        elif (
            self.risk_owner_ref is not None
            or self.acceptance_evidence_type is not None
            or self.accepted_scope_ceiling != DeliveryScope.BLOCKED
        ):
            raise ValueError("optional risk owner cannot imply accepted authority")
        return self


class AffectedPartyContractV1(StrictProtocolModel):
    party_ref: str = Field(min_length=1, max_length=500)
    party_kind: str = Field(min_length=1, max_length=120)
    impact_classes: list[str] = Field(min_length=1)
    disclosure_required: bool
    appeal_required: bool
    redress_required: bool


class SafeguardRequirementV1(StrictProtocolModel):
    required: bool
    evidence_type: str | None = Field(default=None, min_length=1, max_length=120)
    mechanism_ref: str | None = Field(default=None, min_length=1, max_length=500)
    human_fallback_required: bool

    @model_validator(mode="after")
    def validate_safeguard_requirement(self) -> SafeguardRequirementV1:
        if self.required:
            if self.evidence_type is None or self.mechanism_ref is None:
                raise ValueError("required safeguard needs evidence and mechanism refs")
        elif self.evidence_type is not None or self.mechanism_ref is not None:
            raise ValueError("optional safeguard cannot imply configured evidence")
        return self


class DeliveryScenarioV1(StrictProtocolModel):
    scenario_ref: str = Field(min_length=1, max_length=500)
    scenario_class: DeliveryScenarioClass
    project_ref: str = Field(min_length=1, max_length=500)
    model_ref: str = Field(min_length=1, max_length=500)
    maximum_scope: DeliveryScope
    recipient: RecipientContractV1
    risk_owner: RiskOwnerContractV1
    affected_parties: list[AffectedPartyContractV1]
    disclosure: SafeguardRequirementV1
    appeal: SafeguardRequirementV1
    redress: SafeguardRequirementV1
    impact_classes: list[str] = Field(min_length=1)
    regulated_or_irreversible: bool

    @model_validator(mode="after")
    def validate_scenario_boundary(self) -> DeliveryScenarioV1:
        expected_scopes = {
            DeliveryScenarioClass.PERSONAL_LOCAL_PROTOTYPE: DeliveryScope.PERSONAL_LOCAL,
            DeliveryScenarioClass.PUBLIC_FAKE_DATA_DEMO: DeliveryScope.PUBLIC_DEMO,
            DeliveryScenarioClass.INTERNAL_HANDOFF_CANDIDATE: DeliveryScope.INTERNAL_HANDOFF,
            DeliveryScenarioClass.LIMITED_BETA: DeliveryScope.LIMITED_BETA,
            DeliveryScenarioClass.PAID_CUSTOMER_CANDIDATE: DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
            DeliveryScenarioClass.PRODUCTION_CANDIDATE: DeliveryScope.PRODUCTION_CANDIDATE,
            DeliveryScenarioClass.REGULATED_OR_IRREVERSIBLE: DeliveryScope.BLOCKED,
        }
        if self.maximum_scope != expected_scopes[self.scenario_class]:
            raise ValueError("scenario class and scope ceiling do not match")
        if self.regulated_or_irreversible != (
            self.scenario_class == DeliveryScenarioClass.REGULATED_OR_IRREVERSIBLE
        ):
            raise ValueError("regulated scenario classification is inconsistent")
        party_refs = [party.party_ref for party in self.affected_parties]
        if len(party_refs) != len(set(party_refs)):
            raise ValueError("scenario contains duplicate affected-party refs")
        if (self.recipient.external or self.affected_parties) and not self.disclosure.required:
            raise ValueError("external or affected-party scenarios require disclosure")
        if (
            any(party.appeal_required for party in self.affected_parties)
            and not self.appeal.required
        ):
            raise ValueError("affected-party appeal requirement is not configured")
        if (
            any(party.redress_required for party in self.affected_parties)
            and not self.redress.required
        ):
            raise ValueError("affected-party redress requirement is not configured")
        if (
            self.scenario_class
            in {
                DeliveryScenarioClass.LIMITED_BETA,
                DeliveryScenarioClass.PAID_CUSTOMER_CANDIDATE,
                DeliveryScenarioClass.PRODUCTION_CANDIDATE,
            }
            and not self.risk_owner.required
        ):
            raise ValueError("higher-scope scenario requires a scoped risk owner")
        if (
            self.scenario_class == DeliveryScenarioClass.PRODUCTION_CANDIDATE
            and not self.affected_parties
        ):
            raise ValueError("production candidate must identify affected parties")
        return self


class MinimumReconstructableUnitV1(StrictProtocolModel):
    mru_ref: str = Field(min_length=1, max_length=500)
    boundary_type: ReconstructionBoundaryType
    required_for_scope: DeliveryScope
    evidence_kind: Literal["active_reconstruction"]
    blocks_promotion: Literal[True]


class MruResultV1(StrictProtocolModel):
    mru_ref: str = Field(min_length=1, max_length=500)
    boundary_type: ReconstructionBoundaryType
    status: Literal["passed", "failed", "missing", "stale"]
    evidence_refs: list[str]

    @model_validator(mode="after")
    def validate_mru_result(self) -> MruResultV1:
        if self.status == "passed" and not self.evidence_refs:
            raise ValueError("passed MRU requires active reconstruction evidence")
        return self


class HumanCapabilityProfileV1(StrictProtocolModel):
    profile_id: str = Field(min_length=1, max_length=160)
    human_ref: str = Field(min_length=1, max_length=500)
    project_ref: str = Field(min_length=1, max_length=500)
    scenario_refs: list[str] = Field(min_length=1)
    qualified_roles: list[str] = Field(min_length=1)
    boundary_types: list[ReconstructionBoundaryType] = Field(min_length=1)
    status: Literal["active", "challenged", "stale", "insufficient"]
    maximum_scope: DeliveryScope
    evidence_refs: list[str]
    counter_evidence_refs: list[str]
    observed_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    valid_until: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    permanent_global_label: Literal[False]

    @model_validator(mode="after")
    def validate_human_capability(self) -> HumanCapabilityProfileV1:
        observed_at = parse_timestamp(self.observed_at)
        valid_until = parse_timestamp(self.valid_until)
        if self.project_ref in {"*", "global"} or any(
            ref in {"*", "global"} for ref in self.scenario_refs
        ):
            raise ValueError("human capability must be project and scenario scoped")
        if len(self.scenario_refs) != len(set(self.scenario_refs)):
            raise ValueError("human capability has duplicate scenario refs")
        if len(self.qualified_roles) != len(set(self.qualified_roles)):
            raise ValueError("human capability has duplicate roles")
        if len(self.boundary_types) != len(set(self.boundary_types)):
            raise ValueError("human capability has duplicate boundary types")
        expired = valid_until <= observed_at
        if self.status == "active":
            if expired or self.maximum_scope == DeliveryScope.BLOCKED:
                raise ValueError("active human capability must be current and scoped")
            if not self.evidence_refs or self.counter_evidence_refs:
                raise ValueError("active human capability needs evidence and no counter-evidence")
        else:
            if self.maximum_scope != DeliveryScope.BLOCKED:
                raise ValueError("non-active human capability cannot authorize scope")
            if self.status == "stale" and not expired:
                raise ValueError("stale human capability must be expired")
            if self.status == "challenged" and not self.counter_evidence_refs:
                raise ValueError("challenged human capability requires counter-evidence")
        return self


class ModelCapabilityProfileV1(StrictProtocolModel):
    profile_id: str = Field(min_length=1, max_length=160)
    model_ref: str = Field(min_length=1, max_length=500)
    scenario_refs: list[str] = Field(min_length=1)
    task_types: list[str] = Field(min_length=1)
    status: Literal["observed", "challenged", "stale", "unproven"]
    maximum_autonomy_scope: DeliveryScope
    evidence_refs: list[str]
    counter_evidence_refs: list[str]
    known_failure_modes: list[str]
    observed_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    valid_until: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    vendor_claims_sufficient: Literal[False]

    @model_validator(mode="after")
    def validate_model_capability(self) -> ModelCapabilityProfileV1:
        observed_at = parse_timestamp(self.observed_at)
        valid_until = parse_timestamp(self.valid_until)
        if len(self.scenario_refs) != len(set(self.scenario_refs)):
            raise ValueError("model capability has duplicate scenario refs")
        if len(self.task_types) != len(set(self.task_types)):
            raise ValueError("model capability has duplicate task types")
        expired = valid_until <= observed_at
        if self.status == "observed":
            if expired or self.maximum_autonomy_scope == DeliveryScope.BLOCKED:
                raise ValueError("observed model capability must be current and scoped")
            if not self.evidence_refs or self.counter_evidence_refs:
                raise ValueError("observed model capability needs evidence and no counter-evidence")
        else:
            if self.maximum_autonomy_scope != DeliveryScope.BLOCKED:
                raise ValueError("untrusted model capability cannot authorize scope")
            if self.status == "stale" and not expired:
                raise ValueError("stale model capability must be expired")
            if self.status == "challenged" and not self.counter_evidence_refs:
                raise ValueError("challenged model capability requires counter-evidence")
        return self


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
    scenario: DeliveryScenarioV1
    model_capability_profile: ModelCapabilityProfileV1
    maximum_scope: DeliveryScope
    hard_denies: list[str] = Field(min_length=1)
    risk_budget: RiskBudgetV1
    required_evidence: list[EvidenceRequirementV1] = Field(min_length=1)
    required_roles: list[str] = Field(min_length=1)
    required_mrus: list[MinimumReconstructableUnitV1] = Field(min_length=1)
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1
    created_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)

    @model_validator(mode="after")
    def validate_policy_boundary(self) -> TrustPolicyV1:
        missing = HARD_DENIES_REQUIRED.difference(self.hard_denies)
        if missing:
            raise ValueError(f"trust policy missing hard denies: {sorted(missing)}")
        if self.scenario.scenario_ref != self.scenario_ref:
            raise ValueError("scenario contract does not match policy scenario_ref")
        if not scope_is_at_most(self.maximum_scope, self.scenario.maximum_scope):
            raise ValueError("policy expands scenario scope ceiling")
        model_profile = self.model_capability_profile
        if model_profile.model_ref != self.scenario.model_ref:
            raise ValueError("model capability does not match scenario model_ref")
        if self.scenario_ref not in model_profile.scenario_refs:
            raise ValueError("model capability is not scoped to this scenario")
        if not scope_is_at_most(
            self.maximum_scope,
            model_profile.maximum_autonomy_scope,
        ):
            raise ValueError("policy expands model capability scope ceiling")
        evidence_types = [item.evidence_type for item in self.required_evidence]
        if len(evidence_types) != len(set(evidence_types)):
            raise ValueError("trust policy contains duplicate evidence requirements")
        if len(self.required_roles) != len(set(self.required_roles)):
            raise ValueError("trust policy contains duplicate required roles")
        mru_refs = [item.mru_ref for item in self.required_mrus]
        if len(mru_refs) != len(set(mru_refs)):
            raise ValueError("trust policy contains duplicate MRU refs")
        if self.maximum_scope != DeliveryScope.BLOCKED and any(
            not scope_is_at_most(item.required_for_scope, self.maximum_scope)
            for item in self.required_mrus
        ):
            raise ValueError("MRU requirement exceeds policy maximum_scope")
        if "qualified_reconstruction" not in evidence_types:
            raise ValueError("MRU policy requires qualified reconstruction evidence")
        safeguards = (
            self.scenario.disclosure,
            self.scenario.appeal,
            self.scenario.redress,
        )
        missing_safeguards = sorted(
            requirement.evidence_type
            for requirement in safeguards
            if requirement.required
            and requirement.evidence_type not in evidence_types
            and requirement.evidence_type is not None
        )
        if missing_safeguards:
            raise ValueError(f"trust policy missing safeguard evidence: {missing_safeguards}")
        if self.scenario.risk_owner.required:
            risk_evidence = self.scenario.risk_owner.acceptance_evidence_type
            if "risk_owner" not in self.required_roles or risk_evidence not in evidence_types:
                raise ValueError("risk-owner contract is not enforced by policy")
            if not scope_is_at_most(
                self.maximum_scope,
                self.scenario.risk_owner.accepted_scope_ceiling,
            ):
                raise ValueError("policy expands risk-owner accepted scope ceiling")
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
    scenario_ref: str = Field(min_length=1, max_length=500)
    project_ref: str = Field(min_length=1, max_length=500)
    reviewer_roles: list[str] = Field(min_length=1)
    status: Literal["passed", "failed", "missing", "stale"]
    qualified_scope: DeliveryScope
    active_reconstruction: bool
    passive_attention_only: Literal[False]
    required_mrus_total: int = Field(ge=0)
    required_mrus_passed: int = Field(ge=0)
    missing_mru_refs: list[str]
    mru_results: list[MruResultV1] = Field(min_length=1)
    human_capability_profile: HumanCapabilityProfileV1
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
        if len(self.reviewer_roles) != len(set(self.reviewer_roles)):
            raise ValueError("qualified reconstruction has duplicate reviewer roles")
        mru_refs = [item.mru_ref for item in self.mru_results]
        if len(mru_refs) != len(set(mru_refs)):
            raise ValueError("qualified reconstruction has duplicate MRU results")
        if self.required_mrus_passed > self.required_mrus_total:
            raise ValueError("required MRUs passed cannot exceed required MRUs total")
        passed_mrus = sum(item.status == "passed" for item in self.mru_results)
        nonpassed_refs = sorted(
            item.mru_ref for item in self.mru_results if item.status != "passed"
        )
        if self.required_mrus_total != len(self.mru_results):
            raise ValueError("MRU total does not match result count")
        if self.required_mrus_passed != passed_mrus:
            raise ValueError("MRU passed count does not match result states")
        if sorted(self.missing_mru_refs) != nonpassed_refs:
            raise ValueError("missing MRU refs do not match non-passed results")
        profile = self.human_capability_profile
        if profile.human_ref != self.reviewer_ref:
            raise ValueError("human capability does not match reviewer_ref")
        if profile.project_ref != self.project_ref:
            raise ValueError("human capability does not match reconstruction project")
        if self.scenario_ref not in profile.scenario_refs:
            raise ValueError("human capability is not scoped to reconstruction scenario")
        if not set(self.reviewer_roles).issubset(profile.qualified_roles):
            raise ValueError("human capability does not cover reviewer roles")
        result_boundaries = {item.boundary_type for item in self.mru_results}
        if not result_boundaries.issubset(set(profile.boundary_types)):
            raise ValueError("human capability does not cover reconstructed boundaries")
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
            if profile.status != "active":
                raise ValueError("passed reconstruction requires active human capability")
            if not scope_is_at_most(self.qualified_scope, profile.maximum_scope):
                raise ValueError("reconstruction expands human capability scope")
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


class PostDeliverySamplingV1(StrictProtocolModel):
    sampling_id: str = Field(min_length=1, max_length=160)
    strategy: Literal["all_observed", "bounded_sample", "triggered_review"]
    window_started_at: str = Field(
        min_length=1,
        max_length=64,
        pattern=TIMESTAMP_PATTERN,
    )
    window_ended_at: str = Field(
        min_length=1,
        max_length=64,
        pattern=TIMESTAMP_PATTERN,
    )
    eligible_count: int = Field(ge=1)
    sampled_count: int = Field(ge=1)
    selection_ref: str = Field(min_length=1, max_length=500)
    coverage_complete: bool
    limitations: list[str]

    @model_validator(mode="after")
    def validate_sampling_window(self) -> PostDeliverySamplingV1:
        started_at = parse_timestamp(self.window_started_at)
        ended_at = parse_timestamp(self.window_ended_at)
        if ended_at <= started_at:
            raise ValueError("post-delivery sampling window must end after it starts")
        if self.sampled_count > self.eligible_count:
            raise ValueError("sampled outcome count cannot exceed eligible count")
        if self.strategy == "all_observed":
            if not self.coverage_complete or self.sampled_count != self.eligible_count:
                raise ValueError("all-observed sampling must cover every eligible outcome")
        elif not self.coverage_complete and not self.limitations:
            raise ValueError("incomplete outcome sampling must disclose limitations")
        return self


class OutcomeEventV1(StrictProtocolModel):
    event_id: str = Field(min_length=1, max_length=160)
    event_type: OutcomeEventType
    severity: OutcomeSeverity
    status: Literal["reported", "confirmed", "resolved", "disputed"]
    source_refs: list[str] = Field(min_length=1)
    affected_party_refs: list[str]
    occurred_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    external_effect_observed: bool
    claim_boundary_violated: bool
    counter_evidence_refs: list[str]
    resolution_refs: list[str]

    @model_validator(mode="after")
    def validate_outcome_event(self) -> OutcomeEventV1:
        parse_timestamp(self.occurred_at)
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("outcome event contains duplicate source refs")
        if len(self.affected_party_refs) != len(set(self.affected_party_refs)):
            raise ValueError("outcome event contains duplicate affected-party refs")
        if self.event_type == OutcomeEventType.AFFECTED_PARTY_CHALLENGE:
            if not self.affected_party_refs:
                raise ValueError("affected-party challenge requires an affected party ref")
        if self.event_type == OutcomeEventType.CLAIM_VIOLATION:
            if not self.claim_boundary_violated:
                raise ValueError("claim-violation event must mark the claim boundary violated")
        if (
            self.status == "confirmed"
            and self.event_type != OutcomeEventType.DELIVERY_OBSERVATION
            and self.severity == OutcomeSeverity.INFO
        ):
            raise ValueError("confirmed adverse outcome cannot have info severity")
        if self.status == "resolved" and not self.resolution_refs:
            raise ValueError("resolved outcome requires resolution evidence")
        return self


class RollbackOutcomeV1(StrictProtocolModel):
    required: bool
    attempted: bool
    status: Literal["not_required", "not_attempted", "succeeded", "partial", "failed"]
    evidence_refs: list[str]

    @model_validator(mode="after")
    def validate_rollback_state(self) -> RollbackOutcomeV1:
        if not self.required:
            if self.attempted or self.status != "not_required" or self.evidence_refs:
                raise ValueError("optional rollback cannot imply execution evidence")
        elif not self.attempted:
            if self.status != "not_attempted" or self.evidence_refs:
                raise ValueError("unattempted rollback cannot include result evidence")
        elif self.status not in {"succeeded", "partial", "failed"}:
            raise ValueError("attempted rollback requires an execution result")
        elif not self.evidence_refs:
            raise ValueError("attempted rollback requires evidence refs")
        return self


class SourceClearanceVerificationV1(StrictProtocolModel):
    package_ref: str = Field(min_length=1, max_length=500)
    package_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_status: Literal["pass"]
    verified_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    clearance_valid_at: str = Field(
        min_length=1,
        max_length=64,
        pattern=TIMESTAMP_PATTERN,
    )
    checks_passed: list[str] = Field(min_length=1)
    local_self_asserted_signer_only: Literal[True]

    @model_validator(mode="after")
    def validate_source_verification(self) -> SourceClearanceVerificationV1:
        verified_at = parse_timestamp(self.verified_at)
        clearance_valid_at = parse_timestamp(self.clearance_valid_at)
        if clearance_valid_at > verified_at:
            raise ValueError("source clearance validity anchor cannot follow verification")
        if len(self.checks_passed) != len(set(self.checks_passed)):
            raise ValueError("source clearance verification has duplicate checks")
        return self


class TrustDegradationV1(StrictProtocolModel):
    action: TrustDegradationAction
    previous_scope: DeliveryScope
    resulting_scope: DeliveryScope
    recipe_ref: str = Field(min_length=1, max_length=500)
    recipe_state: Literal["active", "frozen", "revoked"]
    source_clearance_revoked: bool
    revoked_clearance_handles: list[str]
    replay_required: bool
    policy_reconstruction_required: bool
    risk_owner_reacceptance_required: bool
    affected_party_follow_up_required: bool
    counter_evidence_refs: list[str]
    reasons: list[str] = Field(min_length=1)
    trust_increase_allowed: Literal[False]

    @model_validator(mode="after")
    def validate_degradation_state(self) -> TrustDegradationV1:
        if not scope_is_at_most(self.resulting_scope, self.previous_scope):
            raise ValueError("outcome feedback cannot increase the clearance scope")
        if len(self.revoked_clearance_handles) != len(set(self.revoked_clearance_handles)):
            raise ValueError("trust degradation contains duplicate revocation handles")
        if self.action == TrustDegradationAction.MAINTAIN_CURRENT_CEILING:
            if self.resulting_scope != self.previous_scope:
                raise ValueError("maintain action cannot change the clearance scope")
            if self.recipe_state != "active" or self.source_clearance_revoked:
                raise ValueError("maintain action requires an active, non-revoked recipe")
            if self.revoked_clearance_handles or self.replay_required:
                raise ValueError("maintain action cannot revoke or require replay")
        elif self.action == TrustDegradationAction.NARROW_SCOPE:
            if (
                self.resulting_scope == DeliveryScope.BLOCKED
                or self.resulting_scope == self.previous_scope
            ):
                raise ValueError("narrow action requires a lower non-blocked scope")
            if self.recipe_state != "active" or self.source_clearance_revoked:
                raise ValueError("narrow action cannot revoke the source clearance")
            if self.revoked_clearance_handles or not self.replay_required:
                raise ValueError("narrow action requires replay without revocation")
        elif self.action == TrustDegradationAction.FREEZE_RECIPE:
            if self.resulting_scope != DeliveryScope.BLOCKED:
                raise ValueError("frozen recipe cannot authorize future delivery")
            if self.recipe_state != "frozen" or self.source_clearance_revoked:
                raise ValueError("freeze action must freeze without revoking the source")
            if self.revoked_clearance_handles or not self.replay_required:
                raise ValueError("freeze action requires replay without revocation handles")
        else:
            if self.resulting_scope != DeliveryScope.BLOCKED:
                raise ValueError("revoked clearance cannot authorize future delivery")
            if self.recipe_state != "revoked" or not self.source_clearance_revoked:
                raise ValueError("revoke action must revoke the source clearance")
            if not self.revoked_clearance_handles or not self.replay_required:
                raise ValueError("revoke action requires revocation handles and replay")
        return self


class OutcomeReceiptProvenanceV1(StrictProtocolModel):
    outcome_envelope_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_package_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verifier: VerifierIdentityV1
    canonicalization: Literal["cbb-json-c14n-v1"]
    signing_status: Literal["locally_signed"]
    signature_algorithm: Literal["ed25519"]
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{86}$")
    signer: SignerIdentityV1
    created_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    expires_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    replay_nonce: str = Field(min_length=16, max_length=200)
    revocation: RevocationReferenceV1
    claim_boundary: ClaimBoundaryV1

    @model_validator(mode="after")
    def validate_outcome_provenance(self) -> OutcomeReceiptProvenanceV1:
        created_at = parse_timestamp(self.created_at)
        expires_at = parse_timestamp(self.expires_at)
        if expires_at <= created_at:
            raise ValueError("outcome receipt provenance must expire after creation")
        if "third-party signer identity" not in self.claim_boundary.not_claimed:
            raise ValueError("local outcome signature must disclaim third-party identity")
        return self


class DeliveryOutcomeReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": DELIVERY_OUTCOME_RECEIPT_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.delivery-outcome-receipt.v1"]
    outcome_receipt_id: str = Field(min_length=1, max_length=160)
    source_delivery_receipt_ref: str = Field(min_length=1, max_length=500)
    source_delivery_receipt_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_clearance_revocation_handle: str = Field(min_length=1, max_length=200)
    subject_ref: str = Field(min_length=1, max_length=500)
    policy_ref: str = Field(min_length=1, max_length=500)
    scenario_ref: str = Field(min_length=1, max_length=500)
    source_approved_scope: DeliveryScope
    source_verification: SourceClearanceVerificationV1
    sampling: PostDeliverySamplingV1
    events: list[OutcomeEventV1] = Field(min_length=1)
    rollback: RollbackOutcomeV1
    status: Literal["monitored", "degraded", "frozen", "revoked"]
    trust_update: TrustDegradationV1
    issued_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    claim_boundary: ClaimBoundaryV1
    outcome_provenance: OutcomeReceiptProvenanceV1
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_outcome_receipt(self) -> DeliveryOutcomeReceiptV1:
        issued_at = parse_timestamp(self.issued_at)
        if issued_at < parse_timestamp(self.sampling.window_ended_at):
            raise ValueError("outcome receipt cannot precede its sampling window")
        if issued_at != parse_timestamp(self.source_verification.verified_at):
            raise ValueError("source verification must occur when the outcome receipt is issued")
        if issued_at != parse_timestamp(self.outcome_provenance.created_at):
            raise ValueError("outcome provenance must be created when the receipt is issued")
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("outcome receipt contains duplicate event ids")
        window_start = parse_timestamp(self.sampling.window_started_at)
        window_end = parse_timestamp(self.sampling.window_ended_at)
        if parse_timestamp(self.source_verification.clearance_valid_at) > window_start:
            raise ValueError("source clearance validity anchor cannot follow outcome sampling")
        if any(
            not window_start <= parse_timestamp(event.occurred_at) <= window_end
            for event in self.events
        ):
            raise ValueError("outcome event falls outside the sampling window")
        if self.trust_update.previous_scope != self.source_approved_scope:
            raise ValueError("trust update does not start from source approved scope")
        expected_status = {
            TrustDegradationAction.MAINTAIN_CURRENT_CEILING: "monitored",
            TrustDegradationAction.NARROW_SCOPE: "degraded",
            TrustDegradationAction.FREEZE_RECIPE: "frozen",
            TrustDegradationAction.REVOKE_CLEARANCE: "revoked",
        }[self.trust_update.action]
        if self.status != expected_status:
            raise ValueError("outcome receipt status does not match trust action")
        if not scope_is_at_most(
            self.claim_boundary.maximum_scope,
            self.trust_update.resulting_scope,
        ):
            raise ValueError("outcome claim boundary expands resulting scope")
        if "customer outcome guarantee" not in self.claim_boundary.not_claimed:
            raise ValueError("outcome receipt must disclaim customer outcome guarantees")
        if (
            self.outcome_provenance.source_package_digest_sha256
            != self.source_verification.package_digest_sha256
        ):
            raise ValueError("outcome provenance source package digest mismatch")
        if not scope_is_at_most(
            self.outcome_provenance.claim_boundary.maximum_scope,
            self.trust_update.resulting_scope,
        ):
            raise ValueError("outcome provenance claim expands resulting scope")
        if self.rollback.status == "failed" and not self.trust_update.source_clearance_revoked:
            raise ValueError("failed rollback must revoke the source clearance")
        substantiated = {"confirmed", "resolved"}
        if any(
            event.status in substantiated
            and event.event_type
            in {OutcomeEventType.CLAIM_VIOLATION, OutcomeEventType.EVIDENCE_INVALIDATED}
            for event in self.events
        ) and not self.trust_update.source_clearance_revoked:
            raise ValueError("substantiated claim or evidence violation must revoke clearance")
        if any(
            event.status in substantiated
            and event.severity in {OutcomeSeverity.HIGH, OutcomeSeverity.CRITICAL}
            and (
                event.event_type == OutcomeEventType.INCIDENT
                or event.external_effect_observed
            )
            for event in self.events
        ) and not self.trust_update.source_clearance_revoked:
            raise ValueError("substantiated high-impact outcome must revoke clearance")
        if self.trust_update.action == TrustDegradationAction.MAINTAIN_CURRENT_CEILING:
            clean_observations_only = all(
                event.event_type == OutcomeEventType.DELIVERY_OBSERVATION
                and event.status == "confirmed"
                and event.severity == OutcomeSeverity.INFO
                and not event.external_effect_observed
                and not event.claim_boundary_violated
                for event in self.events
            )
            if not clean_observations_only or self.rollback.status != "not_required":
                raise ValueError("maintain action requires confirmed clean observations only")
        if (
            any(
                event.event_type == OutcomeEventType.AFFECTED_PARTY_CHALLENGE
                and event.status != "resolved"
                for event in self.events
            )
            and not self.trust_update.affected_party_follow_up_required
        ):
            raise ValueError("open affected-party challenge requires follow-up")
        return self


class AgenticToolContractV1(StrictProtocolModel):
    tool_id: str = Field(min_length=1, max_length=160)
    tool_version: str = Field(min_length=1, max_length=40)
    effect: AgenticToolEffect
    input_schema_ref: str = Field(min_length=1, max_length=500)
    output_schema_ref: str = Field(min_length=1, max_length=500)
    max_input_refs: int = Field(ge=1, le=100)
    max_output_refs: int = Field(ge=1, le=100)
    accepts_untrusted_input: bool
    requires_quarantine: bool
    network_allowed: Literal[False]
    filesystem_write_allowed: Literal[False]
    policy_mutation_allowed: Literal[False]
    gate_decision_allowed: Literal[False]
    production_mutation_allowed: Literal[False]

    @model_validator(mode="after")
    def validate_tool_boundary(self) -> AgenticToolContractV1:
        if self.accepts_untrusted_input and not self.requires_quarantine:
            raise ValueError("untrusted tool input requires quarantine")
        if self.effect == AgenticToolEffect.PROPOSE_CANDIDATE and not self.requires_quarantine:
            raise ValueError("candidate proposal tools require quarantine")
        return self


class AgenticToolCallV1(StrictProtocolModel):
    call_id: str = Field(min_length=1, max_length=160)
    tool_id: str = Field(min_length=1, max_length=160)
    requested_effect: AgenticToolEffect
    input_refs: list[str] = Field(min_length=1, max_length=100)
    untrusted_input_present: bool
    quarantine_acknowledged: bool
    requests_policy_mutation: Literal[False]
    requests_gate_decision: Literal[False]
    requests_production_mutation: Literal[False]

    @model_validator(mode="after")
    def validate_tool_call(self) -> AgenticToolCallV1:
        if len(self.input_refs) != len(set(self.input_refs)):
            raise ValueError("agentic tool call contains duplicate input refs")
        if self.untrusted_input_present and not self.quarantine_acknowledged:
            raise ValueError("untrusted tool call input was not quarantined")
        return self


class AgenticPlanV1(StrictProtocolModel):
    plan_id: str = Field(min_length=1, max_length=160)
    planner_id: str = Field(min_length=1, max_length=160)
    planner_kind: AgenticPlannerKind
    created_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    calls: list[AgenticToolCallV1] = Field(min_length=1, max_length=30)
    final_authority: Literal["proposal_only"]
    policy_mutation_requested: Literal[False]
    gate_decision_requested: Literal[False]
    production_mutation_requested: Literal[False]

    @model_validator(mode="after")
    def validate_agentic_plan(self) -> AgenticPlanV1:
        parse_timestamp(self.created_at)
        call_ids = [call.call_id for call in self.calls]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("agentic plan contains duplicate call ids")
        return self


class AgenticToolResultV1(StrictProtocolModel):
    call_id: str = Field(min_length=1, max_length=160)
    tool_id: str = Field(min_length=1, max_length=160)
    effect: AgenticToolEffect
    status: Literal["passed", "blocked"]
    output_refs: list[str] = Field(max_length=100)
    provenance_refs: list[str] = Field(min_length=1, max_length=100)
    redaction_count: int = Field(ge=0)
    reasons: list[str]
    authority: Literal["supporting_evidence_only"]
    policy_override_allowed: Literal[False]
    gate_decision_allowed: Literal[False]
    production_mutation_performed: Literal[False]

    @model_validator(mode="after")
    def validate_tool_result(self) -> AgenticToolResultV1:
        if len(self.output_refs) != len(set(self.output_refs)):
            raise ValueError("agentic tool result contains duplicate output refs")
        if len(self.provenance_refs) != len(set(self.provenance_refs)):
            raise ValueError("agentic tool result contains duplicate provenance refs")
        if self.status == "passed":
            if not self.output_refs or self.reasons:
                raise ValueError("passed tool result requires output refs and no reasons")
        elif self.output_refs or not self.reasons:
            raise ValueError("blocked tool result requires reasons and no output refs")
        return self


class QuarantinedMemoryEntryV1(StrictProtocolModel):
    memory_id: str = Field(min_length=1, max_length=160)
    memory_kind: Literal["failure", "receipt", "outcome", "counter_evidence"]
    source_ref: str = Field(min_length=1, max_length=500)
    source_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_trust: MemorySourceTrust
    verification_ref: str | None = Field(default=None, max_length=500)
    signature_ref: str | None = Field(default=None, max_length=500)
    observed_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    expires_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    counter_evidence_refs: list[str]
    injection_signals: list[str]
    policy_directive_detected: bool
    eligible_as_supporting_evidence: bool
    quarantined: Literal[True]
    policy_authority: Literal[False]
    raw_content_included: Literal[False]

    @model_validator(mode="after")
    def validate_memory_entry(self) -> QuarantinedMemoryEntryV1:
        observed_at = parse_timestamp(self.observed_at)
        expires_at = parse_timestamp(self.expires_at)
        if expires_at <= observed_at:
            raise ValueError("quarantined memory must expire after observation")
        if len(self.counter_evidence_refs) != len(set(self.counter_evidence_refs)):
            raise ValueError("memory entry contains duplicate counter-evidence refs")
        if len(self.injection_signals) != len(set(self.injection_signals)):
            raise ValueError("memory entry contains duplicate injection signals")
        if self.source_trust == MemorySourceTrust.UNTRUSTED:
            if self.verification_ref is not None or self.signature_ref is not None:
                raise ValueError("untrusted memory cannot claim verification or signature")
            if self.eligible_as_supporting_evidence:
                raise ValueError("untrusted memory cannot be eligible evidence")
        elif self.source_trust == MemorySourceTrust.LOCAL_VERIFIED:
            if self.verification_ref is None or self.signature_ref is not None:
                raise ValueError("local-verified memory requires only a verification ref")
        elif self.signature_ref is None or self.verification_ref is not None:
            raise ValueError("signed-external memory requires only a signature ref")
        if (
            self.policy_directive_detected or self.injection_signals
        ) and self.eligible_as_supporting_evidence:
            raise ValueError("injected memory cannot be eligible evidence")
        return self


class MemoryDispositionV1(StrictProtocolModel):
    memory_id: str = Field(min_length=1, max_length=160)
    reason: Literal[
        "expired",
        "not_yet_observed",
        "untrusted",
        "injection_signal",
        "policy_directive",
        "counter_evidence_pending",
        "ineligible",
    ]


class MemoryQueryResultV1(StrictProtocolModel):
    query_id: str = Field(min_length=1, max_length=160)
    as_of: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    considered_entries: list[QuarantinedMemoryEntryV1] = Field(min_length=1, max_length=100)
    eligible_memory_ids: list[str]
    ignored_entries: list[MemoryDispositionV1]
    unresolved_counter_evidence_refs: list[str]
    policy_override_allowed: Literal[False]
    trust_increase_allowed: Literal[False]
    raw_content_returned: Literal[False]

    @model_validator(mode="after")
    def validate_memory_query(self) -> MemoryQueryResultV1:
        as_of = parse_timestamp(self.as_of)
        memory_ids = [entry.memory_id for entry in self.considered_entries]
        if len(memory_ids) != len(set(memory_ids)):
            raise ValueError("memory query contains duplicate entries")
        if len(self.eligible_memory_ids) != len(set(self.eligible_memory_ids)):
            raise ValueError("memory query contains duplicate eligible ids")
        ignored_ids = [item.memory_id for item in self.ignored_entries]
        if len(ignored_ids) != len(set(ignored_ids)):
            raise ValueError("memory query contains duplicate ignored ids")
        if set(self.eligible_memory_ids).intersection(ignored_ids):
            raise ValueError("memory entry cannot be both eligible and ignored")
        if set(self.eligible_memory_ids).union(ignored_ids) != set(memory_ids):
            raise ValueError("memory query must classify every considered entry")
        by_id = {entry.memory_id: entry for entry in self.considered_entries}
        for memory_id in self.eligible_memory_ids:
            entry = by_id[memory_id]
            if not entry.eligible_as_supporting_evidence:
                raise ValueError("memory query marked an ineligible entry as evidence")
            if parse_timestamp(entry.observed_at) > as_of:
                raise ValueError("memory query marked a future entry as evidence")
            if parse_timestamp(entry.expires_at) <= as_of:
                raise ValueError("memory query marked an expired entry as evidence")
            if entry.counter_evidence_refs:
                raise ValueError("memory query ignored pending counter-evidence")
        if len(self.unresolved_counter_evidence_refs) != len(
            set(self.unresolved_counter_evidence_refs)
        ):
            raise ValueError("memory query contains duplicate counter-evidence refs")
        return self


class AgenticEvidenceContextV1(StrictProtocolModel):
    plan: AgenticPlanV1
    tool_results: list[AgenticToolResultV1] = Field(min_length=1, max_length=30)
    memory_query: MemoryQueryResultV1
    agentic_output_authority: Literal["supporting_evidence_only"]
    policy_override_allowed: Literal[False]
    gate_decision_from_agent: Literal[False]
    production_mutation_performed: Literal[False]

    @model_validator(mode="after")
    def validate_agentic_context(self) -> AgenticEvidenceContextV1:
        calls = {call.call_id: call for call in self.plan.calls}
        result_ids = [result.call_id for result in self.tool_results]
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("agentic evidence contains duplicate tool results")
        if set(result_ids) != set(calls):
            raise ValueError("agentic evidence must account for every planned tool call")
        for result in self.tool_results:
            call = calls[result.call_id]
            if result.tool_id != call.tool_id or result.effect != call.requested_effect:
                raise ValueError("agentic tool result does not match its planned call")
        return self


class EvolutionProposalV1(StrictProtocolModel):
    proposal_id: str = Field(min_length=1, max_length=160)
    change_kind: EvolutionChangeKind
    target_ref: str = Field(min_length=1, max_length=500)
    base_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposer_kind: Literal["agent", "human", "deterministic"]
    proposer_ref: str = Field(min_length=1, max_length=200)
    submitted_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    current_scope: DeliveryScope
    requested_scope: DeliveryScope
    evidence_refs: list[str] = Field(min_length=1, max_length=100)
    memory_refs: list[str] = Field(min_length=1, max_length=100)
    touches_hard_denies: bool
    weakens_required_evidence: bool
    expands_delivery_scope: bool
    expands_tool_authority: bool
    changes_verifier_or_signing: bool
    changes_revocation_semantics: bool
    requests_automatic_apply: bool
    requests_production_mutation: bool
    proposal_only: Literal[True]
    raw_patch_included: Literal[False]

    @model_validator(mode="after")
    def validate_evolution_proposal(self) -> EvolutionProposalV1:
        parse_timestamp(self.submitted_at)
        if self.base_digest_sha256 == self.candidate_digest_sha256:
            raise ValueError("evolution proposal must change the candidate digest")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evolution proposal contains duplicate evidence refs")
        if len(self.memory_refs) != len(set(self.memory_refs)):
            raise ValueError("evolution proposal contains duplicate memory refs")
        scope_expands = not scope_is_at_most(self.requested_scope, self.current_scope)
        if self.expands_delivery_scope != scope_expands:
            raise ValueError("evolution scope-expansion flag does not match requested scope")
        return self


class EvolutionControlEvidenceV1(StrictProtocolModel):
    control_type: EvolutionControlType
    status: EvolutionControlStatus
    evidence_ref: str | None = Field(default=None, max_length=500)
    actor_kind: Literal[
        "deterministic_verifier",
        "human_reconstructor",
        "risk_owner",
        "maintainer",
    ]
    actor_ref: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_control_evidence(self) -> EvolutionControlEvidenceV1:
        expected_actor = {
            EvolutionControlType.DETERMINISTIC_REPLAY: "deterministic_verifier",
            EvolutionControlType.CANARY: "deterministic_verifier",
            EvolutionControlType.ROLLBACK: "deterministic_verifier",
            EvolutionControlType.HUMAN_RECONSTRUCTION: "human_reconstructor",
            EvolutionControlType.RISK_OWNER_ACCEPTANCE: "risk_owner",
            EvolutionControlType.MAINTAINER_APPROVAL: "maintainer",
        }[self.control_type]
        if self.actor_kind != expected_actor:
            raise ValueError("evolution control actor kind does not match control type")
        if self.status == EvolutionControlStatus.MISSING:
            if self.evidence_ref is not None:
                raise ValueError("missing evolution control cannot include evidence")
        elif self.evidence_ref is None:
            raise ValueError("evaluated evolution control requires evidence")
        return self


class EvolutionControlSetV1(StrictProtocolModel):
    controls: list[EvolutionControlEvidenceV1] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def validate_control_set(self) -> EvolutionControlSetV1:
        control_types = [control.control_type for control in self.controls]
        if len(control_types) != len(set(control_types)):
            raise ValueError("evolution control set contains duplicate controls")
        if set(control_types) != set(EvolutionControlType):
            raise ValueError("evolution control set is incomplete")
        return self


class EvolutionGateDecisionV1(StrictProtocolModel):
    status: EvolutionDecisionStatus
    candidate_state: Literal["rejected", "pending", "local_candidate"]
    proposal_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reasons: list[str]
    automatic_apply_allowed: Literal[False]
    production_apply_allowed: Literal[False]
    trust_kernel_mutation_performed: Literal[False]
    release_performed: Literal[False]
    tool_or_memory_authority_used_as_final_basis: Literal[False]
    explicit_maintainer_apply_required: Literal[True]

    @model_validator(mode="after")
    def validate_evolution_decision(self) -> EvolutionGateDecisionV1:
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("evolution decision contains duplicate reasons")
        if self.status == EvolutionDecisionStatus.APPROVED_FOR_LOCAL_CANDIDATE:
            if self.candidate_state != "local_candidate" or self.reasons:
                raise ValueError("approved evolution candidate cannot have blocking reasons")
        elif self.status == EvolutionDecisionStatus.NEEDS_EVIDENCE:
            if self.candidate_state != "pending" or not self.reasons:
                raise ValueError("pending evolution candidate requires reasons")
        elif self.candidate_state != "rejected" or not self.reasons:
            raise ValueError("blocked evolution candidate requires rejection reasons")
        return self


class EvolutionReceiptProvenanceV1(StrictProtocolModel):
    envelope_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verifier: VerifierIdentityV1
    canonicalization: Literal["cbb-json-c14n-v1"]
    signing_status: Literal["locally_signed"]
    signature_algorithm: Literal["ed25519"]
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{86}$")
    signer: SignerIdentityV1
    created_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    expires_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    replay_nonce: str = Field(min_length=16, max_length=200)
    revocation: RevocationReferenceV1
    claim_boundary: ClaimBoundaryV1

    @model_validator(mode="after")
    def validate_evolution_provenance(self) -> EvolutionReceiptProvenanceV1:
        if parse_timestamp(self.expires_at) <= parse_timestamp(self.created_at):
            raise ValueError("evolution receipt provenance must expire after creation")
        if self.claim_boundary.maximum_scope != DeliveryScope.BLOCKED:
            raise ValueError("evolution signature cannot grant delivery authority")
        if "third-party signer identity" not in self.claim_boundary.not_claimed:
            raise ValueError("local evolution signature must disclaim third-party identity")
        return self


class EvolutionGateReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": EVOLUTION_GATE_RECEIPT_SCHEMA_VERSION},
    )

    schema_version: Literal["cbb.evolution-gate-receipt.v1"]
    evolution_receipt_id: str = Field(min_length=1, max_length=160)
    proposal: EvolutionProposalV1
    agentic_evidence: AgenticEvidenceContextV1
    controls: EvolutionControlSetV1
    decision: EvolutionGateDecisionV1
    issued_at: str = Field(min_length=1, max_length=64, pattern=TIMESTAMP_PATTERN)
    claim_boundary: ClaimBoundaryV1
    provenance: EvolutionReceiptProvenanceV1
    privacy: PrivacyBoundaryV1
    automatic_apply_performed: Literal[False]

    @model_validator(mode="after")
    def validate_evolution_receipt(self) -> EvolutionGateReceiptV1:
        issued_at = parse_timestamp(self.issued_at)
        if issued_at != parse_timestamp(self.provenance.created_at):
            raise ValueError("evolution provenance must be created when receipt is issued")
        if self.claim_boundary.maximum_scope != DeliveryScope.BLOCKED:
            raise ValueError("evolution receipt cannot grant delivery authority")
        if parse_timestamp(self.proposal.submitted_at) > issued_at:
            raise ValueError("evolution proposal cannot be submitted after receipt issuance")
        if parse_timestamp(self.agentic_evidence.plan.created_at) > issued_at:
            raise ValueError("agentic plan cannot be created after receipt issuance")
        if parse_timestamp(self.agentic_evidence.memory_query.as_of) > issued_at:
            raise ValueError("memory query cannot occur after receipt issuance")
        required_disclaimers = {
            "automatic policy application",
            "production authorization",
            "global protocol conformance",
        }
        if not required_disclaimers.issubset(self.claim_boundary.not_claimed):
            raise ValueError("evolution receipt claim boundary is incomplete")
        control_by_type = {
            control.control_type: control for control in self.controls.controls
        }
        human_controls = {
            EvolutionControlType.HUMAN_RECONSTRUCTION,
            EvolutionControlType.RISK_OWNER_ACCEPTANCE,
            EvolutionControlType.MAINTAINER_APPROVAL,
        }
        self_authorized = any(
            control_by_type[control_type].actor_ref == self.proposal.proposer_ref
            for control_type in human_controls
        ) or self.provenance.signer.signer_id == self.proposal.proposer_ref
        if (
            self_authorized
            and self.decision.status == EvolutionDecisionStatus.APPROVED_FOR_LOCAL_CANDIDATE
        ):
            raise ValueError("evolution proposer cannot authorize its own proposal")
        if not set(self.proposal.memory_refs).issubset(
            self.agentic_evidence.memory_query.eligible_memory_ids
        ):
            if self.decision.status == EvolutionDecisionStatus.APPROVED_FOR_LOCAL_CANDIDATE:
                raise ValueError("approved evolution candidate uses ineligible memory")
        protected_change = any(
            (
                self.proposal.touches_hard_denies,
                self.proposal.weakens_required_evidence,
                self.proposal.expands_delivery_scope,
                self.proposal.expands_tool_authority,
                self.proposal.changes_verifier_or_signing,
                self.proposal.changes_revocation_semantics,
                self.proposal.requests_automatic_apply,
                self.proposal.requests_production_mutation,
            )
        )
        if (
            protected_change
            and self.decision.status == EvolutionDecisionStatus.APPROVED_FOR_LOCAL_CANDIDATE
        ):
            raise ValueError("protected evolution change cannot be approved locally")
        if self.decision.status == EvolutionDecisionStatus.APPROVED_FOR_LOCAL_CANDIDATE:
            if any(
                control.status != EvolutionControlStatus.PASSED
                for control in self.controls.controls
            ):
                raise ValueError("approved evolution candidate requires every control")
        return self


PROTOCOL_MODELS: dict[str, type[StrictProtocolModel]] = {
    TRUST_POLICY_SCHEMA_VERSION: TrustPolicyV1,
    EVIDENCE_BUNDLE_SCHEMA_VERSION: EvidenceBundleV1,
    QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION: QualifiedReconstructionV1,
    GATE_DECISION_SCHEMA_VERSION: GateDecisionV1,
    DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION: DeliveryTrustReceiptV1,
    RECEIPT_PROVENANCE_SCHEMA_VERSION: ReceiptProvenanceV1,
    DELIVERY_OUTCOME_RECEIPT_SCHEMA_VERSION: DeliveryOutcomeReceiptV1,
    EVOLUTION_GATE_RECEIPT_SCHEMA_VERSION: EvolutionGateReceiptV1,
}
