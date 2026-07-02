"""Cognitive Black Box protocol receipts and deterministic gate.

The CBB protocol core is a metadata-only reference implementation. It decides
whether an AI delivery candidate may move to the next controlled handoff scope
from structured receipts only. It does not call models, inspect raw work
products, mutate production, or treat AI review as a sufficient trust source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from study_anything.core import dual_loop


CLAIM_BOUNDARY_SCHEMA_VERSION = "claim-boundary-v1"
TRUST_ROOT_SCHEMA_VERSION = "trust-root-v1"
REVIEWER_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION = "reviewer-reconstruction-receipt-v1"
RISK_OWNER_SCOPE_SCHEMA_VERSION = "risk-owner-scope-v1"
DELIVERY_DECISION_RECEIPT_SCHEMA_VERSION = "delivery-decision-receipt-v1"

CBB_PROTOCOL_CONTRACTS_REPORT_SCHEMA_VERSION = "cbb-protocol-contracts-verification-v1"
CBB_GATE_REPORT_SCHEMA_VERSION = "cbb-gate-verification-v1"

CBB_PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "customer_payload_included": False,
    "model_prompts_included": False,
    "agent_credentials_included": False,
    "production_payload_included": False,
}

ALLOWED_DECISION_STATUSES = ("allowed", "blocked")
ALLOWED_DELIVERY_DECISIONS = (
    "allow_controlled_customer_handoff",
    "block_delivery",
)
ALLOWED_HANDOFF_SCOPES = (
    "controlled_customer_handoff",
    "sandbox_only",
    "blocked",
)


class CBBProtocolError(ValueError):
    """Raised when a CBB protocol artifact is unsafe or malformed."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CBBProtocolError(f"Expected object JSON at {path}")
    return payload


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_json(dict(payload)), encoding="utf-8")


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        raise CBBProtocolError(f"{label} must include privacy flags")
    for key, expected in CBB_PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise CBBProtocolError(f"{label}.privacy.{key} must be {expected!r}")


def _validate_isolation(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.validate_isolation(payload, label=label)


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise CBBProtocolError(f"{label}.{key} must be an object")
    return value


def _require_nonempty_list(payload: Mapping[str, Any], key: str, *, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise CBBProtocolError(f"{label}.{key} must be a non-empty list")
    return value


def _base_artifact(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(CBB_PRIVACY_FLAGS),
    }


def validate_claim_boundary(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CLAIM_BOUNDARY_SCHEMA_VERSION)
    if payload.get("schema_version") != CLAIM_BOUNDARY_SCHEMA_VERSION:
        raise CBBProtocolError("Invalid claim boundary schema_version")
    for key in (
        "claim_id",
        "project_id",
        "candidate_artifact_ref",
        "current_claim",
        "allowed_scope",
        "not_claimed",
        "requires_before_production",
        "evidence_refs",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBProtocolError(f"claim boundary missing {key}")
    if not str(payload.get("current_claim") or "").strip():
        raise CBBProtocolError("claim boundary must state a current claim")
    if payload.get("allowed_scope") not in ALLOWED_HANDOFF_SCOPES:
        raise CBBProtocolError("claim boundary allowed_scope is invalid")
    _require_nonempty_list(payload, "not_claimed", label="claim_boundary")
    _require_nonempty_list(payload, "requires_before_production", label="claim_boundary")
    _require_object(payload, "evidence_refs", label="claim_boundary")
    _validate_isolation(payload, label="claim_boundary")
    _validate_privacy(payload, label="claim_boundary")
    return dict(payload)


def validate_trust_root(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=TRUST_ROOT_SCHEMA_VERSION)
    if payload.get("schema_version") != TRUST_ROOT_SCHEMA_VERSION:
        raise CBBProtocolError("Invalid trust root schema_version")
    for key in (
        "trust_root_id",
        "project_id",
        "accepted_evidence",
        "forbidden_trust_bases",
        "kernel",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBProtocolError(f"trust root missing {key}")
    accepted = _require_nonempty_list(payload, "accepted_evidence", label="trust_root")
    forbidden = _require_nonempty_list(payload, "forbidden_trust_bases", label="trust_root")
    if "ai_review_only" in accepted:
        raise CBBProtocolError("AI-review-only trust basis is forbidden")
    for required in (
        "controlled_failure_environment",
        "human_attention_reconstruction",
        "dual_loop_gate",
        "claim_boundary",
        "risk_owner_scope",
    ):
        if required not in accepted:
            raise CBBProtocolError(f"trust root missing accepted evidence: {required}")
    if "ai_review_only" not in forbidden:
        raise CBBProtocolError("trust root must forbid AI-review-only trust")
    kernel = _require_object(payload, "kernel", label="trust_root")
    if kernel.get("deterministic") is not True:
        raise CBBProtocolError("trust root kernel must be deterministic")
    if kernel.get("model_calls_allowed") is not False:
        raise CBBProtocolError("trust root kernel must forbid model calls in v0.1")
    if kernel.get("production_mutation_allowed") is not False:
        raise CBBProtocolError("trust root kernel must forbid production mutation")
    _validate_isolation(payload, label="trust_root")
    _validate_privacy(payload, label="trust_root")
    return dict(payload)


def validate_reviewer_reconstruction_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=REVIEWER_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != REVIEWER_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION:
        raise CBBProtocolError("Invalid reviewer reconstruction receipt schema_version")
    for key in (
        "reviewer_receipt_id",
        "project_id",
        "reviewer_ref",
        "qualification",
        "reconstruction",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBProtocolError(f"reviewer reconstruction receipt missing {key}")
    qualification = _require_object(payload, "qualification", label="reviewer_reconstruction")
    reconstruction = _require_object(payload, "reconstruction", label="reviewer_reconstruction")
    if qualification.get("qualified_for_scope") is not True:
        raise CBBProtocolError("reviewer is not qualified for this scope")
    if reconstruction.get("status") != "passed":
        raise CBBProtocolError("reviewer reconstruction did not pass")
    if reconstruction.get("active_reconstruction") is not True:
        raise CBBProtocolError("reviewer reconstruction must be active")
    if reconstruction.get("passive_attention_only") is not False:
        raise CBBProtocolError("passive attention only is insufficient")
    if reconstruction.get("claim_boundary_reconstructed") is not True:
        raise CBBProtocolError("reviewer must reconstruct claim boundary")
    if reconstruction.get("risk_owner_scope_reconstructed") is not True:
        raise CBBProtocolError("reviewer must reconstruct risk owner scope")
    _validate_isolation(payload, label="reviewer_reconstruction")
    _validate_privacy(payload, label="reviewer_reconstruction")
    return dict(payload)


def validate_risk_owner_scope(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=RISK_OWNER_SCOPE_SCHEMA_VERSION)
    if payload.get("schema_version") != RISK_OWNER_SCOPE_SCHEMA_VERSION:
        raise CBBProtocolError("Invalid risk owner scope schema_version")
    for key in (
        "scope_id",
        "project_id",
        "risk_owner_ref",
        "recipient_ref",
        "known_recipient_risk",
        "allowed_delivery_modes",
        "production_mutation_allowed",
        "irreversible_external_effects_allowed",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBProtocolError(f"risk owner scope missing {key}")
    if payload.get("known_recipient_risk") is not True:
        raise CBBProtocolError("recipient risk is unknown")
    if not str(payload.get("risk_owner_ref") or "").strip():
        raise CBBProtocolError("risk owner scope must identify a risk owner ref")
    if not str(payload.get("recipient_ref") or "").strip():
        raise CBBProtocolError("risk owner scope must identify a recipient ref")
    modes = _require_nonempty_list(payload, "allowed_delivery_modes", label="risk_owner_scope")
    if "controlled_customer_handoff" not in modes:
        raise CBBProtocolError("risk owner scope must allow controlled handoff")
    if payload.get("production_mutation_allowed") is not False:
        raise CBBProtocolError("risk owner scope must block production mutation")
    if payload.get("irreversible_external_effects_allowed") is not False:
        raise CBBProtocolError("risk owner scope must block irreversible external effects")
    _validate_isolation(payload, label="risk_owner_scope")
    _validate_privacy(payload, label="risk_owner_scope")
    return dict(payload)


def validate_delivery_decision_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=DELIVERY_DECISION_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != DELIVERY_DECISION_RECEIPT_SCHEMA_VERSION:
        raise CBBProtocolError("Invalid delivery decision receipt schema_version")
    if payload.get("status") not in ALLOWED_DECISION_STATUSES:
        raise CBBProtocolError("delivery decision status is invalid")
    if payload.get("decision") not in ALLOWED_DELIVERY_DECISIONS:
        raise CBBProtocolError("delivery decision is invalid")
    for key in (
        "decision_id",
        "project_id",
        "candidate_artifact_ref",
        "status",
        "decision",
        "reasons",
        "evidence_refs",
        "checks",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBProtocolError(f"delivery decision receipt missing {key}")
    reasons = payload.get("reasons")
    if not isinstance(reasons, list):
        raise CBBProtocolError("delivery decision reasons must be a list")
    checks = _require_object(payload, "checks", label="delivery_decision")
    claim_boundary = _require_object(payload, "claim_boundary", label="delivery_decision")
    if not claim_boundary.get("current_claim"):
        raise CBBProtocolError("delivery decision receipt must state its claim boundary")
    _require_nonempty_list(claim_boundary, "not_claimed", label="delivery_decision.claim_boundary")
    if checks.get("ai_review_only_rejected") is not True:
        raise CBBProtocolError("delivery decision must reject AI-review-only trust")
    if checks.get("production_mutation_blocked") is not True:
        raise CBBProtocolError("delivery decision must block production mutation")
    if checks.get("deterministic_kernel") is not True:
        raise CBBProtocolError("delivery decision must use deterministic kernel")
    if payload.get("status") == "allowed":
        if reasons:
            raise CBBProtocolError("allowed delivery decision must not include block reasons")
        required_true = (
            "claim_boundary_valid",
            "trust_root_valid",
            "reviewer_qualified",
            "reviewer_reconstruction_passed",
            "risk_owner_known",
            "recipient_risk_known",
            "controlled_handoff_scope_only",
            "metadata_only",
        )
        for key in required_true:
            if checks.get(key) is not True:
                raise CBBProtocolError(f"allowed delivery decision requires {key}")
    _validate_isolation(payload, label="delivery_decision")
    _validate_privacy(payload, label="delivery_decision")
    return dict(payload)


def claim_boundary_demo(*, missing: bool = False) -> dict[str, Any]:
    payload = {
        **_base_artifact(CLAIM_BOUNDARY_SCHEMA_VERSION),
        "claim_id": "claim-boundary-demo-001",
        "project_id": "study-anything",
        "candidate_artifact_ref": "artifact:customer-handoff-candidate-metadata",
        "current_claim": (
            "" if missing else "The AI delivery candidate may enter controlled customer handoff."
        ),
        "allowed_scope": "controlled_customer_handoff",
        "not_claimed": [
            "production readiness",
            "legal certification",
            "security certification",
            "general model correctness",
            "customer outcome guarantee",
        ],
        "requires_before_production": [
            "domain acceptance tests",
            "operator-owned deployment approval",
            "recipient-specific rollback plan",
        ],
        "evidence_refs": {
            "failure_contract": "failure-contract.json",
            "sandbox_receipt": "sandbox-receipt.json",
            "attention_summary": "attention-reconstruction-summary.json",
            "dual_loop_gate": "dual-loop-gate-receipt.json",
            "delivery_trust_receipt": "delivery-trust-receipt.json",
        },
    }
    return payload


def trust_root_demo(*, ai_review_only: bool = False) -> dict[str, Any]:
    accepted = [
        "controlled_failure_environment",
        "human_attention_reconstruction",
        "dual_loop_gate",
        "claim_boundary",
        "risk_owner_scope",
        "delivery_trust_receipt",
    ]
    if ai_review_only:
        accepted = ["ai_review_only"]
    return {
        **_base_artifact(TRUST_ROOT_SCHEMA_VERSION),
        "trust_root_id": "trust-root-demo-001",
        "project_id": "study-anything",
        "accepted_evidence": accepted,
        "forbidden_trust_bases": [
            "ai_review_only",
            "raw_human_attention_stream",
            "unbounded_manual_review",
            "unscoped_external_eval",
        ],
        "kernel": {
            "deterministic": True,
            "model_calls_allowed": False,
            "production_mutation_allowed": False,
            "raw_payload_access_allowed": False,
        },
        "claim_boundary": {
            "reference_implementation_only": True,
            "not_claimed": [
                "production customer trust",
                "universal model correctness",
                "regulatory approval",
            ],
        },
    }


def reviewer_reconstruction_demo(*, qualified: bool = True) -> dict[str, Any]:
    return {
        **_base_artifact(REVIEWER_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION),
        "reviewer_receipt_id": "reviewer-reconstruction-demo-001",
        "project_id": "study-anything",
        "reviewer_ref": "reviewer:operator-role",
        "qualification": {
            "qualified_for_scope": qualified,
            "scope_ref": "controlled_customer_handoff",
            "qualification_basis": [
                "understands claim boundary",
                "can reconstruct failure boundary",
                "owns local handoff decision",
            ],
        },
        "reconstruction": {
            "status": "passed" if qualified else "failed",
            "active_reconstruction": True,
            "passive_attention_only": False,
            "claim_boundary_reconstructed": qualified,
            "risk_owner_scope_reconstructed": qualified,
            "minimum_reconstructable_units_passed": 3 if qualified else 1,
            "minimum_reconstructable_units_required": 3,
        },
    }


def risk_owner_scope_demo(*, recipient_risk_known: bool = True) -> dict[str, Any]:
    return {
        **_base_artifact(RISK_OWNER_SCOPE_SCHEMA_VERSION),
        "scope_id": "owner-scope-demo-001",
        "project_id": "study-anything",
        "risk_owner_ref": "owner:local-operator",
        "recipient_ref": "recipient:controlled-customer-reviewer",
        "known_recipient_risk": recipient_risk_known,
        "allowed_delivery_modes": ["controlled_customer_handoff"],
        "production_mutation_allowed": False,
        "irreversible_external_effects_allowed": False,
        "risk_budget": {
            "maximum_scope": "controlled_customer_handoff",
            "requires_recipient_context": True,
            "recipient_context_known": recipient_risk_known,
        },
    }


def _validate_or_reason(
    validator: Any,
    payload: Mapping[str, Any] | None,
    missing_reason: str,
    invalid_reason: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if payload is None:
        return None, missing_reason
    try:
        return validator(payload), None
    except Exception as exc:  # noqa: BLE001 - gate receipt records deterministic reason.
        reason = invalid_reason
        if "AI-review-only" in str(exc) or "AI-review-only" in repr(exc):
            reason = "ai_review_only_trust_basis"
        return None, reason


def evaluate_cbb_gate(
    claim_boundary: Mapping[str, Any] | None,
    trust_root: Mapping[str, Any] | None,
    reviewer_reconstruction: Mapping[str, Any] | None,
    risk_owner_scope: Mapping[str, Any] | None,
    *,
    decision_id: str = "delivery-decision-demo-001",
) -> dict[str, Any]:
    claim, claim_reason = _validate_or_reason(
        validate_claim_boundary,
        claim_boundary,
        "claim_boundary_missing",
        "claim_boundary_missing",
    )
    trust, trust_reason = _validate_or_reason(
        validate_trust_root,
        trust_root,
        "trust_root_missing",
        "trust_root_invalid",
    )
    reviewer, reviewer_reason = _validate_or_reason(
        validate_reviewer_reconstruction_receipt,
        reviewer_reconstruction,
        "reviewer_reconstruction_missing",
        "reviewer_not_qualified",
    )
    risk_owner, risk_reason = _validate_or_reason(
        validate_risk_owner_scope,
        risk_owner_scope,
        "risk_owner_scope_missing",
        "recipient_risk_unknown",
    )

    reasons = [
        reason
        for reason in (claim_reason, trust_reason, reviewer_reason, risk_reason)
        if reason is not None
    ]
    allowed = not reasons
    candidate_ref = "artifact:unknown-candidate"
    project_id = "study-anything"
    if claim is not None:
        candidate_ref = str(claim.get("candidate_artifact_ref"))
        project_id = str(claim.get("project_id"))
    elif claim_boundary is not None:
        candidate_ref = str(
            claim_boundary.get("candidate_artifact_ref") or "artifact:unknown-candidate"
        )
        project_id = str(claim_boundary.get("project_id") or "study-anything")

    checks = {
        "claim_boundary_valid": claim is not None,
        "trust_root_valid": trust is not None,
        "reviewer_qualified": reviewer is not None,
        "reviewer_reconstruction_passed": reviewer is not None,
        "risk_owner_known": risk_owner is not None,
        "recipient_risk_known": risk_owner is not None,
        "ai_review_only_rejected": True,
        "production_mutation_blocked": True,
        "deterministic_kernel": True,
        "controlled_handoff_scope_only": allowed,
        "metadata_only": True,
        "model_calls_performed": False,
    }
    receipt = {
        "schema_version": DELIVERY_DECISION_RECEIPT_SCHEMA_VERSION,
        "decision_id": decision_id,
        "project_id": project_id,
        "candidate_artifact_ref": candidate_ref,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "status": "allowed" if allowed else "blocked",
        "decision": "allow_controlled_customer_handoff" if allowed else "block_delivery",
        "reasons": reasons,
        "evidence_refs": {
            "claim_boundary_ref": "claim-boundary.json",
            "trust_root_ref": "trust-root.json",
            "reviewer_reconstruction_ref": "reviewer-reconstruction-receipt.json",
            "risk_owner_scope_ref": "risk-owner-scope.json",
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": (
                "The deterministic CBB protocol gate evaluated only metadata receipts "
                "for the current controlled handoff scope."
            ),
            "not_claimed": [
                "production readiness",
                "legal certification",
                "regulatory approval",
                "general model correctness",
                "AI self-review sufficiency",
            ],
            "reference_implementation_only": True,
        },
        "next_actions": (
            [
                "assemble customer handoff package",
                "keep production mutation disabled",
                "rerun CBB gate after material evidence changes",
            ]
            if allowed
            else [
                "do not hand off the candidate",
                "repair missing or invalid protocol evidence",
                "rerun deterministic gate after repairs",
            ]
        ),
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(CBB_PRIVACY_FLAGS),
    }
    return validate_delivery_decision_receipt(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    claim = claim_boundary_demo(missing=case_id == "missing-claim-boundary")
    trust = trust_root_demo(ai_review_only=case_id == "ai-review-only-rejected")
    reviewer = reviewer_reconstruction_demo(qualified=case_id != "reviewer-not-qualified")
    risk_owner = risk_owner_scope_demo(recipient_risk_known=case_id != "recipient-risk-unknown")
    decision = evaluate_cbb_gate(claim, trust, reviewer, risk_owner)
    return {
        "claim-boundary.json": claim,
        "trust-root.json": trust,
        "reviewer-reconstruction-receipt.json": reviewer,
        "risk-owner-scope.json": risk_owner,
        "delivery-decision-receipt.json": decision,
    }


def write_html_report(path: str | Path, title: str, payload: Mapping[str, Any]) -> None:
    dual_loop.write_html_report(path, title, payload)
