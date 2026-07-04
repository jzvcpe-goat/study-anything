#!/usr/bin/env python3
"""Verify a metadata-only operator handoff rehearsal for Client Report delivery."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
CLIENT_REPORT = ROOT / "platform" / "generated" / "study-anything-client-report-delivery-class.json"
CUSTOMER_REHEARSAL = ROOT / "platform" / "generated" / "study-anything-customer-delivery-rehearsal.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-client-report-operator-handoff-rehearsal.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-client-report-operator-handoff-rehearsal.md"
SCHEMA_VERSION = "client-report-operator-handoff-rehearsal-v1"

FORBIDDEN_TEXT = (
    "OPENAI" + "_API_KEY",
    "MOONSHOT" + "_API_KEY",
    "AGENT_LLM_API_KEY" + "=",
    "github_pat_",
    "ghp_",
    "sk-proj-",
    "bearer ",
    "raw source text:",
    "raw report text:",
    "raw customer payload:",
    "screenshot:",
    "cookie:",
    "signed url:",
)
FALSE_PRIVACY_KEYS = (
    "model_calls_performed",
    "daemon_or_hosted_service_started",
    "production_mutation_performed",
    "automatic_customer_sending_performed",
    "external_publication_performed",
    "raw_source_text_included",
    "raw_report_text_included",
    "raw_customer_payload_included",
    "screenshots_included",
    "attention_streams_included",
    "real_secrets_included",
    "user_owned_agent_credentials_included",
)
READY_CONFIRMATIONS = (
    "client_report_delivery_class_ready",
    "customer_rehearsal_ready",
    "recipient_scope_bounded",
    "claim_boundary_visible",
    "operator_understands_not_send_approval",
    "no_raw_report_or_customer_payload_attached",
    "actual_external_delivery_outside_system_only",
)
FINAL_NOT_CLAIMED = {
    "customer send approval",
    "actual customer send completed",
    "automatic customer delivery",
    "external publication",
    "production publication",
    "complete factual correctness",
    "legal certification",
    "financial advice certification",
}
CLIENT_REPORT_SOURCE_NOT_CLAIMED = {
    "automatic customer delivery",
    "legal certification",
    "financial advice certification",
    "complete factual correctness",
    "production publication",
}
CUSTOMER_REHEARSAL_SOURCE_NOT_CLAIMED = {
    "customer send approval",
    "automatic customer sending",
    "truth certification",
}


class ClientReportOperatorHandoffRehearsalError(RuntimeError):
    """Readable client-report operator handoff rehearsal verifier failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reject_forbidden_text(payload: Any, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = text.lower()
    hits = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if hits:
        raise ClientReportOperatorHandoffRehearsalError(f"{label} contains forbidden private text: {hits}")


def assert_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise ClientReportOperatorHandoffRehearsalError(f"{label}.{key} must be false")


def assert_absent_or_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if key in mapping and mapping.get(key) is not False:
            raise ClientReportOperatorHandoffRehearsalError(f"{label}.{key} must be absent or false")


def require_not_claimed(claim_boundary: Mapping[str, Any], label: str, required: set[str]) -> None:
    not_claimed = {str(item) for item in claim_boundary.get("not_claimed", [])}
    missing = sorted(required - not_claimed)
    if missing:
        raise ClientReportOperatorHandoffRehearsalError(f"{label} claim boundary missing not_claimed items: {missing}")


def validate_client_report_source(source: Mapping[str, Any]) -> dict[str, Any]:
    if source.get("schema_version") != "client-report-delivery-class-verification-v1":
        raise ClientReportOperatorHandoffRehearsalError("client-report source schema_version drifted")
    if source.get("status") != "pass" or source.get("delivery_class") != "client_report_handoff":
        raise ClientReportOperatorHandoffRehearsalError("client-report source must pass for client_report_handoff")
    privacy = source.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ClientReportOperatorHandoffRehearsalError("client-report source privacy must be metadata-only")
    assert_absent_or_false(privacy, FALSE_PRIVACY_KEYS, "client_report_source.privacy")
    runtime = source.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ClientReportOperatorHandoffRehearsalError("client-report source missing runtime")
    assert_absent_or_false(
        runtime,
        (
            "model_calls_performed",
            "daemon_or_hosted_service_started",
            "production_mutation_performed",
            "customer_message_sent",
            "external_publication_performed",
        ),
        "client_report_source.runtime",
    )
    claim_boundary = source.get("claim_boundary")
    if not isinstance(claim_boundary, Mapping):
        raise ClientReportOperatorHandoffRehearsalError("client-report source missing claim_boundary")
    require_not_claimed(claim_boundary, "client-report source", CLIENT_REPORT_SOURCE_NOT_CLAIMED)

    cases = source.get("case_reports")
    if not isinstance(cases, list) or not cases:
        raise ClientReportOperatorHandoffRehearsalError("client-report source missing case reports")
    ready_cases = [
        case
        for case in cases
        if isinstance(case, Mapping) and case.get("decision") == "allow_controlled_client_report_handoff"
    ]
    blocked_cases = [
        case
        for case in cases
        if isinstance(case, Mapping) and case.get("decision") == "block_client_report_handoff"
    ]
    if len(ready_cases) != 1 or len(blocked_cases) < 4:
        raise ClientReportOperatorHandoffRehearsalError("client-report source must include one ready and at least four blocked cases")
    reject_forbidden_text(source, "client-report source")
    return {
        "ready_case": ready_cases[0],
        "blocked_case": blocked_cases[0],
        "blocked_case_count": len(blocked_cases),
    }


def validate_customer_rehearsal_source(source: Mapping[str, Any]) -> dict[str, Any]:
    if source.get("schema_version") != "customer-delivery-rehearsal-v1":
        raise ClientReportOperatorHandoffRehearsalError("customer rehearsal source schema_version drifted")
    if source.get("status") != "pass":
        raise ClientReportOperatorHandoffRehearsalError("customer rehearsal source must pass")
    privacy = source.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ClientReportOperatorHandoffRehearsalError("customer rehearsal source privacy must be metadata-only")
    assert_absent_or_false(privacy, FALSE_PRIVACY_KEYS, "customer_rehearsal_source.privacy")
    claim_boundary = source.get("claim_boundary")
    if not isinstance(claim_boundary, Mapping):
        raise ClientReportOperatorHandoffRehearsalError("customer rehearsal source missing claim_boundary")
    require_not_claimed(claim_boundary, "customer rehearsal source", CUSTOMER_REHEARSAL_SOURCE_NOT_CLAIMED)

    rehearsal = source.get("rehearsal")
    if not isinstance(rehearsal, Mapping):
        raise ClientReportOperatorHandoffRehearsalError("customer rehearsal source missing rehearsal")
    cases = rehearsal.get("cases")
    if not isinstance(cases, list) or rehearsal.get("ready_count") != 1 or int(rehearsal.get("blocked_count", 0)) < 5:
        raise ClientReportOperatorHandoffRehearsalError("customer rehearsal source must include one ready and at least five blocked cases")
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
        raise ClientReportOperatorHandoffRehearsalError("customer rehearsal cases drifted")
    reject_forbidden_text(source, "customer rehearsal source")
    return {
        "ready_case": ready_cases[0],
        "blocked_case": blocked_cases[0],
        "blocked_case_count": len(blocked_cases),
    }


def rehearsal_case(
    *,
    case_id: str,
    client_report_case_ref: str,
    customer_rehearsal_case_ref: str,
    requested_action: str,
    confirmations: Mapping[str, bool],
    client_report_blocked: bool = False,
    customer_rehearsal_blocked: bool = False,
    raw_payload_requested: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if client_report_blocked:
        reasons.append("client_report_delivery_class_blocked")
    if customer_rehearsal_blocked:
        reasons.append("customer_delivery_rehearsal_blocked")
    if requested_action in {"automatic_customer_send", "external_publication"}:
        reasons.append(f"{requested_action}_attempted")
    if raw_payload_requested:
        reasons.append("raw_report_or_customer_payload_requested")
    for key in READY_CONFIRMATIONS:
        if confirmations.get(key) is not True:
            reasons.append(f"missing_{key}")

    ready = not reasons
    return {
        "case_id": case_id,
        "delivery_class": "client_report_handoff",
        "client_report_case_ref": client_report_case_ref,
        "customer_rehearsal_case_ref": customer_rehearsal_case_ref,
        "requested_action": requested_action,
        "status": "ready" if ready else "blocked",
        "decision": "ready_for_operator_handoff_decision" if ready else "block_operator_handoff",
        "operator_confirmation_inputs": dict(confirmations),
        "reason_count": len(reasons),
        "reasons": reasons,
        "automatic_customer_sending_performed": False,
        "customer_visible_effect_performed": False,
        "production_mutation_performed": False,
        "external_publication_performed": False,
        "truth_certification_performed": False,
        "raw_report_or_customer_payload_included": False,
        "requires_human_external_action_outside_system": True,
    }


def build_report(client_report_path: Path, customer_rehearsal_path: Path) -> dict[str, Any]:
    client_report = load_json(client_report_path)
    customer_rehearsal = load_json(customer_rehearsal_path)
    client_refs = validate_client_report_source(client_report)
    customer_refs = validate_customer_rehearsal_source(customer_rehearsal)

    confirmations = {key: True for key in READY_CONFIRMATIONS}
    cases = [
        rehearsal_case(
            case_id="ready-client-report-operator-decision",
            client_report_case_ref=str(client_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-client-report-class-blocked",
            client_report_case_ref=str(client_refs["blocked_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations=confirmations,
            client_report_blocked=True,
        ),
        rehearsal_case(
            case_id="block-customer-rehearsal-blocked",
            client_report_case_ref=str(client_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["blocked_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations=confirmations,
            customer_rehearsal_blocked=True,
        ),
        rehearsal_case(
            case_id="block-missing-recipient-scope-confirmation",
            client_report_case_ref=str(client_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations={**confirmations, "recipient_scope_bounded": False},
        ),
        rehearsal_case(
            case_id="block-missing-not-send-approval-understanding",
            client_report_case_ref=str(client_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations={**confirmations, "operator_understands_not_send_approval": False},
        ),
        rehearsal_case(
            case_id="block-automatic-customer-send",
            client_report_case_ref=str(client_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="automatic_customer_send",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-external-publication",
            client_report_case_ref=str(client_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="external_publication",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-raw-report-requested",
            client_report_case_ref=str(client_refs["ready_case"]["case_id"]),
            customer_rehearsal_case_ref=str(customer_refs["ready_case"]["case_id"]),
            requested_action="prepare_operator_handoff_decision",
            confirmations={**confirmations, "no_raw_report_or_customer_payload_attached": False},
            raw_payload_requested=True,
        ),
    ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Rehearse a Client Report delivery-class operator handoff decision by combining the "
            "Client Report Delivery Class report and the Customer Delivery Rehearsal, without "
            "sending customer messages, publishing externally, mutating production, or reading raw payloads."
        ),
        "sources": {
            "client_report_delivery_class": {
                "report": str(client_report_path.relative_to(ROOT)),
                "schema_version": client_report["schema_version"],
                "status": client_report["status"],
                "ready_case": client_refs["ready_case"]["case_id"],
                "blocked_case_count": client_refs["blocked_case_count"],
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
            "delivery_class": "client_report_handoff",
            "ready_count": sum(1 for case in cases if case["status"] == "ready"),
            "blocked_count": sum(1 for case in cases if case["status"] == "blocked"),
            "cases": cases,
            "operator_exit_criteria": [
                "exactly_one_ready_case_requires_both_source_reports_to_pass",
                "every_blocked_case_has_reasons",
                "automatic_customer_send_attempts_are_blocked",
                "external_publication_attempts_are_blocked",
                "raw_report_customer_payload_and_credentials_are_absent",
                "actual_external_delivery_happens_outside_this_system_only",
            ],
        },
        "claim_boundary": {
            "current_claim": (
                "A platform Agent or external operator can prepare a Client Report handoff decision from "
                "metadata-only evidence when both the delivery class and customer-delivery rehearsal pass."
            ),
            "not_claimed": [
                "customer send approval",
                "actual customer send completed",
                "automatic customer delivery",
                "external publication",
                "production publication",
                "complete factual correctness",
                "legal certification",
                "financial advice certification",
                "customer outcome guarantee",
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
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
            "screenshots_included": False,
            "attention_streams_included": False,
            "real_secrets_included": False,
            "user_owned_agent_credentials_included": False,
        },
        "negative_fixtures": negative_fixtures(),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_client_report_operator_handoff_rehearsal.py --check",
            "source_commands": [
                "python3 scripts/verify_client_report_delivery_class_handoff.py --check",
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
        raise ClientReportOperatorHandoffRehearsalError("rehearsal report schema/status drifted")
    rehearsal = report.get("rehearsal")
    if not isinstance(rehearsal, Mapping):
        raise ClientReportOperatorHandoffRehearsalError("report missing rehearsal")
    if rehearsal.get("delivery_class") != "client_report_handoff":
        raise ClientReportOperatorHandoffRehearsalError("rehearsal delivery_class drifted")
    cases = rehearsal.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ClientReportOperatorHandoffRehearsalError("rehearsal must include cases")
    if rehearsal.get("ready_count") != 1:
        raise ClientReportOperatorHandoffRehearsalError("rehearsal must include exactly one ready case")
    if int(rehearsal.get("blocked_count", 0)) < 7:
        raise ClientReportOperatorHandoffRehearsalError("rehearsal must include at least seven blocked cases")
    for case in cases:
        if not isinstance(case, Mapping):
            raise ClientReportOperatorHandoffRehearsalError("rehearsal case must be an object")
        assert_false(
            case,
            (
                "automatic_customer_sending_performed",
                "customer_visible_effect_performed",
                "production_mutation_performed",
                "external_publication_performed",
                "truth_certification_performed",
                "raw_report_or_customer_payload_included",
            ),
            f"case.{case.get('case_id')}",
        )
        if case.get("requires_human_external_action_outside_system") is not True:
            raise ClientReportOperatorHandoffRehearsalError(
                f"case {case.get('case_id')} must require outside-system human action"
            )
        if case.get("status") == "ready":
            confirmations = case.get("operator_confirmation_inputs")
            if not isinstance(confirmations, Mapping) or any(confirmations.get(key) is not True for key in READY_CONFIRMATIONS):
                raise ClientReportOperatorHandoffRehearsalError("ready case must include all active confirmations")
            if case.get("decision") != "ready_for_operator_handoff_decision":
                raise ClientReportOperatorHandoffRehearsalError("ready case decision drifted")
        elif case.get("status") == "blocked":
            if case.get("decision") != "block_operator_handoff":
                raise ClientReportOperatorHandoffRehearsalError("blocked case decision drifted")
            if int(case.get("reason_count", 0)) < 1:
                raise ClientReportOperatorHandoffRehearsalError("blocked case must include at least one reason")
        else:
            raise ClientReportOperatorHandoffRehearsalError(f"unknown case status: {case.get('status')}")

    claim = report.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise ClientReportOperatorHandoffRehearsalError("report missing claim_boundary")
    require_not_claimed(claim, "report", FINAL_NOT_CLAIMED)
    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ClientReportOperatorHandoffRehearsalError("rehearsal privacy must be metadata-only")
    assert_false(privacy, FALSE_PRIVACY_KEYS, "privacy")


def negative_case(case_id: str, report: Mapping[str, Any], mutator: Any) -> dict[str, str]:
    payload = copy.deepcopy(report)
    mutator(payload)
    try:
        validate_report(payload)
    except ClientReportOperatorHandoffRehearsalError as exc:
        return {"case_id": case_id, "status": "rejected", "error": str(exc)}
    raise ClientReportOperatorHandoffRehearsalError(f"Negative rehearsal fixture unexpectedly passed: {case_id}")


def negative_fixtures() -> list[dict[str, str]]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "rehearsal": {
            "delivery_class": "client_report_handoff",
            "ready_count": 1,
            "blocked_count": 7,
            "cases": [
                {
                    "case_id": "ready",
                    "status": "ready",
                    "decision": "ready_for_operator_handoff_decision",
                    "operator_confirmation_inputs": {key: True for key in READY_CONFIRMATIONS},
                    "reason_count": 0,
                    "automatic_customer_sending_performed": False,
                    "customer_visible_effect_performed": False,
                    "production_mutation_performed": False,
                    "external_publication_performed": False,
                    "truth_certification_performed": False,
                    "raw_report_or_customer_payload_included": False,
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
                        "automatic_customer_sending_performed": False,
                        "customer_visible_effect_performed": False,
                        "production_mutation_performed": False,
                        "external_publication_performed": False,
                        "truth_certification_performed": False,
                        "raw_report_or_customer_payload_included": False,
                        "requires_human_external_action_outside_system": True,
                    }
                    for index in range(7)
                ],
            ],
        },
        "claim_boundary": {
            "not_claimed": sorted(FINAL_NOT_CLAIMED),
        },
        "privacy": {
            "metadata_only": True,
            **{key: False for key in FALSE_PRIVACY_KEYS},
        },
    }

    def allow_customer_send(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][0]["automatic_customer_sending_performed"] = True

    def remove_ready_case(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["ready_count"] = 0
        payload["rehearsal"]["cases"][0]["status"] = "blocked"

    def strip_recipient_scope(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][0]["operator_confirmation_inputs"]["recipient_scope_bounded"] = False

    def unblock_without_reason(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][1]["reason_count"] = 0
        payload["rehearsal"]["cases"][1]["reasons"] = []

    def leak_raw_report(payload: dict[str, Any]) -> None:
        payload["privacy"]["raw_report_text_included"] = True

    def overclaim_factual_correctness(payload: dict[str, Any]) -> None:
        payload["claim_boundary"]["not_claimed"].remove("complete factual correctness")

    return [
        negative_case("automatic_customer_sending_performed", base, allow_customer_send),
        negative_case("missing_ready_case", base, remove_ready_case),
        negative_case("missing_recipient_scope_confirmation", base, strip_recipient_scope),
        negative_case("blocked_case_without_reason", base, unblock_without_reason),
        negative_case("raw_report_text_included", base, leak_raw_report),
        negative_case("complete_factual_correctness_overclaim", base, overclaim_factual_correctness),
    ]


def markdown_report(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        f"- `{case['case_id']}`: `{case['decision']}` ({case['status']})"
        for case in report["rehearsal"]["cases"]
    )
    return f"""# Client Report Operator Handoff Rehearsal

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

This rehearsal does not approve customer sending, publish externally, mutate
production, certify legal or financial advice, certify complete factual
correctness, guarantee outcomes, or replace customer-specific legal/compliance
review.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-report-source", type=Path, default=CLIENT_REPORT)
    parser.add_argument("--customer-rehearsal-source", type=Path, default=CUSTOMER_REHEARSAL)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.client_report_source, args.customer_rehearsal_source)
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
            raise ClientReportOperatorHandoffRehearsalError(
                "Client Report operator handoff rehearsal report is stale. Run: "
                "python3 scripts/verify_client_report_operator_handoff_rehearsal.py --write"
            )
        if not MARKDOWN_REPORT.exists() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise ClientReportOperatorHandoffRehearsalError(
                "Client Report operator handoff rehearsal markdown is stale. Run: "
                "python3 scripts/verify_client_report_operator_handoff_rehearsal.py --write"
            )
        print("ok    Client Report operator handoff rehearsal is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_client_report_operator_handoff_rehearsal failed: {exc}", file=sys.stderr)
        sys.exit(1)
