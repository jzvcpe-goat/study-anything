#!/usr/bin/env python3
"""Build deterministic metadata-only Code Review Delivery Class artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import dual_loop  # noqa: E402


SCHEMA_VERSION = "code-review-handoff-case-v1"
REPORT_SCHEMA_VERSION = "code-review-delivery-class-verification-v1"
VERSION = "v0.3.31-alpha"
CASE_IDS = (
    "pass",
    "blocked-missing-reconstruction",
    "blocked-unsafe-diff-scope",
    "blocked-ai-review-only",
)
DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "code-review-delivery-class"

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
        "A code-review handoff can be treated as controlled customer handoff "
        "only when the Product Loop, Dual Loop, human reconstruction, source "
        "grounding, and CustomerHandoff boundaries all pass."
    ),
    "not_claimed": [
        "production merge approval",
        "security certification",
        "legal certification",
        "general model correctness",
        "complete vulnerability discovery",
        "automatic PR commenting or customer sending",
    ],
}


class CodeReviewDeliveryClassError(ValueError):
    """Raised when a code-review delivery class artifact is unsafe."""


def _base_case(case_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": VERSION,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "case_id": f"code-review-handoff-{case_id}",
        "delivery_class": "code_review_handoff",
        "source_change_ref": {
            "repo_ref_hash": dual_loop.sha256_text("study-anything-demo-repo"),
            "change_set_hash": dual_loop.sha256_text(f"code-review-change:{case_id}"),
            "diff_locator": "metadata://code-review/change-set",
            "scope_class": "bounded_review_patch",
            "raw_diff_included": False,
            "raw_source_text_included": False,
        },
        "review_artifact_ref": {
            "artifact_hash": dual_loop.sha256_text(f"code-review-artifact:{case_id}"),
            "finding_count": 4,
            "citation_map_hash": dual_loop.sha256_text(f"citation-map:{case_id}"),
            "raw_review_text_included": False,
        },
        "upstream_delivery_trust_case_ref": {
            "case_id": "delivery-trust-case-pass",
            "artifact_hash": dual_loop.sha256_text("delivery-trust-case-pass"),
            "raw_body_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }


def build_case(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise CodeReviewDeliveryClassError(f"Unknown code-review case: {case_id}")
    case = _base_case(case_id)
    checks = {
        "product_loop_passed": True,
        "dual_loop_gate_allowed": True,
        "delivery_trust_case_allowed": True,
        "customer_handoff_package_ready": True,
        "human_reconstruction_checkpoint_passed": True,
        "sandbox_risk_within_budget": True,
        "source_grounding_citations_present": True,
        "external_eval_receipts_supporting_only": True,
        "ai_review_only_evidence_rejected": True,
        "automatic_pr_commenting_allowed": False,
        "automatic_customer_sending_allowed": False,
        "production_mutation_allowed": False,
    }
    reasons: list[str] = []

    if case_id == "blocked-missing-reconstruction":
        checks["human_reconstruction_checkpoint_passed"] = False
        reasons.append("human_reconstruction_missing")
    elif case_id == "blocked-unsafe-diff-scope":
        checks["sandbox_risk_within_budget"] = False
        case["source_change_ref"]["scope_class"] = "production_migration"
        reasons.extend(["sandbox_risk_outside_budget", "diff_scope_expansion"])
    elif case_id == "blocked-ai-review-only":
        checks["product_loop_passed"] = False
        checks["ai_review_only_evidence_rejected"] = False
        reasons.extend(["product_loop_not_passed", "ai_review_only_evidence_rejected"])
    allowed = not reasons
    case.update(
        {
            "status": "ready_for_controlled_code_review_handoff" if allowed else "blocked",
            "decision": "allow_controlled_code_review_handoff" if allowed else "block_code_review_handoff",
            "reasons": reasons,
            "checks": checks,
            "evidence_roles": {
                "product_loop": "required",
                "dual_loop": "required",
                "human_reconstruction": "required",
                "source_grounding": "required",
                "external_eval": "supporting_only_not_sufficient",
                "ai_review": "never_sufficient_alone",
            },
            "handoff_controls": {
                "post_to_pr_allowed": False,
                "send_to_customer_allowed": False,
                "merge_or_deploy_allowed": False,
                "requires_human_reconstruction_summary": True,
                "requires_source_bound_citation_map": True,
            },
        }
    )
    return validate_case(case)


def validate_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=SCHEMA_VERSION)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise CodeReviewDeliveryClassError("code-review handoff schema_version drifted")
    if payload.get("delivery_class") != "code_review_handoff":
        raise CodeReviewDeliveryClassError("delivery_class must be code_review_handoff")
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        raise CodeReviewDeliveryClassError("privacy must be an object")
    for key, expected in PRIVACY.items():
        if privacy.get(key) is not expected:
            raise CodeReviewDeliveryClassError(f"privacy.{key} must be {expected!r}")
    dual_loop.validate_isolation(payload, label=SCHEMA_VERSION)
    checks = payload.get("checks")
    if not isinstance(checks, Mapping):
        raise CodeReviewDeliveryClassError("checks must be an object")
    blocked_reasons = list(payload.get("reasons") or [])
    allowed = payload.get("decision") == "allow_controlled_code_review_handoff"
    if allowed:
        if payload.get("status") != "ready_for_controlled_code_review_handoff":
            raise CodeReviewDeliveryClassError("allowed case must be ready")
        if blocked_reasons:
            raise CodeReviewDeliveryClassError("allowed case must not have block reasons")
    else:
        if payload.get("decision") != "block_code_review_handoff":
            raise CodeReviewDeliveryClassError("blocked case must block handoff")
        if not blocked_reasons:
            raise CodeReviewDeliveryClassError("blocked case must explain reasons")
    if checks.get("automatic_pr_commenting_allowed") is not False:
        raise CodeReviewDeliveryClassError("automatic PR commenting must stay blocked")
    if checks.get("automatic_customer_sending_allowed") is not False:
        raise CodeReviewDeliveryClassError("automatic customer sending must stay blocked")
    if checks.get("production_mutation_allowed") is not False:
        raise CodeReviewDeliveryClassError("production mutation must stay blocked")
    if checks.get("external_eval_receipts_supporting_only") is not True:
        raise CodeReviewDeliveryClassError("external eval receipts must be supporting only")
    if not allowed and checks.get("human_reconstruction_checkpoint_passed") is False:
        if "human_reconstruction_missing" not in blocked_reasons:
            raise CodeReviewDeliveryClassError("missing reconstruction reason required")
    if not allowed and checks.get("sandbox_risk_within_budget") is False:
        if "sandbox_risk_outside_budget" not in blocked_reasons:
            raise CodeReviewDeliveryClassError("sandbox risk reason required")
    if not allowed and checks.get("ai_review_only_evidence_rejected") is False:
        if "ai_review_only_evidence_rejected" not in blocked_reasons:
            raise CodeReviewDeliveryClassError("AI-review-only rejection reason required")
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
                "source_scope": case["source_change_ref"].get("scope_class"),
            }
        )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "delivery_class": "code_review_handoff",
        "case_reports": case_reports,
        "claim_boundary": CLAIM_BOUNDARY,
        "privacy": dict(PRIVACY),
        "runtime": {
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "automatic_pr_commenting_performed": False,
            "customer_message_sent": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_code_review_delivery_class_handoff.py --check",
            "fixture_dir": "fixtures/code-review-delivery-class",
        },
    }
    dual_loop.assert_metadata_only(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_cases(output_dir: Path, cases: Mapping[str, Mapping[str, Any]]) -> None:
    for case_id, payload in cases.items():
        dual_loop.write_json(output_dir / case_id / "code-review-handoff-case.json", payload)


def run(args: argparse.Namespace) -> int:
    selected = CASE_IDS if args.case == "all" else (args.case,)
    cases = {case_id: build_case(case_id) for case_id in selected}
    output_dir = Path(args.output_dir)
    write_cases(output_dir, cases)
    report = build_report(build_all_cases())
    dual_loop.write_json(output_dir / "code-review-delivery-class-report.json", report)
    print(
        dual_loop.dump_json(
            {
                "schema_version": "code-review-delivery-class-cli-result-v1",
                "status": "ok",
                "case_ids": list(selected),
                "output_dir": str(output_dir),
                "report": "code-review-delivery-class-report.json",
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
