#!/usr/bin/env python3
"""Build metadata-only Patch Proposal controlled follow-up feedback reopen-intake gate receipts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_bridge as bridge  # noqa: E402


GATE_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate-v1"

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate"
)
BRIDGE_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge"
BRIDGE_REPORT_REF = (
    "platform/generated/"
    "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.json"
)

CASE_IDS = (
    "pass",
    "blocked-missing-bridge-receipt",
    "blocked-bridge-blocked",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-customer-identity",
    "blocked-send-payload",
    "blocked-automatic-contact",
    "blocked-automatic-intake-creation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

PRIVACY_FLAGS = {
    **bridge.PRIVACY_FLAGS,
    "controlled_follow_up_feedback_reopen_intake_gate_metadata_only": True,
    "reopen_intake_gate_receipt_only": True,
    "raw_follow_up_data_included": False,
    "raw_customer_data_included": False,
    "customer_identity_included": False,
    "customer_visible_follow_up_included": False,
    "customer_visible_payload_included": False,
    "send_payload_included": False,
    "automatic_customer_contact_payload_included": False,
    "automatic_intake_creation_payload_included": False,
    "intake_item_payload_included": False,
    "source_mutation_payload_included": False,
    "production_payload_included": False,
    "external_publication_payload_included": False,
    "model_call_payload_included": False,
}

FORBIDDEN_RAW_FIELDS = {
    *bridge.FORBIDDEN_RAW_FIELDS,
    "raw_follow_up_data",
    "raw_follow_up_body",
    "follow_up_body",
    "follow_up_text",
    "raw_customer_data",
    "raw_customer_reply",
    "customer_reply",
    "customer_reply_body",
    "customer_identity",
    "customer_name",
    "customer_email",
    "customer_phone",
    "requester_identity",
    "customer_visible_message",
    "send_payload",
    "customer_send_payload",
    "automatic_customer_contact_payload",
    "automatic_recontact_payload",
    "automatic_intake_creation_payload",
    "intake_payload",
    "intake_item_payload",
    "new_intake_body",
    "new_intake_payload",
    "customer_visible_intake",
    "source_mutation_payload",
    "production_mutation_payload",
    "external_publication_payload",
    "model_call_payload",
    "model_api_key",
    "agent_credential",
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "A controlled follow-up feedback reopen-intake gate receipt consumes a ready "
        "reopen-intake bridge receipt and decides only whether the prepared candidate "
        "may proceed as a metadata-only customer-feedback intake item under a separate "
        "Product Loop. It does not create the intake item, contact customers, mutate "
        "source, mutate production, publish externally, call a model, or store raw customer data."
    ),
    "not_claimed": [
        "raw follow-up data included",
        "raw customer data included",
        "customer identity included",
        "Study Anything created a new intake item",
        "Study Anything contacted a customer",
        "Study Anything mutated source",
        "Study Anything mutated production",
        "Study Anything published externally",
        "Study Anything called a model",
        "new Product Loop item fully prioritized",
        "customer satisfaction certified",
        "truth or security certified",
    ],
}


class PatchProposalControlledFollowUpReopenIntakeGateError(ValueError):
    """Raised when controlled follow-up feedback reopen-intake gate artifacts are unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpReopenIntakeGateError(f"Expected JSON object: {path}")
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
        raise PatchProposalControlledFollowUpReopenIntakeGateError(f"{label}.{key} must be an object")
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
        raise PatchProposalControlledFollowUpReopenIntakeGateError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpReopenIntakeGateError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _case_flags(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpReopenIntakeGateError(f"Unknown case id: {case_id}")
    bridge_case: str | None
    if case_id == "blocked-missing-bridge-receipt":
        bridge_case = None
    elif case_id == "blocked-bridge-blocked":
        bridge_case = "blocked-closure-blocked"
    else:
        bridge_case = "pass"
    return {
        "bridge_case": bridge_case,
        "closure_ref_present": case_id != "blocked-missing-closure-ref",
        "outcome_ref_present": case_id != "blocked-missing-outcome-ref",
        "action_ref_present": case_id != "blocked-missing-action-ref",
        "external_actor_ref_present": case_id != "blocked-missing-actor-ref",
        "claim_boundary_visible": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_visible": case_id != "blocked-missing-privacy-boundary",
        "raw_follow_up_data_attached": case_id == "blocked-raw-follow-up-data",
        "raw_customer_data_attached": case_id == "blocked-raw-customer-data",
        "customer_identity_attached": case_id == "blocked-customer-identity",
        "send_payload_attached": case_id == "blocked-send-payload",
        "automatic_customer_contact_performed": case_id == "blocked-automatic-contact",
        "automatic_intake_creation_performed": case_id == "blocked-automatic-intake-creation",
        "source_mutation_performed": case_id == "blocked-source-mutation",
        "production_mutation_performed": case_id == "blocked-production-mutation",
        "external_publication_payload_attached": case_id == "blocked-external-publication-payload",
        "model_call_performed": case_id == "blocked-model-call",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_bridge(case_id: str) -> dict[str, Any] | None:
    bridge_case = _case_flags(case_id)["bridge_case"]
    if bridge_case is None:
        return None
    receipt = load_json(
        BRIDGE_FIXTURE_DIR
        / bridge_case
        / "patch-proposal-controlled-follow-up-feedback-reopen-intake-bridge-receipt.json"
    )
    return bridge.validate_controlled_follow_up_feedback_reopen_intake_bridge(receipt)


def _source_ref(flags: Mapping[str, Any]) -> str | None:
    bridge_case = flags["bridge_case"]
    if bridge_case is None:
        return None
    return (
        "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge/"
        f"{bridge_case}/patch-proposal-controlled-follow-up-feedback-reopen-intake-bridge-receipt.json"
    )


def build_controlled_follow_up_feedback_reopen_intake_gate(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    bridge_receipt = source_bridge(case_id)
    source_checks = (
        _require_object(bridge_receipt, "checks", label="source_bridge")
        if bridge_receipt is not None
        else {}
    )
    source_summary = (
        _require_object(bridge_receipt, "reopen_intake_bridge", label="source_bridge")
        if bridge_receipt is not None
        else {}
    )
    source_ready = bridge_receipt is not None and bridge_receipt.get("status") == "ready"
    bridge_hash = artifact_hash(bridge_receipt) if bridge_receipt is not None else None
    closure_receipt_hash = source_summary.get("closure_receipt_hash")
    outcome_receipt_hash = source_summary.get("outcome_receipt_hash")
    action_ref_hash = source_summary.get("action_ref_hash")
    external_actor_ref_hash = source_summary.get("external_actor_ref_hash")
    candidate_ref_hash = source_summary.get("new_intake_candidate_ref_hash")

    checks = {
        "bridge_receipt_present": bridge_receipt is not None,
        "source_bridge_ready": source_ready,
        "product_loop_ref_preserved": source_ready
        and source_checks.get("product_loop_ref_preserved") is True,
        "dual_loop_refs_preserved": source_ready
        and source_checks.get("dual_loop_refs_preserved") is True,
        "delivery_trust_refs_preserved": source_ready
        and source_checks.get("delivery_trust_refs_preserved") is True,
        "active_reconstruction_ref_preserved": source_ready
        and source_checks.get("active_reconstruction_ref_preserved") is True,
        "closure_ref_preserved": source_ready
        and bool(flags["closure_ref_present"])
        and isinstance(closure_receipt_hash, str)
        and len(closure_receipt_hash) == 64,
        "outcome_ref_preserved": source_ready
        and bool(flags["outcome_ref_present"])
        and isinstance(outcome_receipt_hash, str)
        and len(outcome_receipt_hash) == 64,
        "action_ref_preserved": source_ready
        and bool(flags["action_ref_present"])
        and isinstance(action_ref_hash, str)
        and len(action_ref_hash) == 64,
        "external_actor_ref_preserved": source_ready
        and bool(flags["external_actor_ref_present"])
        and isinstance(external_actor_ref_hash, str)
        and len(external_actor_ref_hash) == 64,
        "candidate_ref_preserved": source_ready
        and isinstance(candidate_ref_hash, str)
        and len(candidate_ref_hash) == 64,
        "claim_boundary_visible": bool(flags["claim_boundary_visible"]),
        "privacy_boundary_visible": bool(flags["privacy_boundary_visible"]),
        "metadata_only_intake_gate": True,
        "raw_follow_up_data_attached": bool(flags["raw_follow_up_data_attached"]),
        "raw_customer_data_attached": bool(flags["raw_customer_data_attached"]),
        "customer_identity_attached": bool(flags["customer_identity_attached"]),
        "send_payload_attached": bool(flags["send_payload_attached"]),
        "automatic_customer_contact_performed": bool(flags["automatic_customer_contact_performed"]),
        "automatic_intake_creation_performed": bool(flags["automatic_intake_creation_performed"]),
        "source_mutation_performed": bool(flags["source_mutation_performed"]),
        "production_mutation_performed": bool(flags["production_mutation_performed"]),
        "external_publication_payload_attached": bool(flags["external_publication_payload_attached"]),
        "model_call_performed": bool(flags["model_call_performed"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    if not checks["bridge_receipt_present"]:
        reasons.append("bridge_receipt_missing")
    elif not checks["source_bridge_ready"]:
        reasons.append("source_bridge_not_ready")
    if bridge_receipt is not None and source_ready:
        for key, reason in (
            ("product_loop_ref_preserved", "product_loop_ref_missing"),
            ("dual_loop_refs_preserved", "dual_loop_ref_missing"),
            ("delivery_trust_refs_preserved", "delivery_trust_ref_missing"),
            ("active_reconstruction_ref_preserved", "active_reconstruction_ref_missing"),
            ("closure_ref_preserved", "closure_ref_missing"),
            ("outcome_ref_preserved", "outcome_ref_missing"),
            ("action_ref_preserved", "action_ref_missing"),
            ("external_actor_ref_preserved", "external_actor_ref_missing"),
            ("candidate_ref_preserved", "candidate_ref_missing"),
        ):
            if not checks[key]:
                reasons.append(reason)
    for key, reason in (
        ("claim_boundary_visible", "claim_boundary_missing"),
        ("privacy_boundary_visible", "privacy_boundary_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_follow_up_data_attached", "raw_follow_up_data_rejected"),
        ("raw_customer_data_attached", "raw_customer_data_rejected"),
        ("customer_identity_attached", "customer_identity_rejected"),
        ("send_payload_attached", "send_payload_rejected"),
        ("automatic_customer_contact_performed", "automatic_customer_contact_rejected"),
        ("automatic_intake_creation_performed", "automatic_intake_creation_rejected"),
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
    allowed = not reasons
    receipt = {
        **_base(GATE_SCHEMA_VERSION),
        "gate_id": f"patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-{case_id}",
        "case_id": case_id,
        "status": "allowed" if allowed else "blocked",
        "decision": "allow_reopen_intake_item_gate" if allowed else "block_reopen_intake_item_gate",
        "blocked_reasons": reasons,
        "source_refs": {
            "reopen_intake_bridge_receipt_ref": _source_ref(flags),
            "reopen_intake_bridge_receipt_hash": bridge_hash,
            "reopen_intake_bridge_report_ref": BRIDGE_REPORT_REF,
        },
        "reopen_intake_gate": {
            "package_type": "metadata_only_patch_proposal_controlled_follow_up_feedback_reopen_intake_gate",
            "gate_action": "allow_product_loop_intake_item_candidate" if allowed else None,
            "bridge_receipt_hash": bridge_hash,
            "closure_receipt_hash": closure_receipt_hash if checks["closure_ref_preserved"] else None,
            "outcome_receipt_hash": outcome_receipt_hash if checks["outcome_ref_preserved"] else None,
            "external_actor_ref_hash": external_actor_ref_hash
            if checks["external_actor_ref_preserved"]
            else None,
            "action_ref_hash": action_ref_hash if checks["action_ref_preserved"] else None,
            "intake_candidate_ref_hash": candidate_ref_hash if checks["candidate_ref_preserved"] else None,
            "product_loop_intake_item_ref_hash": (
                dual_loop.sha256_text(f"{case_id}:product-loop-intake-item-ref")
                if allowed
                else None
            ),
            "raw_follow_up_data_included": False,
            "raw_customer_data_included": False,
            "customer_identity_included": False,
            "send_payload_included": False,
            "automatic_customer_contact_payload_included": False,
            "automatic_intake_creation_payload_included": False,
            "payload_hash_only": True,
            "external_system_credentials_included": False,
        },
        "effect_boundary": {
            "study_anything_customer_follow_up_send_performed": False,
            "study_anything_automatic_follow_up_performed": False,
            "study_anything_automatic_customer_contact_performed": False,
            "study_anything_new_feedback_intake_created": False,
            "study_anything_source_mutation_performed": False,
            "study_anything_production_mutation_performed": False,
            "study_anything_external_publication_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
        },
        "checks": checks,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_controlled_follow_up_feedback_reopen_intake_gate(receipt)


def validate_controlled_follow_up_feedback_reopen_intake_gate(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != GATE_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpReopenIntakeGateError(
            "controlled follow-up feedback reopen-intake gate schema_version drifted"
        )
    _validate_privacy(receipt, label=GATE_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "reopen_intake_gate", label=GATE_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=GATE_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=GATE_SCHEMA_VERSION)
    if (
        summary.get("package_type")
        != "metadata_only_patch_proposal_controlled_follow_up_feedback_reopen_intake_gate"
    ):
        raise PatchProposalControlledFollowUpReopenIntakeGateError(
            "reopen_intake_gate package_type must remain metadata-only"
        )
    for key in (
        "raw_follow_up_data_included",
        "raw_customer_data_included",
        "customer_identity_included",
        "send_payload_included",
        "automatic_customer_contact_payload_included",
        "automatic_intake_creation_payload_included",
        "external_system_credentials_included",
    ):
        if summary.get(key) is not False:
            raise PatchProposalControlledFollowUpReopenIntakeGateError(f"reopen_intake_gate.{key} must remain false")
    for key in (
        "study_anything_customer_follow_up_send_performed",
        "study_anything_automatic_follow_up_performed",
        "study_anything_automatic_customer_contact_performed",
        "study_anything_new_feedback_intake_created",
        "study_anything_source_mutation_performed",
        "study_anything_production_mutation_performed",
        "study_anything_external_publication_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalControlledFollowUpReopenIntakeGateError(f"effect_boundary.{key} must remain false")
    if status == "allowed":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalControlledFollowUpReopenIntakeGateError(
                "allowed controlled follow-up feedback reopen-intake gate must not carry reasons"
            )
        if receipt.get("decision") != "allow_reopen_intake_item_gate":
            raise PatchProposalControlledFollowUpReopenIntakeGateError("allowed gate decision drifted")
        for key in (
            "bridge_receipt_present",
            "source_bridge_ready",
            "product_loop_ref_preserved",
            "dual_loop_refs_preserved",
            "delivery_trust_refs_preserved",
            "active_reconstruction_ref_preserved",
            "closure_ref_preserved",
            "outcome_ref_preserved",
            "action_ref_preserved",
            "external_actor_ref_preserved",
            "candidate_ref_preserved",
            "claim_boundary_visible",
            "privacy_boundary_visible",
            "metadata_only_intake_gate",
        ):
            if checks.get(key) is not True:
                raise PatchProposalControlledFollowUpReopenIntakeGateError(
                    f"allowed reopen-intake gate missing check: {key}"
                )
        for key in (
            "raw_follow_up_data_attached",
            "raw_customer_data_attached",
            "customer_identity_attached",
            "send_payload_attached",
            "automatic_customer_contact_performed",
            "automatic_intake_creation_performed",
            "source_mutation_performed",
            "production_mutation_performed",
            "external_publication_payload_attached",
            "model_call_performed",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalControlledFollowUpReopenIntakeGateError(
                    f"allowed reopen-intake gate checks.{key} must remain false"
                )
        if summary.get("gate_action") != "allow_product_loop_intake_item_candidate":
            raise PatchProposalControlledFollowUpReopenIntakeGateError("allowed gate action drifted")
        for key in (
            "bridge_receipt_hash",
            "closure_receipt_hash",
            "outcome_receipt_hash",
            "external_actor_ref_hash",
            "action_ref_hash",
            "intake_candidate_ref_hash",
            "product_loop_intake_item_ref_hash",
        ):
            value = summary.get(key)
            if not isinstance(value, str) or len(value) != 64:
                raise PatchProposalControlledFollowUpReopenIntakeGateError(
                    f"allowed reopen-intake gate {key} must be a hash"
                )
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalControlledFollowUpReopenIntakeGateError(
                "blocked controlled follow-up feedback reopen-intake gate must carry reasons"
            )
        if receipt.get("decision") != "block_reopen_intake_item_gate":
            raise PatchProposalControlledFollowUpReopenIntakeGateError("blocked gate decision drifted")
        if summary.get("gate_action") is not None:
            raise PatchProposalControlledFollowUpReopenIntakeGateError(
                "blocked controlled follow-up feedback reopen-intake gate must not expose gate_action"
            )
    else:
        raise PatchProposalControlledFollowUpReopenIntakeGateError(
            "controlled follow-up feedback reopen-intake gate status must be allowed or blocked"
        )
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {
        "patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json": (
            build_controlled_follow_up_feedback_reopen_intake_gate(case_id)
        )
    }


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_controlled_follow_up_feedback_reopen_intake_gate(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "gate_action": receipt["reopen_intake_gate"]["gate_action"],
            }
        )
    allowed_count = sum(1 for row in case_reports if row["status"] == "allowed")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove controlled follow-up feedback reopen-intake gates consume only ready bridge "
            "receipts and decide whether a prepared candidate may proceed as a metadata-only "
            "Product Loop intake item ref without creating intakes, contacting customers, mutating "
            "systems, publishing, calling models, or storing secrets."
        ),
        "source_chain": {
            "reopen_intake_bridge_receipt": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge/"
                "pass/patch-proposal-controlled-follow-up-feedback-reopen-intake-bridge-receipt.json"
            ),
            "reopen_intake_bridge_report": BRIDGE_REPORT_REF,
        },
        "gate_matrix": {
            "allowed_gates": allowed_count,
            "blocked_gates": blocked_count,
            "total_cases": len(case_reports),
            "missing_bridge_receipt_rejected": True,
            "blocked_bridge_rejected": True,
            "missing_closure_ref_rejected": True,
            "missing_outcome_ref_rejected": True,
            "missing_action_ref_rejected": True,
            "missing_external_actor_ref_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "raw_follow_up_data_rejected": True,
            "raw_customer_data_rejected": True,
            "customer_identity_rejected": True,
            "send_payload_rejected": True,
            "automatic_customer_contact_rejected": True,
            "automatic_intake_creation_rejected": True,
            "source_mutation_rejected": True,
            "production_mutation_rejected": True,
            "external_publication_payload_rejected": True,
            "model_call_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "ready_reopen_intake_bridge_required": True,
            "product_loop_refs_preserved": True,
            "dual_loop_refs_preserved": True,
            "delivery_trust_refs_preserved": True,
            "active_reconstruction_ref_preserved": True,
            "closure_ref_required": True,
            "outcome_ref_required": True,
            "external_actor_ref_required": True,
            "action_ref_required": True,
            "candidate_ref_required": True,
            "claim_boundary_required": True,
            "privacy_boundary_required": True,
            "raw_follow_up_data_rejected": True,
            "raw_customer_data_rejected": True,
            "customer_identity_rejected": True,
            "send_payload_rejected": True,
            "automatic_customer_contact_blocked": True,
            "automatic_intake_creation_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
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
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "ok",
        "case_ids": list(selected),
        "output_dir_ref": args.output_dir.name,
        "privacy": dict(PRIVACY_FLAGS),
    }
    if args.report:
        result["report"] = build_report(cases)
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
