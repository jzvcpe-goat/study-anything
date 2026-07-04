#!/usr/bin/env python3
"""Build metadata-only External Feedback Loop receipts.

External feedback is the third product-development loop. This artifact records
only bounded feedback metadata and the operator reconstruction needed to feed
the Product Loop. It never stores raw customer text, requester identity, model
credentials, screenshots, logs, or production payloads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import dual_loop  # noqa: E402


SCHEMA_VERSION = "external-feedback-receipt-v1"
REPORT_SCHEMA_VERSION = "external-feedback-receipt-verification-v1"
CASE_IDS = (
    "pass",
    "blocked-raw-feedback",
    "blocked-identity",
    "blocked-production-mutation",
    "blocked-ai-review-only",
)

ALLOWED_DELIVERY_CLASSES = {
    "code_review_handoff",
    "client_report_handoff",
    "support_response_handoff",
}
ALLOWED_NEXT_ACTIONS = {
    "product_loop_backlog",
    "eval_fixture_update",
    "docs_followup",
    "support_followup_draft",
}
FORBIDDEN_FIELDS = {
    "raw_feedback_text",
    "raw_customer_message",
    "raw_ticket_payload",
    "requester_identity",
    "customer_identity",
    "user_identity",
    "screenshot",
    "screenshots",
    "keystrokes",
    "mouse_coordinates",
    "eye_tracking",
    "biometrics",
    "cookie",
    "cookies",
    "bearer_token",
    "signed_url",
    "agent_endpoint_secret",
    "model_api_key",
    "production_payload",
}
REQUIRED_TRUE_CHECKS = (
    "feedback_source_bounded",
    "delivery_class_known",
    "claim_boundary_reconstructed",
    "active_human_triage_recorded",
    "no_raw_payload_attached",
)
REQUIRED_FALSE_CHECKS = (
    "ai_review_only_basis",
    "automatic_customer_reply_allowed",
    "automatic_production_mutation_allowed",
    "external_publication_allowed",
)
PRIVACY = {
    **dual_loop.PRIVACY_FLAGS,
    "metadata_only": True,
    "raw_feedback_text_included": False,
    "raw_customer_message_included": False,
    "requester_identity_included": False,
    "customer_identity_included": False,
    "production_payload_included": False,
    "external_publication_performed": False,
    "automatic_customer_reply_performed": False,
    "automatic_production_mutation_performed": False,
}
RUNTIME = {
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
    "production_mutation_performed": False,
    "automatic_customer_reply_performed": False,
    "external_publication_performed": False,
}
CLAIM_BOUNDARY = {
    "current_claim": (
        "External feedback can re-enter the Product Loop as bounded metadata only "
        "when source scope, delivery class, active human triage, and claim boundary "
        "reconstruction are present."
    ),
    "not_claimed": [
        "customer identity disclosure",
        "raw customer feedback storage",
        "automatic customer reply",
        "automatic production mutation",
        "truth certification",
        "customer satisfaction guarantee",
        "replacement for product owner prioritization",
    ],
}


class ExternalFeedbackReceiptError(RuntimeError):
    """Readable external-feedback receipt failure."""


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
    hits: list[str] = []
    for mapping in walk_mappings(payload):
        for key, value in mapping.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in FORBIDDEN_FIELDS and value not in (None, False, "", []):
                hits.append(str(key))
    if hits:
        raise ExternalFeedbackReceiptError(f"external feedback receipt contains forbidden fields: {sorted(set(hits))}")


def base_case(case_id: str) -> dict[str, Any]:
    feedback_hash = dual_loop.sha256_text(f"external-feedback:{case_id}")[:24]
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": f"external-feedback-{case_id}",
        "source_delivery_class": "support_response_handoff",
        "source_handoff_ref": "support-response-handoff:pass",
        "feedback_ref": {
            "feedback_hash": feedback_hash,
            "source_channel": "support_ticket",
            "feedback_kind": "adoption_friction",
            "sentiment": "mixed",
            "severity": "medium",
            "bounded_tags": [
                "setup-confusion",
                "handoff-wording",
                "operator-next-step",
            ],
        },
        "human_reconstruction": {
            "active_triage_checkpoint_ids": [
                "feedback_scope_reconstruction",
                "claim_boundary_reconstruction",
                "next_loop_scope_reconstruction",
            ],
            "active_human_triage_recorded": True,
            "passive_attention_only": False,
            "operator_understands_no_customer_reply": True,
        },
        "checks": {
            "feedback_source_bounded": True,
            "delivery_class_known": True,
            "claim_boundary_reconstructed": True,
            "active_human_triage_recorded": True,
            "no_raw_payload_attached": True,
            "ai_review_only_basis": False,
            "automatic_customer_reply_allowed": False,
            "automatic_production_mutation_allowed": False,
            "external_publication_allowed": False,
        },
        "propagation": {
            "requested_next_action": "product_loop_backlog",
            "allowed_destination": "product_loop_backlog",
            "blocked_destinations": [
                "production_mutation",
                "automatic_customer_reply",
                "external_publication",
                "model_retraining_payload",
            ],
            "requires_product_owner_prioritization": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    return receipt


def build_case(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise ExternalFeedbackReceiptError(f"Unknown External Feedback case: {case_id}")
    receipt = base_case(case_id)
    if case_id == "blocked-raw-feedback":
        receipt["feedback_ref"]["payload_boundary"] = "raw_payload_attempt_rejected"
        receipt["checks"]["no_raw_payload_attached"] = False
    elif case_id == "blocked-identity":
        receipt["feedback_ref"]["identity_scope"] = "unbounded_requester_identity_attempt"
        receipt["checks"]["feedback_source_bounded"] = False
    elif case_id == "blocked-production-mutation":
        receipt["propagation"]["requested_next_action"] = "production_mutation"
        receipt["checks"]["automatic_production_mutation_allowed"] = True
    elif case_id == "blocked-ai-review-only":
        receipt["checks"]["ai_review_only_basis"] = True
        receipt["checks"]["active_human_triage_recorded"] = False
        receipt["human_reconstruction"]["active_human_triage_recorded"] = False
        receipt["human_reconstruction"]["passive_attention_only"] = True
    return validate_case(receipt)


def validate_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=SCHEMA_VERSION)
    reject_forbidden_fields(payload)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ExternalFeedbackReceiptError("external feedback receipt schema_version drifted")
    if payload.get("source_delivery_class") not in ALLOWED_DELIVERY_CLASSES:
        raise ExternalFeedbackReceiptError("external feedback delivery class is unsupported")

    feedback_ref = payload.get("feedback_ref")
    if not isinstance(feedback_ref, Mapping):
        raise ExternalFeedbackReceiptError("external feedback receipt missing feedback_ref")
    if not feedback_ref.get("feedback_hash") or not feedback_ref.get("source_channel"):
        raise ExternalFeedbackReceiptError("external feedback receipt missing bounded feedback reference")

    checks = payload.get("checks")
    if not isinstance(checks, Mapping):
        raise ExternalFeedbackReceiptError("external feedback receipt missing checks")
    propagation = payload.get("propagation")
    if not isinstance(propagation, Mapping):
        raise ExternalFeedbackReceiptError("external feedback receipt missing propagation")

    reasons: list[str] = []
    for key in REQUIRED_TRUE_CHECKS:
        if checks.get(key) is not True:
            reasons.append(f"missing_{key}")
    for key in REQUIRED_FALSE_CHECKS:
        if checks.get(key) is not False:
            reasons.append(key)
    next_action = str(propagation.get("requested_next_action", ""))
    if next_action not in ALLOWED_NEXT_ACTIONS:
        reasons.append("requested_next_action_outside_feedback_budget")

    human = payload.get("human_reconstruction")
    if not isinstance(human, Mapping):
        raise ExternalFeedbackReceiptError("external feedback receipt missing human_reconstruction")
    if human.get("passive_attention_only") is True:
        reasons.append("passive_attention_only")
    if human.get("operator_understands_no_customer_reply") is not True:
        reasons.append("operator_did_not_confirm_no_customer_reply")

    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ExternalFeedbackReceiptError("external feedback receipt privacy must be metadata-only")
    for key, expected in PRIVACY.items():
        if privacy.get(key) is not expected:
            raise ExternalFeedbackReceiptError(f"external feedback privacy.{key} must be {expected!r}")
    runtime = payload.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ExternalFeedbackReceiptError("external feedback receipt missing runtime")
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise ExternalFeedbackReceiptError(f"external feedback runtime.{key} must be {expected!r}")

    receipt = dict(payload)
    receipt["reasons"] = reasons
    receipt["reason_count"] = len(reasons)
    receipt["status"] = "accepted_for_product_loop" if not reasons else "blocked"
    receipt["decision"] = (
        "accept_external_feedback_into_product_loop"
        if not reasons
        else "block_external_feedback_propagation"
    )
    receipt["next_boundary"] = "product_loop_backlog_only_not_production"
    return receipt


def build_all_cases() -> dict[str, dict[str, Any]]:
    return {case_id: build_case(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    accepted = [case for case in cases.values() if case["status"] == "accepted_for_product_loop"]
    blocked = [case for case in cases.values() if case["status"] == "blocked"]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "purpose": (
            "Prove external feedback can re-enter the Product Loop as metadata-only "
            "evidence without raw customer content, automatic replies, or production mutation."
        ),
        "case_reports": [
            {
                "case_id": case["receipt_id"].replace("external-feedback-", ""),
                "status": case["status"],
                "decision": case["decision"],
                "reason_count": case["reason_count"],
                "reasons": list(case["reasons"]),
                "source_delivery_class": case["source_delivery_class"],
                "requested_next_action": case["propagation"]["requested_next_action"],
            }
            for case in cases.values()
        ],
        "accepted_case_count": len(accepted),
        "blocked_case_count": len(blocked),
        "feedback_loop_rules": {
            "external_feedback_is_metadata_only": True,
            "active_human_triage_required": True,
            "raw_feedback_text_rejected": True,
            "customer_identity_rejected": True,
            "ai_review_only_rejected": True,
            "production_mutation_blocked": True,
            "automatic_customer_reply_blocked": True,
            "next_boundary": "product_loop_backlog_only_not_production",
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    dual_loop.assert_metadata_only(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_cases(output_dir: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        dual_loop.write_json(output_dir / case_id / "external-feedback-receipt.json", payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "fixtures" / "external-feedback-receipt")
    args = parser.parse_args()

    cases = build_all_cases()
    selected = cases if args.case == "all" else {args.case: cases[args.case]}
    write_cases(args.output_dir, selected)
    print(
        json.dumps(
            {
                "schema_version": "external-feedback-receipt-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "output_dir": str(args.output_dir),
                "model_calls_performed": False,
                "production_mutation_performed": False,
                "external_publication_performed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
