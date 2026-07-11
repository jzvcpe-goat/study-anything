"""Typed allowlist for Agentic evidence tools with no release authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    AgenticPlanV1,
    AgenticToolContractV1,
    AgenticToolEffect,
    AgenticToolResultV1,
)


@dataclass(frozen=True)
class AgenticToolRegistry:
    contracts: Mapping[str, AgenticToolContractV1]

    @property
    def digest_sha256(self) -> str:
        return canonical_sha256(
            {
                tool_id: contract.model_dump(mode="json")
                for tool_id, contract in sorted(self.contracts.items())
            }
        )

    def validate_plan(self, plan: AgenticPlanV1) -> tuple[str, ...]:
        reasons: set[str] = set()
        for call in plan.calls:
            contract = self.contracts.get(call.tool_id)
            if contract is None:
                reasons.add(f"unknown_tool:{call.tool_id}")
                continue
            if call.requested_effect != contract.effect:
                reasons.add(f"effect_mismatch:{call.call_id}")
            if len(call.input_refs) > contract.max_input_refs:
                reasons.add(f"input_bound_exceeded:{call.call_id}")
            if call.untrusted_input_present and not contract.accepts_untrusted_input:
                reasons.add(f"untrusted_input_rejected:{call.call_id}")
            if contract.requires_quarantine and not call.quarantine_acknowledged:
                reasons.add(f"quarantine_missing:{call.call_id}")
            if any(
                (
                    contract.network_allowed,
                    contract.filesystem_write_allowed,
                    contract.policy_mutation_allowed,
                    contract.gate_decision_allowed,
                    contract.production_mutation_allowed,
                )
            ):
                reasons.add(f"unsafe_contract:{call.tool_id}")
        return tuple(sorted(reasons))

    def validate_results(
        self,
        plan: AgenticPlanV1,
        results: tuple[AgenticToolResultV1, ...] | list[AgenticToolResultV1],
    ) -> tuple[str, ...]:
        reasons: set[str] = set(self.validate_plan(plan))
        calls = {call.call_id: call for call in plan.calls}
        for result in results:
            call = calls.get(result.call_id)
            contract = self.contracts.get(result.tool_id)
            if call is None:
                reasons.add(f"unplanned_result:{result.call_id}")
                continue
            if contract is None:
                reasons.add(f"unknown_result_tool:{result.tool_id}")
                continue
            if result.tool_id != call.tool_id or result.effect != contract.effect:
                reasons.add(f"result_contract_mismatch:{result.call_id}")
            if len(result.output_refs) > contract.max_output_refs:
                reasons.add(f"output_bound_exceeded:{result.call_id}")
        return tuple(sorted(reasons))


def default_tool_registry() -> AgenticToolRegistry:
    contracts = (
        AgenticToolContractV1(
            tool_id="cbb.receipt.lookup",
            tool_version="1",
            effect=AgenticToolEffect.READ_METADATA,
            input_schema_ref="cbb.tool.receipt-lookup-input.v1",
            output_schema_ref="cbb.tool.receipt-lookup-output.v1",
            max_input_refs=20,
            max_output_refs=20,
            accepts_untrusted_input=False,
            requires_quarantine=False,
            network_allowed=False,
            filesystem_write_allowed=False,
            policy_mutation_allowed=False,
            gate_decision_allowed=False,
            production_mutation_allowed=False,
        ),
        AgenticToolContractV1(
            tool_id="cbb.memory.search",
            tool_version="1",
            effect=AgenticToolEffect.QUERY_QUARANTINE,
            input_schema_ref="cbb.tool.memory-search-input.v1",
            output_schema_ref="cbb.tool.memory-search-output.v1",
            max_input_refs=50,
            max_output_refs=50,
            accepts_untrusted_input=True,
            requires_quarantine=True,
            network_allowed=False,
            filesystem_write_allowed=False,
            policy_mutation_allowed=False,
            gate_decision_allowed=False,
            production_mutation_allowed=False,
        ),
        AgenticToolContractV1(
            tool_id="cbb.evolution.propose",
            tool_version="1",
            effect=AgenticToolEffect.PROPOSE_CANDIDATE,
            input_schema_ref="cbb.tool.evolution-proposal-input.v1",
            output_schema_ref="cbb.tool.evolution-proposal-output.v1",
            max_input_refs=50,
            max_output_refs=10,
            accepts_untrusted_input=True,
            requires_quarantine=True,
            network_allowed=False,
            filesystem_write_allowed=False,
            policy_mutation_allowed=False,
            gate_decision_allowed=False,
            production_mutation_allowed=False,
        ),
    )
    return AgenticToolRegistry({contract.tool_id: contract for contract in contracts})
