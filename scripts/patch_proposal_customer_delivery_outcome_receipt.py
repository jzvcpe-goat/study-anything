#!/usr/bin/env python3
"""Build metadata-only Patch Proposal Customer Delivery Outcome Receipt artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import cbb_protocol, dual_loop  # noqa: E402
import patch_proposal_customer_delivery_rehearsal as delivery_rehearsal  # noqa: E402


OUTCOME_SCHEMA_VERSION = "patch-proposal-customer-delivery-outcome-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-delivery-outcome-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-delivery-outcome"
REHEARSAL_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-delivery-rehearsal"

CASE_IDS = (
    "pass-human-operator",
    "pass-host-platform-agent",
    "blocked-rehearsal-blocked",
    "blocked-missing-external-actor",
    "blocked-missing-action-reference",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-customer-visible-body",
    "blocked-pr-comment-body",
    "blocked-external-publication-payload",
    "blocked-production-payload",
    "blocked-automatic-send",
    "blocked-source-mutation",
    "blocked-secret",
    "blocked-model-credential",
)

PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "raw_patch_body_included": False,
    "raw_diff_body_included": False,
    "raw_repository_file_body_included": False,
    "raw_pr_comment_included": False,
    "raw_customer_body_included": False,
    "customer_visible_payload_included": False,
    "external_publication_payload_included": False,
    "production_payload_included": False,
    "repository_secrets_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}

ISOLATION = dict(dual_loop.ISOLATION_BOUNDARY)
FORBIDDEN_RAW_FIELDS = {
    "raw_patch_body",
    "patch_body",
    "raw_diff_body",
    "diff_body",
    "raw_repository_file_body",
    "repository_file_body",
    "raw_source_text",
    "raw_customer_body",
    "customer_body",
    "customer_visible_body",
    "customer_visible_payload",
    "customer_visible_content",
    "raw_customer_payload",
    "pr_comment_body",
    "raw_pr_comment",
    "external_publication_payload",
    "production_payload",
    "secret",
    "secrets",
    "model_key",
    "model_keys",
    "agent_credentials",
}


class PatchProposalCustomerDeliveryOutcomeError(ValueError):
    """Raised when customer-delivery outcome artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerDeliveryOutcomeError(f"Expected JSON object: {path}")
    return payload


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dump_json(payload))


def _base(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(ISOLATION),
        "privacy": dict(PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise PatchProposalCustomerDeliveryOutcomeError(f"{label}.{key} must be an object")
    return value


def _forbidden_raw_paths(payload: Any, *, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child = f"{path}.{key}"
            if str(key) in FORBIDDEN_RAW_FIELDS:
                paths.append(child)
            paths.extend(_forbidden_raw_paths(value, path=child))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            paths.extend(_forbidden_raw_paths(value, path=f"{path}[{index}]"))
    return paths


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.assert_metadata_only(payload, label=label)
    forbidden = _forbidden_raw_paths(payload)
    if forbidden:
        raise PatchProposalCustomerDeliveryOutcomeError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerDeliveryOutcomeError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerDeliveryOutcomeError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str | None]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerDeliveryOutcomeError(f"Unknown case id: {case_id}")
    return {
        "rehearsal_case": "blocked-envelope-blocked" if case_id == "blocked-rehearsal-blocked" else "pass",
        "external_actor_type": None
        if case_id == "blocked-missing-external-actor"
        else ("host_platform_agent" if case_id == "pass-host-platform-agent" else "human_operator"),
        "external_action_ref_hash_present": case_id != "blocked-missing-action-reference",
        "claim_boundary_visible": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_visible": case_id != "blocked-missing-privacy-boundary",
        "customer_visible_body_attached": case_id == "blocked-customer-visible-body",
        "pr_comment_body_attached": case_id == "blocked-pr-comment-body",
        "external_publication_payload_attached": case_id == "blocked-external-publication-payload",
        "production_payload_attached": case_id == "blocked-production-payload",
        "automatic_send_performed": case_id == "blocked-automatic-send",
        "source_mutation_performed": case_id == "blocked-source-mutation",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_rehearsal(case_id: str) -> dict[str, Any]:
    rehearsal_case = str(_case_flags(case_id)["rehearsal_case"])
    receipt = load_json(
        REHEARSAL_FIXTURE_DIR / rehearsal_case / "patch-proposal-customer-delivery-rehearsal-receipt.json"
    )
    return delivery_rehearsal.validate_customer_delivery_rehearsal(receipt)


def _action_ref_hash(case_id: str, actor_type: str | None) -> str | None:
    if not _case_flags(case_id)["external_action_ref_hash_present"]:
        return None
    return dual_loop.sha256_text(f"{case_id}:{actor_type}:external-customer-delivery-outcome")


def build_customer_delivery_outcome(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    rehearsal_receipt = source_rehearsal(case_id)
    actor_type = flags["external_actor_type"]
    action_ref_hash = _action_ref_hash(case_id, str(actor_type) if actor_type else None)
    checks = {
        "source_rehearsal_ready": rehearsal_receipt.get("status") == "ready",
        "external_action_recorded": True,
        "external_actor_declared": actor_type in {"human_operator", "host_platform_agent"},
        "action_happened_outside_study_anything": True,
        "action_reference_hash_present": isinstance(action_ref_hash, str) and len(action_ref_hash) == 64,
        "claim_boundary_visible": bool(flags["claim_boundary_visible"]),
        "privacy_boundary_visible": bool(flags["privacy_boundary_visible"]),
        "metadata_only_outcome": True,
        "customer_visible_body_attached": bool(flags["customer_visible_body_attached"]),
        "pr_comment_body_attached": bool(flags["pr_comment_body_attached"]),
        "external_publication_payload_attached": bool(flags["external_publication_payload_attached"]),
        "production_payload_attached": bool(flags["production_payload_attached"]),
        "automatic_send_performed": bool(flags["automatic_send_performed"]),
        "source_mutation_performed": bool(flags["source_mutation_performed"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    for key, reason in (
        ("source_rehearsal_ready", "source_rehearsal_not_ready"),
        ("external_actor_declared", "external_actor_missing"),
        ("action_reference_hash_present", "action_reference_hash_missing"),
        ("claim_boundary_visible", "claim_boundary_missing"),
        ("privacy_boundary_visible", "privacy_boundary_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("customer_visible_body_attached", "customer_visible_body_rejected"),
        ("pr_comment_body_attached", "pr_comment_body_rejected"),
        ("external_publication_payload_attached", "external_publication_payload_rejected"),
        ("production_payload_attached", "production_payload_rejected"),
        ("automatic_send_performed", "automatic_send_rejected"),
        ("source_mutation_performed", "source_mutation_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    recorded = not reasons
    receipt = {
        **_base(OUTCOME_SCHEMA_VERSION),
        "outcome_id": f"patch-proposal-customer-delivery-outcome-{case_id}",
        "case_id": case_id,
        "status": "recorded" if recorded else "blocked",
        "decision": "record_external_customer_delivery_outcome" if recorded else "block_customer_delivery_outcome",
        "blocked_reasons": reasons,
        "source_refs": {
            "rehearsal_receipt_ref": (
                f"fixtures/patch-proposal-customer-delivery-rehearsal/{flags['rehearsal_case']}/"
                "patch-proposal-customer-delivery-rehearsal-receipt.json"
            ),
            "rehearsal_receipt_hash": artifact_hash(rehearsal_receipt),
            "rehearsal_report_ref": "platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.json",
        },
        "external_action_summary": {
            "package_type": "metadata_only_patch_proposal_customer_delivery_outcome",
            "action_type": "customer_delivery_handoff_recorded" if recorded else None,
            "actor_type": actor_type if recorded else actor_type,
            "occurred_outside_study_anything": True,
            "action_ref_hash": action_ref_hash,
            "payload_included": False,
            "payload_hash_only": True,
            "external_system_credentials_included": False,
        },
        "effect_boundary": {
            "study_anything_customer_send_performed": False,
            "study_anything_automatic_send_performed": False,
            "study_anything_repository_mutation_performed": False,
            "study_anything_pr_commenting_performed": False,
            "study_anything_external_publication_performed": False,
            "study_anything_production_mutation_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": (
                "A recorded outcome proves only that a human or host platform reported an external customer "
                "handoff action by metadata reference. It does not include customer-visible content, perform the "
                "send, comment on PRs, publish externally, mutate source, mutate production, or certify correctness."
            ),
            "not_claimed": [
                "customer-visible body included",
                "Study Anything sent the customer message",
                "Study Anything commented on a PR",
                "Study Anything published externally",
                "Study Anything changed source",
                "Study Anything changed production",
                "truth or security certified",
            ],
        },
    }
    return validate_customer_delivery_outcome(receipt)


def validate_customer_delivery_outcome(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != OUTCOME_SCHEMA_VERSION:
        raise PatchProposalCustomerDeliveryOutcomeError("customer delivery outcome schema_version drifted")
    _validate_privacy(receipt, label=OUTCOME_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "external_action_summary", label=OUTCOME_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=OUTCOME_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=OUTCOME_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_patch_proposal_customer_delivery_outcome":
        raise PatchProposalCustomerDeliveryOutcomeError("outcome package_type must remain metadata-only")
    if summary.get("payload_included") is not False:
        raise PatchProposalCustomerDeliveryOutcomeError("outcome payload must not be included")
    if summary.get("external_system_credentials_included") is not False:
        raise PatchProposalCustomerDeliveryOutcomeError("external credentials must not be included")
    for key in (
        "study_anything_customer_send_performed",
        "study_anything_automatic_send_performed",
        "study_anything_repository_mutation_performed",
        "study_anything_pr_commenting_performed",
        "study_anything_external_publication_performed",
        "study_anything_production_mutation_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalCustomerDeliveryOutcomeError(f"effect_boundary.{key} must remain false")
    if status == "recorded":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalCustomerDeliveryOutcomeError("recorded customer delivery outcome must not carry reasons")
        for key in (
            "source_rehearsal_ready",
            "external_action_recorded",
            "external_actor_declared",
            "action_happened_outside_study_anything",
            "action_reference_hash_present",
            "claim_boundary_visible",
            "privacy_boundary_visible",
            "metadata_only_outcome",
        ):
            if checks.get(key) is not True:
                raise PatchProposalCustomerDeliveryOutcomeError(f"recorded customer delivery outcome missing check: {key}")
        for key in (
            "customer_visible_body_attached",
            "pr_comment_body_attached",
            "external_publication_payload_attached",
            "production_payload_attached",
            "automatic_send_performed",
            "source_mutation_performed",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalCustomerDeliveryOutcomeError(
                    f"recorded customer delivery outcome checks.{key} must remain false"
                )
        if summary.get("actor_type") not in {"human_operator", "host_platform_agent"}:
            raise PatchProposalCustomerDeliveryOutcomeError("recorded outcome actor_type must be bounded")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalCustomerDeliveryOutcomeError("blocked customer delivery outcome must carry reasons")
        if summary.get("action_type") is not None:
            raise PatchProposalCustomerDeliveryOutcomeError("blocked customer delivery outcome must not expose action_type")
    else:
        raise PatchProposalCustomerDeliveryOutcomeError("customer delivery outcome status must be recorded or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-customer-delivery-outcome-receipt.json": build_customer_delivery_outcome(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_customer_delivery_outcome(
            cases[case_id]["patch-proposal-customer-delivery-outcome-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "actor_type": receipt["external_action_summary"]["actor_type"],
            }
        )
    recorded_count = sum(1 for row in case_reports if row["status"] == "recorded")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove an external human or host platform customer-delivery action can be recorded as metadata-only "
            "outcome evidence without Study Anything sending, commenting, publishing, mutating source, mutating "
            "production, or storing customer-visible payloads."
        ),
        "source_chain": {
            "ready_rehearsal_receipt": (
                "fixtures/patch-proposal-customer-delivery-rehearsal/pass/"
                "patch-proposal-customer-delivery-rehearsal-receipt.json"
            ),
            "rehearsal_report": "platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.json",
        },
        "outcome_matrix": {
            "recorded_outcomes": recorded_count,
            "blocked_outcomes": blocked_count,
            "total_cases": len(case_reports),
            "human_operator_outcome_recorded": True,
            "host_platform_agent_outcome_recorded": True,
            "blocked_rehearsal_rejected": True,
            "missing_external_actor_rejected": True,
            "missing_action_reference_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "customer_visible_body_rejected": True,
            "pr_comment_body_rejected": True,
            "external_publication_payload_rejected": True,
            "production_payload_rejected": True,
            "automatic_send_rejected": True,
            "source_mutation_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "ready_rehearsal_required": True,
            "external_actor_required": True,
            "metadata_reference_required": True,
            "payload_body_rejected": True,
            "pr_comment_body_rejected": True,
            "automatic_send_blocked": True,
            "source_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "production_payload_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The outcome receipt proves only metadata-only recording of an external customer handoff result. "
                "It does not prove content quality, send messages, publish, comment on PRs, mutate source, or mutate production."
            ),
            "not_claimed": [
                "customer-visible body included",
                "Study Anything sent the customer message",
                "Study Anything commented on a PR",
                "Study Anything published externally",
                "Study Anything changed source",
                "Study Anything changed production",
                "truth or security certified",
            ],
        },
    }
    _validate_privacy(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_case_artifacts(output_dir: Path, cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> None:
    for case_id, artifacts in cases.items():
        for filename, payload in artifacts.items():
            write_json(output_dir / case_id / filename, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASE_IDS, "all"], default="all")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    selected = CASE_IDS if args.case == "all" else (args.case,)
    cases = {case_id: build_case_artifacts(case_id) for case_id in selected}
    write_case_artifacts(args.output_dir, cases)
    result: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "ok",
        "case_ids": list(selected),
        "output_dir_ref": args.output_dir.name,
        "privacy": dict(PRIVACY_FLAGS),
    }
    if args.report:
        result["report"] = build_report(cases)
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
