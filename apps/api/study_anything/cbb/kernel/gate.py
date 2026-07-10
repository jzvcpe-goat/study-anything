"""Pure, deterministic CBB Protocol v1 trust-kernel evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Literal

from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    DETERMINISTIC_TIMESTAMP,
    GATE_DECISION_SCHEMA_VERSION,
    SCOPE_ORDER,
    ClaimBoundaryV1,
    DeliveryScope,
    EvidenceBundleV1,
    EvidenceItemV1,
    GateDecisionV1,
    QualifiedReconstructionV1,
    TrustPolicyV1,
    scope_is_at_most,
)


HARD_DENY_EVIDENCE_PREFIX = "hard_deny:"
QUALIFIED_RECONSTRUCTION_EVIDENCE = "qualified_reconstruction"
QUALIFIED_REVIEWER_ROLE = "qualified_reviewer"


def _minimum_scope(scopes: Iterable[DeliveryScope]) -> DeliveryScope:
    return min(scopes, key=SCOPE_ORDER.__getitem__)


def _evidence_by_type(
    evidence_bundle: EvidenceBundleV1,
) -> tuple[dict[str, EvidenceItemV1], list[str]]:
    counts = Counter(item.evidence_type for item in evidence_bundle.evidence)
    duplicates = sorted(kind for kind, count in counts.items() if count > 1)
    return {item.evidence_type: item for item in evidence_bundle.evidence}, duplicates


def _triggered_hard_denies(
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
) -> tuple[list[str], list[str]]:
    triggered: list[str] = []
    unknown: list[str] = []
    policy_denies = set(policy.hard_denies)
    for item in evidence_bundle.evidence:
        if not item.evidence_type.startswith(HARD_DENY_EVIDENCE_PREFIX):
            continue
        deny = item.evidence_type.removeprefix(HARD_DENY_EVIDENCE_PREFIX)
        if item.status != "passed":
            continue
        if deny in policy_denies:
            triggered.append(deny)
        else:
            unknown.append(deny or "empty")
    return sorted(set(triggered)), sorted(set(unknown))


def _required_evidence_state(
    policy: TrustPolicyV1,
    evidence_by_type: dict[str, EvidenceItemV1],
    reconstruction: QualifiedReconstructionV1,
) -> tuple[list[str], list[str], list[str]]:
    missing: list[str] = []
    failed: list[str] = []
    insufficient_scope: list[str] = []
    for requirement in policy.required_evidence:
        if not requirement.blocking:
            continue
        evidence_type = requirement.evidence_type
        if evidence_type == QUALIFIED_RECONSTRUCTION_EVIDENCE:
            if reconstruction.status in {"missing", "stale"}:
                missing.append(evidence_type)
            elif reconstruction.status != "passed":
                failed.append(evidence_type)
            elif not scope_is_at_most(
                requirement.required_for_scope,
                reconstruction.qualified_scope,
            ):
                insufficient_scope.append(evidence_type)
            continue

        item = evidence_by_type.get(evidence_type)
        if item is None or item.status in {"missing", "stale", "not_applicable"}:
            missing.append(evidence_type)
        elif item.status != "passed":
            failed.append(evidence_type)
        elif not scope_is_at_most(
            requirement.required_for_scope,
            item.supported_scope,
        ):
            insufficient_scope.append(evidence_type)
    return (
        sorted(set(missing)),
        sorted(set(failed)),
        sorted(set(insufficient_scope)),
    )


def _role_state(
    policy: TrustPolicyV1,
    reconstruction: QualifiedReconstructionV1,
) -> list[str]:
    missing_roles: list[str] = []
    for role in policy.required_roles:
        if role == QUALIFIED_REVIEWER_ROLE and reconstruction.status == "passed":
            continue
        missing_roles.append(f"role:{role}")
    return sorted(set(missing_roles))


def _source_refs(
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
) -> list[str]:
    refs = [f"policy:{policy.policy_id}"]
    refs.extend(item.source_ref for item in evidence_bundle.evidence)
    refs.extend(reconstruction.evidence_refs)
    return sorted(set(refs))


def _decision_id(
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    decided_at: str,
) -> str:
    digest = canonical_sha256(
        {
            "policy_sha256": canonical_sha256(policy),
            "evidence_bundle_sha256": canonical_sha256(evidence_bundle),
            "reconstruction_sha256": canonical_sha256(reconstruction),
            "decided_at": decided_at,
        }
    )
    return f"cbb-decision:{digest[:32]}"


def evaluate_gate(
    policy: TrustPolicyV1,
    evidence_bundle: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    *,
    decided_at: str = DETERMINISTIC_TIMESTAMP,
) -> GateDecisionV1:
    """Evaluate canonical receipts without I/O, models, retrieval, or tools."""

    evidence_by_type, duplicate_types = _evidence_by_type(evidence_bundle)
    hard_denies, unknown_denies = _triggered_hard_denies(policy, evidence_bundle)
    missing, failed, insufficient_scope = _required_evidence_state(
        policy,
        evidence_by_type,
        reconstruction,
    )
    missing.extend(_role_state(policy, reconstruction))
    missing = sorted(set(missing))

    integrity_reasons: list[str] = []
    if evidence_bundle.subject_ref != policy.subject_ref:
        integrity_reasons.append("subject_ref_mismatch")
    if evidence_bundle.policy_ref != policy.policy_id:
        integrity_reasons.append("evidence_policy_ref_mismatch")
    if reconstruction.policy_ref != policy.policy_id:
        integrity_reasons.append("reconstruction_policy_ref_mismatch")
    integrity_reasons.extend(f"duplicate_evidence_type:{kind}" for kind in duplicate_types)
    integrity_reasons.extend(f"unknown_hard_deny_signal:{kind}" for kind in unknown_denies)

    blocking_reasons = sorted(
        set(
            integrity_reasons
            + [f"hard_deny:{deny}" for deny in hard_denies]
            + [f"evidence_failed:{kind}" for kind in failed]
        )
    )
    missing_reasons = sorted(
        set(missing + [f"insufficient_scope:{kind}" for kind in insufficient_scope])
    )

    status: Literal["allow", "block", "needs_evidence"]
    if blocking_reasons:
        status = "block"
        approved_scope = DeliveryScope.BLOCKED
        reasons = blocking_reasons
        missing_evidence_types: list[str] = []
    elif missing_reasons:
        status = "needs_evidence"
        approved_scope = DeliveryScope.BLOCKED
        reasons = ["required_evidence_unavailable"]
        missing_evidence_types = missing_reasons
    else:
        approved_scope = _minimum_scope(
            (
                policy.maximum_scope,
                policy.claim_boundary.maximum_scope,
                evidence_bundle.maximum_supported_scope,
                evidence_bundle.claim_boundary.maximum_scope,
                reconstruction.qualified_scope,
                reconstruction.claim_boundary.maximum_scope,
            )
        )
        if approved_scope == DeliveryScope.BLOCKED:
            status = "block"
            reasons = ["scope_ceiling_blocked"]
        else:
            status = "allow"
            reasons = []
        missing_evidence_types = []

    claim = (
        f"The deterministic CBB v1 kernel authorizes only {approved_scope.value}."
        if status == "allow"
        else "The deterministic CBB v1 kernel does not authorize delivery."
    )
    return GateDecisionV1(
        schema_version=GATE_DECISION_SCHEMA_VERSION,
        decision_id=_decision_id(policy, evidence_bundle, reconstruction, decided_at),
        subject_ref=policy.subject_ref,
        policy_ref=policy.policy_id,
        evidence_bundle_ref=evidence_bundle.bundle_id,
        reconstruction_ref=reconstruction.reconstruction_id,
        status=status,
        approved_scope=approved_scope,
        reasons=reasons,
        hard_denies_triggered=hard_denies,
        missing_evidence_types=missing_evidence_types,
        source_decision_refs=_source_refs(policy, evidence_bundle, reconstruction),
        claim_boundary=ClaimBoundaryV1(
            current_claim=claim,
            maximum_scope=approved_scope,
            not_claimed=[
                "production approval",
                "portable signed attestation",
                "customer outcome guarantee",
                "general model correctness",
                "authority beyond the evaluated policy and evidence",
            ],
        ),
        privacy=policy.privacy,
        decided_at=decided_at,
    )
