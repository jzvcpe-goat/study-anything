#!/usr/bin/env python3
"""Verify a metadata-only operator handoff rehearsal for Code Review delivery."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CODE_REVIEW_REPORT = ROOT / "platform" / "generated" / "study-anything-code-review-delivery-class.json"
CUSTOMER_REHEARSAL_REPORT = ROOT / "platform" / "generated" / "study-anything-customer-delivery-rehearsal.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-code-review-operator-handoff-rehearsal.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-code-review-operator-handoff-rehearsal.md"
SCHEMA_VERSION = "code-review-operator-handoff-rehearsal-v1"

FORBIDDEN_TEXT = (
    "OPENAI" + "_API_KEY",
    "MOONSHOT" + "_API_KEY",
    "AGENT_LLM_API_KEY" + "=",
    "github_pat_",
    "ghp_",
    "sk-proj-",
    "bearer ",
    "raw source text:",
    "raw diff:",
    "raw report text:",
    "raw review text:",
    "raw customer payload:",
    "screenshot:",
    "cookie:",
    "signed url:",
)
FALSE_PRIVACY_KEYS = (
    "model_calls_performed",
    "daemon_or_hosted_service_started",
    "production_mutation_performed",
    "automatic_pr_commenting_performed",
    "automatic_customer_sending_performed",
    "external_publication_performed",
    "raw_source_text_included",
    "raw_diff_included",
    "raw_report_text_included",
    "raw_review_text_included",
    "raw_customer_payload_included",
    "screenshots_included",
    "attention_streams_included",
    "real_secrets_included",
    "user_owned_agent_credentials_included",
)
READY_CONFIRMATIONS = (
    "code_review_delivery_class_ready",
    "customer_rehearsal_ready",
    "claim_boundary_visible",
    "operator_understands_not_send_approval",
    "no_raw_diff_or_review_text_attached",
    "actual_external_send_or_pr_comment_outside_system_only",
)
REQUIRED_NOT_CLAIMED = {
    "production merge approval",
    "security certification",
    "complete vulnerability discovery",
    "automatic PR commenting or customer sending",
    "customer send approval",
    "truth certification",
}
CODE_REVIEW_SOURCE_NOT_CLAIMED = {
    "production merge approval",
    "security certification",
    "complete vulnerability discovery",
    "automatic PR commenting or customer sending",
}
CUSTOMER_REHEARSAL_SOURCE_NOT_CLAIMED = {
    "customer send approval",
    "automatic customer sending",
    "truth certification",
}


class CodeReviewOperatorHandoffRehearsalError(RuntimeError):
    """Readable code-review operator handoff rehearsal verifier failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reject_forbidden_text(payload: Any, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = text.lower()
    hits = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if hits:
        raise CodeReviewOperatorHandoffRehearsalError(f"{label} contains forbidden private text: {hits}")


def assert_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise CodeReviewOperatorHandoffRehearsalError(f"{label}.{key} must be false")


def assert_absent_or_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if key in mapping and mapping.get(key) is not False:
            raise CodeReviewOperatorHandoffRehearsalError(f"{label}.{key} must be absent or false")


def require_not_claimed(claim_boundary: Mapping[str, Any], label: str, required: set[str]) -> None:
    not_claimed = {str(item) for item in claim_boundary.get("not_claimed", [])}
    missing = sorted(required - not_claimed)
    if missing:
        raise CodeReviewOperatorHandoffRehearsalError(f"{label} claim boundary missing not_claimed items: {missing}")


def validate_code_review_source(source: Mapping[str, Any]) -> dict[str, Any]:
    if source.get("schema_version") != "code-review-delivery-class-verification-v1":
        raise CodeReviewOperatorHandoffRehearsalError("code-review source schema_version drifted")
    if source.get("status") != "pass" or source.get("delivery_class") != "code_review_handoff":
        raise CodeReviewOperatorHandoffRehearsalError("code-review source must pass for code_review_handoff")
    privacy = source.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise CodeReviewOperatorHandoffRehearsalError("code-review source privacy must be metadata-only")
    assert_absent_or_false(privacy, FALSE_PRIVACY_KEYS, "code_review_source.privacy")
    runtime = source.get("runtime")
    if not isinstance(runtime, Mapping):
        raise CodeReviewOperatorHandoffRehearsalError("code-review source missing runtime")
    assert_false(
        runtime,
        (
            "model_calls_performed",
            "daemon_or_hosted_service_started",
            "production_mutation_performed",
            "automatic_pr_commenting_performed",
            "customer_message_sent",
        ),
        "code_review_source.runtime",
    )
    claim_boundary = source.get("claim_boundary")
    if not isinstance(claim_boundary, Mapping):
        raise CodeReviewOperatorHandoffRehearsalError("code-review source missing claim_boundary")
    require_not_claimed(claim_boundary, "code-review source", CODE_REVIEW_SOURCE_NOT_CLAIMED)

    cases = source.get("case_reports")
    if not isinstance(cases, list) or not cases:
        raise CodeReviewOperatorHandoffRehearsalError("code-review source missing case reports")
    ready_cases = [
        case
        for case in cases
        if isinstance(case, Mapping) and case.get("decision") == "allow_controlled_code_review_handoff"
    ]
    blocked_cases = [
        case
        for case in cases
        if isinstance(case, Mapping) and case.get("decision") == "block_code_review_handoff"
    ]
    if len(ready_cases) != 1 or len(blocked_cases) < 3:
        raise CodeReviewOperatorHandoffRehearsalError("code-review source must include one ready and at least three blocked cases")
    reject_forbidden_text(source, "code-review source")
    return {
        "ready_case": ready_cases[0],
        "blocked_case": blocked_cases[0],
        "blocked_case_count": len(blocked_cases),
    }


def validate_customer_rehearsal_source(source: Mapping[str, Any]) -> dict[str, Any]:
    if source.get("schema_version") != "customer-delivery-rehearsal-v1":
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal source schema_version drifted")
    if source.get("status") != "pass":
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal source must pass")
    privacy = source.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal source privacy must be metadata-only")
    assert_absent_or_false(privacy, FALSE_PRIVACY_KEYS, "customer_rehearsal_source.privacy")
    claim_boundary = source.get("claim_boundary")
    if not isinstance(claim_boundary, Mapping):
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal source missing claim_boundary")
    require_not_claimed(claim_boundary, "customer rehearsal source", CUSTOMER_REHEARSAL_SOURCE_NOT_CLAIMED)

    rehearsal = source.get("rehearsal")
    if not isinstance(rehearsal, Mapping):
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal source missing rehearsal")
    if rehearsal.get("ready_count") != 1 or int(rehearsal.get("blocked_count", 0)) < 5:
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal source must include one ready and at least five blocked cases")
    cases = rehearsal.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal source missing cases")
    ready_cases = [
        case
        for case in cases
        if isinstance(case, Mapping) and case.get("decision") == "ready_for_manual_send_review"
    ]
    blocked_cases = [
        case
        for case in cases
        if isinstance(case, Mapping) and case.get("decision") == "block_customer_delivery"
    ]
    if len(ready_cases) != 1 or len(blocked_cases) < 5:
        raise CodeReviewOperatorHandoffRehearsalError("customer rehearsal cases drifted")
    reject_forbidden_text(source, "customer rehearsal source")
    return {
        "ready_case": ready_cases[0],
        "blocked_case": blocked_cases[0],
        "blocked_case_count": len(blocked_cases),
    }


def rehearsal_case(
    *,
    case_id: str,
    code_review_case_ref: str,
    customer_rehearsal_case_ref: str,
    requested_action: str,
    confirmations: Mapping[str, bool],
    code_review_blocked: bool = False,
    customer_rehearsal_blocked: bool = False,
    raw_payload_requested: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if code_review_blocked:
        reasons.append("code_review_delivery_class_blocked")
    if customer_rehearsal_blocked:
        reasons.append("customer_delivery_rehearsal_blocked")
    if requested_action in {"automatic_pr_comment", "automatic_customer_send"}:
        reasons.append(f"{requested_action}_attempted")
    if raw_payload_requested:
        reasons.append("raw_diff_or_review_text_requested")
    for key in READY_CONFIRMATIONS:
        if confirmations.get(key) is not True:
            reasons.append(f"missing_{key}")

    ready = not reasons
    return {
        "case_id": case_id,
        "delivery_class": "code_review_handoff",
        "code_review_case_ref": code_review_case_ref,
        "customer_rehearsal_case_ref": customer_rehearsal_case_ref,
        "requested_action": requested_action,
        "status": "ready" if ready else "blocked",
        "decision": "ready_for_operator_handoff_decision" if ready else "block_operator_handoff",
        "operator_confirmation_inputs": dict(confirmations),
        "reason_count": len(reasons),
        "reasons": reasons,
        "automatic_pr_commenting_performed": False,
        "automatic_customer_sending_performed": False,
        "customer_visible_effect_performed": False,
        "production_mutation_performed": False,
        "external_publication_performed": False,
        "truth_certification_performed": False,
        "raw_diff_or_review_text_included": False,
        "requires_human_external_action_outside_system": True,
    }


def build_report(code_review_path: Path, customer_rehearsal_path: Path) -> dict[str, Any]:
    code_review = load_json(code_review_path)
    customer_rehearsal = load_json(customer_rehearsal_path)
    code_review_refs = validate_code_review_source(code_review)
    customer_refs = validate_customer_rehearsal_source(customer_rehearsal)

    confirmations = {key: True for key in READY_CONFIRMATIONS}
    cases = [
        rehearsal_case(
            case_id="ready-code-review-operator-decision",
            code_review_case_ref=str(code_review_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-code-review-class-blocked",
            code_review_case_ref=str(code_review_refs["blocked_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations=confirmations,
            code_review_blocked=True,
        ),
        rehearsal_case(
            case_id="block-customer-rehearsal-blocked",
            code_review_case_ref=str(code_review_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["blocked_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations=confirmations,
            customer_rehearsal_blocked=True,
        ),
        rehearsal_case(
            case_id="block-missing-not-send-approval-understanding",
            code_review_case_ref=str(code_review_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations={**confirmations, "operator_understands_not_send_approval": False},
        ),
        rehearsal_case(
            case_id="block-automatic-pr-comment",
            code_review_case_ref=str(code_review_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="automatic_pr_comment",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-automatic-customer-send",
            code_review_case_ref=str(code_review_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="automatic_customer_send",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-raw-diff-requested",
            code_review_case_ref=str(code_review_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations={**confirmations, "no_raw_diff_or_review_text_attached": False},
            raw_payload_requested=True,
        ),
    ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Rehearse a Code Review delivery-class operator handoff decision by combining the "
            "Code Review Delivery Class report and the Customer Delivery Rehearsal, without "
            "posting PR comments, sending customer messages, mutating production, or reading raw payloads."
        ),
        "sources": {
            "code_review_delivery_class": {
                "report": str(code_review_path.relative_to(ROOT)),
                "schema_version": code_review["schema_version"],
                "status": code_review["status"],
                "ready_case": code_review_refs["ready_case"]["case_id"],
                "blocked_case_count": code_review_refs["blocked_case_count"],
            },
            "customer_delivery_rehearsal": {
                "report": str(customer_rehearsal_path.relative_to(ROOT)),
                "schema_version": customer_rehearsal["schema_version"],
                "status": customer_rehearsal["status"],
                "ready_case": customer_refs["ready_case"]["case_id"],
                "blocked_case_count": customer_refs["blocked_case_count"],
            },
        },
        "rehearsal": {
            "mode": "operator_handoff_decision_only",
            "delivery_class": "code_review_handoff",
            "ready_count": sum(1 for case in cases if case["status"] == "ready"),
            "blocked_count": sum(1 for case in cases if case["status"] == "blocked"),
            "cases": cases,
            "operator_exit_criteria": [
                "exactly_one_ready_case_requires_both_source_reports_to_pass",
                "every_blocked_case_has_reasons",
                "automatic_pr_commenting_attempts_are_blocked",
                "automatic_customer_send_attempts_are_blocked",
                "raw_diff_review_text_and_credentials_are_absent",
                "actual_external_action_happens_outside_this_system_only",
            ],
        },
        "claim_boundary": {
            "current_claim": (
                "A platform Agent or external operator can prepare a Code Review handoff decision from "
                "metadata-only evidence when both the delivery class and customer-delivery rehearsal pass."
            ),
            "not_claimed": [
                "customer send approval",
                "actual customer send completed",
                "automatic PR commenting or customer sending",
                "production merge approval",
                "security certification",
                "complete vulnerability discovery",
                "truth certification",
                "customer outcome guarantee",
                "replacement for customer-specific legal or compliance review",
            ],
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "automatic_pr_commenting_performed": False,
            "automatic_customer_sending_performed": False,
            "external_publication_performed": False,
            "raw_source_text_included": False,
            "raw_diff_included": False,
            "raw_report_text_included": False,
            "raw_review_text_included": False,
            "raw_customer_payload_included": False,
            "screenshots_included": False,
            "attention_streams_included": False,
            "real_secrets_included": False,
            "user_owned_agent_credentials_included": False,
        },
        "negative_fixtures": negative_fixtures(),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_code_review_operator_handoff_rehearsal.py --check",
            "source_commands": [
                "python3 scripts/verify_code_review_delivery_class_handoff.py --check",
                "python3 scripts/verify_customer_delivery_rehearsal.py --check",
            ],
            "report": str(REPORT.relative_to(ROOT)),
            "markdown_report": str(MARKDOWN_REPORT.relative_to(ROOT)),
        },
    }
    validate_report(report)
    reject_forbidden_text(report, SCHEMA_VERSION)
    return report


def validate_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("status") != "pass":
        raise CodeReviewOperatorHandoffRehearsalError("rehearsal report schema/status drifted")
    rehearsal = report.get("rehearsal")
    if not isinstance(rehearsal, Mapping):
        raise CodeReviewOperatorHandoffRehearsalError("report missing rehearsal")
    if rehearsal.get("delivery_class") != "code_review_handoff":
        raise CodeReviewOperatorHandoffRehearsalError("rehearsal delivery_class drifted")
    cases = rehearsal.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CodeReviewOperatorHandoffRehearsalError("rehearsal must include cases")
    if rehearsal.get("ready_count") != 1:
        raise CodeReviewOperatorHandoffRehearsalError("rehearsal must include exactly one ready case")
    if int(rehearsal.get("blocked_count", 0)) < 6:
        raise CodeReviewOperatorHandoffRehearsalError("rehearsal must include at least six blocked cases")
    for case in cases:
        if not isinstance(case, Mapping):
            raise CodeReviewOperatorHandoffRehearsalError("rehearsal case must be an object")
        assert_false(
            case,
            (
                "automatic_pr_commenting_performed",
                "automatic_customer_sending_performed",
                "customer_visible_effect_performed",
                "production_mutation_performed",
                "external_publication_performed",
                "truth_certification_performed",
                "raw_diff_or_review_text_included",
            ),
            f"case.{case.get('case_id')}",
        )
        if case.get("requires_human_external_action_outside_system") is not True:
            raise CodeReviewOperatorHandoffRehearsalError(
                f"case {case.get('case_id')} must require outside-system human action"
            )
        if case.get("status") == "ready":
            confirmations = case.get("operator_confirmation_inputs")
            if not isinstance(confirmations, Mapping) or any(confirmations.get(key) is not True for key in READY_CONFIRMATIONS):
                raise CodeReviewOperatorHandoffRehearsalError("ready case must include all active confirmations")
            if case.get("decision") != "ready_for_operator_handoff_decision":
                raise CodeReviewOperatorHandoffRehearsalError("ready case decision drifted")
        elif case.get("status") == "blocked":
            if case.get("decision") != "block_operator_handoff":
                raise CodeReviewOperatorHandoffRehearsalError("blocked case decision drifted")
            if int(case.get("reason_count", 0)) < 1:
                raise CodeReviewOperatorHandoffRehearsalError("blocked case must include at least one reason")
        else:
            raise CodeReviewOperatorHandoffRehearsalError(f"unknown case status: {case.get('status')}")

    claim = report.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise CodeReviewOperatorHandoffRehearsalError("report missing claim_boundary")
    require_not_claimed(claim, "report", REQUIRED_NOT_CLAIMED)
    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise CodeReviewOperatorHandoffRehearsalError("rehearsal privacy must be metadata-only")
    assert_false(privacy, FALSE_PRIVACY_KEYS, "privacy")


def negative_case(case_id: str, report: Mapping[str, Any], mutator: Any) -> dict[str, str]:
    payload = copy.deepcopy(report)
    mutator(payload)
    try:
        validate_report(payload)
    except CodeReviewOperatorHandoffRehearsalError as exc:
        return {"case_id": case_id, "status": "rejected", "error": str(exc)}
    raise CodeReviewOperatorHandoffRehearsalError(f"Negative rehearsal fixture unexpectedly passed: {case_id}")


def negative_fixtures() -> list[dict[str, str]]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "rehearsal": {
            "delivery_class": "code_review_handoff",
            "ready_count": 1,
            "blocked_count": 6,
            "cases": [
                {
                    "case_id": "ready",
                    "status": "ready",
                    "decision": "ready_for_operator_handoff_decision",
                    "operator_confirmation_inputs": {key: True for key in READY_CONFIRMATIONS},
                    "reason_count": 0,
                    "automatic_pr_commenting_performed": False,
                    "automatic_customer_sending_performed": False,
                    "customer_visible_effect_performed": False,
                    "production_mutation_performed": False,
                    "external_publication_performed": False,
                    "truth_certification_performed": False,
                    "raw_diff_or_review_text_included": False,
                    "requires_human_external_action_outside_system": True,
                },
                *[
                    {
                        "case_id": f"blocked-{index}",
                        "status": "blocked",
                        "decision": "block_operator_handoff",
                        "operator_confirmation_inputs": {key: True for key in READY_CONFIRMATIONS},
                        "reason_count": 1,
                        "reasons": ["fixture_block"],
                        "automatic_pr_commenting_performed": False,
                        "automatic_customer_sending_performed": False,
                        "customer_visible_effect_performed": False,
                        "production_mutation_performed": False,
                        "external_publication_performed": False,
                        "truth_certification_performed": False,
                        "raw_diff_or_review_text_included": False,
                        "requires_human_external_action_outside_system": True,
                    }
                    for index in range(6)
                ],
            ],
        },
        "claim_boundary": {
            "not_claimed": sorted(REQUIRED_NOT_CLAIMED),
        },
        "privacy": {
            "metadata_only": True,
            **{key: False for key in FALSE_PRIVACY_KEYS},
        },
    }

    def allow_pr_comment(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][0]["automatic_pr_commenting_performed"] = True

    def remove_ready_case(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["ready_count"] = 0
        payload["rehearsal"]["cases"][0]["status"] = "blocked"

    def strip_not_send_understanding(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][0]["operator_confirmation_inputs"]["operator_understands_not_send_approval"] = False

    def unblock_without_reason(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][1]["reason_count"] = 0
        payload["rehearsal"]["cases"][1]["reasons"] = []

    def leak_raw_review(payload: dict[str, Any]) -> None:
        payload["privacy"]["raw_review_text_included"] = True

    def overclaim_security(payload: dict[str, Any]) -> None:
        payload["claim_boundary"]["not_claimed"].remove("security certification")

    return [
        negative_case("automatic_pr_commenting_performed", base, allow_pr_comment),
        negative_case("missing_ready_case", base, remove_ready_case),
        negative_case("missing_not_send_approval_understanding", base, strip_not_send_understanding),
        negative_case("blocked_case_without_reason", base, unblock_without_reason),
        negative_case("raw_review_text_included", base, leak_raw_review),
        negative_case("security_certification_overclaim", base, overclaim_security),
    ]


def markdown_report(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        f"- `{case['case_id']}`: `{case['decision']}` ({case['status']})"
        for case in report["rehearsal"]["cases"]
    )
    return f"""# Code Review Operator Handoff Rehearsal

- Schema: `{report["schema_version"]}`
- Status: `{report["status"]}`
- Mode: `{report["rehearsal"]["mode"]}`
- Delivery class: `{report["rehearsal"]["delivery_class"]}`
- Ready cases: `{report["rehearsal"]["ready_count"]}`
- Blocked cases: `{report["rehearsal"]["blocked_count"]}`

## Rehearsal Matrix

{rows}

## Claim Boundary

{report["claim_boundary"]["current_claim"]}

This rehearsal does not approve customer sending, post PR comments, merge or
deploy code, certify security, discover all vulnerabilities, certify truth,
guarantee outcomes, or replace customer-specific legal/compliance review.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-review-source", type=Path, default=CODE_REVIEW_REPORT)
    parser.add_argument("--customer-rehearsal-source", type=Path, default=CUSTOMER_REHEARSAL_REPORT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.code_review_source, args.customer_rehearsal_source)
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
            raise CodeReviewOperatorHandoffRehearsalError(
                "Code Review operator handoff rehearsal report is stale. Run: "
                "python3 scripts/verify_code_review_operator_handoff_rehearsal.py --write"
            )
        if not MARKDOWN_REPORT.exists() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise CodeReviewOperatorHandoffRehearsalError(
                "Code Review operator handoff rehearsal markdown is stale. Run: "
                "python3 scripts/verify_code_review_operator_handoff_rehearsal.py --write"
            )
        print("ok    Code Review operator handoff rehearsal is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_code_review_operator_handoff_rehearsal failed: {exc}", file=sys.stderr)
        sys.exit(1)
