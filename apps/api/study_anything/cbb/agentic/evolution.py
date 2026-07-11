"""Issue signed, proposal-only evolution-gate receipts."""

from __future__ import annotations

from typing import Any

from study_anything.cbb.agentic.policy import evaluate_evolution_gate
from study_anything.cbb.agentic.signing import sign_evolution_envelope
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    EVOLUTION_GATE_RECEIPT_SCHEMA_VERSION,
    AgenticEvidenceContextV1,
    ClaimBoundaryV1,
    DeliveryScope,
    EvolutionControlSetV1,
    EvolutionGateReceiptV1,
    EvolutionProposalV1,
    PrivacyBoundaryV1,
)


class EvolutionEvaluationError(ValueError):
    """Raised when an evolution candidate cannot produce a canonical receipt."""


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


def issue_evolution_gate_receipt(
    proposal: EvolutionProposalV1,
    context: AgenticEvidenceContextV1,
    controls: EvolutionControlSetV1,
    *,
    issued_at: str,
    private_key: Any,
    signer_id: str,
    key_id: str,
    expires_at: str,
    replay_nonce: str,
) -> EvolutionGateReceiptV1:
    """Evaluate and sign a receipt without applying or releasing the candidate."""

    decision = evaluate_evolution_gate(proposal, context, controls)
    receipt_id = "cbb-evolution:" + canonical_sha256(
        {
            "proposal": proposal.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
            "issued_at": issued_at,
        }
    )[:32]
    claim_boundary = ClaimBoundaryV1(
        current_claim=(
            "This receipt records a deterministic decision about a local evolution "
            "candidate. It does not apply the candidate or grant delivery authority."
        ),
        maximum_scope=DeliveryScope.BLOCKED,
        not_claimed=[
            "automatic policy application",
            "production authorization",
            "global protocol conformance",
            "third-party signer identity",
            "independent security audit completion",
            "model or memory output as a trust root",
        ],
    )
    envelope: dict[str, Any] = {
        "schema_version": EVOLUTION_GATE_RECEIPT_SCHEMA_VERSION,
        "evolution_receipt_id": receipt_id,
        "proposal": proposal.model_dump(mode="json"),
        "agentic_evidence": context.model_dump(mode="json"),
        "controls": controls.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
        "issued_at": issued_at,
        "claim_boundary": claim_boundary.model_dump(mode="json"),
        "privacy": _privacy().model_dump(mode="json"),
        "automatic_apply_performed": False,
    }
    provenance = sign_evolution_envelope(
        envelope,
        decision,
        private_key=private_key,
        signer_id=signer_id,
        key_id=key_id,
        created_at=issued_at,
        expires_at=expires_at,
        replay_nonce=replay_nonce,
        evolution_receipt_id=receipt_id,
    )
    return EvolutionGateReceiptV1.model_validate(
        {
            **envelope,
            "provenance": provenance.model_dump(mode="json"),
        }
    )
