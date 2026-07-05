#!/usr/bin/env python3
"""Gate reopen-intake backlog signals before Product Owner spec/eval work."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import cbb_protocol, dual_loop  # noqa: E402
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge as reopen_backlog_bridge  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt-v1"
CANDIDATE_SCHEMA_VERSION = "patch-proposal-product-spec-eval-candidate-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate-v1"

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate"
)

CASE_IDS = (
    "pass",
    "blocked-missing-backlog-bridge-receipt",
    "blocked-bridge-blocked",
    "blocked-missing-gate-ref",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-backlog-signal-ref",
    "blocked-missing-owner-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-raw-backlog-data",
    "blocked-customer-identity",
    "blocked-automatic-customer-contact",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-priority-assignment",
    "blocked-skip-to-delivery-harness",
    "blocked-automatic-execution",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

PRIVACY_FLAGS = {
    **reopen_backlog_bridge.PRIVACY_FLAGS,
    "reopen_intake_product_owner_gate_metadata_only": True,
    "product_owner_identity_included": False,
    "priority_score_included": False,
    "raw_product_spec_included": False,
    "raw_eval_body_included": False,
    "raw_backlog_data_included": False,
    "customer_visible_follow_up_included": False,
    "spec_eval_candidate_metadata_only": True,
}

EFFECT_BOUNDARY = {
    **reopen_backlog_bridge.EFFECT_BOUNDARY,
    "study_anything_spec_eval_storage_mutated": False,
    "study_anything_spec_eval_candidate_queue_mutated": False,
    "study_anything_automatic_execution_performed": False,
    "study_anything_customer_visible_follow_up_performed": False,
}

FORBIDDEN_RAW_FIELDS = {
    *reopen_backlog_bridge.FORBIDDEN_RAW_FIELDS,
    "product_owner_identity",
    "owner_identity",
    "assigned_priority",
    "automatic_priority",
    "priority_score",
    "priority_rank",
    "priority_value",
    "raw_backlog_data",
    "raw_backlog_body",
    "backlog_item_body",
    "raw_product_spec",
    "product_spec_body",
    "raw_eval_body",
    "eval_prompt",
    "customer_visible_follow_up",
    "customer_visible_reply",
    "follow_up_body",
    "source_mutation_payload",
    "production_payload",
}

BLOCKED_DESTINATIONS = [
    "automatic_priority_assignment",
    "automatic_execution",
    "customer_visible_follow_up",
    "source_mutation",
    "external_publication",
    "production_mutation",
    "model_call",
]

CLAIM_BOUNDARY = {
    "current_claim": (
        "A restarted Product Loop backlog signal from the reopen-intake bridge can "
        "become a metadata-only spec/eval candidate only after active Product Owner "
        "boundary reconstruction. The candidate remains unprioritized, non-executable, "
        "not customer-visible, and outside source or production effects."
    ),
    "not_claimed": [
        "live backlog item created",
        "automatic priority assignment",
        "automatic execution",
        "customer-visible follow-up",
        "raw backlog data included",
        "raw follow-up data included",
        "raw customer data included",
        "customer identity included",
        "source mutation",
        "external publication",
        "production mutation",
        "model call performed",
        "spec/eval authored",
        "customer satisfaction guarantee",
    ],
}


class PatchProposalControlledFollowUpFeedbackProductOwnerGateError(ValueError):
    """Raised when the controlled follow-up reopen-intake Product Owner gate is unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"Expected JSON object: {path}")
    return payload


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dump_json(payload))


def _base(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"{label}.{key} must be an object")
    return value


def _forbidden_raw_paths(payload: Any, *, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child = f"{path}.{key}"
            if str(key) in FORBIDDEN_RAW_FIELDS:
                paths.append(child)
            paths.extend(_forbidden_raw_paths(value, path=child))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            paths.extend(_forbidden_raw_paths(value, path=f"{path}[{index}]"))
    return paths


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.assert_metadata_only(payload, label=label)
    forbidden = _forbidden_raw_paths(payload)
    if forbidden:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _validate_effect_boundary(payload: Mapping[str, Any], *, label: str) -> None:
    effect = _require_object(payload, "effect_boundary", label=label)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(
                f"{label}.effect_boundary.{key} must be {expected!r}"
            )


def _bridge_case_for_product_owner_case(case_id: str) -> str | None:
    bridge_cases = {
        "pass": "pass",
        "blocked-missing-backlog-bridge-receipt": None,
        "blocked-bridge-blocked": "blocked-gate-blocked",
        "blocked-missing-gate-ref": "blocked-missing-gate-receipt",
        "blocked-missing-bridge-ref": "blocked-missing-bridge-ref",
        "blocked-missing-closure-ref": "blocked-missing-closure-ref",
        "blocked-missing-outcome-ref": "blocked-missing-outcome-ref",
        "blocked-missing-action-ref": "blocked-missing-action-ref",
        "blocked-missing-actor-ref": "blocked-missing-actor-ref",
        "blocked-missing-intake-candidate-ref": "blocked-missing-intake-candidate-ref",
        "blocked-missing-intake-item-ref": "blocked-missing-intake-item-ref",
        "blocked-missing-claim-boundary": "blocked-missing-claim-boundary",
        "blocked-missing-privacy-boundary": "blocked-missing-privacy-boundary",
        "blocked-raw-follow-up-data": "blocked-raw-follow-up-data",
        "blocked-raw-customer-data": "blocked-raw-customer-data",
        "blocked-raw-backlog-data": "pass",
        "blocked-customer-identity": "blocked-customer-identity",
        "blocked-automatic-customer-contact": "blocked-automatic-customer-contact",
        "blocked-automatic-backlog-creation": "blocked-automatic-backlog-creation",
        "blocked-automatic-priority-assignment": "blocked-automatic-prioritization",
        "blocked-automatic-execution": "blocked-automatic-execution",
        "blocked-product-loop-backlog-mutation": "blocked-product-loop-backlog-mutation",
        "blocked-source-mutation": "blocked-source-mutation",
        "blocked-production-mutation": "blocked-production-mutation",
        "blocked-external-publication-payload": "blocked-external-publication-payload",
        "blocked-model-call": "blocked-model-call",
        "blocked-secret": "blocked-secret",
        "blocked-model-credential": "blocked-model-credential",
    }
    return bridge_cases.get(case_id, "pass")


def source_bridge(case_id: str) -> dict[str, Any] | None:
    bridge_case = _bridge_case_for_product_owner_case(case_id)
    if bridge_case is None:
        return None
    bridge = reopen_backlog_bridge.build_controlled_follow_up_feedback_reopen_intake_backlog_bridge(bridge_case)
    return reopen_backlog_bridge.validate_controlled_follow_up_feedback_reopen_intake_backlog_bridge(bridge)


def source_signal(case_id: str) -> dict[str, Any] | None:
    bridge = source_bridge(case_id)
    if bridge is None:
        return None
    signal = bridge.get("backlog_signal")
    return reopen_backlog_bridge.validate_backlog_signal(signal) if isinstance(signal, Mapping) else None


def validate_backlog_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    validated = reopen_backlog_bridge.validate_backlog_signal(signal)
    if validated.get("destination") != "product_loop_backlog":
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("source signal must come from product_loop_backlog")
    if validated.get("next_boundary") != "product_owner_prioritization":
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("source signal must stop at product owner prioritization")
    if validated.get("priority_assignment") != "not_assigned":
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("source signal must not include priority assignment")
    required_refs = (
        "signal_id",
        "source_reopen_intake_gate_ref",
        "source_reopen_intake_bridge_ref",
        "closure_receipt_hash",
        "outcome_receipt_hash",
        "action_ref_hash",
        "external_actor_ref_hash",
        "intake_candidate_ref_hash",
        "product_loop_intake_item_ref_hash",
    )
    for key in required_refs:
        value = validated.get(key)
        if not isinstance(value, str) or not value:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(
                f"source signal missing required reopen-intake ref: {key}"
            )
    for key in ("ready_for_execution", "ready_for_customer_delivery"):
        if validated.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"source signal {key} must remain false")
    return validated


def build_candidate(backlog_signal: Mapping[str, Any]) -> dict[str, Any]:
    signal = validate_backlog_signal(backlog_signal)
    signal_hash = artifact_hash(signal)
    candidate = {
        **_base(CANDIDATE_SCHEMA_VERSION),
        "candidate_id": f"patch-proposal-reopen-intake-spec-eval-candidate-{signal_hash[:16]}",
        "source_backlog_signal_id": signal["signal_id"],
        "source_backlog_signal_hash": signal_hash,
        "source_feedback_intake_id": signal["source_feedback_intake_id"],
        "source_feedback_intake_case_id": signal["source_feedback_intake_case_id"],
        "source_feedback_intake_hash": signal["source_feedback_intake_hash"],
        "source_feedback_intake_ref": signal["source_feedback_intake_ref"],
        "source_reopen_intake_gate_ref": signal["source_reopen_intake_gate_ref"],
        "source_reopen_intake_gate_hash": signal["source_reopen_intake_gate_hash"],
        "source_reopen_intake_bridge_ref": signal["source_reopen_intake_bridge_ref"],
        "source_reopen_intake_bridge_hash": signal["source_reopen_intake_bridge_hash"],
        "closure_receipt_hash": signal["closure_receipt_hash"],
        "outcome_receipt_hash": signal["outcome_receipt_hash"],
        "action_ref_hash": signal["action_ref_hash"],
        "external_actor_ref_hash": signal["external_actor_ref_hash"],
        "intake_candidate_ref_hash": signal["intake_candidate_ref_hash"],
        "product_loop_intake_item_ref_hash": signal["product_loop_intake_item_ref_hash"],
        "source_delivery_class": "patch-proposal",
        "feedback_ref": {
            "signal_type": signal["feedback_ref"]["signal_type"],
            "signal_ref_hash": signal["feedback_ref"]["signal_ref_hash"],
            "payload_hash_only": True,
            "raw_feedback_included": False,
            "customer_identity_included": False,
            "private_customer_data_included": False,
        },
        "loop": "developer_feedback_loop",
        "source_loop": "controlled_follow_up_feedback_reopen_intake",
        "destination": "product_spec_eval_candidate_queue",
        "next_boundary": "product_spec_eval_authoring",
        "priority_state": "unassigned",
        "priority_score_included": False,
        "requires_product_owner_prioritization_before_execution": True,
        "ready_for_execution": False,
        "ready_for_delivery_trust_harness": False,
        "provenance_chain": signal.get("provenance_chain", []),
        "blocked_destinations": list(BLOCKED_DESTINATIONS),
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_candidate(candidate)


def validate_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("candidate schema_version drifted")
    _validate_privacy(candidate, label=CANDIDATE_SCHEMA_VERSION)
    _validate_effect_boundary(candidate, label=CANDIDATE_SCHEMA_VERSION)
    if candidate.get("destination") != "product_spec_eval_candidate_queue":
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("candidate destination must be product_spec_eval_candidate_queue")
    if candidate.get("next_boundary") != "product_spec_eval_authoring":
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("candidate next boundary must be product_spec_eval_authoring")
    if candidate.get("priority_state") != "unassigned":
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("candidate priority must remain unassigned")
    if candidate.get("priority_score_included") is not False:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("candidate must not include priority score")
    for key in ("ready_for_execution", "ready_for_delivery_trust_harness"):
        if candidate.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"candidate {key} must remain false")
    blocked = candidate.get("blocked_destinations")
    if not isinstance(blocked, list):
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("candidate blocked_destinations must be a list")
    for destination in BLOCKED_DESTINATIONS:
        if destination not in blocked:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"candidate missing blocked destination: {destination}")
    return dict(candidate)


def build_product_owner_receipt(
    case_id: str,
    *,
    backlog_signal: Mapping[str, Any] | None = None,
    source_bridge_payload: Mapping[str, Any] | None = None,
    active_owner_reconstruction: bool = True,
    requested_next_boundary: str = "product_spec_eval_candidate_queue",
    raw_backlog_data_attached: bool = False,
    automatic_backlog_creation_requested: bool = False,
    automatic_priority_assignment_requested: bool = False,
    automatic_execution_requested: bool = False,
    automatic_customer_contact_requested: bool = False,
    product_loop_backlog_mutation_requested: bool = False,
    source_mutation_requested: bool = False,
    production_mutation_requested: bool = False,
    external_publication_payload_attached: bool = False,
    model_call_requested: bool = False,
    secret_attached: bool = False,
    model_credential_attached: bool = False,
) -> dict[str, Any]:
    bridge = (
        reopen_backlog_bridge.validate_controlled_follow_up_feedback_reopen_intake_backlog_bridge(
            source_bridge_payload
        )
        if source_bridge_payload is not None
        else None
    )
    signal_payload = backlog_signal
    if signal_payload is None and bridge is not None:
        maybe_signal = bridge.get("backlog_signal")
        signal_payload = maybe_signal if isinstance(maybe_signal, Mapping) else None

    reasons: list[str] = []
    source_bridge_blocked_reasons: list[str] = []
    bridge_allowed = bridge is not None and bridge.get("status") == "queued_for_product_loop"
    if bridge is None:
        reasons.append("source_reopen_intake_backlog_bridge_missing")
    elif not bridge_allowed:
        reasons.append("source_reopen_intake_backlog_bridge_not_allowed")
        bridge_reasons = bridge.get("blocked_reasons")
        if isinstance(bridge_reasons, list):
            source_bridge_blocked_reasons = [str(reason) for reason in bridge_reasons]
            reasons.extend(source_bridge_blocked_reasons)

    validated_signal: dict[str, Any] | None = None
    if signal_payload is None:
        reasons.append("source_backlog_signal_missing")
    else:
        try:
            validated_signal = validate_backlog_signal(signal_payload)
        except PatchProposalControlledFollowUpFeedbackProductOwnerGateError as exc:
            reasons.append("backlog_signal_ref_missing")
            source_bridge_blocked_reasons.append(str(exc))
    if not active_owner_reconstruction:
        reasons.append("product_owner_reconstruction_missing")
    if requested_next_boundary != "product_spec_eval_candidate_queue":
        reasons.append("requested_next_boundary_not_product_spec_eval_candidate_queue")
    for flag, reason in (
        (raw_backlog_data_attached, "raw_backlog_data_rejected"),
        (automatic_backlog_creation_requested, "automatic_backlog_creation_rejected"),
        (automatic_priority_assignment_requested, "automatic_priority_assignment_rejected"),
        (automatic_execution_requested, "automatic_execution_rejected"),
        (automatic_customer_contact_requested, "automatic_customer_contact_rejected"),
        (product_loop_backlog_mutation_requested, "product_loop_backlog_mutation_rejected"),
        (source_mutation_requested, "source_mutation_rejected"),
        (production_mutation_requested, "production_mutation_rejected"),
        (external_publication_payload_attached, "external_publication_payload_rejected"),
        (model_call_requested, "model_call_rejected"),
        (secret_attached, "secret_rejected"),
        (model_credential_attached, "model_credential_rejected"),
    ):
        if flag:
            reasons.append(reason)

    candidate = None if reasons else build_candidate(validated_signal or {})
    signal_hash = artifact_hash(validated_signal) if validated_signal is not None else None
    bridge_case = _bridge_case_for_product_owner_case(case_id)
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "product_owner_receipt_id": (
            f"patch-proposal-controlled-follow-up-product-owner-{signal_hash[:16]}"
            if signal_hash
            else f"patch-proposal-controlled-follow-up-product-owner-blocked-{case_id}"
        ),
        "case_id": case_id,
        "status": "queued_for_spec_eval_candidate" if candidate else "blocked",
        "decision": "create_patch_proposal_spec_eval_candidate" if candidate else "block_patch_proposal_product_owner_gate",
        "blocked_reasons": list(dict.fromkeys(reasons)),
        "source_refs": {
            "backlog_bridge_ref": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge/"
                f"{bridge_case}/patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"
                if bridge_case
                else None
            ),
            "backlog_bridge_id": bridge.get("bridge_id") if bridge else None,
            "backlog_bridge_hash": artifact_hash(bridge) if bridge else None,
            "source_bridge_status": bridge.get("status") if bridge else None,
            "source_bridge_blocked_reasons": source_bridge_blocked_reasons,
            "backlog_signal_id": validated_signal.get("signal_id") if validated_signal else None,
            "backlog_signal_hash": signal_hash,
            "reopen_intake_gate_ref": (
                validated_signal.get("source_feedback_intake_ref") if validated_signal else None
            ),
            "reopen_intake_gate_hash": (
                validated_signal.get("source_feedback_intake_hash") if validated_signal else None
            ),
            "reopen_intake_bridge_ref": (
                validated_signal.get("source_reopen_intake_bridge_ref") if validated_signal else None
            ),
            "reopen_intake_bridge_hash": (
                validated_signal.get("source_reopen_intake_bridge_hash") if validated_signal else None
            ),
            "closure_receipt_hash": validated_signal.get("closure_receipt_hash") if validated_signal else None,
            "outcome_receipt_hash": validated_signal.get("outcome_receipt_hash") if validated_signal else None,
            "action_ref_hash": validated_signal.get("action_ref_hash") if validated_signal else None,
            "external_actor_ref_hash": validated_signal.get("external_actor_ref_hash") if validated_signal else None,
            "intake_candidate_ref_hash": validated_signal.get("intake_candidate_ref_hash") if validated_signal else None,
            "product_loop_intake_item_ref_hash": (
                validated_signal.get("product_loop_intake_item_ref_hash") if validated_signal else None
            ),
        },
        "product_owner_reconstruction": {
            "active_reconstruction_present": active_owner_reconstruction,
            "passive_attention_only_sufficient": False,
            "owner_ref": "product-owner-role",
            "reconstructed_boundaries": [
                "controlled_follow_up_feedback_signal_hash_only",
                "reopen_intake_backlog_signal_hash_only",
                "full_reopen_intake_evidence_chain_preserved",
                "spec_eval_candidate_queue_only",
                "priority_unassigned",
                "no_automatic_execution",
                "no_automatic_backlog_creation",
                "no_automatic_customer_contact",
                "no_source_mutation",
                "no_production_mutation",
            ],
        },
        "requested_transition": {
            "from": "product_loop_backlog",
            "to": requested_next_boundary,
            "raw_backlog_data_attached": raw_backlog_data_attached,
            "automatic_backlog_creation_requested": automatic_backlog_creation_requested,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "automatic_customer_contact_requested": automatic_customer_contact_requested,
            "product_loop_backlog_mutation_requested": product_loop_backlog_mutation_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_payload_attached": external_publication_payload_attached,
            "model_call_requested": model_call_requested,
        },
        "product_owner_policy": {
            "allowed_next_boundary": "product_spec_eval_candidate_queue",
            "automatic_backlog_creation_allowed": False,
            "automatic_priority_assignment_allowed": False,
            "automatic_execution_allowed": False,
            "automatic_customer_contact_allowed": False,
            "product_loop_backlog_mutation_allowed": False,
            "source_mutation_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "model_calls_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "checks": {
            "source_reopen_intake_backlog_bridge_present": bridge is not None,
            "source_reopen_intake_backlog_bridge_allowed": bridge_allowed,
            "source_backlog_signal_present": validated_signal is not None,
            "active_product_owner_reconstruction_present": active_owner_reconstruction,
            "metadata_only_candidate": True,
            "raw_backlog_data_attached": raw_backlog_data_attached,
            "automatic_backlog_creation_requested": automatic_backlog_creation_requested,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "automatic_customer_contact_requested": automatic_customer_contact_requested,
            "product_loop_backlog_mutation_requested": product_loop_backlog_mutation_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_payload_attached": external_publication_payload_attached,
            "model_call_requested": model_call_requested,
            "secret_attached": secret_attached,
            "model_credential_attached": model_credential_attached,
        },
        "quality_gates": {
            "accepted_backlog_signal_required": True,
            "active_product_owner_reconstruction_required": True,
            "metadata_only_spec_eval_candidate_required": True,
            "raw_backlog_data_rejected": True,
            "automatic_backlog_creation_blocked": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_execution_blocked": True,
            "automatic_customer_contact_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "candidate": candidate,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_product_owner_receipt(receipt)


def validate_product_owner_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    _validate_effect_boundary(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    decision = receipt.get("decision")
    reasons = receipt.get("blocked_reasons")
    candidate = receipt.get("candidate")
    if status not in {"queued_for_spec_eval_candidate", "blocked"}:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("receipt status must be queued_for_spec_eval_candidate or blocked")
    if not isinstance(reasons, list):
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("receipt blocked_reasons must be a list")
    if status == "queued_for_spec_eval_candidate":
        if decision != "create_patch_proposal_spec_eval_candidate":
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("queued receipt must create a patch proposal spec/eval candidate")
        if reasons:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("queued receipt must not carry blocked reasons")
        if not isinstance(candidate, Mapping):
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("queued receipt must include candidate")
        validate_candidate(candidate)
    else:
        if decision != "block_patch_proposal_product_owner_gate":
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("blocked receipt must block the Product Owner gate")
        if not reasons:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("blocked receipt must include reasons")
        if candidate is not None:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("blocked receipt must not include candidate")

    reconstruction = _require_object(receipt, "product_owner_reconstruction", label=RECEIPT_SCHEMA_VERSION)
    if reconstruction.get("passive_attention_only_sufficient") is not False:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("passive Product Owner attention alone is insufficient")
    if status == "queued_for_spec_eval_candidate" and reconstruction.get("active_reconstruction_present") is not True:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("queued receipt requires active Product Owner reconstruction")
    policy = _require_object(receipt, "product_owner_policy", label=RECEIPT_SCHEMA_VERSION)
    if policy.get("allowed_next_boundary") != "product_spec_eval_candidate_queue":
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError("policy must stop at spec/eval candidate queue")
    for key in (
        "automatic_backlog_creation_allowed",
        "automatic_priority_assignment_allowed",
        "automatic_execution_allowed",
        "automatic_customer_contact_allowed",
        "product_loop_backlog_mutation_allowed",
        "source_mutation_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
        "model_calls_allowed",
    ):
        if policy.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"policy.{key} must be False")
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    for key in (
        "raw_backlog_data_attached",
        "automatic_backlog_creation_requested",
        "automatic_priority_assignment_requested",
        "automatic_execution_requested",
        "automatic_customer_contact_requested",
        "product_loop_backlog_mutation_requested",
        "source_mutation_requested",
        "production_mutation_requested",
        "external_publication_payload_attached",
        "model_call_requested",
        "secret_attached",
        "model_credential_attached",
    ):
        if status == "queued_for_spec_eval_candidate" and checks.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"queued receipt checks.{key} must be False")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpFeedbackProductOwnerGateError(f"Unknown case id: {case_id}")
    bridge = source_bridge(case_id)
    signal = source_signal(case_id)
    if case_id == "blocked-missing-backlog-signal-ref" and signal is not None:
        signal = copy.deepcopy(signal)
        signal.pop("signal_id", None)
    receipt = build_product_owner_receipt(
        case_id,
        backlog_signal=signal,
        source_bridge_payload=bridge,
        active_owner_reconstruction=case_id != "blocked-missing-owner-reconstruction",
        requested_next_boundary=(
            "delivery_trust_harness" if case_id == "blocked-skip-to-delivery-harness" else "product_spec_eval_candidate_queue"
        ),
        raw_backlog_data_attached=case_id == "blocked-raw-backlog-data",
        automatic_backlog_creation_requested=case_id == "blocked-automatic-backlog-creation",
        automatic_priority_assignment_requested=case_id == "blocked-automatic-priority-assignment",
        automatic_execution_requested=case_id == "blocked-automatic-execution",
        automatic_customer_contact_requested=case_id == "blocked-automatic-customer-contact",
        product_loop_backlog_mutation_requested=case_id == "blocked-product-loop-backlog-mutation",
        source_mutation_requested=case_id == "blocked-source-mutation",
        production_mutation_requested=case_id == "blocked-production-mutation",
        external_publication_payload_attached=case_id == "blocked-external-publication-payload",
        model_call_requested=case_id == "blocked-model-call",
        secret_attached=case_id == "blocked-secret",
        model_credential_attached=case_id == "blocked-model-credential",
    )
    artifacts = {"patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json": receipt}
    candidate = receipt.get("candidate")
    if isinstance(candidate, Mapping):
        artifacts["patch-proposal-product-spec-eval-candidate.json"] = dict(candidate)
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_product_owner_receipt(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "candidate_created": receipt["candidate"] is not None,
            }
        )
    queued_count = sum(1 for row in case_reports if row["status"] == "queued_for_spec_eval_candidate")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove controlled follow-up feedback reopen-intake backlog signals can create metadata-only "
            "spec/eval candidates only after active Product Owner boundary reconstruction, without live "
            "backlog creation, priority assignment, execution, customer contact, backlog/source/production "
            "mutation, external publication, model calls, secrets, or model credentials."
        ),
        "source_chain": {
            "controlled_follow_up_feedback_reopen_intake_backlog_bridge_report": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"
            ),
            "recorded_backlog_signal": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge/"
                "pass/product-loop-backlog-signal.json"
            ),
        },
        "product_owner_matrix": {
            "queued_spec_eval_candidates": queued_count,
            "blocked_product_owner_transitions": blocked_count,
            "total_cases": len(case_reports),
            "reopen_intake_backlog_signal_queued": True,
            "missing_backlog_bridge_receipt_rejected": True,
            "blocked_backlog_bridge_rejected": True,
            "missing_gate_ref_rejected": True,
            "missing_bridge_ref_rejected": True,
            "missing_closure_ref_rejected": True,
            "missing_outcome_ref_rejected": True,
            "missing_action_ref_rejected": True,
            "missing_actor_ref_rejected": True,
            "missing_intake_candidate_ref_rejected": True,
            "missing_intake_item_ref_rejected": True,
            "missing_backlog_signal_ref_rejected": True,
            "missing_owner_reconstruction_rejected": True,
            "missing_claim_boundary_rejected": True,
            "missing_privacy_boundary_rejected": True,
            "raw_follow_up_data_rejected": True,
            "raw_customer_data_rejected": True,
            "raw_backlog_data_rejected": True,
            "customer_identity_rejected": True,
            "automatic_customer_contact_rejected": True,
            "automatic_backlog_creation_rejected": True,
            "automatic_priority_assignment_rejected": True,
            "skip_to_delivery_harness_rejected": True,
            "automatic_execution_rejected": True,
            "product_loop_backlog_mutation_rejected": True,
            "source_mutation_rejected": True,
            "production_mutation_rejected": True,
            "external_publication_payload_rejected": True,
            "model_call_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "accepted_backlog_signal_required": True,
            "source_reopen_intake_backlog_bridge_required": True,
            "active_product_owner_reconstruction_required": True,
            "metadata_only_spec_eval_candidate_required": True,
            "raw_follow_up_customer_and_backlog_data_rejected": True,
            "customer_identity_rejected": True,
            "automatic_backlog_creation_blocked": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_execution_blocked": True,
            "automatic_customer_contact_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    _validate_privacy(report, label=REPORT_SCHEMA_VERSION)
    _validate_effect_boundary(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_case_artifacts(output_dir: Path, cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            write_json(output_dir / case_id / filename, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    selected = CASE_IDS if args.case == "all" else (args.case,)
    cases = {case_id: build_case_artifacts(case_id) for case_id in selected}
    write_case_artifacts(args.output_dir, cases)
    result: dict[str, Any] = {
        "schema_version": "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-gate-cli-result-v1",
        "status": "ok",
        "case_ids": list(cases),
        "output_dir_ref": args.output_dir.name,
        "queued_spec_eval_candidates": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]["status"]
            == "queued_for_spec_eval_candidate"
        ),
        "blocked_product_owner_transitions": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]["status"]
            == "blocked"
        ),
        "privacy": dict(PRIVACY_FLAGS),
        "effect_boundary": dict(EFFECT_BOUNDARY),
    }
    if args.report:
        result["report"] = build_report(cases)
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
