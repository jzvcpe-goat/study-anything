#!/usr/bin/env python3
"""Build deterministic metadata-only Support Response Delivery Class artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import dual_loop  # noqa: E402


SCHEMA_VERSION = "support-response-handoff-case-v1"
REPORT_SCHEMA_VERSION = "support-response-delivery-class-verification-v1"
VERSION = "v0.3.31-alpha"
CASE_IDS = (
    "pass",
    "blocked-missing-reconstruction",
    "blocked-risk-over-budget",
    "blocked-unbounded-recipient",
    "blocked-policy-gap",
    "blocked-ai-summary-only",
)
DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "support-response-delivery-class"

PRIVACY = {
    "metadata_only": True,
    "raw_diff_included": False,
    "raw_source_text_included": False,
    "raw_report_text_included": False,
    "raw_response_text_included": False,
    "raw_ticket_payload_included": False,
    "raw_review_text_included": False,
    "raw_customer_payload_included": False,
    "user_identity_included": False,
    "screenshots_included": False,
    "keystrokes_included": False,
    "mouse_coordinates_included": False,
    "eye_tracking_included": False,
    "biometrics_included": False,
    "eye_tracking_or_biometrics_included": False,
    "real_secrets_included": False,
    "cookies_included": False,
    "bearer_tokens_included": False,
    "cookies_or_bearer_tokens_included": False,
    "signed_urls_included": False,
    "model_calls_performed": False,
    "user_owned_agent_credentials_included": False,
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "A support response draft can be treated as controlled customer handoff evidence "
        "only when Product Loop, Dual Loop, active human reconstruction, source "
        "grounding, support-policy scope, bounded requester scope, and CustomerHandoff boundaries pass."
    ),
    "not_claimed": [
        "automatic support reply delivery",
        "support resolution guarantee",
        "private requester identity disclosure",
        "legal certification",
        "financial advice certification",
        "complete factual correctness",
        "general model correctness",
        "production publication",
        "replacement for customer-specific legal or compliance review",
    ],
}

REQUIRED_TRUE_CHECKS = (
    "product_loop_passed",
    "dual_loop_gate_allowed",
    "delivery_trust_case_allowed",
    "customer_handoff_package_ready",
    "human_reconstruction_checkpoint_passed",
    "sandbox_risk_within_budget",
    "source_grounding_citations_present",
    "support_policy_scope_present",
    "issue_resolution_boundary_present",
    "recipient_scope_bounded",
    "claim_boundary_present",
    "rollback_or_correction_plan_present",
    "external_eval_receipts_supporting_only",
    "ai_summary_only_evidence_rejected",
)

REQUIRED_FALSE_CHECKS = (
    "automatic_customer_sending_allowed",
    "external_publication_allowed",
    "production_mutation_allowed",
    "raw_report_text_included",
    "raw_response_text_included",
    "raw_ticket_payload_included",
    "raw_customer_payload_included",
    "user_identity_included",
)


class SupportResponseDeliveryClassError(ValueError):
    """Raised when a support-response delivery class artifact is unsafe."""


def _base_case(case_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": VERSION,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "case_id": f"support-response-handoff-{case_id}",
        "delivery_class": "support_response_handoff",
        "report_artifact_ref": {
            "artifact_hash": dual_loop.sha256_text(f"support-response-artifact:{case_id}"),
            "report_locator": "metadata://support-response/draft",
            "report_type": "support_reply_draft",
            "source_count": 4,
            "citation_map_hash": dual_loop.sha256_text(f"support-response-citation-map:{case_id}"),
            "support_policy_hash": dual_loop.sha256_text(f"support-policy-scope:{case_id}"),
            "raw_report_text_included": False,
            "raw_response_text_included": False,
            "raw_ticket_payload_included": False,
            "raw_customer_payload_included": False,
            "user_identity_included": False,
        },
        "recipient_context_ref": {
            "recipient_class": "bounded_support_requester",
            "recipient_scope_hash": dual_loop.sha256_text(f"support-requester-scope:{case_id}"),
            "customer_payload_hash": dual_loop.sha256_text(f"support-ticket-payload:{case_id}"),
            "raw_customer_payload_included": False,
            "raw_ticket_payload_included": False,
            "user_identity_included": False,
        },
        "upstream_delivery_trust_case_ref": {
            "case_id": "delivery-trust-case-pass",
            "artifact_hash": dual_loop.sha256_text("delivery-trust-case-pass"),
            "raw_body_included": False,
        },
        "risk_budget": {
            "budget_level": "medium",
            "observed_level": "medium",
            "external_effects_allowed": False,
            "irreversible_effects_allowed": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }


def build_case(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise SupportResponseDeliveryClassError(f"Unknown support-response case: {case_id}")
    case = _base_case(case_id)
    checks = {
        "product_loop_passed": True,
        "dual_loop_gate_allowed": True,
        "delivery_trust_case_allowed": True,
        "customer_handoff_package_ready": True,
        "human_reconstruction_checkpoint_passed": True,
        "sandbox_risk_within_budget": True,
        "source_grounding_citations_present": True,
        "support_policy_scope_present": True,
        "issue_resolution_boundary_present": True,
        "recipient_scope_bounded": True,
        "claim_boundary_present": True,
        "rollback_or_correction_plan_present": True,
        "external_eval_receipts_supporting_only": True,
        "ai_summary_only_evidence_rejected": True,
        "automatic_customer_sending_allowed": False,
        "external_publication_allowed": False,
        "production_mutation_allowed": False,
        "raw_report_text_included": False,
        "raw_response_text_included": False,
        "raw_ticket_payload_included": False,
        "raw_customer_payload_included": False,
        "user_identity_included": False,
    }
    reasons: list[str] = []

    if case_id == "blocked-missing-reconstruction":
        checks["human_reconstruction_checkpoint_passed"] = False
        reasons.append("human_reconstruction_missing")
    elif case_id == "blocked-risk-over-budget":
        checks["sandbox_risk_within_budget"] = False
        case["risk_budget"]["observed_level"] = "high"
        reasons.append("sandbox_risk_outside_budget")
    elif case_id == "blocked-unbounded-recipient":
        checks["recipient_scope_bounded"] = False
        case["recipient_context_ref"]["recipient_class"] = "unknown_external_audience"
        reasons.append("recipient_scope_unbounded")
    elif case_id == "blocked-policy-gap":
        checks["support_policy_scope_present"] = False
        checks["issue_resolution_boundary_present"] = False
        reasons.append("support_policy_scope_missing")
    elif case_id == "blocked-ai-summary-only":
        checks["product_loop_passed"] = False
        checks["ai_summary_only_evidence_rejected"] = False
        reasons.extend(["product_loop_not_passed", "ai_summary_only_evidence_rejected"])

    allowed = not reasons
    case.update(
        {
            "status": "ready_for_controlled_support_response_handoff" if allowed else "blocked",
            "decision": "allow_controlled_support_response_handoff" if allowed else "block_support_response_handoff",
            "reasons": reasons,
            "checks": checks,
            "evidence_roles": {
                "product_loop": "required",
                "dual_loop": "required",
                "human_reconstruction": "required",
                "source_grounding": "required",
                "support_policy": "required",
                "recipient_scope": "required",
                "external_eval": "supporting_only_not_sufficient",
                "ai_summary": "never_sufficient_alone",
            },
            "handoff_controls": {
                "send_to_customer_allowed": False,
                "publish_external_allowed": False,
                "requires_active_reconstruction_summary": True,
                "requires_source_bound_citation_map": True,
                "requires_claim_boundary_notice": True,
                "requires_manual_delivery_action": True,
            },
        }
    )
    return validate_case(case)


def validate_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=SCHEMA_VERSION)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SupportResponseDeliveryClassError("support-response handoff schema_version drifted")
    if payload.get("delivery_class") != "support_response_handoff":
        raise SupportResponseDeliveryClassError("delivery_class must be support_response_handoff")
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        raise SupportResponseDeliveryClassError("privacy must be an object")
    for key, expected in PRIVACY.items():
        if privacy.get(key) is not expected:
            raise SupportResponseDeliveryClassError(f"privacy.{key} must be {expected!r}")
    for section_name in ("report_artifact_ref", "recipient_context_ref"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            raise SupportResponseDeliveryClassError(f"{section_name} must be an object")
        for flag in (
            "raw_report_text_included",
            "raw_response_text_included",
            "raw_customer_payload_included",
            "raw_ticket_payload_included",
            "user_identity_included",
        ):
            if section.get(flag, False) is not False:
                raise SupportResponseDeliveryClassError(f"{section_name}.{flag} must stay False")
        for field in (
            "raw_report_text",
            "report_text",
            "raw_response_text",
            "response_text",
            "raw_customer_payload",
            "customer_payload",
            "raw_ticket_payload",
            "ticket_payload",
            "requester_identity",
            "user_identity",
        ):
            if field in section and section.get(field) is not False:
                raise SupportResponseDeliveryClassError(f"{section_name}.{field} is forbidden")
    dual_loop.validate_isolation(payload, label=SCHEMA_VERSION)
    checks = payload.get("checks")
    if not isinstance(checks, Mapping):
        raise SupportResponseDeliveryClassError("checks must be an object")
    blocked_reasons = list(payload.get("reasons") or [])
    allowed = payload.get("decision") == "allow_controlled_support_response_handoff"
    if allowed:
        if payload.get("status") != "ready_for_controlled_support_response_handoff":
            raise SupportResponseDeliveryClassError("allowed case must be ready")
        if blocked_reasons:
            raise SupportResponseDeliveryClassError("allowed case must not have block reasons")
        for key in REQUIRED_TRUE_CHECKS:
            if checks.get(key) is not True:
                raise SupportResponseDeliveryClassError(f"allowed case requires checks.{key}=True")
    else:
        if payload.get("decision") != "block_support_response_handoff":
            raise SupportResponseDeliveryClassError("blocked case must block handoff")
        if not blocked_reasons:
            raise SupportResponseDeliveryClassError("blocked case must explain reasons")
    for key in REQUIRED_FALSE_CHECKS:
        if checks.get(key) is not False:
            raise SupportResponseDeliveryClassError(f"checks.{key} must stay False")
    controls = payload.get("handoff_controls")
    if not isinstance(controls, Mapping):
        raise SupportResponseDeliveryClassError("handoff_controls must be an object")
    if controls.get("send_to_customer_allowed") is not False:
        raise SupportResponseDeliveryClassError("automatic customer sending must stay blocked")
    if controls.get("publish_external_allowed") is not False:
        raise SupportResponseDeliveryClassError("external publication must stay blocked")
    if checks.get("external_eval_receipts_supporting_only") is not True:
        raise SupportResponseDeliveryClassError("external eval receipts must be supporting only")
    if not allowed and checks.get("human_reconstruction_checkpoint_passed") is False:
        if "human_reconstruction_missing" not in blocked_reasons:
            raise SupportResponseDeliveryClassError("missing reconstruction reason required")
    if not allowed and checks.get("sandbox_risk_within_budget") is False:
        if "sandbox_risk_outside_budget" not in blocked_reasons:
            raise SupportResponseDeliveryClassError("sandbox risk reason required")
    if not allowed and checks.get("recipient_scope_bounded") is False:
        if "recipient_scope_unbounded" not in blocked_reasons:
            raise SupportResponseDeliveryClassError("recipient scope reason required")
    if not allowed and checks.get("support_policy_scope_present") is False:
        if "support_policy_scope_missing" not in blocked_reasons:
            raise SupportResponseDeliveryClassError("support policy scope reason required")
    if not allowed and checks.get("ai_summary_only_evidence_rejected") is False:
        if "ai_summary_only_evidence_rejected" not in blocked_reasons:
            raise SupportResponseDeliveryClassError("AI-summary-only rejection reason required")
    return dict(payload)


def build_all_cases() -> dict[str, dict[str, Any]]:
    return {case_id: build_case(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        case = validate_case(cases[case_id])
        case_reports.append(
            {
                "case_id": case_id,
                "status": case["status"],
                "decision": case["decision"],
                "reasons": case["reasons"],
                "recipient_class": case["recipient_context_ref"].get("recipient_class"),
                "risk_observed_level": case["risk_budget"].get("observed_level"),
            }
        )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "delivery_class": "support_response_handoff",
        "case_reports": case_reports,
        "claim_boundary": CLAIM_BOUNDARY,
        "privacy": dict(PRIVACY),
        "runtime": {
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "customer_message_sent": False,
            "external_publication_performed": False,
            "support_reply_sent": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_support_response_delivery_class_handoff.py --check",
            "fixture_dir": "fixtures/support-response-delivery-class",
        },
    }
    dual_loop.assert_metadata_only(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_cases(output_dir: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        dual_loop.write_json(output_dir / case_id / "support-response-handoff-case.json", payload)


def run(args: argparse.Namespace) -> int:
    selected = CASE_IDS if args.case == "all" else (args.case,)
    cases = {case_id: build_case(case_id) for case_id in selected}
    output_dir = Path(args.output_dir)
    write_cases(output_dir, cases)
    report = build_report(build_all_cases())
    dual_loop.write_json(output_dir / "support-response-delivery-class-report.json", report)
    print(
        dual_loop.dump_json(
            {
                "schema_version": "support-response-delivery-class-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "output_dir": str(output_dir),
                "report": "support-response-delivery-class-report.json",
            }
        ),
        end="",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", *CASE_IDS), default="all")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
