"""Shared deterministic trust-degradation policy for post-delivery evidence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from study_anything.cbb.protocol.models import (
    SCOPE_ORDER,
    DeliveryScope,
    OutcomeEventType,
    OutcomeEventV1,
    OutcomeSeverity,
    RollbackOutcomeV1,
    TrustDegradationAction,
    TrustDegradationV1,
)


OutcomeReceiptStatus = Literal["monitored", "degraded", "frozen", "revoked"]

_SEVERITY_ORDER = {
    OutcomeSeverity.INFO: 0,
    OutcomeSeverity.LOW: 1,
    OutcomeSeverity.MEDIUM: 2,
    OutcomeSeverity.HIGH: 3,
    OutcomeSeverity.CRITICAL: 4,
}


def _is_open(event: OutcomeEventV1) -> bool:
    return event.status in {"reported", "confirmed", "disputed"}


def _is_substantiated(event: OutcomeEventV1) -> bool:
    return event.status in {"confirmed", "resolved"}


def _is_safe_observation(event: OutcomeEventV1) -> bool:
    return (
        event.event_type == OutcomeEventType.DELIVERY_OBSERVATION
        and event.status == "confirmed"
        and event.severity == OutcomeSeverity.INFO
        and not event.external_effect_observed
        and not event.claim_boundary_violated
    )


def determine_trust_action(
    previous_scope: DeliveryScope,
    events: Iterable[OutcomeEventV1],
    rollback: RollbackOutcomeV1,
) -> TrustDegradationAction:
    """Return the fail-closed action; resolved adverse events never count as clean."""

    event_items = tuple(events)
    substantiated = tuple(event for event in event_items if _is_substantiated(event))
    if rollback.status == "failed":
        return TrustDegradationAction.REVOKE_CLEARANCE
    if any(
        event.event_type
        in {OutcomeEventType.CLAIM_VIOLATION, OutcomeEventType.EVIDENCE_INVALIDATED}
        for event in substantiated
    ):
        return TrustDegradationAction.REVOKE_CLEARANCE
    if any(
        event.event_type == OutcomeEventType.INCIDENT
        and _SEVERITY_ORDER[event.severity] >= _SEVERITY_ORDER[OutcomeSeverity.HIGH]
        for event in substantiated
    ):
        return TrustDegradationAction.REVOKE_CLEARANCE
    if any(
        event.external_effect_observed
        and _SEVERITY_ORDER[event.severity] >= _SEVERITY_ORDER[OutcomeSeverity.HIGH]
        for event in substantiated
    ):
        return TrustDegradationAction.REVOKE_CLEARANCE

    if rollback.required and rollback.status in {"partial", "not_attempted"}:
        return TrustDegradationAction.FREEZE_RECIPE
    if any(
        event.event_type == OutcomeEventType.AFFECTED_PARTY_CHALLENGE and event.status != "resolved"
        for event in event_items
    ):
        return TrustDegradationAction.FREEZE_RECIPE
    if any(
        _is_open(event)
        and (
            event.event_type
            in {OutcomeEventType.CLAIM_VIOLATION, OutcomeEventType.EVIDENCE_INVALIDATED}
            or (
                event.event_type == OutcomeEventType.INCIDENT
                and _SEVERITY_ORDER[event.severity] >= _SEVERITY_ORDER[OutcomeSeverity.MEDIUM]
            )
            or (
                event.event_type in {OutcomeEventType.NEAR_MISS, OutcomeEventType.COMPLAINT}
                and _SEVERITY_ORDER[event.severity] >= _SEVERITY_ORDER[OutcomeSeverity.HIGH]
            )
        )
        for event in event_items
    ):
        return TrustDegradationAction.FREEZE_RECIPE

    has_adverse_evidence = rollback.status == "succeeded" or any(
        not _is_safe_observation(event) for event in event_items
    )
    if has_adverse_evidence:
        if SCOPE_ORDER[previous_scope] > SCOPE_ORDER[DeliveryScope.SANDBOX_ONLY]:
            return TrustDegradationAction.NARROW_SCOPE
        return TrustDegradationAction.FREEZE_RECIPE
    return TrustDegradationAction.MAINTAIN_CURRENT_CEILING


def _reason_codes(
    action: TrustDegradationAction,
    events: tuple[OutcomeEventV1, ...],
    rollback: RollbackOutcomeV1,
) -> list[str]:
    reasons: set[str] = set()
    if rollback.status != "not_required":
        reasons.add(f"rollback:{rollback.status}")
    for event in events:
        if not _is_safe_observation(event):
            reasons.add(f"outcome:{event.event_type.value}:{event.status}:{event.severity.value}")
    if not reasons:
        reasons.add("bounded_sample:no_adverse_signal_observed")
    reasons.add(f"trust_action:{action.value}")
    return sorted(reasons)


def derive_trust_update(
    previous_scope: DeliveryScope,
    events: Iterable[OutcomeEventV1],
    rollback: RollbackOutcomeV1,
    *,
    recipe_ref: str,
    source_revocation_handle: str,
) -> tuple[TrustDegradationV1, OutcomeReceiptStatus]:
    """Build the canonical trust update used by both issuance and verification."""

    event_items = tuple(events)
    action = determine_trust_action(previous_scope, event_items, rollback)
    if action == TrustDegradationAction.MAINTAIN_CURRENT_CEILING:
        resulting_scope = previous_scope
        recipe_state: Literal["active", "frozen", "revoked"] = "active"
        status: OutcomeReceiptStatus = "monitored"
    elif action == TrustDegradationAction.NARROW_SCOPE:
        resulting_scope = DeliveryScope.SANDBOX_ONLY
        recipe_state = "active"
        status = "degraded"
    elif action == TrustDegradationAction.FREEZE_RECIPE:
        resulting_scope = DeliveryScope.BLOCKED
        recipe_state = "frozen"
        status = "frozen"
    else:
        resulting_scope = DeliveryScope.BLOCKED
        recipe_state = "revoked"
        status = "revoked"

    non_clean_events = tuple(event for event in event_items if not _is_safe_observation(event))
    affected_party_follow_up = any(
        event.event_type == OutcomeEventType.AFFECTED_PARTY_CHALLENGE and event.status != "resolved"
        for event in event_items
    )
    source_revoked = action == TrustDegradationAction.REVOKE_CLEARANCE
    counter_evidence_refs = sorted(
        {
            ref
            for event in non_clean_events
            for ref in (*event.source_refs, *event.counter_evidence_refs)
        }
    )
    trust_update = TrustDegradationV1(
        action=action,
        previous_scope=previous_scope,
        resulting_scope=resulting_scope,
        recipe_ref=recipe_ref,
        recipe_state=recipe_state,
        source_clearance_revoked=source_revoked,
        revoked_clearance_handles=([source_revocation_handle] if source_revoked else []),
        replay_required=action != TrustDegradationAction.MAINTAIN_CURRENT_CEILING,
        policy_reconstruction_required=(action != TrustDegradationAction.MAINTAIN_CURRENT_CEILING),
        risk_owner_reacceptance_required=(
            action != TrustDegradationAction.MAINTAIN_CURRENT_CEILING
        ),
        affected_party_follow_up_required=affected_party_follow_up,
        counter_evidence_refs=counter_evidence_refs,
        reasons=_reason_codes(action, event_items, rollback),
        trust_increase_allowed=False,
    )
    return trust_update, status
