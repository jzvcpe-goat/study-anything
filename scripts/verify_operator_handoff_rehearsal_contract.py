#!/usr/bin/env python3
"""Verify the shared metadata-only Operator Handoff Rehearsal contract."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "platform" / "schemas" / "delivery-trust" / "operator-handoff-rehearsal-contract-v1.schema.json"
CODE_REVIEW_REPORT = ROOT / "platform" / "generated" / "study-anything-code-review-operator-handoff-rehearsal.json"
CLIENT_REPORT = ROOT / "platform" / "generated" / "study-anything-client-report-operator-handoff-rehearsal.json"
SUPPORT_RESPONSE_REPORT = ROOT / "platform" / "generated" / "study-anything-support-response-operator-handoff-rehearsal.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-operator-handoff-rehearsal-contract.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-operator-handoff-rehearsal-contract.md"
SCHEMA_VERSION = "operator-handoff-rehearsal-contract-v1"

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
    "raw response text:",
    "raw ticket payload:",
    "raw customer payload:",
    "screenshot:",
    "cookie:",
    "signed url:",
)
SIDE_EFFECT_KEYS = (
    "model_calls_performed",
    "daemon_or_hosted_service_started",
    "production_mutation_performed",
    "automatic_pr_commenting_performed",
    "automatic_customer_sending_performed",
    "customer_visible_effect_performed",
    "external_publication_performed",
    "truth_certification_performed",
)
RAW_PAYLOAD_KEYS = (
    "raw_source_text_included",
    "raw_diff_included",
    "raw_report_text_included",
    "raw_review_text_included",
    "raw_customer_payload_included",
    "raw_diff_or_review_text_included",
    "raw_report_or_customer_payload_included",
    "raw_response_or_ticket_payload_included",
    "screenshots_included",
    "attention_streams_included",
    "real_secrets_included",
    "user_owned_agent_credentials_included",
    "raw_response_text_included",
    "raw_ticket_payload_included",
    "user_identity_included",
)
COMMON_NOT_CLAIMED = {
    "customer send approval",
    "actual customer send completed",
    "customer outcome guarantee",
    "replacement for customer-specific legal or compliance review",
}
CLASS_CONFIGS = {
    "code_review_handoff": {
        "report": CODE_REVIEW_REPORT,
        "schema_version": "code-review-operator-handoff-rehearsal-v1",
        "min_blocked": 6,
        "required_not_claimed": {
            *COMMON_NOT_CLAIMED,
            "automatic PR commenting or customer sending",
            "production merge approval",
            "security certification",
            "complete vulnerability discovery",
        },
        "required_confirmations": {
            "claim_boundary_visible",
            "operator_understands_not_send_approval",
            "actual_external_send_or_pr_comment_outside_system_only",
        },
    },
    "client_report_handoff": {
        "report": CLIENT_REPORT,
        "schema_version": "client-report-operator-handoff-rehearsal-v1",
        "min_blocked": 7,
        "required_not_claimed": {
            *COMMON_NOT_CLAIMED,
            "automatic customer delivery",
            "external publication",
            "production publication",
            "complete factual correctness",
            "legal certification",
            "financial advice certification",
        },
        "required_confirmations": {
            "recipient_scope_bounded",
            "claim_boundary_visible",
            "operator_understands_not_send_approval",
            "actual_external_delivery_outside_system_only",
        },
    },
    "support_response_handoff": {
        "report": SUPPORT_RESPONSE_REPORT,
        "schema_version": "support-response-operator-handoff-rehearsal-v1",
        "min_blocked": 8,
        "required_not_claimed": {
            *COMMON_NOT_CLAIMED,
            "automatic support reply delivery",
            "automatic customer delivery",
            "external publication",
            "production publication",
            "complete factual correctness",
            "support resolution guarantee",
            "private requester identity disclosure",
            "legal certification",
            "financial advice certification",
        },
        "required_confirmations": {
            "recipient_scope_bounded",
            "support_policy_scope_bounded",
            "claim_boundary_visible",
            "operator_understands_not_send_approval",
            "actual_external_delivery_outside_system_only",
        },
    },
}


class OperatorHandoffContractError(RuntimeError):
    """Readable shared operator handoff contract failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reject_forbidden_text(payload: Any, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = text.lower()
    hits = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if hits:
        raise OperatorHandoffContractError(f"{label} contains forbidden private text: {hits}")


def assert_absent_or_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if key in mapping and mapping.get(key) is not False:
            raise OperatorHandoffContractError(f"{label}.{key} must be absent or false")


def require_not_claimed(claim_boundary: Mapping[str, Any], label: str, required: set[str]) -> None:
    not_claimed = {str(item) for item in claim_boundary.get("not_claimed", [])}
    missing = sorted(required - not_claimed)
    if missing:
        raise OperatorHandoffContractError(f"{label} claim boundary missing not_claimed items: {missing}")


def reason_categories(cases: list[Mapping[str, Any]]) -> list[str]:
    reasons: set[str] = set()
    for case in cases:
        for reason in case.get("reasons", []):
            reasons.add(str(reason))
    return sorted(reasons)


def validate_class_report(delivery_class: str, path: Path) -> dict[str, Any]:
    config = CLASS_CONFIGS[delivery_class]
    report = load_json(path)
    if report.get("schema_version") != config["schema_version"] or report.get("status") != "pass":
        raise OperatorHandoffContractError(f"{delivery_class} report schema/status drifted")
    reject_forbidden_text(report, delivery_class)

    rehearsal = report.get("rehearsal")
    if not isinstance(rehearsal, Mapping) or rehearsal.get("delivery_class") != delivery_class:
        raise OperatorHandoffContractError(f"{delivery_class} missing rehearsal contract")
    if rehearsal.get("mode") != "operator_handoff_decision_only":
        raise OperatorHandoffContractError(f"{delivery_class} must stay decision-only")
    cases = rehearsal.get("cases")
    if not isinstance(cases, list) or not cases:
        raise OperatorHandoffContractError(f"{delivery_class} missing cases")
    ready_cases = [case for case in cases if isinstance(case, Mapping) and case.get("status") == "ready"]
    blocked_cases = [case for case in cases if isinstance(case, Mapping) and case.get("status") == "blocked"]
    if len(ready_cases) != 1 or rehearsal.get("ready_count") != 1:
        raise OperatorHandoffContractError(f"{delivery_class} must include exactly one ready case")
    if len(blocked_cases) < int(config["min_blocked"]) or int(rehearsal.get("blocked_count", 0)) < int(config["min_blocked"]):
        raise OperatorHandoffContractError(f"{delivery_class} blocked case coverage is too low")

    ready_confirmations = ready_cases[0].get("operator_confirmation_inputs")
    if not isinstance(ready_confirmations, Mapping):
        raise OperatorHandoffContractError(f"{delivery_class} ready case missing active confirmations")
    missing_confirmations = sorted(str(item) for item in config["required_confirmations"] if ready_confirmations.get(item) is not True)
    if missing_confirmations:
        raise OperatorHandoffContractError(f"{delivery_class} ready case missing confirmations: {missing_confirmations}")

    for case in cases:
        if not isinstance(case, Mapping):
            raise OperatorHandoffContractError(f"{delivery_class} case must be an object")
        assert_absent_or_false(case, SIDE_EFFECT_KEYS, f"{delivery_class}.case.{case.get('case_id')}")
        assert_absent_or_false(case, RAW_PAYLOAD_KEYS, f"{delivery_class}.case.{case.get('case_id')}")
        if case.get("requires_human_external_action_outside_system") is not True:
            raise OperatorHandoffContractError(f"{delivery_class} case must require outside-system human action")
        if case.get("status") == "ready":
            if case.get("decision") != "ready_for_operator_handoff_decision":
                raise OperatorHandoffContractError(f"{delivery_class} ready case decision drifted")
            if any(value is not True for value in dict(ready_confirmations).values()):
                raise OperatorHandoffContractError(f"{delivery_class} ready case confirmations must all be true")
        elif case.get("status") == "blocked":
            if case.get("decision") != "block_operator_handoff":
                raise OperatorHandoffContractError(f"{delivery_class} blocked case decision drifted")
            if int(case.get("reason_count", 0)) < 1:
                raise OperatorHandoffContractError(f"{delivery_class} blocked case must include a reason")
        else:
            raise OperatorHandoffContractError(f"{delivery_class} has unknown case status: {case.get('status')}")

    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise OperatorHandoffContractError(f"{delivery_class} privacy must be metadata-only")
    assert_absent_or_false(privacy, SIDE_EFFECT_KEYS, f"{delivery_class}.privacy")
    assert_absent_or_false(privacy, RAW_PAYLOAD_KEYS, f"{delivery_class}.privacy")
    claim = report.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise OperatorHandoffContractError(f"{delivery_class} missing claim boundary")
    require_not_claimed(claim, delivery_class, set(config["required_not_claimed"]))

    categories = reason_categories(blocked_cases)
    return {
        "delivery_class": delivery_class,
        "report": str(path.relative_to(ROOT)),
        "schema_version": str(report["schema_version"]),
        "status": "pass",
        "mode": str(rehearsal["mode"]),
        "ready_case": str(ready_cases[0]["case_id"]),
        "ready_count": len(ready_cases),
        "blocked_count": len(blocked_cases),
        "blocked_reason_categories": categories,
        "required_confirmations": sorted(str(item) for item in ready_confirmations),
        "not_claimed_count": len(claim.get("not_claimed", [])),
    }


def validate_schema_file() -> dict[str, str]:
    schema = load_json(SCHEMA)
    if schema.get("properties", {}).get("schema_version", {}).get("const") != SCHEMA_VERSION:
        raise OperatorHandoffContractError("operator handoff schema const drifted")
    return {"path": str(SCHEMA.relative_to(ROOT)), "schema_version": SCHEMA_VERSION}


def build_report(code_review_path: Path, client_report_path: Path) -> dict[str, Any]:
    schema_ref = validate_schema_file()
    classes = [
        validate_class_report("code_review_handoff", code_review_path),
        validate_class_report("client_report_handoff", client_report_path),
        validate_class_report("support_response_handoff", SUPPORT_RESPONSE_REPORT),
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Verify the shared operator handoff rehearsal contract across supported delivery classes "
            "without replacing class-specific verifiers or crossing customer-visible boundaries."
        ),
        "schema": schema_ref,
        "shared_contract": {
            "mode": "operator_handoff_decision_only",
            "supported_delivery_classes": [item["delivery_class"] for item in classes],
            "source_reports_must_pass": True,
            "ready_rule": "exactly_one_ready_case_with_all_active_confirmations_true",
            "blocked_rule": "blocked_cases_must_include_reasons",
            "automatic_external_actions_blocked": [
                "automatic_pr_commenting",
                "automatic_customer_sending",
                "external_publication",
                "production_mutation",
            ],
            "raw_payloads_forbidden": [
                "raw_source_text",
                "raw_diff",
                "raw_review_text",
                "raw_report_text",
                "raw_customer_payload",
                "screenshots",
                "attention_streams",
                "secrets",
                "user_owned_agent_credentials",
            ],
            "human_boundary": "operator may prepare a decision, but actual external action happens outside this system",
            "class_specific_verifiers_remain_authoritative": True,
        },
        "delivery_classes": classes,
        "coverage": {
            "delivery_class_count": len(classes),
            "all_classes_have_one_ready_case": all(item["ready_count"] == 1 for item in classes),
            "all_classes_have_blocked_cases": all(item["blocked_count"] >= 1 for item in classes),
            "all_supported_delivery_classes_share_contract": True,
            "operator_handoff_is_not_customer_send": True,
            "operator_handoff_is_not_ai_review_only": True,
        },
        "claim_boundary": {
            "current_claim": (
            "Code Review, Client Report, and Support Response delivery classes share a metadata-only operator handoff "
            "contract: a platform Agent can prepare a bounded ready/block decision, but cannot send, "
            "publish, comment, merge, mutate production, certify truth, or replace customer-specific review."
            ),
            "not_claimed": [
                "customer send approval",
                "actual customer send completed",
                "automatic customer delivery",
                "automatic PR commenting",
                "external publication",
                "production mutation",
                "production merge approval",
                "security certification",
                "legal certification",
                "financial advice certification",
                "complete factual correctness",
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
            "customer_visible_effect_performed": False,
            "raw_source_text_included": False,
            "raw_diff_included": False,
            "raw_review_text_included": False,
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
            "screenshots_included": False,
            "attention_streams_included": False,
            "real_secrets_included": False,
            "user_owned_agent_credentials_included": False,
        },
        "negative_fixtures": negative_fixtures(classes),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_operator_handoff_rehearsal_contract.py --check",
            "source_commands": [
                "python3 scripts/verify_code_review_operator_handoff_rehearsal.py --check",
                "python3 scripts/verify_client_report_operator_handoff_rehearsal.py --check",
                "python3 scripts/verify_support_response_operator_handoff_rehearsal.py --check",
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
        raise OperatorHandoffContractError("contract report schema/status drifted")
    classes = report.get("delivery_classes")
    if not isinstance(classes, list) or len(classes) < 2:
        raise OperatorHandoffContractError("contract must include at least two delivery classes")
    class_ids = [item.get("delivery_class") for item in classes if isinstance(item, Mapping)]
    if class_ids != ["code_review_handoff", "client_report_handoff", "support_response_handoff"]:
        raise OperatorHandoffContractError(f"delivery class order drifted: {class_ids}")
    for item in classes:
        if not isinstance(item, Mapping):
            raise OperatorHandoffContractError("delivery class summary must be an object")
        if item.get("ready_count") != 1:
            raise OperatorHandoffContractError(f"{item.get('delivery_class')} must have exactly one ready case")
        if int(item.get("blocked_count", 0)) < 1:
            raise OperatorHandoffContractError(f"{item.get('delivery_class')} must have blocked cases")
        confirmations = item.get("required_confirmations")
        if not isinstance(confirmations, list) or "operator_understands_not_send_approval" not in confirmations:
            raise OperatorHandoffContractError(f"{item.get('delivery_class')} missing operator understanding confirmation")
        categories = item.get("blocked_reason_categories")
        if not isinstance(categories, list) or not categories:
            raise OperatorHandoffContractError(f"{item.get('delivery_class')} missing blocked reason categories")
    shared = report.get("shared_contract")
    if not isinstance(shared, Mapping) or shared.get("class_specific_verifiers_remain_authoritative") is not True:
        raise OperatorHandoffContractError("shared contract must keep class verifiers authoritative")
    coverage = report.get("coverage")
    if not isinstance(coverage, Mapping):
        raise OperatorHandoffContractError("contract missing coverage")
    for key in (
        "all_classes_have_one_ready_case",
        "all_classes_have_blocked_cases",
        "operator_handoff_is_not_customer_send",
        "operator_handoff_is_not_ai_review_only",
    ):
        if coverage.get(key) is not True:
            raise OperatorHandoffContractError(f"coverage.{key} must be true")
    claim = report.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise OperatorHandoffContractError("contract missing claim boundary")
    require_not_claimed(claim, "contract", {
        "customer send approval",
        "automatic customer delivery",
        "automatic PR commenting",
        "production mutation",
        "truth certification",
        "customer outcome guarantee",
    })
    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise OperatorHandoffContractError("contract privacy must be metadata-only")
    assert_absent_or_false(privacy, SIDE_EFFECT_KEYS, "privacy")
    assert_absent_or_false(privacy, RAW_PAYLOAD_KEYS, "privacy")


def negative_case(case_id: str, report: Mapping[str, Any], mutator: Any) -> dict[str, str]:
    payload = copy.deepcopy(report)
    mutator(payload)
    try:
        validate_report(payload)
    except OperatorHandoffContractError as exc:
        return {"case_id": case_id, "status": "rejected", "error": str(exc)}
    raise OperatorHandoffContractError(f"Negative contract fixture unexpectedly passed: {case_id}")


def negative_fixtures(classes: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "shared_contract": {
            "class_specific_verifiers_remain_authoritative": True,
        },
        "delivery_classes": copy.deepcopy(classes),
        "coverage": {
            "all_classes_have_one_ready_case": True,
            "all_classes_have_blocked_cases": True,
            "operator_handoff_is_not_customer_send": True,
            "operator_handoff_is_not_ai_review_only": True,
        },
        "claim_boundary": {
            "not_claimed": [
                "customer send approval",
                "automatic customer delivery",
                "automatic PR commenting",
                "production mutation",
                "truth certification",
                "customer outcome guarantee",
            ],
        },
        "privacy": {
            "metadata_only": True,
            **{key: False for key in SIDE_EFFECT_KEYS},
            **{key: False for key in RAW_PAYLOAD_KEYS},
        },
    }

    def remove_class(payload: dict[str, Any]) -> None:
        payload["delivery_classes"] = payload["delivery_classes"][:1]

    def duplicate_ready(payload: dict[str, Any]) -> None:
        payload["delivery_classes"][0]["ready_count"] = 2

    def remove_operator_confirmation(payload: dict[str, Any]) -> None:
        payload["delivery_classes"][1]["required_confirmations"].remove("operator_understands_not_send_approval")

    def allow_customer_send(payload: dict[str, Any]) -> None:
        payload["privacy"]["automatic_customer_sending_performed"] = True

    def leak_raw_report(payload: dict[str, Any]) -> None:
        payload["privacy"]["raw_report_text_included"] = True

    def overclaim_truth(payload: dict[str, Any]) -> None:
        payload["claim_boundary"]["not_claimed"].remove("truth certification")

    return [
        negative_case("missing_delivery_class", base, remove_class),
        negative_case("multiple_ready_cases", base, duplicate_ready),
        negative_case("missing_operator_understanding_confirmation", base, remove_operator_confirmation),
        negative_case("automatic_customer_sending_performed", base, allow_customer_send),
        negative_case("raw_report_text_included", base, leak_raw_report),
        negative_case("truth_certification_overclaim", base, overclaim_truth),
    ]


def markdown_report(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        f"- `{item['delivery_class']}`: ready `{item['ready_count']}`, blocked `{item['blocked_count']}`"
        for item in report["delivery_classes"]
    )
    return f"""# Operator Handoff Rehearsal Contract

- Schema: `{report["schema_version"]}`
- Status: `{report["status"]}`
- Mode: `{report["shared_contract"]["mode"]}`
- Delivery classes: `{report["coverage"]["delivery_class_count"]}`

## Delivery Classes

{rows}

## Shared Boundary

{report["claim_boundary"]["current_claim"]}

This contract does not approve customer sending, post PR comments, publish
externally, mutate production, certify truth, certify security/legal/financial
claims, guarantee outcomes, or replace customer-specific review.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-review-source", type=Path, default=CODE_REVIEW_REPORT)
    parser.add_argument("--client-report-source", type=Path, default=CLIENT_REPORT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.code_review_source, args.client_report_source)
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
            raise OperatorHandoffContractError(
                "Operator handoff rehearsal contract report is stale. Run: "
                "python3 scripts/verify_operator_handoff_rehearsal_contract.py --write"
            )
        if not MARKDOWN_REPORT.exists() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise OperatorHandoffContractError(
                "Operator handoff rehearsal contract markdown is stale. Run: "
                "python3 scripts/verify_operator_handoff_rehearsal_contract.py --write"
            )
        print("ok    operator handoff rehearsal contract is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_operator_handoff_rehearsal_contract failed: {exc}", file=sys.stderr)
        sys.exit(1)
