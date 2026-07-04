#!/usr/bin/env python3
"""Verify a metadata-only customer-delivery rehearsal from the trust envelope."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPORT = ROOT / "platform" / "generated" / "study-anything-customer-delivery-trust-envelope.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-customer-delivery-rehearsal.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-customer-delivery-rehearsal.md"
SCHEMA_VERSION = "customer-delivery-rehearsal-v1"

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
    "raw_diff_included",
    "raw_report_text_included",
    "raw_customer_payload_included",
    "screenshots_included",
    "attention_streams_included",
    "real_secrets_included",
    "user_owned_agent_credentials_included",
)
REQUIRED_NOT_CLAIMED = {
    "customer send approval",
    "production approval",
    "automatic customer sending",
    "truth certification",
    "customer outcome guarantee",
}
READY_CONFIRMATIONS = (
    "recipient_scope_confirmed",
    "customer_context_within_delivery_class",
    "claim_boundary_visible",
    "no_raw_payload_or_secret_attached",
    "human_actual_send_outside_system_only",
)


class CustomerDeliveryRehearsalError(RuntimeError):
    """Readable customer-delivery rehearsal verifier failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reject_forbidden_text(payload: Any, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = text.lower()
    hits = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if hits:
        raise CustomerDeliveryRehearsalError(f"{label} contains forbidden private text: {hits}")


def assert_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise CustomerDeliveryRehearsalError(f"{label}.{key} must be false")


def validate_source(source: Mapping[str, Any]) -> None:
    if source.get("schema_version") != "customer-delivery-trust-envelope-v1":
        raise CustomerDeliveryRehearsalError("source must be customer-delivery-trust-envelope-v1")
    if source.get("status") != "pass":
        raise CustomerDeliveryRehearsalError("source customer-delivery envelope must pass")

    envelope = source.get("envelope")
    if not isinstance(envelope, Mapping):
        raise CustomerDeliveryRehearsalError("source missing envelope")
    items = envelope.get("items")
    blocked_items = envelope.get("blocked_items")
    if not isinstance(items, list) or not items:
        raise CustomerDeliveryRehearsalError("source must include draftable envelope items")
    if not isinstance(blocked_items, list) or not blocked_items:
        raise CustomerDeliveryRehearsalError("source must include blocked envelope items")
    for item in items:
        if not isinstance(item, Mapping):
            raise CustomerDeliveryRehearsalError("source envelope item must be an object")
        assert_false(
            item,
            (
                "automatic_customer_send_allowed",
                "customer_visible_effect_allowed",
                "production_mutation_allowed",
                "external_publication_allowed",
                "raw_payload_allowed",
            ),
            "source.envelope.item",
        )
        if item.get("human_scope_confirmation_required") is not True:
            raise CustomerDeliveryRehearsalError("source envelope item must require human scope confirmation")
    for item in blocked_items:
        if not isinstance(item, Mapping):
            raise CustomerDeliveryRehearsalError("source blocked item must be an object")
        assert_false(
            item,
            (
                "automatic_customer_send_allowed",
                "customer_visible_effect_allowed",
                "production_mutation_allowed",
                "external_publication_allowed",
                "raw_payload_allowed",
            ),
            "source.envelope.blocked_item",
        )

    gate = source.get("delivery_gate")
    if not isinstance(gate, Mapping):
        raise CustomerDeliveryRehearsalError("source missing delivery_gate")
    assert_false(
        gate,
        (
            "automatic_customer_send_allowed",
            "production_mutation_allowed",
            "external_publication_allowed",
            "truth_certification_allowed",
        ),
        "source.delivery_gate",
    )
    if gate.get("human_scope_confirmation_required") is not True:
        raise CustomerDeliveryRehearsalError("source delivery gate must require human scope confirmation")

    claim = source.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise CustomerDeliveryRehearsalError("source missing claim_boundary")
    missing = sorted(REQUIRED_NOT_CLAIMED - {str(item) for item in claim.get("not_claimed", [])})
    if missing:
        raise CustomerDeliveryRehearsalError(f"source claim boundary missing not_claimed items: {missing}")

    privacy = source.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise CustomerDeliveryRehearsalError("source privacy must be metadata-only")
    assert_false(privacy, FALSE_PRIVACY_KEYS, "source.privacy")
    reject_forbidden_text(source, "source customer-delivery envelope")


def rehearsal_case(
    *,
    case_id: str,
    delivery_class: str,
    source_ref: str,
    requested_action: str,
    confirmations: Mapping[str, bool],
    source_blocked: bool = False,
    raw_payload_present: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if source_blocked:
        reasons.append("source_envelope_item_blocked")
    if requested_action == "automatic_customer_send":
        reasons.append("automatic_customer_send_attempted")
    if raw_payload_present:
        reasons.append("raw_payload_or_secret_attached")
    for key in READY_CONFIRMATIONS:
        if confirmations.get(key) is not True:
            reasons.append(f"missing_{key}")

    ready = not reasons
    return {
        "case_id": case_id,
        "delivery_class": delivery_class,
        "source_ref": source_ref,
        "requested_action": requested_action,
        "status": "ready" if ready else "blocked",
        "decision": "ready_for_manual_send_review" if ready else "block_customer_delivery",
        "operator_confirmation_inputs": dict(confirmations),
        "reason_count": len(reasons),
        "reasons": reasons,
        "automatic_customer_send_performed": False,
        "customer_visible_effect_performed": False,
        "production_mutation_performed": False,
        "external_publication_performed": False,
        "truth_certification_performed": False,
        "raw_payload_included": False,
        "requires_human_actual_send_outside_system": True,
    }


def build_rehearsal(source_path: Path) -> dict[str, Any]:
    source = load_json(source_path)
    validate_source(source)
    envelope = source["envelope"]
    first_item = envelope["items"][0]
    first_blocked = envelope["blocked_items"][0]
    confirmations = {key: True for key in READY_CONFIRMATIONS}

    cases = [
        rehearsal_case(
            case_id="ready-manual-scope-confirmed",
            delivery_class=str(first_item["delivery_class"]),
            source_ref=str(first_item["envelope_item_id"]),
            requested_action="prepare_manual_send_review",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-missing-human-scope",
            delivery_class=str(first_item["delivery_class"]),
            source_ref=str(first_item["envelope_item_id"]),
            requested_action="prepare_manual_send_review",
            confirmations={**confirmations, "recipient_scope_confirmed": False},
        ),
        rehearsal_case(
            case_id="block-hidden-claim-boundary",
            delivery_class=str(first_item["delivery_class"]),
            source_ref=str(first_item["envelope_item_id"]),
            requested_action="prepare_manual_send_review",
            confirmations={**confirmations, "claim_boundary_visible": False},
        ),
        rehearsal_case(
            case_id="block-raw-payload-attached",
            delivery_class=str(first_item["delivery_class"]),
            source_ref=str(first_item["envelope_item_id"]),
            requested_action="prepare_manual_send_review",
            confirmations={**confirmations, "no_raw_payload_or_secret_attached": False},
            raw_payload_present=True,
        ),
        rehearsal_case(
            case_id="block-automatic-customer-send",
            delivery_class=str(first_item["delivery_class"]),
            source_ref=str(first_item["envelope_item_id"]),
            requested_action="automatic_customer_send",
            confirmations=confirmations,
        ),
        rehearsal_case(
            case_id="block-source-blocked-item",
            delivery_class=str(first_blocked["delivery_class"]),
            source_ref=str(first_blocked["blocked_item_id"]),
            requested_action="prepare_manual_send_review",
            confirmations=confirmations,
            source_blocked=True,
        ),
    ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Rehearse a pre-customer-send operator decision from the Customer Delivery Trust Envelope "
            "without sending, mutating production, reading raw payloads, or certifying truth."
        ),
        "source": {
            "report": str(source_path.relative_to(ROOT)),
            "schema_version": source["schema_version"],
            "status": source["status"],
            "envelope_item_count": len(envelope["items"]),
            "blocked_item_count": len(envelope["blocked_items"]),
        },
        "rehearsal": {
            "mode": "operator_pre_send_rehearsal_only",
            "ready_count": sum(1 for case in cases if case["status"] == "ready"),
            "blocked_count": sum(1 for case in cases if case["status"] == "blocked"),
            "cases": cases,
            "operator_exit_criteria": [
                "exactly_one_ready_case_requires_all_human_scope_confirmations",
                "every_blocked_case_has_reasons",
                "automatic_customer_send_attempts_are_blocked",
                "blocked_envelope_items_remain_blocked",
                "raw_payloads_and_credentials_are_absent",
                "actual_customer_send_happens_outside_this_system_only",
            ],
        },
        "claim_boundary": {
            "current_claim": (
                "An external operator or platform Agent can rehearse ready/block decisions from a "
                "metadata-only customer-delivery envelope before any customer-visible action."
            ),
            "not_claimed": [
                "customer send approval",
                "actual customer send completed",
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
        "negative_fixtures": negative_fixtures(source),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_customer_delivery_rehearsal.py --check",
            "source_command": "python3 scripts/verify_customer_delivery_trust_envelope.py --check",
            "report": str(REPORT.relative_to(ROOT)),
            "markdown_report": str(MARKDOWN_REPORT.relative_to(ROOT)),
        },
    }
    validate_rehearsal(report)
    reject_forbidden_text(report, SCHEMA_VERSION)
    return report


def validate_rehearsal(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("status") != "pass":
        raise CustomerDeliveryRehearsalError("rehearsal report schema/status drifted")
    rehearsal = report.get("rehearsal")
    if not isinstance(rehearsal, Mapping):
        raise CustomerDeliveryRehearsalError("report missing rehearsal")
    cases = rehearsal.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CustomerDeliveryRehearsalError("rehearsal must include cases")
    if rehearsal.get("ready_count") != 1:
        raise CustomerDeliveryRehearsalError("rehearsal must include exactly one ready case")
    if int(rehearsal.get("blocked_count", 0)) < 5:
        raise CustomerDeliveryRehearsalError("rehearsal must include at least five blocked cases")
    for case in cases:
        if not isinstance(case, Mapping):
            raise CustomerDeliveryRehearsalError("rehearsal case must be an object")
        assert_false(
            case,
            (
                "automatic_customer_send_performed",
                "customer_visible_effect_performed",
                "production_mutation_performed",
                "external_publication_performed",
                "truth_certification_performed",
                "raw_payload_included",
            ),
            f"case.{case.get('case_id')}",
        )
        if case.get("requires_human_actual_send_outside_system") is not True:
            raise CustomerDeliveryRehearsalError(f"case {case.get('case_id')} must require outside-system human send")
        if case.get("status") == "ready":
            confirmations = case.get("operator_confirmation_inputs")
            if not isinstance(confirmations, Mapping) or any(confirmations.get(key) is not True for key in READY_CONFIRMATIONS):
                raise CustomerDeliveryRehearsalError("ready case must include all active confirmations")
            if case.get("decision") != "ready_for_manual_send_review":
                raise CustomerDeliveryRehearsalError("ready case decision drifted")
        elif case.get("status") == "blocked":
            if case.get("decision") != "block_customer_delivery":
                raise CustomerDeliveryRehearsalError("blocked case decision drifted")
            if int(case.get("reason_count", 0)) < 1:
                raise CustomerDeliveryRehearsalError("blocked case must include at least one reason")
        else:
            raise CustomerDeliveryRehearsalError(f"unknown case status: {case.get('status')}")

    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise CustomerDeliveryRehearsalError("rehearsal privacy must be metadata-only")
    assert_false(privacy, FALSE_PRIVACY_KEYS, "privacy")


def negative_case(case_id: str, report: Mapping[str, Any], mutator: Any) -> dict[str, str]:
    payload = copy.deepcopy(report)
    mutator(payload)
    try:
        validate_rehearsal(payload)
    except CustomerDeliveryRehearsalError as exc:
        return {"case_id": case_id, "status": "rejected", "error": str(exc)}
    raise CustomerDeliveryRehearsalError(f"Negative rehearsal fixture unexpectedly passed: {case_id}")


def negative_fixtures(source: Mapping[str, Any]) -> list[dict[str, str]]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "rehearsal": {
            "ready_count": 1,
            "blocked_count": 5,
            "cases": [
                {
                    "case_id": "ready",
                    "status": "ready",
                    "decision": "ready_for_manual_send_review",
                    "operator_confirmation_inputs": {key: True for key in READY_CONFIRMATIONS},
                    "reason_count": 0,
                    "automatic_customer_send_performed": False,
                    "customer_visible_effect_performed": False,
                    "production_mutation_performed": False,
                    "external_publication_performed": False,
                    "truth_certification_performed": False,
                    "raw_payload_included": False,
                    "requires_human_actual_send_outside_system": True,
                },
                *[
                    {
                        "case_id": f"blocked-{index}",
                        "status": "blocked",
                        "decision": "block_customer_delivery",
                        "operator_confirmation_inputs": {key: True for key in READY_CONFIRMATIONS},
                        "reason_count": 1,
                        "reasons": ["fixture_block"],
                        "automatic_customer_send_performed": False,
                        "customer_visible_effect_performed": False,
                        "production_mutation_performed": False,
                        "external_publication_performed": False,
                        "truth_certification_performed": False,
                        "raw_payload_included": False,
                        "requires_human_actual_send_outside_system": True,
                    }
                    for index in range(5)
                ],
            ],
        },
        "privacy": {
            "metadata_only": True,
            **{key: False for key in FALSE_PRIVACY_KEYS},
        },
    }
    validate_source(source)

    def allow_automatic_send(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][0]["automatic_customer_send_performed"] = True

    def remove_ready_case(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["ready_count"] = 0
        payload["rehearsal"]["cases"][0]["status"] = "blocked"

    def strip_confirmation(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][0]["operator_confirmation_inputs"]["claim_boundary_visible"] = False

    def unblock_without_reason(payload: dict[str, Any]) -> None:
        payload["rehearsal"]["cases"][1]["reason_count"] = 0
        payload["rehearsal"]["cases"][1]["reasons"] = []

    def leak_payload(payload: dict[str, Any]) -> None:
        payload["privacy"]["raw_customer_payload_included"] = True

    return [
        negative_case("automatic_customer_send_performed", base, allow_automatic_send),
        negative_case("missing_ready_case", base, remove_ready_case),
        negative_case("missing_claim_boundary_confirmation", base, strip_confirmation),
        negative_case("blocked_case_without_reason", base, unblock_without_reason),
        negative_case("raw_customer_payload_included", base, leak_payload),
    ]


def markdown_report(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        f"- `{case['case_id']}`: `{case['decision']}` ({case['status']})"
        for case in report["rehearsal"]["cases"]
    )
    return f"""# Customer Delivery Rehearsal

- Schema: `{report["schema_version"]}`
- Status: `{report["status"]}`
- Mode: `{report["rehearsal"]["mode"]}`
- Ready cases: `{report["rehearsal"]["ready_count"]}`
- Blocked cases: `{report["rehearsal"]["blocked_count"]}`

## Rehearsal Matrix

{rows}

## Claim Boundary

{report["claim_boundary"]["current_claim"]}

This rehearsal does not approve customer sending, complete a customer send,
mutate production, certify truth, guarantee outcomes, or replace
customer-specific legal/compliance review.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_rehearsal(args.source)
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
            raise CustomerDeliveryRehearsalError(
                "Customer delivery rehearsal report is stale. Run: "
                "python3 scripts/verify_customer_delivery_rehearsal.py --write"
            )
        if not MARKDOWN_REPORT.exists() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise CustomerDeliveryRehearsalError(
                "Customer delivery rehearsal markdown is stale. Run: "
                "python3 scripts/verify_customer_delivery_rehearsal.py --write"
            )
        print("ok    Customer delivery rehearsal is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_customer_delivery_rehearsal failed: {exc}", file=sys.stderr)
        sys.exit(1)
