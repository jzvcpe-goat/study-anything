#!/usr/bin/env python3
"""Gate Patch Proposal customer-feedback backlog signals before spec/eval work.

This layer is metadata-only. It consumes `product-loop-backlog-signal-v1`
artifacts emitted by the Patch Proposal Customer Feedback Backlog Bridge and
can only create a spec/eval candidate after active Product Owner boundary
reconstruction. It never assigns priority, executes work, mutates source,
replies to customers, publishes externally, mutates production, calls models,
or stores raw customer material.
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
import patch_proposal_customer_feedback_backlog_bridge as backlog_bridge  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-customer-feedback-product-owner-receipt-v1"
CANDIDATE_SCHEMA_VERSION = "patch-proposal-product-spec-eval-candidate-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-product-owner-gate-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-feedback-product-owner-gate"

PASS_CASE_IDS = (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
)
CASE_IDS = (
    *PASS_CASE_IDS,
    "blocked-missing-owner-reconstruction",
    "blocked-automatic-priority-assignment",
    "blocked-skip-to-delivery-harness",
    "blocked-automatic-execution",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-blocked-backlog-source",
    "blocked-secret",
    "blocked-model-credential",
)

PRIVACY_FLAGS = {
    **backlog_bridge.PRIVACY_FLAGS,
    "product_owner_identity_included": False,
    "priority_score_included": False,
    "raw_product_spec_included": False,
    "raw_eval_body_included": False,
    "customer_visible_follow_up_included": False,
    "spec_eval_candidate_metadata_only": True,
}

EFFECT_BOUNDARY = {
    **backlog_bridge.EFFECT_BOUNDARY,
    "study_anything_spec_eval_storage_mutated": False,
    "study_anything_spec_eval_candidate_queue_mutated": False,
    "study_anything_automatic_execution_performed": False,
    "study_anything_customer_visible_follow_up_performed": False,
}

FORBIDDEN_RAW_FIELDS = {
    *backlog_bridge.FORBIDDEN_RAW_FIELDS,
    "product_owner_identity",
    "owner_identity",
    "assigned_priority",
    "automatic_priority",
    "priority_score",
    "priority_rank",
    "priority_value",
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
        "A Patch Proposal customer-feedback backlog signal can enter the spec/eval "
        "candidate queue only after active Product Owner boundary reconstruction. "
        "The candidate remains unprioritized, non-executable, metadata-only, and "
        "outside customer-visible or production effects."
    ),
    "not_claimed": [
        "automatic priority assignment",
        "automatic execution",
        "customer-visible follow-up",
        "source mutation",
        "external publication",
        "production mutation",
        "model call performed",
        "customer satisfaction guarantee",
    ],
}


class PatchProposalCustomerFeedbackProductOwnerGateError(ValueError):
    """Raised when the Patch Proposal Product Owner gate is unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerFeedbackProductOwnerGateError(f"Expected JSON object: {path}")
    return payload


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dump_json(payload))


def _base(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(backlog_bridge.ISOLATION),
        "privacy": dict(PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise PatchProposalCustomerFeedbackProductOwnerGateError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerFeedbackProductOwnerGateError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerFeedbackProductOwnerGateError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in backlog_bridge.ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerFeedbackProductOwnerGateError(f"{label}.isolation.{key} must be {expected!r}")


def _validate_effect_boundary(payload: Mapping[str, Any], *, label: str) -> None:
    effect = _require_object(payload, "effect_boundary", label=label)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalCustomerFeedbackProductOwnerGateError(f"{label}.effect_boundary.{key} must be {expected!r}")


def _bridge_case_for_product_owner_case(case_id: str) -> str:
    if case_id == "pass-operator-signal":
        return "pass-operator-signal"
    if case_id == "pass-host-platform-agent-signal":
        return "pass-host-platform-agent-signal"
    if case_id == "blocked-blocked-backlog-source":
        return "blocked-raw-customer-reply"
    return "pass-customer-signal"


def source_bridge(case_id: str) -> dict[str, Any]:
    bridge_case = _bridge_case_for_product_owner_case(case_id)
    bridge = backlog_bridge.build_customer_feedback_backlog_bridge(bridge_case)
    return backlog_bridge.validate_customer_feedback_backlog_bridge(bridge)


def source_signal(case_id: str) -> dict[str, Any] | None:
    bridge = source_bridge(case_id)
    signal = bridge.get("backlog_signal")
    return backlog_bridge.validate_backlog_signal(signal) if isinstance(signal, Mapping) else None


def validate_backlog_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    validated = backlog_bridge.validate_backlog_signal(signal)
    if validated.get("destination") != "product_loop_backlog":
        raise PatchProposalCustomerFeedbackProductOwnerGateError("source signal must come from product_loop_backlog")
    if validated.get("next_boundary") != "product_owner_prioritization":
        raise PatchProposalCustomerFeedbackProductOwnerGateError("source signal must stop at product owner prioritization")
    if validated.get("priority_assignment") != "not_assigned":
        raise PatchProposalCustomerFeedbackProductOwnerGateError("source signal must not include priority assignment")
    if validated.get("ready_for_execution") is not False:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("source signal must not be executable")
    if validated.get("ready_for_customer_delivery") is not False:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("source signal must not be customer-deliverable")
    return validated


def build_candidate(backlog_signal: Mapping[str, Any]) -> dict[str, Any]:
    signal = validate_backlog_signal(backlog_signal)
    signal_hash = artifact_hash(signal)
    candidate = {
        **_base(CANDIDATE_SCHEMA_VERSION),
        "candidate_id": f"patch-proposal-product-spec-eval-candidate-{signal_hash[:16]}",
        "source_backlog_signal_id": signal["signal_id"],
        "source_backlog_signal_hash": signal_hash,
        "source_feedback_intake_id": signal["source_feedback_intake_id"],
        "source_feedback_intake_case_id": signal["source_feedback_intake_case_id"],
        "source_feedback_intake_hash": signal["source_feedback_intake_hash"],
        "source_feedback_intake_ref": signal["source_feedback_intake_ref"],
        "source_delivery_outcome_ref": signal["source_delivery_outcome_ref"],
        "source_delivery_outcome_hash": signal["source_delivery_outcome_hash"],
        "source_delivery_class": "patch-proposal",
        "feedback_ref": {
            "signal_type": signal["feedback_ref"]["signal_type"],
            "signal_ref_hash": signal["feedback_ref"]["signal_ref_hash"],
            "payload_hash_only": True,
            "raw_feedback_included": False,
            "private_customer_data_included": False,
        },
        "loop": "developer_feedback_loop",
        "destination": "product_spec_eval_candidate_queue",
        "next_boundary": "product_spec_eval_authoring",
        "priority_state": "unassigned",
        "priority_score_included": False,
        "requires_product_owner_prioritization_before_execution": True,
        "ready_for_execution": False,
        "ready_for_delivery_trust_harness": False,
        "blocked_destinations": list(BLOCKED_DESTINATIONS),
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_candidate(candidate)


def validate_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("candidate schema_version drifted")
    _validate_privacy(candidate, label=CANDIDATE_SCHEMA_VERSION)
    _validate_effect_boundary(candidate, label=CANDIDATE_SCHEMA_VERSION)
    if candidate.get("destination") != "product_spec_eval_candidate_queue":
        raise PatchProposalCustomerFeedbackProductOwnerGateError("candidate destination must be product_spec_eval_candidate_queue")
    if candidate.get("next_boundary") != "product_spec_eval_authoring":
        raise PatchProposalCustomerFeedbackProductOwnerGateError("candidate next boundary must be product_spec_eval_authoring")
    if candidate.get("priority_state") != "unassigned":
        raise PatchProposalCustomerFeedbackProductOwnerGateError("candidate priority must remain unassigned")
    if candidate.get("priority_score_included") is not False:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("candidate must not include priority score")
    for key in ("ready_for_execution", "ready_for_delivery_trust_harness"):
        if candidate.get(key) is not False:
            raise PatchProposalCustomerFeedbackProductOwnerGateError(f"candidate {key} must remain false")
    blocked = candidate.get("blocked_destinations")
    if not isinstance(blocked, list):
        raise PatchProposalCustomerFeedbackProductOwnerGateError("candidate blocked_destinations must be a list")
    for destination in BLOCKED_DESTINATIONS:
        if destination not in blocked:
            raise PatchProposalCustomerFeedbackProductOwnerGateError(f"candidate missing blocked destination: {destination}")
    return dict(candidate)


def build_product_owner_receipt(
    case_id: str,
    *,
    backlog_signal: Mapping[str, Any] | None = None,
    source_bridge_payload: Mapping[str, Any] | None = None,
    active_owner_reconstruction: bool = True,
    requested_next_boundary: str = "product_spec_eval_candidate_queue",
    automatic_priority_assignment_requested: bool = False,
    automatic_execution_requested: bool = False,
    customer_visible_follow_up_requested: bool = False,
    source_mutation_requested: bool = False,
    production_mutation_requested: bool = False,
    secret_attached: bool = False,
    model_credential_attached: bool = False,
) -> dict[str, Any]:
    bridge = (
        backlog_bridge.validate_customer_feedback_backlog_bridge(source_bridge_payload)
        if source_bridge_payload is not None
        else None
    )
    signal_payload = backlog_signal
    if signal_payload is None and bridge is not None:
        maybe_signal = bridge.get("backlog_signal")
        signal_payload = maybe_signal if isinstance(maybe_signal, Mapping) else None

    reasons: list[str] = []
    validated_signal: dict[str, Any] | None = None
    if signal_payload is None:
        reasons.append("source_backlog_signal_missing")
    else:
        validated_signal = validate_backlog_signal(signal_payload)
    if not active_owner_reconstruction:
        reasons.append("product_owner_reconstruction_missing")
    if requested_next_boundary != "product_spec_eval_candidate_queue":
        reasons.append("requested_next_boundary_not_product_spec_eval_candidate_queue")
    for flag, reason in (
        (automatic_priority_assignment_requested, "automatic_priority_assignment_rejected"),
        (automatic_execution_requested, "automatic_execution_rejected"),
        (customer_visible_follow_up_requested, "customer_visible_follow_up_rejected"),
        (source_mutation_requested, "source_mutation_rejected"),
        (production_mutation_requested, "production_mutation_rejected"),
        (secret_attached, "secret_rejected"),
        (model_credential_attached, "model_credential_rejected"),
    ):
        if flag:
            reasons.append(reason)

    candidate = None if reasons else build_candidate(validated_signal or {})
    signal_hash = artifact_hash(validated_signal) if validated_signal is not None else None
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "product_owner_receipt_id": (
            f"patch-proposal-customer-feedback-product-owner-{signal_hash[:16]}"
            if signal_hash
            else f"patch-proposal-customer-feedback-product-owner-blocked-{case_id}"
        ),
        "case_id": case_id,
        "status": "queued_for_spec_eval_candidate" if candidate else "blocked",
        "decision": "create_patch_proposal_spec_eval_candidate" if candidate else "block_patch_proposal_product_owner_gate",
        "blocked_reasons": reasons,
        "source_refs": {
            "backlog_bridge_ref": (
                f"fixtures/patch-proposal-customer-feedback-backlog-bridge/"
                f"{_bridge_case_for_product_owner_case(case_id)}/patch-proposal-customer-feedback-backlog-bridge.json"
            ),
            "backlog_bridge_id": bridge.get("bridge_id") if bridge else None,
            "backlog_bridge_hash": artifact_hash(bridge) if bridge else None,
            "backlog_signal_id": validated_signal.get("signal_id") if validated_signal else None,
            "backlog_signal_hash": signal_hash,
            "customer_feedback_intake_ref": validated_signal.get("source_feedback_intake_ref") if validated_signal else None,
            "customer_feedback_intake_hash": (
                validated_signal.get("source_feedback_intake_hash") if validated_signal else None
            ),
            "customer_delivery_outcome_ref": (
                validated_signal.get("source_delivery_outcome_ref") if validated_signal else None
            ),
            "customer_delivery_outcome_hash": (
                validated_signal.get("source_delivery_outcome_hash") if validated_signal else None
            ),
        },
        "product_owner_reconstruction": {
            "active_reconstruction_present": active_owner_reconstruction,
            "passive_attention_only_sufficient": False,
            "owner_ref": "product-owner-role",
            "reconstructed_boundaries": [
                "feedback_signal_hash_only",
                "spec_eval_candidate_queue_only",
                "priority_unassigned",
                "no_automatic_execution",
                "no_customer_visible_follow_up",
                "no_source_mutation",
                "no_production_mutation",
            ],
        },
        "requested_transition": {
            "from": "product_loop_backlog",
            "to": requested_next_boundary,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "customer_visible_follow_up_requested": customer_visible_follow_up_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
        },
        "product_owner_policy": {
            "allowed_next_boundary": "product_spec_eval_candidate_queue",
            "automatic_priority_assignment_allowed": False,
            "automatic_execution_allowed": False,
            "customer_visible_follow_up_allowed": False,
            "source_mutation_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "checks": {
            "source_backlog_signal_present": validated_signal is not None,
            "active_product_owner_reconstruction_present": active_owner_reconstruction,
            "metadata_only_candidate": True,
            "automatic_priority_assignment_requested": automatic_priority_assignment_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "customer_visible_follow_up_requested": customer_visible_follow_up_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "secret_attached": secret_attached,
            "model_credential_attached": model_credential_attached,
        },
        "quality_gates": {
            "accepted_backlog_signal_required": True,
            "active_product_owner_reconstruction_required": True,
            "metadata_only_spec_eval_candidate_required": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_execution_blocked": True,
            "customer_visible_follow_up_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "candidate": candidate,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_product_owner_receipt(receipt)


def validate_product_owner_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    _validate_effect_boundary(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    decision = receipt.get("decision")
    reasons = receipt.get("blocked_reasons")
    candidate = receipt.get("candidate")
    if status not in {"queued_for_spec_eval_candidate", "blocked"}:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("receipt status must be queued_for_spec_eval_candidate or blocked")
    if not isinstance(reasons, list):
        raise PatchProposalCustomerFeedbackProductOwnerGateError("receipt blocked_reasons must be a list")
    if status == "queued_for_spec_eval_candidate":
        if decision != "create_patch_proposal_spec_eval_candidate":
            raise PatchProposalCustomerFeedbackProductOwnerGateError("queued receipt must create a patch proposal spec/eval candidate")
        if reasons:
            raise PatchProposalCustomerFeedbackProductOwnerGateError("queued receipt must not carry blocked reasons")
        if not isinstance(candidate, Mapping):
            raise PatchProposalCustomerFeedbackProductOwnerGateError("queued receipt must include candidate")
        validate_candidate(candidate)
    else:
        if decision != "block_patch_proposal_product_owner_gate":
            raise PatchProposalCustomerFeedbackProductOwnerGateError("blocked receipt must block the Product Owner gate")
        if not reasons:
            raise PatchProposalCustomerFeedbackProductOwnerGateError("blocked receipt must include reasons")
        if candidate is not None:
            raise PatchProposalCustomerFeedbackProductOwnerGateError("blocked receipt must not include candidate")

    reconstruction = _require_object(receipt, "product_owner_reconstruction", label=RECEIPT_SCHEMA_VERSION)
    if reconstruction.get("passive_attention_only_sufficient") is not False:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("passive Product Owner attention alone is insufficient")
    if status == "queued_for_spec_eval_candidate" and reconstruction.get("active_reconstruction_present") is not True:
        raise PatchProposalCustomerFeedbackProductOwnerGateError("queued receipt requires active Product Owner reconstruction")

    policy = _require_object(receipt, "product_owner_policy", label=RECEIPT_SCHEMA_VERSION)
    if policy.get("allowed_next_boundary") != "product_spec_eval_candidate_queue":
        raise PatchProposalCustomerFeedbackProductOwnerGateError("policy must stop at spec/eval candidate queue")
    for key in (
        "automatic_priority_assignment_allowed",
        "automatic_execution_allowed",
        "customer_visible_follow_up_allowed",
        "source_mutation_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
    ):
        if policy.get(key) is not False:
            raise PatchProposalCustomerFeedbackProductOwnerGateError(f"policy.{key} must be False")
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    for key in (
        "automatic_priority_assignment_requested",
        "automatic_execution_requested",
        "customer_visible_follow_up_requested",
        "source_mutation_requested",
        "production_mutation_requested",
        "secret_attached",
        "model_credential_attached",
    ):
        if status == "queued_for_spec_eval_candidate" and checks.get(key) is not False:
            raise PatchProposalCustomerFeedbackProductOwnerGateError(f"queued receipt checks.{key} must be False")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerFeedbackProductOwnerGateError(f"Unknown case id: {case_id}")
    bridge = source_bridge(case_id)
    signal = source_signal(case_id)
    receipt = build_product_owner_receipt(
        case_id,
        backlog_signal=signal,
        source_bridge_payload=bridge,
        active_owner_reconstruction=case_id != "blocked-missing-owner-reconstruction",
        requested_next_boundary=(
            "delivery_trust_harness" if case_id == "blocked-skip-to-delivery-harness" else "product_spec_eval_candidate_queue"
        ),
        automatic_priority_assignment_requested=case_id == "blocked-automatic-priority-assignment",
        automatic_execution_requested=case_id == "blocked-automatic-execution",
        customer_visible_follow_up_requested=case_id == "blocked-customer-visible-follow-up",
        source_mutation_requested=case_id == "blocked-source-mutation",
        production_mutation_requested=case_id == "blocked-production-mutation",
        secret_attached=case_id == "blocked-secret",
        model_credential_attached=case_id == "blocked-model-credential",
    )
    artifacts = {"patch-proposal-customer-feedback-product-owner-receipt.json": receipt}
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
            cases[case_id]["patch-proposal-customer-feedback-product-owner-receipt.json"]
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
            "Prove Patch Proposal customer-feedback backlog signals can create metadata-only spec/eval "
            "candidates only after active Product Owner boundary reconstruction, without priority assignment, "
            "execution, customer-visible follow-up, source mutation, production mutation, secrets, or model credentials."
        ),
        "source_chain": {
            "customer_feedback_intake_report": "platform/generated/study-anything-patch-proposal-customer-feedback-intake.json",
            "customer_feedback_backlog_bridge_report": (
                "platform/generated/study-anything-patch-proposal-customer-feedback-backlog-bridge.json"
            ),
            "recorded_backlog_signal": (
                "fixtures/patch-proposal-customer-feedback-backlog-bridge/pass-customer-signal/"
                "product-loop-backlog-signal.json"
            ),
        },
        "product_owner_matrix": {
            "queued_spec_eval_candidates": queued_count,
            "blocked_product_owner_transitions": blocked_count,
            "total_cases": len(case_reports),
            "customer_signal_queued": True,
            "operator_signal_queued": True,
            "host_platform_agent_signal_queued": True,
            "missing_owner_reconstruction_rejected": True,
            "automatic_priority_assignment_rejected": True,
            "automatic_execution_rejected": True,
            "customer_visible_follow_up_rejected": True,
            "source_mutation_rejected": True,
            "production_mutation_rejected": True,
            "blocked_backlog_source_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "accepted_backlog_signal_required": True,
            "active_product_owner_reconstruction_required": True,
            "metadata_only_spec_eval_candidate_required": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_execution_blocked": True,
            "customer_visible_follow_up_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
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
    parser.add_argument("--backlog-signal", type=Path, help="Build a receipt from a product-loop-backlog-signal JSON file.")
    parser.add_argument("--bridge", type=Path, help="Build a receipt from a Patch Proposal Customer Feedback Backlog Bridge JSON file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.backlog_signal or args.bridge:
        bridge_payload = load_json(args.bridge) if args.bridge else None
        signal_payload = load_json(args.backlog_signal) if args.backlog_signal else None
        cases = {
            "custom": {
                "patch-proposal-customer-feedback-product-owner-receipt.json": build_product_owner_receipt(
                    "custom",
                    backlog_signal=signal_payload,
                    source_bridge_payload=bridge_payload,
                )
            }
        }
        receipt = cases["custom"]["patch-proposal-customer-feedback-product-owner-receipt.json"]
        candidate = receipt.get("candidate")
        if isinstance(candidate, Mapping):
            cases["custom"]["patch-proposal-product-spec-eval-candidate.json"] = dict(candidate)
    else:
        selected = CASE_IDS if args.case == "all" else (args.case,)
        cases = {case_id: build_case_artifacts(case_id) for case_id in selected}

    write_case_artifacts(args.output_dir, cases)
    result: dict[str, Any] = {
        "schema_version": "patch-proposal-customer-feedback-product-owner-gate-cli-result-v1",
        "status": "ok",
        "case_ids": list(cases),
        "output_dir_ref": args.output_dir.name,
        "queued_spec_eval_candidates": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-customer-feedback-product-owner-receipt.json"]["status"]
            == "queued_for_spec_eval_candidate"
        ),
        "blocked_product_owner_transitions": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-customer-feedback-product-owner-receipt.json"]["status"] == "blocked"
        ),
        "privacy": dict(PRIVACY_FLAGS),
        "effect_boundary": dict(EFFECT_BOUNDARY),
    }
    if args.report and not (args.backlog_signal or args.bridge):
        result["report"] = build_report(cases)
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
