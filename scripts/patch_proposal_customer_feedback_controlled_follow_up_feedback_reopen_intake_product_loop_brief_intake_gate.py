#!/usr/bin/env python3
"""Gate controlled follow-up feedback reopen-intake Product Loop brief candidates into Product Loop runs.

This layer consumes `patch-proposal-product-loop-brief-candidate-v1` artifacts
from the controlled follow-up feedback reopen-intake Spec/Eval Authoring Gate. It can emit
only metadata-only Product Loop scenario/run candidates after active
developer/product-loop boundary reconstruction.

It does not execute work, call models, send customer-visible follow-up, mutate
source, mutate production, invoke the Delivery Trust Harness, or store raw
brief/spec/eval/customer material.
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

from study_anything.core import cbb_protocol, dual_loop, product_loop_harness  # noqa: E402
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_spec_eval_authoring_gate as authoring_gate  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate"

CASE_IDS = (
    "pass",
    "blocked-missing-authoring-receipt",
    "blocked-authoring-blocked",
    "blocked-missing-brief-candidate-ref",
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
    "blocked-missing-product-loop-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-brief-body",
    "blocked-raw-spec-body",
    "blocked-raw-eval-body",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-raw-backlog-data",
    "blocked-customer-identity",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-priority-assignment",
    "blocked-ai-review-only",
    "blocked-skip-to-delivery-trust",
    "blocked-delivery-trust-invocation",
    "blocked-automatic-execution",
    "blocked-customer-contact",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_NEXT_BOUNDARY = "product_loop_harness_candidate"
FORBIDDEN_NEXT_BOUNDARY = "delivery_trust_harness"

PRIVACY_FLAGS = {
    **authoring_gate.PRIVACY_FLAGS,
    **product_loop_harness.PRODUCT_LOOP_PRIVACY_FLAGS,
    "patch_proposal_brief_candidate_metadata_only": True,
    "product_loop_scenario_candidate_metadata_only": True,
    "product_loop_run_candidate_metadata_only": True,
    "raw_brief_body_included": False,
    "raw_spec_body_included": False,
    "raw_eval_prompt_included": False,
    "raw_customer_feedback_included": False,
}

EFFECT_BOUNDARY = {
    **authoring_gate.EFFECT_BOUNDARY,
    "study_anything_product_loop_scenario_queue_mutated": False,
    "study_anything_product_loop_run_queue_mutated": False,
    "study_anything_delivery_trust_harness_invoked": False,
    "study_anything_customer_visible_follow_up_performed": False,
    "study_anything_source_mutation_performed": False,
    "study_anything_production_mutation_performed": False,
    "study_anything_automatic_execution_performed": False,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
}

FORBIDDEN_RAW_FIELDS = {
    *authoring_gate.FORBIDDEN_RAW_FIELDS,
    "raw_brief_body",
    "brief_body",
    "product_loop_brief_body",
    "raw_spec_body",
    "raw_eval_body",
    "raw_eval_prompt",
    "raw_follow_up_data",
    "raw_customer_data",
    "raw_backlog_data",
    "customer_identity",
    "raw_product_loop_scenario",
    "raw_product_loop_run",
    "raw_customer_feedback",
    "customer_visible_follow_up",
    "customer_visible_reply",
    "follow_up_body",
    "external_publication_payload",
    "source_mutation_payload",
    "production_payload",
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
        "A Patch Proposal controlled follow-up feedback reopen-intake Product Loop brief candidate "
        "can become metadata-only Product Loop scenario/run candidates only after "
        "active developer/product-loop boundary reconstruction. The transition stops "
        "before Delivery Trust Harness invocation and cannot perform automatic, "
        "customer-visible, external publication, source, production, or model-call effects."
    ),
    "not_claimed": [
        "Delivery Trust Harness completed",
        "customer-visible follow-up allowed",
        "source mutation allowed",
        "production mutation allowed",
        "automatic execution",
        "automatic backlog creation or priority assignment",
        "customer contact",
        "external publication allowed",
        "finished customer deliverable",
        "model call performed",
    ],
}


class PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(ValueError):
    """Raised when Patch Proposal Product Loop brief intake is unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(f"Expected JSON object: {path}")
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
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in dual_loop.ISOLATION_BOUNDARY.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                f"{label}.isolation.{key} must be {expected!r}"
            )


def _validate_effect_boundary(payload: Mapping[str, Any], *, label: str) -> None:
    effect = _require_object(payload, "effect_boundary", label=label)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                f"{label}.effect_boundary.{key} must be {expected!r}"
            )


def _authoring_case_for_intake_case(case_id: str) -> str | None:
    authoring_cases = {
        "pass": "pass",
        "blocked-missing-authoring-receipt": None,
        "blocked-authoring-blocked": "blocked-product-owner-blocked",
        "blocked-missing-gate-ref": "blocked-missing-gate-ref",
        "blocked-missing-bridge-ref": "blocked-missing-bridge-ref",
        "blocked-missing-closure-ref": "blocked-missing-closure-ref",
        "blocked-missing-outcome-ref": "blocked-missing-outcome-ref",
        "blocked-missing-action-ref": "blocked-missing-action-ref",
        "blocked-missing-actor-ref": "blocked-missing-actor-ref",
        "blocked-missing-intake-candidate-ref": "blocked-missing-intake-candidate-ref",
        "blocked-missing-intake-item-ref": "blocked-missing-intake-item-ref",
        "blocked-missing-backlog-signal-ref": "blocked-missing-backlog-signal-ref",
        "blocked-missing-product-owner-ref": "blocked-missing-product-owner-ref",
        "blocked-missing-claim-boundary": "blocked-missing-claim-boundary",
        "blocked-missing-privacy-boundary": "blocked-missing-privacy-boundary",
        "blocked-raw-spec-body": "blocked-raw-spec-body",
        "blocked-raw-eval-body": "blocked-raw-eval-body",
        "blocked-raw-follow-up-data": "blocked-raw-follow-up-data",
        "blocked-raw-customer-data": "blocked-raw-customer-data",
        "blocked-raw-backlog-data": "blocked-raw-backlog-data",
        "blocked-customer-identity": "blocked-customer-identity",
        "blocked-automatic-backlog-creation": "blocked-automatic-backlog-creation",
        "blocked-automatic-priority-assignment": "blocked-automatic-priority-assignment",
        "blocked-automatic-execution": "blocked-automatic-execution",
        "blocked-customer-contact": "blocked-customer-contact",
        "blocked-product-loop-backlog-mutation": "blocked-product-loop-backlog-mutation",
        "blocked-source-mutation": "blocked-source-mutation",
        "blocked-production-mutation": "blocked-production-mutation",
        "blocked-external-publication-payload": "blocked-external-publication-payload",
        "blocked-model-call": "blocked-model-call",
        "blocked-secret": "blocked-secret",
        "blocked-model-credential": "blocked-model-credential",
    }
    return authoring_cases.get(case_id, "pass")


def source_authoring_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    source_case = _authoring_case_for_intake_case(case_id)
    if source_case is None:
        return {}
    return authoring_gate.build_case_artifacts(source_case)


def source_authoring_receipt(case_id: str) -> dict[str, Any] | None:
    return source_authoring_artifacts(case_id).get(
        "patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"
    )


def source_brief_candidate(case_id: str) -> dict[str, Any] | None:
    receipt = source_authoring_receipt(case_id)
    if not isinstance(receipt, Mapping):
        return None
    candidate = receipt.get("brief_candidate")
    return authoring_gate.validate_brief_candidate(candidate) if isinstance(candidate, Mapping) else None


def validate_source_brief_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validated = authoring_gate.validate_brief_candidate(candidate)
    if validated.get("destination") != "product_loop_brief_candidate_queue":
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "source brief candidate must come from product_loop_brief_candidate_queue"
        )
    if validated.get("next_boundary") != "product_loop_brief_intake":
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "source brief candidate must stop at product_loop_brief_intake"
        )
    if validated.get("ready_for_product_loop_brief_intake") is not True:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "source brief candidate must be ready for Product Loop brief intake"
        )
    if validated.get("ready_for_execution") is not False:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "source brief candidate must not be executable"
        )
    if validated.get("ready_for_delivery_trust_harness") is not False:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "source brief candidate must not skip to Delivery Trust Harness"
        )
    required_refs = (
        "brief_candidate_id",
        "source_spec_eval_candidate_id",
        "source_spec_eval_candidate_hash",
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
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                f"source brief candidate missing required reopen-intake brief ref: {key}"
            )
    return validated


def _brief_candidate_ref(candidate: Mapping[str, Any], candidate_hash: str) -> dict[str, Any]:
    return {
        "brief_candidate_id": candidate["brief_candidate_id"],
        "source_spec_eval_candidate_id": candidate["source_spec_eval_candidate_id"],
        "source_spec_eval_candidate_hash": candidate["source_spec_eval_candidate_hash"],
        "source_backlog_signal_id": candidate["source_backlog_signal_id"],
        "source_backlog_signal_hash": candidate["source_backlog_signal_hash"],
        "source_feedback_intake_id": candidate["source_feedback_intake_id"],
        "source_feedback_intake_hash": candidate["source_feedback_intake_hash"],
        "source_feedback_intake_ref": candidate.get("source_feedback_intake_ref"),
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
        "brief_candidate_hash": candidate_hash,
        "body_included": False,
        "raw_brief_body_included": False,
        "raw_spec_body_included": False,
        "raw_eval_prompt_included": False,
        "raw_follow_up_data_included": False,
        "raw_customer_feedback_included": False,
        "raw_backlog_data_included": False,
        "customer_identity_included": False,
    }


def build_product_loop_candidate(
    brief_candidate: Mapping[str, Any],
    *,
    external_scope: str = "controlled_customer_handoff",
    ai_review_only: bool = False,
    loop_dominance: bool = False,
) -> dict[str, dict[str, Any]]:
    candidate = validate_source_brief_candidate(brief_candidate)
    candidate_hash = artifact_hash(candidate)
    scenario = product_loop_harness.build_product_loop_scenario(
        "pass",
        external_scope=external_scope,
        ai_review_only=ai_review_only,
        loop_dominance=loop_dominance,
    )
    scenario["scenario_id"] = f"patch-proposal-reopen-intake-product-loop-brief-intake-scenario-{candidate_hash[:16]}"
    scenario["source"] = {
        "source_type": "patch_proposal_reopen_intake_product_loop_brief_candidate",
        "source_ref": candidate["brief_candidate_id"],
        "content_digest": candidate_hash,
    }
    scenario["loops"]["agentic_coding_loop"]["input_ref"] = "patch-proposal-product-loop-brief-candidate.json"
    scenario["loops"]["agentic_coding_loop"]["patch_proposal_brief_candidate_ref"] = _brief_candidate_ref(
        candidate,
        candidate_hash,
    )
    scenario["loops"]["developer_feedback_loop"][
        "reconstruction_ref"
    ] = "patch-proposal-product-loop-brief-intake-reconstruction.json"
    scenario["claim_boundary"] = {
        "current_claim": (
            "This Product Loop scenario/run candidate was created from a metadata-only "
            "Patch Proposal reopen-intake Product Loop brief candidate, not raw "
            "brief/spec/eval/follow-up/customer/backlog bodies."
        ),
        "not_claimed": [
            "Delivery Trust Harness has run",
            "customer delivery is allowed",
            "Product Loop backlog mutation is allowed",
            "source mutation is allowed",
            "production mutation is allowed",
        ],
    }
    scenario = product_loop_harness.validate_product_loop_scenario(scenario)
    run = product_loop_harness.build_product_loop_run(scenario)
    return {
        "product-loop-scenario.json": scenario,
        "product-loop-run.json": run,
    }


def build_intake_receipt(
    case_id: str,
    *,
    brief_candidate: Mapping[str, Any] | None = None,
    source_authoring_receipt_payload: Mapping[str, Any] | None = None,
    active_product_loop_reconstruction: bool = True,
    requested_next_boundary: str = ALLOWED_NEXT_BOUNDARY,
    external_scope: str = "controlled_customer_handoff",
    ai_review_only: bool = False,
    loop_dominance: bool = False,
    raw_brief_body_requested: bool = False,
    raw_spec_body_requested: bool = False,
    raw_eval_body_requested: bool = False,
    raw_follow_up_data_attached: bool = False,
    raw_customer_data_attached: bool = False,
    raw_backlog_data_attached: bool = False,
    customer_identity_attached: bool = False,
    automatic_backlog_creation_requested: bool = False,
    automatic_priority_assignment_requested: bool = False,
    automatic_execution_requested: bool = False,
    customer_contact_requested: bool = False,
    product_loop_backlog_mutation_requested: bool = False,
    delivery_trust_harness_invocation_requested: bool = False,
    source_mutation_requested: bool = False,
    production_mutation_requested: bool = False,
    external_publication_payload_attached: bool = False,
    model_call_requested: bool = False,
    secret_attached: bool = False,
    model_credential_attached: bool = False,
) -> dict[str, Any]:
    authoring_receipt = (
        authoring_gate.validate_authoring_receipt(source_authoring_receipt_payload)
        if source_authoring_receipt_payload is not None
        else None
    )
    candidate_payload = brief_candidate
    if candidate_payload is None and authoring_receipt is not None:
        maybe_candidate = authoring_receipt.get("brief_candidate")
        candidate_payload = maybe_candidate if isinstance(maybe_candidate, Mapping) else None

    reasons: list[str] = []
    source_authoring_blocked_reasons: list[str] = []
    authoring_allowed = (
        authoring_receipt is not None
        and authoring_receipt.get("status") == "queued_for_product_loop_brief_candidate"
    )
    if authoring_receipt is None:
        reasons.append("source_authoring_receipt_missing")
    elif not authoring_allowed:
        reasons.append("source_authoring_receipt_not_allowed")
        upstream_reasons = authoring_receipt.get("blocked_reasons")
        if isinstance(upstream_reasons, list):
            source_authoring_blocked_reasons = [str(reason) for reason in upstream_reasons]
            reasons.extend(source_authoring_blocked_reasons)

    validated_candidate: dict[str, Any] | None = None
    if candidate_payload is None:
        reasons.append("source_brief_candidate_missing")
    else:
        try:
            validated_candidate = validate_source_brief_candidate(candidate_payload)
        except PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError as exc:
            if "missing required reopen-intake brief ref" in str(exc):
                reasons.append("source_brief_candidate_ref_missing")
            else:
                reasons.append("source_brief_candidate_invalid")
            source_authoring_blocked_reasons.append(str(exc))
    if not active_product_loop_reconstruction:
        reasons.append("product_loop_reconstruction_missing")
    if requested_next_boundary != ALLOWED_NEXT_BOUNDARY:
        reasons.append("requested_next_boundary_not_product_loop_harness_candidate")
    if external_scope not in product_loop_harness.ALLOWED_PROMOTION_SCOPES:
        reasons.append("external_feedback_scope_expansion")
    if ai_review_only:
        reasons.append("ai_review_only_evidence_rejected")
    if loop_dominance:
        reasons.append("loop_dominance_detected")
    for flag, reason in (
        (raw_brief_body_requested, "raw_brief_body_rejected"),
        (raw_spec_body_requested, "raw_spec_body_rejected"),
        (raw_eval_body_requested, "raw_eval_body_rejected"),
        (raw_follow_up_data_attached, "raw_follow_up_data_rejected"),
        (raw_customer_data_attached, "raw_customer_data_rejected"),
        (raw_backlog_data_attached, "raw_backlog_data_rejected"),
        (customer_identity_attached, "customer_identity_rejected"),
        (automatic_backlog_creation_requested, "automatic_backlog_creation_rejected"),
        (automatic_priority_assignment_requested, "automatic_priority_assignment_rejected"),
        (automatic_execution_requested, "automatic_execution_rejected"),
        (customer_contact_requested, "customer_contact_rejected"),
        (product_loop_backlog_mutation_requested, "product_loop_backlog_mutation_rejected"),
        (delivery_trust_harness_invocation_requested, "delivery_trust_harness_invocation_rejected"),
        (source_mutation_requested, "source_mutation_rejected"),
        (production_mutation_requested, "production_mutation_rejected"),
        (external_publication_payload_attached, "external_publication_payload_rejected"),
        (model_call_requested, "model_call_rejected"),
        (secret_attached, "secret_rejected"),
        (model_credential_attached, "model_credential_rejected"),
    ):
        if flag:
            reasons.append(reason)

    product_loop_candidate = None
    if not reasons and validated_candidate is not None:
        product_loop_candidate = build_product_loop_candidate(
            validated_candidate,
            external_scope=external_scope,
            ai_review_only=ai_review_only,
            loop_dominance=loop_dominance,
        )

    source_hash = artifact_hash(validated_candidate) if validated_candidate is not None else None
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "intake_receipt_id": (
            f"patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-{source_hash[:16]}"
            if source_hash
            else f"patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-blocked-{case_id}"
        ),
        "case_id": case_id,
        "source_brief_candidate_id": validated_candidate.get("brief_candidate_id") if validated_candidate else None,
        "source_brief_candidate_hash": source_hash,
        "source_authoring_receipt_id": (
            authoring_receipt.get("authoring_receipt_id") if authoring_receipt else None
        ),
        "source_authoring_receipt_hash": artifact_hash(authoring_receipt) if authoring_receipt else None,
        "status": "created_product_loop_scenario_run_candidate" if product_loop_candidate else "blocked",
        "decision": (
            "create_patch_proposal_reopen_intake_product_loop_scenario_run_candidate"
            if product_loop_candidate
            else "block_patch_proposal_reopen_intake_product_loop_brief_intake_gate"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "authoring_receipt_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate/"
                f"{_authoring_case_for_intake_case(case_id)}/"
                "patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"
                if _authoring_case_for_intake_case(case_id)
                else None
            ),
            "authoring_receipt_id": authoring_receipt.get("authoring_receipt_id") if authoring_receipt else None,
            "authoring_receipt_hash": artifact_hash(authoring_receipt) if authoring_receipt else None,
            "authoring_receipt_status": authoring_receipt.get("status") if authoring_receipt else None,
            "authoring_blocked_reasons": source_authoring_blocked_reasons,
            "brief_candidate_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate/"
                f"{_authoring_case_for_intake_case(case_id)}/"
                "patch-proposal-product-loop-brief-candidate.json"
                if _authoring_case_for_intake_case(case_id)
                else None
            ),
            "brief_candidate_id": validated_candidate.get("brief_candidate_id") if validated_candidate else None,
            "brief_candidate_hash": source_hash,
            "spec_eval_candidate_id": (
                validated_candidate.get("source_spec_eval_candidate_id") if validated_candidate else None
            ),
            "spec_eval_candidate_hash": (
                validated_candidate.get("source_spec_eval_candidate_hash") if validated_candidate else None
            ),
            "backlog_signal_id": validated_candidate.get("source_backlog_signal_id") if validated_candidate else None,
            "backlog_signal_hash": (
                validated_candidate.get("source_backlog_signal_hash") if validated_candidate else None
            ),
            "feedback_intake_id": validated_candidate.get("source_feedback_intake_id") if validated_candidate else None,
            "feedback_intake_hash": (
                validated_candidate.get("source_feedback_intake_hash") if validated_candidate else None
            ),
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
            "brief_candidate_body_included": False,
        },
        "product_loop_reconstruction": {
            "active_reconstruction_present": active_product_loop_reconstruction,
            "passive_attention_only_sufficient": False,
            "developer_ref": "developer-product-loop-role",
            "reconstructed_boundaries": [
                "metadata_only_patch_proposal_brief_candidate",
                "full_reopen_intake_spec_eval_authoring_chain_preserved",
                "three_loop_product_harness_required",
                "ai_review_only_rejected",
                "raw_brief_spec_eval_and_customer_data_rejected",
                "no_delivery_trust_harness_invocation",
                "no_customer_contact",
                "no_product_loop_backlog_mutation",
                "no_source_mutation",
                "no_production_mutation",
            ],
        },
        "requested_transition": {
            "from": "product_loop_brief_candidate_queue",
            "to": requested_next_boundary,
            "external_scope": external_scope,
            "raw_brief_body_requested": raw_brief_body_requested,
            "raw_spec_body_requested": raw_spec_body_requested,
            "raw_eval_body_requested": raw_eval_body_requested,
            "raw_follow_up_data_attached": raw_follow_up_data_attached,
            "raw_customer_data_attached": raw_customer_data_attached,
            "raw_backlog_data_attached": raw_backlog_data_attached,
            "customer_identity_attached": customer_identity_attached,
            "automatic_backlog_creation_requested": automatic_backlog_creation_requested,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "customer_contact_requested": customer_contact_requested,
            "product_loop_backlog_mutation_requested": product_loop_backlog_mutation_requested,
            "delivery_trust_harness_invocation_requested": delivery_trust_harness_invocation_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_payload_attached": external_publication_payload_attached,
            "model_call_requested": model_call_requested,
        },
        "intake_policy": {
            "required_input_schema": authoring_gate.BRIEF_CANDIDATE_SCHEMA_VERSION,
            "allowed_next_boundary": ALLOWED_NEXT_BOUNDARY,
            "delivery_trust_harness_invocation_allowed": False,
            "delivery_trust_harness_skip_allowed": False,
            "ai_review_only_allowed": False,
            "raw_brief_body_allowed": False,
            "raw_spec_body_allowed": False,
            "raw_eval_body_allowed": False,
            "raw_follow_up_data_allowed": False,
            "raw_customer_data_allowed": False,
            "raw_backlog_data_allowed": False,
            "customer_identity_allowed": False,
            "automatic_backlog_creation_allowed": False,
            "automatic_priority_assignment_allowed": False,
            "automatic_execution_allowed": False,
            "customer_contact_allowed": False,
            "product_loop_backlog_mutation_allowed": False,
            "source_mutation_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "model_call_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "checks": {
            "source_authoring_receipt_present": authoring_receipt is not None,
            "source_authoring_receipt_allowed": authoring_allowed,
            "source_brief_candidate_present": validated_candidate is not None,
            "active_product_loop_reconstruction_present": active_product_loop_reconstruction,
            "metadata_only_product_loop_candidate": True,
            "raw_brief_body_requested": raw_brief_body_requested,
            "raw_spec_body_requested": raw_spec_body_requested,
            "raw_eval_body_requested": raw_eval_body_requested,
            "raw_follow_up_data_attached": raw_follow_up_data_attached,
            "raw_customer_data_attached": raw_customer_data_attached,
            "raw_backlog_data_attached": raw_backlog_data_attached,
            "customer_identity_attached": customer_identity_attached,
            "automatic_backlog_creation_requested": automatic_backlog_creation_requested,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "customer_contact_requested": customer_contact_requested,
            "product_loop_backlog_mutation_requested": product_loop_backlog_mutation_requested,
            "delivery_trust_harness_invocation_requested": delivery_trust_harness_invocation_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_payload_attached": external_publication_payload_attached,
            "model_call_requested": model_call_requested,
            "secret_attached": secret_attached,
            "model_credential_attached": model_credential_attached,
        },
        "scenario": product_loop_candidate["product-loop-scenario.json"] if product_loop_candidate else None,
        "run": product_loop_candidate["product-loop-run.json"] if product_loop_candidate else None,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_intake_receipt(receipt)


def validate_intake_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError("receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    _validate_effect_boundary(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    decision = receipt.get("decision")
    reasons = receipt.get("blocked_reasons")
    scenario = receipt.get("scenario")
    run = receipt.get("run")
    if status not in {"created_product_loop_scenario_run_candidate", "blocked"}:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError("receipt status is invalid")
    if not isinstance(reasons, list):
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError("receipt blocked_reasons must be a list")
    if status == "created_product_loop_scenario_run_candidate":
        if decision != "create_patch_proposal_reopen_intake_product_loop_scenario_run_candidate":
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "created receipt must create Patch Proposal reopen-intake Product Loop scenario/run candidate"
            )
        if reasons:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "created receipt must not include blocked reasons"
            )
        if not isinstance(scenario, Mapping) or not isinstance(run, Mapping):
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "created receipt must include scenario and run"
            )
        scenario_payload = product_loop_harness.validate_product_loop_scenario(scenario)
        run_payload = product_loop_harness.validate_product_loop_run(run)
        if scenario_payload["source"]["source_type"] != "patch_proposal_reopen_intake_product_loop_brief_candidate":
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "scenario source must be Patch Proposal reopen-intake Product Loop brief candidate"
            )
        agentic = scenario_payload["loops"]["agentic_coding_loop"]
        if agentic.get("input_ref") != "patch-proposal-product-loop-brief-candidate.json":
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "agentic loop input_ref must be the Patch Proposal brief candidate"
            )
        brief_ref = agentic.get("patch_proposal_brief_candidate_ref")
        if not isinstance(brief_ref, Mapping) or brief_ref.get("body_included") is not False:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "scenario must carry only a metadata-only Patch Proposal brief candidate ref"
            )
        for key in (
            "source_reopen_intake_gate_ref",
            "source_reopen_intake_bridge_ref",
            "closure_receipt_hash",
            "outcome_receipt_hash",
            "action_ref_hash",
            "external_actor_ref_hash",
            "intake_candidate_ref_hash",
            "product_loop_intake_item_ref_hash",
        ):
            if not isinstance(brief_ref.get(key), str) or not brief_ref.get(key):
                raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                    f"scenario brief ref missing {key}"
                )
        if run_payload["status"] != "allowed":
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "created Product Loop run candidate must be allowed by Product Loop Harness"
            )
        if run_payload["promotion"]["allowed_next_layer"] != "delivery_trust_harness":
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "Product Loop run candidate may only stop before Delivery Trust Harness"
            )
    else:
        if decision != "block_patch_proposal_reopen_intake_product_loop_brief_intake_gate":
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "blocked receipt must block Patch Proposal Product Loop brief intake"
            )
        if not reasons:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "blocked receipt must include reasons"
            )
        if scenario is not None or run is not None:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "blocked receipt must not include scenario or run"
            )

    reconstruction = _require_object(receipt, "product_loop_reconstruction", label=RECEIPT_SCHEMA_VERSION)
    if reconstruction.get("passive_attention_only_sufficient") is not False:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "passive Product Loop attention alone is insufficient"
        )
    if status == "created_product_loop_scenario_run_candidate" and reconstruction.get("active_reconstruction_present") is not True:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "created receipt requires active Product Loop reconstruction"
        )
    policy = _require_object(receipt, "intake_policy", label=RECEIPT_SCHEMA_VERSION)
    if policy.get("allowed_next_boundary") != ALLOWED_NEXT_BOUNDARY:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "policy must stop at Product Loop Harness candidate"
        )
    for key in (
        "delivery_trust_harness_invocation_allowed",
        "delivery_trust_harness_skip_allowed",
        "ai_review_only_allowed",
        "raw_brief_body_allowed",
        "raw_spec_body_allowed",
        "raw_eval_body_allowed",
        "raw_follow_up_data_allowed",
        "raw_customer_data_allowed",
        "raw_backlog_data_allowed",
        "customer_identity_allowed",
        "automatic_backlog_creation_allowed",
        "automatic_priority_assignment_allowed",
        "automatic_execution_allowed",
        "customer_contact_allowed",
        "product_loop_backlog_mutation_allowed",
        "source_mutation_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
        "model_call_allowed",
    ):
        if policy.get(key) is not False:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(f"policy.{key} must be False")
    transition = _require_object(receipt, "requested_transition", label=RECEIPT_SCHEMA_VERSION)
    if status == "created_product_loop_scenario_run_candidate":
        if transition.get("to") != ALLOWED_NEXT_BOUNDARY:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
            "created receipt must target Product Loop Harness candidate"
            )
        for key in (
            "raw_brief_body_requested",
            "raw_spec_body_requested",
            "raw_eval_body_requested",
            "raw_follow_up_data_attached",
            "raw_customer_data_attached",
            "raw_backlog_data_attached",
            "customer_identity_attached",
            "automatic_backlog_creation_requested",
            "automatic_priority_assignment_requested",
            "automatic_execution_requested",
            "customer_contact_requested",
            "product_loop_backlog_mutation_requested",
            "delivery_trust_harness_invocation_requested",
            "source_mutation_requested",
            "production_mutation_requested",
            "external_publication_payload_attached",
            "model_call_requested",
        ):
            if transition.get(key) is not False:
                raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                    f"created receipt must not request {key}"
                )
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    if status == "created_product_loop_scenario_run_candidate":
        if checks.get("source_authoring_receipt_allowed") is not True:
            raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                "created receipt requires an allowed source authoring receipt"
            )
        for key in (
            "raw_brief_body_requested",
            "raw_spec_body_requested",
            "raw_eval_body_requested",
            "raw_follow_up_data_attached",
            "raw_customer_data_attached",
            "raw_backlog_data_attached",
            "customer_identity_attached",
            "automatic_backlog_creation_requested",
            "automatic_priority_assignment_requested",
            "automatic_execution_requested",
            "customer_contact_requested",
            "product_loop_backlog_mutation_requested",
            "delivery_trust_harness_invocation_requested",
            "source_mutation_requested",
            "production_mutation_requested",
            "external_publication_payload_attached",
            "model_call_requested",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(
                    f"created receipt checks.{key} must be False"
                )
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerFeedbackProductLoopBriefIntakeGateError(f"Unknown case id: {case_id}")
    receipt_payload = source_authoring_receipt(case_id)
    candidate = source_brief_candidate(case_id)
    if case_id == "blocked-missing-authoring-receipt":
        candidate = None
        receipt_payload = None
    if case_id == "blocked-missing-brief-candidate-ref" and candidate is not None:
        candidate = dict(candidate)
        candidate.pop("brief_candidate_id", None)
    receipt = build_intake_receipt(
        case_id,
        brief_candidate=candidate,
        source_authoring_receipt_payload=receipt_payload,
        active_product_loop_reconstruction=case_id != "blocked-missing-product-loop-reconstruction",
        requested_next_boundary=(
            FORBIDDEN_NEXT_BOUNDARY if case_id == "blocked-skip-to-delivery-trust" else ALLOWED_NEXT_BOUNDARY
        ),
        ai_review_only=case_id == "blocked-ai-review-only",
        raw_brief_body_requested=case_id == "blocked-raw-brief-body",
        raw_spec_body_requested=case_id == "blocked-raw-spec-body",
        raw_eval_body_requested=case_id == "blocked-raw-eval-body",
        raw_follow_up_data_attached=case_id == "blocked-raw-follow-up-data",
        raw_customer_data_attached=case_id == "blocked-raw-customer-data",
        raw_backlog_data_attached=case_id == "blocked-raw-backlog-data",
        customer_identity_attached=case_id == "blocked-customer-identity",
        automatic_backlog_creation_requested=case_id == "blocked-automatic-backlog-creation",
        automatic_priority_assignment_requested=case_id == "blocked-automatic-priority-assignment",
        automatic_execution_requested=case_id == "blocked-automatic-execution",
        customer_contact_requested=case_id == "blocked-customer-contact",
        product_loop_backlog_mutation_requested=case_id == "blocked-product-loop-backlog-mutation",
        delivery_trust_harness_invocation_requested=case_id == "blocked-delivery-trust-invocation",
        source_mutation_requested=case_id == "blocked-source-mutation",
        production_mutation_requested=case_id == "blocked-production-mutation",
        external_publication_payload_attached=case_id == "blocked-external-publication-payload",
        model_call_requested=case_id == "blocked-model-call",
        secret_attached=case_id == "blocked-secret",
        model_credential_attached=case_id == "blocked-model-credential",
    )
    artifacts = {"patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json": receipt}
    if isinstance(receipt.get("scenario"), Mapping):
        artifacts["product-loop-scenario.json"] = dict(receipt["scenario"])
    if isinstance(receipt.get("run"), Mapping):
        artifacts["product-loop-run.json"] = dict(receipt["run"])
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_intake_receipt(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "scenario_created": receipt["scenario"] is not None,
                "run_created": receipt["run"] is not None,
            }
        )
    created_count = sum(1 for row in case_reports if row["status"] == "created_product_loop_scenario_run_candidate")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove Patch Proposal controlled follow-up feedback reopen-intake Product Loop brief candidates can create "
            "metadata-only Product Loop scenario/run candidates only after active developer/product-loop "
            "reconstruction, without AI-review-only promotion, Delivery Trust Harness invocation, automatic "
            "execution, customer follow-up, external publication, source mutation, production mutation, "
            "model calls, secrets, or model credentials."
        ),
        "source_chain": {
            "input_schema": authoring_gate.BRIEF_CANDIDATE_SCHEMA_VERSION,
            "input_gate": authoring_gate.REPORT_SCHEMA_VERSION,
            "output_schemas": [
                product_loop_harness.PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION,
                product_loop_harness.PRODUCT_LOOP_RUN_SCHEMA_VERSION,
            ],
            "allowed_next_boundary": ALLOWED_NEXT_BOUNDARY,
        },
        "case_reports": case_reports,
        "intake_matrix": {
            "created_product_loop_candidates": created_count,
            "blocked_intake_transitions": blocked_count,
            "delivery_trust_invocations": 0,
            "customer_visible_follow_ups": 0,
            "source_mutations": 0,
            "production_mutations": 0,
            "external_publications": 0,
            "model_calls": 0,
        },
        "gate_rules": {
            "source_brief_candidate_required": True,
            "active_product_loop_reconstruction_required": True,
            "ai_review_only_blocks": True,
            "delivery_trust_harness_invocation_blocked": True,
            "delivery_trust_harness_skip_blocked": True,
            "automatic_execution_blocked": True,
            "customer_visible_follow_up_blocked": True,
            "external_publication_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "model_calls_blocked": True,
            "metadata_only": True,
        },
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    _validate_privacy(report, label=REPORT_SCHEMA_VERSION)
    _validate_effect_boundary(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_artifacts(output_dir: Path, cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            write_json(output_dir / case_id / filename, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--brief-candidate", type=Path, help="Build from a Patch Proposal brief candidate JSON file.")
    parser.add_argument("--authoring-receipt", type=Path, help="Optional source authoring receipt JSON file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.brief_candidate:
        authoring_receipt = load_json(args.authoring_receipt) if args.authoring_receipt else None
        selected = {
            "custom": {
                "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json": build_intake_receipt(
                    "custom",
                    brief_candidate=load_json(args.brief_candidate),
                    source_authoring_receipt_payload=authoring_receipt,
                )
            }
        }
    else:
        cases = build_all_case_artifacts()
        selected = cases if args.case == "all" else {args.case: cases[args.case]}
    write_artifacts(args.output_dir, selected)
    print(
        dump_json(
            {
                "schema_version": "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "created_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts[
                        "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"
                    ]["status"]
                    == "created_product_loop_scenario_run_candidate"
                ),
                "blocked_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts[
                        "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"
                    ]["status"]
                    == "blocked"
                ),
                "model_calls_performed": False,
                "delivery_trust_harness_invoked": False,
                "customer_visible_follow_up_performed": False,
                "source_mutation_performed": False,
                "production_mutation_performed": False,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
