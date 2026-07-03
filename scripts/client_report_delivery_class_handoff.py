#!/usr/bin/env python3
"""Build deterministic metadata-only Client Report Delivery Class artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import dual_loop  # noqa: E402


SCHEMA_VERSION = "client-report-handoff-case-v1"
REPORT_SCHEMA_VERSION = "client-report-delivery-class-verification-v1"
VERSION = "v0.3.31-alpha"
CASE_IDS = (
    "pass",
    "blocked-missing-reconstruction",
    "blocked-risk-over-budget",
    "blocked-unbounded-recipient",
    "blocked-ai-summary-only",
)
DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "client-report-delivery-class"

PRIVACY = {
    "metadata_only": True,
    "raw_diff_included": False,
    "raw_source_text_included": False,
    "raw_report_text_included": False,
    "raw_review_text_included": False,
    "raw_customer_payload_included": False,
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
        "A client report can be treated as controlled customer handoff evidence "
        "only when Product Loop, Dual Loop, active human reconstruction, source "
        "grounding, bounded recipient scope, and CustomerHandoff boundaries pass."
    ),
    "not_claimed": [
        "automatic customer delivery",
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
    "raw_customer_payload_included",
)


class ClientReportDeliveryClassError(ValueError):
    """Raised when a client-report delivery class artifact is unsafe."""


def _base_case(case_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": VERSION,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "case_id": f"client-report-handoff-{case_id}",
        "delivery_class": "client_report_handoff",
        "report_artifact_ref": {
            "artifact_hash": dual_loop.sha256_text(f"client-report-artifact:{case_id}"),
            "report_locator": "metadata://client-report/report",
            "report_type": "analysis_memo",
            "source_count": 6,
            "citation_map_hash": dual_loop.sha256_text(f"client-report-citation-map:{case_id}"),
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
        },
        "recipient_context_ref": {
            "recipient_class": "bounded_client_stakeholder",
            "recipient_scope_hash": dual_loop.sha256_text(f"client-recipient-scope:{case_id}"),
            "customer_payload_hash": dual_loop.sha256_text(f"client-customer-payload:{case_id}"),
            "raw_customer_payload_included": False,
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
        raise ClientReportDeliveryClassError(f"Unknown client-report case: {case_id}")
    case = _base_case(case_id)
    checks = {
        "product_loop_passed": True,
        "dual_loop_gate_allowed": True,
        "delivery_trust_case_allowed": True,
        "customer_handoff_package_ready": True,
        "human_reconstruction_checkpoint_passed": True,
        "sandbox_risk_within_budget": True,
        "source_grounding_citations_present": True,
        "recipient_scope_bounded": True,
        "claim_boundary_present": True,
        "rollback_or_correction_plan_present": True,
        "external_eval_receipts_supporting_only": True,
        "ai_summary_only_evidence_rejected": True,
        "automatic_customer_sending_allowed": False,
        "external_publication_allowed": False,
        "production_mutation_allowed": False,
        "raw_report_text_included": False,
        "raw_customer_payload_included": False,
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
    elif case_id == "blocked-ai-summary-only":
        checks["product_loop_passed"] = False
        checks["ai_summary_only_evidence_rejected"] = False
        reasons.extend(["product_loop_not_passed", "ai_summary_only_evidence_rejected"])

    allowed = not reasons
    case.update(
        {
            "status": "ready_for_controlled_client_report_handoff" if allowed else "blocked",
            "decision": "allow_controlled_client_report_handoff" if allowed else "block_client_report_handoff",
            "reasons": reasons,
            "checks": checks,
            "evidence_roles": {
                "product_loop": "required",
                "dual_loop": "required",
                "human_reconstruction": "required",
                "source_grounding": "required",
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
        raise ClientReportDeliveryClassError("client-report handoff schema_version drifted")
    if payload.get("delivery_class") != "client_report_handoff":
        raise ClientReportDeliveryClassError("delivery_class must be client_report_handoff")
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        raise ClientReportDeliveryClassError("privacy must be an object")
    for key, expected in PRIVACY.items():
        if privacy.get(key) is not expected:
            raise ClientReportDeliveryClassError(f"privacy.{key} must be {expected!r}")
    for section_name in ("report_artifact_ref", "recipient_context_ref"):
        section = payload.get(section_name)
        if not isinstance(section, Mapping):
            raise ClientReportDeliveryClassError(f"{section_name} must be an object")
        for flag in ("raw_report_text_included", "raw_customer_payload_included"):
            if section.get(flag, False) is not False:
                raise ClientReportDeliveryClassError(f"{section_name}.{flag} must stay False")
        for field in ("raw_report_text", "report_text", "raw_customer_payload", "customer_payload"):
            if field in section and section.get(field) is not False:
                raise ClientReportDeliveryClassError(f"{section_name}.{field} is forbidden")
    dual_loop.validate_isolation(payload, label=SCHEMA_VERSION)
    checks = payload.get("checks")
    if not isinstance(checks, Mapping):
        raise ClientReportDeliveryClassError("checks must be an object")
    blocked_reasons = list(payload.get("reasons") or [])
    allowed = payload.get("decision") == "allow_controlled_client_report_handoff"
    if allowed:
        if payload.get("status") != "ready_for_controlled_client_report_handoff":
            raise ClientReportDeliveryClassError("allowed case must be ready")
        if blocked_reasons:
            raise ClientReportDeliveryClassError("allowed case must not have block reasons")
        for key in REQUIRED_TRUE_CHECKS:
            if checks.get(key) is not True:
                raise ClientReportDeliveryClassError(f"allowed case requires checks.{key}=True")
    else:
        if payload.get("decision") != "block_client_report_handoff":
            raise ClientReportDeliveryClassError("blocked case must block handoff")
        if not blocked_reasons:
            raise ClientReportDeliveryClassError("blocked case must explain reasons")
    for key in REQUIRED_FALSE_CHECKS:
        if checks.get(key) is not False:
            raise ClientReportDeliveryClassError(f"checks.{key} must stay False")
    controls = payload.get("handoff_controls")
    if not isinstance(controls, Mapping):
        raise ClientReportDeliveryClassError("handoff_controls must be an object")
    if controls.get("send_to_customer_allowed") is not False:
        raise ClientReportDeliveryClassError("automatic customer sending must stay blocked")
    if controls.get("publish_external_allowed") is not False:
        raise ClientReportDeliveryClassError("external publication must stay blocked")
    if checks.get("external_eval_receipts_supporting_only") is not True:
        raise ClientReportDeliveryClassError("external eval receipts must be supporting only")
    if not allowed and checks.get("human_reconstruction_checkpoint_passed") is False:
        if "human_reconstruction_missing" not in blocked_reasons:
            raise ClientReportDeliveryClassError("missing reconstruction reason required")
    if not allowed and checks.get("sandbox_risk_within_budget") is False:
        if "sandbox_risk_outside_budget" not in blocked_reasons:
            raise ClientReportDeliveryClassError("sandbox risk reason required")
    if not allowed and checks.get("recipient_scope_bounded") is False:
        if "recipient_scope_unbounded" not in blocked_reasons:
            raise ClientReportDeliveryClassError("recipient scope reason required")
    if not allowed and checks.get("ai_summary_only_evidence_rejected") is False:
        if "ai_summary_only_evidence_rejected" not in blocked_reasons:
            raise ClientReportDeliveryClassError("AI-summary-only rejection reason required")
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
        "delivery_class": "client_report_handoff",
        "case_reports": case_reports,
        "claim_boundary": CLAIM_BOUNDARY,
        "privacy": dict(PRIVACY),
        "runtime": {
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "customer_message_sent": False,
            "external_publication_performed": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_client_report_delivery_class_handoff.py --check",
            "fixture_dir": "fixtures/client-report-delivery-class",
        },
    }
    dual_loop.assert_metadata_only(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_cases(output_dir: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        dual_loop.write_json(output_dir / case_id / "client-report-handoff-case.json", payload)


def run(args: argparse.Namespace) -> int:
    selected = CASE_IDS if args.case == "all" else (args.case,)
    cases = {case_id: build_case(case_id) for case_id in selected}
    output_dir = Path(args.output_dir)
    write_cases(output_dir, cases)
    report = build_report(build_all_cases())
    dual_loop.write_json(output_dir / "client-report-delivery-class-report.json", report)
    print(
        dual_loop.dump_json(
            {
                "schema_version": "client-report-delivery-class-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "output_dir": str(output_dir),
                "report": "client-report-delivery-class-report.json",
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
