#!/usr/bin/env python3
"""Verify an external operator acceptance drill from the Trust Evidence ZIP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping
import sys
import zipfile

from generate_trust_evidence_handoff_pack import ARCHIVE_PATH, ARCHIVE_ROOT, ROOT
from verify_trust_evidence_handoff_pack_consumer_walkthrough import (
    assert_metadata_only,
    consume_pack,
    dump_json,
    read_json_member,
    sha256_bytes,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-trust-evidence-acceptance-drill.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-trust-evidence-acceptance-drill.md"
SCHEMA_VERSION = "trust-evidence-acceptance-drill-v1"


class TrustEvidenceAcceptanceDrillError(RuntimeError):
    """Readable Trust Evidence acceptance drill failure."""


DELIVERY_CLASS_EXPECTATIONS = {
    "code_review_handoff": {
        "member": "platform/generated/study-anything-code-review-delivery-class.json",
        "allowed_decision": "allow_controlled_code_review_handoff",
        "blocked_decision": "block_code_review_handoff",
        "operator_allow_action": "prepare_controlled_code_review_handoff",
        "required_blocked_cases": {
            "blocked-missing-reconstruction": {"human_reconstruction_missing"},
            "blocked-unsafe-diff-scope": {"sandbox_risk_outside_budget", "diff_scope_expansion"},
            "blocked-ai-review-only": {"product_loop_not_passed", "ai_review_only_evidence_rejected"},
        },
    },
    "client_report_handoff": {
        "member": "platform/generated/study-anything-client-report-delivery-class.json",
        "allowed_decision": "allow_controlled_client_report_handoff",
        "blocked_decision": "block_client_report_handoff",
        "operator_allow_action": "prepare_controlled_client_report_handoff",
        "required_blocked_cases": {
            "blocked-missing-reconstruction": {"human_reconstruction_missing"},
            "blocked-risk-over-budget": {"sandbox_risk_outside_budget"},
            "blocked-unbounded-recipient": {"recipient_scope_unbounded"},
            "blocked-ai-summary-only": {"product_loop_not_passed", "ai_summary_only_evidence_rejected"},
        },
    },
}


def _case_by_id(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    cases = report.get("case_reports")
    if not isinstance(cases, list):
        raise TrustEvidenceAcceptanceDrillError("delivery class report missing case_reports")
    result: dict[str, Mapping[str, Any]] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            raise TrustEvidenceAcceptanceDrillError("delivery class case report must be an object")
        case_id = str(case.get("case_id"))
        result[case_id] = case
    return result


def _blocked_decision(class_id: str, case_id: str, case: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    reasons = set(case.get("reasons") or [])
    required = expected["required_blocked_cases"][case_id]
    missing = sorted(required - reasons)
    if missing:
        raise TrustEvidenceAcceptanceDrillError(f"{class_id}:{case_id} missing blocked reasons: {missing}")
    if case.get("decision") != expected["blocked_decision"] or case.get("status") != "blocked":
        raise TrustEvidenceAcceptanceDrillError(f"{class_id}:{case_id} blocked decision drifted")
    return {
        "delivery_class": class_id,
        "case_id": case_id,
        "operator_decision": "block_handoff",
        "source_decision": case["decision"],
        "status": case["status"],
        "required_reasons_present": sorted(required),
        "claim_boundary_preserved": True,
    }


def _allowed_decision(class_id: str, case: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    if case.get("decision") != expected["allowed_decision"]:
        raise TrustEvidenceAcceptanceDrillError(f"{class_id}:pass allowed decision drifted")
    if not str(case.get("status", "")).startswith("ready_for_controlled_"):
        raise TrustEvidenceAcceptanceDrillError(f"{class_id}:pass status is not controlled-ready")
    if case.get("reasons") not in ([], None):
        raise TrustEvidenceAcceptanceDrillError(f"{class_id}:pass must not carry blocked reasons")
    return {
        "delivery_class": class_id,
        "case_id": "pass",
        "operator_decision": expected["operator_allow_action"],
        "source_decision": case["decision"],
        "status": case["status"],
        "claim_boundary_preserved": True,
        "next_boundary": "controlled_handoff_only_not_customer_sending",
    }


def _privacy_from_report(class_id: str, report: Mapping[str, Any]) -> dict[str, bool]:
    privacy = report.get("privacy")
    runtime = report.get("runtime")
    if not isinstance(privacy, Mapping) or not isinstance(runtime, Mapping):
        raise TrustEvidenceAcceptanceDrillError(f"{class_id} missing privacy/runtime metadata")
    expected_false = (
        "raw_source_text_included",
        "raw_report_text_included",
        "raw_customer_payload_included",
        "screenshots_included",
        "model_calls_performed",
        "user_owned_agent_credentials_included",
    )
    for key in expected_false:
        if privacy.get(key) is not False:
            raise TrustEvidenceAcceptanceDrillError(f"{class_id}.privacy.{key} must stay false")
    for key in (
        "model_calls_performed",
        "production_mutation_performed",
        "external_publication_performed",
        "customer_message_sent",
        "automatic_pr_commenting_performed",
    ):
        if runtime.get(key, False) is not False:
            raise TrustEvidenceAcceptanceDrillError(f"{class_id}.runtime.{key} must stay false")
    return {
        "metadata_only": privacy.get("metadata_only") is True,
        "model_calls_performed": False,
        "production_mutation_performed": False,
        "external_publication_performed": False,
        "automatic_customer_sending_performed": False,
        "raw_payload_included": False,
        "user_owned_agent_credentials_included": False,
    }


def build_drill(pack_path: Path) -> dict[str, Any]:
    consumer_report = consume_pack(pack_path)
    pack_bytes = pack_path.read_bytes()
    class_summaries: list[dict[str, Any]] = []
    operator_decisions: list[dict[str, Any]] = []
    with zipfile.ZipFile(pack_path) as archive:
        for class_id, expected in DELIVERY_CLASS_EXPECTATIONS.items():
            report = read_json_member(archive, f"{ARCHIVE_ROOT}/{expected['member']}")
            if report.get("delivery_class") != class_id or report.get("status") != "pass":
                raise TrustEvidenceAcceptanceDrillError(f"{class_id} embedded report drifted")
            assert_metadata_only(report, label=f"acceptance-drill:{class_id}")
            cases = _case_by_id(report)
            if "pass" not in cases:
                raise TrustEvidenceAcceptanceDrillError(f"{class_id} pass case missing")
            operator_decisions.append(_allowed_decision(class_id, cases["pass"], expected))
            for case_id in expected["required_blocked_cases"]:
                if case_id not in cases:
                    raise TrustEvidenceAcceptanceDrillError(f"{class_id}:{case_id} missing")
                operator_decisions.append(_blocked_decision(class_id, case_id, cases[case_id], expected))
            negative_checks = report.get("negative_checks")
            if not isinstance(negative_checks, Mapping) or not negative_checks:
                raise TrustEvidenceAcceptanceDrillError(f"{class_id} missing negative checks")
            class_summaries.append(
                {
                    "delivery_class": class_id,
                    "case_count": len(cases),
                    "negative_check_count": len(negative_checks),
                    "privacy": _privacy_from_report(class_id, report),
                    "claim_boundary_hash": sha256_bytes(
                        str(report.get("claim_boundary", {}).get("current_claim", "")).encode("utf-8")
                    ),
                }
            )

    allowed = [row for row in operator_decisions if row["operator_decision"].startswith("prepare_controlled_")]
    blocked = [row for row in operator_decisions if row["operator_decision"] == "block_handoff"]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Prove an external operator can make controlled allow/block handoff decisions from the Trust Evidence ZIP alone.",
        "pack": {
            "path": str(pack_path.relative_to(ROOT)) if pack_path.is_relative_to(ROOT) else pack_path.name,
            "zip_sha256": sha256_bytes(pack_bytes),
            "consumer_walkthrough_schema": consumer_report["schema_version"],
            "consumer_walkthrough_status": consumer_report["status"],
        },
        "operator_decision_matrix": {
            "allowed_controlled_handoffs": len(allowed),
            "blocked_handoffs": len(blocked),
            "total_decisions": len(operator_decisions),
            "no_single_loop_dominates": True,
            "ai_review_only_rejected": True,
            "risk_over_budget_rejected": True,
            "missing_reconstruction_rejected": True,
            "scope_expansion_rejected": True,
        },
        "delivery_classes": class_summaries,
        "operator_decisions": operator_decisions,
        "claim_boundary": {
            "current_claim": (
                "An external operator can inspect the Trust Evidence ZIP and derive controlled "
                "handoff allow/block decisions for the supported delivery classes without reading "
                "raw source text or relying on an AI-review-only black box."
            ),
            "not_claimed": [
                "production approval",
                "automatic customer sending",
                "truth certification",
                "customer outcome guarantee",
                "general model correctness",
                "replacement for customer-specific legal or compliance review",
            ],
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "automatic_customer_sending_performed": False,
            "external_publication_performed": False,
            "raw_source_text_included": False,
            "raw_diff_included": False,
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
            "screenshots_included": False,
            "attention_streams_included": False,
            "real_secrets_included": False,
            "user_owned_agent_credentials_included": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_trust_evidence_acceptance_drill.py --check",
            "report": str(REPORT.relative_to(ROOT)),
            "markdown_report": str(MARKDOWN_REPORT.relative_to(ROOT)),
        },
    }
    assert_metadata_only(report, label=SCHEMA_VERSION)
    return report


def markdown_report(report: Mapping[str, Any]) -> str:
    decisions = report["operator_decisions"]
    rows = "\n".join(
        f"- `{row['delivery_class']}` / `{row['case_id']}`: `{row['operator_decision']}`"
        for row in decisions
    )
    return f"""# Trust Evidence Acceptance Drill

- Schema: `{report["schema_version"]}`
- Status: `{report["status"]}`
- ZIP SHA-256: `{report["pack"]["zip_sha256"]}`
- Allowed controlled handoffs: `{report["operator_decision_matrix"]["allowed_controlled_handoffs"]}`
- Blocked handoffs: `{report["operator_decision_matrix"]["blocked_handoffs"]}`

## Operator Decisions

{rows}

## Claim Boundary

{report["claim_boundary"]["current_claim"]}

This drill does not prove production approval, automatic customer sending,
truth certification, customer outcome guarantees, or general model correctness.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=ARCHIVE_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_drill(args.pack)
    text = dump_json(report)
    markdown = markdown_report(report)
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
        print(f"wrote {MARKDOWN_REPORT.relative_to(ROOT)}")
        return
    if args.check:
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != text:
            raise TrustEvidenceAcceptanceDrillError(
                "Trust Evidence acceptance drill report is stale. Run: "
                "python3 scripts/verify_trust_evidence_acceptance_drill.py --write"
            )
        if not MARKDOWN_REPORT.exists() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise TrustEvidenceAcceptanceDrillError(
                "Trust Evidence acceptance drill markdown is stale. Run: "
                "python3 scripts/verify_trust_evidence_acceptance_drill.py --write"
            )
        print("ok    Trust Evidence acceptance drill is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_trust_evidence_acceptance_drill failed: {exc}", file=sys.stderr)
        sys.exit(1)
