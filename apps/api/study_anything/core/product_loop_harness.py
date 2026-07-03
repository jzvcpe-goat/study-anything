"""Metadata-only product development loop harness.

This layer turns the three product-development loops into deterministic
artifacts:

- Agentic Coding Loop: minutes, coding agent to product spec/evals.
- Developer Feedback Loop: hours, developer vision to product spec/evals.
- External Feedback Loop: days, external feedback to developer vision.

The harness is intentionally local-first and metadata-only. It does not call
models, read raw diffs, store raw feedback, start daemons, or mutate production.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from study_anything.core import cbb_protocol, dual_loop


PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION = "product-loop-scenario-v1"
PRODUCT_LOOP_RUN_SCHEMA_VERSION = "product-loop-run-v1"
PRODUCT_LOOP_HARNESS_REPORT_SCHEMA_VERSION = "product-loop-harness-verification-v1"

CASE_IDS = (
    "pass",
    "blocked-missing-product-spec-evals",
    "blocked-missing-developer-vision",
    "blocked-external-scope-expansion",
    "blocked-ai-review-only",
    "blocked-loop-dominance",
)

ALLOWED_SCENARIO_STATUSES = ("ready", "blocked")
ALLOWED_RUN_STATUSES = ("allowed", "blocked")
ALLOWED_RUN_DECISIONS = ("promote_to_delivery_trust_harness", "block_product_loop")
ALLOWED_FEEDBACK_SCOPES = (
    "spec_eval_update",
    "developer_vision_update",
    "controlled_customer_handoff",
    "production_customer_handoff",
)
ALLOWED_PROMOTION_SCOPES = (
    "spec_eval_update",
    "developer_vision_update",
    "controlled_customer_handoff",
)

PRODUCT_LOOP_PRIVACY_FLAGS = {
    **cbb_protocol.CBB_PRIVACY_FLAGS,
    "raw_diff_included": False,
    "raw_external_feedback_text_included": False,
    "raw_product_spec_included": False,
    "customer_payload_included": False,
    "production_payload_included": False,
    "model_prompts_included": False,
    "agent_credentials_included": False,
}


class ProductLoopHarnessError(ValueError):
    """Raised when product loop harness evidence is unsafe or invalid."""


def _base_artifact(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(PRODUCT_LOOP_PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ProductLoopHarnessError(f"{label}.{key} must be an object")
    return value


def _require_nonempty_list(payload: Mapping[str, Any], key: str, *, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ProductLoopHarnessError(f"{label}.{key} must be a non-empty list")
    return value


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    cbb_protocol._validate_privacy(payload, label=label)  # noqa: SLF001
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRODUCT_LOOP_PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise ProductLoopHarnessError(f"{label}.privacy.{key} must be {expected!r}")


def _validate_isolation(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.validate_isolation(payload, label=label)


def build_product_loop_scenario(
    case_id: str,
    *,
    missing_product_spec_evals: bool = False,
    missing_developer_vision: bool = False,
    external_scope: str = "controlled_customer_handoff",
    ai_review_only: bool = False,
    loop_dominance: bool = False,
) -> dict[str, Any]:
    """Build one deterministic product-loop scenario."""

    spec_evals_present = not missing_product_spec_evals
    developer_vision_present = not missing_developer_vision
    scenario = {
        **_base_artifact(PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION),
        "scenario_id": f"product-loop-scenario-{case_id}",
        "project_id": "study-anything",
        "case_id": case_id,
        "scenario_type": "tri_loop_product_development",
        "source": {
            "source_type": "deterministic_fixture",
            "source_ref": f"product-loop:{case_id}",
            "content_digest": dual_loop.sha256_text(f"product-loop:{case_id}"),
        },
        "loops": {
            "agentic_coding_loop": {
                "time_scale": "minutes",
                "actor_ref": "coding-agent",
                "input_ref": "product-spec-evals.json" if spec_evals_present else None,
                "output_ref": "candidate-change-metadata.json",
                "product_spec_evals_present": spec_evals_present,
                "ai_review_only": ai_review_only,
                "model_calls_required": False,
                "production_mutation_allowed": False,
            },
            "developer_feedback_loop": {
                "time_scale": "hours",
                "actor_ref": "developer-vision",
                "developer_vision_present": developer_vision_present,
                "active_reconstruction_required": True,
                "passive_attention_only_sufficient": False,
                "reconstruction_ref": (
                    "developer-reconstruction-summary.json"
                    if developer_vision_present
                    else None
                ),
            },
            "external_feedback_loop": {
                "time_scale": "days",
                "actor_ref": "external-feedback",
                "structured_intake_ref": "external-feedback-intake.json",
                "requested_scope": external_scope,
                "raw_feedback_access_required": False,
                "external_feedback_original_text_stored": False,
            },
        },
        "loop_contract": {
            "all_three_loops_required": True,
            "neither_loop_may_dominate": not loop_dominance,
            "agentic_loop_may_promote_alone": False,
            "developer_loop_may_promote_alone": False,
            "external_loop_may_promote_alone": False,
        },
        "promotion_policy": {
            "allowed_requested_scopes": list(ALLOWED_PROMOTION_SCOPES),
            "allowed_next_layer": "delivery_trust_harness",
            "production_mutation_allowed": False,
            "irreversible_external_effects_allowed": False,
        },
        "status": (
            "blocked"
            if missing_product_spec_evals
            or missing_developer_vision
            or ai_review_only
            or loop_dominance
            or external_scope not in ALLOWED_PROMOTION_SCOPES
            else "ready"
        ),
        "claim_boundary": {
            "current_claim": (
                "The product-development loop may promote a candidate to the "
                "Delivery Trust Harness only when agentic coding, developer "
                "vision, and external feedback loops all pass."
            ),
            "not_claimed": [
                "production readiness",
                "customer outcome guarantee",
                "general model correctness",
                "full manual review completion",
            ],
        },
    }
    return validate_product_loop_scenario(scenario)


def validate_product_loop_scenario(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION)
    if payload.get("schema_version") != PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION:
        raise ProductLoopHarnessError("Invalid product loop scenario schema_version")
    for key in (
        "scenario_id",
        "project_id",
        "case_id",
        "scenario_type",
        "source",
        "loops",
        "loop_contract",
        "promotion_policy",
        "status",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise ProductLoopHarnessError(f"product loop scenario missing {key}")
    if payload.get("scenario_type") != "tri_loop_product_development":
        raise ProductLoopHarnessError("product loop scenario type is invalid")
    if payload.get("status") not in ALLOWED_SCENARIO_STATUSES:
        raise ProductLoopHarnessError("product loop scenario status is invalid")
    loops = _require_object(payload, "loops", label="product_loop_scenario")
    for loop_key in (
        "agentic_coding_loop",
        "developer_feedback_loop",
        "external_feedback_loop",
    ):
        _require_object(loops, loop_key, label="product_loop_scenario.loops")
    agentic = _require_object(loops, "agentic_coding_loop", label="product_loop_scenario.loops")
    if agentic.get("time_scale") != "minutes":
        raise ProductLoopHarnessError("agentic coding loop must be minutes scale")
    if agentic.get("model_calls_required") is not False:
        raise ProductLoopHarnessError("product loop must not require model calls")
    if agentic.get("production_mutation_allowed") is not False:
        raise ProductLoopHarnessError("product loop must block production mutation")
    developer = _require_object(loops, "developer_feedback_loop", label="product_loop_scenario.loops")
    if developer.get("time_scale") != "hours":
        raise ProductLoopHarnessError("developer feedback loop must be hours scale")
    if developer.get("active_reconstruction_required") is not True:
        raise ProductLoopHarnessError("developer loop must require active reconstruction")
    if developer.get("passive_attention_only_sufficient") is not False:
        raise ProductLoopHarnessError("passive attention alone is insufficient")
    external = _require_object(loops, "external_feedback_loop", label="product_loop_scenario.loops")
    if external.get("time_scale") != "days":
        raise ProductLoopHarnessError("external feedback loop must be days scale")
    if external.get("requested_scope") not in ALLOWED_FEEDBACK_SCOPES:
        raise ProductLoopHarnessError("external feedback requested scope is invalid")
    if external.get("raw_feedback_access_required") is not False:
        raise ProductLoopHarnessError("external loop must not require raw feedback access")
    contract = _require_object(payload, "loop_contract", label="product_loop_scenario")
    if contract.get("all_three_loops_required") is not True:
        raise ProductLoopHarnessError("product loop must require all three loops")
    if contract.get("agentic_loop_may_promote_alone") is not False:
        raise ProductLoopHarnessError("agentic loop must not promote alone")
    if contract.get("developer_loop_may_promote_alone") is not False:
        raise ProductLoopHarnessError("developer loop must not promote alone")
    if contract.get("external_loop_may_promote_alone") is not False:
        raise ProductLoopHarnessError("external loop must not promote alone")
    policy = _require_object(payload, "promotion_policy", label="product_loop_scenario")
    allowed = _require_nonempty_list(
        policy,
        "allowed_requested_scopes",
        label="product_loop_scenario.promotion_policy",
    )
    for scope in allowed:
        if scope not in ALLOWED_PROMOTION_SCOPES:
            raise ProductLoopHarnessError("product loop promotion scope is invalid")
    if policy.get("production_mutation_allowed") is not False:
        raise ProductLoopHarnessError("promotion policy must block production mutation")
    if policy.get("irreversible_external_effects_allowed") is not False:
        raise ProductLoopHarnessError("promotion policy must block irreversible effects")
    claim = _require_object(payload, "claim_boundary", label="product_loop_scenario")
    _require_nonempty_list(claim, "not_claimed", label="product_loop_scenario.claim_boundary")
    _validate_isolation(payload, label="product_loop_scenario")
    _validate_privacy(payload, label="product_loop_scenario")
    return dict(payload)


def build_product_loop_run(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one product-development scenario across the three loops."""

    scenario_payload = validate_product_loop_scenario(scenario)
    loops = scenario_payload["loops"]
    agentic = loops["agentic_coding_loop"]
    developer = loops["developer_feedback_loop"]
    external = loops["external_feedback_loop"]
    contract = scenario_payload["loop_contract"]
    policy = scenario_payload["promotion_policy"]

    reasons: list[str] = []
    if agentic.get("product_spec_evals_present") is not True:
        reasons.append("product_spec_evals_missing")
    if agentic.get("ai_review_only") is True:
        reasons.append("ai_review_only_evidence_rejected")
    if developer.get("developer_vision_present") is not True:
        reasons.append("developer_vision_missing")
    if external.get("requested_scope") not in policy["allowed_requested_scopes"]:
        reasons.append("external_feedback_scope_expansion")
    if contract.get("neither_loop_may_dominate") is not True:
        reasons.append("loop_dominance_detected")

    unique_reasons = list(dict.fromkeys(reasons))
    status = "allowed" if not unique_reasons else "blocked"
    decision = "promote_to_delivery_trust_harness" if status == "allowed" else "block_product_loop"
    loop_statuses = {
        "agentic_coding_loop": "passed"
        if agentic.get("product_spec_evals_present") is True
        and agentic.get("ai_review_only") is not True
        else "blocked",
        "developer_feedback_loop": "passed"
        if developer.get("developer_vision_present") is True
        else "blocked",
        "external_feedback_loop": "passed"
        if external.get("requested_scope") in policy["allowed_requested_scopes"]
        else "blocked",
    }
    run = {
        **_base_artifact(PRODUCT_LOOP_RUN_SCHEMA_VERSION),
        "run_id": f"product-loop-run-{scenario_payload['case_id']}",
        "project_id": scenario_payload["project_id"],
        "scenario_id": scenario_payload["scenario_id"],
        "case_id": scenario_payload["case_id"],
        "source": scenario_payload["source"],
        "status": status,
        "decision": decision,
        "reasons": unique_reasons,
        "loop_statuses": loop_statuses,
        "loop_parity": {
            "agentic_loop_required": True,
            "developer_loop_required": True,
            "external_loop_required": True,
            "neither_loop_may_dominate": contract.get("neither_loop_may_dominate") is True,
        },
        "time_scales": {
            "agentic_coding_loop": "minutes",
            "developer_feedback_loop": "hours",
            "external_feedback_loop": "days",
        },
        "evidence_refs": {
            "scenario_ref": "product-loop-scenario.json",
            "product_spec_evals_ref": agentic.get("input_ref"),
            "developer_vision_ref": developer.get("reconstruction_ref"),
            "external_feedback_intake_ref": external.get("structured_intake_ref"),
        },
        "promotion": {
            "requested_scope": external.get("requested_scope"),
            "allowed_next_layer": (
                policy["allowed_next_layer"] if status == "allowed" else None
            ),
            "production_mutation_allowed": False,
        },
        "checks": {
            "product_spec_evals_present": agentic.get("product_spec_evals_present") is True,
            "developer_vision_present": developer.get("developer_vision_present") is True,
            "external_feedback_scope_within_policy": (
                external.get("requested_scope") in policy["allowed_requested_scopes"]
            ),
            "ai_review_only_rejected": agentic.get("ai_review_only") is not True,
            "all_three_loops_required": contract.get("all_three_loops_required") is True,
            "neither_loop_may_dominate": contract.get("neither_loop_may_dominate") is True,
            "metadata_only": True,
            "model_calls_performed": False,
            "production_mutation_blocked": True,
        },
        "claim_boundary": {
            "current_claim": (
                "This product-development loop run may promote only to the Delivery "
                "Trust Harness, not to production or unrestricted customer delivery."
            ),
            "not_claimed": [
                "production readiness",
                "customer outcome guarantee",
                "general model correctness",
                "legal certification",
            ],
        },
    }
    return validate_product_loop_run(run)


def validate_product_loop_run(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=PRODUCT_LOOP_RUN_SCHEMA_VERSION)
    if payload.get("schema_version") != PRODUCT_LOOP_RUN_SCHEMA_VERSION:
        raise ProductLoopHarnessError("Invalid product loop run schema_version")
    for key in (
        "run_id",
        "project_id",
        "scenario_id",
        "case_id",
        "source",
        "status",
        "decision",
        "reasons",
        "loop_statuses",
        "loop_parity",
        "time_scales",
        "evidence_refs",
        "promotion",
        "checks",
        "claim_boundary",
        "isolation",
        "privacy",
    ):
        if key not in payload:
            raise ProductLoopHarnessError(f"product loop run missing {key}")
    if payload.get("status") not in ALLOWED_RUN_STATUSES:
        raise ProductLoopHarnessError("product loop run status is invalid")
    if payload.get("decision") not in ALLOWED_RUN_DECISIONS:
        raise ProductLoopHarnessError("product loop run decision is invalid")
    reasons = payload.get("reasons")
    if not isinstance(reasons, list):
        raise ProductLoopHarnessError("product loop run reasons must be a list")
    if payload.get("status") == "allowed":
        if payload.get("decision") != "promote_to_delivery_trust_harness":
            raise ProductLoopHarnessError("allowed product loop must promote to delivery harness")
        if reasons:
            raise ProductLoopHarnessError("allowed product loop must have no reasons")
    else:
        if payload.get("decision") != "block_product_loop":
            raise ProductLoopHarnessError("blocked product loop must block")
        if not reasons:
            raise ProductLoopHarnessError("blocked product loop must include reasons")
    loop_statuses = _require_object(payload, "loop_statuses", label="product_loop_run")
    for loop_key in (
        "agentic_coding_loop",
        "developer_feedback_loop",
        "external_feedback_loop",
    ):
        if loop_statuses.get(loop_key) not in ("passed", "blocked"):
            raise ProductLoopHarnessError(f"product loop {loop_key} status is invalid")
    parity = _require_object(payload, "loop_parity", label="product_loop_run")
    for key in (
        "agentic_loop_required",
        "developer_loop_required",
        "external_loop_required",
    ):
        if parity.get(key) is not True:
            raise ProductLoopHarnessError(f"product loop parity missing {key}")
    if payload.get("status") == "allowed" and parity.get("neither_loop_may_dominate") is not True:
        raise ProductLoopHarnessError("allowed product loop must preserve loop parity")
    if "loop_dominance_detected" in reasons and parity.get("neither_loop_may_dominate") is not False:
        raise ProductLoopHarnessError("loop dominance reason requires failed parity")
    time_scales = _require_object(payload, "time_scales", label="product_loop_run")
    if time_scales != {
        "agentic_coding_loop": "minutes",
        "developer_feedback_loop": "hours",
        "external_feedback_loop": "days",
    }:
        raise ProductLoopHarnessError("product loop time scales drifted")
    checks = _require_object(payload, "checks", label="product_loop_run")
    if checks.get("metadata_only") is not True:
        raise ProductLoopHarnessError("product loop must be metadata-only")
    if checks.get("model_calls_performed") is not False:
        raise ProductLoopHarnessError("product loop must not perform model calls")
    if checks.get("production_mutation_blocked") is not True:
        raise ProductLoopHarnessError("product loop must block production mutation")
    promotion = _require_object(payload, "promotion", label="product_loop_run")
    if promotion.get("production_mutation_allowed") is not False:
        raise ProductLoopHarnessError("product loop promotion must block production mutation")
    claim = _require_object(payload, "claim_boundary", label="product_loop_run")
    _require_nonempty_list(claim, "not_claimed", label="product_loop_run.claim_boundary")
    _validate_isolation(payload, label="product_loop_run")
    _validate_privacy(payload, label="product_loop_run")
    return dict(payload)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    if case_id not in CASE_IDS:
        raise ProductLoopHarnessError(f"Unknown product loop harness case: {case_id}")
    scenario = build_product_loop_scenario(
        case_id,
        missing_product_spec_evals=case_id == "blocked-missing-product-spec-evals",
        missing_developer_vision=case_id == "blocked-missing-developer-vision",
        external_scope=(
            "production_customer_handoff"
            if case_id == "blocked-external-scope-expansion"
            else "controlled_customer_handoff"
        ),
        ai_review_only=case_id == "blocked-ai-review-only",
        loop_dominance=case_id == "blocked-loop-dominance",
    )
    run = build_product_loop_run(scenario)
    return {
        "product-loop-scenario.json": scenario,
        "product-loop-run.json": run,
    }


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_harness_report(
    cases: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    case_reports: list[dict[str, Any]] = []
    ordered_case_ids = [case_id for case_id in CASE_IDS if case_id in cases]
    if not ordered_case_ids:
        raise ProductLoopHarnessError("product loop harness report requires at least one case")
    for case_id in ordered_case_ids:
        run = validate_product_loop_run(cases[case_id]["product-loop-run.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": run["status"],
                "decision": run["decision"],
                "reasons": run["reasons"],
                "loop_statuses": run["loop_statuses"],
                "artifact_count": len(cases[case_id]),
            }
        )
    report = {
        "schema_version": PRODUCT_LOOP_HARNESS_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "artifact_contracts": {
            "product_loop_scenario": PRODUCT_LOOP_SCENARIO_SCHEMA_VERSION,
            "product_loop_run": PRODUCT_LOOP_RUN_SCHEMA_VERSION,
        },
        "case_reports": case_reports,
        "trust_rules": {
            "all_three_loops_required": True,
            "neither_loop_may_dominate": True,
            "agentic_loop_time_scale": "minutes",
            "developer_loop_time_scale": "hours",
            "external_loop_time_scale": "days",
            "ai_review_only_blocks": True,
            "external_scope_expansion_blocks": True,
            "missing_product_spec_evals_blocks": True,
            "missing_developer_vision_blocks": True,
            "metadata_only": True,
        },
        "privacy": {
            **PRODUCT_LOOP_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "claim_boundary": {
            "current_claim": (
                "Product Loop Harness proves deterministic metadata-only tri-loop "
                "product-development gating before Delivery Trust Harness promotion."
            ),
            "not_claimed": [
                "production readiness",
                "customer outcome guarantee",
                "legal certification",
                "general model correctness",
            ],
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_product_loop_harness.py --check",
            "fixture_dir": "fixtures/product-loop-harness",
        },
    }
    dual_loop.assert_metadata_only(report, label=PRODUCT_LOOP_HARNESS_REPORT_SCHEMA_VERSION)
    return report


def write_artifact_set(output_dir: str | Path, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        cbb_protocol.write_json(target / filename, payload)
