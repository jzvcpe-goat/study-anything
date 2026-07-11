"""Pure post-delivery evaluation for Delivery Clearance outcome evidence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from study_anything.cbb.outcomes.policy import derive_trust_update
from study_anything.cbb.outcomes.signing import (
    sign_outcome_envelope,
    verify_outcome_receipt,
)
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    DELIVERY_OUTCOME_RECEIPT_SCHEMA_VERSION,
    ClaimBoundaryV1,
    DeliveryOutcomeReceiptV1,
    OutcomeEventV1,
    PostDeliverySamplingV1,
    PrivacyBoundaryV1,
    RollbackOutcomeV1,
    SourceClearanceVerificationV1,
    TrustDegradationAction,
)
from study_anything.cbb.provenance.signing import (
    OfflineProvenancePackageV1,
    verify_offline_package,
)


class OutcomeEvaluationError(ValueError):
    """Raised when source clearance or outcome inputs fail closed."""


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


def evaluate_delivery_outcome(
    package: OfflineProvenancePackageV1,
    *,
    sampling: PostDeliverySamplingV1,
    events: Iterable[OutcomeEventV1],
    rollback: RollbackOutcomeV1,
    recipe_ref: str,
    issued_at: str,
    private_key: Any,
    signer_id: str,
    key_id: str,
    expires_at: str,
    replay_nonce: str,
    revoked_handles: Iterable[str] = (),
) -> DeliveryOutcomeReceiptV1:
    """Verify source clearance and deterministically emit non-increasing trust."""

    clearance_valid_at = package.receipt_provenance.created_at
    verification = verify_offline_package(
        package,
        now=clearance_valid_at,
        revoked_handles=revoked_handles,
    )
    if not verification.passed:
        raise OutcomeEvaluationError(
            "source delivery clearance did not pass offline verification: "
            + ",".join(verification.reasons)
        )
    source_receipt = package.delivery_trust_receipt
    if source_receipt.status != "allow":
        raise OutcomeEvaluationError("post-delivery outcome requires an allowed source receipt")

    event_items = tuple(events)
    if not event_items:
        raise OutcomeEvaluationError("post-delivery outcome requires at least one event")
    previous_scope = source_receipt.approved_scope
    trust_update, status = derive_trust_update(
        previous_scope,
        event_items,
        rollback,
        recipe_ref=recipe_ref,
        source_revocation_handle=package.receipt_provenance.revocation.handle,
    )
    action = trust_update.action
    resulting_scope = trust_update.resulting_scope
    source_digest = canonical_sha256(source_receipt)
    outcome_id = canonical_sha256(
        {
            "source_delivery_receipt_digest_sha256": source_digest,
            "sampling": sampling.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in event_items],
            "rollback": rollback.model_dump(mode="json"),
            "issued_at": issued_at,
        }
    )[:32]
    verified_checks = sorted(name for name, passed in verification.checks.items() if passed)
    current_claim = (
        "Bounded post-delivery evidence did not reduce the existing clearance ceiling."
        if action == TrustDegradationAction.MAINTAIN_CURRENT_CEILING
        else "Post-delivery evidence reduced or suspended the prior clearance boundary."
    )
    outcome_receipt_id = f"cbb-outcome:{outcome_id}"
    source_verification = SourceClearanceVerificationV1(
        package_ref=package.package_id,
        package_digest_sha256=package.receipt_provenance.package_digest_sha256,
        verification_status="pass",
        verified_at=issued_at,
        clearance_valid_at=clearance_valid_at,
        checks_passed=verified_checks,
        local_self_asserted_signer_only=True,
    )
    claim_boundary = ClaimBoundaryV1(
        current_claim=current_claim,
        maximum_scope=resulting_scope,
        not_claimed=[
            "customer outcome guarantee",
            "global model correctness",
            "production approval",
            "legal or security certification",
            "trust increase from elapsed time or accumulated pass count",
            "automatic policy mutation",
        ],
    )
    envelope: dict[str, Any] = {
        "schema_version": DELIVERY_OUTCOME_RECEIPT_SCHEMA_VERSION,
        "outcome_receipt_id": outcome_receipt_id,
        "source_delivery_receipt_ref": source_receipt.receipt_id,
        "source_delivery_receipt_digest_sha256": source_digest,
        "source_clearance_revocation_handle": (package.receipt_provenance.revocation.handle),
        "subject_ref": source_receipt.subject_ref,
        "policy_ref": source_receipt.policy_ref,
        "scenario_ref": package.trust_policy.scenario_ref,
        "source_approved_scope": previous_scope.value,
        "source_verification": source_verification.model_dump(mode="json"),
        "sampling": sampling.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in event_items],
        "rollback": rollback.model_dump(mode="json"),
        "status": status,
        "trust_update": trust_update.model_dump(mode="json"),
        "issued_at": issued_at,
        "claim_boundary": claim_boundary.model_dump(mode="json"),
        "privacy": _privacy().model_dump(mode="json"),
    }
    provenance = sign_outcome_envelope(
        envelope,
        source_package_digest_sha256=(package.receipt_provenance.package_digest_sha256),
        private_key=private_key,
        signer_id=signer_id,
        key_id=key_id,
        created_at=issued_at,
        expires_at=expires_at,
        replay_nonce=replay_nonce,
        outcome_receipt_id=outcome_receipt_id,
        maximum_scope=resulting_scope,
    )
    return DeliveryOutcomeReceiptV1.model_validate(
        {
            **envelope,
            "outcome_provenance": provenance.model_dump(mode="json"),
        }
    )


def revocation_registry_updates(
    receipt: DeliveryOutcomeReceiptV1,
    package: OfflineProvenancePackageV1,
    *,
    now: str,
    revoked_source_handles: Iterable[str] = (),
    revoked_outcome_handles: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return source revocations only after both source and outcome verify offline."""

    verification = verify_outcome_receipt(
        package,
        receipt,
        now=now,
        revoked_source_handles=revoked_source_handles,
        revoked_outcome_handles=revoked_outcome_handles,
    )
    if not verification.passed:
        raise OutcomeEvaluationError(
            "outcome receipt did not pass offline verification: " + ",".join(verification.reasons)
        )
    if not receipt.trust_update.source_clearance_revoked:
        return ()
    return tuple(receipt.trust_update.revoked_clearance_handles)
