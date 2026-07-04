#!/usr/bin/env python3
"""Gate Product Loop backlog items before they can enter spec/eval work.

This layer is intentionally metadata-only. It consumes
`product-loop-backlog-item-v1` artifacts from the External Feedback Backlog
Bridge and emits a Product Owner prioritization receipt. It never assigns a
real priority, writes to backlog storage, executes work, replies to customers,
publishes externally, or mutates production.
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
import external_feedback_backlog_bridge as backlog_bridge  # noqa: E402


RECEIPT_SCHEMA_VERSION = "product-owner-prioritization-receipt-v1"
CANDIDATE_SCHEMA_VERSION = "product-spec-eval-candidate-v1"
REPORT_SCHEMA_VERSION = "product-owner-prioritization-gate-verification-v1"
CASE_IDS = (
    "pass",
    "blocked-missing-owner-reconstruction",
    "blocked-automatic-priority",
    "blocked-skip-to-delivery-harness",
    "blocked-automatic-execution",
    "blocked-production-mutation",
    "blocked-customer-visible-action",
    "blocked-blocked-backlog-source",
)

FORBIDDEN_FIELDS = {
    "product_owner_identity",
    "owner_identity",
    "priority_score",
    "priority_rank",
    "priority_value",
    "raw_product_spec",
    "raw_eval_body",
    "raw_backlog_text",
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
    **backlog_bridge.PRIVACY,
    "product_owner_identity_included": False,
    "priority_score_included": False,
    "raw_product_spec_included": False,
    "raw_eval_body_included": False,
    "spec_eval_candidate_metadata_only": True,
}
RUNTIME = {
    **backlog_bridge.RUNTIME,
    "automatic_priority_assignment_performed": False,
    "automatic_execution_performed": False,
    "spec_eval_storage_mutated": False,
    "customer_visible_action_performed": False,
}
CLAIM_BOUNDARY = {
    "current_claim": (
        "A Product Loop backlog item can enter the product spec/eval candidate "
        "queue only after active Product Owner boundary reconstruction."
    ),
    "not_claimed": [
        "automatic priority assignment",
        "automatic execution",
        "customer-visible reply",
        "production mutation",
        "external publication",
        "readiness for Delivery Trust Harness",
        "customer satisfaction guarantee",
    ],
}


class ProductOwnerPrioritizationGateError(RuntimeError):
    """Readable Product Owner prioritization gate failure."""


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
        raise ProductOwnerPrioritizationGateError(
            f"product owner prioritization payload contains forbidden fields: {sorted(set(hits))}"
        )


def reject_gate_payload(payload: Mapping[str, Any]) -> None:
    dual_loop.assert_metadata_only(payload, label=RECEIPT_SCHEMA_VERSION)
    reject_forbidden_fields(payload)


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dual_loop.dump_json(payload))


def validate_backlog_item(item: Mapping[str, Any]) -> dict[str, Any]:
    validated = backlog_bridge.validate_backlog_item(item)
    if validated.get("destination") != "product_loop_backlog":
        raise ProductOwnerPrioritizationGateError("source item must come from product_loop_backlog")
    if validated.get("next_boundary") != "product_owner_prioritization":
        raise ProductOwnerPrioritizationGateError("source item must stop at product owner prioritization")
    if validated.get("ready_for_delivery_trust_harness") is not False:
        raise ProductOwnerPrioritizationGateError("source backlog item must not be ready for delivery trust")
    return validated


def build_candidate(backlog_item: Mapping[str, Any]) -> dict[str, Any]:
    item = validate_backlog_item(backlog_item)
    source_hash = artifact_hash(item)
    candidate = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "candidate_id": f"product-spec-eval-candidate-{source_hash[:16]}",
        "source_backlog_item_id": item["item_id"],
        "source_backlog_item_hash": source_hash,
        "source_receipt_id": item["source_receipt_id"],
        "source_delivery_class": item["source_delivery_class"],
        "feedback_ref": {
            "feedback_hash": item["feedback_ref"]["feedback_hash"],
            "source_channel": item["feedback_ref"]["source_channel"],
            "feedback_kind": item["feedback_ref"]["feedback_kind"],
            "sentiment": item["feedback_ref"]["sentiment"],
            "severity": item["feedback_ref"]["severity"],
            "bounded_tags": list(item["feedback_ref"].get("bounded_tags", [])),
        },
        "loop": "developer_feedback_loop",
        "destination": "product_spec_eval_candidate_queue",
        "next_boundary": "product_spec_eval_authoring",
        "priority_state": "unassigned",
        "priority_score_included": False,
        "requires_product_owner_prioritization_before_execution": True,
        "ready_for_execution": False,
        "ready_for_delivery_trust_harness": False,
        "blocked_destinations": list(BLOCKED_DESTINATIONS),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_candidate(candidate)


def validate_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    reject_gate_payload(candidate)
    if candidate.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise ProductOwnerPrioritizationGateError("candidate schema_version drifted")
    if candidate.get("destination") != "product_spec_eval_candidate_queue":
        raise ProductOwnerPrioritizationGateError("candidate destination must be product_spec_eval_candidate_queue")
    if candidate.get("next_boundary") != "product_spec_eval_authoring":
        raise ProductOwnerPrioritizationGateError("candidate next boundary must be product_spec_eval_authoring")
    if candidate.get("priority_state") != "unassigned":
        raise ProductOwnerPrioritizationGateError("candidate priority must remain unassigned")
    if candidate.get("priority_score_included") is not False:
        raise ProductOwnerPrioritizationGateError("candidate must not include priority score")
    if candidate.get("ready_for_execution") is not False:
        raise ProductOwnerPrioritizationGateError("candidate must not be ready for execution")
    if candidate.get("ready_for_delivery_trust_harness") is not False:
        raise ProductOwnerPrioritizationGateError("candidate must not skip to delivery trust harness")
    for blocked in BLOCKED_DESTINATIONS:
        if blocked not in candidate.get("blocked_destinations", []):
            raise ProductOwnerPrioritizationGateError(f"candidate missing blocked destination: {blocked}")
    validate_privacy_runtime(candidate, label="candidate")
    return dict(candidate)


def validate_privacy_runtime(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ProductOwnerPrioritizationGateError(f"{label} privacy must be metadata-only")
    for key, expected in PRIVACY.items():
        if privacy.get(key) is not expected:
            raise ProductOwnerPrioritizationGateError(f"{label} privacy.{key} must be {expected!r}")
    runtime = payload.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ProductOwnerPrioritizationGateError(f"{label} missing runtime")
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise ProductOwnerPrioritizationGateError(f"{label} runtime.{key} must be {expected!r}")


def build_receipt(
    *,
    backlog_item: Mapping[str, Any] | None = None,
    source_bridge: Mapping[str, Any] | None = None,
    active_owner_reconstruction: bool = True,
    requested_next_boundary: str = "product_spec_eval_candidate_queue",
    automatic_priority_requested: bool = False,
    automatic_execution_requested: bool = False,
    production_mutation_requested: bool = False,
    customer_visible_action_requested: bool = False,
) -> dict[str, Any]:
    bridge_payload = backlog_bridge.validate_bridge(source_bridge) if source_bridge is not None else None
    source_item = backlog_item
    if source_item is None and bridge_payload is not None:
        maybe_item = bridge_payload.get("backlog_item")
        source_item = maybe_item if isinstance(maybe_item, Mapping) else None

    reasons: list[str] = []
    item_payload: dict[str, Any] | None = None
    if source_item is None:
        reasons.append("source_backlog_item_missing")
    else:
        item_payload = validate_backlog_item(source_item)
    if not active_owner_reconstruction:
        reasons.append("product_owner_reconstruction_missing")
    if requested_next_boundary != "product_spec_eval_candidate_queue":
        reasons.append("requested_next_boundary_not_spec_eval_candidate_queue")
    if automatic_priority_requested:
        reasons.append("automatic_priority_assignment_rejected")
    if automatic_execution_requested:
        reasons.append("automatic_execution_rejected")
    if production_mutation_requested:
        reasons.append("production_mutation_rejected")
    if customer_visible_action_requested:
        reasons.append("customer_visible_action_rejected")

    candidate = None if reasons else build_candidate(item_payload or {})
    source_hash = artifact_hash(item_payload) if item_payload is not None else None
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": (
            f"product-owner-prioritization-{source_hash[:16]}"
            if source_hash
            else "product-owner-prioritization-blocked-source"
        ),
        "source_backlog_item_id": item_payload.get("item_id") if item_payload else None,
        "source_backlog_item_hash": source_hash,
        "source_bridge_id": bridge_payload.get("bridge_id") if bridge_payload else None,
        "source_receipt_id": item_payload.get("source_receipt_id") if item_payload else None,
        "source_delivery_class": item_payload.get("source_delivery_class") if item_payload else None,
        "status": "queued_for_spec_eval_candidate" if candidate else "blocked",
        "decision": "create_product_spec_eval_candidate" if candidate else "block_product_owner_prioritization",
        "blocked_reasons": reasons,
        "product_owner_reconstruction": {
            "active_reconstruction_present": active_owner_reconstruction,
            "passive_attention_only_sufficient": False,
            "owner_ref": "product-owner-role",
            "reconstructed_boundaries": [
                "feedback_hash_only",
                "candidate_queue_only",
                "no_automatic_priority",
                "no_customer_visible_action",
                "no_production_mutation",
            ],
        },
        "requested_transition": {
            "from": "product_loop_backlog",
            "to": requested_next_boundary,
            "automatic_priority_requested": automatic_priority_requested,
            "automatic_execution_requested": automatic_execution_requested,
            "production_mutation_requested": production_mutation_requested,
            "customer_visible_action_requested": customer_visible_action_requested,
        },
        "prioritization_policy": {
            "allowed_next_boundary": "product_spec_eval_candidate_queue",
            "automatic_priority_assignment_allowed": False,
            "automatic_execution_allowed": False,
            "customer_visible_action_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "blocked_destinations": list(BLOCKED_DESTINATIONS),
        },
        "candidate": candidate,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    return validate_receipt(receipt)


def validate_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    reject_gate_payload(payload)
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ProductOwnerPrioritizationGateError("receipt schema_version drifted")
    status = payload.get("status")
    decision = payload.get("decision")
    reasons = payload.get("blocked_reasons")
    candidate = payload.get("candidate")
    if status not in {"queued_for_spec_eval_candidate", "blocked"}:
        raise ProductOwnerPrioritizationGateError("receipt status is invalid")
    if not isinstance(reasons, list):
        raise ProductOwnerPrioritizationGateError("receipt blocked_reasons must be a list")
    if status == "queued_for_spec_eval_candidate":
        if decision != "create_product_spec_eval_candidate":
            raise ProductOwnerPrioritizationGateError("queued receipt must create a spec/eval candidate")
        if reasons:
            raise ProductOwnerPrioritizationGateError("queued receipt must not include blocked reasons")
        if not isinstance(candidate, Mapping):
            raise ProductOwnerPrioritizationGateError("queued receipt must include candidate")
        validate_candidate(candidate)
    else:
        if decision != "block_product_owner_prioritization":
            raise ProductOwnerPrioritizationGateError("blocked receipt must block prioritization")
        if not reasons:
            raise ProductOwnerPrioritizationGateError("blocked receipt must include reasons")
        if candidate is not None:
            raise ProductOwnerPrioritizationGateError("blocked receipt must not include candidate")
    owner = payload.get("product_owner_reconstruction")
    if not isinstance(owner, Mapping):
        raise ProductOwnerPrioritizationGateError("receipt missing product owner reconstruction")
    if owner.get("passive_attention_only_sufficient") is not False:
        raise ProductOwnerPrioritizationGateError("passive owner attention alone is insufficient")
    transition = payload.get("requested_transition")
    if not isinstance(transition, Mapping):
        raise ProductOwnerPrioritizationGateError("receipt missing requested transition")
    policy = payload.get("prioritization_policy")
    if not isinstance(policy, Mapping):
        raise ProductOwnerPrioritizationGateError("receipt missing prioritization policy")
    if policy.get("allowed_next_boundary") != "product_spec_eval_candidate_queue":
        raise ProductOwnerPrioritizationGateError("policy must stop at spec/eval candidate queue")
    for key in (
        "automatic_priority_assignment_allowed",
        "automatic_execution_allowed",
        "customer_visible_action_allowed",
        "production_mutation_allowed",
        "external_publication_allowed",
    ):
        if policy.get(key) is not False:
            raise ProductOwnerPrioritizationGateError(f"policy.{key} must be False")
    validate_privacy_runtime(payload, label="receipt")
    return dict(payload)


def build_all_cases() -> dict[str, dict[str, Any]]:
    bridges = backlog_bridge.build_all_cases()
    pass_item = bridges["pass"]["backlog_item"]
    if not isinstance(pass_item, Mapping):
        raise ProductOwnerPrioritizationGateError("pass bridge missing backlog item")
    return {
        "pass": build_receipt(backlog_item=pass_item, source_bridge=bridges["pass"]),
        "blocked-missing-owner-reconstruction": build_receipt(
            backlog_item=pass_item,
            source_bridge=bridges["pass"],
            active_owner_reconstruction=False,
        ),
        "blocked-automatic-priority": build_receipt(
            backlog_item=pass_item,
            source_bridge=bridges["pass"],
            automatic_priority_requested=True,
        ),
        "blocked-skip-to-delivery-harness": build_receipt(
            backlog_item=pass_item,
            source_bridge=bridges["pass"],
            requested_next_boundary="delivery_trust_harness",
        ),
        "blocked-automatic-execution": build_receipt(
            backlog_item=pass_item,
            source_bridge=bridges["pass"],
            automatic_execution_requested=True,
        ),
        "blocked-production-mutation": build_receipt(
            backlog_item=pass_item,
            source_bridge=bridges["pass"],
            production_mutation_requested=True,
        ),
        "blocked-customer-visible-action": build_receipt(
            backlog_item=pass_item,
            source_bridge=bridges["pass"],
            customer_visible_action_requested=True,
        ),
        "blocked-blocked-backlog-source": build_receipt(source_bridge=bridges["blocked-raw-feedback"]),
    }


def build_report(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    queued = [case for case in cases.values() if case["status"] == "queued_for_spec_eval_candidate"]
    blocked = [case for case in cases.values() if case["status"] == "blocked"]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "purpose": (
            "Prove metadata-only Product Loop backlog items can enter a spec/eval "
            "candidate queue only after Product Owner boundary reconstruction."
        ),
        "case_reports": [
            {
                "case_id": case_id,
                "status": case["status"],
                "decision": case["decision"],
                "blocked_reasons": list(case["blocked_reasons"]),
                "candidate_created": case["candidate"] is not None,
            }
            for case_id, case in cases.items()
        ],
        "queued_case_count": len(queued),
        "blocked_case_count": len(blocked),
        "candidate_count": sum(1 for case in cases.values() if case["candidate"] is not None),
        "gate_rules": {
            "product_owner_reconstruction_required": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_execution_blocked": True,
            "customer_visible_action_blocked": True,
            "production_mutation_blocked": True,
            "allowed_next_boundary": "product_spec_eval_candidate_queue",
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
        dual_loop.write_json(output_dir / case_id / "product-owner-prioritization-receipt.json", receipt)
        candidate = receipt.get("candidate")
        if isinstance(candidate, Mapping):
            dual_loop.write_json(output_dir / case_id / "product-spec-eval-candidate.json", candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--backlog-item", type=Path, help="Build a receipt from a Product Loop backlog item JSON file.")
    parser.add_argument("--bridge", type=Path, help="Build a receipt from an External Feedback Backlog Bridge JSON file.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "fixtures" / "product-owner-prioritization-gate")
    args = parser.parse_args()

    if args.backlog_item:
        selected = {
            "custom": build_receipt(
                backlog_item=dual_loop.load_json(args.backlog_item),
                source_bridge=dual_loop.load_json(args.bridge) if args.bridge else None,
            )
        }
    elif args.bridge:
        selected = {"custom": build_receipt(source_bridge=dual_loop.load_json(args.bridge))}
    else:
        cases = build_all_cases()
        selected = cases if args.case == "all" else {args.case: cases[args.case]}
    write_cases(args.output_dir, selected)
    print(
        json.dumps(
            {
                "schema_version": "product-owner-prioritization-gate-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "queued_case_count": sum(
                    1 for receipt in selected.values() if receipt["status"] == "queued_for_spec_eval_candidate"
                ),
                "blocked_case_count": sum(1 for receipt in selected.values() if receipt["status"] == "blocked"),
                "model_calls_performed": False,
                "automatic_priority_assignment_performed": False,
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
