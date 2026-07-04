#!/usr/bin/env python3
"""Verify the customer-delivery trust envelope derived from controlled handoff evidence."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPORT = ROOT / "platform" / "generated" / "study-anything-controlled-handoff-runbook.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-customer-delivery-trust-envelope.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-customer-delivery-trust-envelope.md"
SCHEMA_VERSION = "customer-delivery-trust-envelope-v1"

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
SOURCE_FALSE_PRIVACY_KEYS = (
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
    "production approval",
    "automatic customer sending",
    "truth certification",
    "customer outcome guarantee",
}


class CustomerDeliveryTrustEnvelopeError(RuntimeError):
    """Readable customer-delivery trust envelope verifier failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reject_forbidden_text(payload: Any, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = text.lower()
    hits = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if hits:
        raise CustomerDeliveryTrustEnvelopeError(f"{label} contains forbidden private text: {hits}")


def assert_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise CustomerDeliveryTrustEnvelopeError(f"{label}.{key} must be false")


def validate_source(source: Mapping[str, Any]) -> None:
    if source.get("schema_version") != "controlled-handoff-runbook-v1":
        raise CustomerDeliveryTrustEnvelopeError("source must be controlled-handoff-runbook-v1")
    if source.get("status") != "pass":
        raise CustomerDeliveryTrustEnvelopeError("source controlled handoff runbook must pass")

    runbook = source.get("runbook")
    if not isinstance(runbook, Mapping):
        raise CustomerDeliveryTrustEnvelopeError("source missing runbook")
    allowed_steps = runbook.get("allowed_steps")
    blocked_steps = runbook.get("blocked_steps")
    if not isinstance(allowed_steps, list) or not allowed_steps:
        raise CustomerDeliveryTrustEnvelopeError("source must contain allowed preparation steps")
    if not isinstance(blocked_steps, list) or not blocked_steps:
        raise CustomerDeliveryTrustEnvelopeError("source must contain blocked paths")

    for step in allowed_steps:
        if not isinstance(step, Mapping):
            raise CustomerDeliveryTrustEnvelopeError("allowed source step must be an object")
        if step.get("operator_action") != "prepare_controlled_handoff_packet":
            raise CustomerDeliveryTrustEnvelopeError("allowed source step must only prepare a controlled packet")
        if step.get("allowed_next_action") != "draft_handoff_only":
            raise CustomerDeliveryTrustEnvelopeError("allowed source step must remain draft-only")
        if step.get("customer_visible_effect_allowed") is not False:
            raise CustomerDeliveryTrustEnvelopeError("allowed source step must not allow customer-visible effects")
        if step.get("production_mutation_allowed") is not False:
            raise CustomerDeliveryTrustEnvelopeError("allowed source step must not allow production mutation")
        if step.get("raw_payload_allowed") is not False:
            raise CustomerDeliveryTrustEnvelopeError("allowed source step must not allow raw payloads")
        if step.get("final_human_scope_confirmation_required") is not True:
            raise CustomerDeliveryTrustEnvelopeError("allowed source step must require final human scope confirmation")

    for step in blocked_steps:
        if not isinstance(step, Mapping):
            raise CustomerDeliveryTrustEnvelopeError("blocked source step must be an object")
        if step.get("operator_action") != "keep_handoff_blocked":
            raise CustomerDeliveryTrustEnvelopeError("blocked source step must remain blocked")
        if step.get("customer_visible_effect_allowed") is not False:
            raise CustomerDeliveryTrustEnvelopeError("blocked source step must not allow customer-visible effects")
        if step.get("raw_payload_allowed") is not False:
            raise CustomerDeliveryTrustEnvelopeError("blocked source step must not allow raw payloads")

    claim = source.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise CustomerDeliveryTrustEnvelopeError("source missing claim_boundary")
    not_claimed = {str(item) for item in claim.get("not_claimed", [])}
    missing = sorted(REQUIRED_NOT_CLAIMED - not_claimed)
    if missing:
        raise CustomerDeliveryTrustEnvelopeError(f"source claim boundary missing not_claimed items: {missing}")

    privacy = source.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise CustomerDeliveryTrustEnvelopeError("source privacy must be metadata-only")
    assert_false(privacy, SOURCE_FALSE_PRIVACY_KEYS, "source.privacy")
    reject_forbidden_text(source, "source controlled handoff runbook")


def build_envelope_item(step: Mapping[str, Any], order: int) -> dict[str, Any]:
    delivery_class = str(step.get("delivery_class"))
    return {
        "envelope_item_id": f"customer-envelope-{delivery_class}",
        "order": order,
        "delivery_class": delivery_class,
        "source_step_id": step.get("step_id"),
        "source_operator_action": step.get("operator_action"),
        "customer_packet_status": "draft_ready_for_human_scope_confirmation",
        "customer_visible_material": [
            "claim_boundary_summary",
            "delivery_class_id",
            "verification_commands",
            "metadata_receipt_refs",
            "blocked_path_summary",
        ],
        "withheld_material": [
            "raw_source_text",
            "raw_diff",
            "raw_report_body",
            "raw_customer_payload",
            "screenshots",
            "attention_streams",
            "secrets_or_credentials",
        ],
        "requires_before_any_customer_send": [
            "human_confirms_recipient_scope",
            "human_confirms_customer_context_is_within_delivery_class",
            "human_confirms_claim_boundary_is_visible",
            "human_confirms_no_raw_payload_or_secret_is_attached",
            "human_performs_the_actual_send_outside_this_system",
        ],
        "forbidden": [
            "automatic_customer_send",
            "production_mutation",
            "external_publication_without_human_scope_confirmation",
            "truth_certification_claim",
            "customer_outcome_guarantee_claim",
            "raw_payload_attachment",
        ],
        "automatic_customer_send_allowed": False,
        "customer_visible_effect_allowed": False,
        "production_mutation_allowed": False,
        "external_publication_allowed": False,
        "raw_payload_allowed": False,
        "human_scope_confirmation_required": True,
    }


def build_blocked_item(step: Mapping[str, Any], order: int) -> dict[str, Any]:
    reasons = step.get("blocked_reasons")
    if not isinstance(reasons, list) or not reasons:
        raise CustomerDeliveryTrustEnvelopeError("blocked source step missing reasons")
    delivery_class = str(step.get("delivery_class"))
    return {
        "blocked_item_id": f"customer-block-{delivery_class}-{step.get('source_case_id')}",
        "order": order,
        "delivery_class": delivery_class,
        "source_step_id": step.get("step_id"),
        "source_case_id": step.get("source_case_id"),
        "customer_packet_status": "not_allowed",
        "blocked_reasons": list(reasons),
        "unblock_requires": [
            "rerun_failed_protocol_layer",
            "regenerate_metadata_receipts",
            "rerun_acceptance_drill",
            "rerun_controlled_handoff_runbook",
            "rebuild_customer_delivery_trust_envelope",
        ],
        "automatic_customer_send_allowed": False,
        "customer_visible_effect_allowed": False,
        "production_mutation_allowed": False,
        "external_publication_allowed": False,
        "raw_payload_allowed": False,
    }


def build_envelope(source_path: Path) -> dict[str, Any]:
    source = load_json(source_path)
    validate_source(source)
    runbook = source["runbook"]
    envelope_items = [
        build_envelope_item(step, order)
        for order, step in enumerate(runbook["allowed_steps"], start=1)
    ]
    blocked_items = [
        build_blocked_item(step, order)
        for order, step in enumerate(runbook["blocked_steps"], start=1)
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Wrap controlled handoff preparation into a metadata-only customer-delivery trust envelope "
            "that can be inspected before any customer-visible action."
        ),
        "source": {
            "report": str(source_path.relative_to(ROOT)),
            "schema_version": source["schema_version"],
            "status": source["status"],
            "allowed_steps": len(runbook["allowed_steps"]),
            "blocked_steps": len(runbook["blocked_steps"]),
        },
        "envelope": {
            "mode": "pre_customer_send_boundary_only",
            "items": envelope_items,
            "blocked_items": blocked_items,
            "operator_exit_criteria": [
                "all_envelope_items_keep_customer_visible_effects_disabled",
                "blocked_items_are_not_converted_into_customer_packets",
                "claim_boundary_is_visible_to_the_human_operator",
                "human_scope_confirmation_is_recorded_outside_the_envelope_before_send",
                "raw_payloads_and_credentials_are_absent",
            ],
        },
        "delivery_gate": {
            "decision": "ready_for_manual_scope_confirmation",
            "promotion_target": "manual_customer_handoff_review",
            "automatic_customer_send_allowed": False,
            "production_mutation_allowed": False,
            "external_publication_allowed": False,
            "truth_certification_allowed": False,
            "human_scope_confirmation_required": True,
        },
        "platform_agent_boundary": {
            "codex": "may draft a metadata-only envelope and cite verifier commands; must not send to customer",
            "kimi": "may explain envelope boundaries from metadata; must not publish externally",
            "workbuddy": "may assemble local packet refs; must not mutate production or bypass human send",
            "hermes": "may import the envelope contract; must keep model credentials inside the host Agent",
        },
        "claim_boundary": {
            "current_claim": (
                "A platform Agent or external operator can prepare a customer-delivery trust envelope "
                "from controlled handoff evidence while keeping customer send, production mutation, and truth "
                "certification outside the system."
            ),
            "not_claimed": [
                "customer send approval",
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
            "minimum_command": "python3 scripts/verify_customer_delivery_trust_envelope.py --check",
            "source_command": "python3 scripts/verify_controlled_handoff_runbook.py --check",
            "report": str(REPORT.relative_to(ROOT)),
            "markdown_report": str(MARKDOWN_REPORT.relative_to(ROOT)),
        },
    }
    validate_envelope(report)
    reject_forbidden_text(report, SCHEMA_VERSION)
    return report


def validate_envelope(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("status") != "pass":
        raise CustomerDeliveryTrustEnvelopeError("envelope report schema/status drifted")
    gate = report.get("delivery_gate")
    if not isinstance(gate, Mapping):
        raise CustomerDeliveryTrustEnvelopeError("envelope missing delivery_gate")
    assert_false(
        gate,
        (
            "automatic_customer_send_allowed",
            "production_mutation_allowed",
            "external_publication_allowed",
            "truth_certification_allowed",
        ),
        "delivery_gate",
    )
    if gate.get("human_scope_confirmation_required") is not True:
        raise CustomerDeliveryTrustEnvelopeError("delivery gate must require human scope confirmation")

    envelope = report.get("envelope")
    if not isinstance(envelope, Mapping):
        raise CustomerDeliveryTrustEnvelopeError("report missing envelope")
    items = envelope.get("items")
    blocked_items = envelope.get("blocked_items")
    if not isinstance(items, list) or not items:
        raise CustomerDeliveryTrustEnvelopeError("envelope must include allowed items")
    if not isinstance(blocked_items, list) or not blocked_items:
        raise CustomerDeliveryTrustEnvelopeError("envelope must include blocked items")
    for item in items:
        if not isinstance(item, Mapping):
            raise CustomerDeliveryTrustEnvelopeError("envelope item must be an object")
        assert_false(
            item,
            (
                "automatic_customer_send_allowed",
                "customer_visible_effect_allowed",
                "production_mutation_allowed",
                "external_publication_allowed",
                "raw_payload_allowed",
            ),
            "envelope.item",
        )
        if item.get("human_scope_confirmation_required") is not True:
            raise CustomerDeliveryTrustEnvelopeError("envelope item must require human scope confirmation")
    for item in blocked_items:
        if not isinstance(item, Mapping):
            raise CustomerDeliveryTrustEnvelopeError("blocked envelope item must be an object")
        assert_false(
            item,
            (
                "automatic_customer_send_allowed",
                "customer_visible_effect_allowed",
                "production_mutation_allowed",
                "external_publication_allowed",
                "raw_payload_allowed",
            ),
            "envelope.blocked_item",
        )

    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise CustomerDeliveryTrustEnvelopeError("envelope privacy must be metadata-only")
    assert_false(privacy, SOURCE_FALSE_PRIVACY_KEYS, "privacy")


def negative_case(case_id: str, source: Mapping[str, Any], mutator: Any) -> dict[str, str]:
    payload = copy.deepcopy(source)
    mutator(payload)
    try:
        validate_source(payload)
    except CustomerDeliveryTrustEnvelopeError as exc:
        return {"case_id": case_id, "status": "rejected", "error": str(exc)}
    raise CustomerDeliveryTrustEnvelopeError(f"Negative envelope fixture unexpectedly passed: {case_id}")


def negative_fixtures(source: Mapping[str, Any]) -> list[dict[str, str]]:
    def allow_customer_effect(payload: dict[str, Any]) -> None:
        payload["runbook"]["allowed_steps"][0]["customer_visible_effect_allowed"] = True

    def remove_human_scope_confirmation(payload: dict[str, Any]) -> None:
        payload["runbook"]["allowed_steps"][0]["final_human_scope_confirmation_required"] = False

    def unblock_blocked_path(payload: dict[str, Any]) -> None:
        payload["runbook"]["blocked_steps"][0]["operator_action"] = "prepare_controlled_handoff_packet"

    def inject_raw_payload(payload: dict[str, Any]) -> None:
        payload["privacy"]["raw_customer_payload_included"] = True

    return [
        negative_case("customer_visible_effect_allowed", source, allow_customer_effect),
        negative_case("missing_human_scope_confirmation", source, remove_human_scope_confirmation),
        negative_case("blocked_path_unblocked", source, unblock_blocked_path),
        negative_case("raw_customer_payload_included", source, inject_raw_payload),
    ]


def markdown_report(report: Mapping[str, Any]) -> str:
    items = "\n".join(
        f"- `{item['delivery_class']}`: `{item['customer_packet_status']}`; "
        "customer send remains disabled"
        for item in report["envelope"]["items"]
    )
    blocked = "\n".join(
        f"- `{item['delivery_class']}` / `{item['source_case_id']}`: `{item['customer_packet_status']}`"
        for item in report["envelope"]["blocked_items"]
    )
    return f"""# Customer Delivery Trust Envelope

- Schema: `{report["schema_version"]}`
- Status: `{report["status"]}`
- Mode: `{report["envelope"]["mode"]}`
- Delivery gate: `{report["delivery_gate"]["decision"]}`

## Draftable Envelope Items

{items}

## Blocked Items

{blocked}

## Claim Boundary

{report["claim_boundary"]["current_claim"]}

This envelope does not approve customer sending, production mutation, truth
certification, customer outcome guarantees, or customer-specific legal/compliance
review.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_envelope(args.source)
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
            raise CustomerDeliveryTrustEnvelopeError(
                "Customer delivery trust envelope report is stale. Run: "
                "python3 scripts/verify_customer_delivery_trust_envelope.py --write"
            )
        if not MARKDOWN_REPORT.exists() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise CustomerDeliveryTrustEnvelopeError(
                "Customer delivery trust envelope markdown is stale. Run: "
                "python3 scripts/verify_customer_delivery_trust_envelope.py --write"
            )
        print("ok    Customer delivery trust envelope is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_customer_delivery_trust_envelope failed: {exc}", file=sys.stderr)
        sys.exit(1)
