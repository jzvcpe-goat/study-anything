#!/usr/bin/env python3
"""Bridge Patch Proposal feedback candidates into Delivery Trust Case refs.

This layer consumes the metadata-only
`patch-proposal-delivery-trust-case-candidate-v1` emitted by the Patch Proposal
Customer Feedback Delivery Trust Intake Gate. It then runs the existing
Delivery Trust Case assembly logic in local deterministic mode and emits only
metadata refs for the resulting Delivery Trust receipt, CustomerHandoffPackage,
and Delivery Trust Case.

It does not embed the customer handoff package body, send anything to a
customer, mutate source, mutate production, call models, store secrets, or
start a daemon.
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

from study_anything.core import (  # noqa: E402
    cbb_protocol,
    customer_handoff,
    delivery_trust,
    delivery_trust_case,
    dual_loop,
)
import patch_proposal_customer_feedback_delivery_trust_intake_gate as intake_gate  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-delivery-trust-case-bridge-receipt-v1"
HANDOFF_REFS_SCHEMA_VERSION = "patch-proposal-delivery-trust-case-handoff-refs-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-delivery-trust-case-bridge-v1"

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-delivery-trust-case-bridge"
)

PASS_CASE_IDS = intake_gate.PASS_CASE_IDS
CASE_IDS = (
    *PASS_CASE_IDS,
    "blocked-missing-candidate",
    "blocked-invalid-candidate",
    "blocked-missing-product-loop-run",
    "blocked-product-loop-hash-mismatch",
    "blocked-missing-dual-loop-evidence",
    "blocked-dual-loop-evidence-mismatch",
    "blocked-dual-loop-gate-blocked",
    "blocked-ai-review-only",
    "blocked-customer-visible-send",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_SOURCE_SCHEMA_VERSION = intake_gate.CANDIDATE_SCHEMA_VERSION
ALLOWED_SOURCE_BOUNDARY = intake_gate.ALLOWED_NEXT_BOUNDARY

PRIVACY_FLAGS = {
    **intake_gate.PRIVACY_FLAGS,
    "delivery_trust_case_bridge_metadata_only": True,
    "delivery_trust_case_body_included": False,
    "customer_handoff_package_body_included": False,
    "handoff_refs_only": True,
    "raw_customer_payload_included": False,
    "raw_sandbox_log_included": False,
    "raw_attention_trace_included": False,
}

PROHIBITED_EFFECTS = {
    "study_anything_customer_visible_send_performed": False,
    "study_anything_source_mutation_performed": False,
    "study_anything_production_mutation_performed": False,
    "study_anything_external_publication_performed": False,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
}

FORBIDDEN_RAW_FIELDS = {
    *intake_gate.FORBIDDEN_RAW_FIELDS,
    "raw_customer_payload",
    "raw_handoff_payload",
    "raw_delivery_case",
    "raw_delivery_case_body",
    "delivery_case_body",
    "customer_handoff_package",
    "customer_handoff_package_body",
    "delivery_trust_case",
    "delivery_trust_case_body",
    "customer_visible_send",
    "customer_visible_send_body",
    "customer_visible_reply",
    "source_mutation_payload",
    "production_payload",
    "model_api_key",
    "agent_credential",
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "A Patch Proposal Delivery Trust case candidate can be assembled into "
        "metadata-only Delivery Trust case and handoff refs only when the "
        "candidate, Product Loop run, controlled-failure evidence, attention "
        "reconstruction, and Dual Loop gate all match."
    ),
    "not_claimed": [
        "raw customer payload included",
        "customer-visible send performed",
        "source mutation allowed",
        "production mutation allowed",
        "external publication performed",
        "model call performed",
        "real customer delivery",
        "production deployment approval",
    ],
}


class PatchProposalDeliveryTrustCaseBridgeError(ValueError):
    """Raised when Patch Proposal Delivery Trust case bridge evidence is unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalDeliveryTrustCaseBridgeError(f"Expected JSON object: {path}")
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
        raise PatchProposalDeliveryTrustCaseBridgeError(f"{label}.{key} must be an object")
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
        raise PatchProposalDeliveryTrustCaseBridgeError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalDeliveryTrustCaseBridgeError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _effect_boundary(*, harness_invoked: bool) -> dict[str, Any]:
    return {
        "study_anything_delivery_trust_case_harness_invoked": harness_invoked,
        "study_anything_delivery_trust_receipt_created_as_metadata_artifact": harness_invoked,
        "study_anything_customer_handoff_package_created_as_metadata_artifact": harness_invoked,
        "study_anything_delivery_trust_case_created_as_metadata_artifact": harness_invoked,
        **PROHIBITED_EFFECTS,
    }


def _validate_effect_boundary(payload: Mapping[str, Any], *, label: str) -> None:
    effect = _require_object(payload, "effect_boundary", label=label)
    for key, expected in PROHIBITED_EFFECTS.items():
        if effect.get(key) is not expected:
            raise PatchProposalDeliveryTrustCaseBridgeError(
                f"{label}.effect_boundary.{key} must be {expected!r}"
            )
    status = payload.get("status")
    if status == "delivery_trust_case_refs_ready":
        for key in (
            "study_anything_delivery_trust_case_harness_invoked",
            "study_anything_delivery_trust_receipt_created_as_metadata_artifact",
            "study_anything_customer_handoff_package_created_as_metadata_artifact",
            "study_anything_delivery_trust_case_created_as_metadata_artifact",
        ):
            if effect.get(key) is not True:
                raise PatchProposalDeliveryTrustCaseBridgeError(
                    f"{label}.effect_boundary.{key} must be true for ready refs"
                )


def _artifact_ref(kind: str, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "kind": kind,
        "path": path,
        "schema_version": payload.get("schema_version"),
        "sha256": artifact_hash(payload),
        "raw_body_included": False,
    }
    for key in ("candidate_id", "run_id", "contract_id", "receipt_id", "summary_id", "gate_id", "case_id", "package_id"):
        value = payload.get(key)
        if isinstance(value, str):
            ref[key] = value
    return ref


def _source_case_id(case_id: str) -> str:
    return case_id if case_id in PASS_CASE_IDS else "pass-customer-signal"


def source_intake_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return intake_gate.build_case_artifacts(_source_case_id(case_id))


def source_candidate(case_id: str) -> dict[str, Any] | None:
    artifacts = source_intake_artifacts(case_id)
    candidate = artifacts.get("patch-proposal-delivery-trust-case-candidate.json")
    return intake_gate.validate_candidate(candidate) if isinstance(candidate, Mapping) else None


def source_product_loop_run(case_id: str) -> dict[str, Any] | None:
    return intake_gate.source_product_loop_run(_source_case_id(case_id))


def default_dual_loop_artifacts(*, within_budget: bool = True) -> dict[str, Any]:
    return intake_gate.default_dual_loop_artifacts(within_budget=within_budget, attention_present=True)


def _validate_candidate_source(
    candidate: Mapping[str, Any] | None,
    product_loop_run: Mapping[str, Any] | None,
    failure_contract: Mapping[str, Any] | None,
    sandbox_receipt: Mapping[str, Any] | None,
    attention_summary: Mapping[str, Any] | None,
    dual_loop_gate: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    reasons: list[str] = []
    candidate_valid = None
    run = None
    contract = None
    sandbox = None
    attention = None
    gate = None

    if candidate is None:
        reasons.append("candidate_missing")
    else:
        try:
            candidate_valid = intake_gate.validate_candidate(candidate)
        except Exception:
            reasons.append("candidate_invalid")

    if product_loop_run is None:
        reasons.append("product_loop_run_missing")
    else:
        try:
            run = intake_gate.validate_product_loop_run_source(product_loop_run)
        except Exception:
            reasons.append("product_loop_run_invalid")

    for label, value, validator, missing_reason, invalid_reason in (
        (
            "failure_contract",
            failure_contract,
            dual_loop.validate_failure_contract,
            "failure_contract_missing",
            "failure_contract_invalid",
        ),
        (
            "sandbox_receipt",
            sandbox_receipt,
            dual_loop.validate_sandbox_receipt,
            "sandbox_receipt_missing",
            "sandbox_receipt_invalid",
        ),
        (
            "attention_summary",
            attention_summary,
            dual_loop.validate_attention_summary,
            "attention_reconstruction_missing",
            "attention_reconstruction_invalid",
        ),
        (
            "dual_loop_gate",
            dual_loop_gate,
            dual_loop.validate_gate_receipt,
            "dual_loop_gate_missing",
            "dual_loop_gate_invalid",
        ),
    ):
        if value is None:
            reasons.append(missing_reason)
            continue
        try:
            validated = validator(value)
        except Exception:
            reasons.append(invalid_reason)
            continue
        if label == "failure_contract":
            contract = validated
        elif label == "sandbox_receipt":
            sandbox = validated
        elif label == "attention_summary":
            attention = validated
        elif label == "dual_loop_gate":
            gate = validated

    if candidate_valid is not None and run is not None:
        if candidate_valid.get("source_product_loop_run_hash") != artifact_hash(run):
            reasons.append("product_loop_run_hash_mismatch")
        if candidate_valid.get("source_product_loop_run_id") != run.get("run_id"):
            reasons.append("product_loop_run_id_mismatch")
        if candidate_valid.get("next_boundary") != ALLOWED_SOURCE_BOUNDARY:
            reasons.append("candidate_boundary_mismatch")

    if candidate_valid is not None and contract is not None and sandbox is not None and attention is not None and gate is not None:
        controlled = _require_object(candidate_valid, "controlled_failure_ref", label=ALLOWED_SOURCE_SCHEMA_VERSION)
        reconstruction = _require_object(
            candidate_valid,
            "attention_reconstruction_ref",
            label=ALLOWED_SOURCE_SCHEMA_VERSION,
        )
        gate_ref = _require_object(candidate_valid, "dual_loop_gate_ref", label=ALLOWED_SOURCE_SCHEMA_VERSION)
        expected_refs = {
            "failure_contract_hash": artifact_hash(contract),
            "failure_contract_id": contract["contract_id"],
            "sandbox_receipt_hash": artifact_hash(sandbox),
            "sandbox_receipt_id": sandbox["receipt_id"],
            "attention_summary_hash": artifact_hash(attention),
            "attention_summary_id": attention["summary_id"],
            "dual_loop_gate_hash": artifact_hash(gate),
            "dual_loop_gate_id": gate["gate_id"],
            "status": gate["status"],
            "decision": gate["decision"],
        }
        actual_refs = {
            "failure_contract_hash": controlled.get("failure_contract_hash"),
            "failure_contract_id": controlled.get("failure_contract_id"),
            "sandbox_receipt_hash": controlled.get("sandbox_receipt_hash"),
            "sandbox_receipt_id": controlled.get("sandbox_receipt_id"),
            "attention_summary_hash": reconstruction.get("attention_summary_hash"),
            "attention_summary_id": reconstruction.get("attention_summary_id"),
            "dual_loop_gate_hash": gate_ref.get("dual_loop_gate_hash"),
            "dual_loop_gate_id": gate_ref.get("dual_loop_gate_id"),
            "status": gate_ref.get("status"),
            "decision": gate_ref.get("decision"),
        }
        mismatched = [key for key, expected in expected_refs.items() if actual_refs.get(key) != expected]
        if mismatched:
            reasons.append("dual_loop_evidence_ref_mismatch")
        if gate.get("status") != "allowed":
            reasons.append("dual_loop_gate_blocked")
            reasons.extend(str(reason) for reason in gate.get("reasons", []))

    return candidate_valid, run, contract, sandbox, attention, gate, list(dict.fromkeys(reasons))


def _build_handoff_refs(
    *,
    case_id: str,
    candidate: Mapping[str, Any],
    product_loop_run: Mapping[str, Any],
    failure_contract: Mapping[str, Any],
    sandbox_receipt: Mapping[str, Any],
    attention_summary: Mapping[str, Any],
    dual_loop_gate: Mapping[str, Any],
) -> dict[str, Any]:
    delivery_receipt = delivery_trust.build_delivery_trust_receipt(
        failure_contract,
        sandbox_receipt,
        dual_loop_gate,
        attention_summary,
        receipt_id=f"patch-proposal-delivery-trust-receipt-{case_id}",
    )
    handoff_package = customer_handoff.build_customer_handoff_package(
        delivery_receipt,
        failure_contract,
        sandbox_receipt,
        attention_summary,
        dual_loop_gate,
        package_id=f"patch-proposal-customer-handoff-package-{case_id}",
    )
    case = delivery_trust_case.build_delivery_trust_case(
        product_loop_run,
        dual_loop_gate,
        delivery_receipt,
        handoff_package,
        case_id=f"patch-proposal-{case_id}",
    )
    refs = {
        **_base(HANDOFF_REFS_SCHEMA_VERSION),
        "case_id": case_id,
        "candidate_ref": _artifact_ref(
            "patch-proposal-delivery-trust-case-candidate",
            f"fixtures/patch-proposal-customer-feedback-delivery-trust-intake-gate/{case_id}/patch-proposal-delivery-trust-case-candidate.json",
            candidate,
        ),
        "source_evidence_refs": [
            _artifact_ref("product-loop-run", "product-loop-run.json", product_loop_run),
            _artifact_ref("failure-contract", "failure-contract.json", failure_contract),
            _artifact_ref("sandbox-receipt", "sandbox-receipt.json", sandbox_receipt),
            _artifact_ref("attention-reconstruction-summary", "attention-reconstruction-summary.json", attention_summary),
            _artifact_ref("dual-loop-gate-receipt", "dual-loop-gate-receipt.json", dual_loop_gate),
        ],
        "delivery_trust_refs": [
            _artifact_ref("delivery-trust-receipt", "delivery-trust-receipt.json", delivery_receipt),
            _artifact_ref("customer-handoff-package", "customer-handoff-package.json", handoff_package),
            _artifact_ref("delivery-trust-case", "delivery-trust-case.json", case),
        ],
        "harness_summary": {
            "implementation": "study_anything.core.delivery_trust_case.build_delivery_trust_case",
            "status": case["status"],
            "decision": case["decision"],
            "layer_statuses": dict(case["layer_statuses"]),
            "reasons": list(case["reasons"]),
            "customer_handoff_package_body_included": False,
            "delivery_trust_case_body_included": False,
            "customer_visible_send_performed": False,
        },
        "effect_boundary": _effect_boundary(harness_invoked=True),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_handoff_refs(refs)


def validate_handoff_refs(refs: Mapping[str, Any]) -> dict[str, Any]:
    if refs.get("schema_version") != HANDOFF_REFS_SCHEMA_VERSION:
        raise PatchProposalDeliveryTrustCaseBridgeError("handoff refs schema_version drifted")
    _validate_privacy(refs, label=HANDOFF_REFS_SCHEMA_VERSION)
    _validate_effect_boundary(refs, label=HANDOFF_REFS_SCHEMA_VERSION)
    candidate_ref = _require_object(refs, "candidate_ref", label=HANDOFF_REFS_SCHEMA_VERSION)
    if candidate_ref.get("raw_body_included") is not False:
        raise PatchProposalDeliveryTrustCaseBridgeError("candidate ref must not include raw body")
    for key in ("source_evidence_refs", "delivery_trust_refs"):
        values = refs.get(key)
        if not isinstance(values, list) or not values:
            raise PatchProposalDeliveryTrustCaseBridgeError(f"handoff refs missing {key}")
        for item in values:
            if not isinstance(item, Mapping):
                raise PatchProposalDeliveryTrustCaseBridgeError(f"{key} item must be object")
            if item.get("raw_body_included") is not False:
                raise PatchProposalDeliveryTrustCaseBridgeError(f"{key} must not include raw bodies")
    summary = _require_object(refs, "harness_summary", label=HANDOFF_REFS_SCHEMA_VERSION)
    if summary.get("status") != "ready_for_controlled_customer_handoff":
        raise PatchProposalDeliveryTrustCaseBridgeError("handoff refs require ready Delivery Trust Case")
    if summary.get("customer_visible_send_performed") is not False:
        raise PatchProposalDeliveryTrustCaseBridgeError("handoff refs must not send customers")
    return dict(refs)


def build_bridge_receipt(
    case_id: str,
    *,
    candidate: Mapping[str, Any] | None = None,
    product_loop_run: Mapping[str, Any] | None = None,
    failure_contract: Mapping[str, Any] | None = None,
    sandbox_receipt: Mapping[str, Any] | None = None,
    attention_summary: Mapping[str, Any] | None = None,
    dual_loop_gate: Mapping[str, Any] | None = None,
    customer_visible_send_requested: bool = False,
    source_mutation_requested: bool = False,
    production_mutation_requested: bool = False,
    secret_attached: bool = False,
    model_credential_attached: bool = False,
) -> dict[str, Any]:
    (
        candidate_valid,
        run,
        contract,
        sandbox,
        attention,
        gate,
        reasons,
    ) = _validate_candidate_source(
        candidate,
        product_loop_run,
        failure_contract,
        sandbox_receipt,
        attention_summary,
        dual_loop_gate,
    )
    for flag, reason in (
        (customer_visible_send_requested, "customer_visible_send_rejected"),
        (source_mutation_requested, "source_mutation_rejected"),
        (production_mutation_requested, "production_mutation_rejected"),
        (secret_attached, "secret_rejected"),
        (model_credential_attached, "model_credential_rejected"),
    ):
        if flag:
            reasons.append(reason)
    reasons = list(dict.fromkeys(reasons))

    handoff_refs = None
    bridge_error = None
    if not reasons and candidate_valid and run and contract and sandbox and attention and gate:
        try:
            handoff_refs = _build_handoff_refs(
                case_id=case_id,
                candidate=candidate_valid,
                product_loop_run=run,
                failure_contract=contract,
                sandbox_receipt=sandbox,
                attention_summary=attention,
                dual_loop_gate=gate,
            )
        except Exception as exc:  # noqa: BLE001 - converted to metadata-only code.
            bridge_error = str(type(exc).__name__)
            reasons.append("delivery_trust_case_harness_blocked")

    ready = handoff_refs is not None and not reasons
    candidate_hash = artifact_hash(candidate_valid) if candidate_valid else None
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "bridge_receipt_id": (
            f"patch-proposal-delivery-trust-case-bridge-{candidate_hash[:16]}"
            if candidate_hash
            else f"patch-proposal-delivery-trust-case-bridge-blocked-{case_id}"
        ),
        "case_id": case_id,
        "source_candidate_schema_version": ALLOWED_SOURCE_SCHEMA_VERSION,
        "source_candidate_id": candidate_valid.get("candidate_id") if candidate_valid else None,
        "source_candidate_hash": candidate_hash,
        "status": "delivery_trust_case_refs_ready" if ready else "blocked",
        "decision": (
            "emit_delivery_trust_case_handoff_refs"
            if ready
            else "block_patch_proposal_delivery_trust_case_bridge"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "candidate_ref": (
                f"fixtures/patch-proposal-customer-feedback-delivery-trust-intake-gate/"
                f"{_source_case_id(case_id)}/patch-proposal-delivery-trust-case-candidate.json"
            ),
            "candidate_body_included": False,
            "product_loop_run_body_included": False,
            "dual_loop_artifact_bodies_included": False,
        },
        "harness_policy": {
            "required_source_boundary": ALLOWED_SOURCE_BOUNDARY,
            "candidate_required": True,
            "product_loop_run_required": True,
            "controlled_failure_required": True,
            "attention_reconstruction_required": True,
            "dual_loop_gate_required": True,
            "delivery_trust_case_harness_allowed": ready,
            "emit_refs_only": True,
            "customer_visible_send_allowed": False,
            "source_mutation_allowed": False,
            "production_mutation_allowed": False,
            "model_call_allowed": False,
        },
        "handoff_refs": handoff_refs,
        "harness_error_code": bridge_error,
        "requested_actions": {
            "customer_visible_send_requested": customer_visible_send_requested,
            "source_mutation_requested": source_mutation_requested,
            "production_mutation_requested": production_mutation_requested,
            "secret_attached": secret_attached,
            "model_credential_attached": model_credential_attached,
        },
        "effect_boundary": _effect_boundary(harness_invoked=ready),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_bridge_receipt(receipt)


def validate_bridge_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalDeliveryTrustCaseBridgeError("receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    _validate_effect_boundary(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    decision = receipt.get("decision")
    reasons = receipt.get("blocked_reasons")
    if status not in {"delivery_trust_case_refs_ready", "blocked"}:
        raise PatchProposalDeliveryTrustCaseBridgeError("bridge receipt status is invalid")
    if not isinstance(reasons, list):
        raise PatchProposalDeliveryTrustCaseBridgeError("bridge receipt blocked_reasons must be a list")
    refs = receipt.get("handoff_refs")
    if status == "delivery_trust_case_refs_ready":
        if decision != "emit_delivery_trust_case_handoff_refs":
            raise PatchProposalDeliveryTrustCaseBridgeError("ready receipt decision drifted")
        if reasons:
            raise PatchProposalDeliveryTrustCaseBridgeError("ready receipt must not include blocked reasons")
        if not isinstance(refs, Mapping):
            raise PatchProposalDeliveryTrustCaseBridgeError("ready receipt must include handoff refs")
        validate_handoff_refs(refs)
    else:
        if decision != "block_patch_proposal_delivery_trust_case_bridge":
            raise PatchProposalDeliveryTrustCaseBridgeError("blocked receipt decision drifted")
        if not reasons:
            raise PatchProposalDeliveryTrustCaseBridgeError("blocked receipt must include reasons")
        if refs is not None:
            raise PatchProposalDeliveryTrustCaseBridgeError("blocked receipt must not include handoff refs")
    policy = _require_object(receipt, "harness_policy", label=RECEIPT_SCHEMA_VERSION)
    for key in (
        "customer_visible_send_allowed",
        "source_mutation_allowed",
        "production_mutation_allowed",
        "model_call_allowed",
    ):
        if policy.get(key) is not False:
            raise PatchProposalDeliveryTrustCaseBridgeError(f"harness_policy.{key} must be false")
    if policy.get("emit_refs_only") is not True:
        raise PatchProposalDeliveryTrustCaseBridgeError("bridge must emit refs only")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise PatchProposalDeliveryTrustCaseBridgeError(f"Unknown case id: {case_id}")
    candidate = source_candidate(case_id)
    run = source_product_loop_run(case_id)
    dual = default_dual_loop_artifacts(within_budget=case_id != "blocked-dual-loop-gate-blocked")

    if case_id == "blocked-missing-candidate":
        candidate = None
    if case_id == "blocked-invalid-candidate" and candidate is not None:
        candidate = copy.deepcopy(candidate)
        candidate["next_boundary"] = "production"
    if case_id == "blocked-missing-product-loop-run":
        run = None
    if case_id == "blocked-product-loop-hash-mismatch" and run is not None:
        run = copy.deepcopy(run)
        run["run_id"] = "product-loop-run-hash-mismatch"
    if case_id == "blocked-missing-dual-loop-evidence":
        dual["sandbox_receipt"] = None
    if case_id == "blocked-dual-loop-evidence-mismatch" and dual["sandbox_receipt"] is not None:
        sandbox = copy.deepcopy(dual["sandbox_receipt"])
        sandbox["receipt_id"] = "sandbox-receipt-mismatched"
        dual["sandbox_receipt"] = sandbox
    if case_id == "blocked-ai-review-only" and run is not None:
        run = copy.deepcopy(run)
        run["checks"] = dict(run["checks"])
        run["checks"]["ai_review_only_rejected"] = False

    receipt = build_bridge_receipt(
        case_id,
        candidate=candidate,
        product_loop_run=run,
        failure_contract=dual["failure_contract"],
        sandbox_receipt=dual["sandbox_receipt"],
        attention_summary=dual["attention_summary"],
        dual_loop_gate=dual["dual_loop_gate"],
        customer_visible_send_requested=case_id == "blocked-customer-visible-send",
        source_mutation_requested=case_id == "blocked-source-mutation",
        production_mutation_requested=case_id == "blocked-production-mutation",
        secret_attached=case_id == "blocked-secret",
        model_credential_attached=case_id == "blocked-model-credential",
    )
    artifacts = {"patch-proposal-delivery-trust-case-bridge-receipt.json": receipt}
    refs = receipt.get("handoff_refs")
    if isinstance(refs, Mapping):
        artifacts["patch-proposal-delivery-trust-case-handoff-refs.json"] = validate_handoff_refs(refs)
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_bridge_receipt(cases[case_id]["patch-proposal-delivery-trust-case-bridge-receipt.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "handoff_refs_created": receipt["handoff_refs"] is not None,
            }
        )
    ready_count = sum(1 for row in case_reports if row["status"] == "delivery_trust_case_refs_ready")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove Patch Proposal Delivery Trust case candidates can invoke the local deterministic "
            "Delivery Trust Case Harness only after candidate, Product Loop, controlled-failure, "
            "attention-reconstruction, and Dual Loop refs match, while emitting refs only."
        ),
        "case_reports": case_reports,
        "bridge_matrix": {
            "ready_delivery_trust_case_ref_sets": ready_count,
            "blocked_bridge_transitions": blocked_count,
            "customer_visible_sends": 0,
            "source_mutations": 0,
            "production_mutations": 0,
            "model_calls": 0,
        },
        "bridge_rules": {
            "candidate_required": True,
            "product_loop_run_required": True,
            "controlled_failure_required": True,
            "attention_reconstruction_required": True,
            "dual_loop_gate_required": True,
            "delivery_trust_case_harness_local_deterministic_only": True,
            "emit_refs_only": True,
            "metadata_only": True,
            "customer_visible_send_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
        },
        "effect_boundary": _effect_boundary(harness_invoked=True),
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
    parser.add_argument("--candidate", type=Path, help="Build from a Patch Proposal Delivery Trust case candidate.")
    parser.add_argument("--product-loop-run", type=Path, help="Product Loop run JSON for custom candidate builds.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.candidate:
        if not args.product_loop_run:
            raise SystemExit("--product-loop-run is required with --candidate")
        dual = default_dual_loop_artifacts()
        receipt = build_bridge_receipt(
            "custom",
            candidate=load_json(args.candidate),
            product_loop_run=load_json(args.product_loop_run),
            failure_contract=dual["failure_contract"],
            sandbox_receipt=dual["sandbox_receipt"],
            attention_summary=dual["attention_summary"],
            dual_loop_gate=dual["dual_loop_gate"],
        )
        selected: dict[str, dict[str, dict[str, Any]]] = {
            "custom": {"patch-proposal-delivery-trust-case-bridge-receipt.json": receipt}
        }
        refs = receipt.get("handoff_refs")
        if isinstance(refs, Mapping):
            selected["custom"]["patch-proposal-delivery-trust-case-handoff-refs.json"] = validate_handoff_refs(refs)
    else:
        cases = build_all_case_artifacts()
        selected = cases if args.case == "all" else {args.case: cases[args.case]}

    write_artifacts(args.output_dir, selected)
    print(
        dump_json(
            {
                "schema_version": "patch-proposal-delivery-trust-case-bridge-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "ready_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts["patch-proposal-delivery-trust-case-bridge-receipt.json"]["status"]
                    == "delivery_trust_case_refs_ready"
                ),
                "blocked_case_count": sum(
                    1
                    for artifacts in selected.values()
                    if artifacts["patch-proposal-delivery-trust-case-bridge-receipt.json"]["status"] == "blocked"
                ),
                "model_calls_performed": False,
                "customer_visible_send_performed": False,
                "source_mutation_performed": False,
                "production_mutation_performed": False,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
