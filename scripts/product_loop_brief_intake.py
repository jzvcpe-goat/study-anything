#!/usr/bin/env python3
"""Bridge Product Spec/Eval briefs into the Product Loop Harness.

This metadata-only layer consumes a `product-spec-eval-brief-v1` artifact and
emits a bounded intake receipt. When the brief and human/product-loop boundary
checks pass, the receipt includes a Product Loop Harness scenario/run candidate.

It does not execute work, call models, store raw specs or eval prompts, mutate
production, reply to customers, or skip directly to the Delivery Trust Harness.
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

from study_anything.core import cbb_protocol, dual_loop, product_loop_harness  # noqa: E402
import product_spec_eval_authoring_gate as spec_eval_gate  # noqa: E402


RECEIPT_SCHEMA_VERSION = "product-loop-brief-intake-receipt-v1"
REPORT_SCHEMA_VERSION = "product-loop-brief-intake-gate-verification-v1"

CASE_IDS = (
    "pass",
    "blocked-missing-brief",
    "blocked-invalid-brief",
    "blocked-missing-developer-vision",
    "blocked-external-scope-expansion",
    "blocked-ai-review-only",
    "blocked-production-mutation",
    "blocked-skip-to-delivery-harness",
)

ALLOWED_NEXT_BOUNDARY = "product_loop_harness"
BLOCKED_DESTINATIONS = [
    "automatic_execution",
    "delivery_trust_harness",
    "customer_visible_reply",
    "production_mutation",
    "external_publication",
]
PRIVACY = {
    **product_loop_harness.PRODUCT_LOOP_PRIVACY_FLAGS,
    "product_spec_eval_brief_body_included": False,
    "raw_acceptance_criteria_included": False,
    "eval_prompt_included": False,
    "eval_dataset_body_included": False,
    "product_loop_brief_intake_metadata_only": True,
}
RUNTIME = {
    "deterministic_fixture": True,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
    "automatic_execution_performed": False,
    "product_work_executed": False,
    "customer_visible_action_performed": False,
    "production_mutation_performed": False,
    "delivery_trust_harness_invoked": False,
}
CLAIM_BOUNDARY = {
    "current_claim": (
        "A Product Spec/Eval brief can become a Product Loop Harness candidate "
        "only through a metadata-only intake gate that preserves three-loop "
        "parity and blocks execution or production mutation."
    ),
    "not_claimed": [
        "finished product implementation",
        "production readiness",
        "customer outcome guarantee",
        "general model correctness",
        "automatic execution approval",
        "Delivery Trust Harness completion",
    ],
}


class ProductLoopBriefIntakeError(RuntimeError):
    """Readable Product Loop brief intake failure."""


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dual_loop.dump_json(payload))


def _require_mapping(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ProductLoopBriefIntakeError(f"{label}.{key} must be an object")
    return value


def _validate_privacy_runtime(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = _require_mapping(payload, "privacy", label=label)
    for key, expected in PRIVACY.items():
        if privacy.get(key) is not expected:
            raise ProductLoopBriefIntakeError(f"{label}.privacy.{key} must be {expected!r}")
    runtime = _require_mapping(payload, "runtime", label=label)
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise ProductLoopBriefIntakeError(f"{label}.runtime.{key} must be {expected!r}")


def reject_payload(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.assert_metadata_only(payload, label=label)
    spec_eval_gate.reject_forbidden_fields(payload)


def validate_source_brief(brief: Mapping[str, Any]) -> dict[str, Any]:
    source = spec_eval_gate.validate_brief(brief)
    if source.get("ready_for_product_loop_harness") is not True:
        raise ProductLoopBriefIntakeError("source brief must be ready for Product Loop Harness")
    if source.get("ready_for_execution") is not False:
        raise ProductLoopBriefIntakeError("source brief must not be executable")
    if source.get("ready_for_delivery_trust_harness") is not False:
        raise ProductLoopBriefIntakeError("source brief must not skip to Delivery Trust Harness")
    if source.get("next_boundary") != "product_loop_harness_candidate":
        raise ProductLoopBriefIntakeError("source brief next boundary must be product loop candidate")
    return source


def _brief_ref(brief: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "brief_id": brief["brief_id"],
        "source_candidate_id": brief["source_candidate_id"],
        "source_candidate_hash": brief["source_candidate_hash"],
        "brief_hash": artifact_hash(brief),
        "body_included": False,
    }


def build_product_loop_candidate(
    brief: Mapping[str, Any],
    *,
    external_scope: str = "controlled_customer_handoff",
    ai_review_only: bool = False,
    loop_dominance: bool = False,
) -> dict[str, dict[str, Any]]:
    """Build a Product Loop Harness scenario/run from a valid brief."""

    source = validate_source_brief(brief)
    brief_hash = artifact_hash(source)
    scenario = product_loop_harness.build_product_loop_scenario(
        "pass",
        external_scope=external_scope,
        ai_review_only=ai_review_only,
        loop_dominance=loop_dominance,
    )
    scenario["scenario_id"] = f"product-loop-brief-intake-scenario-{brief_hash[:16]}"
    scenario["source"] = {
        "source_type": "product_spec_eval_brief",
        "source_ref": source["brief_id"],
        "content_digest": brief_hash,
    }
    scenario["loops"]["agentic_coding_loop"]["input_ref"] = "product-spec-eval-brief.json"
    scenario["loops"]["agentic_coding_loop"]["product_spec_eval_brief_ref"] = _brief_ref(source)
    scenario["loops"]["developer_feedback_loop"][
        "reconstruction_ref"
    ] = "product-loop-brief-intake-reconstruction.json"
    scenario["claim_boundary"] = {
        "current_claim": (
            "This Product Loop candidate was created from a metadata-only "
            "Product Spec/Eval brief, not from raw spec/eval bodies."
        ),
        "not_claimed": [
            "implementation is complete",
            "customer delivery is allowed",
            "production mutation is allowed",
            "Delivery Trust Harness has passed",
        ],
    }
    scenario = product_loop_harness.validate_product_loop_scenario(scenario)
    run = product_loop_harness.build_product_loop_run(scenario)
    return {
        "product-loop-scenario.json": scenario,
        "product-loop-run.json": run,
    }


def build_receipt(
    *,
    brief: Mapping[str, Any] | None = None,
    active_developer_vision: bool = True,
    requested_next_boundary: str = ALLOWED_NEXT_BOUNDARY,
    external_scope: str = "controlled_customer_handoff",
    ai_review_only: bool = False,
    loop_dominance: bool = False,
    raw_spec_body_requested: bool = False,
    raw_eval_body_requested: bool = False,
    automatic_execution_requested: bool = False,
    production_mutation_requested: bool = False,
    customer_visible_action_requested: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    source_brief: dict[str, Any] | None = None

    if brief is None:
        reasons.append("product_spec_eval_brief_missing")
    else:
        try:
            source_brief = validate_source_brief(brief)
        except Exception:
            reasons.append("product_spec_eval_brief_invalid")

    if not active_developer_vision:
        reasons.append("developer_vision_missing")
    if requested_next_boundary != ALLOWED_NEXT_BOUNDARY:
        reasons.append("requested_next_boundary_not_product_loop_harness")
    if external_scope not in product_loop_harness.ALLOWED_PROMOTION_SCOPES:
        reasons.append("external_feedback_scope_expansion")
    if ai_review_only:
        reasons.append("ai_review_only_evidence_rejected")
    if loop_dominance:
        reasons.append("loop_dominance_detected")
    if raw_spec_body_requested:
        reasons.append("raw_spec_body_rejected")
    if raw_eval_body_requested:
        reasons.append("raw_eval_body_rejected")
    if automatic_execution_requested:
        reasons.append("automatic_execution_rejected")
    if production_mutation_requested:
        reasons.append("production_mutation_rejected")
    if customer_visible_action_requested:
        reasons.append("customer_visible_action_rejected")

    candidate: dict[str, dict[str, Any]] | None = None
    if not reasons and source_brief is not None:
        candidate = build_product_loop_candidate(
            source_brief,
            external_scope=external_scope,
            ai_review_only=ai_review_only,
            loop_dominance=loop_dominance,
        )

    source_hash = artifact_hash(source_brief) if source_brief is not None else None
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": (
            f"product-loop-brief-intake-{source_hash[:16]}"
            if source_hash
            else "product-loop-brief-intake-blocked-source"
        ),
        "source_brief_id": source_brief.get("brief_id") if source_brief else None,
        "source_brief_hash": source_hash,
        "source_candidate_id": source_brief.get("source_candidate_id") if source_brief else None,
        "source_candidate_hash": source_brief.get("source_candidate_hash") if source_brief else None,
        "status": "created_product_loop_candidate" if candidate else "blocked",
        "decision": "create_product_loop_harness_candidate" if candidate else "block_product_loop_brief_intake",
        "blocked_reasons": reasons,
        "requested_transition": {
            "from": "product_spec_eval_brief",
            "to": requested_next_boundary,
            "external_scope": external_scope,
            "raw_spec_body_requested": raw_spec_body_requested,
            "raw_eval_body_requested": raw_eval_body_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "production_mutation_requested": production_mutation_requested,
            "customer_visible_action_requested": customer_visible_action_requested,
        },
        "intake_reconstruction": {
            "active_developer_vision_present": active_developer_vision,
            "passive_attention_only_sufficient": False,
            "reconstructed_boundaries": [
                "metadata_only_product_spec_eval_brief",
                "three_loop_product_harness_required",
                "no_raw_spec_or_eval_body",
                "no_ai_review_only_promotion",
                "no_delivery_trust_harness_skip",
                "no_customer_visible_action",
                "no_production_mutation",
            ],
        },
        "intake_policy": {
            "required_input_schema": spec_eval_gate.BRIEF_SCHEMA_VERSION,
            "allowed_next_boundary": ALLOWED_NEXT_BOUNDARY,
            "raw_spec_body_allowed": False,
            "raw_eval_body_allowed": False,
            "automatic_execution_allowed": False,
            "customer_visible_action_allowed": False,
            "production_mutation_allowed": False,
            "delivery_trust_harness_skip_allowed": False,
            "ai_review_only_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "scenario": candidate["product-loop-scenario.json"] if candidate else None,
        "run": candidate["product-loop-run.json"] if candidate else None,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    return validate_receipt(receipt)


def validate_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    reject_payload(payload, label=RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ProductLoopBriefIntakeError("receipt schema_version drifted")
    status = payload.get("status")
    decision = payload.get("decision")
    reasons = payload.get("blocked_reasons")
    scenario = payload.get("scenario")
    run = payload.get("run")
    if status not in {"created_product_loop_candidate", "blocked"}:
        raise ProductLoopBriefIntakeError("receipt status is invalid")
    if not isinstance(reasons, list):
        raise ProductLoopBriefIntakeError("receipt blocked_reasons must be a list")
    if status == "created_product_loop_candidate":
        if decision != "create_product_loop_harness_candidate":
            raise ProductLoopBriefIntakeError("created receipt must create Product Loop candidate")
        if reasons:
            raise ProductLoopBriefIntakeError("created receipt must not include blocked reasons")
        transition = _require_mapping(payload, "requested_transition", label="receipt")
        if transition.get("to") != ALLOWED_NEXT_BOUNDARY:
            raise ProductLoopBriefIntakeError("created receipt must target Product Loop Harness")
        if transition.get("external_scope") not in product_loop_harness.ALLOWED_PROMOTION_SCOPES:
            raise ProductLoopBriefIntakeError("created receipt external scope must remain within policy")
        for key in (
            "raw_spec_body_requested",
            "raw_eval_body_requested",
            "automatic_execution_requested",
            "production_mutation_requested",
            "customer_visible_action_requested",
        ):
            if transition.get(key) is not False:
                raise ProductLoopBriefIntakeError(f"created receipt must not request {key}")
        if not isinstance(scenario, Mapping) or not isinstance(run, Mapping):
            raise ProductLoopBriefIntakeError("created receipt must include scenario and run")
        scenario_payload = product_loop_harness.validate_product_loop_scenario(scenario)
        run_payload = product_loop_harness.validate_product_loop_run(run)
        if run_payload["status"] != "allowed":
            raise ProductLoopBriefIntakeError("created Product Loop run must be allowed")
        if run_payload["decision"] != "promote_to_delivery_trust_harness":
            raise ProductLoopBriefIntakeError("created Product Loop run must stop at Delivery Trust Harness")
        if scenario_payload["source"]["source_type"] != "product_spec_eval_brief":
            raise ProductLoopBriefIntakeError("scenario source must be Product Spec/Eval brief")
        agentic = scenario_payload["loops"]["agentic_coding_loop"]
        if agentic.get("input_ref") != "product-spec-eval-brief.json":
            raise ProductLoopBriefIntakeError("agentic loop input_ref must be the Product Spec/Eval brief")
        ref = agentic.get("product_spec_eval_brief_ref")
        if not isinstance(ref, Mapping) or ref.get("body_included") is not False:
            raise ProductLoopBriefIntakeError("scenario must carry only a metadata-only brief ref")
    else:
        if decision != "block_product_loop_brief_intake":
            raise ProductLoopBriefIntakeError("blocked receipt must block Product Loop brief intake")
        if not reasons:
            raise ProductLoopBriefIntakeError("blocked receipt must include reasons")
        if scenario is not None or run is not None:
            raise ProductLoopBriefIntakeError("blocked receipt must not include scenario or run")

    reconstruction = _require_mapping(payload, "intake_reconstruction", label="receipt")
    if reconstruction.get("passive_attention_only_sufficient") is not False:
        raise ProductLoopBriefIntakeError("passive attention alone is insufficient for brief intake")
    policy = _require_mapping(payload, "intake_policy", label="receipt")
    if policy.get("allowed_next_boundary") != ALLOWED_NEXT_BOUNDARY:
        raise ProductLoopBriefIntakeError("policy must stop at Product Loop Harness")
    for key in (
        "raw_spec_body_allowed",
        "raw_eval_body_allowed",
        "automatic_execution_allowed",
        "customer_visible_action_allowed",
        "production_mutation_allowed",
        "delivery_trust_harness_skip_allowed",
        "ai_review_only_allowed",
    ):
        if policy.get(key) is not False:
            raise ProductLoopBriefIntakeError(f"policy.{key} must be False")
    _validate_privacy_runtime(payload, label="receipt")
    return dict(payload)


def build_all_cases() -> dict[str, dict[str, Any]]:
    source_cases = spec_eval_gate.build_all_cases()
    pass_brief = source_cases["pass"]["brief"]
    if not isinstance(pass_brief, Mapping):
        raise ProductLoopBriefIntakeError("Product Spec/Eval pass case missing brief")
    invalid_brief = dict(pass_brief)
    invalid_brief["next_boundary"] = "delivery_trust_harness"
    return {
        "pass": build_receipt(brief=pass_brief),
        "blocked-missing-brief": build_receipt(brief=None),
        "blocked-invalid-brief": build_receipt(brief=invalid_brief),
        "blocked-missing-developer-vision": build_receipt(
            brief=pass_brief,
            active_developer_vision=False,
        ),
        "blocked-external-scope-expansion": build_receipt(
            brief=pass_brief,
            external_scope="production_customer_handoff",
        ),
        "blocked-ai-review-only": build_receipt(brief=pass_brief, ai_review_only=True),
        "blocked-production-mutation": build_receipt(
            brief=pass_brief,
            production_mutation_requested=True,
        ),
        "blocked-skip-to-delivery-harness": build_receipt(
            brief=pass_brief,
            requested_next_boundary="delivery_trust_harness",
        ),
    }


def build_report(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    created = [case for case in cases.values() if case["status"] == "created_product_loop_candidate"]
    blocked = [case for case in cases.values() if case["status"] == "blocked"]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "purpose": (
            "Prove Product Spec/Eval briefs are consumed through a metadata-only "
            "Product Loop Harness intake gate before any executable work or "
            "Delivery Trust Harness promotion."
        ),
        "case_reports": [
            {
                "case_id": case_id,
                "status": case["status"],
                "decision": case["decision"],
                "blocked_reasons": list(case["blocked_reasons"]),
                "scenario_created": case["scenario"] is not None,
                "run_created": case["run"] is not None,
            }
            for case_id, case in cases.items()
        ],
        "created_case_count": len(created),
        "blocked_case_count": len(blocked),
        "scenario_count": sum(1 for case in cases.values() if case["scenario"] is not None),
        "run_count": sum(1 for case in cases.values() if case["run"] is not None),
        "gate_rules": {
            "source_brief_required": True,
            "active_developer_vision_required": True,
            "product_loop_harness_required": True,
            "delivery_trust_harness_skip_blocked": True,
            "ai_review_only_blocks": True,
            "external_scope_expansion_blocks": True,
            "raw_spec_body_blocked": True,
            "raw_eval_body_blocked": True,
            "automatic_execution_blocked": True,
            "customer_visible_action_blocked": True,
            "production_mutation_blocked": True,
            "metadata_only": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    reject_payload(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_cases(output_dir: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, receipt in cases.items():
        case_dir = output_dir / case_id
        dual_loop.write_json(case_dir / "product-loop-brief-intake-receipt.json", receipt)
        if isinstance(receipt.get("scenario"), Mapping):
            dual_loop.write_json(case_dir / "product-loop-scenario.json", receipt["scenario"])
        if isinstance(receipt.get("run"), Mapping):
            dual_loop.write_json(case_dir / "product-loop-run.json", receipt["run"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--brief", type=Path, help="Build a receipt from a Product Spec/Eval brief JSON file.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "fixtures" / "product-loop-brief-intake",
    )
    args = parser.parse_args()

    if args.brief:
        selected = {"custom": build_receipt(brief=dual_loop.load_json(args.brief))}
    else:
        cases = build_all_cases()
        selected = cases if args.case == "all" else {args.case: cases[args.case]}
    write_cases(args.output_dir, selected)
    print(
        json.dumps(
            {
                "schema_version": "product-loop-brief-intake-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "created_case_count": sum(
                    1 for receipt in selected.values() if receipt["status"] == "created_product_loop_candidate"
                ),
                "blocked_case_count": sum(
                    1 for receipt in selected.values() if receipt["status"] == "blocked"
                ),
                "model_calls_performed": False,
                "product_work_executed": False,
                "production_mutation_performed": False,
                "customer_visible_action_performed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
