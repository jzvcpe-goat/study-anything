"""Deterministic fixture planner for the proposal-only Agentic boundary."""

from __future__ import annotations

from study_anything.cbb.protocol.models import (
    AgenticPlanV1,
    AgenticPlannerKind,
    AgenticToolCallV1,
    AgenticToolEffect,
)


class DeterministicEvidencePlanner:
    """Build a fixed metadata-only plan; it never emits a gate decision."""

    planner_id = "delivery-clearance-deterministic-evidence-planner"

    def plan(
        self,
        *,
        proposal_ref: str,
        receipt_refs: list[str],
        memory_refs: list[str],
        created_at: str,
    ) -> AgenticPlanV1:
        return AgenticPlanV1(
            plan_id=f"agentic-plan:{proposal_ref}",
            planner_id=self.planner_id,
            planner_kind=AgenticPlannerKind.DETERMINISTIC_FIXTURE,
            created_at=created_at,
            calls=[
                AgenticToolCallV1(
                    call_id="call:receipt-lookup",
                    tool_id="cbb.receipt.lookup",
                    requested_effect=AgenticToolEffect.READ_METADATA,
                    input_refs=receipt_refs,
                    untrusted_input_present=False,
                    quarantine_acknowledged=False,
                    requests_policy_mutation=False,
                    requests_gate_decision=False,
                    requests_production_mutation=False,
                ),
                AgenticToolCallV1(
                    call_id="call:memory-search",
                    tool_id="cbb.memory.search",
                    requested_effect=AgenticToolEffect.QUERY_QUARANTINE,
                    input_refs=memory_refs,
                    untrusted_input_present=True,
                    quarantine_acknowledged=True,
                    requests_policy_mutation=False,
                    requests_gate_decision=False,
                    requests_production_mutation=False,
                ),
                AgenticToolCallV1(
                    call_id="call:evolution-proposal",
                    tool_id="cbb.evolution.propose",
                    requested_effect=AgenticToolEffect.PROPOSE_CANDIDATE,
                    input_refs=[proposal_ref, *receipt_refs, *memory_refs],
                    untrusted_input_present=True,
                    quarantine_acknowledged=True,
                    requests_policy_mutation=False,
                    requests_gate_decision=False,
                    requests_production_mutation=False,
                ),
            ],
            final_authority="proposal_only",
            policy_mutation_requested=False,
            gate_decision_requested=False,
            production_mutation_requested=False,
        )
