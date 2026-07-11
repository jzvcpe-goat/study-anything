"""Deterministic public-only fixtures for Agentic evolution isolation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from study_anything.cbb.agentic.evolution import issue_evolution_gate_receipt
from study_anything.cbb.agentic.memory import query_quarantined_memory
from study_anything.cbb.agentic.planner import DeterministicEvidencePlanner
from study_anything.cbb.protocol.canonical import model_payload
from study_anything.cbb.protocol.models import (
    AgenticEvidenceContextV1,
    AgenticToolEffect,
    AgenticToolResultV1,
    DeliveryScope,
    EvolutionChangeKind,
    EvolutionControlEvidenceV1,
    EvolutionControlSetV1,
    EvolutionControlStatus,
    EvolutionControlType,
    EvolutionProposalV1,
    MemorySourceTrust,
    QuarantinedMemoryEntryV1,
)


FIXTURE_ROOT = Path("fixtures") / "cbb-v1-agentic-evolution"
ISSUED_AT = "2026-07-11T07:00:00Z"
EXPIRES_AT = "2026-08-10T07:00:00Z"
QUERY_AS_OF = "2026-07-11T06:55:00Z"
PROPOSER_REF = "agent:evolution-planner"
SIGNER_REF = "maintainer:fixture-signer"
ControlActorKind = Literal[
    "deterministic_verifier",
    "human_reconstructor",
    "risk_owner",
    "maintainer",
]


def fixture_private_key(seed: bytes = b"cbb-v1-agentic-evolution-fixture") -> Any:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed).digest())


def memory_entries() -> dict[str, QuarantinedMemoryEntryV1]:
    return {
        "safe": QuarantinedMemoryEntryV1(
            memory_id="memory:safe-failure-pattern",
            memory_kind="failure",
            source_ref="outcome-receipt:near-miss",
            source_digest_sha256="1" * 64,
            content_digest_sha256="2" * 64,
            source_trust=MemorySourceTrust.LOCAL_VERIFIED,
            verification_ref="verification:outcome-replay",
            signature_ref=None,
            observed_at="2026-07-10T00:00:00Z",
            expires_at="2026-08-10T00:00:00Z",
            counter_evidence_refs=[],
            injection_signals=[],
            policy_directive_detected=False,
            eligible_as_supporting_evidence=True,
            quarantined=True,
            policy_authority=False,
            raw_content_included=False,
        ),
        "poisoned": QuarantinedMemoryEntryV1(
            memory_id="memory:poisoned-instruction",
            memory_kind="receipt",
            source_ref="untrusted:retrieval-result",
            source_digest_sha256="3" * 64,
            content_digest_sha256="4" * 64,
            source_trust=MemorySourceTrust.UNTRUSTED,
            verification_ref=None,
            signature_ref=None,
            observed_at="2026-07-10T00:00:00Z",
            expires_at="2026-08-10T00:00:00Z",
            counter_evidence_refs=[],
            injection_signals=["instruction_like_content"],
            policy_directive_detected=True,
            eligible_as_supporting_evidence=False,
            quarantined=True,
            policy_authority=False,
            raw_content_included=False,
        ),
        "contested": QuarantinedMemoryEntryV1(
            memory_id="memory:contested-outcome",
            memory_kind="outcome",
            source_ref="outcome-receipt:contested",
            source_digest_sha256="5" * 64,
            content_digest_sha256="6" * 64,
            source_trust=MemorySourceTrust.LOCAL_VERIFIED,
            verification_ref="verification:outcome-contested",
            signature_ref=None,
            observed_at="2026-07-10T00:00:00Z",
            expires_at="2026-08-10T00:00:00Z",
            counter_evidence_refs=["counter-evidence:challenge-1"],
            injection_signals=[],
            policy_directive_detected=False,
            eligible_as_supporting_evidence=True,
            quarantined=True,
            policy_authority=False,
            raw_content_included=False,
        ),
        "expired": QuarantinedMemoryEntryV1(
            memory_id="memory:expired-receipt",
            memory_kind="receipt",
            source_ref="receipt:expired",
            source_digest_sha256="7" * 64,
            content_digest_sha256="8" * 64,
            source_trust=MemorySourceTrust.SIGNED_EXTERNAL,
            verification_ref=None,
            signature_ref="signature:external-fixture",
            observed_at="2026-06-01T00:00:00Z",
            expires_at="2026-07-01T00:00:00Z",
            counter_evidence_refs=[],
            injection_signals=[],
            policy_directive_detected=False,
            eligible_as_supporting_evidence=True,
            quarantined=True,
            policy_authority=False,
            raw_content_included=False,
        ),
        "future": QuarantinedMemoryEntryV1(
            memory_id="memory:future-observation",
            memory_kind="receipt",
            source_ref="receipt:future",
            source_digest_sha256="9" * 64,
            content_digest_sha256="b" * 64,
            source_trust=MemorySourceTrust.LOCAL_VERIFIED,
            verification_ref="verification:future-fixture",
            signature_ref=None,
            observed_at="2026-07-12T00:00:00Z",
            expires_at="2026-08-12T00:00:00Z",
            counter_evidence_refs=[],
            injection_signals=[],
            policy_directive_detected=False,
            eligible_as_supporting_evidence=True,
            quarantined=True,
            policy_authority=False,
            raw_content_included=False,
        ),
    }


def _controls(
    *,
    overrides: dict[EvolutionControlType, EvolutionControlStatus] | None = None,
    self_authorize: bool = False,
) -> EvolutionControlSetV1:
    overrides = overrides or {}
    actor_kinds: dict[EvolutionControlType, ControlActorKind] = {
        EvolutionControlType.DETERMINISTIC_REPLAY: "deterministic_verifier",
        EvolutionControlType.CANARY: "deterministic_verifier",
        EvolutionControlType.ROLLBACK: "deterministic_verifier",
        EvolutionControlType.HUMAN_RECONSTRUCTION: "human_reconstructor",
        EvolutionControlType.RISK_OWNER_ACCEPTANCE: "risk_owner",
        EvolutionControlType.MAINTAINER_APPROVAL: "maintainer",
    }
    actor_refs = {
        EvolutionControlType.DETERMINISTIC_REPLAY: "verifier:evolution-replay",
        EvolutionControlType.CANARY: "verifier:evolution-canary",
        EvolutionControlType.ROLLBACK: "verifier:evolution-rollback",
        EvolutionControlType.HUMAN_RECONSTRUCTION: "human:reconstructor",
        EvolutionControlType.RISK_OWNER_ACCEPTANCE: "human:risk-owner",
        EvolutionControlType.MAINTAINER_APPROVAL: "human:maintainer",
    }
    if self_authorize:
        actor_refs[EvolutionControlType.HUMAN_RECONSTRUCTION] = PROPOSER_REF
    controls: list[EvolutionControlEvidenceV1] = []
    for control_type in EvolutionControlType:
        status = overrides.get(control_type, EvolutionControlStatus.PASSED)
        controls.append(
            EvolutionControlEvidenceV1(
                control_type=control_type,
                status=status,
                evidence_ref=(
                    None
                    if status == EvolutionControlStatus.MISSING
                    else f"evidence:{control_type.value}:{status.value}"
                ),
                actor_kind=actor_kinds[control_type],
                actor_ref=actor_refs[control_type],
            )
        )
    return EvolutionControlSetV1(controls=controls)


def _tool_results() -> list[AgenticToolResultV1]:
    return [
        AgenticToolResultV1(
            call_id="call:receipt-lookup",
            tool_id="cbb.receipt.lookup",
            effect=AgenticToolEffect.READ_METADATA,
            status="passed",
            output_refs=["evidence:receipt-baseline"],
            provenance_refs=["provenance:receipt-baseline"],
            redaction_count=0,
            reasons=[],
            authority="supporting_evidence_only",
            policy_override_allowed=False,
            gate_decision_allowed=False,
            production_mutation_performed=False,
        ),
        AgenticToolResultV1(
            call_id="call:memory-search",
            tool_id="cbb.memory.search",
            effect=AgenticToolEffect.QUERY_QUARANTINE,
            status="passed",
            output_refs=["evidence:memory-safe"],
            provenance_refs=["provenance:memory-query"],
            redaction_count=1,
            reasons=[],
            authority="supporting_evidence_only",
            policy_override_allowed=False,
            gate_decision_allowed=False,
            production_mutation_performed=False,
        ),
        AgenticToolResultV1(
            call_id="call:evolution-proposal",
            tool_id="cbb.evolution.propose",
            effect=AgenticToolEffect.PROPOSE_CANDIDATE,
            status="passed",
            output_refs=["evidence:recipe-proposal"],
            provenance_refs=["provenance:proposal-builder"],
            redaction_count=0,
            reasons=[],
            authority="supporting_evidence_only",
            policy_override_allowed=False,
            gate_decision_allowed=False,
            production_mutation_performed=False,
        ),
    ]


def _proposal(
    case_id: str,
    *,
    memory_refs: list[str],
    protected_overrides: dict[str, bool] | None = None,
) -> EvolutionProposalV1:
    flags = {
        "touches_hard_denies": False,
        "weakens_required_evidence": False,
        "expands_tool_authority": False,
        "changes_verifier_or_signing": False,
        "changes_revocation_semantics": False,
        "requests_automatic_apply": False,
        "requests_production_mutation": False,
    }
    flags.update(protected_overrides or {})
    return EvolutionProposalV1(
        proposal_id=f"evolution-proposal:{case_id}",
        change_kind=EvolutionChangeKind.TRUST_RECIPE,
        target_ref="trust-recipe:internal-handoff",
        base_digest_sha256="a" * 64,
        candidate_digest_sha256=hashlib.sha256(case_id.encode("utf-8")).hexdigest(),
        summary_digest_sha256=hashlib.sha256(f"summary:{case_id}".encode()).hexdigest(),
        proposer_kind="agent",
        proposer_ref=PROPOSER_REF,
        submitted_at="2026-07-11T06:50:00Z",
        current_scope=DeliveryScope.INTERNAL_HANDOFF,
        requested_scope=DeliveryScope.INTERNAL_HANDOFF,
        evidence_refs=[
            "evidence:receipt-baseline",
            "evidence:memory-safe",
            "evidence:recipe-proposal",
        ],
        memory_refs=memory_refs,
        expands_delivery_scope=False,
        proposal_only=True,
        raw_patch_included=False,
        **flags,
    )


def _build_case(
    case_id: str,
    *,
    entries: list[QuarantinedMemoryEntryV1],
    proposal_memory_refs: list[str],
    expected_status: str,
    controls: EvolutionControlSetV1 | None = None,
    protected_overrides: dict[str, bool] | None = None,
) -> dict[str, Any]:
    proposal = _proposal(
        case_id,
        memory_refs=proposal_memory_refs,
        protected_overrides=protected_overrides,
    )
    plan = DeterministicEvidencePlanner().plan(
        proposal_ref=proposal.proposal_id,
        receipt_refs=["receipt:baseline"],
        memory_refs=[entry.memory_id for entry in entries],
        created_at="2026-07-11T06:51:00Z",
    )
    context = AgenticEvidenceContextV1(
        plan=plan,
        tool_results=_tool_results(),
        memory_query=query_quarantined_memory(
            entries,
            query_id=f"memory-query:{case_id}",
            as_of=QUERY_AS_OF,
        ),
        agentic_output_authority="supporting_evidence_only",
        policy_override_allowed=False,
        gate_decision_from_agent=False,
        production_mutation_performed=False,
    )
    control_set = controls or _controls()
    receipt = issue_evolution_gate_receipt(
        proposal,
        context,
        control_set,
        issued_at=ISSUED_AT,
        private_key=fixture_private_key(),
        signer_id=SIGNER_REF,
        key_id="fixture-agentic-evolution-key-1",
        expires_at=EXPIRES_AT,
        replay_nonce=f"evolution-replay-nonce:{case_id}",
    )
    return {
        "case_id": case_id,
        "expected_status": expected_status,
        "inputs": {
            "proposal": model_payload(proposal),
            "agentic_evidence": model_payload(context),
            "controls": model_payload(control_set),
            "issued_at": ISSUED_AT,
            "expires_at": EXPIRES_AT,
            "replay_nonce": f"evolution-replay-nonce:{case_id}",
        },
        "receipt": model_payload(receipt),
    }


def build_agentic_evolution_cases() -> dict[str, dict[str, Any]]:
    entries = memory_entries()
    safe_memory = entries["safe"].memory_id
    cases = {
        "approved-local-candidate": _build_case(
            "approved-local-candidate",
            entries=[entries["safe"]],
            proposal_memory_refs=[safe_memory],
            expected_status="approved_for_local_candidate",
        ),
        "missing-human-reconstruction": _build_case(
            "missing-human-reconstruction",
            entries=[entries["safe"]],
            proposal_memory_refs=[safe_memory],
            expected_status="needs_evidence",
            controls=_controls(
                overrides={
                    EvolutionControlType.HUMAN_RECONSTRUCTION: EvolutionControlStatus.MISSING
                }
            ),
        ),
        "hard-deny-change-blocked": _build_case(
            "hard-deny-change-blocked",
            entries=[entries["safe"]],
            proposal_memory_refs=[safe_memory],
            expected_status="block",
            protected_overrides={"touches_hard_denies": True},
        ),
        "poisoned-memory-needs-evidence": _build_case(
            "poisoned-memory-needs-evidence",
            entries=[entries["safe"], entries["poisoned"]],
            proposal_memory_refs=[entries["poisoned"].memory_id],
            expected_status="needs_evidence",
        ),
        "self-authorization-blocked": _build_case(
            "self-authorization-blocked",
            entries=[entries["safe"]],
            proposal_memory_refs=[safe_memory],
            expected_status="block",
            controls=_controls(self_authorize=True),
        ),
        "tool-authority-expansion-blocked": _build_case(
            "tool-authority-expansion-blocked",
            entries=[entries["safe"]],
            proposal_memory_refs=[safe_memory],
            expected_status="block",
            protected_overrides={"expands_tool_authority": True},
        ),
    }
    return cases


def fixture_outputs(root: Path) -> dict[Path, str]:
    return {
        root / FIXTURE_ROOT / f"{case_id}.json": json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
        for case_id, payload in build_agentic_evolution_cases().items()
    }
