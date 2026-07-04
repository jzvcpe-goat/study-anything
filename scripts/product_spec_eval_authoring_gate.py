#!/usr/bin/env python3
"""Gate Product Spec/Eval authoring before any executable work exists.

This metadata-only layer consumes `product-spec-eval-candidate-v1` artifacts
from the Product Owner Prioritization Gate and emits a bounded spec/eval brief.
It never assigns priority, stores raw specs or eval bodies, executes work,
replies to customers, publishes externally, mutates production, or skips to the
Delivery Trust Harness.
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

from study_anything.core import dual_loop  # noqa: E402
import external_feedback_receipt as external_feedback  # noqa: E402
import product_owner_prioritization_gate as owner_gate  # noqa: E402


RECEIPT_SCHEMA_VERSION = "product-spec-eval-authoring-receipt-v1"
BRIEF_SCHEMA_VERSION = "product-spec-eval-brief-v1"
REPORT_SCHEMA_VERSION = "product-spec-eval-authoring-gate-verification-v1"
CASE_IDS = (
    "pass",
    "blocked-missing-authoring-reconstruction",
    "blocked-raw-spec-body",
    "blocked-automatic-execution",
    "blocked-skip-to-delivery-harness",
    "blocked-production-mutation",
    "blocked-customer-visible-action",
    "blocked-invalid-candidate-source",
)

FORBIDDEN_FIELDS = {
    "raw_product_spec",
    "raw_eval_body",
    "raw_acceptance_criteria",
    "acceptance_criteria_text",
    "eval_prompt",
    "eval_dataset_body",
    "priority_score",
    "priority_rank",
    "customer_visible_reply",
    "customer_visible_message",
    "production_payload",
}
BLOCKED_DESTINATIONS = [
    "delivery_trust_harness",
    "automatic_execution",
    "customer_visible_reply",
    "production_mutation",
    "external_publication",
]
PRIVACY = {
    **owner_gate.PRIVACY,
    "raw_acceptance_criteria_included": False,
    "eval_prompt_included": False,
    "eval_dataset_body_included": False,
    "spec_eval_brief_metadata_only": True,
}
RUNTIME = {
    **owner_gate.RUNTIME,
    "raw_spec_storage_mutated": False,
    "eval_storage_mutated": False,
    "product_loop_harness_mutated": False,
}
CLAIM_BOUNDARY = {
    "current_claim": (
        "A Product Spec/Eval candidate can become a metadata-only spec/eval "
        "brief only after active authoring-boundary reconstruction."
    ),
    "not_claimed": [
        "finished product spec",
        "finished eval suite",
        "automatic priority assignment",
        "automatic execution",
        "customer-visible reply",
        "production mutation",
        "external publication",
        "readiness for Delivery Trust Harness",
        "customer satisfaction guarantee",
    ],
}


class ProductSpecEvalAuthoringGateError(RuntimeError):
    """Readable Product Spec/Eval authoring gate failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for child in value.values():
            found.extend(walk_mappings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_mappings(child))
    return found


def reject_forbidden_fields(payload: Mapping[str, Any]) -> None:
    external_feedback.reject_forbidden_fields(payload)
    hits: list[str] = []
    for mapping in walk_mappings(payload):
        for key, value in mapping.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in FORBIDDEN_FIELDS and value not in (None, False, "", []):
                hits.append(str(key))
    if hits:
        raise ProductSpecEvalAuthoringGateError(
            f"product spec/eval authoring payload contains forbidden fields: {sorted(set(hits))}"
        )


def reject_gate_payload(payload: Mapping[str, Any]) -> None:
    dual_loop.assert_metadata_only(payload, label=RECEIPT_SCHEMA_VERSION)
    reject_forbidden_fields(payload)


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dual_loop.dump_json(payload))


def validate_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validated = owner_gate.validate_candidate(candidate)
    if validated.get("destination") != "product_spec_eval_candidate_queue":
        raise ProductSpecEvalAuthoringGateError("source candidate must come from spec/eval candidate queue")
    if validated.get("next_boundary") != "product_spec_eval_authoring":
        raise ProductSpecEvalAuthoringGateError("source candidate must stop at spec/eval authoring")
    if validated.get("ready_for_execution") is not False:
        raise ProductSpecEvalAuthoringGateError("source candidate must not be executable")
    if validated.get("ready_for_delivery_trust_harness") is not False:
        raise ProductSpecEvalAuthoringGateError("source candidate must not be ready for delivery trust")
    return validated


def stable_ref(prefix: str, seed: str, index: int) -> dict[str, Any]:
    token = dual_loop.sha256_text(f"{prefix}:{seed}:{index}")[:16]
    return {
        "ref_id": f"{prefix}-{index}",
        "ref_hash": token,
        "body_included": False,
    }


def build_brief(candidate: Mapping[str, Any]) -> dict[str, Any]:
    item = validate_candidate(candidate)
    source_hash = artifact_hash(item)
    brief = {
        "schema_version": BRIEF_SCHEMA_VERSION,
        "brief_id": f"product-spec-eval-brief-{source_hash[:16]}",
        "source_candidate_id": item["candidate_id"],
        "source_candidate_hash": source_hash,
        "source_backlog_item_id": item["source_backlog_item_id"],
        "source_delivery_class": item["source_delivery_class"],
        "feedback_ref": dict(item["feedback_ref"]),
        "loop": "developer_feedback_loop",
        "destination": "product_spec_eval_brief",
        "next_boundary": "product_loop_harness_candidate",
        "spec_ref": {
            "problem_statement_hash": dual_loop.sha256_text("problem:" + source_hash)[:16],
            "scope_boundary_hash": dual_loop.sha256_text("scope:" + source_hash)[:16],
            "raw_spec_body_included": False,
        },
        "acceptance_criteria_refs": [stable_ref("acceptance-criterion", source_hash, index) for index in range(1, 4)],
        "eval_plan_refs": [stable_ref("eval-plan", source_hash, index) for index in range(1, 4)],
        "quality_gates": {
            "source_bound": True,
            "claim_boundary_required": True,
            "ai_review_only_rejected": True,
            "human_authoring_reconstruction_required": True,
            "raw_spec_body_allowed": False,
            "raw_eval_body_allowed": False,
        },
        "ready_for_product_loop_harness": True,
        "ready_for_execution": False,
        "ready_for_delivery_trust_harness": False,
        "blocked_destinations": list(BLOCKED_DESTINATIONS),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_brief(brief)


def validate_brief(brief: Mapping[str, Any]) -> dict[str, Any]:
    reject_gate_payload(brief)
    if brief.get("schema_version") != BRIEF_SCHEMA_VERSION:
        raise ProductSpecEvalAuthoringGateError("brief schema_version drifted")
    if brief.get("destination") != "product_spec_eval_brief":
        raise ProductSpecEvalAuthoringGateError("brief destination must be product_spec_eval_brief")
    if brief.get("next_boundary") != "product_loop_harness_candidate":
        raise ProductSpecEvalAuthoringGateError("brief next boundary must be product_loop_harness_candidate")
    if brief.get("ready_for_product_loop_harness") is not True:
        raise ProductSpecEvalAuthoringGateError("brief must be ready only for product loop harness candidate")
    if brief.get("ready_for_execution") is not False:
        raise ProductSpecEvalAuthoringGateError("brief must not be executable")
    if brief.get("ready_for_delivery_trust_harness") is not False:
        raise ProductSpecEvalAuthoringGateError("brief must not skip to delivery trust")
    if not isinstance(brief.get("acceptance_criteria_refs"), list) or len(brief["acceptance_criteria_refs"]) < 3:
        raise ProductSpecEvalAuthoringGateError("brief must include bounded acceptance criteria refs")
    if not isinstance(brief.get("eval_plan_refs"), list) or len(brief["eval_plan_refs"]) < 3:
        raise ProductSpecEvalAuthoringGateError("brief must include bounded eval plan refs")
    spec_ref = brief.get("spec_ref")
    if not isinstance(spec_ref, Mapping) or spec_ref.get("raw_spec_body_included") is not False:
        raise ProductSpecEvalAuthoringGateError("brief spec_ref must exclude raw spec body")
    for blocked in BLOCKED_DESTINATIONS:
        if blocked not in brief.get("blocked_destinations", []):
            raise ProductSpecEvalAuthoringGateError(f"brief missing blocked destination: {blocked}")
    validate_privacy_runtime(brief, label="brief")
    return dict(brief)


def validate_privacy_runtime(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ProductSpecEvalAuthoringGateError(f"{label} privacy must be metadata-only")
    for key, expected in PRIVACY.items():
        if privacy.get(key) is not expected:
            raise ProductSpecEvalAuthoringGateError(f"{label} privacy.{key} must be {expected!r}")
    runtime = payload.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ProductSpecEvalAuthoringGateError(f"{label} missing runtime")
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise ProductSpecEvalAuthoringGateError(f"{label} runtime.{key} must be {expected!r}")


def build_receipt(
    *,
    candidate: Mapping[str, Any] | None = None,
    active_authoring_reconstruction: bool = True,
    requested_next_boundary: str = "product_loop_harness_candidate",
    raw_spec_body_requested: bool = False,
    automatic_execution_requested: bool = False,
    production_mutation_requested: bool = False,
    customer_visible_action_requested: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    candidate_payload: dict[str, Any] | None = None
    if candidate is None:
        reasons.append("source_candidate_missing")
    else:
        try:
            candidate_payload = validate_candidate(candidate)
        except Exception:
            reasons.append("source_candidate_invalid")
    if not active_authoring_reconstruction:
        reasons.append("authoring_reconstruction_missing")
    if requested_next_boundary != "product_loop_harness_candidate":
        reasons.append("requested_next_boundary_not_product_loop_harness_candidate")
    if raw_spec_body_requested:
        reasons.append("raw_spec_body_rejected")
    if automatic_execution_requested:
        reasons.append("automatic_execution_rejected")
    if production_mutation_requested:
        reasons.append("production_mutation_rejected")
    if customer_visible_action_requested:
        reasons.append("customer_visible_action_rejected")

    brief = None if reasons else build_brief(candidate_payload or {})
    source_hash = artifact_hash(candidate_payload) if candidate_payload is not None else None
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": f"product-spec-eval-authoring-{source_hash[:16]}" if source_hash else "product-spec-eval-authoring-blocked-source",
        "source_candidate_id": candidate_payload.get("candidate_id") if candidate_payload else None,
        "source_candidate_hash": source_hash,
        "source_backlog_item_id": candidate_payload.get("source_backlog_item_id") if candidate_payload else None,
        "source_delivery_class": candidate_payload.get("source_delivery_class") if candidate_payload else None,
        "status": "authored_spec_eval_brief" if brief else "blocked",
        "decision": "create_product_spec_eval_brief" if brief else "block_product_spec_eval_authoring",
        "blocked_reasons": reasons,
        "authoring_reconstruction": {
            "active_reconstruction_present": active_authoring_reconstruction,
            "passive_attention_only_sufficient": False,
            "reconstructed_boundaries": [
                "metadata_only_spec_refs",
                "metadata_only_eval_refs",
                "no_raw_spec_body",
                "no_automatic_execution",
                "no_customer_visible_action",
                "no_production_mutation",
            ],
        },
        "requested_transition": {
            "from": "product_spec_eval_candidate_queue",
            "to": requested_next_boundary,
            "raw_spec_body_requested": raw_spec_body_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "production_mutation_requested": production_mutation_requested,
            "customer_visible_action_requested": customer_visible_action_requested,
        },
        "authoring_policy": {
            "allowed_next_boundary": "product_loop_harness_candidate",
            "raw_spec_body_allowed": False,
            "raw_eval_body_allowed": False,
            "automatic_execution_allowed": False,
            "customer_visible_action_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "brief": brief,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    return validate_receipt(receipt)


def validate_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    reject_gate_payload(payload)
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ProductSpecEvalAuthoringGateError("receipt schema_version drifted")
    status = payload.get("status")
    decision = payload.get("decision")
    reasons = payload.get("blocked_reasons")
    brief = payload.get("brief")
    if status not in {"authored_spec_eval_brief", "blocked"}:
        raise ProductSpecEvalAuthoringGateError("receipt status is invalid")
    if not isinstance(reasons, list):
        raise ProductSpecEvalAuthoringGateError("receipt blocked_reasons must be a list")
    if status == "authored_spec_eval_brief":
        if decision != "create_product_spec_eval_brief":
            raise ProductSpecEvalAuthoringGateError("authored receipt must create a spec/eval brief")
        if reasons:
            raise ProductSpecEvalAuthoringGateError("authored receipt must not include blocked reasons")
        if not isinstance(brief, Mapping):
            raise ProductSpecEvalAuthoringGateError("authored receipt must include brief")
        validate_brief(brief)
    else:
        if decision != "block_product_spec_eval_authoring":
            raise ProductSpecEvalAuthoringGateError("blocked receipt must block authoring")
        if not reasons:
            raise ProductSpecEvalAuthoringGateError("blocked receipt must include reasons")
        if brief is not None:
            raise ProductSpecEvalAuthoringGateError("blocked receipt must not include brief")
    authoring = payload.get("authoring_reconstruction")
    if not isinstance(authoring, Mapping):
        raise ProductSpecEvalAuthoringGateError("receipt missing authoring reconstruction")
    if authoring.get("passive_attention_only_sufficient") is not False:
        raise ProductSpecEvalAuthoringGateError("passive authoring attention alone is insufficient")
    policy = payload.get("authoring_policy")
    if not isinstance(policy, Mapping):
        raise ProductSpecEvalAuthoringGateError("receipt missing authoring policy")
    if policy.get("allowed_next_boundary") != "product_loop_harness_candidate":
        raise ProductSpecEvalAuthoringGateError("policy must stop at product loop harness candidate")
    for key in (
        "raw_spec_body_allowed",
        "raw_eval_body_allowed",
        "automatic_execution_allowed",
        "customer_visible_action_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
    ):
        if policy.get(key) is not False:
            raise ProductSpecEvalAuthoringGateError(f"policy.{key} must be False")
    validate_privacy_runtime(payload, label="receipt")
    return dict(payload)


def build_all_cases() -> dict[str, dict[str, Any]]:
    owner_cases = owner_gate.build_all_cases()
    candidate = owner_cases["pass"]["candidate"]
    if not isinstance(candidate, Mapping):
        raise ProductSpecEvalAuthoringGateError("Product Owner pass case missing candidate")
    invalid_candidate = dict(candidate)
    invalid_candidate["destination"] = "delivery_trust_harness"
    return {
        "pass": build_receipt(candidate=candidate),
        "blocked-missing-authoring-reconstruction": build_receipt(
            candidate=candidate,
            active_authoring_reconstruction=False,
        ),
        "blocked-raw-spec-body": build_receipt(candidate=candidate, raw_spec_body_requested=True),
        "blocked-automatic-execution": build_receipt(candidate=candidate, automatic_execution_requested=True),
        "blocked-skip-to-delivery-harness": build_receipt(
            candidate=candidate,
            requested_next_boundary="delivery_trust_harness",
        ),
        "blocked-production-mutation": build_receipt(candidate=candidate, production_mutation_requested=True),
        "blocked-customer-visible-action": build_receipt(candidate=candidate, customer_visible_action_requested=True),
        "blocked-invalid-candidate-source": build_receipt(candidate=invalid_candidate),
    }


def build_report(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    authored = [case for case in cases.values() if case["status"] == "authored_spec_eval_brief"]
    blocked = [case for case in cases.values() if case["status"] == "blocked"]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "purpose": (
            "Prove metadata-only spec/eval candidates can become bounded spec/eval "
            "briefs without creating executable work or raw spec/eval bodies."
        ),
        "case_reports": [
            {
                "case_id": case_id,
                "status": case["status"],
                "decision": case["decision"],
                "blocked_reasons": list(case["blocked_reasons"]),
                "brief_created": case["brief"] is not None,
            }
            for case_id, case in cases.items()
        ],
        "authored_case_count": len(authored),
        "blocked_case_count": len(blocked),
        "brief_count": sum(1 for case in cases.values() if case["brief"] is not None),
        "gate_rules": {
            "authoring_reconstruction_required": True,
            "raw_spec_body_blocked": True,
            "raw_eval_body_blocked": True,
            "automatic_execution_blocked": True,
            "customer_visible_action_blocked": True,
            "production_mutation_blocked": True,
            "allowed_next_boundary": "product_loop_harness_candidate",
            "delivery_trust_harness_skip_blocked": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    reject_gate_payload(report)
    return report


def write_cases(output_dir: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, receipt in cases.items():
        dual_loop.write_json(output_dir / case_id / "product-spec-eval-authoring-receipt.json", receipt)
        brief = receipt.get("brief")
        if isinstance(brief, Mapping):
            dual_loop.write_json(output_dir / case_id / "product-spec-eval-brief.json", brief)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--candidate", type=Path, help="Build a receipt from a Product Spec/Eval candidate JSON file.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "fixtures" / "product-spec-eval-authoring-gate")
    args = parser.parse_args()

    if args.candidate:
        selected = {"custom": build_receipt(candidate=dual_loop.load_json(args.candidate))}
    else:
        cases = build_all_cases()
        selected = cases if args.case == "all" else {args.case: cases[args.case]}
    write_cases(args.output_dir, selected)
    print(
        json.dumps(
            {
                "schema_version": "product-spec-eval-authoring-gate-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "authored_case_count": sum(1 for receipt in selected.values() if receipt["status"] == "authored_spec_eval_brief"),
                "blocked_case_count": sum(1 for receipt in selected.values() if receipt["status"] == "blocked"),
                "model_calls_performed": False,
                "raw_spec_body_written": False,
                "automatic_execution_performed": False,
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
