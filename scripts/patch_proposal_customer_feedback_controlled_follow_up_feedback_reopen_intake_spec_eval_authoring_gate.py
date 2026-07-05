#!/usr/bin/env python3
"""Gate Patch Proposal controlled follow-up feedback reopen-intake spec/eval authoring.

This layer consumes `patch-proposal-product-spec-eval-candidate-v1` artifacts
from the controlled follow-up feedback reopen-intake Product Owner Gate. It can emit only a
metadata-only Product Loop brief candidate after active authoring-boundary
reconstruction. It never writes raw specs, raw eval prompts, executes work,
contacts customers, mutates source, mutates production, calls models, or stores
secrets or model credentials.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import cbb_protocol, dual_loop  # noqa: E402
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate as owner_gate  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt-v1"
BRIEF_CANDIDATE_SCHEMA_VERSION = "patch-proposal-product-loop-brief-candidate-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate"

CASE_IDS = (
    "pass",
    "blocked-missing-product-owner-receipt",
    "blocked-product-owner-blocked",
    "blocked-missing-spec-eval-candidate-ref",
    "blocked-missing-gate-ref",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-backlog-signal-ref",
    "blocked-missing-product-owner-ref",
    "blocked-missing-authoring-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-spec-body",
    "blocked-raw-eval-body",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-raw-backlog-data",
    "blocked-customer-identity",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-priority-assignment",
    "blocked-automatic-execution",
    "blocked-skip-to-delivery-trust",
    "blocked-customer-contact",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

PRIVACY_FLAGS = {
    **owner_gate.PRIVACY_FLAGS,
    "raw_acceptance_criteria_included": False,
    "raw_eval_prompt_included": False,
    "raw_eval_dataset_included": False,
    "raw_follow_up_data_included": False,
    "raw_customer_data_included": False,
    "raw_backlog_data_included": False,
    "product_loop_brief_candidate_metadata_only": True,
}

EFFECT_BOUNDARY = {
    **owner_gate.EFFECT_BOUNDARY,
    "study_anything_raw_spec_storage_mutated": False,
    "study_anything_eval_storage_mutated": False,
    "study_anything_product_loop_brief_candidate_queue_mutated": False,
    "study_anything_delivery_trust_harness_mutated": False,
}

FORBIDDEN_RAW_FIELDS = {
    *owner_gate.FORBIDDEN_RAW_FIELDS,
    "raw_acceptance_criteria",
    "acceptance_criteria_text",
    "raw_eval_prompt",
    "eval_prompt",
    "raw_eval_dataset",
    "eval_dataset_body",
    "raw_follow_up_data",
    "raw_customer_data",
    "raw_backlog_data",
    "raw_brief_body",
    "brief_body",
    "product_loop_brief_body",
}

BLOCKED_DESTINATIONS = [
    "delivery_trust_harness",
    "automatic_execution",
    "customer_contact",
    "source_mutation",
    "external_publication",
    "production_mutation",
    "model_call",
]

CLAIM_BOUNDARY = {
    "current_claim": (
        "A Patch Proposal controlled follow-up feedback reopen-intake spec/eval candidate can "
        "become a metadata-only Product Loop brief candidate only after active "
        "authoring-boundary reconstruction. The candidate remains non-executable, "
        "model-call-free, and cannot skip to the Delivery Trust Harness."
    ),
    "not_claimed": [
        "finished product spec",
        "finished eval suite",
        "automatic execution",
        "customer contact",
        "automatic backlog creation",
        "automatic priority assignment",
        "source mutation",
        "external publication",
        "production mutation",
        "Delivery Trust Harness readiness",
        "model call performed",
    ],
}


class PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(ValueError):
    """Raised when the Patch Proposal spec/eval authoring gate is unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(f"Expected JSON object: {path}")
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
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in dual_loop.ISOLATION_BOUNDARY.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                f"{label}.isolation.{key} must be {expected!r}"
            )


def _validate_effect_boundary(payload: Mapping[str, Any], *, label: str) -> None:
    effect = _require_object(payload, "effect_boundary", label=label)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                f"{label}.effect_boundary.{key} must be {expected!r}"
            )


def stable_ref(prefix: str, seed: str, index: int) -> dict[str, Any]:
    token = dual_loop.sha256_text(f"{prefix}:{seed}:{index}")[:16]
    return {
        "ref_id": f"{prefix}-{index}",
        "ref_hash": token,
        "body_included": False,
    }


def _owner_case_for_authoring_case(case_id: str) -> str | None:
    owner_cases = {
        "pass": "pass",
        "blocked-missing-product-owner-receipt": None,
        "blocked-product-owner-blocked": "blocked-bridge-blocked",
        "blocked-missing-gate-ref": "blocked-missing-gate-ref",
        "blocked-missing-bridge-ref": "blocked-missing-bridge-ref",
        "blocked-missing-closure-ref": "blocked-missing-closure-ref",
        "blocked-missing-outcome-ref": "blocked-missing-outcome-ref",
        "blocked-missing-action-ref": "blocked-missing-action-ref",
        "blocked-missing-actor-ref": "blocked-missing-actor-ref",
        "blocked-missing-intake-candidate-ref": "blocked-missing-intake-candidate-ref",
        "blocked-missing-intake-item-ref": "blocked-missing-intake-item-ref",
        "blocked-missing-backlog-signal-ref": "blocked-missing-backlog-signal-ref",
        "blocked-missing-product-owner-ref": "blocked-missing-owner-reconstruction",
        "blocked-missing-claim-boundary": "blocked-missing-claim-boundary",
        "blocked-missing-privacy-boundary": "blocked-missing-privacy-boundary",
        "blocked-raw-follow-up-data": "blocked-raw-follow-up-data",
        "blocked-raw-customer-data": "blocked-raw-customer-data",
        "blocked-raw-backlog-data": "blocked-raw-backlog-data",
        "blocked-customer-identity": "blocked-customer-identity",
        "blocked-automatic-backlog-creation": "blocked-automatic-backlog-creation",
        "blocked-automatic-priority-assignment": "blocked-automatic-priority-assignment",
        "blocked-automatic-execution": "blocked-automatic-execution",
        "blocked-customer-contact": "blocked-automatic-customer-contact",
        "blocked-product-loop-backlog-mutation": "blocked-product-loop-backlog-mutation",
        "blocked-source-mutation": "blocked-source-mutation",
        "blocked-production-mutation": "blocked-production-mutation",
        "blocked-external-publication-payload": "blocked-external-publication-payload",
        "blocked-model-call": "blocked-model-call",
        "blocked-secret": "blocked-secret",
        "blocked-model-credential": "blocked-model-credential",
    }
    return owner_cases.get(case_id, "pass")


def source_product_owner_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    source_case = _owner_case_for_authoring_case(case_id)
    if source_case is None:
        return {}
    return owner_gate.build_case_artifacts(source_case)


def source_product_owner_candidate(case_id: str) -> dict[str, Any] | None:
    artifacts = source_product_owner_artifacts(case_id)
    receipt = artifacts.get("patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json")
    if not isinstance(receipt, Mapping):
        return None
    candidate = receipt.get("candidate")
    return owner_gate.validate_candidate(candidate) if isinstance(candidate, Mapping) else None


def validate_source_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validated = owner_gate.validate_candidate(candidate)
    if validated.get("destination") != "product_spec_eval_candidate_queue":
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "source candidate must come from product_spec_eval_candidate_queue"
        )
    if validated.get("next_boundary") != "product_spec_eval_authoring":
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "source candidate must stop at product_spec_eval_authoring"
        )
    if validated.get("ready_for_execution") is not False:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("source candidate must not be executable")
    if validated.get("ready_for_delivery_trust_harness") is not False:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "source candidate must not be ready for Delivery Trust Harness"
        )
    required_refs = (
        "candidate_id",
        "source_backlog_signal_id",
        "source_backlog_signal_hash",
        "source_feedback_intake_id",
        "source_feedback_intake_hash",
        "source_feedback_intake_ref",
        "source_reopen_intake_gate_ref",
        "source_reopen_intake_gate_hash",
        "source_reopen_intake_bridge_ref",
        "source_reopen_intake_bridge_hash",
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
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                f"source candidate missing required reopen-intake ref: {key}"
            )
    return validated


def build_brief_candidate(source_candidate: Mapping[str, Any]) -> dict[str, Any]:
    candidate = validate_source_candidate(source_candidate)
    source_hash = artifact_hash(candidate)
    brief_candidate = {
        **_base(BRIEF_CANDIDATE_SCHEMA_VERSION),
        "brief_candidate_id": f"patch-proposal-product-loop-brief-candidate-{source_hash[:16]}",
        "source_spec_eval_candidate_id": candidate["candidate_id"],
        "source_spec_eval_candidate_hash": source_hash,
        "source_backlog_signal_id": candidate["source_backlog_signal_id"],
        "source_backlog_signal_hash": candidate["source_backlog_signal_hash"],
        "source_feedback_intake_id": candidate["source_feedback_intake_id"],
        "source_feedback_intake_hash": candidate["source_feedback_intake_hash"],
        "source_feedback_intake_ref": candidate["source_feedback_intake_ref"],
        "source_reopen_intake_gate_ref": candidate["source_reopen_intake_gate_ref"],
        "source_reopen_intake_gate_hash": candidate["source_reopen_intake_gate_hash"],
        "source_reopen_intake_bridge_ref": candidate["source_reopen_intake_bridge_ref"],
        "source_reopen_intake_bridge_hash": candidate["source_reopen_intake_bridge_hash"],
        "closure_receipt_hash": candidate["closure_receipt_hash"],
        "outcome_receipt_hash": candidate["outcome_receipt_hash"],
        "action_ref_hash": candidate["action_ref_hash"],
        "external_actor_ref_hash": candidate["external_actor_ref_hash"],
        "intake_candidate_ref_hash": candidate["intake_candidate_ref_hash"],
        "product_loop_intake_item_ref_hash": candidate["product_loop_intake_item_ref_hash"],
        "source_delivery_class": "patch-proposal",
        "feedback_ref": {
            "signal_type": candidate["feedback_ref"]["signal_type"],
            "signal_ref_hash": candidate["feedback_ref"]["signal_ref_hash"],
            "payload_hash_only": True,
            "raw_feedback_included": False,
            "private_customer_data_included": False,
        },
        "loop": "developer_feedback_loop",
        "source_loop": "controlled_follow_up_feedback_reopen_intake",
        "destination": "product_loop_brief_candidate_queue",
        "next_boundary": "product_loop_brief_intake",
        "spec_ref": {
            "problem_statement_hash": dual_loop.sha256_text("problem:" + source_hash)[:16],
            "scope_boundary_hash": dual_loop.sha256_text("scope:" + source_hash)[:16],
            "raw_spec_body_included": False,
        },
        "acceptance_criteria_refs": [stable_ref("patch-acceptance-criterion", source_hash, index) for index in range(1, 4)],
        "eval_plan_refs": [stable_ref("patch-eval-plan", source_hash, index) for index in range(1, 4)],
        "quality_gates": {
            "source_candidate_required": True,
            "active_authoring_reconstruction_required": True,
            "raw_spec_body_allowed": False,
            "raw_eval_prompt_allowed": False,
            "ai_review_only_rejected": True,
            "delivery_trust_harness_skip_blocked": True,
        },
        "ready_for_product_loop_brief_intake": True,
        "ready_for_execution": False,
        "ready_for_delivery_trust_harness": False,
        "blocked_destinations": list(BLOCKED_DESTINATIONS),
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_brief_candidate(brief_candidate)


def validate_brief_candidate(brief_candidate: Mapping[str, Any]) -> dict[str, Any]:
    if brief_candidate.get("schema_version") != BRIEF_CANDIDATE_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("brief candidate schema_version drifted")
    _validate_privacy(brief_candidate, label=BRIEF_CANDIDATE_SCHEMA_VERSION)
    _validate_effect_boundary(brief_candidate, label=BRIEF_CANDIDATE_SCHEMA_VERSION)
    if brief_candidate.get("destination") != "product_loop_brief_candidate_queue":
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "brief candidate destination must be product_loop_brief_candidate_queue"
        )
    if brief_candidate.get("next_boundary") != "product_loop_brief_intake":
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "brief candidate next boundary must be product_loop_brief_intake"
        )
    if brief_candidate.get("ready_for_product_loop_brief_intake") is not True:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "brief candidate must be ready only for Product Loop brief intake"
        )
    for key in ("ready_for_execution", "ready_for_delivery_trust_harness"):
        if brief_candidate.get(key) is not False:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(f"brief candidate {key} must be false")
    if not isinstance(brief_candidate.get("acceptance_criteria_refs"), list):
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "brief candidate acceptance_criteria_refs must be a list"
        )
    if not isinstance(brief_candidate.get("eval_plan_refs"), list):
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("brief candidate eval_plan_refs must be a list")
    spec_ref = brief_candidate.get("spec_ref")
    if not isinstance(spec_ref, Mapping) or spec_ref.get("raw_spec_body_included") is not False:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("brief candidate spec_ref must exclude raw spec")
    blocked = brief_candidate.get("blocked_destinations")
    if not isinstance(blocked, list):
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "brief candidate blocked_destinations must be a list"
        )
    for destination in BLOCKED_DESTINATIONS:
        if destination not in blocked:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                f"brief candidate missing blocked destination: {destination}"
            )
    return dict(brief_candidate)


def build_authoring_receipt(
    case_id: str,
    *,
    source_candidate: Mapping[str, Any] | None = None,
    source_product_owner_receipt: Mapping[str, Any] | None = None,
    active_authoring_reconstruction: bool = True,
    requested_next_boundary: str = "product_loop_brief_intake",
    raw_spec_body_requested: bool = False,
    raw_eval_body_requested: bool = False,
    raw_follow_up_data_attached: bool = False,
    raw_customer_data_attached: bool = False,
    raw_backlog_data_attached: bool = False,
    automatic_backlog_creation_requested: bool = False,
    automatic_priority_assignment_requested: bool = False,
    automatic_execution_requested: bool = False,
    customer_contact_requested: bool = False,
    product_loop_backlog_mutation_requested: bool = False,
    source_mutation_requested: bool = False,
    production_mutation_requested: bool = False,
    external_publication_payload_attached: bool = False,
    model_call_requested: bool = False,
    secret_attached: bool = False,
    model_credential_attached: bool = False,
) -> dict[str, Any]:
    owner_receipt = (
        owner_gate.validate_product_owner_receipt(source_product_owner_receipt)
        if source_product_owner_receipt is not None
        else None
    )
    candidate_payload = source_candidate
    if candidate_payload is None and owner_receipt is not None:
        maybe_candidate = owner_receipt.get("candidate")
        candidate_payload = maybe_candidate if isinstance(maybe_candidate, Mapping) else None

    reasons: list[str] = []
    source_owner_blocked_reasons: list[str] = []
    owner_allowed = owner_receipt is not None and owner_receipt.get("status") == "queued_for_spec_eval_candidate"
    if owner_receipt is None:
        reasons.append("source_product_owner_receipt_missing")
    elif not owner_allowed:
        reasons.append("source_product_owner_receipt_not_allowed")
        owner_reasons = owner_receipt.get("blocked_reasons")
        if isinstance(owner_reasons, list):
            source_owner_blocked_reasons = [str(reason) for reason in owner_reasons]
            reasons.extend(source_owner_blocked_reasons)

    validated_candidate: dict[str, Any] | None = None
    if candidate_payload is None:
        reasons.append("source_spec_eval_candidate_missing")
    else:
        try:
            validated_candidate = validate_source_candidate(candidate_payload)
        except PatchProposalCustomerFeedbackSpecEvalAuthoringGateError as exc:
            if "missing required reopen-intake ref" in str(exc):
                reasons.append("source_spec_eval_candidate_ref_missing")
            else:
                reasons.append("source_spec_eval_candidate_invalid")
            source_owner_blocked_reasons.append(str(exc))
    if not active_authoring_reconstruction:
        reasons.append("authoring_reconstruction_missing")
    if requested_next_boundary != "product_loop_brief_intake":
        reasons.append("requested_next_boundary_not_product_loop_brief_intake")
    for flag, reason in (
        (raw_spec_body_requested, "raw_spec_body_rejected"),
        (raw_eval_body_requested, "raw_eval_body_rejected"),
        (raw_follow_up_data_attached, "raw_follow_up_data_rejected"),
        (raw_customer_data_attached, "raw_customer_data_rejected"),
        (raw_backlog_data_attached, "raw_backlog_data_rejected"),
        (automatic_backlog_creation_requested, "automatic_backlog_creation_rejected"),
        (automatic_priority_assignment_requested, "automatic_priority_assignment_rejected"),
        (automatic_execution_requested, "automatic_execution_rejected"),
        (customer_contact_requested, "customer_contact_rejected"),
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

    brief_candidate = None if reasons else build_brief_candidate(validated_candidate or {})
    source_hash = artifact_hash(validated_candidate) if validated_candidate is not None else None
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "authoring_receipt_id": (
            f"patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-{source_hash[:16]}"
            if source_hash
            else f"patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-blocked-{case_id}"
        ),
        "case_id": case_id,
        "status": "queued_for_product_loop_brief_candidate" if brief_candidate else "blocked",
        "decision": (
            "create_patch_proposal_product_loop_brief_candidate"
            if brief_candidate
            else "block_patch_proposal_spec_eval_authoring_gate"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "product_owner_receipt_ref": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate/"
                f"{_owner_case_for_authoring_case(case_id)}/"
                "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"
                if _owner_case_for_authoring_case(case_id)
                else None
            ),
            "product_owner_receipt_id": owner_receipt.get("product_owner_receipt_id") if owner_receipt else None,
            "product_owner_receipt_hash": artifact_hash(owner_receipt) if owner_receipt else None,
            "product_owner_receipt_status": owner_receipt.get("status") if owner_receipt else None,
            "product_owner_blocked_reasons": source_owner_blocked_reasons,
            "spec_eval_candidate_id": validated_candidate.get("candidate_id") if validated_candidate else None,
            "spec_eval_candidate_hash": source_hash,
            "backlog_signal_id": validated_candidate.get("source_backlog_signal_id") if validated_candidate else None,
            "feedback_intake_id": validated_candidate.get("source_feedback_intake_id") if validated_candidate else None,
            "feedback_intake_ref": validated_candidate.get("source_feedback_intake_ref") if validated_candidate else None,
            "reopen_intake_gate_ref": (
                validated_candidate.get("source_reopen_intake_gate_ref") if validated_candidate else None
            ),
            "reopen_intake_gate_hash": (
                validated_candidate.get("source_reopen_intake_gate_hash") if validated_candidate else None
            ),
            "reopen_intake_bridge_ref": (
                validated_candidate.get("source_reopen_intake_bridge_ref") if validated_candidate else None
            ),
            "reopen_intake_bridge_hash": (
                validated_candidate.get("source_reopen_intake_bridge_hash") if validated_candidate else None
            ),
            "closure_receipt_hash": validated_candidate.get("closure_receipt_hash") if validated_candidate else None,
            "outcome_receipt_hash": validated_candidate.get("outcome_receipt_hash") if validated_candidate else None,
            "action_ref_hash": validated_candidate.get("action_ref_hash") if validated_candidate else None,
            "external_actor_ref_hash": (
                validated_candidate.get("external_actor_ref_hash") if validated_candidate else None
            ),
            "intake_candidate_ref_hash": (
                validated_candidate.get("intake_candidate_ref_hash") if validated_candidate else None
            ),
            "product_loop_intake_item_ref_hash": (
                validated_candidate.get("product_loop_intake_item_ref_hash") if validated_candidate else None
            ),
        },
        "authoring_reconstruction": {
            "active_reconstruction_present": active_authoring_reconstruction,
            "passive_attention_only_sufficient": False,
            "author_ref": "product-spec-eval-author-role",
            "reconstructed_boundaries": [
                "metadata_only_spec_refs",
                "metadata_only_eval_refs",
                "full_reopen_intake_product_owner_chain_preserved",
                "no_raw_spec_body",
                "no_raw_eval_prompt",
                "no_automatic_execution",
                "no_delivery_trust_harness_skip",
                "no_customer_contact",
                "no_source_mutation",
                "no_production_mutation",
            ],
        },
        "requested_transition": {
            "from": "product_spec_eval_candidate_queue",
            "to": requested_next_boundary,
            "raw_spec_body_requested": raw_spec_body_requested,
            "raw_eval_body_requested": raw_eval_body_requested,
            "raw_follow_up_data_attached": raw_follow_up_data_attached,
            "raw_customer_data_attached": raw_customer_data_attached,
            "raw_backlog_data_attached": raw_backlog_data_attached,
            "automatic_backlog_creation_requested": automatic_backlog_creation_requested,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "customer_contact_requested": customer_contact_requested,
            "product_loop_backlog_mutation_requested": product_loop_backlog_mutation_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_payload_attached": external_publication_payload_attached,
            "model_call_requested": model_call_requested,
        },
        "authoring_policy": {
            "allowed_next_boundary": "product_loop_brief_intake",
            "raw_spec_body_allowed": False,
            "raw_eval_body_allowed": False,
            "automatic_backlog_creation_allowed": False,
            "automatic_priority_assignment_allowed": False,
            "automatic_execution_allowed": False,
            "customer_contact_allowed": False,
            "product_loop_backlog_mutation_allowed": False,
            "source_mutation_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "model_calls_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "checks": {
            "source_product_owner_receipt_present": owner_receipt is not None,
            "source_product_owner_receipt_allowed": owner_allowed,
            "source_spec_eval_candidate_present": validated_candidate is not None,
            "active_authoring_reconstruction_present": active_authoring_reconstruction,
            "metadata_only_brief_candidate": True,
            "raw_spec_body_requested": raw_spec_body_requested,
            "raw_eval_body_requested": raw_eval_body_requested,
            "raw_follow_up_data_attached": raw_follow_up_data_attached,
            "raw_customer_data_attached": raw_customer_data_attached,
            "raw_backlog_data_attached": raw_backlog_data_attached,
            "automatic_backlog_creation_requested": automatic_backlog_creation_requested,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "customer_contact_requested": customer_contact_requested,
            "product_loop_backlog_mutation_requested": product_loop_backlog_mutation_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_payload_attached": external_publication_payload_attached,
            "model_call_requested": model_call_requested,
            "secret_attached": secret_attached,
            "model_credential_attached": model_credential_attached,
        },
        "quality_gates": {
            "source_spec_eval_candidate_required": True,
            "active_authoring_reconstruction_required": True,
            "metadata_only_product_loop_brief_candidate_required": True,
            "raw_spec_body_blocked": True,
            "raw_eval_body_blocked": True,
            "raw_follow_up_customer_and_backlog_data_rejected": True,
            "automatic_backlog_creation_blocked": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_execution_blocked": True,
            "delivery_trust_harness_skip_blocked": True,
            "customer_contact_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "brief_candidate": brief_candidate,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_authoring_receipt(receipt)


def validate_authoring_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    _validate_effect_boundary(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    decision = receipt.get("decision")
    reasons = receipt.get("blocked_reasons")
    brief_candidate = receipt.get("brief_candidate")
    if status not in {"queued_for_product_loop_brief_candidate", "blocked"}:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
            "receipt status must be queued_for_product_loop_brief_candidate or blocked"
        )
    if not isinstance(reasons, list):
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("receipt blocked_reasons must be a list")
    if status == "queued_for_product_loop_brief_candidate":
        if decision != "create_patch_proposal_product_loop_brief_candidate":
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                "queued receipt must create a patch proposal Product Loop brief candidate"
            )
        if reasons:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                "queued receipt must not carry blocked reasons"
            )
        if not isinstance(brief_candidate, Mapping):
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("queued receipt must include brief candidate")
        validate_brief_candidate(brief_candidate)
    else:
        if decision != "block_patch_proposal_spec_eval_authoring_gate":
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                "blocked receipt must block the spec/eval authoring gate"
            )
        if not reasons:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("blocked receipt must include reasons")
        if brief_candidate is not None:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                "blocked receipt must not include brief candidate"
            )

    reconstruction = _require_object(receipt, "authoring_reconstruction", label=RECEIPT_SCHEMA_VERSION)
    if reconstruction.get("passive_attention_only_sufficient") is not False:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("passive authoring attention alone is insufficient")
    if status == "queued_for_product_loop_brief_candidate" and reconstruction.get("active_reconstruction_present") is not True:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("queued receipt requires active authoring reconstruction")
    policy = _require_object(receipt, "authoring_policy", label=RECEIPT_SCHEMA_VERSION)
    if policy.get("allowed_next_boundary") != "product_loop_brief_intake":
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError("policy must stop at Product Loop brief intake")
    for key in (
        "raw_spec_body_allowed",
        "raw_eval_body_allowed",
        "automatic_backlog_creation_allowed",
        "automatic_priority_assignment_allowed",
        "automatic_execution_allowed",
        "customer_contact_allowed",
        "product_loop_backlog_mutation_allowed",
        "source_mutation_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
        "model_calls_allowed",
    ):
        if policy.get(key) is not False:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(f"policy.{key} must be False")
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    for key in (
        "raw_spec_body_requested",
        "raw_eval_body_requested",
        "raw_follow_up_data_attached",
        "raw_customer_data_attached",
        "raw_backlog_data_attached",
        "automatic_backlog_creation_requested",
        "automatic_priority_assignment_requested",
        "automatic_execution_requested",
        "customer_contact_requested",
        "product_loop_backlog_mutation_requested",
        "source_mutation_requested",
        "production_mutation_requested",
        "external_publication_payload_attached",
        "model_call_requested",
        "secret_attached",
        "model_credential_attached",
    ):
        if status == "queued_for_product_loop_brief_candidate" and checks.get(key) is not False:
            raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(
                f"queued receipt checks.{key} must be False"
            )
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerFeedbackSpecEvalAuthoringGateError(f"Unknown case id: {case_id}")
    owner_artifacts = source_product_owner_artifacts(case_id)
    owner_receipt = owner_artifacts.get(
        "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"
    )
    source_candidate = source_product_owner_candidate(case_id)
    if case_id == "blocked-missing-spec-eval-candidate-ref" and source_candidate is not None:
        source_candidate = dict(source_candidate)
        source_candidate.pop("candidate_id", None)
    receipt = build_authoring_receipt(
        case_id,
        source_candidate=source_candidate,
        source_product_owner_receipt=owner_receipt,
        active_authoring_reconstruction=case_id != "blocked-missing-authoring-reconstruction",
        requested_next_boundary=(
            "delivery_trust_harness" if case_id == "blocked-skip-to-delivery-trust" else "product_loop_brief_intake"
        ),
        raw_spec_body_requested=case_id == "blocked-raw-spec-body",
        raw_eval_body_requested=case_id == "blocked-raw-eval-body",
        raw_follow_up_data_attached=case_id == "blocked-raw-follow-up-data",
        raw_customer_data_attached=case_id == "blocked-raw-customer-data",
        raw_backlog_data_attached=case_id == "blocked-raw-backlog-data",
        automatic_backlog_creation_requested=case_id == "blocked-automatic-backlog-creation",
        automatic_priority_assignment_requested=case_id == "blocked-automatic-priority-assignment",
        automatic_execution_requested=case_id == "blocked-automatic-execution",
        customer_contact_requested=case_id == "blocked-customer-contact",
        product_loop_backlog_mutation_requested=case_id == "blocked-product-loop-backlog-mutation",
        source_mutation_requested=case_id == "blocked-source-mutation",
        production_mutation_requested=case_id == "blocked-production-mutation",
        external_publication_payload_attached=case_id == "blocked-external-publication-payload",
        model_call_requested=case_id == "blocked-model-call",
        secret_attached=case_id == "blocked-secret",
        model_credential_attached=case_id == "blocked-model-credential",
    )
    artifacts = {"patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json": receipt}
    brief_candidate = receipt.get("brief_candidate")
    if isinstance(brief_candidate, Mapping):
        artifacts["patch-proposal-product-loop-brief-candidate.json"] = dict(brief_candidate)
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_authoring_receipt(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "brief_candidate_created": receipt["brief_candidate"] is not None,
            }
        )
    queued_count = sum(1 for row in case_reports if row["status"] == "queued_for_product_loop_brief_candidate")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove Patch Proposal controlled follow-up feedback reopen-intake spec/eval candidates can create "
            "metadata-only Product Loop brief candidates only after active authoring-boundary "
            "reconstruction, without raw specs, raw eval prompts, execution, Delivery Trust Harness "
            "skips, customer follow-up, source mutation, production mutation, model calls, secrets, "
            "or model credentials."
        ),
        "source_chain": {
            "reopen_intake_product_owner_gate_report": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.json"
            ),
            "recorded_spec_eval_candidate": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate/pass/"
                "patch-proposal-product-spec-eval-candidate.json"
            ),
        },
        "authoring_matrix": {
            "queued_product_loop_brief_candidates": queued_count,
            "blocked_authoring_transitions": blocked_count,
            "total_cases": len(case_reports),
            "reopen_intake_product_owner_candidate_queued": True,
            "missing_product_owner_receipt_rejected": True,
            "blocked_product_owner_receipt_rejected": True,
            "missing_spec_eval_candidate_ref_rejected": True,
            "missing_gate_ref_rejected": True,
            "missing_bridge_ref_rejected": True,
            "missing_closure_ref_rejected": True,
            "missing_outcome_ref_rejected": True,
            "missing_action_ref_rejected": True,
            "missing_actor_ref_rejected": True,
            "missing_intake_candidate_ref_rejected": True,
            "missing_intake_item_ref_rejected": True,
            "missing_backlog_signal_ref_rejected": True,
            "missing_product_owner_ref_rejected": True,
            "missing_authoring_reconstruction_rejected": True,
            "missing_claim_boundary_rejected": True,
            "missing_privacy_boundary_rejected": True,
            "raw_spec_body_rejected": True,
            "raw_eval_body_rejected": True,
            "raw_follow_up_data_rejected": True,
            "raw_customer_data_rejected": True,
            "raw_backlog_data_rejected": True,
            "customer_identity_rejected": True,
            "automatic_backlog_creation_rejected": True,
            "automatic_priority_assignment_rejected": True,
            "automatic_execution_rejected": True,
            "delivery_trust_harness_skip_rejected": True,
            "customer_contact_rejected": True,
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
            "source_spec_eval_candidate_required": True,
            "active_authoring_reconstruction_required": True,
            "metadata_only_product_loop_brief_candidate_required": True,
            "raw_spec_body_blocked": True,
            "raw_eval_body_blocked": True,
            "raw_follow_up_customer_and_backlog_data_rejected": True,
            "customer_identity_rejected": True,
            "automatic_backlog_creation_blocked": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_execution_blocked": True,
            "delivery_trust_harness_skip_blocked": True,
            "customer_contact_blocked": True,
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
    parser.add_argument("--product-owner-candidate", type=Path, help="Build a receipt from a spec/eval candidate JSON file.")
    parser.add_argument("--product-owner-receipt", type=Path, help="Build a receipt from a Product Owner receipt JSON file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.product_owner_candidate or args.product_owner_receipt:
        owner_receipt = load_json(args.product_owner_receipt) if args.product_owner_receipt else None
        source_candidate = load_json(args.product_owner_candidate) if args.product_owner_candidate else None
        cases = {
            "custom": {
                "patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json": build_authoring_receipt(
                    "custom",
                    source_candidate=source_candidate,
                    source_product_owner_receipt=owner_receipt,
                )
            }
        }
        receipt = cases["custom"]["patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"]
        brief_candidate = receipt.get("brief_candidate")
        if isinstance(brief_candidate, Mapping):
            cases["custom"]["patch-proposal-product-loop-brief-candidate.json"] = dict(brief_candidate)
    else:
        selected = CASE_IDS if args.case == "all" else (args.case,)
        cases = {case_id: build_case_artifacts(case_id) for case_id in selected}

    write_case_artifacts(args.output_dir, cases)
    result: dict[str, Any] = {
        "schema_version": "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate-cli-result-v1",
        "status": "ok",
        "case_ids": list(cases),
        "output_dir_ref": args.output_dir.name,
        "queued_product_loop_brief_candidates": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"]["status"]
            == "queued_for_product_loop_brief_candidate"
        ),
        "blocked_authoring_transitions": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"]["status"] == "blocked"
        ),
        "privacy": dict(PRIVACY_FLAGS),
        "effect_boundary": dict(EFFECT_BOUNDARY),
    }
    if args.report and not (args.product_owner_candidate or args.product_owner_receipt):
        result["report"] = build_report(cases)
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
