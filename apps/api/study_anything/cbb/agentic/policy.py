"""Deterministic evolution gate; Agentic outputs remain supporting evidence."""

from __future__ import annotations

from study_anything.cbb.agentic.memory import query_quarantined_memory
from study_anything.cbb.agentic.tools import default_tool_registry
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    AgenticEvidenceContextV1,
    EvolutionControlSetV1,
    EvolutionControlStatus,
    EvolutionControlType,
    EvolutionDecisionStatus,
    EvolutionGateDecisionV1,
    EvolutionProposalV1,
)


_PROTECTED_FLAGS = {
    "touches_hard_denies": "protected_change:hard_denies",
    "weakens_required_evidence": "protected_change:required_evidence",
    "expands_delivery_scope": "protected_change:delivery_scope",
    "expands_tool_authority": "protected_change:tool_authority",
    "changes_verifier_or_signing": "protected_change:verifier_or_signing",
    "changes_revocation_semantics": "protected_change:revocation",
    "requests_automatic_apply": "protected_change:automatic_apply",
    "requests_production_mutation": "protected_change:production_mutation",
}


def evaluate_evolution_gate(
    proposal: EvolutionProposalV1,
    context: AgenticEvidenceContextV1,
    controls: EvolutionControlSetV1,
) -> EvolutionGateDecisionV1:
    """Return a local-candidate decision without applying the proposed change."""

    block_reasons: set[str] = set()
    needs_reasons: set[str] = set()

    registry = default_tool_registry()
    block_reasons.update(
        f"tool_boundary:{reason}"
        for reason in registry.validate_results(context.plan, context.tool_results)
    )
    expected_memory = query_quarantined_memory(
        context.memory_query.considered_entries,
        query_id=context.memory_query.query_id,
        as_of=context.memory_query.as_of,
    )
    if expected_memory != context.memory_query:
        block_reasons.add("memory_quarantine:deterministic_replay_mismatch")
    if context.memory_query.policy_override_allowed:
        block_reasons.add("memory_quarantine:policy_override_requested")
    if context.memory_query.unresolved_counter_evidence_refs:
        needs_reasons.add("memory_quarantine:counter_evidence_pending")

    for field_name, reason in _PROTECTED_FLAGS.items():
        if getattr(proposal, field_name):
            block_reasons.add(reason)

    controls_by_type = {
        control.control_type: control for control in controls.controls
    }
    human_control_types = {
        EvolutionControlType.HUMAN_RECONSTRUCTION,
        EvolutionControlType.RISK_OWNER_ACCEPTANCE,
        EvolutionControlType.MAINTAINER_APPROVAL,
    }
    if any(
        controls_by_type[control_type].actor_ref == proposal.proposer_ref
        for control_type in human_control_types
    ):
        block_reasons.add("actor_separation:self_authorization")

    for control in controls.controls:
        if control.status == EvolutionControlStatus.FAILED:
            block_reasons.add(f"control_failed:{control.control_type.value}")
        elif control.status == EvolutionControlStatus.MISSING:
            needs_reasons.add(f"control_missing:{control.control_type.value}")

    eligible_memory = set(context.memory_query.eligible_memory_ids)
    missing_memory = sorted(set(proposal.memory_refs).difference(eligible_memory))
    if missing_memory:
        needs_reasons.update(f"memory_not_eligible:{memory_id}" for memory_id in missing_memory)

    tool_outputs = {
        output_ref
        for result in context.tool_results
        if result.status == "passed"
        for output_ref in result.output_refs
    }
    missing_evidence = sorted(set(proposal.evidence_refs).difference(tool_outputs))
    if missing_evidence:
        needs_reasons.update(f"evidence_not_produced:{ref}" for ref in missing_evidence)
    needs_reasons.update(
        f"tool_result_blocked:{result.call_id}"
        for result in context.tool_results
        if result.status == "blocked"
    )

    proposal_digest = canonical_sha256(proposal)
    if block_reasons:
        return EvolutionGateDecisionV1(
            status=EvolutionDecisionStatus.BLOCK,
            candidate_state="rejected",
            proposal_digest_sha256=proposal_digest,
            reasons=sorted(block_reasons),
            automatic_apply_allowed=False,
            production_apply_allowed=False,
            trust_kernel_mutation_performed=False,
            release_performed=False,
            tool_or_memory_authority_used_as_final_basis=False,
            explicit_maintainer_apply_required=True,
        )
    if needs_reasons:
        return EvolutionGateDecisionV1(
            status=EvolutionDecisionStatus.NEEDS_EVIDENCE,
            candidate_state="pending",
            proposal_digest_sha256=proposal_digest,
            reasons=sorted(needs_reasons),
            automatic_apply_allowed=False,
            production_apply_allowed=False,
            trust_kernel_mutation_performed=False,
            release_performed=False,
            tool_or_memory_authority_used_as_final_basis=False,
            explicit_maintainer_apply_required=True,
        )
    return EvolutionGateDecisionV1(
        status=EvolutionDecisionStatus.APPROVED_FOR_LOCAL_CANDIDATE,
        candidate_state="local_candidate",
        proposal_digest_sha256=proposal_digest,
        reasons=[],
        automatic_apply_allowed=False,
        production_apply_allowed=False,
        trust_kernel_mutation_performed=False,
        release_performed=False,
        tool_or_memory_authority_used_as_final_basis=False,
        explicit_maintainer_apply_required=True,
    )
