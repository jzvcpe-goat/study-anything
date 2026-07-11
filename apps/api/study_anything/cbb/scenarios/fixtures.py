"""Deterministic vibe-coding scenario fixtures for CBB Protocol v1."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal

from study_anything.cbb.kernel.gate import evaluate_gate
from study_anything.cbb.protocol.canonical import canonical_sha256, model_payload
from study_anything.cbb.protocol.models import (
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
    TRUST_POLICY_SCHEMA_VERSION,
    AffectedPartyContractV1,
    ClaimBoundaryV1,
    DeliveryScenarioClass,
    DeliveryScenarioV1,
    DeliveryScope,
    EvidenceBundleV1,
    EvidenceItemV1,
    EvidenceRequirementV1,
    HumanCapabilityProfileV1,
    MinimumReconstructableUnitV1,
    ModelCapabilityProfileV1,
    MruResultV1,
    PrivacyBoundaryV1,
    QualifiedReconstructionV1,
    RecipientContractV1,
    ReconstructionBoundaryType,
    RiskBudgetV1,
    RiskOwnerContractV1,
    SafeguardRequirementV1,
    TrustPolicyV1,
)


FIXTURE_ROOT = Path("fixtures") / "cbb-v1-scenarios"
OBSERVED_AT = "2026-06-28T00:00:00Z"
VALID_UNTIL = "2026-09-26T00:00:00Z"


@dataclass(frozen=True)
class ScenarioSpec:
    case_id: str
    scenario_class: DeliveryScenarioClass
    maximum_scope: DeliveryScope
    recipient_kind: Literal[
        "self",
        "internal_operator",
        "public_demo_audience",
        "limited_beta_user",
        "paid_customer_operator",
        "production_operator",
        "regulated_subject",
    ]
    recipient_external: bool
    affected_party: bool
    risk_owner_required: bool
    safeguards: tuple[str, ...]
    reviewer_roles: tuple[str, ...]
    boundaries: tuple[ReconstructionBoundaryType, ...]
    additional_evidence: tuple[str, ...]
    omitted_evidence: tuple[str, ...] = ()
    regulated_or_irreversible: bool = False
    expected_status: Literal["allow", "block", "needs_evidence"] = "allow"


SCENARIO_SPECS = (
    ScenarioSpec(
        case_id="personal-local-prototype",
        scenario_class=DeliveryScenarioClass.PERSONAL_LOCAL_PROTOTYPE,
        maximum_scope=DeliveryScope.PERSONAL_LOCAL,
        recipient_kind="self",
        recipient_external=False,
        affected_party=False,
        risk_owner_required=False,
        safeguards=(),
        reviewer_roles=("qualified_reviewer",),
        boundaries=(
            ReconstructionBoundaryType.INTENT_AND_NON_GOALS,
            ReconstructionBoundaryType.CRITICAL_FAILURE_PATH,
            ReconstructionBoundaryType.ROLLBACK_TRIGGER,
        ),
        additional_evidence=(),
    ),
    ScenarioSpec(
        case_id="public-fake-data-demo",
        scenario_class=DeliveryScenarioClass.PUBLIC_FAKE_DATA_DEMO,
        maximum_scope=DeliveryScope.PUBLIC_DEMO,
        recipient_kind="public_demo_audience",
        recipient_external=True,
        affected_party=False,
        risk_owner_required=False,
        safeguards=("disclosure_notice",),
        reviewer_roles=("qualified_reviewer",),
        boundaries=(
            ReconstructionBoundaryType.INTENT_AND_NON_GOALS,
            ReconstructionBoundaryType.CRITICAL_FAILURE_PATH,
            ReconstructionBoundaryType.AFFECTED_PARTIES_AND_RECIPIENT,
            ReconstructionBoundaryType.ROLLBACK_TRIGGER,
        ),
        additional_evidence=(),
    ),
    ScenarioSpec(
        case_id="limited-beta",
        scenario_class=DeliveryScenarioClass.LIMITED_BETA,
        maximum_scope=DeliveryScope.LIMITED_BETA,
        recipient_kind="limited_beta_user",
        recipient_external=True,
        affected_party=True,
        risk_owner_required=True,
        safeguards=("disclosure_notice", "appeal_path", "redress_path"),
        reviewer_roles=(
            "qualified_reviewer",
            "technical_reviewer",
            "operational_reviewer",
        ),
        boundaries=tuple(ReconstructionBoundaryType),
        additional_evidence=("rollback_replay",),
    ),
    ScenarioSpec(
        case_id="paid-customer-candidate",
        scenario_class=DeliveryScenarioClass.PAID_CUSTOMER_CANDIDATE,
        maximum_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
        recipient_kind="paid_customer_operator",
        recipient_external=True,
        affected_party=True,
        risk_owner_required=True,
        safeguards=("disclosure_notice", "appeal_path", "redress_path"),
        reviewer_roles=(
            "qualified_reviewer",
            "technical_reviewer",
            "operational_reviewer",
        ),
        boundaries=tuple(ReconstructionBoundaryType),
        additional_evidence=("rollback_replay", "external_eval_receipt"),
    ),
    ScenarioSpec(
        case_id="production-candidate-blocked",
        scenario_class=DeliveryScenarioClass.PRODUCTION_CANDIDATE,
        maximum_scope=DeliveryScope.PRODUCTION_CANDIDATE,
        recipient_kind="production_operator",
        recipient_external=True,
        affected_party=True,
        risk_owner_required=True,
        safeguards=("disclosure_notice", "appeal_path", "redress_path"),
        reviewer_roles=(
            "qualified_reviewer",
            "technical_reviewer",
            "operational_reviewer",
            "domain_reviewer",
            "security_reviewer",
            "deployment_operator",
        ),
        boundaries=tuple(ReconstructionBoundaryType),
        additional_evidence=(
            "rollback_replay",
            "domain_review",
            "security_review",
            "deployment_approval",
            "affected_party_protection",
        ),
        omitted_evidence=(
            "domain_review",
            "security_review",
            "deployment_approval",
            "affected_party_protection",
        ),
        expected_status="needs_evidence",
    ),
    ScenarioSpec(
        case_id="regulated-or-irreversible-blocked",
        scenario_class=DeliveryScenarioClass.REGULATED_OR_IRREVERSIBLE,
        maximum_scope=DeliveryScope.BLOCKED,
        recipient_kind="regulated_subject",
        recipient_external=True,
        affected_party=True,
        risk_owner_required=False,
        safeguards=("disclosure_notice", "appeal_path", "redress_path"),
        reviewer_roles=("qualified_reviewer", "domain_reviewer"),
        boundaries=tuple(ReconstructionBoundaryType),
        additional_evidence=(),
        regulated_or_irreversible=True,
        expected_status="block",
    ),
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


def _claim(scope: DeliveryScope, text: str) -> ClaimBoundaryV1:
    return ClaimBoundaryV1(
        current_claim=text,
        maximum_scope=scope,
        not_claimed=[
            "production approval",
            "legal or security certification",
            "customer outcome guarantee",
            "general model correctness",
            "permanent global human or model qualification",
        ],
    )


def _safeguard(kind: str, required: bool) -> SafeguardRequirementV1:
    return SafeguardRequirementV1(
        required=required,
        evidence_type=kind if required else None,
        mechanism_ref=f"mechanism:{kind}" if required else None,
        human_fallback_required=required and kind in {"appeal_path", "redress_path"},
    )


def _scenario(spec: ScenarioSpec) -> DeliveryScenarioV1:
    scenario_ref = f"scenario:vibe-coded-app:{spec.case_id}"
    risk_owner_scope = (
        spec.maximum_scope if spec.risk_owner_required else DeliveryScope.BLOCKED
    )
    return DeliveryScenarioV1(
        scenario_ref=scenario_ref,
        scenario_class=spec.scenario_class,
        project_ref="project:vibe-coded-app",
        model_ref="model:fixture-agent-v1",
        maximum_scope=spec.maximum_scope,
        recipient=RecipientContractV1(
            recipient_ref=f"recipient:{spec.case_id}",
            recipient_kind=spec.recipient_kind,
            external=spec.recipient_external,
            automatic_execution_authority=False,
        ),
        risk_owner=RiskOwnerContractV1(
            required=spec.risk_owner_required,
            risk_owner_ref=(
                f"risk-owner:{spec.case_id}" if spec.risk_owner_required else None
            ),
            accepted_scope_ceiling=risk_owner_scope,
            acceptance_evidence_type=(
                "risk_owner_acceptance" if spec.risk_owner_required else None
            ),
        ),
        affected_parties=(
            [
                AffectedPartyContractV1(
                    party_ref=f"affected-party:{spec.case_id}",
                    party_kind="scenario_user",
                    impact_classes=["service_access", "decision_or_experience"],
                    disclosure_required=True,
                    appeal_required=True,
                    redress_required=True,
                )
            ]
            if spec.affected_party
            else []
        ),
        disclosure=_safeguard(
            "disclosure_notice",
            "disclosure_notice" in spec.safeguards,
        ),
        appeal=_safeguard("appeal_path", "appeal_path" in spec.safeguards),
        redress=_safeguard("redress_path", "redress_path" in spec.safeguards),
        impact_classes=[
            "fake_data_only"
            if spec.scenario_class
            in {
                DeliveryScenarioClass.PERSONAL_LOCAL_PROTOTYPE,
                DeliveryScenarioClass.PUBLIC_FAKE_DATA_DEMO,
            }
            else "real_delivery_candidate"
        ],
        regulated_or_irreversible=spec.regulated_or_irreversible,
    )


def _mrus(spec: ScenarioSpec) -> list[MinimumReconstructableUnitV1]:
    return [
        MinimumReconstructableUnitV1(
            mru_ref=f"mru:{spec.case_id}:{boundary.value}",
            boundary_type=boundary,
            required_for_scope=spec.maximum_scope,
            evidence_kind="active_reconstruction",
            blocks_promotion=True,
        )
        for boundary in spec.boundaries
    ]


def _required_evidence(spec: ScenarioSpec) -> list[EvidenceRequirementV1]:
    evidence_types = [
        "failure_contract",
        "sandbox_receipt",
        "qualified_reconstruction",
        "dual_loop_gate",
    ]
    if spec.risk_owner_required:
        evidence_types.append("risk_owner_acceptance")
    evidence_types.extend(spec.safeguards)
    evidence_types.extend(spec.additional_evidence)
    return [
        EvidenceRequirementV1(
            evidence_type=evidence_type,
            required_for_scope=spec.maximum_scope,
            blocking=evidence_type != "external_eval_receipt",
        )
        for evidence_type in evidence_types
    ]


def _policy(spec: ScenarioSpec) -> TrustPolicyV1:
    scenario = _scenario(spec)
    model_observed = spec.maximum_scope != DeliveryScope.BLOCKED
    required_roles = list(spec.reviewer_roles)
    if spec.risk_owner_required:
        required_roles.append("risk_owner")
    return TrustPolicyV1(
        schema_version=TRUST_POLICY_SCHEMA_VERSION,
        policy_id=f"cbb-policy:{spec.case_id}",
        subject_ref=f"artifact:vibe-coded-app:{spec.case_id}",
        scenario_ref=scenario.scenario_ref,
        scenario=scenario,
        model_capability_profile=ModelCapabilityProfileV1(
            profile_id=f"model-capability:{spec.case_id}",
            model_ref=scenario.model_ref,
            scenario_refs=[scenario.scenario_ref],
            task_types=["vibe_coded_web_application"],
            status="observed" if model_observed else "unproven",
            maximum_autonomy_scope=spec.maximum_scope,
            evidence_refs=(
                [f"model-replay:{spec.case_id}"] if model_observed else []
            ),
            counter_evidence_refs=[],
            known_failure_modes=[
                "generated_tests_may_miss_cross_boundary_effects",
                "model_self_review_is_not_final_authority",
            ],
            observed_at=OBSERVED_AT,
            valid_until=VALID_UNTIL,
            vendor_claims_sufficient=False,
        ),
        maximum_scope=spec.maximum_scope,
        hard_denies=[
            "ai_review_only_trust",
            "irreversible_external_effect",
            "production_mutation",
            "unbounded_real_user_exposure",
        ],
        risk_budget=RiskBudgetV1(
            level="blocked" if spec.maximum_scope == DeliveryScope.BLOCKED else "medium",
            production_mutation_allowed=False,
            real_user_exposure_allowed=False,
            irreversible_external_effects_allowed=False,
        ),
        required_evidence=_required_evidence(spec),
        required_roles=required_roles,
        required_mrus=_mrus(spec),
        claim_boundary=_claim(
            spec.maximum_scope,
            f"This fixture evaluates only the {spec.case_id} scenario boundary.",
        ),
        privacy=_privacy(),
        created_at=OBSERVED_AT,
    )


def _evidence(spec: ScenarioSpec, policy: TrustPolicyV1) -> EvidenceBundleV1:
    evidence: list[EvidenceItemV1] = []
    for requirement in policy.required_evidence:
        if requirement.evidence_type == "qualified_reconstruction":
            continue
        if requirement.evidence_type in spec.omitted_evidence:
            continue
        evidence.append(
            EvidenceItemV1(
                evidence_id=f"evidence:{spec.case_id}:{requirement.evidence_type}",
                evidence_type=requirement.evidence_type,
                status="passed",
                source_schema_version="cbb.scenario-evidence.v1",
                source_ref=f"evidence/{requirement.evidence_type}.json",
                supported_scope=spec.maximum_scope,
                metadata={"scenario_ref": policy.scenario_ref},
            )
        )
    if spec.regulated_or_irreversible:
        evidence.append(
            EvidenceItemV1(
                evidence_id=f"evidence:{spec.case_id}:hard-deny",
                evidence_type="hard_deny:irreversible_external_effect",
                status="passed",
                source_schema_version="cbb.hard-deny-signal.v1",
                source_ref="evidence/irreversible-effect.json",
                supported_scope=DeliveryScope.BLOCKED,
                metadata={"observed": True},
            )
        )
    return EvidenceBundleV1(
        schema_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
        bundle_id=f"cbb-evidence:{spec.case_id}",
        subject_ref=policy.subject_ref,
        policy_ref=policy.policy_id,
        evidence=evidence,
        maximum_supported_scope=spec.maximum_scope,
        claim_boundary=_claim(
            spec.maximum_scope,
            f"Evidence is bounded to the {spec.case_id} fixture only.",
        ),
        privacy=_privacy(),
        created_at=OBSERVED_AT,
    )


def _reconstruction(
    spec: ScenarioSpec,
    policy: TrustPolicyV1,
) -> QualifiedReconstructionV1:
    qualified_scope = (
        DeliveryScope.SANDBOX_ONLY
        if spec.maximum_scope == DeliveryScope.BLOCKED
        else spec.maximum_scope
    )
    mru_results = [
        MruResultV1(
            mru_ref=requirement.mru_ref,
            boundary_type=requirement.boundary_type,
            status="passed",
            evidence_refs=[f"reconstruction/{requirement.mru_ref}.json"],
        )
        for requirement in policy.required_mrus
    ]
    return QualifiedReconstructionV1(
        schema_version=QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
        reconstruction_id=f"cbb-reconstruction:{spec.case_id}",
        policy_ref=policy.policy_id,
        reviewer_ref=f"reviewer:{spec.case_id}",
        scenario_ref=policy.scenario_ref,
        project_ref=policy.scenario.project_ref,
        reviewer_roles=list(spec.reviewer_roles),
        status="passed",
        qualified_scope=qualified_scope,
        active_reconstruction=True,
        passive_attention_only=False,
        required_mrus_total=len(mru_results),
        required_mrus_passed=len(mru_results),
        missing_mru_refs=[],
        mru_results=mru_results,
        human_capability_profile=HumanCapabilityProfileV1(
            profile_id=f"human-capability:{spec.case_id}",
            human_ref=f"reviewer:{spec.case_id}",
            project_ref=policy.scenario.project_ref,
            scenario_refs=[policy.scenario_ref],
            qualified_roles=list(spec.reviewer_roles),
            boundary_types=list(spec.boundaries),
            status="active",
            maximum_scope=qualified_scope,
            evidence_refs=[f"human-reconstruction:{spec.case_id}"],
            counter_evidence_refs=[],
            observed_at=OBSERVED_AT,
            valid_until=VALID_UNTIL,
            permanent_global_label=False,
        ),
        evidence_refs=[f"human-reconstruction:{spec.case_id}"],
        observed_at=OBSERVED_AT,
        valid_until=VALID_UNTIL,
        claim_boundary=_claim(
            qualified_scope,
            f"The reviewer is qualified only for {spec.case_id} and this time window.",
        ),
        privacy=_privacy(),
    )


def build_scenario_cases() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for spec in SCENARIO_SPECS:
        policy = _policy(spec)
        evidence = _evidence(spec, policy)
        reconstruction = _reconstruction(spec, policy)
        decision = evaluate_gate(policy, evidence, reconstruction)
        expected_scope = (
            spec.maximum_scope
            if spec.expected_status == "allow"
            else DeliveryScope.BLOCKED
        )
        cases[spec.case_id] = {
            "case_id": spec.case_id,
            "policy_digest_sha256": canonical_sha256(policy),
            "inputs": {
                "trust_policy": model_payload(policy),
                "evidence_bundle": model_payload(evidence),
                "qualified_reconstruction": model_payload(reconstruction),
            },
            "decision": model_payload(decision),
            "expected": {
                "status": spec.expected_status,
                "approved_scope": expected_scope.value,
                "omitted_evidence": list(spec.omitted_evidence),
            },
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
        for case_id, payload in build_scenario_cases().items()
    }
