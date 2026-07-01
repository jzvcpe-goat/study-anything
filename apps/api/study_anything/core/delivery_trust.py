"""Delivery trust receipt contracts for Cognitive Black Box.

The delivery trust layer does not decide that an AI result is universally true.
It decides whether a candidate AI delivery has enough structured evidence to be
handed to a customer inside the current controlled scope. In v0.1 this remains
metadata-only: no model calls, no production mutation, no raw customer/source
payloads, and no AI-review-only promotion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from study_anything.core import dual_loop


DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION = "delivery-trust-receipt-v1"
DELIVERY_TRUST_REPORT_SCHEMA_VERSION = "delivery-trust-receipt-verification-v1"

ALLOWED_DELIVERY_STATUSES = ("allowed", "blocked")
ALLOWED_DELIVERY_DECISIONS = (
    "allow_controlled_customer_handoff",
    "block_customer_handoff",
)

DELIVERY_PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "customer_payload_included": False,
    "client_secrets_included": False,
}


class DeliveryTrustError(ValueError):
    """Raised when delivery trust evidence is unsafe or malformed."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DeliveryTrustError(f"Expected object JSON at {path}")
    return payload


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_json(dict(payload)), encoding="utf-8")


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        raise DeliveryTrustError(f"{label} must include privacy flags")
    for key, expected in DELIVERY_PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise DeliveryTrustError(f"{label}.privacy.{key} must be {expected!r}")


def validate_delivery_trust_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION:
        raise DeliveryTrustError("Invalid delivery trust receipt schema_version")
    if payload.get("status") not in ALLOWED_DELIVERY_STATUSES:
        raise DeliveryTrustError("delivery trust receipt status is invalid")
    if payload.get("decision") not in ALLOWED_DELIVERY_DECISIONS:
        raise DeliveryTrustError("delivery trust receipt decision is invalid")
    for key in (
        "receipt_id",
        "project_id",
        "candidate_artifact_ref",
        "dual_loop_refs",
        "trust_basis",
        "checks",
        "claim_boundary",
        "customer_delivery_scope",
        "reasons",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise DeliveryTrustError(f"delivery trust receipt missing {key}")

    dual_loop.validate_isolation(payload, label="delivery_trust_receipt")
    _validate_privacy(payload, label="delivery_trust_receipt")

    trust_basis = payload["trust_basis"]
    if not isinstance(trust_basis, Mapping):
        raise DeliveryTrustError("delivery trust receipt trust_basis must be an object")
    if trust_basis.get("controlled_failure_environment") != "required":
        raise DeliveryTrustError("controlled failure environment must be required")
    if trust_basis.get("human_attention_reconstruction") != "required":
        raise DeliveryTrustError("human attention reconstruction must be required")
    if trust_basis.get("ai_eval_receipts_role") != "supporting_only_not_sufficient":
        raise DeliveryTrustError("AI eval receipts cannot be sufficient by themselves")
    if trust_basis.get("human_review_role") != "active_reconstruction_not_full_manual_re_review":
        raise DeliveryTrustError("human review must be active reconstruction, not full re-review")

    claim_boundary = payload["claim_boundary"]
    if not isinstance(claim_boundary, Mapping):
        raise DeliveryTrustError("delivery trust receipt claim_boundary must be an object")
    if not claim_boundary.get("current_claim"):
        raise DeliveryTrustError("delivery trust receipt must state a current claim")
    not_claimed = claim_boundary.get("not_claimed")
    if not isinstance(not_claimed, list) or not not_claimed:
        raise DeliveryTrustError("delivery trust receipt must state what is not claimed")

    scope = payload["customer_delivery_scope"]
    if not isinstance(scope, Mapping):
        raise DeliveryTrustError("delivery trust receipt customer_delivery_scope must be object")
    if scope.get("production_mutation_allowed") is not False:
        raise DeliveryTrustError("delivery trust receipt must block production mutation")
    if scope.get("irreversible_external_effects_allowed") is not False:
        raise DeliveryTrustError("delivery trust receipt must block irreversible effects")

    checks = payload["checks"]
    if not isinstance(checks, Mapping):
        raise DeliveryTrustError("delivery trust receipt checks must be an object")
    if checks.get("no_ai_review_black_box_as_sole_basis") is not True:
        raise DeliveryTrustError("AI-review-only trust basis is forbidden")
    if checks.get("no_excessive_manual_re_review_required") is not True:
        raise DeliveryTrustError("delivery trust must avoid full manual re-review as the gate")
    if payload.get("status") == "allowed":
        required_true = (
            "failure_contract_valid",
            "sandbox_receipt_valid",
            "dual_loop_gate_allowed",
            "controlled_failure_environment_passed",
            "human_reconstruction_present",
            "human_reconstruction_passed",
            "structured_artifact_bridge_only",
            "production_mutation_blocked",
            "reversible_delivery_path",
            "customer_claim_boundary_present",
        )
        for key in required_true:
            if checks.get(key) is not True:
                raise DeliveryTrustError(f"allowed delivery trust receipt requires {key}")
    return dict(payload)


def build_delivery_trust_receipt(
    failure_contract: Mapping[str, Any],
    sandbox_receipt: Mapping[str, Any],
    gate_receipt: Mapping[str, Any],
    attention_summary: Mapping[str, Any] | None,
    *,
    receipt_id: str = "delivery-trust-receipt-demo-001",
) -> dict[str, Any]:
    contract = dual_loop.validate_failure_contract(failure_contract)
    sandbox = dual_loop.validate_sandbox_receipt(sandbox_receipt)
    gate = dual_loop.validate_gate_receipt(gate_receipt)
    attention: dict[str, Any] | None = None
    if attention_summary is not None:
        attention = dual_loop.validate_attention_summary(attention_summary)

    contract_id = contract["contract_id"]
    for artifact_name, artifact in (
        ("sandbox_receipt", sandbox),
        ("gate_receipt", gate),
    ):
        if artifact.get("contract_id") != contract_id:
            raise DeliveryTrustError(f"{artifact_name} contract_id does not match")
    if attention is not None and attention.get("contract_id") != contract_id:
        raise DeliveryTrustError("attention_summary contract_id does not match")

    sandbox_passed = sandbox.get("status") == "passed"
    sandbox_within_budget = bool(sandbox["risk_budget"]["within_budget"])
    sandbox_contained = all(
        isinstance(item, Mapping)
        and item.get("containment_status") == "contained"
        and item.get("propagated") is False
        for item in sandbox.get("observed_failures", [])
    )
    attention_present = attention is not None
    attention_passed = bool(attention and attention.get("status") == "passed")
    gate_allowed = gate.get("status") == "allowed"
    reasons: list[str] = []
    if not sandbox_passed or not sandbox_contained:
        reasons.append("controlled_failure_environment_not_passed")
    if not sandbox_within_budget:
        reasons.append("sandbox_risk_outside_budget")
    if not attention_present:
        reasons.append("human_reconstruction_missing")
    elif not attention_passed:
        reasons.append("human_reconstruction_failed")
    if not gate_allowed:
        reasons.append("dual_loop_gate_blocked")

    allowed = not reasons
    checks = {
        "failure_contract_valid": True,
        "sandbox_receipt_valid": True,
        "dual_loop_gate_allowed": gate_allowed,
        "controlled_failure_environment_passed": sandbox_passed
        and sandbox_contained
        and sandbox_within_budget,
        "human_reconstruction_present": attention_present,
        "human_reconstruction_passed": attention_passed,
        "structured_artifact_bridge_only": True,
        "no_ai_review_black_box_as_sole_basis": True,
        "no_excessive_manual_re_review_required": True,
        "production_mutation_blocked": True,
        "reversible_delivery_path": bool(sandbox.get("rollback", {}).get("available"))
        and bool(sandbox.get("rollback", {}).get("rehearsed")),
        "customer_claim_boundary_present": True,
    }
    receipt = {
        "schema_version": DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "project_id": contract["project_id"],
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "candidate_artifact_ref": contract["candidate_artifact_ref"],
        "status": "allowed" if allowed else "blocked",
        "decision": (
            "allow_controlled_customer_handoff" if allowed else "block_customer_handoff"
        ),
        "reasons": reasons,
        "dual_loop_refs": {
            "failure_contract_ref": "failure-contract.json",
            "sandbox_receipt_ref": "sandbox-receipt.json",
            "attention_summary_ref": (
                "attention-reconstruction-summary.json" if attention_present else None
            ),
            "gate_receipt_ref": "dual-loop-gate-receipt.json",
        },
        "trust_basis": {
            "controlled_failure_environment": "required",
            "human_attention_reconstruction": "required",
            "dual_loop_propagation_gate": "required",
            "ai_eval_receipts_role": "supporting_only_not_sufficient",
            "human_review_role": "active_reconstruction_not_full_manual_re_review",
            "passive_attention_role": "weak_not_sufficient",
        },
        "checks": checks,
        "customer_delivery_scope": {
            "scope_id": "controlled-customer-handoff-v0.1",
            "allowed_handoff": allowed,
            "allowed_material_refs": [
                "candidate_artifact_ref",
                "known_limitations",
                "verification_command_refs",
                "rollback_ref",
            ],
            "production_mutation_allowed": False,
            "irreversible_external_effects_allowed": False,
            "real_customer_effects_allowed": False,
        },
        "claim_boundary": {
            "current_claim": (
                "The candidate passed local metadata-only Dual Loop gates for a "
                "controlled customer handoff."
            ),
            "not_claimed": [
                "general model correctness",
                "production deployment approval",
                "customer outcome guarantee",
                "AI self-review sufficiency",
                "full human re-review completion",
            ],
            "requires_before_real_production": [
                "domain acceptance tests",
                "operator-owned deployment approval",
                "customer-specific rollback plan",
                "legal and security review when required",
            ],
        },
        "next_actions": [
            "attach delivery trust receipt to the handoff package",
            "keep production mutation disabled until a stronger sandbox level passes",
            "rerun Dual Loop gates after any material change",
        ],
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(DELIVERY_PRIVACY_FLAGS),
    }
    return validate_delivery_trust_receipt(receipt)


def write_html_report(path: str | Path, title: str, payload: Mapping[str, Any]) -> None:
    dual_loop.write_html_report(path, title, payload)
