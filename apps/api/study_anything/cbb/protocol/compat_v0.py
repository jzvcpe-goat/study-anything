"""Deterministic, scope-narrowing adapters from shipped v0 receipts to v1."""

from __future__ import annotations

from typing import Any, Literal, Mapping

from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    CANONICALIZATION_ALGORITHM,
    DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION,
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    GATE_DECISION_SCHEMA_VERSION,
    QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
    RECEIPT_PROVENANCE_SCHEMA_VERSION,
    TRUST_POLICY_SCHEMA_VERSION,
    ClaimBoundaryV1,
    DeliveryScope,
    DeliveryTrustReceiptV1,
    EvidenceBundleV1,
    EvidenceItemV1,
    EvidenceRequirementV1,
    GateDecisionV1,
    PrivacyBoundaryV1,
    QualifiedReconstructionV1,
    ReceiptProvenanceV1,
    RiskBudgetV1,
    TrustPolicyV1,
    VerifierIdentityV1,
    parse_timestamp,
    scope_is_at_most,
)
from study_anything.core import delivery_trust, dual_loop


DEFAULT_OBSERVED_AT = dual_loop.DETERMINISTIC_TIMESTAMP
DEFAULT_VALID_UNTIL = "2026-09-26T00:00:00Z"


class CompatibilityMappingError(ValueError):
    """Raised when v0 evidence cannot be mapped without increasing authority."""


def privacy_boundary() -> PrivacyBoundaryV1:
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


def assert_scope_not_expanded(source_scope: DeliveryScope, target_scope: DeliveryScope) -> None:
    if not scope_is_at_most(target_scope, source_scope):
        raise CompatibilityMappingError(
            f"scope expansion rejected: {source_scope.value} -> {target_scope.value}"
        )


def failure_contract_to_trust_policy(
    failure_contract: Mapping[str, Any],
) -> TrustPolicyV1:
    contract = dual_loop.validate_failure_contract(failure_contract)
    maximum_scope = (
        DeliveryScope.BLOCKED
        if contract["risk"]["level"] == "blocked"
        else DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF
    )
    return TrustPolicyV1(
        schema_version=TRUST_POLICY_SCHEMA_VERSION,
        policy_id=f"cbb-policy:{contract['contract_id']}",
        subject_ref=str(contract["candidate_artifact_ref"]),
        scenario_ref=str(contract["task_ref"]),
        maximum_scope=maximum_scope,
        hard_denies=[
            "ai_review_only_trust",
            "irreversible_external_effect",
            "production_mutation",
            "unbounded_real_user_exposure",
        ],
        risk_budget=RiskBudgetV1(
            level=contract["risk"]["budget_level"],
            production_mutation_allowed=False,
            real_user_exposure_allowed=False,
            irreversible_external_effects_allowed=False,
        ),
        required_evidence=[
            EvidenceRequirementV1(
                evidence_type="failure_contract",
                required_for_scope=DeliveryScope.SANDBOX_ONLY,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="sandbox_receipt",
                required_for_scope=DeliveryScope.SANDBOX_ONLY,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="qualified_reconstruction",
                required_for_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="dual_loop_gate",
                required_for_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="delivery_trust_receipt",
                required_for_scope=DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
                blocking=True,
            ),
        ],
        required_roles=["qualified_reviewer"],
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "The candidate may be evaluated up to the mapped v0 delivery scope only."
            ),
            maximum_scope=maximum_scope,
            not_claimed=[
                "production approval",
                "portable signed attestation",
                "customer outcome guarantee",
                "general model correctness",
            ],
        ),
        privacy=privacy_boundary(),
        created_at=str(contract.get("created_at") or dual_loop.DETERMINISTIC_TIMESTAMP),
    )


def failure_and_sandbox_to_evidence_bundle(
    failure_contract: Mapping[str, Any],
    sandbox_receipt: Mapping[str, Any],
    policy: TrustPolicyV1,
) -> EvidenceBundleV1:
    contract = dual_loop.validate_failure_contract(failure_contract)
    sandbox = dual_loop.validate_sandbox_receipt(sandbox_receipt)
    if sandbox["contract_id"] != contract["contract_id"]:
        raise CompatibilityMappingError("sandbox contract_id does not match failure contract")
    contained = all(
        isinstance(item, Mapping)
        and item.get("containment_status") == "contained"
        and item.get("propagated") is False
        for item in sandbox.get("observed_failures", [])
    )
    rollback_passed = bool(sandbox.get("rollback", {}).get("available")) and bool(
        sandbox.get("rollback", {}).get("rehearsed")
    )
    sandbox_passed = (
        sandbox["status"] == "passed"
        and bool(sandbox["risk_budget"]["within_budget"])
        and contained
        and rollback_passed
    )
    supported_scope = (
        DeliveryScope.SANDBOX_ONLY if sandbox_passed else DeliveryScope.BLOCKED
    )
    return EvidenceBundleV1(
        schema_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
        bundle_id=f"cbb-evidence:{sandbox['sandbox_run_id']}",
        subject_ref=policy.subject_ref,
        policy_ref=policy.policy_id,
        evidence=[
            EvidenceItemV1(
                evidence_id=f"evidence:{contract['contract_id']}",
                evidence_type="failure_contract",
                status="passed",
                source_schema_version=dual_loop.FAILURE_CONTRACT_SCHEMA_VERSION,
                source_ref="failure-contract.json",
                supported_scope=DeliveryScope.SANDBOX_ONLY,
                metadata={
                    "risk_level": contract["risk"]["level"],
                    "rollback_required": contract["failure_boundaries"]["rollback_required"],
                },
            ),
            EvidenceItemV1(
                evidence_id=f"evidence:{sandbox['sandbox_run_id']}",
                evidence_type="sandbox_receipt",
                status="passed" if sandbox_passed else "failed",
                source_schema_version=dual_loop.SANDBOX_RECEIPT_SCHEMA_VERSION,
                source_ref="sandbox-receipt.json",
                supported_scope=supported_scope,
                metadata={
                    "contained": contained,
                    "within_budget": bool(sandbox["risk_budget"]["within_budget"]),
                    "rollback_rehearsed": rollback_passed,
                },
            ),
        ],
        maximum_supported_scope=supported_scope,
        claim_boundary=ClaimBoundaryV1(
            current_claim="The mapped v0 sandbox evidence supports this scope only.",
            maximum_scope=supported_scope,
            not_claimed=[
                "human reconstruction completion",
                "customer handoff approval",
                "portable signed attestation",
                "production approval",
            ],
        ),
        privacy=privacy_boundary(),
        created_at=str(sandbox.get("executed_at") or dual_loop.DETERMINISTIC_TIMESTAMP),
    )


def attention_summary_to_qualified_reconstruction(
    attention_summary: Mapping[str, Any] | None,
    policy: TrustPolicyV1,
    *,
    observed_at: str = DEFAULT_OBSERVED_AT,
    valid_until: str | None = None,
) -> QualifiedReconstructionV1:
    summary: dict[str, Any] | None = None
    if attention_summary is not None:
        summary = dual_loop.validate_attention_summary(attention_summary)
    effective_valid_until = str(
        valid_until
        or (summary or {}).get("valid_until")
        or DEFAULT_VALID_UNTIL
    )
    expired = parse_timestamp(effective_valid_until) <= parse_timestamp(observed_at)
    status: Literal["passed", "failed", "missing", "stale"]
    if summary is None:
        status = "missing"
    elif expired:
        status = "stale"
    elif summary["status"] == "passed":
        status = "passed"
    else:
        status = "failed"
    passed = status == "passed"
    return QualifiedReconstructionV1(
        schema_version=QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
        reconstruction_id=(
            f"cbb-reconstruction:{summary['summary_id']}"
            if summary is not None
            else "cbb-reconstruction:missing"
        ),
        policy_ref=policy.policy_id,
        reviewer_ref="reviewer:v0-local-operator",
        status=status,
        qualified_scope=(
            DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF
            if passed
            else DeliveryScope.BLOCKED
        ),
        active_reconstruction=passed,
        passive_attention_only=False,
        required_mrus_total=int((summary or {}).get("required_mrus_total") or 0),
        required_mrus_passed=int((summary or {}).get("required_mrus_passed") or 0),
        missing_mru_refs=list((summary or {}).get("missing_mrus") or []),
        evidence_refs=(
            ["attention-reconstruction-summary.json"] if summary is not None else []
        ),
        observed_at=observed_at,
        valid_until=effective_valid_until,
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "The mapped v0 reconstruction qualifies the reviewer for this scope."
                if passed
                else "The mapped v0 reconstruction does not currently qualify delivery."
            ),
            maximum_scope=(
                DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF
                if passed
                else DeliveryScope.BLOCKED
            ),
            not_claimed=[
                "global reviewer qualification",
                "permanent human capability",
                "passive attention as understanding",
                "production approval",
            ],
        ),
        privacy=privacy_boundary(),
    )


def dual_loop_and_delivery_to_gate_decision(
    gate_receipt: Mapping[str, Any],
    delivery_receipt: Mapping[str, Any],
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
) -> GateDecisionV1:
    gate = dual_loop.validate_gate_receipt(gate_receipt)
    receipt = delivery_trust.validate_delivery_trust_receipt(delivery_receipt)
    source_scope = (
        DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF
        if receipt["status"] == "allowed"
        else DeliveryScope.BLOCKED
    )
    reasons = list(receipt.get("reasons") or [])
    missing_evidence: list[str] = []
    if reconstruction.status != "passed":
        missing_evidence.append("qualified_reconstruction")
    if gate["status"] != "allowed" and "dual_loop_gate_blocked" not in reasons:
        reasons.append("dual_loop_gate_blocked")
    status: Literal["allow", "block", "needs_evidence"]
    if missing_evidence:
        status = "needs_evidence"
        approved_scope = DeliveryScope.BLOCKED
        if not reasons:
            reasons.append("qualified_reconstruction_unavailable")
    elif receipt["status"] == "allowed" and gate["status"] == "allowed":
        status = "allow"
        approved_scope = DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF
        reasons = []
    else:
        status = "block"
        approved_scope = DeliveryScope.BLOCKED
        if not reasons:
            reasons.append("v0_delivery_not_allowed")
    assert_scope_not_expanded(source_scope, approved_scope)
    return GateDecisionV1(
        schema_version=GATE_DECISION_SCHEMA_VERSION,
        decision_id=f"cbb-decision:{receipt['receipt_id']}",
        subject_ref=policy.subject_ref,
        policy_ref=policy.policy_id,
        evidence_bundle_ref=evidence_bundle.bundle_id,
        reconstruction_ref=reconstruction.reconstruction_id,
        status=status,
        approved_scope=approved_scope,
        reasons=reasons,
        hard_denies_triggered=[],
        missing_evidence_types=missing_evidence,
        source_decision_refs=[
            "dual-loop-gate-receipt.json",
            "delivery-trust-receipt.json",
        ],
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "The v0 evidence maps to controlled customer handoff only."
                if status == "allow"
                else "The mapped v0 evidence does not authorize delivery."
            ),
            maximum_scope=approved_scope,
            not_claimed=[
                "production approval",
                "portable signed attestation",
                "customer outcome guarantee",
                "scope beyond the source v0 receipt",
            ],
        ),
        privacy=privacy_boundary(),
        decided_at=str(receipt.get("created_at") or dual_loop.DETERMINISTIC_TIMESTAMP),
    )


def build_unsigned_provenance(
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
) -> ReceiptProvenanceV1:
    verifier_identity = {
        "verifier_id": "cbb-v0-compatibility-adapter",
        "verifier_version": "v1",
    }
    return ReceiptProvenanceV1(
        schema_version=RECEIPT_PROVENANCE_SCHEMA_VERSION,
        provenance_id=f"cbb-provenance:{evidence_bundle.bundle_id}",
        subject_digest_kind="metadata_ref_sha256",
        subject_digest_sha256=canonical_sha256({"subject_ref": policy.subject_ref}),
        policy_digest_sha256=canonical_sha256(policy),
        evidence_digest_sha256=canonical_sha256(evidence_bundle),
        verifier=VerifierIdentityV1(
            **verifier_identity,
            verifier_digest_sha256=canonical_sha256(verifier_identity),
        ),
        canonicalization=CANONICALIZATION_ALGORITHM,
        signing_status="unsigned_development",
        signature_algorithm=None,
        signature=None,
        created_at=dual_loop.DETERMINISTIC_TIMESTAMP,
        claim_boundary=ClaimBoundaryV1(
            current_claim="The receipt has deterministic local digest bindings only.",
            maximum_scope=DeliveryScope.BLOCKED,
            not_claimed=[
                "portable signed attestation",
                "signer identity verification",
                "cross-implementation trust",
            ],
        ),
    )


def delivery_trust_to_v1_receipt(
    delivery_receipt: Mapping[str, Any],
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    decision: GateDecisionV1,
) -> DeliveryTrustReceiptV1:
    receipt = delivery_trust.validate_delivery_trust_receipt(delivery_receipt)
    source_scope = (
        DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF
        if receipt["status"] == "allowed"
        else DeliveryScope.BLOCKED
    )
    assert_scope_not_expanded(source_scope, decision.approved_scope)
    return DeliveryTrustReceiptV1(
        schema_version=DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION,
        receipt_id=f"cbb-receipt:{receipt['receipt_id']}",
        subject_ref=policy.subject_ref,
        policy_ref=policy.policy_id,
        evidence_bundle_ref=evidence_bundle.bundle_id,
        reconstruction_ref=reconstruction.reconstruction_id,
        decision_ref=decision.decision_id,
        status=decision.status,
        approved_scope=decision.approved_scope,
        reasons=list(decision.reasons),
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "The candidate may enter controlled customer handoff under the mapped v0 receipt."
                if decision.status == "allow"
                else "The candidate is not authorized for delivery by the mapped v0 receipt."
            ),
            maximum_scope=decision.approved_scope,
            not_claimed=list(receipt["claim_boundary"]["not_claimed"])
            + ["portable signed attestation", "scope beyond the source v0 receipt"],
        ),
        provenance=build_unsigned_provenance(policy, evidence_bundle),
        privacy=privacy_boundary(),
        issued_at=str(receipt.get("created_at") or dual_loop.DETERMINISTIC_TIMESTAMP),
    )


def map_v0_delivery_chain(
    failure_contract: Mapping[str, Any],
    sandbox_receipt: Mapping[str, Any],
    attention_summary: Mapping[str, Any] | None,
    gate_receipt: Mapping[str, Any],
    delivery_receipt: Mapping[str, Any],
    *,
    observed_at: str = DEFAULT_OBSERVED_AT,
) -> dict[str, Any]:
    policy = failure_contract_to_trust_policy(failure_contract)
    evidence = failure_and_sandbox_to_evidence_bundle(
        failure_contract,
        sandbox_receipt,
        policy,
    )
    reconstruction = attention_summary_to_qualified_reconstruction(
        attention_summary,
        policy,
        observed_at=observed_at,
    )
    decision = dual_loop_and_delivery_to_gate_decision(
        gate_receipt,
        delivery_receipt,
        policy,
        evidence,
        reconstruction,
    )
    receipt = delivery_trust_to_v1_receipt(
        delivery_receipt,
        policy,
        evidence,
        reconstruction,
        decision,
    )
    return {
        "trust_policy": policy,
        "evidence_bundle": evidence,
        "qualified_reconstruction": reconstruction,
        "gate_decision": decision,
        "delivery_trust_receipt": receipt,
        "receipt_provenance": receipt.provenance,
    }
