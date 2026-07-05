#!/usr/bin/env python3
"""Gate Patch Proposal feedback handoff refs into controlled follow-up refs.

This layer consumes the metadata-only Delivery Trust Case Bridge artifacts from
the Patch Proposal Customer Feedback chain. It requires an active operator or
host-platform Agent reconstruction of the customer follow-up boundary before it
prepares a metadata-only follow-up envelope ref.

It does not create a customer-visible follow-up body, send anything to a
customer, mutate source, mutate production, publish externally, call models,
store secrets, or start a daemon.
"""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_delivery_trust_case_bridge as case_bridge  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-boundary-receipt-v1"
ENVELOPE_REFS_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-envelope-refs-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate-v1"
RECONSTRUCTION_SCHEMA_VERSION = "patch-proposal-follow-up-feedback-boundary-reconstruction-v1"

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate"
)

PASS_CASE_IDS = case_bridge.PASS_CASE_IDS
CASE_IDS = (
    *PASS_CASE_IDS,
    "blocked-missing-bridge-receipt",
    "blocked-invalid-bridge-receipt",
    "blocked-missing-handoff-refs",
    "blocked-handoff-refs-mismatch",
    "blocked-missing-reconstruction",
    "blocked-passive-reconstruction",
    "blocked-unsupported-reconstruction-source",
    "blocked-missing-product-loop-ref",
    "blocked-missing-dual-loop-ref",
    "blocked-missing-delivery-trust-case-ref",
    "blocked-raw-follow-up-body",
    "blocked-automatic-customer-send",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_SOURCE_STATUS = "delivery_trust_case_refs_ready"
ALLOWED_RECONSTRUCTION_SOURCES = {"operator", "host_platform_agent"}
REQUIRED_CHECKPOINT_IDS = {
    "recipient_scope",
    "claim_boundary",
    "evidence_refs",
    "blocked_effects",
}
REQUIRED_DELIVERY_TRUST_KINDS = {
    "delivery-trust-receipt",
    "customer-handoff-package",
    "delivery-trust-case",
}
REQUIRED_DUAL_LOOP_KINDS = {
    "failure-contract",
    "sandbox-receipt",
    "attention-reconstruction-summary",
    "dual-loop-gate-receipt",
}

PRIVACY_FLAGS = {
    **case_bridge.PRIVACY_FLAGS,
    "controlled_follow_up_boundary_metadata_only": True,
    "follow_up_envelope_refs_only": True,
    "follow_up_body_included": False,
    "raw_follow_up_body_included": False,
    "customer_visible_follow_up_included": False,
    "customer_visible_payload_included": False,
    "raw_customer_payload_included": False,
    "raw_customer_reply_included": False,
    "delivery_trust_case_body_included": False,
    "customer_handoff_package_body_included": False,
}

PROHIBITED_EFFECTS = {
    "study_anything_automatic_customer_send_performed": False,
    "study_anything_customer_visible_send_performed": False,
    "study_anything_customer_visible_follow_up_performed": False,
    "study_anything_source_mutation_performed": False,
    "study_anything_production_mutation_performed": False,
    "study_anything_external_publication_performed": False,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
}

FORBIDDEN_RAW_FIELDS = {
    *case_bridge.FORBIDDEN_RAW_FIELDS,
    "raw_follow_up",
    "raw_follow_up_body",
    "follow_up_body",
    "follow_up_text",
    "customer_follow_up_body",
    "customer_visible_follow_up",
    "customer_visible_follow_up_body",
    "automatic_customer_send_payload",
    "customer_visible_send",
    "customer_visible_send_body",
    "external_publication_payload",
    "source_mutation_payload",
    "production_payload",
    "model_api_key",
    "agent_credential",
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "A Patch Proposal Delivery Trust case handoff may be converted into "
        "metadata-only customer follow-up envelope refs only after Product Loop, "
        "Dual Loop, Delivery Trust Case, and active operator or host-platform "
        "Agent boundary reconstruction evidence all match."
    ),
    "not_claimed": [
        "raw follow-up body generated",
        "automatic customer send performed",
        "customer-visible send performed",
        "customer-visible follow-up performed",
        "source mutation allowed",
        "production mutation allowed",
        "external publication performed",
        "model call performed",
        "customer delivery completed",
        "human over-review replaced for all domains",
    ],
}


class PatchProposalControlledFollowUpFeedbackBoundaryGateError(ValueError):
    """Raised when controlled follow-up boundary evidence is unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"Expected JSON object: {path}")
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
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"{label}.{key} must be an object")
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
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _effect_boundary(*, envelope_prepared: bool) -> dict[str, Any]:
    return {
        "study_anything_controlled_follow_up_envelope_refs_prepared": envelope_prepared,
        **PROHIBITED_EFFECTS,
    }


def _validate_effect_boundary(payload: Mapping[str, Any], *, label: str) -> None:
    effect = _require_object(payload, "effect_boundary", label=label)
    for key, expected in PROHIBITED_EFFECTS.items():
        if effect.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(
                f"{label}.effect_boundary.{key} must be {expected!r}"
            )
    if payload.get("status") == "follow_up_envelope_refs_ready":
        if effect.get("study_anything_controlled_follow_up_envelope_refs_prepared") is not True:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(
                f"{label}.effect_boundary.study_anything_controlled_follow_up_envelope_refs_prepared must be true"
            )


def _artifact_ref(kind: str, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "kind": kind,
        "path": path,
        "schema_version": payload.get("schema_version"),
        "sha256": artifact_hash(payload),
        "raw_body_included": False,
    }
    for key in (
        "bridge_receipt_id",
        "reconstruction_id",
        "candidate_id",
        "run_id",
        "contract_id",
        "receipt_id",
        "summary_id",
        "gate_id",
        "case_id",
        "package_id",
        "envelope_id",
    ):
        value = payload.get(key)
        if isinstance(value, str):
            ref[key] = value
    return ref


def _source_case_id(case_id: str) -> str:
    return case_id if case_id in PASS_CASE_IDS else "pass-customer-signal"


def source_bridge_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return case_bridge.build_case_artifacts(_source_case_id(case_id))


def source_bridge_receipt(case_id: str) -> dict[str, Any] | None:
    artifacts = source_bridge_artifacts(case_id)
    receipt = artifacts.get("patch-proposal-controlled-follow-up-feedback-delivery-trust-case-bridge-receipt.json")
    return case_bridge.validate_bridge_receipt(receipt) if isinstance(receipt, Mapping) else None


def source_handoff_refs(case_id: str) -> dict[str, Any] | None:
    artifacts = source_bridge_artifacts(case_id)
    refs = artifacts.get("patch-proposal-controlled-follow-up-feedback-delivery-trust-case-handoff-refs.json")
    return case_bridge.validate_handoff_refs(refs) if isinstance(refs, Mapping) else None


def _reconstruction_source(case_id: str) -> str:
    if case_id == "pass-host-platform-agent-signal":
        return "host_platform_agent"
    return "operator"


def default_reconstruction(case_id: str) -> dict[str, Any]:
    source_type = _reconstruction_source(case_id)
    checkpoints = [
        {
            "checkpoint_id": "recipient_scope",
            "checkpoint_label": "recipient scope",
            "reconstructed_boundary": "Only the operator or host-platform Agent receives metadata refs; no customer send is allowed.",
            "evidence_strength": "strong",
            "raw_answer_included": False,
        },
        {
            "checkpoint_id": "claim_boundary",
            "checkpoint_label": "claim boundary",
            "reconstructed_boundary": "It may claim refs are ready, not that a customer-ready message body exists.",
            "evidence_strength": "strong",
            "raw_answer_included": False,
        },
        {
            "checkpoint_id": "evidence_refs",
            "checkpoint_label": "required evidence refs",
            "reconstructed_boundary": "Product Loop, Dual Loop, Delivery Trust receipt, CustomerHandoffPackage, and Delivery Trust Case refs must match.",
            "evidence_strength": "strong",
            "raw_answer_included": False,
        },
        {
            "checkpoint_id": "blocked_effects",
            "checkpoint_label": "blocked effects",
            "reconstructed_boundary": "Customer sends, source mutation, production mutation, external publication, model calls, and secrets remain blocked.",
            "evidence_strength": "strong",
            "raw_answer_included": False,
        },
    ]
    reconstruction = {
        **_base(RECONSTRUCTION_SCHEMA_VERSION),
        "reconstruction_id": f"patch-proposal-follow-up-boundary-reconstruction-{case_id}",
        "case_id": case_id,
        "source_type": source_type,
        "active_checkpoint_count": len(checkpoints),
        "strong_evidence_count": len(checkpoints),
        "passive_attention_only": False,
        "checkpoints": checkpoints,
        "model_calls_performed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_reconstruction(reconstruction)


def validate_reconstruction(reconstruction: Mapping[str, Any]) -> dict[str, Any]:
    if reconstruction.get("schema_version") != RECONSTRUCTION_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("reconstruction schema_version drifted")
    _validate_privacy(reconstruction, label=RECONSTRUCTION_SCHEMA_VERSION)
    source_type = reconstruction.get("source_type")
    if source_type not in ALLOWED_RECONSTRUCTION_SOURCES:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("unsupported reconstruction source")
    if reconstruction.get("passive_attention_only") is not False:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("passive attention is insufficient")
    if reconstruction.get("active_checkpoint_count") != len(REQUIRED_CHECKPOINT_IDS):
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("active checkpoint count drifted")
    if reconstruction.get("strong_evidence_count") != len(REQUIRED_CHECKPOINT_IDS):
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("strong evidence count drifted")
    checkpoints = reconstruction.get("checkpoints")
    if not isinstance(checkpoints, list):
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("reconstruction checkpoints must be a list")
    checkpoint_ids = set()
    for item in checkpoints:
        if not isinstance(item, Mapping):
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("reconstruction checkpoint must be an object")
        if item.get("raw_answer_included") is not False:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("checkpoint must not include raw answers")
        if item.get("evidence_strength") != "strong":
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("checkpoint evidence must be strong")
        checkpoint_ids.add(str(item.get("checkpoint_id")))
    if checkpoint_ids != REQUIRED_CHECKPOINT_IDS:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("required reconstruction checkpoints missing")
    return dict(reconstruction)


def _validate_bridge_source(
    bridge_receipt: Mapping[str, Any] | None,
    handoff_refs: Mapping[str, Any] | None,
    reconstruction: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    receipt = None
    refs = None
    active = None

    if bridge_receipt is None:
        reasons.append("bridge_receipt_missing")
    else:
        try:
            receipt = case_bridge.validate_bridge_receipt(bridge_receipt)
        except Exception:
            reasons.append("bridge_receipt_invalid")

    if handoff_refs is None:
        reasons.append("handoff_refs_missing")
    else:
        try:
            refs = case_bridge.validate_handoff_refs(handoff_refs)
        except Exception:
            reasons.append("handoff_refs_invalid")

    if reconstruction is None:
        reasons.append("active_reconstruction_missing")
    else:
        try:
            active = validate_reconstruction(reconstruction)
        except Exception as exc:  # noqa: BLE001 - normalized to deterministic reasons below.
            message = str(exc)
            if "passive attention" in message:
                reasons.append("passive_reconstruction_rejected")
            elif "unsupported reconstruction source" in message:
                reasons.append("unsupported_reconstruction_source")
            else:
                reasons.append("active_reconstruction_invalid")

    if receipt is not None:
        if receipt.get("status") != ALLOWED_SOURCE_STATUS:
            reasons.append("bridge_receipt_not_ready")
        if refs is not None and receipt.get("handoff_refs") != refs:
            reasons.append("handoff_refs_mismatch")

    if refs is not None:
        source_kinds = {str(item.get("kind")) for item in refs.get("source_evidence_refs", []) if isinstance(item, Mapping)}
        delivery_kinds = {str(item.get("kind")) for item in refs.get("delivery_trust_refs", []) if isinstance(item, Mapping)}
        if "product-loop-run" not in source_kinds:
            reasons.append("product_loop_ref_missing")
        if not REQUIRED_DUAL_LOOP_KINDS.issubset(source_kinds):
            reasons.append("dual_loop_ref_missing")
        if not REQUIRED_DELIVERY_TRUST_KINDS.issubset(delivery_kinds):
            reasons.append("delivery_trust_case_ref_missing")

    return receipt, refs, active, list(dict.fromkeys(reasons))


def _build_envelope_refs(
    *,
    case_id: str,
    bridge_receipt: Mapping[str, Any],
    handoff_refs: Mapping[str, Any],
    reconstruction: Mapping[str, Any],
) -> dict[str, Any]:
    envelope_stub = {
        "schema_version": "controlled-customer-follow-up-envelope-v1",
        "envelope_id": f"patch-proposal-controlled-follow-up-envelope-{case_id}",
        "case_id": case_id,
        "source_bridge_receipt_hash": artifact_hash(bridge_receipt),
        "source_handoff_refs_hash": artifact_hash(handoff_refs),
        "source_reconstruction_hash": artifact_hash(reconstruction),
        "raw_follow_up_body_included": False,
        "automatic_customer_send_performed": False,
        "customer_visible_send_performed": False,
        "customer_visible_follow_up_performed": False,
        "source_mutation_performed": False,
        "production_mutation_performed": False,
        "external_publication_performed": False,
        "model_calls_performed": False,
    }
    refs = {
        **_base(ENVELOPE_REFS_SCHEMA_VERSION),
        "case_id": case_id,
        "source_bridge_receipt_ref": _artifact_ref(
            "patch-proposal-delivery-trust-case-bridge-receipt",
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge/{_source_case_id(case_id)}/patch-proposal-controlled-follow-up-feedback-delivery-trust-case-bridge-receipt.json",
            bridge_receipt,
        ),
        "source_handoff_refs_ref": _artifact_ref(
            "patch-proposal-delivery-trust-case-handoff-refs",
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge/{_source_case_id(case_id)}/patch-proposal-controlled-follow-up-feedback-delivery-trust-case-handoff-refs.json",
            handoff_refs,
        ),
        "active_reconstruction_ref": _artifact_ref(
            "patch-proposal-follow-up-boundary-reconstruction",
            "patch-proposal-follow-up-feedback-boundary-reconstruction.json",
            reconstruction,
        ),
        "source_evidence_refs": list(handoff_refs["source_evidence_refs"]),
        "delivery_trust_refs": list(handoff_refs["delivery_trust_refs"]),
        "follow_up_envelope_ref": _artifact_ref(
            "controlled-customer-follow-up-envelope",
            "controlled-customer-follow-up-envelope.json",
            envelope_stub,
        ),
        "harness_summary": {
            "status": "ready_for_controlled_follow_up_envelope_refs",
            "decision": "prepare_metadata_only_follow_up_envelope_refs",
            "active_reconstruction_source": reconstruction["source_type"],
            "active_checkpoint_count": reconstruction["active_checkpoint_count"],
            "raw_follow_up_body_included": False,
            "automatic_customer_send_performed": False,
            "customer_visible_send_performed": False,
            "customer_visible_follow_up_performed": False,
            "source_mutation_performed": False,
            "production_mutation_performed": False,
            "external_publication_performed": False,
            "model_calls_performed": False,
        },
        "effect_boundary": _effect_boundary(envelope_prepared=True),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_envelope_refs(refs)


def validate_envelope_refs(refs: Mapping[str, Any]) -> dict[str, Any]:
    if refs.get("schema_version") != ENVELOPE_REFS_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("envelope refs schema_version drifted")
    _validate_privacy(refs, label=ENVELOPE_REFS_SCHEMA_VERSION)
    _validate_effect_boundary(refs, label=ENVELOPE_REFS_SCHEMA_VERSION)
    for key in ("source_bridge_receipt_ref", "source_handoff_refs_ref", "active_reconstruction_ref", "follow_up_envelope_ref"):
        ref = _require_object(refs, key, label=ENVELOPE_REFS_SCHEMA_VERSION)
        if ref.get("raw_body_included") is not False:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"{key} must not include raw body")
    for key in ("source_evidence_refs", "delivery_trust_refs"):
        values = refs.get(key)
        if not isinstance(values, list) or not values:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"envelope refs missing {key}")
        for item in values:
            if not isinstance(item, Mapping):
                raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"{key} item must be object")
            if item.get("raw_body_included") is not False:
                raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"{key} must not include raw bodies")
    summary = _require_object(refs, "harness_summary", label=ENVELOPE_REFS_SCHEMA_VERSION)
    for key in (
        "raw_follow_up_body_included",
        "automatic_customer_send_performed",
        "customer_visible_send_performed",
        "customer_visible_follow_up_performed",
        "source_mutation_performed",
        "production_mutation_performed",
        "external_publication_performed",
        "model_calls_performed",
    ):
        if summary.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"harness_summary.{key} must be false")
    if summary.get("status") != "ready_for_controlled_follow_up_envelope_refs":
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("envelope refs status drifted")
    return dict(refs)


def build_boundary_receipt(
    case_id: str,
    *,
    bridge_receipt: Mapping[str, Any] | None = None,
    handoff_refs: Mapping[str, Any] | None = None,
    reconstruction: Mapping[str, Any] | None = None,
    raw_follow_up_body_attached: bool = False,
    automatic_customer_send_requested: bool = False,
    customer_visible_send_requested: bool = False,
    customer_visible_follow_up_requested: bool = False,
    source_mutation_requested: bool = False,
    production_mutation_requested: bool = False,
    external_publication_requested: bool = False,
    model_call_requested: bool = False,
    secret_attached: bool = False,
    model_credential_attached: bool = False,
) -> dict[str, Any]:
    receipt, refs, active, reasons = _validate_bridge_source(bridge_receipt, handoff_refs, reconstruction)
    for flag, reason in (
        (raw_follow_up_body_attached, "raw_follow_up_body_rejected"),
        (automatic_customer_send_requested, "automatic_customer_send_rejected"),
        (customer_visible_send_requested, "customer_visible_send_rejected"),
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

    envelope_refs = None
    gate_error = None
    if not reasons and receipt and refs and active:
        try:
            envelope_refs = _build_envelope_refs(
                case_id=case_id,
                bridge_receipt=receipt,
                handoff_refs=refs,
                reconstruction=active,
            )
        except Exception as exc:  # noqa: BLE001 - converted to metadata-only code.
            gate_error = str(type(exc).__name__)
            reasons.append("follow_up_envelope_refs_blocked")

    ready = envelope_refs is not None and not reasons
    source_hash = artifact_hash(receipt) if receipt else None
    active_hash = artifact_hash(active) if active else None
    boundary_receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "boundary_receipt_id": (
            f"patch-proposal-controlled-follow-up-boundary-{source_hash[:16]}"
            if source_hash
            else f"patch-proposal-controlled-follow-up-boundary-blocked-{case_id}"
        ),
        "case_id": case_id,
        "source_bridge_schema_version": case_bridge.RECEIPT_SCHEMA_VERSION,
        "source_bridge_receipt_id": receipt.get("bridge_receipt_id") if receipt else None,
        "source_bridge_receipt_hash": source_hash,
        "active_reconstruction_schema_version": RECONSTRUCTION_SCHEMA_VERSION,
        "active_reconstruction_id": active.get("reconstruction_id") if active else None,
        "active_reconstruction_hash": active_hash,
        "status": "follow_up_envelope_refs_ready" if ready else "blocked",
        "decision": (
            "prepare_metadata_only_follow_up_envelope_refs"
            if ready
            else "block_controlled_follow_up_boundary"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "bridge_receipt_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge/"
                f"{_source_case_id(case_id)}/patch-proposal-controlled-follow-up-feedback-delivery-trust-case-bridge-receipt.json"
            ),
            "handoff_refs_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge/"
                f"{_source_case_id(case_id)}/patch-proposal-controlled-follow-up-feedback-delivery-trust-case-handoff-refs.json"
            ),
            "bridge_receipt_body_included": False,
            "handoff_refs_body_included": False,
            "active_reconstruction_body_included": False,
        },
        "harness_policy": {
            "source_bridge_status_required": ALLOWED_SOURCE_STATUS,
            "product_loop_ref_required": True,
            "dual_loop_ref_required": True,
            "delivery_trust_case_ref_required": True,
            "active_operator_or_host_platform_agent_reconstruction_required": True,
            "passive_attention_rejected": True,
            "emit_refs_only": True,
            "raw_follow_up_body_allowed": False,
            "automatic_customer_send_allowed": False,
            "customer_visible_send_allowed": False,
            "customer_visible_follow_up_allowed": False,
            "source_mutation_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "model_call_allowed": False,
        },
        "envelope_refs": envelope_refs,
        "harness_error_code": gate_error,
        "requested_actions": {
            "raw_follow_up_body_attached": raw_follow_up_body_attached,
            "automatic_customer_send_requested": automatic_customer_send_requested,
            "customer_visible_send_requested": customer_visible_send_requested,
            "customer_visible_follow_up_requested": customer_visible_follow_up_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "external_publication_requested": external_publication_requested,
            "model_call_requested": model_call_requested,
            "secret_attached": secret_attached,
            "model_credential_attached": model_credential_attached,
        },
        "effect_boundary": _effect_boundary(envelope_prepared=ready),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_boundary_receipt(boundary_receipt)


def validate_boundary_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    _validate_effect_boundary(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    decision = receipt.get("decision")
    reasons = receipt.get("blocked_reasons")
    if status not in {"follow_up_envelope_refs_ready", "blocked"}:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("boundary receipt status is invalid")
    if not isinstance(reasons, list):
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("boundary receipt blocked_reasons must be a list")
    refs = receipt.get("envelope_refs")
    if status == "follow_up_envelope_refs_ready":
        if decision != "prepare_metadata_only_follow_up_envelope_refs":
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("ready receipt decision drifted")
        if reasons:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("ready receipt must not include blocked reasons")
        if not isinstance(refs, Mapping):
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("ready receipt must include envelope refs")
        validate_envelope_refs(refs)
    else:
        if decision != "block_controlled_follow_up_boundary":
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("blocked receipt decision drifted")
        if not reasons:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("blocked receipt must include reasons")
        if refs is not None:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("blocked receipt must not include envelope refs")
    policy = _require_object(receipt, "harness_policy", label=RECEIPT_SCHEMA_VERSION)
    for key in (
        "raw_follow_up_body_allowed",
        "automatic_customer_send_allowed",
        "customer_visible_send_allowed",
        "customer_visible_follow_up_allowed",
        "source_mutation_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
        "model_call_allowed",
    ):
        if policy.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"harness_policy.{key} must be false")
    if policy.get("emit_refs_only") is not True:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError("boundary gate must emit refs only")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpFeedbackBoundaryGateError(f"Unknown case id: {case_id}")
    receipt = source_bridge_receipt(case_id)
    refs = source_handoff_refs(case_id)
    reconstruction = default_reconstruction(case_id)

    if case_id == "blocked-missing-bridge-receipt":
        receipt = None
    if case_id == "blocked-invalid-bridge-receipt" and receipt is not None:
        receipt = copy.deepcopy(receipt)
        receipt["schema_version"] = "invalid-bridge-receipt"
    if case_id == "blocked-missing-handoff-refs":
        refs = None
    if case_id == "blocked-handoff-refs-mismatch" and refs is not None:
        refs = copy.deepcopy(refs)
        refs["case_id"] = "mismatched-handoff-refs"
    if case_id == "blocked-missing-reconstruction":
        reconstruction = None
    if case_id == "blocked-passive-reconstruction" and reconstruction is not None:
        reconstruction = copy.deepcopy(reconstruction)
        reconstruction["passive_attention_only"] = True
        reconstruction["active_checkpoint_count"] = 0
        reconstruction["strong_evidence_count"] = 0
    if case_id == "blocked-unsupported-reconstruction-source" and reconstruction is not None:
        reconstruction = copy.deepcopy(reconstruction)
        reconstruction["source_type"] = "ai_review_only"
    if case_id == "blocked-missing-product-loop-ref" and refs is not None:
        refs = copy.deepcopy(refs)
        refs["source_evidence_refs"] = [
            item for item in refs["source_evidence_refs"] if item.get("kind") != "product-loop-run"
        ]
    if case_id == "blocked-missing-dual-loop-ref" and refs is not None:
        refs = copy.deepcopy(refs)
        refs["source_evidence_refs"] = [
            item for item in refs["source_evidence_refs"] if item.get("kind") != "sandbox-receipt"
        ]
    if case_id == "blocked-missing-delivery-trust-case-ref" and refs is not None:
        refs = copy.deepcopy(refs)
        refs["delivery_trust_refs"] = [
            item for item in refs["delivery_trust_refs"] if item.get("kind") != "delivery-trust-case"
        ]

    boundary_receipt = build_boundary_receipt(
        case_id,
        bridge_receipt=receipt,
        handoff_refs=refs,
        reconstruction=reconstruction,
        raw_follow_up_body_attached=case_id == "blocked-raw-follow-up-body",
        automatic_customer_send_requested=case_id == "blocked-automatic-customer-send",
        customer_visible_follow_up_requested=case_id == "blocked-customer-visible-follow-up",
        source_mutation_requested=case_id == "blocked-source-mutation",
        production_mutation_requested=case_id == "blocked-production-mutation",
        external_publication_requested=case_id == "blocked-external-publication",
        model_call_requested=case_id == "blocked-model-call",
        secret_attached=case_id == "blocked-secret",
        model_credential_attached=case_id == "blocked-model-credential",
    )
    artifacts = {"patch-proposal-controlled-follow-up-feedback-boundary-receipt.json": boundary_receipt}
    if isinstance(reconstruction, Mapping):
        artifacts["patch-proposal-follow-up-feedback-boundary-reconstruction.json"] = dict(reconstruction)
    envelope_refs = boundary_receipt.get("envelope_refs")
    if isinstance(envelope_refs, Mapping):
        artifacts["patch-proposal-controlled-follow-up-feedback-envelope-refs.json"] = validate_envelope_refs(envelope_refs)
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_boundary_receipt(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-boundary-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "envelope_refs_created": receipt["envelope_refs"] is not None,
            }
        )
    ready_count = sum(1 for row in case_reports if row["status"] == "follow_up_envelope_refs_ready")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove Patch Proposal Delivery Trust case/handoff refs can prepare only metadata-only "
            "customer follow-up envelope refs after active operator or host-platform Agent boundary "
            "reconstruction, while customer sends and irreversible effects remain blocked."
        ),
        "case_reports": case_reports,
        "boundary_matrix": {
            "ready_follow_up_envelope_ref_sets": ready_count,
            "blocked_follow_up_transitions": blocked_count,
            "raw_follow_up_bodies": 0,
            "automatic_customer_sends": 0,
            "customer_visible_sends": 0,
            "customer_visible_follow_ups": 0,
            "source_mutations": 0,
            "production_mutations": 0,
            "external_publications": 0,
            "model_calls": 0,
        },
        "boundary_rules": {
            "delivery_trust_case_bridge_receipt_required": True,
            "delivery_trust_case_handoff_refs_required": True,
            "product_loop_ref_required": True,
            "dual_loop_ref_required": True,
            "delivery_trust_case_ref_required": True,
            "active_operator_or_host_platform_agent_reconstruction_required": True,
            "passive_attention_rejected": True,
            "emit_refs_only": True,
            "metadata_only": True,
            "raw_follow_up_body_blocked": True,
            "automatic_customer_send_blocked": True,
            "customer_visible_send_blocked": True,
            "customer_visible_follow_up_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "external_publication_blocked": True,
            "model_calls_blocked": True,
        },
        "effect_boundary": _effect_boundary(envelope_prepared=True),
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
    parser.add_argument("--bridge-receipt", type=Path, help="Build from a Delivery Trust Case Bridge receipt.")
    parser.add_argument("--handoff-refs", type=Path, help="Handoff refs JSON for custom boundary builds.")
    parser.add_argument("--reconstruction", type=Path, help="Active follow-up boundary reconstruction JSON.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.bridge_receipt:
        if not args.handoff_refs or not args.reconstruction:
            raise SystemExit("--handoff-refs and --reconstruction are required with --bridge-receipt")
        receipt = build_boundary_receipt(
            "custom",
            bridge_receipt=load_json(args.bridge_receipt),
            handoff_refs=load_json(args.handoff_refs),
            reconstruction=load_json(args.reconstruction),
        )
        selected: dict[str, dict[str, dict[str, Any]]] = {
            "custom": {"patch-proposal-controlled-follow-up-feedback-boundary-receipt.json": receipt}
        }
        envelope_refs = receipt.get("envelope_refs")
        if isinstance(envelope_refs, Mapping):
            selected["custom"]["patch-proposal-controlled-follow-up-feedback-envelope-refs.json"] = validate_envelope_refs(
                envelope_refs
            )
    else:
        cases = build_all_case_artifacts()
        selected = cases if args.case == "all" else {args.case: cases[args.case]}

    write_artifacts(args.output_dir, selected)
    print(
        dump_json(
            {
                "schema_version": "patch-proposal-controlled-follow-up-boundary-gate-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "ready_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts["patch-proposal-controlled-follow-up-feedback-boundary-receipt.json"]["status"]
                    == "follow_up_envelope_refs_ready"
                ),
                "blocked_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts["patch-proposal-controlled-follow-up-feedback-boundary-receipt.json"]["status"] == "blocked"
                ),
                "model_calls_performed": False,
                "raw_follow_up_body_included": False,
                "customer_visible_send_performed": False,
                "source_mutation_performed": False,
                "production_mutation_performed": False,
                "external_publication_performed": False,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
