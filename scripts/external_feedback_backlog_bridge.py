#!/usr/bin/env python3
"""Bridge accepted External Feedback receipts into Product Loop backlog items.

The bridge is intentionally metadata-only. It never stores raw feedback text,
customer identity, support ticket bodies, screenshots, model credentials, or
production payloads. It also never replies to customers, publishes externally,
or mutates production.
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


BRIDGE_SCHEMA_VERSION = "external-feedback-backlog-bridge-v1"
BACKLOG_ITEM_SCHEMA_VERSION = "product-loop-backlog-item-v1"
REPORT_SCHEMA_VERSION = "external-feedback-backlog-bridge-verification-v1"
CASE_IDS = external_feedback.CASE_IDS

PRIVACY = {
    **external_feedback.PRIVACY,
    "backlog_item_metadata_only": True,
    "feedback_hash_only": True,
    "customer_visible_reply_created": False,
    "product_owner_identity_included": False,
}
RUNTIME = {
    **external_feedback.RUNTIME,
    "backlog_storage_mutated": False,
    "customer_visible_reply_created": False,
}
CLAIM_BOUNDARY = {
    "current_claim": (
        "Accepted external feedback can be converted into a Product Loop backlog "
        "item as metadata only. Blocked feedback cannot create a backlog item."
    ),
    "not_claimed": [
        "raw feedback import",
        "requester identity import",
        "customer-visible reply",
        "automatic production mutation",
        "external publication",
        "automatic prioritization",
        "customer satisfaction guarantee",
    ],
}


class ExternalFeedbackBacklogBridgeError(RuntimeError):
    """Readable external-feedback backlog bridge failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def reject_bridge_payload(payload: Mapping[str, Any]) -> None:
    dual_loop.assert_metadata_only(payload, label=BRIDGE_SCHEMA_VERSION)
    external_feedback.reject_forbidden_fields(payload)


def receipt_hash(receipt: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dual_loop.dump_json(receipt))


def build_backlog_item(receipt: Mapping[str, Any]) -> dict[str, Any]:
    feedback_ref = receipt.get("feedback_ref")
    propagation = receipt.get("propagation")
    if not isinstance(feedback_ref, Mapping) or not isinstance(propagation, Mapping):
        raise ExternalFeedbackBacklogBridgeError("accepted feedback receipt missing feedback_ref or propagation")
    source_hash = receipt_hash(receipt)
    item = {
        "schema_version": BACKLOG_ITEM_SCHEMA_VERSION,
        "item_id": f"product-loop-backlog-{source_hash[:16]}",
        "source_receipt_id": receipt["receipt_id"],
        "source_receipt_hash": source_hash,
        "source_delivery_class": receipt["source_delivery_class"],
        "source_handoff_ref": receipt["source_handoff_ref"],
        "feedback_ref": {
            "feedback_hash": feedback_ref["feedback_hash"],
            "source_channel": feedback_ref["source_channel"],
            "feedback_kind": feedback_ref["feedback_kind"],
            "sentiment": feedback_ref["sentiment"],
            "severity": feedback_ref["severity"],
            "bounded_tags": list(feedback_ref.get("bounded_tags", [])),
        },
        "loop": "external_feedback_loop",
        "destination": "product_loop_backlog",
        "next_boundary": "product_owner_prioritization",
        "blocked_destinations": list(propagation.get("blocked_destinations", [])),
        "requires_product_owner_prioritization": True,
        "ready_for_delivery_trust_harness": False,
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    reject_bridge_payload(item)
    return item


def validate_backlog_item(item: Mapping[str, Any]) -> dict[str, Any]:
    reject_bridge_payload(item)
    if item.get("schema_version") != BACKLOG_ITEM_SCHEMA_VERSION:
        raise ExternalFeedbackBacklogBridgeError("backlog item schema_version drifted")
    if item.get("destination") != "product_loop_backlog":
        raise ExternalFeedbackBacklogBridgeError("backlog item destination must be product_loop_backlog")
    if item.get("next_boundary") != "product_owner_prioritization":
        raise ExternalFeedbackBacklogBridgeError("backlog item must stop at product owner prioritization")
    if item.get("requires_product_owner_prioritization") is not True:
        raise ExternalFeedbackBacklogBridgeError("backlog item must require product owner prioritization")
    if item.get("ready_for_delivery_trust_harness") is not False:
        raise ExternalFeedbackBacklogBridgeError("backlog item must not skip to delivery trust harness")
    for blocked in ("production_mutation", "automatic_customer_reply", "external_publication"):
        if blocked not in item.get("blocked_destinations", []):
            raise ExternalFeedbackBacklogBridgeError(f"backlog item missing blocked destination: {blocked}")
    privacy = item.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ExternalFeedbackBacklogBridgeError("backlog item privacy must be metadata-only")
    runtime = item.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ExternalFeedbackBacklogBridgeError("backlog item missing runtime")
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise ExternalFeedbackBacklogBridgeError(f"backlog item runtime.{key} must be {expected!r}")
    return dict(item)


def build_bridge(receipt: Mapping[str, Any]) -> dict[str, Any]:
    validated = external_feedback.validate_case(receipt)
    reasons: list[str] = []
    if validated.get("status") != "accepted_for_product_loop":
        reasons.append("external_feedback_receipt_not_accepted")
    if validated.get("decision") != "accept_external_feedback_into_product_loop":
        reasons.append("external_feedback_decision_blocked")
    if validated.get("next_boundary") != "product_loop_backlog_only_not_production":
        reasons.append("next_boundary_not_product_loop_backlog")
    propagation = validated.get("propagation")
    if not isinstance(propagation, Mapping):
        raise ExternalFeedbackBacklogBridgeError("feedback receipt missing propagation")
    if propagation.get("requested_next_action") != "product_loop_backlog":
        reasons.append("requested_next_action_outside_feedback_budget")
    if propagation.get("allowed_destination") != "product_loop_backlog":
        reasons.append("allowed_destination_not_product_loop_backlog")
    if propagation.get("requires_product_owner_prioritization") is not True:
        reasons.append("product_owner_prioritization_missing")

    backlog_item = None if reasons else build_backlog_item(validated)
    bridge = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "bridge_id": f"external-feedback-backlog-{receipt_hash(validated)[:16]}",
        "source_receipt_id": validated["receipt_id"],
        "source_receipt_hash": receipt_hash(validated),
        "source_delivery_class": validated["source_delivery_class"],
        "status": "queued_for_product_loop" if backlog_item else "blocked",
        "decision": "create_product_loop_backlog_item" if backlog_item else "block_backlog_item_creation",
        "blocked_reasons": reasons,
        "backlog_item": backlog_item,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    return validate_bridge(bridge)


def validate_bridge(payload: Mapping[str, Any]) -> dict[str, Any]:
    reject_bridge_payload(payload)
    if payload.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise ExternalFeedbackBacklogBridgeError("bridge schema_version drifted")
    status = payload.get("status")
    decision = payload.get("decision")
    backlog_item = payload.get("backlog_item")
    blocked_reasons = payload.get("blocked_reasons")
    if status not in {"queued_for_product_loop", "blocked"}:
        raise ExternalFeedbackBacklogBridgeError("bridge status is invalid")
    if not isinstance(blocked_reasons, list):
        raise ExternalFeedbackBacklogBridgeError("bridge blocked_reasons must be a list")
    if status == "queued_for_product_loop":
        if decision != "create_product_loop_backlog_item":
            raise ExternalFeedbackBacklogBridgeError("queued bridge must create a backlog item")
        if blocked_reasons:
            raise ExternalFeedbackBacklogBridgeError("queued bridge must not include blocked reasons")
        if not isinstance(backlog_item, Mapping):
            raise ExternalFeedbackBacklogBridgeError("queued bridge must include a backlog item")
        validate_backlog_item(backlog_item)
    else:
        if decision != "block_backlog_item_creation":
            raise ExternalFeedbackBacklogBridgeError("blocked bridge must block backlog item creation")
        if not blocked_reasons:
            raise ExternalFeedbackBacklogBridgeError("blocked bridge must include reasons")
        if backlog_item is not None:
            raise ExternalFeedbackBacklogBridgeError("blocked bridge must not include a backlog item")
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ExternalFeedbackBacklogBridgeError("bridge privacy must be metadata-only")
    runtime = payload.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ExternalFeedbackBacklogBridgeError("bridge missing runtime")
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise ExternalFeedbackBacklogBridgeError(f"bridge runtime.{key} must be {expected!r}")
    return dict(payload)


def build_all_cases() -> dict[str, dict[str, Any]]:
    return {
        case_id: build_bridge(receipt)
        for case_id, receipt in external_feedback.build_all_cases().items()
    }


def build_report(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    queued = [case for case in cases.values() if case["status"] == "queued_for_product_loop"]
    blocked = [case for case in cases.values() if case["status"] == "blocked"]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "purpose": (
            "Prove accepted External Feedback receipts can create metadata-only "
            "Product Loop backlog items while blocked receipts cannot enter the backlog."
        ),
        "case_reports": [
            {
                "case_id": str(case["source_receipt_id"]).replace("external-feedback-", ""),
                "status": case["status"],
                "decision": case["decision"],
                "blocked_reasons": list(case["blocked_reasons"]),
                "backlog_item_created": case["backlog_item"] is not None,
                "source_delivery_class": case["source_delivery_class"],
            }
            for case in cases.values()
        ],
        "queued_case_count": len(queued),
        "blocked_case_count": len(blocked),
        "backlog_item_count": sum(1 for case in cases.values() if case["backlog_item"] is not None),
        "bridge_rules": {
            "accepted_receipt_required": True,
            "blocked_receipt_cannot_create_backlog_item": True,
            "raw_feedback_text_rejected": True,
            "requester_identity_rejected": True,
            "customer_visible_reply_blocked": True,
            "production_mutation_blocked": True,
            "destination": "product_loop_backlog",
            "next_boundary": "product_owner_prioritization",
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    reject_bridge_payload(report)
    return report


def write_cases(output_dir: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, bridge in cases.items():
        dual_loop.write_json(output_dir / case_id / "external-feedback-backlog-bridge.json", bridge)
        backlog_item = bridge.get("backlog_item")
        if isinstance(backlog_item, Mapping):
            dual_loop.write_json(output_dir / case_id / "product-loop-backlog-item.json", backlog_item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--receipt", type=Path, help="Build a bridge decision from a receipt JSON file.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "fixtures" / "external-feedback-backlog-bridge")
    args = parser.parse_args()

    if args.receipt:
        bridge = build_bridge(dual_loop.load_json(args.receipt))
        selected = {str(bridge["source_receipt_id"]).replace("external-feedback-", ""): bridge}
    else:
        cases = build_all_cases()
        selected = cases if args.case == "all" else {args.case: cases[args.case]}
    write_cases(args.output_dir, selected)
    print(
        json.dumps(
            {
                "schema_version": "external-feedback-backlog-bridge-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "queued_case_count": sum(1 for bridge in selected.values() if bridge["status"] == "queued_for_product_loop"),
                "blocked_case_count": sum(1 for bridge in selected.values() if bridge["status"] == "blocked"),
                "model_calls_performed": False,
                "production_mutation_performed": False,
                "external_publication_performed": False,
                "customer_visible_reply_created": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
