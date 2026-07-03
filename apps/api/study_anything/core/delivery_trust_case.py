"""End-to-end Delivery Trust Case harness.

Delivery Trust Case is the total assembly layer for Cognitive Black Box. It
does not create new authority by itself; it checks that Product Loop evidence,
Dual Loop evidence, DeliveryTrustReceipt, and CustomerHandoffPackage all agree
before a candidate can be called ready for controlled customer handoff.

The layer is deterministic and metadata-only. It performs no model calls,
starts no daemon, sends nothing to customers, and mutates no production system.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from study_anything.core import (
    customer_handoff,
    delivery_trust,
    dual_loop,
    product_loop_harness,
)


DELIVERY_TRUST_CASE_SCHEMA_VERSION = "delivery-trust-case-v1"
DELIVERY_TRUST_CASE_REPORT_SCHEMA_VERSION = "delivery-trust-case-harness-verification-v1"

CASE_IDS = (
    "pass",
    "blocked-product-loop",
    "blocked-dual-loop",
    "blocked-customer-handoff",
    "blocked-ai-review-only",
)

ALLOWED_CASE_STATUSES = ("ready_for_controlled_customer_handoff", "blocked")
ALLOWED_CASE_DECISIONS = ("allow_controlled_customer_handoff", "block_customer_handoff")

DELIVERY_TRUST_CASE_PRIVACY_FLAGS = {
    **product_loop_harness.PRODUCT_LOOP_PRIVACY_FLAGS,
    **customer_handoff.PACKAGE_PRIVACY_FLAGS,
    "customer_payload_included": False,
    "delivery_artifact_body_included": False,
    "automatic_customer_delivery_performed": False,
}


class DeliveryTrustCaseError(ValueError):
    """Raised when a Delivery Trust Case is unsafe or invalid."""


def _base_artifact(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(DELIVERY_TRUST_CASE_PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise DeliveryTrustCaseError(f"{label}.{key} must be an object")
    return value


def _require_list(payload: Mapping[str, Any], key: str, *, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise DeliveryTrustCaseError(f"{label}.{key} must be a list")
    return list(value)


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in DELIVERY_TRUST_CASE_PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise DeliveryTrustCaseError(f"{label}.privacy.{key} must be {expected!r}")


def _summary_ref(kind: str, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path,
        "sha256": dual_loop.sha256_text(dual_loop.dump_json(payload)),
        "raw_body_included": False,
    }


def _classify_customer_handoff_error(error: Exception) -> str:
    text = str(error).lower()
    if "scope exceeds" in text or "scope escalation" in text:
        return "customer_handoff_scope_expansion"
    if "claim" in text:
        return "customer_handoff_claim_boundary_missing"
    if "private" in text or "secret" in text:
        return "customer_handoff_private_data"
    if "delivery trust" in text:
        return "customer_handoff_delivery_trust_invalid"
    if "external eval" in text or "sufficient" in text:
        return "customer_handoff_eval_sufficiency_invalid"
    return "customer_handoff_invalid"


def _summarize_customer_handoff(
    package: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    if package is None:
        return (
            {
                "present": False,
                "validated": False,
                "status": "missing",
                "decision": None,
                "package_id": None,
                "error_code": "customer_handoff_missing",
                "error_digest": dual_loop.sha256_text("customer_handoff_missing"),
            },
            ["customer_handoff_not_ready"],
        )
    try:
        validated = customer_handoff.validate_customer_handoff_package(package)
    except Exception as exc:  # noqa: BLE001 - converted into metadata-only error code.
        code = _classify_customer_handoff_error(exc)
        return (
            {
                "present": True,
                "validated": False,
                "status": "blocked",
                "decision": None,
                "package_id": package.get("package_id"),
                "error_code": code,
                "error_digest": dual_loop.sha256_text(code),
            },
            ["customer_handoff_not_ready", code],
        )
    return (
        {
            "present": True,
            "validated": True,
            "status": validated["status"],
            "decision": validated["decision"],
            "package_id": validated["package_id"],
            "artifact_count": len(validated["manifest"]["artifacts"]),
            "external_eval_role": validated["external_eval_receipts"]["role"],
            "automatic_customer_sending_allowed": False,
            "production_mutation_allowed": False,
            "scope_escalation_allowed": False,
        },
        [],
    )


def build_delivery_trust_case(
    product_loop_run: Mapping[str, Any],
    dual_loop_gate: Mapping[str, Any],
    delivery_trust_receipt: Mapping[str, Any],
    customer_handoff_package: Mapping[str, Any] | None = None,
    *,
    case_id: str = "custom",
) -> dict[str, Any]:
    """Build one metadata-only end-to-end delivery trust case."""

    product_run = product_loop_harness.validate_product_loop_run(product_loop_run)
    gate = dual_loop.validate_gate_receipt(dual_loop_gate)
    delivery = delivery_trust.validate_delivery_trust_receipt(delivery_trust_receipt)
    package_summary, package_reasons = _summarize_customer_handoff(customer_handoff_package)

    reasons: list[str] = []
    if product_run["status"] != "allowed":
        reasons.append("product_loop_not_passed")
        reasons.extend(str(reason) for reason in product_run["reasons"])
    if gate["status"] != "allowed":
        reasons.append("dual_loop_gate_blocked")
        reasons.extend(str(reason) for reason in gate["reasons"])
    if delivery["status"] != "allowed":
        reasons.append("delivery_trust_not_allowed")
        reasons.extend(str(reason) for reason in delivery["reasons"])
    reasons.extend(package_reasons)
    unique_reasons = list(dict.fromkeys(reasons))

    ready = not unique_reasons
    status = "ready_for_controlled_customer_handoff" if ready else "blocked"
    decision = "allow_controlled_customer_handoff" if ready else "block_customer_handoff"
    product_checks = product_run["checks"]
    delivery_checks = delivery["checks"]
    package_valid = package_summary["validated"] is True
    external_eval_supporting = (
        package_summary.get("external_eval_role") == "supporting_only_not_sufficient"
        if package_valid
        else False
    )

    case = {
        **_base_artifact(DELIVERY_TRUST_CASE_SCHEMA_VERSION),
        "case_id": f"delivery-trust-case-{case_id}",
        "project_id": product_run["project_id"],
        "candidate_artifact_ref": delivery["candidate_artifact_ref"],
        "status": status,
        "decision": decision,
        "reasons": unique_reasons,
        "layer_statuses": {
            "product_loop": product_run["status"],
            "dual_loop_gate": gate["status"],
            "delivery_trust": delivery["status"],
            "customer_handoff": (
                "ready" if package_valid else str(package_summary["status"])
            ),
        },
        "evidence_chain": [
            _summary_ref("product-loop-run", "product-loop-run.json", product_run),
            _summary_ref("dual-loop-gate-receipt", "dual-loop-gate-receipt.json", gate),
            _summary_ref(
                "delivery-trust-receipt",
                "delivery-trust-receipt.json",
                delivery,
            ),
            *(
                [
                    _summary_ref(
                        "customer-handoff-package",
                        "customer-handoff-package.json",
                        customer_handoff_package,
                    )
                ]
                if customer_handoff_package is not None
                else []
            ),
        ],
        "trust_basis": {
            "product_development_loop": "required",
            "controlled_failure_environment": "required",
            "human_attention_reconstruction": "required",
            "dual_loop_propagation_gate": "required",
            "delivery_trust_receipt": "required",
            "customer_handoff_package": "required",
            "ai_eval_receipts_role": "supporting_only_not_sufficient",
            "human_review_role": "active_reconstruction_not_full_manual_re_review",
        },
        "checks": {
            "product_loop_allowed": product_run["status"] == "allowed",
            "product_spec_evals_present": product_checks["product_spec_evals_present"],
            "developer_vision_present": product_checks["developer_vision_present"],
            "external_feedback_scope_within_policy": product_checks[
                "external_feedback_scope_within_policy"
            ],
            "product_loop_parity_preserved": product_run["loop_parity"][
                "neither_loop_may_dominate"
            ]
            is True,
            "dual_loop_gate_allowed": gate["status"] == "allowed",
            "delivery_trust_allowed": delivery["status"] == "allowed",
            "customer_handoff_valid": package_valid,
            "external_eval_receipts_supporting_only": external_eval_supporting,
            "no_ai_review_black_box_as_sole_basis": (
                delivery_checks["no_ai_review_black_box_as_sole_basis"] is True
                and (
                    product_checks["ai_review_only_rejected"] is True
                    or "ai_review_only_evidence_rejected" in unique_reasons
                )
            ),
            "no_excessive_manual_re_review_required": delivery_checks[
                "no_excessive_manual_re_review_required"
            ]
            is True,
            "structured_artifact_bridge_only": True,
            "metadata_only": True,
            "model_calls_performed": False,
            "production_mutation_blocked": True,
            "irreversible_external_effects_blocked": True,
            "automatic_customer_sending_blocked": True,
            "claim_boundary_present": bool(delivery["claim_boundary"]["current_claim"]),
        },
        "customer_handoff_summary": package_summary,
        "customer_delivery_scope": {
            "scope_id": delivery["customer_delivery_scope"]["scope_id"],
            "controlled_handoff_allowed": ready,
            "production_mutation_allowed": False,
            "irreversible_external_effects_allowed": False,
            "real_customer_effects_allowed": False,
            "automatic_customer_sending_allowed": False,
        },
        "claim_boundary": {
            "current_claim": (
                "The AI-generated candidate is ready for controlled customer "
                "handoff inside the local metadata-only scope."
                if ready
                else "The AI-generated candidate is not ready for controlled customer handoff."
            ),
            "not_claimed": [
                "production deployment approval",
                "real customer delivery",
                "general model correctness",
                "legal certification",
                "security certification",
                "AI self-review sufficiency",
                "full human re-review completion",
            ],
            "requires_before_real_production": [
                "domain acceptance tests",
                "operator-owned deployment approval",
                "customer-specific rollback plan",
                "security and legal review when required",
            ],
        },
        "next_actions": (
            [
                "package the controlled customer handoff evidence",
                "keep production mutation disabled",
                "rerun the case after any material artifact change",
            ]
            if ready
            else [
                "resolve blocking reasons before customer handoff",
                "rerun Product Loop and Dual Loop evidence after changes",
                "do not send the candidate to customers automatically",
            ]
        ),
    }
    return validate_delivery_trust_case(case)


def validate_delivery_trust_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=DELIVERY_TRUST_CASE_SCHEMA_VERSION)
    if payload.get("schema_version") != DELIVERY_TRUST_CASE_SCHEMA_VERSION:
        raise DeliveryTrustCaseError("Invalid delivery trust case schema_version")
    for key in (
        "case_id",
        "project_id",
        "candidate_artifact_ref",
        "status",
        "decision",
        "reasons",
        "layer_statuses",
        "evidence_chain",
        "trust_basis",
        "checks",
        "customer_handoff_summary",
        "customer_delivery_scope",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise DeliveryTrustCaseError(f"delivery trust case missing {key}")
    if payload.get("status") not in ALLOWED_CASE_STATUSES:
        raise DeliveryTrustCaseError("delivery trust case status is invalid")
    if payload.get("decision") not in ALLOWED_CASE_DECISIONS:
        raise DeliveryTrustCaseError("delivery trust case decision is invalid")
    reasons = _require_list(payload, "reasons", label="delivery_trust_case")
    if payload["status"] == "ready_for_controlled_customer_handoff":
        if payload["decision"] != "allow_controlled_customer_handoff":
            raise DeliveryTrustCaseError("ready delivery trust case must allow handoff")
        if reasons:
            raise DeliveryTrustCaseError("ready delivery trust case must not include reasons")
    else:
        if payload["decision"] != "block_customer_handoff":
            raise DeliveryTrustCaseError("blocked delivery trust case must block handoff")
        if not reasons:
            raise DeliveryTrustCaseError("blocked delivery trust case must include reasons")
    dual_loop.validate_isolation(payload, label="delivery_trust_case")
    _validate_privacy(payload, label="delivery_trust_case")

    layers = _require_object(payload, "layer_statuses", label="delivery_trust_case")
    checks = _require_object(payload, "checks", label="delivery_trust_case")
    trust_basis = _require_object(payload, "trust_basis", label="delivery_trust_case")
    required_basis = {
        "product_development_loop": "required",
        "controlled_failure_environment": "required",
        "human_attention_reconstruction": "required",
        "dual_loop_propagation_gate": "required",
        "delivery_trust_receipt": "required",
        "customer_handoff_package": "required",
        "ai_eval_receipts_role": "supporting_only_not_sufficient",
        "human_review_role": "active_reconstruction_not_full_manual_re_review",
    }
    for key, expected in required_basis.items():
        if trust_basis.get(key) != expected:
            raise DeliveryTrustCaseError(f"delivery trust case trust_basis.{key} drifted")

    if checks.get("metadata_only") is not True:
        raise DeliveryTrustCaseError("delivery trust case must be metadata-only")
    if checks.get("model_calls_performed") is not False:
        raise DeliveryTrustCaseError("delivery trust case must not perform model calls")
    for key in (
        "production_mutation_blocked",
        "irreversible_external_effects_blocked",
        "automatic_customer_sending_blocked",
        "structured_artifact_bridge_only",
        "claim_boundary_present",
    ):
        if checks.get(key) is not True:
            raise DeliveryTrustCaseError(f"delivery trust case requires {key}")
    if checks.get("no_ai_review_black_box_as_sole_basis") is not True:
        raise DeliveryTrustCaseError("AI-review-only trust basis is forbidden")
    if checks.get("no_excessive_manual_re_review_required") is not True:
        raise DeliveryTrustCaseError("full manual re-review must not be the delivery gate")
    if payload["status"] == "ready_for_controlled_customer_handoff":
        required_true = (
            "product_loop_allowed",
            "product_spec_evals_present",
            "developer_vision_present",
            "external_feedback_scope_within_policy",
            "product_loop_parity_preserved",
            "dual_loop_gate_allowed",
            "delivery_trust_allowed",
            "customer_handoff_valid",
            "external_eval_receipts_supporting_only",
        )
        for key in required_true:
            if checks.get(key) is not True:
                raise DeliveryTrustCaseError(f"ready delivery trust case requires {key}")
        if layers != {
            "product_loop": "allowed",
            "dual_loop_gate": "allowed",
            "delivery_trust": "allowed",
            "customer_handoff": "ready",
        }:
            raise DeliveryTrustCaseError("ready delivery trust layer statuses drifted")
    scope = _require_object(payload, "customer_delivery_scope", label="delivery_trust_case")
    if scope.get("production_mutation_allowed") is not False:
        raise DeliveryTrustCaseError("delivery trust case must block production mutation")
    if scope.get("irreversible_external_effects_allowed") is not False:
        raise DeliveryTrustCaseError("delivery trust case must block irreversible effects")
    if scope.get("real_customer_effects_allowed") is not False:
        raise DeliveryTrustCaseError("delivery trust case must block real customer effects")
    if scope.get("automatic_customer_sending_allowed") is not False:
        raise DeliveryTrustCaseError("delivery trust case must block automatic customer sending")
    claim = _require_object(payload, "claim_boundary", label="delivery_trust_case")
    if not claim.get("current_claim"):
        raise DeliveryTrustCaseError("delivery trust case must state a current claim")
    if not _require_list(claim, "not_claimed", label="delivery_trust_case.claim_boundary"):
        raise DeliveryTrustCaseError("delivery trust case must state what is not claimed")
    if not _require_list(
        claim,
        "requires_before_real_production",
        label="delivery_trust_case.claim_boundary",
    ):
        raise DeliveryTrustCaseError("delivery trust case must list production prerequisites")
    evidence = _require_list(payload, "evidence_chain", label="delivery_trust_case")
    if len(evidence) < 3:
        raise DeliveryTrustCaseError("delivery trust case must include evidence refs")
    for item in evidence:
        if not isinstance(item, Mapping):
            raise DeliveryTrustCaseError("delivery trust evidence ref must be object")
        if item.get("raw_body_included") is not False:
            raise DeliveryTrustCaseError("delivery trust evidence refs must not include raw bodies")
    return dict(payload)


def _customer_delivery_contract() -> dict[str, Any]:
    contract = dual_loop.failure_contract_demo()
    contract["task_ref"] = "task:delivery-trust-case"
    contract["candidate_artifact_ref"] = "artifact:ai-delivery-candidate-metadata"
    contract["failure_boundaries"]["rollback_strategy_ref"] = (
        "rollback:ai-delivery-candidate-withdrawal"
    )
    contract["risk"]["score"] = 0.47
    return dual_loop.validate_failure_contract(contract)


def _rekey_sandbox(receipt: Mapping[str, Any]) -> dict[str, Any]:
    sandbox = copy.deepcopy(dict(receipt))
    sandbox["rollback"]["rollback_ref"] = "rollback:ai-delivery-candidate-withdrawal"
    return dual_loop.validate_sandbox_receipt(sandbox)


def _delivery_pass_artifacts() -> dict[str, dict[str, Any]]:
    contract = _customer_delivery_contract()
    sandbox = _rekey_sandbox(dual_loop.sandbox_receipt_demo())
    attention_trace = dual_loop.attention_trace_demo()
    attention_summary = dual_loop.attention_summary_demo()
    gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention_summary)
    receipt = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox,
        gate,
        attention_summary,
    )
    package = customer_handoff.build_customer_handoff_package(
        receipt,
        contract,
        sandbox,
        attention_summary,
        gate,
    )
    return {
        "failure-contract.json": contract,
        "sandbox-receipt.json": sandbox,
        "attention-reconstruction-trace.json": attention_trace,
        "attention-reconstruction-summary.json": attention_summary,
        "dual-loop-gate-receipt.json": gate,
        "delivery-trust-receipt.json": receipt,
        "customer-handoff-package.json": package,
    }


def _delivery_blocked_artifacts() -> dict[str, dict[str, Any]]:
    contract = _customer_delivery_contract()
    sandbox = _rekey_sandbox(dual_loop.sandbox_receipt_demo(within_budget=False))
    attention_summary = dual_loop.attention_summary_demo()
    gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention_summary)
    receipt = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox,
        gate,
        attention_summary,
    )
    return {
        "failure-contract.json": contract,
        "sandbox-receipt.json": sandbox,
        "attention-reconstruction-summary.json": attention_summary,
        "dual-loop-gate-receipt.json": gate,
        "delivery-trust-receipt.json": receipt,
    }


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise DeliveryTrustCaseError(f"Unknown delivery trust case: {case_id}")
    product_case = {
        "pass": "pass",
        "blocked-product-loop": "blocked-missing-developer-vision",
        "blocked-dual-loop": "pass",
        "blocked-customer-handoff": "pass",
        "blocked-ai-review-only": "blocked-ai-review-only",
    }[case_id]
    product_artifacts = product_loop_harness.build_case_artifacts(product_case)
    delivery_artifacts = (
        _delivery_blocked_artifacts()
        if case_id == "blocked-dual-loop"
        else _delivery_pass_artifacts()
    )
    if case_id == "blocked-customer-handoff":
        package = copy.deepcopy(delivery_artifacts["customer-handoff-package.json"])
        scope = dict(package["customer_delivery_scope"])
        scope["allowed_material_refs"] = [
            *scope["allowed_material_refs"],
            "production_deployment_approval",
        ]
        package["customer_delivery_scope"] = scope
        delivery_artifacts["customer-handoff-package.json"] = package

    case = build_delivery_trust_case(
        product_artifacts["product-loop-run.json"],
        delivery_artifacts["dual-loop-gate-receipt.json"],
        delivery_artifacts["delivery-trust-receipt.json"],
        delivery_artifacts.get("customer-handoff-package.json"),
        case_id=case_id,
    )
    return {
        **product_artifacts,
        **delivery_artifacts,
        "delivery-trust-case.json": case,
    }


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_harness_report(
    cases: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    ordered = [case_id for case_id in CASE_IDS if case_id in cases]
    if not ordered:
        raise DeliveryTrustCaseError("delivery trust case report requires cases")
    case_reports = []
    for case_id in ordered:
        case = validate_delivery_trust_case(cases[case_id]["delivery-trust-case.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": case["status"],
                "decision": case["decision"],
                "reasons": case["reasons"],
                "layer_statuses": case["layer_statuses"],
                "artifact_count": len(cases[case_id]),
            }
        )
    report = {
        "schema_version": DELIVERY_TRUST_CASE_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "artifact_contracts": {
            "delivery_trust_case": DELIVERY_TRUST_CASE_SCHEMA_VERSION,
            "product_loop_run": product_loop_harness.PRODUCT_LOOP_RUN_SCHEMA_VERSION,
            "dual_loop_gate_receipt": dual_loop.DUAL_LOOP_GATE_RECEIPT_SCHEMA_VERSION,
            "delivery_trust_receipt": delivery_trust.DELIVERY_TRUST_RECEIPT_SCHEMA_VERSION,
            "customer_handoff_package": customer_handoff.CUSTOMER_HANDOFF_PACKAGE_SCHEMA_VERSION,
        },
        "case_reports": case_reports,
        "trust_rules": {
            "product_loop_required": True,
            "dual_loop_gate_required": True,
            "delivery_trust_receipt_required": True,
            "customer_handoff_package_required": True,
            "external_eval_receipts_supporting_only": True,
            "ai_review_only_forbidden": True,
            "full_manual_re_review_not_required_for_pass": True,
            "production_mutation_blocked": True,
            "automatic_customer_sending_blocked": True,
            "metadata_only": True,
        },
        "privacy": {
            **DELIVERY_TRUST_CASE_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "claim_boundary": {
            "current_claim": (
                "Delivery Trust Case Harness proves deterministic metadata-only "
                "end-to-end gating for controlled customer handoff."
            ),
            "not_claimed": [
                "production deployment approval",
                "real customer delivery",
                "general model correctness",
                "legal certification",
                "security certification",
            ],
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_delivery_trust_case_harness.py --check",
            "fixture_dir": "fixtures/delivery-trust-case",
        },
    }
    dual_loop.assert_metadata_only(report, label=DELIVERY_TRUST_CASE_REPORT_SCHEMA_VERSION)
    return report


def write_artifact_set(output_dir: str | Path, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        dual_loop.write_json(target / filename, payload)
