#!/usr/bin/env python3
"""Gate controlled follow-up feedback Product Loop runs into Delivery Trust case candidates.

This layer consumes Product Loop scenario/run candidates emitted by the Patch
Proposal controlled follow-up feedback Product Loop Brief Intake Gate. It
requires controlled-failure and attention-reconstruction evidence, then emits
only a metadata-only Delivery Trust case candidate.

It does not invoke the Delivery Trust Case Harness, create a customer handoff
package, send customer-visible follow-up, mutate source, mutate production,
call models, or store raw payloads.
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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_product_loop_brief_intake_gate as brief_intake_gate  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt-v1"
CANDIDATE_SCHEMA_VERSION = "patch-proposal-delivery-trust-case-candidate-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate"

PASS_CASE_IDS = (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
)
CASE_IDS = (
    *PASS_CASE_IDS,
    "blocked-missing-product-loop-run",
    "blocked-invalid-product-loop-run",
    "blocked-missing-sandbox-receipt",
    "blocked-missing-attention-reconstruction",
    "blocked-dual-loop-gate-blocked",
    "blocked-ai-review-only",
    "blocked-direct-delivery-trust-harness",
    "blocked-customer-handoff-package",
    "blocked-automatic-execution",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_NEXT_BOUNDARY = "delivery_trust_case_harness"

PRIVACY_FLAGS = {
    **brief_intake_gate.PRIVACY_FLAGS,
    "delivery_trust_case_candidate_metadata_only": True,
    "customer_handoff_package_included": False,
    "raw_delivery_case_included": False,
    "raw_customer_payload_included": False,
    "raw_sandbox_log_included": False,
    "raw_attention_trace_included": False,
}

EFFECT_BOUNDARY = {
    **brief_intake_gate.EFFECT_BOUNDARY,
    "study_anything_delivery_trust_case_candidate_queue_mutated": False,
    "study_anything_delivery_trust_case_harness_invoked": False,
    "study_anything_customer_handoff_package_created": False,
    "study_anything_customer_visible_follow_up_performed": False,
    "study_anything_automatic_execution_performed": False,
    "study_anything_source_mutation_performed": False,
    "study_anything_production_mutation_performed": False,
    "study_anything_external_publication_performed": False,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
}

FORBIDDEN_RAW_FIELDS = {
    *brief_intake_gate.FORBIDDEN_RAW_FIELDS,
    "raw_delivery_case",
    "delivery_case_body",
    "customer_handoff_package",
    "raw_customer_payload",
    "raw_sandbox_log",
    "sandbox_log_body",
    "raw_attention_trace",
    "attention_trace_body",
    "customer_visible_follow_up",
    "customer_visible_reply",
    "follow_up_body",
    "external_publication_payload",
    "source_mutation_payload",
    "production_payload",
}

BLOCKED_DESTINATIONS = [
    "delivery_trust_case_harness_invocation",
    "customer_handoff_package_creation",
    "automatic_execution",
    "customer_visible_follow_up",
    "source_mutation",
    "external_publication",
    "production_mutation",
    "model_call",
]

CLAIM_BOUNDARY = {
    "current_claim": (
        "A Patch Proposal Product Loop run can become a metadata-only Delivery "
        "Trust case candidate only when the controlled follow-up feedback Product "
        "Loop, controlled-failure, attention-reconstruction, and Dual Loop gate "
        "evidence are all present. The candidate stops before Delivery Trust Case "
        "Harness invocation, customer handoff package creation, external publication, "
        "or model calls."
    ),
    "not_claimed": [
        "Delivery Trust Case Harness completed",
        "customer handoff package created",
        "customer-visible follow-up allowed",
        "source mutation allowed",
        "production mutation allowed",
        "automatic execution",
        "external publication allowed",
        "model call performed",
    ],
}


class PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(ValueError):
    """Raised when Patch Proposal Delivery Trust intake is unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(f"Expected JSON object: {path}")
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
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _validate_effect_boundary(payload: Mapping[str, Any], *, label: str) -> None:
    effect = _require_object(payload, "effect_boundary", label=label)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
                f"{label}.effect_boundary.{key} must be {expected!r}"
            )


def source_product_loop_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    source_case = case_id if case_id in PASS_CASE_IDS else "pass-customer-signal"
    return brief_intake_gate.build_case_artifacts(source_case)


def source_product_loop_run(case_id: str) -> dict[str, Any] | None:
    artifacts = source_product_loop_artifacts(case_id)
    run = artifacts.get("product-loop-run.json")
    return product_loop_harness.validate_product_loop_run(run) if isinstance(run, Mapping) else None


def source_product_loop_scenario(case_id: str) -> dict[str, Any] | None:
    artifacts = source_product_loop_artifacts(case_id)
    scenario = artifacts.get("product-loop-scenario.json")
    return product_loop_harness.validate_product_loop_scenario(scenario) if isinstance(scenario, Mapping) else None


def default_dual_loop_artifacts(*, within_budget: bool = True, attention_present: bool = True) -> dict[str, Any]:
    contract = dual_loop.failure_contract_demo()
    sandbox = dual_loop.sandbox_receipt_demo(within_budget=within_budget)
    attention_summary = dual_loop.attention_summary_demo() if attention_present else None
    gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention_summary)
    artifacts = {
        "failure_contract": contract,
        "sandbox_receipt": sandbox,
        "attention_summary": attention_summary,
        "dual_loop_gate": gate,
    }
    return artifacts


def validate_product_loop_run_source(run: Mapping[str, Any]) -> dict[str, Any]:
    validated = product_loop_harness.validate_product_loop_run(run)
    if validated.get("status") != "allowed":
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("Product Loop run must be allowed")
    if validated.get("promotion", {}).get("allowed_next_layer") != "delivery_trust_harness":
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "Product Loop run must stop at Delivery Trust Harness"
        )
    if validated.get("promotion", {}).get("production_mutation_allowed") is not False:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "Product Loop run must block production mutation"
        )
    checks = validated.get("checks", {})
    if checks.get("ai_review_only_rejected") is not True:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "Product Loop run must reject AI-review-only evidence"
        )
    if checks.get("model_calls_performed") is not False:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "Product Loop run must not require model calls"
        )
    if validated.get("source", {}).get("source_type") != "patch_proposal_product_loop_brief_candidate":
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "Product Loop run source must be Patch Proposal brief candidate"
        )
    if validated.get("evidence_refs", {}).get("product_spec_evals_ref") != "patch-proposal-product-loop-brief-candidate.json":
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "Product Loop run must reference the Patch Proposal brief candidate"
        )
    return validated


def _validate_dual_loop_inputs(
    failure_contract: Mapping[str, Any] | None,
    sandbox_receipt: Mapping[str, Any] | None,
    attention_summary: Mapping[str, Any] | None,
    dual_loop_gate: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    contract = None
    sandbox = None
    attention = None
    gate = None
    try:
        contract = dual_loop.validate_failure_contract(failure_contract) if failure_contract is not None else None
    except Exception:
        reasons.append("failure_contract_invalid")
    if contract is None and "failure_contract_invalid" not in reasons:
        reasons.append("failure_contract_missing")
    try:
        sandbox = dual_loop.validate_sandbox_receipt(sandbox_receipt) if sandbox_receipt is not None else None
    except Exception:
        reasons.append("sandbox_receipt_invalid")
    if sandbox is None and "sandbox_receipt_invalid" not in reasons:
        reasons.append("sandbox_receipt_missing")
    try:
        attention = dual_loop.validate_attention_summary(attention_summary) if attention_summary is not None else None
    except Exception:
        reasons.append("attention_reconstruction_invalid")
    if attention is None and "attention_reconstruction_invalid" not in reasons:
        reasons.append("attention_reconstruction_missing")
    if contract is not None and sandbox is not None and attention is not None:
        gate = dual_loop.validate_gate_receipt(dual_loop_gate) if dual_loop_gate is not None else None
        if gate is None:
            gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention)
        if gate.get("status") != "allowed":
            reasons.append("dual_loop_gate_blocked")
            reasons.extend(str(reason) for reason in gate.get("reasons", []))
    return contract, sandbox, attention, gate, list(dict.fromkeys(reasons))


def build_candidate(
    product_loop_run: Mapping[str, Any],
    failure_contract: Mapping[str, Any],
    sandbox_receipt: Mapping[str, Any],
    attention_summary: Mapping[str, Any],
    dual_loop_gate: Mapping[str, Any],
) -> dict[str, Any]:
    run = validate_product_loop_run_source(product_loop_run)
    contract = dual_loop.validate_failure_contract(failure_contract)
    sandbox = dual_loop.validate_sandbox_receipt(sandbox_receipt)
    attention = dual_loop.validate_attention_summary(attention_summary)
    gate = dual_loop.validate_gate_receipt(dual_loop_gate)
    run_hash = artifact_hash(run)
    gate_hash = artifact_hash(gate)
    candidate = {
        **_base(CANDIDATE_SCHEMA_VERSION),
        "candidate_id": f"patch-proposal-controlled-follow-up-feedback-delivery-trust-case-candidate-{run_hash[:16]}",
        "source_delivery_class": "patch-proposal",
        "destination": "delivery_trust_case_candidate_queue",
        "next_boundary": ALLOWED_NEXT_BOUNDARY,
        "source_product_loop_run_id": run["run_id"],
        "source_product_loop_run_hash": run_hash,
        "source_product_loop_scenario_id": run["scenario_id"],
        "source_chain": {
            "source_type": "controlled_follow_up_feedback_product_loop_run",
            "source_product_loop_run_ref": "product-loop-run.json",
            "source_product_loop_scenario_ref": "product-loop-scenario.json",
            "source_product_loop_brief_intake_receipt_ref": (
                "patch-proposal-controlled-follow-up-feedback-product-loop-brief-intake-receipt.json"
            ),
            "raw_product_loop_run_included": False,
            "raw_product_loop_scenario_included": False,
        },
        "controlled_failure_ref": {
            "failure_contract_id": contract["contract_id"],
            "failure_contract_hash": artifact_hash(contract),
            "sandbox_receipt_id": sandbox["receipt_id"],
            "sandbox_receipt_hash": artifact_hash(sandbox),
            "raw_sandbox_log_included": False,
        },
        "attention_reconstruction_ref": {
            "attention_summary_id": attention["summary_id"],
            "attention_summary_hash": artifact_hash(attention),
            "raw_attention_trace_included": False,
            "passive_attention_only_sufficient": False,
        },
        "dual_loop_gate_ref": {
            "dual_loop_gate_id": gate["gate_id"],
            "dual_loop_gate_hash": gate_hash,
            "status": gate["status"],
            "decision": gate["decision"],
        },
        "ready_for_delivery_trust_case_harness": True,
        "ready_for_customer_handoff": False,
        "ready_for_production": False,
        "customer_handoff_package_included": False,
        "blocked_destinations": list(BLOCKED_DESTINATIONS),
        "quality_gates": {
            "product_loop_run_required": True,
            "controlled_failure_required": True,
            "attention_reconstruction_required": True,
            "dual_loop_gate_required": True,
            "ai_review_only_rejected": True,
            "customer_handoff_package_deferred": True,
            "delivery_trust_case_harness_invocation_blocked": True,
            "automatic_execution_blocked": True,
            "external_publication_blocked": True,
            "model_calls_blocked": True,
        },
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_candidate(candidate)


def validate_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("candidate schema_version drifted")
    _validate_privacy(candidate, label=CANDIDATE_SCHEMA_VERSION)
    _validate_effect_boundary(candidate, label=CANDIDATE_SCHEMA_VERSION)
    if candidate.get("destination") != "delivery_trust_case_candidate_queue":
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("candidate destination drifted")
    if candidate.get("next_boundary") != ALLOWED_NEXT_BOUNDARY:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("candidate next boundary drifted")
    if candidate.get("ready_for_delivery_trust_case_harness") is not True:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "candidate must be ready only for Delivery Trust Case Harness"
        )
    for key in ("ready_for_customer_handoff", "ready_for_production", "customer_handoff_package_included"):
        if candidate.get(key) is not False:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(f"candidate {key} must be false")
    attention = _require_object(candidate, "attention_reconstruction_ref", label=CANDIDATE_SCHEMA_VERSION)
    if attention.get("passive_attention_only_sufficient") is not False:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
            "candidate must reject passive attention as sufficient"
        )
    gate = _require_object(candidate, "dual_loop_gate_ref", label=CANDIDATE_SCHEMA_VERSION)
    if gate.get("status") != "allowed":
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("candidate requires allowed Dual Loop gate")
    return dict(candidate)


def build_intake_receipt(
    case_id: str,
    *,
    product_loop_run: Mapping[str, Any] | None = None,
    failure_contract: Mapping[str, Any] | None = None,
    sandbox_receipt: Mapping[str, Any] | None = None,
    attention_summary: Mapping[str, Any] | None = None,
    dual_loop_gate: Mapping[str, Any] | None = None,
    requested_next_boundary: str = ALLOWED_NEXT_BOUNDARY,
    delivery_trust_harness_invocation_requested: bool = False,
    customer_handoff_package_requested: bool = False,
    automatic_execution_requested: bool = False,
    customer_visible_follow_up_requested: bool = False,
    source_mutation_requested: bool = False,
    production_mutation_requested: bool = False,
    external_publication_requested: bool = False,
    model_call_requested: bool = False,
    secret_attached: bool = False,
    model_credential_attached: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    run = None
    if product_loop_run is None:
        reasons.append("product_loop_run_missing")
    else:
        try:
            run = validate_product_loop_run_source(product_loop_run)
        except Exception:
            reasons.append("product_loop_run_invalid")

    contract, sandbox, attention, gate, dual_reasons = _validate_dual_loop_inputs(
        failure_contract,
        sandbox_receipt,
        attention_summary,
        dual_loop_gate,
    )
    reasons.extend(dual_reasons)
    if requested_next_boundary != ALLOWED_NEXT_BOUNDARY:
        reasons.append("requested_next_boundary_not_delivery_trust_case_harness")
    for flag, reason in (
        (delivery_trust_harness_invocation_requested, "delivery_trust_harness_invocation_rejected"),
        (customer_handoff_package_requested, "customer_handoff_package_rejected"),
        (automatic_execution_requested, "automatic_execution_rejected"),
        (customer_visible_follow_up_requested, "customer_visible_follow_up_rejected"),
        (source_mutation_requested, "source_mutation_rejected"),
        (production_mutation_requested, "production_mutation_rejected"),
        (external_publication_requested, "external_publication_rejected"),
        (model_call_requested, "model_call_rejected"),
        (secret_attached, "secret_rejected"),
        (model_credential_attached, "model_credential_rejected"),
    ):
        if flag:
            reasons.append(reason)
    reasons = list(dict.fromkeys(reasons))

    candidate = None
    if not reasons and run is not None and contract is not None and sandbox is not None and attention is not None and gate is not None:
        candidate = build_candidate(run, contract, sandbox, attention, gate)

    run_hash = artifact_hash(run) if run is not None else None
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "intake_receipt_id": (
            f"patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-{run_hash[:16]}"
            if run_hash
            else f"patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-blocked-{case_id}"
        ),
        "case_id": case_id,
        "source_product_loop_run_id": run.get("run_id") if run else None,
        "source_product_loop_run_hash": run_hash,
        "status": "queued_for_delivery_trust_case_candidate" if candidate else "blocked",
        "decision": (
            "create_patch_proposal_controlled_follow_up_feedback_delivery_trust_case_candidate"
            if candidate
            else "block_patch_proposal_controlled_follow_up_feedback_delivery_trust_intake_gate"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "product_loop_run_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate/"
                f"{case_id if case_id in PASS_CASE_IDS else 'pass-customer-signal'}/product-loop-run.json"
            ),
            "product_loop_scenario_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate/"
                f"{case_id if case_id in PASS_CASE_IDS else 'pass-customer-signal'}/product-loop-scenario.json"
            ),
            "product_loop_brief_intake_receipt_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate/"
                f"{case_id if case_id in PASS_CASE_IDS else 'pass-customer-signal'}/"
                "patch-proposal-controlled-follow-up-feedback-product-loop-brief-intake-receipt.json"
            ),
            "product_loop_run_body_included": False,
            "product_loop_scenario_body_included": False,
        },
        "requested_transition": {
            "from": "product_loop_run_candidate",
            "to": requested_next_boundary,
            "delivery_trust_harness_invocation_requested": delivery_trust_harness_invocation_requested,
            "customer_handoff_package_requested": customer_handoff_package_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "customer_visible_follow_up_requested": customer_visible_follow_up_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_requested": external_publication_requested,
            "model_call_requested": model_call_requested,
        },
        "intake_policy": {
            "allowed_next_boundary": ALLOWED_NEXT_BOUNDARY,
            "product_loop_run_required": True,
            "controlled_failure_required": True,
            "attention_reconstruction_required": True,
            "dual_loop_gate_required": True,
            "delivery_trust_case_harness_invocation_allowed": False,
            "customer_handoff_package_creation_allowed": False,
            "automatic_execution_allowed": False,
            "customer_visible_follow_up_allowed": False,
            "source_mutation_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "model_call_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "candidate": candidate,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_intake_receipt(receipt)


def validate_intake_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    _validate_effect_boundary(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    decision = receipt.get("decision")
    reasons = receipt.get("blocked_reasons")
    candidate = receipt.get("candidate")
    if status not in {"queued_for_delivery_trust_case_candidate", "blocked"}:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("receipt status is invalid")
    if not isinstance(reasons, list):
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("receipt blocked_reasons must be a list")
    if status == "queued_for_delivery_trust_case_candidate":
        if decision != "create_patch_proposal_controlled_follow_up_feedback_delivery_trust_case_candidate":
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("queued receipt decision drifted")
        if reasons:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("queued receipt must not include reasons")
        if not isinstance(candidate, Mapping):
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("queued receipt must include candidate")
        validate_candidate(candidate)
    else:
        if decision != "block_patch_proposal_controlled_follow_up_feedback_delivery_trust_intake_gate":
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("blocked receipt decision drifted")
        if not reasons:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("blocked receipt must include reasons")
        if candidate is not None:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("blocked receipt must not include candidate")
    policy = _require_object(receipt, "intake_policy", label=RECEIPT_SCHEMA_VERSION)
    if policy.get("allowed_next_boundary") != ALLOWED_NEXT_BOUNDARY:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("policy next boundary drifted")
    for key in (
        "delivery_trust_case_harness_invocation_allowed",
        "customer_handoff_package_creation_allowed",
        "automatic_execution_allowed",
        "customer_visible_follow_up_allowed",
        "source_mutation_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
        "model_call_allowed",
    ):
        if policy.get(key) is not False:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(f"policy.{key} must be False")
    transition = _require_object(receipt, "requested_transition", label=RECEIPT_SCHEMA_VERSION)
    if status == "queued_for_delivery_trust_case_candidate":
        if transition.get("to") != ALLOWED_NEXT_BOUNDARY:
            raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError("queued receipt transition drifted")
        for key in (
            "delivery_trust_harness_invocation_requested",
            "customer_handoff_package_requested",
            "automatic_execution_requested",
            "customer_visible_follow_up_requested",
            "source_mutation_requested",
            "production_mutation_requested",
            "external_publication_requested",
            "model_call_requested",
        ):
            if transition.get(key) is not False:
                raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(
                    f"queued receipt must not request {key}"
                )
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerFeedbackDeliveryTrustIntakeGateError(f"Unknown case id: {case_id}")
    run = source_product_loop_run(case_id)
    dual = default_dual_loop_artifacts(
        within_budget=case_id != "blocked-dual-loop-gate-blocked",
        attention_present=case_id != "blocked-missing-attention-reconstruction",
    )
    if case_id == "blocked-missing-product-loop-run":
        run = None
    if case_id == "blocked-invalid-product-loop-run" and run is not None:
        run = dict(run)
        run["promotion"] = dict(run["promotion"])
        run["promotion"]["allowed_next_layer"] = "production"
    if case_id == "blocked-ai-review-only" and run is not None:
        run = dict(run)
        run["checks"] = dict(run["checks"])
        run["checks"]["ai_review_only_rejected"] = False
    receipt = build_intake_receipt(
        case_id,
        product_loop_run=run,
        failure_contract=dual["failure_contract"],
        sandbox_receipt=None if case_id == "blocked-missing-sandbox-receipt" else dual["sandbox_receipt"],
        attention_summary=dual["attention_summary"],
        dual_loop_gate=dual["dual_loop_gate"],
        delivery_trust_harness_invocation_requested=case_id == "blocked-direct-delivery-trust-harness",
        customer_handoff_package_requested=case_id == "blocked-customer-handoff-package",
        automatic_execution_requested=case_id == "blocked-automatic-execution",
        customer_visible_follow_up_requested=case_id == "blocked-customer-visible-follow-up",
        source_mutation_requested=case_id == "blocked-source-mutation",
        production_mutation_requested=case_id == "blocked-production-mutation",
        external_publication_requested=case_id == "blocked-external-publication",
        model_call_requested=case_id == "blocked-model-call",
        secret_attached=case_id == "blocked-secret",
        model_credential_attached=case_id == "blocked-model-credential",
    )
    artifacts = {"patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt.json": receipt}
    candidate = receipt.get("candidate")
    if isinstance(candidate, Mapping):
        artifacts["patch-proposal-delivery-trust-case-candidate.json"] = dict(candidate)
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_intake_receipt(cases[case_id]["patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "candidate_created": receipt["candidate"] is not None,
            }
        )
    queued_count = sum(1 for row in case_reports if row["status"] == "queued_for_delivery_trust_case_candidate")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove Patch Proposal Product Loop runs can create metadata-only Delivery Trust "
            "case candidates only when Product Loop, controlled-failure, attention-reconstruction, "
            "and Dual Loop gate evidence are present, without invoking Delivery Trust Case Harness "
            "or customer handoff."
        ),
        "case_reports": case_reports,
        "intake_matrix": {
            "queued_delivery_trust_case_candidates": queued_count,
            "blocked_intake_transitions": blocked_count,
            "delivery_trust_case_harness_invocations": 0,
            "customer_handoff_packages_created": 0,
            "automatic_executions": 0,
            "customer_visible_follow_ups": 0,
            "external_publications": 0,
            "source_mutations": 0,
            "production_mutations": 0,
            "model_calls": 0,
        },
        "gate_rules": {
            "product_loop_run_required": True,
            "controlled_failure_required": True,
            "attention_reconstruction_required": True,
            "dual_loop_gate_required": True,
            "customer_handoff_package_creation_blocked": True,
            "delivery_trust_case_harness_invocation_blocked": True,
            "automatic_execution_blocked": True,
            "external_publication_blocked": True,
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
    parser.add_argument("--product-loop-run", type=Path, help="Build from a Product Loop run JSON file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.product_loop_run:
        dual = default_dual_loop_artifacts()
        selected = {
            "custom": {
                "patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt.json": build_intake_receipt(
                    "custom",
                    product_loop_run=load_json(args.product_loop_run),
                    failure_contract=dual["failure_contract"],
                    sandbox_receipt=dual["sandbox_receipt"],
                    attention_summary=dual["attention_summary"],
                    dual_loop_gate=dual["dual_loop_gate"],
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
                "schema_version": "patch-proposal-customer-feedback-delivery-trust-intake-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "queued_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts["patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt.json"]["status"]
                    == "queued_for_delivery_trust_case_candidate"
                ),
                "blocked_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts["patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt.json"]["status"] == "blocked"
                ),
                "model_calls_performed": False,
                "delivery_trust_case_harness_invoked": False,
                "customer_handoff_package_created": False,
                "automatic_execution_performed": False,
                "customer_visible_follow_up_performed": False,
                "external_publication_performed": False,
                "source_mutation_performed": False,
                "production_mutation_performed": False,
                "model_calls_performed": False,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
