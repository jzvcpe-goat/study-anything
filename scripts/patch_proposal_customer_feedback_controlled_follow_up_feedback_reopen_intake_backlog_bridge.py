#!/usr/bin/env python3
"""Bridge controlled follow-up feedback reopen-intake gates into backlog signals.

The bridge is metadata-only. It can prepare a Product Loop backlog signal ref
from an allowed reopen-intake gate receipt, but it cannot create a live backlog
item, assign priority, execute work, contact customers, mutate source, mutate
production, publish externally, call models, or store raw customer material.
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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate as gate  # noqa: E402


BRIDGE_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge-v1"
BACKLOG_SIGNAL_SCHEMA_VERSION = "product-loop-backlog-signal-v1"
REPORT_SCHEMA_VERSION = BRIDGE_SCHEMA_VERSION

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge"
)
GATE_FIXTURE_DIR = (
    ROOT
    / "fixtures"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate"
)
GATE_REPORT_REF = (
    "platform/generated/"
    "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.json"
)

CASE_IDS = (
    "pass",
    "blocked-missing-gate-receipt",
    "blocked-gate-blocked",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-product-loop-target",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-customer-identity",
    "blocked-automatic-customer-contact",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-prioritization",
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
    **gate.PRIVACY_FLAGS,
    "controlled_follow_up_feedback_reopen_intake_backlog_bridge_metadata_only": True,
    "product_loop_backlog_signal_metadata_only": True,
    "raw_backlog_description_included": False,
    "raw_follow_up_data_included": False,
    "raw_customer_data_included": False,
    "customer_identity_included": False,
    "customer_visible_payload_included": False,
    "automatic_backlog_creation_payload_included": False,
    "automatic_priority_rationale_included": False,
    "automatic_execution_payload_included": False,
}

EFFECT_BOUNDARY = {
    "study_anything_backlog_storage_mutated": False,
    "study_anything_product_loop_backlog_mutation_performed": False,
    "study_anything_backlog_item_created": False,
    "study_anything_priority_assignment_performed": False,
    "study_anything_patch_execution_performed": False,
    "study_anything_customer_follow_up_send_performed": False,
    "study_anything_automatic_follow_up_performed": False,
    "study_anything_automatic_customer_contact_performed": False,
    "study_anything_repository_mutation_performed": False,
    "study_anything_external_publication_performed": False,
    "study_anything_production_mutation_performed": False,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
}

FORBIDDEN_RAW_FIELDS = {
    *gate.FORBIDDEN_RAW_FIELDS,
    "raw_backlog_description",
    "backlog_description_body",
    "backlog_item_body",
    "product_backlog_body",
    "raw_follow_up_data",
    "raw_follow_up_body",
    "raw_customer_data",
    "raw_customer_reply",
    "customer_identity",
    "customer_email",
    "customer_name",
    "customer_visible_payload",
    "priority_rationale",
    "automatic_priority",
    "assigned_priority",
    "execution_payload",
    "automatic_execution_payload",
    "apply_patch_payload",
    "raw_patch_body",
    "raw_diff_body",
    "source_mutation_payload",
    "production_mutation_payload",
    "external_publication_payload",
    "model_call_payload",
    "model_api_key",
    "agent_credential",
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "An allowed controlled follow-up feedback reopen-intake gate receipt can become a "
        "metadata-only Product Loop backlog signal ref. The signal is not a live backlog "
        "item, not prioritized, not executed, not sent to a customer, not published, "
        "not promoted to production, and not evidence of customer satisfaction."
    ),
    "not_claimed": [
        "raw follow-up data included",
        "raw customer data included",
        "customer identity included",
        "live backlog item created",
        "automatic priority assigned",
        "automatic execution started",
        "Study Anything contacted a customer",
        "Study Anything changed source",
        "Study Anything changed production",
        "Study Anything published externally",
        "Study Anything called a model",
        "customer satisfaction certified",
        "truth or security certified",
    ],
}


class PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(ValueError):
    """Raised when reopen-intake backlog bridge artifacts are unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            f"Expected JSON object: {path}"
        )
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
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            f"{label}.{key} must be an object"
        )
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
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _case_flags(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            f"Unknown case id: {case_id}"
        )
    if case_id == "blocked-missing-gate-receipt":
        gate_case: str | None = None
    elif case_id == "blocked-gate-blocked":
        gate_case = "blocked-bridge-blocked"
    else:
        gate_case = "pass"
    return {
        "gate_case": gate_case,
        "bridge_ref_present": case_id != "blocked-missing-bridge-ref",
        "closure_ref_present": case_id != "blocked-missing-closure-ref",
        "outcome_ref_present": case_id != "blocked-missing-outcome-ref",
        "action_ref_present": case_id != "blocked-missing-action-ref",
        "external_actor_ref_present": case_id != "blocked-missing-actor-ref",
        "intake_candidate_ref_present": case_id != "blocked-missing-intake-candidate-ref",
        "product_loop_intake_item_ref_present": case_id != "blocked-missing-intake-item-ref",
        "product_loop_target_declared": case_id != "blocked-missing-product-loop-target",
        "claim_boundary_visible": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_visible": case_id != "blocked-missing-privacy-boundary",
        "raw_follow_up_data_attached": case_id == "blocked-raw-follow-up-data",
        "raw_customer_data_attached": case_id == "blocked-raw-customer-data",
        "customer_identity_attached": case_id == "blocked-customer-identity",
        "automatic_customer_contact_performed": case_id == "blocked-automatic-customer-contact",
        "automatic_backlog_creation_performed": case_id == "blocked-automatic-backlog-creation",
        "automatic_prioritization_performed": case_id == "blocked-automatic-prioritization",
        "automatic_execution_performed": case_id == "blocked-automatic-execution",
        "product_loop_backlog_mutation_performed": case_id == "blocked-product-loop-backlog-mutation",
        "source_mutation_performed": case_id == "blocked-source-mutation",
        "production_mutation_performed": case_id == "blocked-production-mutation",
        "external_publication_payload_attached": case_id == "blocked-external-publication-payload",
        "model_call_performed": case_id == "blocked-model-call",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_gate(case_id: str) -> dict[str, Any] | None:
    gate_case = _case_flags(case_id)["gate_case"]
    if gate_case is None:
        return None
    receipt = load_json(
        GATE_FIXTURE_DIR
        / gate_case
        / "patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"
    )
    return gate.validate_controlled_follow_up_feedback_reopen_intake_gate(receipt)


def _source_gate_ref(flags: Mapping[str, Any]) -> str | None:
    gate_case = flags["gate_case"]
    if gate_case is None:
        return None
    return (
        "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate/"
        f"{gate_case}/patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"
    )


def build_backlog_signal(case_id: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
    summary = _require_object(receipt, "reopen_intake_gate", label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    source_refs = _require_object(receipt, "source_refs", label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    source_hash = artifact_hash(receipt)
    signal_ref_hash = summary["product_loop_intake_item_ref_hash"]
    signal = {
        **_base(BACKLOG_SIGNAL_SCHEMA_VERSION),
        "signal_id": f"patch-proposal-reopen-intake-product-loop-backlog-{source_hash[:16]}",
        "source_feedback_intake_id": receipt["gate_id"],
        "source_feedback_intake_case_id": receipt["case_id"],
        "source_feedback_intake_hash": source_hash,
        "source_feedback_intake_ref": (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate/"
            f"{receipt['case_id']}/patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"
        ),
        "source_reopen_intake_gate_id": receipt["gate_id"],
        "source_reopen_intake_gate_hash": source_hash,
        "source_reopen_intake_gate_ref": (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate/"
            f"{receipt['case_id']}/patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"
        ),
        "source_reopen_intake_bridge_ref": source_refs["reopen_intake_bridge_receipt_ref"],
        "source_reopen_intake_bridge_hash": source_refs["reopen_intake_bridge_receipt_hash"],
        "closure_receipt_hash": summary["closure_receipt_hash"],
        "outcome_receipt_hash": summary["outcome_receipt_hash"],
        "external_actor_ref_hash": summary["external_actor_ref_hash"],
        "action_ref_hash": summary["action_ref_hash"],
        "intake_candidate_ref_hash": summary["intake_candidate_ref_hash"],
        "product_loop_intake_item_ref_hash": signal_ref_hash,
        "feedback_ref": {
            "signal_type": "controlled_follow_up_feedback_reopen_intake",
            "signal_ref_hash": signal_ref_hash,
            "payload_hash_only": True,
            "raw_feedback_included": False,
            "raw_follow_up_data_included": False,
            "raw_customer_data_included": False,
            "customer_identity_included": False,
        },
        "loop": "external_feedback_loop",
        "source_loop": "controlled_follow_up_feedback_reopen_intake",
        "destination": "product_loop_backlog",
        "next_boundary": "product_owner_prioritization",
        "priority_assignment": "not_assigned",
        "requires_product_owner_prioritization": True,
        "ready_for_execution": False,
        "ready_for_customer_delivery": False,
        "blocked_destinations": [
            "automatic_backlog_creation",
            "automatic_priority_assignment",
            "automatic_execution",
            "automatic_follow_up",
            "customer_visible_action",
            "source_mutation",
            "external_publication",
            "production_mutation",
            "model_call",
        ],
        "provenance_chain": [
            "product_loop",
            "dual_loop",
            "delivery_trust_case",
            "active_reconstruction",
            "controlled_follow_up_outcome",
            "controlled_follow_up_feedback_loop_closure",
            "controlled_follow_up_feedback_reopen_intake_bridge",
            "controlled_follow_up_feedback_reopen_intake_gate",
        ],
        "restarted_product_loop": True,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_backlog_signal(signal)


def build_controlled_follow_up_feedback_reopen_intake_backlog_bridge(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    receipt = source_gate(case_id)
    source_checks = _require_object(receipt, "checks", label="source_reopen_intake_gate") if receipt else {}
    source_summary = (
        _require_object(receipt, "reopen_intake_gate", label="source_reopen_intake_gate") if receipt else {}
    )
    source_refs = _require_object(receipt, "source_refs", label="source_reopen_intake_gate") if receipt else {}
    source_allowed = receipt is not None and receipt.get("status") == "allowed"
    gate_hash = artifact_hash(receipt) if receipt is not None else None

    checks = {
        "reopen_intake_gate_receipt_present": receipt is not None,
        "source_reopen_intake_gate_allowed": source_allowed,
        "product_loop_ref_preserved": source_allowed
        and source_checks.get("product_loop_ref_preserved") is True,
        "dual_loop_refs_preserved": source_allowed
        and source_checks.get("dual_loop_refs_preserved") is True,
        "delivery_trust_refs_preserved": source_allowed
        and source_checks.get("delivery_trust_refs_preserved") is True,
        "active_reconstruction_ref_preserved": source_allowed
        and source_checks.get("active_reconstruction_ref_preserved") is True,
        "bridge_ref_preserved": source_allowed
        and bool(flags["bridge_ref_present"])
        and isinstance(source_refs.get("reopen_intake_bridge_receipt_ref"), str)
        and isinstance(source_refs.get("reopen_intake_bridge_receipt_hash"), str)
        and len(source_refs["reopen_intake_bridge_receipt_hash"]) == 64,
        "closure_ref_preserved": source_allowed
        and bool(flags["closure_ref_present"])
        and isinstance(source_summary.get("closure_receipt_hash"), str)
        and len(source_summary["closure_receipt_hash"]) == 64,
        "outcome_ref_preserved": source_allowed
        and bool(flags["outcome_ref_present"])
        and isinstance(source_summary.get("outcome_receipt_hash"), str)
        and len(source_summary["outcome_receipt_hash"]) == 64,
        "action_ref_preserved": source_allowed
        and bool(flags["action_ref_present"])
        and isinstance(source_summary.get("action_ref_hash"), str)
        and len(source_summary["action_ref_hash"]) == 64,
        "external_actor_ref_preserved": source_allowed
        and bool(flags["external_actor_ref_present"])
        and isinstance(source_summary.get("external_actor_ref_hash"), str)
        and len(source_summary["external_actor_ref_hash"]) == 64,
        "intake_candidate_ref_preserved": source_allowed
        and bool(flags["intake_candidate_ref_present"])
        and isinstance(source_summary.get("intake_candidate_ref_hash"), str)
        and len(source_summary["intake_candidate_ref_hash"]) == 64,
        "product_loop_intake_item_ref_preserved": source_allowed
        and bool(flags["product_loop_intake_item_ref_present"])
        and isinstance(source_summary.get("product_loop_intake_item_ref_hash"), str)
        and len(source_summary["product_loop_intake_item_ref_hash"]) == 64,
        "product_loop_target_declared": bool(flags["product_loop_target_declared"]),
        "claim_boundary_visible": bool(flags["claim_boundary_visible"]),
        "privacy_boundary_visible": bool(flags["privacy_boundary_visible"]),
        "metadata_only_backlog_signal": True,
        "raw_follow_up_data_attached": bool(flags["raw_follow_up_data_attached"]),
        "raw_customer_data_attached": bool(flags["raw_customer_data_attached"]),
        "customer_identity_attached": bool(flags["customer_identity_attached"]),
        "automatic_customer_contact_performed": bool(flags["automatic_customer_contact_performed"]),
        "automatic_backlog_creation_performed": bool(flags["automatic_backlog_creation_performed"]),
        "automatic_prioritization_performed": bool(flags["automatic_prioritization_performed"]),
        "automatic_execution_performed": bool(flags["automatic_execution_performed"]),
        "product_loop_backlog_mutation_performed": bool(flags["product_loop_backlog_mutation_performed"]),
        "source_mutation_performed": bool(flags["source_mutation_performed"]),
        "production_mutation_performed": bool(flags["production_mutation_performed"]),
        "external_publication_payload_attached": bool(flags["external_publication_payload_attached"]),
        "model_call_performed": bool(flags["model_call_performed"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    if not checks["reopen_intake_gate_receipt_present"]:
        reasons.append("reopen_intake_gate_receipt_missing")
    elif not checks["source_reopen_intake_gate_allowed"]:
        reasons.append("source_reopen_intake_gate_not_allowed")
    if receipt is not None and source_allowed:
        for key, reason in (
            ("product_loop_ref_preserved", "product_loop_ref_missing"),
            ("dual_loop_refs_preserved", "dual_loop_ref_missing"),
            ("delivery_trust_refs_preserved", "delivery_trust_ref_missing"),
            ("active_reconstruction_ref_preserved", "active_reconstruction_ref_missing"),
            ("bridge_ref_preserved", "reopen_intake_bridge_ref_missing"),
            ("closure_ref_preserved", "closure_ref_missing"),
            ("outcome_ref_preserved", "outcome_ref_missing"),
            ("action_ref_preserved", "action_ref_missing"),
            ("external_actor_ref_preserved", "external_actor_ref_missing"),
            ("intake_candidate_ref_preserved", "intake_candidate_ref_missing"),
            ("product_loop_intake_item_ref_preserved", "product_loop_intake_item_ref_missing"),
        ):
            if not checks[key]:
                reasons.append(reason)
    for key, reason in (
        ("product_loop_target_declared", "product_loop_target_missing"),
        ("claim_boundary_visible", "claim_boundary_missing"),
        ("privacy_boundary_visible", "privacy_boundary_missing"),
        ("metadata_only_backlog_signal", "metadata_only_backlog_signal_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_follow_up_data_attached", "raw_follow_up_data_rejected"),
        ("raw_customer_data_attached", "raw_customer_data_rejected"),
        ("customer_identity_attached", "customer_identity_rejected"),
        ("automatic_customer_contact_performed", "automatic_customer_contact_rejected"),
        ("automatic_backlog_creation_performed", "automatic_backlog_creation_rejected"),
        ("automatic_prioritization_performed", "automatic_prioritization_rejected"),
        ("automatic_execution_performed", "automatic_execution_rejected"),
        ("product_loop_backlog_mutation_performed", "product_loop_backlog_mutation_rejected"),
        ("source_mutation_performed", "source_mutation_rejected"),
        ("production_mutation_performed", "production_mutation_rejected"),
        ("external_publication_payload_attached", "external_publication_payload_rejected"),
        ("model_call_performed", "model_call_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    reasons = list(dict.fromkeys(reasons))
    backlog_signal = None if reasons or receipt is None else build_backlog_signal(case_id, receipt)
    bridge = {
        **_base(BRIDGE_SCHEMA_VERSION),
        "bridge_id": f"patch-proposal-reopen-intake-backlog-bridge-{(gate_hash or 'missing')[:16]}-{case_id}",
        "case_id": case_id,
        "status": "queued_for_product_loop" if backlog_signal else "blocked",
        "decision": (
            "emit_reopen_intake_product_loop_backlog_signal"
            if backlog_signal
            else "block_reopen_intake_product_loop_backlog_signal"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "reopen_intake_gate_receipt_ref": _source_gate_ref(flags),
            "reopen_intake_gate_receipt_hash": gate_hash,
            "reopen_intake_gate_report_ref": GATE_REPORT_REF,
            "reopen_intake_bridge_receipt_ref": source_refs.get("reopen_intake_bridge_receipt_ref"),
            "reopen_intake_bridge_receipt_hash": source_refs.get("reopen_intake_bridge_receipt_hash"),
        },
        "backlog_signal": backlog_signal,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "checks": checks,
        "quality_gates": {
            "allowed_reopen_intake_gate_required": True,
            "full_product_loop_chain_required": True,
            "full_dual_loop_chain_required": True,
            "full_delivery_trust_chain_required": True,
            "active_reconstruction_required": True,
            "metadata_only_backlog_signal_required": True,
            "backlog_creation_requires_later_product_owner_gate": True,
            "priority_assignment_requires_later_product_owner_gate": True,
            "automatic_customer_contact_blocked": True,
            "automatic_backlog_creation_blocked": True,
            "automatic_prioritization_blocked": True,
            "automatic_execution_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_controlled_follow_up_feedback_reopen_intake_backlog_bridge(bridge)


def validate_backlog_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    if signal.get("schema_version") != BACKLOG_SIGNAL_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "backlog signal schema_version drifted"
        )
    _validate_privacy(signal, label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    if signal.get("destination") != "product_loop_backlog":
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "backlog signal destination must be product_loop_backlog"
        )
    if signal.get("next_boundary") != "product_owner_prioritization":
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "backlog signal must stop at product owner prioritization"
        )
    if signal.get("priority_assignment") != "not_assigned":
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "backlog signal must not assign priority"
        )
    if signal.get("requires_product_owner_prioritization") is not True:
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "backlog signal must require product owner prioritization"
        )
    for key in ("ready_for_execution", "ready_for_customer_delivery"):
        if signal.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                f"backlog signal {key} must remain false"
            )
    blocked = signal.get("blocked_destinations")
    if not isinstance(blocked, list):
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "backlog signal blocked_destinations must be a list"
        )
    for destination in (
        "automatic_backlog_creation",
        "automatic_priority_assignment",
        "automatic_execution",
        "automatic_follow_up",
        "customer_visible_action",
        "source_mutation",
        "external_publication",
        "production_mutation",
        "model_call",
    ):
        if destination not in blocked:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                f"backlog signal missing blocked destination: {destination}"
            )
    for key in (
        "source_reopen_intake_gate_hash",
        "source_reopen_intake_bridge_hash",
        "closure_receipt_hash",
        "outcome_receipt_hash",
        "external_actor_ref_hash",
        "action_ref_hash",
        "intake_candidate_ref_hash",
        "product_loop_intake_item_ref_hash",
    ):
        value = signal.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                f"backlog signal {key} must be a hash"
            )
    effect = _require_object(signal, "effect_boundary", label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                f"backlog signal effect_boundary.{key} must be {expected!r}"
            )
    return dict(signal)


def validate_controlled_follow_up_feedback_reopen_intake_backlog_bridge(
    bridge: Mapping[str, Any],
) -> dict[str, Any]:
    if bridge.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "reopen-intake backlog bridge schema_version drifted"
        )
    _validate_privacy(bridge, label=BRIDGE_SCHEMA_VERSION)
    status = bridge.get("status")
    decision = bridge.get("decision")
    blocked_reasons = bridge.get("blocked_reasons")
    backlog_signal = bridge.get("backlog_signal")
    checks = _require_object(bridge, "checks", label=BRIDGE_SCHEMA_VERSION)
    if status not in {"queued_for_product_loop", "blocked"}:
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "bridge status must be queued_for_product_loop or blocked"
        )
    if not isinstance(blocked_reasons, list):
        raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
            "bridge blocked_reasons must be a list"
        )
    effect = _require_object(bridge, "effect_boundary", label=BRIDGE_SCHEMA_VERSION)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                f"bridge effect_boundary.{key} must be {expected!r}"
            )
    if status == "queued_for_product_loop":
        if decision != "emit_reopen_intake_product_loop_backlog_signal":
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                "queued bridge must emit reopen-intake backlog signal"
            )
        if blocked_reasons:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                "queued bridge must not carry blocked reasons"
            )
        for key in (
            "reopen_intake_gate_receipt_present",
            "source_reopen_intake_gate_allowed",
            "product_loop_ref_preserved",
            "dual_loop_refs_preserved",
            "delivery_trust_refs_preserved",
            "active_reconstruction_ref_preserved",
            "bridge_ref_preserved",
            "closure_ref_preserved",
            "outcome_ref_preserved",
            "action_ref_preserved",
            "external_actor_ref_preserved",
            "intake_candidate_ref_preserved",
            "product_loop_intake_item_ref_preserved",
            "product_loop_target_declared",
            "claim_boundary_visible",
            "privacy_boundary_visible",
            "metadata_only_backlog_signal",
        ):
            if checks.get(key) is not True:
                raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                    f"queued bridge missing check: {key}"
                )
        for key in (
            "raw_follow_up_data_attached",
            "raw_customer_data_attached",
            "customer_identity_attached",
            "automatic_customer_contact_performed",
            "automatic_backlog_creation_performed",
            "automatic_prioritization_performed",
            "automatic_execution_performed",
            "product_loop_backlog_mutation_performed",
            "source_mutation_performed",
            "production_mutation_performed",
            "external_publication_payload_attached",
            "model_call_performed",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                    f"queued bridge checks.{key} must remain false"
                )
        if not isinstance(backlog_signal, Mapping):
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                "queued bridge must include backlog signal"
            )
        validate_backlog_signal(backlog_signal)
    else:
        if decision != "block_reopen_intake_product_loop_backlog_signal":
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                "blocked bridge must block reopen-intake backlog signal"
            )
        if not blocked_reasons:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                "blocked bridge must include reasons"
            )
        if backlog_signal is not None:
            raise PatchProposalControlledFollowUpFeedbackReopenIntakeBacklogBridgeError(
                "blocked bridge must not include backlog signal"
            )
    return dict(bridge)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    bridge = build_controlled_follow_up_feedback_reopen_intake_backlog_bridge(case_id)
    artifacts = {"patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json": bridge}
    signal = bridge.get("backlog_signal")
    if isinstance(signal, Mapping):
        artifacts["product-loop-backlog-signal.json"] = dict(signal)
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        bridge = validate_controlled_follow_up_feedback_reopen_intake_backlog_bridge(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": bridge["status"],
                "decision": bridge["decision"],
                "blocked_reasons": bridge["blocked_reasons"],
                "backlog_signal_created": bridge["backlog_signal"] is not None,
            }
        )
    queued_count = sum(1 for row in case_reports if row["status"] == "queued_for_product_loop")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove allowed controlled follow-up feedback reopen-intake gate receipts can emit "
            "metadata-only Product Loop backlog signal refs without creating backlog items, "
            "assigning priority, executing work, contacting customers, mutating systems, "
            "publishing externally, calling models, or storing secrets."
        ),
        "source_chain": {
            "reopen_intake_gate_report": GATE_REPORT_REF,
            "allowed_reopen_intake_gate_receipt": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate/"
                "pass/patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"
            ),
        },
        "backlog_matrix": {
            "queued_backlog_signals": queued_count,
            "blocked_backlog_signals": blocked_count,
            "total_cases": len(case_reports),
            "allowed_reopen_intake_gate_queued": True,
            "missing_gate_receipt_rejected": True,
            "blocked_gate_rejected": True,
            "missing_bridge_ref_rejected": True,
            "missing_closure_ref_rejected": True,
            "missing_outcome_ref_rejected": True,
            "missing_action_ref_rejected": True,
            "missing_external_actor_ref_rejected": True,
            "missing_intake_candidate_ref_rejected": True,
            "missing_intake_item_ref_rejected": True,
            "missing_product_loop_target_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "raw_follow_up_data_rejected": True,
            "raw_customer_data_rejected": True,
            "customer_identity_rejected": True,
            "automatic_customer_contact_rejected": True,
            "automatic_backlog_creation_rejected": True,
            "automatic_prioritization_rejected": True,
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
            "allowed_reopen_intake_gate_required": True,
            "product_loop_target_required": True,
            "metadata_only_backlog_signal_required": True,
            "backlog_creation_requires_later_product_owner_gate": True,
            "priority_assignment_requires_later_product_owner_gate": True,
            "automatic_customer_contact_blocked": True,
            "automatic_backlog_creation_blocked": True,
            "automatic_prioritization_blocked": True,
            "automatic_execution_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    _validate_privacy(report, label=REPORT_SCHEMA_VERSION)
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
        "schema_version": "patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge-cli-result-v1",
        "status": "ok",
        "case_ids": list(selected),
        "output_dir_ref": args.output_dir.name,
        "queued_backlog_signals": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"]["status"]
            == "queued_for_product_loop"
        ),
        "blocked_backlog_signals": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"]["status"]
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
