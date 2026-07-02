"""Cognitive Black Box delivery scenario harness.

This layer connects CBB self-intake receipts to the three product-development
loops: Agentic Coding, Developer Feedback, and External Feedback. It remains
metadata-only and deterministic. It does not call models, store raw external
feedback text, inspect raw diffs, start daemons, or mutate production systems.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from study_anything.core import cbb_protocol, cbb_receipt_chain, dual_loop


CBB_DELIVERY_SCENARIO_SCHEMA_VERSION = "cbb-delivery-scenario-v1"
CBB_EXTERNAL_FEEDBACK_INTAKE_SCHEMA_VERSION = "cbb-external-feedback-intake-v1"
CBB_TRI_LOOP_RUN_SCHEMA_VERSION = "cbb-tri-loop-run-v1"
CBB_DELIVERY_HARNESS_REPORT_SCHEMA_VERSION = (
    "cbb-delivery-scenario-harness-verification-v1"
)

CASE_IDS = (
    "pass",
    "blocked-missing-developer-reconstruction",
    "blocked-risk-over-budget",
    "blocked-external-scope-expansion",
    "blocked-stale-receipt-chain",
    "blocked-ai-review-only",
)

ALLOWED_SCENARIO_STATUSES = ("ready", "blocked")
ALLOWED_TRI_LOOP_STATUSES = ("allowed", "blocked")
ALLOWED_TRI_LOOP_DECISIONS = ("promote_next_sandbox_level", "block_delivery_scenario")
ALLOWED_FEEDBACK_SCOPES = (
    "sandbox_level_1",
    "sandbox_level_2",
    "controlled_customer_handoff",
    "production_customer_handoff",
)
ALLOWED_PROMOTION_SCOPES = (
    "sandbox_level_1",
    "sandbox_level_2",
    "controlled_customer_handoff",
)

EXTERNAL_FEEDBACK_PRIVACY_FLAGS = {
    **cbb_protocol.CBB_PRIVACY_FLAGS,
    "external_feedback_original_text_included": False,
    "external_feedback_user_identity_included": False,
    "external_feedback_private_context_included": False,
    "external_feedback_raw_payload_included": False,
}


class CBBDeliveryHarnessError(ValueError):
    """Raised when CBB delivery scenario evidence is unsafe or invalid."""


def _base_artifact(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(EXTERNAL_FEEDBACK_PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise CBBDeliveryHarnessError(f"{label}.{key} must be an object")
    return value


def _require_nonempty_list(payload: Mapping[str, Any], key: str, *, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise CBBDeliveryHarnessError(f"{label}.{key} must be a non-empty list")
    return value


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    cbb_protocol._validate_privacy(payload, label=label)  # noqa: SLF001
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in EXTERNAL_FEEDBACK_PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise CBBDeliveryHarnessError(f"{label}.privacy.{key} must be {expected!r}")


def _validate_isolation(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.validate_isolation(payload, label=label)


def build_delivery_scenario(
    case_id: str,
    *,
    missing_developer_reconstruction: bool = False,
    risk_over_budget: bool = False,
    ai_review_only: bool = False,
) -> dict[str, Any]:
    """Build a deterministic metadata-only delivery scenario."""

    developer_present = not missing_developer_reconstruction
    scenario = {
        **_base_artifact(CBB_DELIVERY_SCENARIO_SCHEMA_VERSION),
        "scenario_id": f"cbb-delivery-scenario-{case_id}",
        "project_id": cbb_receipt_chain.PROJECT_ID,
        "case_id": case_id,
        "source": cbb_receipt_chain.default_pr_285_source(),
        "scenario_type": "controlled_ai_delivery",
        "candidate": {
            "candidate_ref": "github-pr:285",
            "receipt_chain_ref": "receipt-chain.json",
            "self_intake_ref": "self-intake-receipt.json",
            "delivery_evidence_pack_ref": "delivery-evidence-pack.json",
        },
        "loops": {
            "agentic_coding_loop": {
                "loop_ref": "agentic-coding-loop",
                "delivery_artifact_ref": "github-pr:285",
                "sandbox_receipt_ref": "receipt-chain.json",
                "self_intake_ref": "self-intake-receipt.json",
                "ai_review_only": ai_review_only,
                "model_calls_performed": False,
                "production_mutation_allowed": False,
            },
            "developer_feedback_loop": {
                "loop_ref": "developer-feedback-loop",
                "active_reconstruction_required": True,
                "developer_reconstruction_present": developer_present,
                "reconstruction_ref": (
                    "reviewer-reconstruction-receipt.json" if developer_present else None
                ),
                "passive_attention_only_sufficient": False,
            },
            "external_feedback_loop": {
                "loop_ref": "external-feedback-loop",
                "structured_intake_ref": "external-feedback-intake.json",
                "raw_feedback_access_required": False,
                "external_feedback_original_text_stored": False,
            },
        },
        "risk_budget": {
            "budget_level": "medium",
            "observed_level": "high" if risk_over_budget else "medium",
            "within_budget": not risk_over_budget,
            "maximum_scope": "controlled_customer_handoff",
            "production_mutation_allowed": False,
            "irreversible_external_effects_allowed": False,
        },
        "promotion_policy": {
            "allowed_requested_scopes": list(ALLOWED_PROMOTION_SCOPES),
            "next_sandbox_level": "sandbox_level_2",
            "requires_all_three_loops": True,
            "neither_loop_may_dominate": True,
        },
        "status": "blocked" if risk_over_budget else "ready",
        "claim_boundary": {
            "current_claim": (
                "This scenario may promote an AI delivery only when agentic, "
                "developer, and external feedback loops all pass inside metadata-only "
                "CBB evidence boundaries."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
            ],
        },
    }
    return validate_delivery_scenario(scenario)


def build_external_feedback_intake(
    case_id: str,
    *,
    requested_scope: str = "controlled_customer_handoff",
    attributed: bool = True,
) -> dict[str, Any]:
    intake = {
        **_base_artifact(CBB_EXTERNAL_FEEDBACK_INTAKE_SCHEMA_VERSION),
        "feedback_intake_id": f"external-feedback-intake-{case_id}",
        "project_id": cbb_receipt_chain.PROJECT_ID,
        "source": {
            "source_type": "external_platform_feedback",
            "platform_ref": "platform:workbuddy-compatible",
            "feedback_ref": f"external-feedback:{case_id}",
            "collected_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        },
        "classification": {
            "signal_type": "delivery_acceptance_boundary",
            "severity": "medium",
            "requested_scope": requested_scope,
            "summary_code": "import_path_and_trust_boundary_feedback",
            "contains_raw_feedback": False,
            "contains_customer_payload": False,
        },
        "attribution": {
            "attributed": attributed,
            "attributed_to_loop": "external_feedback_loop" if attributed else None,
            "requires_product_change": False,
            "requires_risk_budget_change": requested_scope == "production_customer_handoff",
        },
        "handling": {
            "structured_artifact_bridge_only": True,
            "manual_upload_required": False,
            "production_mutation_allowed": False,
            "model_call_required": False,
        },
        "claim_boundary": {
            "current_claim": (
                "External feedback was reduced to metadata-only scope and attribution "
                "signals for the CBB delivery harness."
            ),
            "not_claimed": [
                "full customer sentiment",
                "raw feedback preservation",
                "production approval",
                "legal certification",
            ],
        },
    }
    return validate_external_feedback_intake(intake)


def validate_delivery_scenario(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CBB_DELIVERY_SCENARIO_SCHEMA_VERSION)
    if payload.get("schema_version") != CBB_DELIVERY_SCENARIO_SCHEMA_VERSION:
        raise CBBDeliveryHarnessError("Invalid delivery scenario schema_version")
    for key in (
        "scenario_id",
        "project_id",
        "case_id",
        "source",
        "scenario_type",
        "candidate",
        "loops",
        "risk_budget",
        "promotion_policy",
        "status",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBDeliveryHarnessError(f"delivery scenario missing {key}")
    if payload.get("status") not in ALLOWED_SCENARIO_STATUSES:
        raise CBBDeliveryHarnessError("delivery scenario status is invalid")
    source = _require_object(payload, "source", label="delivery_scenario")
    if source.get("merge_commit") != cbb_receipt_chain.PR_285_MERGE_COMMIT:
        raise CBBDeliveryHarnessError("delivery scenario source commit is stale")
    loops = _require_object(payload, "loops", label="delivery_scenario")
    for loop_key in (
        "agentic_coding_loop",
        "developer_feedback_loop",
        "external_feedback_loop",
    ):
        _require_object(loops, loop_key, label="delivery_scenario.loops")
    agentic = _require_object(loops, "agentic_coding_loop", label="delivery_scenario.loops")
    if agentic.get("model_calls_performed") is not False:
        raise CBBDeliveryHarnessError("delivery scenario must not perform model calls")
    if agentic.get("production_mutation_allowed") is not False:
        raise CBBDeliveryHarnessError("delivery scenario must block production mutation")
    developer = _require_object(loops, "developer_feedback_loop", label="delivery_scenario.loops")
    if developer.get("active_reconstruction_required") is not True:
        raise CBBDeliveryHarnessError("developer reconstruction must be active")
    if developer.get("passive_attention_only_sufficient") is not False:
        raise CBBDeliveryHarnessError("passive attention alone is not sufficient")
    risk_budget = _require_object(payload, "risk_budget", label="delivery_scenario")
    if risk_budget.get("production_mutation_allowed") is not False:
        raise CBBDeliveryHarnessError("risk budget must block production mutation")
    if risk_budget.get("irreversible_external_effects_allowed") is not False:
        raise CBBDeliveryHarnessError("risk budget must block irreversible effects")
    policy = _require_object(payload, "promotion_policy", label="delivery_scenario")
    allowed = _require_nonempty_list(
        policy,
        "allowed_requested_scopes",
        label="delivery_scenario.promotion_policy",
    )
    for scope in allowed:
        if scope not in ALLOWED_PROMOTION_SCOPES:
            raise CBBDeliveryHarnessError("delivery scenario promotion scope is invalid")
    if policy.get("requires_all_three_loops") is not True:
        raise CBBDeliveryHarnessError("delivery scenario must require all three loops")
    if policy.get("neither_loop_may_dominate") is not True:
        raise CBBDeliveryHarnessError("delivery scenario must keep loop parity")
    claim = _require_object(payload, "claim_boundary", label="delivery_scenario")
    _require_nonempty_list(claim, "not_claimed", label="delivery_scenario.claim_boundary")
    _validate_isolation(payload, label="delivery_scenario")
    _validate_privacy(payload, label="delivery_scenario")
    return dict(payload)


def validate_external_feedback_intake(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CBB_EXTERNAL_FEEDBACK_INTAKE_SCHEMA_VERSION)
    if payload.get("schema_version") != CBB_EXTERNAL_FEEDBACK_INTAKE_SCHEMA_VERSION:
        raise CBBDeliveryHarnessError("Invalid external feedback intake schema_version")
    for key in (
        "feedback_intake_id",
        "project_id",
        "source",
        "classification",
        "attribution",
        "handling",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBDeliveryHarnessError(f"external feedback intake missing {key}")
    classification = _require_object(payload, "classification", label="external_feedback")
    requested_scope = classification.get("requested_scope")
    if requested_scope not in ALLOWED_FEEDBACK_SCOPES:
        raise CBBDeliveryHarnessError("external feedback requested scope is invalid")
    if classification.get("contains_raw_feedback") is not False:
        raise CBBDeliveryHarnessError("external feedback must not contain raw feedback")
    if classification.get("contains_customer_payload") is not False:
        raise CBBDeliveryHarnessError("external feedback must not contain customer payload")
    attribution = _require_object(payload, "attribution", label="external_feedback")
    if attribution.get("attributed") not in (True, False):
        raise CBBDeliveryHarnessError("external feedback attribution flag is invalid")
    handling = _require_object(payload, "handling", label="external_feedback")
    if handling.get("structured_artifact_bridge_only") is not True:
        raise CBBDeliveryHarnessError("external feedback must use artifact bridge only")
    if handling.get("production_mutation_allowed") is not False:
        raise CBBDeliveryHarnessError("external feedback must not mutate production")
    if handling.get("model_call_required") is not False:
        raise CBBDeliveryHarnessError("external feedback must not require model calls")
    claim = _require_object(payload, "claim_boundary", label="external_feedback")
    _require_nonempty_list(claim, "not_claimed", label="external_feedback.claim_boundary")
    _validate_isolation(payload, label="external_feedback")
    _validate_privacy(payload, label="external_feedback")
    return dict(payload)


def _safe_validate_receipt_chain(receipt_chain: Mapping[str, Any]) -> tuple[bool, str | None, dict[str, Any]]:
    try:
        validated = cbb_receipt_chain.validate_receipt_chain(receipt_chain)
    except Exception as exc:  # noqa: BLE001 - tri-loop receipt captures deterministic reason.
        message = str(exc)
        if "stale" in message:
            return False, "stale_receipt_chain", dict(receipt_chain)
        return False, "receipt_chain_invalid", dict(receipt_chain)
    return True, None, validated


def _safe_validate_self_intake(
    self_intake: Mapping[str, Any],
    receipt_chain: Mapping[str, Any],
) -> tuple[bool, str | None, dict[str, Any]]:
    try:
        validated = cbb_receipt_chain.validate_self_intake_receipt(
            self_intake,
            receipt_chain=receipt_chain,
        )
    except Exception as exc:  # noqa: BLE001 - tri-loop receipt captures deterministic reason.
        message = str(exc)
        if "AI-review-only" in message:
            return False, "ai_review_only_evidence_rejected", dict(self_intake)
        if "reviewer" in message:
            return False, "developer_reconstruction_missing", dict(self_intake)
        return False, "self_intake_invalid", dict(self_intake)
    return True, None, validated


def build_tri_loop_run(
    scenario: Mapping[str, Any],
    external_feedback: Mapping[str, Any],
    receipt_chain: Mapping[str, Any],
    self_intake: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one CBB delivery scenario across all three feedback loops."""

    scenario_payload = validate_delivery_scenario(scenario)
    external_payload = validate_external_feedback_intake(external_feedback)
    chain_ok, chain_reason, chain_payload = _safe_validate_receipt_chain(receipt_chain)
    self_ok, self_reason, self_payload = _safe_validate_self_intake(
        self_intake,
        chain_payload,
    )

    reasons: list[str] = []
    if chain_reason:
        reasons.append(chain_reason)
    if self_reason and self_reason not in reasons:
        reasons.append(self_reason)

    loops = scenario_payload["loops"]
    agentic = loops["agentic_coding_loop"]
    developer = loops["developer_feedback_loop"]
    external = external_payload["classification"]
    attribution = external_payload["attribution"]
    risk = scenario_payload["risk_budget"]
    policy = scenario_payload["promotion_policy"]

    if agentic.get("ai_review_only") is True:
        reasons.append("ai_review_only_evidence_rejected")
    if risk.get("within_budget") is not True:
        reasons.append("sandbox_risk_outside_budget")
    if developer.get("developer_reconstruction_present") is not True:
        reasons.append("developer_reconstruction_missing")
    if attribution.get("attributed") is not True:
        reasons.append("external_feedback_unattributed")
    if external.get("requested_scope") not in policy["allowed_requested_scopes"]:
        reasons.append("external_scope_expansion")

    unique_reasons = list(dict.fromkeys(reasons))
    status = "allowed" if not unique_reasons and chain_ok and self_ok else "blocked"
    decision = "promote_next_sandbox_level" if status == "allowed" else "block_delivery_scenario"
    loop_statuses = {
        "agentic_coding_loop": "passed"
        if chain_ok
        and self_ok
        and agentic.get("ai_review_only") is not True
        and risk.get("within_budget") is True
        else "blocked",
        "developer_feedback_loop": "passed"
        if developer.get("developer_reconstruction_present") is True
        else "blocked",
        "external_feedback_loop": "passed"
        if attribution.get("attributed") is True
        and external.get("requested_scope") in policy["allowed_requested_scopes"]
        else "blocked",
    }
    run = {
        **_base_artifact(CBB_TRI_LOOP_RUN_SCHEMA_VERSION),
        "tri_loop_run_id": f"tri-loop-run-{scenario_payload['case_id']}",
        "project_id": cbb_receipt_chain.PROJECT_ID,
        "scenario_id": scenario_payload["scenario_id"],
        "case_id": scenario_payload["case_id"],
        "source": cbb_receipt_chain.default_pr_285_source(),
        "status": status,
        "decision": decision,
        "reasons": unique_reasons,
        "loop_statuses": loop_statuses,
        "loop_parity": {
            "agentic_loop_required": True,
            "developer_loop_required": True,
            "external_loop_required": True,
            "neither_loop_may_dominate": True,
        },
        "evidence_refs": {
            "delivery_scenario_ref": "delivery-scenario.json",
            "external_feedback_intake_ref": "external-feedback-intake.json",
            "receipt_chain_ref": "receipt-chain.json",
            "receipt_chain_digest": chain_payload.get("chain_digest"),
            "self_intake_ref": "self-intake-receipt.json",
            "self_intake_id": self_payload.get("self_intake_id"),
        },
        "promotion": {
            "requested_scope": external.get("requested_scope"),
            "allowed_next_scope": (
                scenario_payload["promotion_policy"]["next_sandbox_level"]
                if status == "allowed"
                else None
            ),
            "production_mutation_allowed": False,
        },
        "checks": {
            "receipt_chain_valid": chain_ok,
            "self_intake_passed": self_ok and self_payload.get("status") == "passed",
            "sandbox_risk_within_budget": risk.get("within_budget") is True,
            "developer_reconstruction_present": (
                developer.get("developer_reconstruction_present") is True
            ),
            "external_feedback_attributed": attribution.get("attributed") is True,
            "external_scope_within_policy": (
                external.get("requested_scope") in policy["allowed_requested_scopes"]
            ),
            "ai_review_only_rejected": agentic.get("ai_review_only") is not True,
            "metadata_only": True,
            "model_calls_performed": False,
            "production_mutation_blocked": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The CBB delivery scenario may promote only when agentic coding, "
                "developer reconstruction, and external feedback intake all pass."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
            ],
        },
    }
    return validate_tri_loop_run(run)


def validate_tri_loop_run(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=CBB_TRI_LOOP_RUN_SCHEMA_VERSION)
    if payload.get("schema_version") != CBB_TRI_LOOP_RUN_SCHEMA_VERSION:
        raise CBBDeliveryHarnessError("Invalid tri-loop run schema_version")
    for key in (
        "tri_loop_run_id",
        "project_id",
        "scenario_id",
        "case_id",
        "source",
        "status",
        "decision",
        "reasons",
        "loop_statuses",
        "loop_parity",
        "evidence_refs",
        "promotion",
        "checks",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise CBBDeliveryHarnessError(f"tri-loop run missing {key}")
    if payload.get("status") not in ALLOWED_TRI_LOOP_STATUSES:
        raise CBBDeliveryHarnessError("tri-loop status is invalid")
    if payload.get("decision") not in ALLOWED_TRI_LOOP_DECISIONS:
        raise CBBDeliveryHarnessError("tri-loop decision is invalid")
    reasons = payload.get("reasons")
    if not isinstance(reasons, list):
        raise CBBDeliveryHarnessError("tri-loop reasons must be a list")
    if payload.get("status") == "allowed":
        if payload.get("decision") != "promote_next_sandbox_level":
            raise CBBDeliveryHarnessError("allowed tri-loop run must promote next sandbox level")
        if reasons:
            raise CBBDeliveryHarnessError("allowed tri-loop run must have no reasons")
    else:
        if payload.get("decision") != "block_delivery_scenario":
            raise CBBDeliveryHarnessError("blocked tri-loop run must block scenario")
        if not reasons:
            raise CBBDeliveryHarnessError("blocked tri-loop run must include reasons")
    loop_statuses = _require_object(payload, "loop_statuses", label="tri_loop")
    for loop_key in (
        "agentic_coding_loop",
        "developer_feedback_loop",
        "external_feedback_loop",
    ):
        if loop_statuses.get(loop_key) not in ("passed", "blocked"):
            raise CBBDeliveryHarnessError(f"tri-loop {loop_key} status is invalid")
    parity = _require_object(payload, "loop_parity", label="tri_loop")
    for key in (
        "agentic_loop_required",
        "developer_loop_required",
        "external_loop_required",
        "neither_loop_may_dominate",
    ):
        if parity.get(key) is not True:
            raise CBBDeliveryHarnessError(f"tri-loop parity missing {key}")
    checks = _require_object(payload, "checks", label="tri_loop")
    if checks.get("metadata_only") is not True:
        raise CBBDeliveryHarnessError("tri-loop must be metadata-only")
    if checks.get("model_calls_performed") is not False:
        raise CBBDeliveryHarnessError("tri-loop must not perform model calls")
    if checks.get("production_mutation_blocked") is not True:
        raise CBBDeliveryHarnessError("tri-loop must block production mutation")
    claim = _require_object(payload, "claim_boundary", label="tri_loop")
    _require_nonempty_list(claim, "not_claimed", label="tri_loop.claim_boundary")
    _validate_isolation(payload, label="tri_loop")
    _validate_privacy(payload, label="tri_loop")
    return dict(payload)


def _stale_receipt_chain(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    chain = deepcopy(artifacts["receipt-chain.json"])
    chain["source"]["merge_commit"] = "70697083d3c576d758fbd9639df3fe3b582ec72a"
    chain["chain_digest"] = cbb_receipt_chain.compute_receipt_chain_digest(chain)
    return chain


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise CBBDeliveryHarnessError(f"Unknown CBB delivery harness case: {case_id}")
    base = cbb_receipt_chain.build_pr_285_self_intake_artifacts()
    scenario = build_delivery_scenario(
        case_id,
        missing_developer_reconstruction=case_id
        == "blocked-missing-developer-reconstruction",
        risk_over_budget=case_id == "blocked-risk-over-budget",
        ai_review_only=case_id == "blocked-ai-review-only",
    )
    requested_scope = (
        "production_customer_handoff"
        if case_id == "blocked-external-scope-expansion"
        else "controlled_customer_handoff"
    )
    external = build_external_feedback_intake(case_id, requested_scope=requested_scope)
    receipt_chain = (
        _stale_receipt_chain(base)
        if case_id == "blocked-stale-receipt-chain"
        else base["receipt-chain.json"]
    )
    tri_loop = build_tri_loop_run(
        scenario,
        external,
        receipt_chain,
        base["self-intake-receipt.json"],
    )
    return {
        "delivery-scenario.json": scenario,
        "external-feedback-intake.json": external,
        "receipt-chain.json": receipt_chain,
        "self-intake-receipt.json": base["self-intake-receipt.json"],
        "tri-loop-run.json": tri_loop,
    }


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_harness_report(
    cases: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    case_reports: list[dict[str, Any]] = []
    ordered_case_ids = [case_id for case_id in CASE_IDS if case_id in cases]
    if not ordered_case_ids:
        raise CBBDeliveryHarnessError("CBB delivery harness report requires at least one case")
    for case_id in ordered_case_ids:
        tri_loop = validate_tri_loop_run(cases[case_id]["tri-loop-run.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": tri_loop["status"],
                "decision": tri_loop["decision"],
                "reasons": tri_loop["reasons"],
                "loop_statuses": tri_loop["loop_statuses"],
                "artifact_count": len(cases[case_id]),
            }
        )
    report = {
        "schema_version": CBB_DELIVERY_HARNESS_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "source": cbb_receipt_chain.default_pr_285_source(),
        "artifact_contracts": {
            "delivery_scenario": CBB_DELIVERY_SCENARIO_SCHEMA_VERSION,
            "external_feedback_intake": CBB_EXTERNAL_FEEDBACK_INTAKE_SCHEMA_VERSION,
            "tri_loop_run": CBB_TRI_LOOP_RUN_SCHEMA_VERSION,
        },
        "case_reports": case_reports,
        "trust_rules": {
            "all_three_loops_required": True,
            "neither_loop_may_dominate": True,
            "receipt_chain_must_be_current": True,
            "developer_reconstruction_required": True,
            "external_feedback_must_be_structured": True,
            "external_scope_expansion_blocks": True,
            "ai_review_only_blocks": True,
            "metadata_only": True,
        },
        "privacy": {
            **EXTERNAL_FEEDBACK_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
            "raw_diff_included": False,
            "raw_external_feedback_text_included": False,
            "real_customer_data_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "claim_boundary": {
            "current_claim": (
                "CBB delivery scenario harness proves metadata-only tri-loop gating "
                "for controlled AI delivery promotion."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
            ],
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cbb_delivery_harness.py --check",
            "fixture_dir": "fixtures/cbb-delivery-harness",
        },
    }
    dual_loop.assert_metadata_only(report, label=CBB_DELIVERY_HARNESS_REPORT_SCHEMA_VERSION)
    return report


def write_artifact_set(output_dir: str | Path, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        cbb_protocol.write_json(target / filename, payload)
