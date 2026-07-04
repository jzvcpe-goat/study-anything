#!/usr/bin/env python3
"""Verify the controlled handoff runbook derived from Trust Evidence decisions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPORT = ROOT / "platform" / "generated" / "study-anything-trust-evidence-acceptance-drill.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-controlled-handoff-runbook.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-controlled-handoff-runbook.md"
SCHEMA_VERSION = "controlled-handoff-runbook-v1"

REQUIRED_NOT_CLAIMED = {
    "production approval",
    "automatic customer sending",
    "truth certification",
    "customer outcome guarantee",
}
REQUIRED_MATRIX_FLAGS = {
    "no_single_loop_dominates",
    "ai_review_only_rejected",
    "risk_over_budget_rejected",
    "missing_reconstruction_rejected",
    "scope_expansion_rejected",
}
FORBIDDEN_TEXT = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY" + "=",
    "github_pat_",
    "ghp_",
    "sk-proj-",
    "raw source text:",
    "raw diff:",
    "raw report text:",
    "raw customer payload:",
    "bearer ",
)


class ControlledHandoffRunbookError(RuntimeError):
    """Readable controlled-handoff runbook verifier failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reject_forbidden_text(payload: Any, label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = text.lower()
    hits = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if hits:
        raise ControlledHandoffRunbookError(f"{label} contains forbidden private text: {hits}")


def assert_false(mapping: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise ControlledHandoffRunbookError(f"{label}.{key} must be false")


def validate_source(source: Mapping[str, Any]) -> None:
    if source.get("schema_version") != "trust-evidence-acceptance-drill-v1":
        raise ControlledHandoffRunbookError("source must be trust-evidence-acceptance-drill-v1")
    if source.get("status") != "pass":
        raise ControlledHandoffRunbookError("source acceptance drill must pass")
    matrix = source.get("operator_decision_matrix")
    if not isinstance(matrix, Mapping):
        raise ControlledHandoffRunbookError("source missing operator_decision_matrix")
    for flag in REQUIRED_MATRIX_FLAGS:
        if matrix.get(flag) is not True:
            raise ControlledHandoffRunbookError(f"source matrix flag must be true: {flag}")
    if int(matrix.get("allowed_controlled_handoffs", 0)) < 1:
        raise ControlledHandoffRunbookError("source must contain allowed controlled handoffs")
    if int(matrix.get("blocked_handoffs", 0)) < 1:
        raise ControlledHandoffRunbookError("source must contain blocked handoffs")

    claim = source.get("claim_boundary")
    if not isinstance(claim, Mapping):
        raise ControlledHandoffRunbookError("source missing claim_boundary")
    not_claimed = {str(item) for item in claim.get("not_claimed", [])}
    missing = sorted(REQUIRED_NOT_CLAIMED - not_claimed)
    if missing:
        raise ControlledHandoffRunbookError(f"source claim boundary missing not_claimed items: {missing}")

    privacy = source.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise ControlledHandoffRunbookError("source privacy must be metadata-only")
    assert_false(
        privacy,
        (
            "model_calls_performed",
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
        ),
        "source.privacy",
    )
    reject_forbidden_text(source, "source acceptance drill")


def build_allowed_step(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    delivery_class = str(row.get("delivery_class"))
    if row.get("case_id") != "pass" or not str(row.get("operator_decision", "")).startswith("prepare_controlled_"):
        raise ControlledHandoffRunbookError("allowed runbook step must come from a pass prepare_controlled decision")
    if row.get("claim_boundary_preserved") is not True:
        raise ControlledHandoffRunbookError(f"{delivery_class} allowed step lost claim boundary")
    return {
        "step_id": f"prepare-{delivery_class}",
        "order": index,
        "delivery_class": delivery_class,
        "source_case_id": "pass",
        "source_decision": row.get("source_decision"),
        "operator_action": "prepare_controlled_handoff_packet",
        "allowed_next_action": "draft_handoff_only",
        "requires": [
            "verify_trust_evidence_zip_digest",
            "confirm_delivery_class_scope",
            "confirm_active_human_reconstruction",
            "confirm_claim_boundary_with_recipient",
            "attach_metadata_receipts_only",
        ],
        "forbidden": [
            "send_customer_message_automatically",
            "mutate_production",
            "publish_externally",
            "claim_truth_certification",
            "claim_customer_outcome_guarantee",
            "include_raw_source_or_customer_payload",
        ],
        "customer_visible_effect_allowed": False,
        "production_mutation_allowed": False,
        "external_publication_allowed": False,
        "raw_payload_allowed": False,
        "final_human_scope_confirmation_required": True,
    }


def build_blocked_step(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    delivery_class = str(row.get("delivery_class"))
    reasons = row.get("required_reasons_present")
    if row.get("operator_decision") != "block_handoff" or not isinstance(reasons, list) or not reasons:
        raise ControlledHandoffRunbookError("blocked runbook step must include required blocked reasons")
    if row.get("claim_boundary_preserved") is not True:
        raise ControlledHandoffRunbookError(f"{delivery_class} blocked step lost claim boundary")
    return {
        "step_id": f"block-{delivery_class}-{row.get('case_id')}",
        "order": index,
        "delivery_class": delivery_class,
        "source_case_id": row.get("case_id"),
        "source_decision": row.get("source_decision"),
        "operator_action": "keep_handoff_blocked",
        "blocked_reasons": list(reasons),
        "unblock_requires": [
            "rerun_failed_protocol_layer",
            "restore_active_human_reconstruction_if_missing",
            "lower_or_re-scope_risk_budget_if_needed",
            "regenerate_metadata_receipts_before_any_handoff",
        ],
        "customer_visible_effect_allowed": False,
        "production_mutation_allowed": False,
        "external_publication_allowed": False,
        "raw_payload_allowed": False,
    }


def build_runbook(source_path: Path) -> dict[str, Any]:
    source = load_json(source_path)
    validate_source(source)
    decisions = source.get("operator_decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ControlledHandoffRunbookError("source missing operator_decisions")

    allowed_steps: list[dict[str, Any]] = []
    blocked_steps: list[dict[str, Any]] = []
    for index, row in enumerate(decisions, start=1):
        if not isinstance(row, Mapping):
            raise ControlledHandoffRunbookError("operator decision must be an object")
        if str(row.get("operator_decision", "")).startswith("prepare_controlled_"):
            allowed_steps.append(build_allowed_step(row, index))
        elif row.get("operator_decision") == "block_handoff":
            blocked_steps.append(build_blocked_step(row, index))
        else:
            raise ControlledHandoffRunbookError(f"unknown operator decision: {row.get('operator_decision')}")

    if not allowed_steps or not blocked_steps:
        raise ControlledHandoffRunbookError("runbook must contain both allowed and blocked paths")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Turn Trust Evidence ZIP acceptance decisions into a controlled handoff runbook "
            "that an external operator or platform Agent can follow without customer sending or production mutation."
        ),
        "source": {
            "report": str(source_path.relative_to(ROOT)),
            "schema_version": source["schema_version"],
            "status": source["status"],
            "zip_sha256": source["pack"]["zip_sha256"],
            "allowed_controlled_handoffs": source["operator_decision_matrix"]["allowed_controlled_handoffs"],
            "blocked_handoffs": source["operator_decision_matrix"]["blocked_handoffs"],
        },
        "runbook": {
            "mode": "controlled_handoff_preparation_only",
            "allowed_steps": allowed_steps,
            "blocked_steps": blocked_steps,
            "operator_exit_criteria": [
                "all_allowed_steps_still_within_delivery_class_scope",
                "all_blocked_cases_remain_blocked_until_reverified",
                "recipient_scope_is_bounded_before_any_handoff",
                "claim_boundary_is_attached_to_the_packet",
                "raw_payloads_and_credentials_are_absent",
            ],
        },
        "platform_agent_boundary": {
            "codex": "may prepare metadata-only handoff packet and commands; must not send to customer",
            "kimi": "may inspect packaged evidence and draft handoff explanation; must not publish externally",
            "workbuddy": "may call local tools and assemble packet; must not mutate production or bypass human scope confirmation",
            "hermes": "may import the same metadata contract; must keep credentials inside the host Agent",
        },
        "claim_boundary": {
            "current_claim": (
                "A platform Agent or external operator can prepare a controlled handoff packet "
                "from accepted metadata evidence while preserving all blocked paths and claim limits."
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
            "minimum_command": "python3 scripts/verify_controlled_handoff_runbook.py --check",
            "source_command": "python3 scripts/verify_trust_evidence_acceptance_drill.py --check",
            "report": str(REPORT.relative_to(ROOT)),
            "markdown_report": str(MARKDOWN_REPORT.relative_to(ROOT)),
        },
    }
    reject_forbidden_text(report, SCHEMA_VERSION)
    return report


def markdown_report(report: Mapping[str, Any]) -> str:
    allowed = "\n".join(
        f"- `{step['delivery_class']}`: `{step['operator_action']}` -> `{step['allowed_next_action']}`"
        for step in report["runbook"]["allowed_steps"]
    )
    blocked = "\n".join(
        f"- `{step['delivery_class']}` / `{step['source_case_id']}`: `{step['operator_action']}` "
        f"because `{', '.join(step['blocked_reasons'])}`"
        for step in report["runbook"]["blocked_steps"]
    )
    return f"""# Controlled Handoff Runbook

- Schema: `{report["schema_version"]}`
- Status: `{report["status"]}`
- Mode: `{report["runbook"]["mode"]}`
- Source ZIP SHA-256: `{report["source"]["zip_sha256"]}`

## Allowed Preparation Steps

{allowed}

## Blocked Paths

{blocked}

## Claim Boundary

{report["claim_boundary"]["current_claim"]}

This runbook does not approve production, send customer messages, certify truth,
guarantee customer outcomes, or replace customer-specific legal/compliance review.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_runbook(args.source)
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
            raise ControlledHandoffRunbookError(
                "Controlled handoff runbook report is stale. Run: "
                "python3 scripts/verify_controlled_handoff_runbook.py --write"
            )
        if not MARKDOWN_REPORT.exists() or MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise ControlledHandoffRunbookError(
                "Controlled handoff runbook markdown is stale. Run: "
                "python3 scripts/verify_controlled_handoff_runbook.py --write"
            )
        print("ok    Controlled handoff runbook is up to date")
        return
    print(text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_controlled_handoff_runbook failed: {exc}", file=sys.stderr)
        sys.exit(1)
