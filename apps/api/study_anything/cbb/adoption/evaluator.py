"""Deterministic controlled-adoption evaluation with no new release authority."""

from __future__ import annotations

from typing import Literal

from study_anything.cbb.adoption.attestation_intake import (
    evaluate_external_adoption_attestation,
)
from study_anything.cbb.adoption.attestation_models import (
    AdoptionAttestationSourceClass,
    AdoptionAttestationState,
    ExternalAdoptionAttestationEnvelopeV1,
    ExternalAdoptionAttestationReceiptV1,
    ExternalAdoptionExpectedScopeV1,
)
from study_anything.cbb.adoption.models import (
    AdoptionEvidenceClass,
    AdoptionMode,
    AdoptionObservationKind,
    ControlledAdoptionCaseV1,
    ControlledAdoptionReceiptV1,
    ControlledAdoptionStatus,
)
from study_anything.cbb.outcomes.signing import (
    verify_outcome_receipt,
    verify_outcome_source_binding,
)
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    TrustDegradationAction,
    scope_is_at_most,
)
from study_anything.cbb.provenance.signing import (
    OfflineProvenancePackageV1,
    verify_offline_package,
)


ADOPTION_NOT_CLAIMED = [
    "new delivery authority",
    "production approval",
    "automatic customer sending",
    "general customer outcome",
    "independent security audit completion",
    "external adoption without an independently verified adoption attestation",
    "scope beyond the source Delivery Clearance receipt",
]


def _blocked_status(case: ControlledAdoptionCaseV1) -> ControlledAdoptionStatus:
    if case.reopen_requested:
        return ControlledAdoptionStatus.REOPEN_REQUIRED
    return ControlledAdoptionStatus.BLOCKED


def evaluate_controlled_adoption(
    package: OfflineProvenancePackageV1,
    case: ControlledAdoptionCaseV1,
    *,
    expected_release_scope_commit: str,
    expected_conformance_pack_sha256: str,
    revoked_source_handles: set[str] | None = None,
    external_attestation_expected_scope: ExternalAdoptionExpectedScopeV1 | None = None,
    external_attestation_envelope: ExternalAdoptionAttestationEnvelopeV1 | None = None,
) -> ControlledAdoptionReceiptV1:
    """Evaluate one observation; adoption evidence can only maintain or reduce scope."""

    revoked_handles = set(revoked_source_handles or ())
    source = package.receipt_provenance
    binding = case.binding
    source_verification = verify_offline_package(
        package,
        now=case.observed_at,
        revoked_handles=revoked_handles,
    )
    attestation_context_complete = (
        external_attestation_expected_scope is not None
        and external_attestation_envelope is not None
    )
    attestation_context_absent = (
        external_attestation_expected_scope is None
        and external_attestation_envelope is None
    )
    external_attestation_receipt: ExternalAdoptionAttestationReceiptV1 | None = None
    if attestation_context_complete:
        assert external_attestation_expected_scope is not None
        assert external_attestation_envelope is not None
        external_attestation_receipt = evaluate_external_adoption_attestation(
            external_attestation_expected_scope,
            external_attestation_envelope,
            evaluated_at=external_attestation_envelope.submitted_at,
        )
    case_digest = canonical_sha256(case.model_dump(mode="json"))
    attestation_digest = (
        canonical_sha256(external_attestation_receipt.model_dump(mode="json"))
        if external_attestation_receipt is not None
        else None
    )
    attestation_binding = (
        external_attestation_receipt.binding
        if external_attestation_receipt is not None
        else None
    )
    attestation = (
        external_attestation_envelope.attestation
        if external_attestation_envelope is not None
        else None
    )
    expected_outcome_ref = (
        case.outcome_receipt.outcome_receipt_id
        if case.outcome_receipt is not None
        else None
    )
    external_attestation_valid = bool(
        case.evidence_class == AdoptionEvidenceClass.EXTERNAL_ADOPTER
        and case.real_adopter_evidence_claimed
        and external_attestation_receipt is not None
        and external_attestation_receipt.state
        == AdoptionAttestationState.EXTERNAL_ATTESTATION_VERIFIED
        and external_attestation_receipt.source_class
        == AdoptionAttestationSourceClass.EXTERNAL_ATTESTATION
        and external_attestation_receipt.real_adopter_evidence_accepted
        and external_attestation_receipt.external_identity_attested
        and external_attestation_receipt.signature_verified
        and external_attestation_receipt.observation_execution_completed
        and attestation_binding is not None
        and attestation_binding.repository == "jzvcpe-goat/study-anything"
        and attestation_binding.release_scope_commit
        == expected_release_scope_commit
        and attestation_binding.protocol_version == binding.protocol_version
        and attestation_binding.conformance_pack_sha256
        == expected_conformance_pack_sha256
        and attestation_binding.source_package_digest_sha256
        == binding.source_package_digest_sha256
        and attestation_binding.source_delivery_receipt_ref
        == binding.source_delivery_receipt_ref
        and attestation_binding.source_clearance_revocation_handle
        == binding.source_clearance_revocation_handle
        and attestation_binding.source_approved_scope
        == binding.source_approved_scope
        and attestation_binding.adoption_case_id == case.case_id
        and attestation_binding.adoption_case_sha256 == case_digest
        and attestation is not None
        and attestation.adoption_mode == case.adoption_mode
        and attestation.observation_kind == case.observation_kind
        and attestation.requested_scope == case.effect_boundary.requested_scope
        and attestation.outcome_receipt_ref == expected_outcome_ref
        and attestation.observation.observed_at == case.observed_at
    )
    checks = {
        "release_scope_commit_bound": (
            binding.release_scope_commit == expected_release_scope_commit
        ),
        "protocol_version_bound": binding.protocol_version == "1.0.0",
        "source_package_ref_bound": binding.source_package_ref == package.package_id,
        "source_package_digest_bound": (
            binding.source_package_digest_sha256 == source.package_digest_sha256
        ),
        "source_delivery_receipt_bound": (
            binding.source_delivery_receipt_ref
            == package.delivery_trust_receipt.receipt_id
        ),
        "source_revocation_handle_bound": (
            binding.source_clearance_revocation_handle == source.revocation.handle
        ),
        "source_scope_bound": (
            binding.source_approved_scope == package.gate_decision.approved_scope
        ),
        "conformance_pack_digest_bound": (
            binding.conformance_pack_sha256 == expected_conformance_pack_sha256
        ),
        "source_clearance_verified": source_verification.passed,
        "source_not_previously_revoked": (
            not case.source_revoked_before_observation
            and source.revocation.handle not in revoked_handles
        ),
        "requested_scope_not_expanded": scope_is_at_most(
            case.effect_boundary.requested_scope,
            binding.source_approved_scope,
        ),
        "operator_reconstruction_present": case.operator_reconstruction_present,
        "risk_owner_reacceptance_present_when_required": (
            case.observation_kind != AdoptionObservationKind.PASS
            or not (
                case.adoption_mode == AdoptionMode.CANARY
                or case.effect_boundary.real_user_exposure_observed
                or case.effect_boundary.external_effect_observed
            )
            or case.risk_owner_reacceptance_present
        ),
        "evidence_class_matches_mode": (
            case.evidence_class == AdoptionEvidenceClass.SYNTHETIC_FIXTURE
            or (
                case.evidence_class == AdoptionEvidenceClass.LOCAL_SHADOW
                and case.adoption_mode == AdoptionMode.SHADOW
            )
            or (
                case.evidence_class == AdoptionEvidenceClass.LOCAL_DOGFOOD
                and case.adoption_mode == AdoptionMode.DOGFOOD
            )
            or (
                case.evidence_class == AdoptionEvidenceClass.EXTERNAL_ADOPTER
                and case.adoption_mode == AdoptionMode.CANARY
            )
        ),
        "external_adopter_attestation_supported": (
            (
                case.evidence_class != AdoptionEvidenceClass.EXTERNAL_ADOPTER
                and not case.real_adopter_evidence_claimed
                and attestation_context_absent
            )
            or (attestation_context_complete and external_attestation_valid)
        ),
        "no_production_mutation": (
            not case.effect_boundary.production_mutation_performed
        ),
        "no_automatic_customer_send": (
            not case.effect_boundary.automatic_customer_send_performed
        ),
        "real_user_exposure_within_scope": (
            not case.effect_boundary.real_user_exposure_observed
            or binding.source_approved_scope
            in {
                DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                DeliveryScope.LIMITED_BETA,
                DeliveryScope.PRODUCTION_CANDIDATE,
            }
        ),
        "external_effect_within_scope": (
            case.observation_kind
            in {
                AdoptionObservationKind.INCIDENT,
                AdoptionObservationKind.ROLLBACK,
                AdoptionObservationKind.REVOCATION,
                AdoptionObservationKind.REOPEN,
            }
            or not case.effect_boundary.external_effect_observed
            or binding.source_approved_scope
            in {
                DeliveryScope.PUBLIC_DEMO,
                DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                DeliveryScope.LIMITED_BETA,
                DeliveryScope.PRODUCTION_CANDIDATE,
            }
        ),
    }

    outcome = case.outcome_receipt
    outcome_status: Literal["monitored", "degraded", "frozen", "revoked"] | None = None
    trust_action: str | None = None
    outcome_ref: str | None = None
    if outcome is not None:
        outcome_ref = outcome.outcome_receipt_id
        outcome_status = outcome.status
        trust_action = outcome.trust_update.action.value
        outcome_verification = verify_outcome_receipt(
            package,
            outcome,
            now=case.observed_at,
        )
        checks["outcome_signature_verified"] = outcome_verification.passed
        checks["outcome_source_bound"] = not verify_outcome_source_binding(
            package,
            outcome,
        )
    else:
        checks["outcome_signature_verified"] = True
        checks["outcome_source_bound"] = True

    blocking_reasons = sorted(name for name, passed in checks.items() if not passed)
    if case.reopen_requested:
        blocking_reasons.append("fresh_clearance_required_for_reopen")

    if blocking_reasons:
        status = _blocked_status(case)
        resulting_scope = DeliveryScope.BLOCKED
        authorization_delta: Literal["none", "narrowed", "blocked"] = "blocked"
    elif outcome is None or (
        outcome.trust_update.action
        == TrustDegradationAction.MAINTAIN_CURRENT_CEILING
    ):
        status = ControlledAdoptionStatus.OBSERVED
        resulting_scope = case.effect_boundary.requested_scope
        authorization_delta = "none"
    elif outcome.trust_update.action == TrustDegradationAction.NARROW_SCOPE:
        if outcome.rollback.status == "succeeded":
            status = ControlledAdoptionStatus.ROLLED_BACK
        else:
            status = ControlledAdoptionStatus.INCIDENT_RECORDED
        resulting_scope = outcome.trust_update.resulting_scope
        authorization_delta = "narrowed"
    elif outcome.trust_update.action == TrustDegradationAction.FREEZE_RECIPE:
        status = ControlledAdoptionStatus.INCIDENT_RECORDED
        resulting_scope = DeliveryScope.BLOCKED
        authorization_delta = "blocked"
    else:
        status = ControlledAdoptionStatus.REVOKED
        resulting_scope = DeliveryScope.BLOCKED
        authorization_delta = "blocked"

    if case.observation_kind == AdoptionObservationKind.BLOCK and status == ControlledAdoptionStatus.OBSERVED:
        status = ControlledAdoptionStatus.BLOCKED
        resulting_scope = DeliveryScope.BLOCKED
        authorization_delta = "blocked"
        blocking_reasons.append("fixture_expected_block")

    reasons = sorted(
        set(
            blocking_reasons
            or [
                f"controlled_adoption:{status.value}",
                "no_new_delivery_authority",
            ]
        )
    )
    receipt_material: dict[str, object] = {
        "case": case.model_dump(mode="json"),
        "checks": checks,
        "status": status.value,
        "resulting_scope": resulting_scope.value,
    }
    if external_attestation_receipt is not None:
        receipt_material.update(
            {
                "external_attestation_receipt_ref": (
                    external_attestation_receipt.receipt_id
                ),
                "external_attestation_receipt_sha256": attestation_digest,
            }
        )
    receipt_digest = canonical_sha256(receipt_material)
    return ControlledAdoptionReceiptV1(
        schema_version="cbb.controlled-adoption-receipt.v1",
        receipt_id=f"controlled-adoption:{receipt_digest[:32]}",
        case_id=case.case_id,
        evidence_class=case.evidence_class,
        adoption_mode=case.adoption_mode,
        observation_kind=case.observation_kind,
        status=status,
        binding=binding,
        requested_scope=case.effect_boundary.requested_scope,
        resulting_scope=resulting_scope,
        outcome_receipt_ref=outcome_ref,
        outcome_status=outcome_status,
        trust_action=trust_action,
        external_attestation_receipt_ref=(
            external_attestation_receipt.receipt_id
            if external_attestation_receipt is not None
            else None
        ),
        external_attestation_receipt_sha256=attestation_digest,
        authorization_delta=authorization_delta,
        checks=checks,
        reasons=reasons,
        real_adopter_evidence=external_attestation_valid,
        customer_delivery_authorized=False,
        production_authorized=False,
        audit_completed=False,
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "This receipt records bounded controlled-adoption behavior against an "
                "existing Delivery Clearance package; it grants no new release authority."
            ),
            maximum_scope=resulting_scope,
            not_claimed=ADOPTION_NOT_CLAIMED,
        ),
        privacy=PrivacyBoundaryV1(
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
        ),
        observed_at=case.observed_at,
    )
