#!/usr/bin/env python3
"""Build metadata-only Patch Proposal Customer Delivery Rehearsal artifacts."""

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
import patch_proposal_customer_delivery_envelope as delivery_envelope  # noqa: E402


REHEARSAL_SCHEMA_VERSION = "patch-proposal-customer-delivery-rehearsal-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-delivery-rehearsal-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-delivery-rehearsal"
ENVELOPE_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-delivery-envelope"

CASE_IDS = (
    "pass",
    "blocked-envelope-blocked",
    "blocked-missing-recipient-scope",
    "blocked-missing-delivery-class-scope",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-missing-manual-send-boundary",
    "blocked-raw-customer-draft",
    "blocked-raw-patch-body",
    "blocked-raw-diff-body",
    "blocked-pr-comment-action",
    "blocked-auto-send",
    "blocked-external-publication",
    "blocked-production-mutation",
    "blocked-secret",
    "blocked-model-credential",
)

PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "raw_patch_body_included": False,
    "raw_diff_body_included": False,
    "raw_repository_file_body_included": False,
    "raw_pr_comment_included": False,
    "raw_customer_draft_included": False,
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
    "raw_customer_draft",
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


class PatchProposalCustomerDeliveryRehearsalError(ValueError):
    """Raised when customer-delivery rehearsal artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerDeliveryRehearsalError(f"Expected JSON object: {path}")
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
        raise PatchProposalCustomerDeliveryRehearsalError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerDeliveryRehearsalError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerDeliveryRehearsalError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerDeliveryRehearsalError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerDeliveryRehearsalError(f"Unknown case id: {case_id}")
    return {
        "envelope_case": "blocked-boundary-blocked" if case_id == "blocked-envelope-blocked" else "pass",
        "recipient_scope_confirmed": case_id != "blocked-missing-recipient-scope",
        "delivery_class_scope_confirmed": case_id != "blocked-missing-delivery-class-scope",
        "claim_boundary_visible": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_visible": case_id != "blocked-missing-privacy-boundary",
        "manual_send_boundary_acknowledged": case_id != "blocked-missing-manual-send-boundary",
        "raw_customer_draft_attached": case_id == "blocked-raw-customer-draft",
        "raw_patch_body_requested": case_id == "blocked-raw-patch-body",
        "raw_diff_body_requested": case_id == "blocked-raw-diff-body",
        "pr_comment_action_requested": case_id == "blocked-pr-comment-action",
        "auto_send_requested": case_id == "blocked-auto-send",
        "external_publication_requested": case_id == "blocked-external-publication",
        "production_mutation_requested": case_id == "blocked-production-mutation",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_envelope(case_id: str) -> dict[str, Any]:
    envelope_case = str(_case_flags(case_id)["envelope_case"])
    receipt = load_json(ENVELOPE_FIXTURE_DIR / envelope_case / "patch-proposal-customer-delivery-envelope.json")
    return delivery_envelope.validate_customer_delivery_envelope(receipt)


def build_customer_delivery_rehearsal(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    envelope_receipt = source_envelope(case_id)
    confirmations = {
        "recipient_scope_confirmed": bool(flags["recipient_scope_confirmed"]),
        "delivery_class_scope_confirmed": bool(flags["delivery_class_scope_confirmed"]),
        "claim_boundary_visible": bool(flags["claim_boundary_visible"]),
        "privacy_boundary_visible": bool(flags["privacy_boundary_visible"]),
        "manual_send_boundary_acknowledged": bool(flags["manual_send_boundary_acknowledged"]),
    }
    checks = {
        "source_envelope_ready": envelope_receipt.get("status") == "ready",
        "active_reconstruction_present": True,
        "passive_attention_only": False,
        "metadata_only_rehearsal": True,
        **confirmations,
        "raw_customer_draft_attached": bool(flags["raw_customer_draft_attached"]),
        "raw_patch_body_requested": bool(flags["raw_patch_body_requested"]),
        "raw_diff_body_requested": bool(flags["raw_diff_body_requested"]),
        "pr_comment_action_requested": bool(flags["pr_comment_action_requested"]),
        "auto_send_requested": bool(flags["auto_send_requested"]),
        "external_publication_requested": bool(flags["external_publication_requested"]),
        "production_mutation_requested": bool(flags["production_mutation_requested"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    for key, reason in (
        ("source_envelope_ready", "source_envelope_not_ready"),
        ("recipient_scope_confirmed", "recipient_scope_missing"),
        ("delivery_class_scope_confirmed", "delivery_class_scope_missing"),
        ("claim_boundary_visible", "claim_boundary_missing"),
        ("privacy_boundary_visible", "privacy_boundary_missing"),
        ("manual_send_boundary_acknowledged", "manual_send_boundary_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_customer_draft_attached", "raw_customer_draft_rejected"),
        ("raw_patch_body_requested", "raw_patch_body_request_rejected"),
        ("raw_diff_body_requested", "raw_diff_body_request_rejected"),
        ("pr_comment_action_requested", "pr_comment_action_rejected"),
        ("auto_send_requested", "automatic_customer_send_rejected"),
        ("external_publication_requested", "external_publication_rejected"),
        ("production_mutation_requested", "production_mutation_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    ready = not reasons
    receipt = {
        **_base(REHEARSAL_SCHEMA_VERSION),
        "rehearsal_id": f"patch-proposal-customer-delivery-rehearsal-{case_id}",
        "case_id": case_id,
        "status": "ready" if ready else "blocked",
        "decision": "ready_for_manual_customer_handoff_review" if ready else "block_patch_proposal_customer_delivery",
        "blocked_reasons": reasons,
        "source_refs": {
            "envelope_receipt_ref": (
                f"fixtures/patch-proposal-customer-delivery-envelope/{flags['envelope_case']}/"
                "patch-proposal-customer-delivery-envelope.json"
            ),
            "envelope_receipt_hash": artifact_hash(envelope_receipt),
            "envelope_report_ref": "platform/generated/study-anything-patch-proposal-customer-delivery-envelope.json",
        },
        "operator_reconstruction": {
            "mode": "active_boundary_reconstruction",
            "passive_attention_only": False,
            "strong_evidence": all(confirmations.values()),
            "confirmation_inputs": confirmations,
            "attention_streams_included": False,
        },
        "rehearsal_summary": {
            "package_type": "metadata_only_patch_proposal_customer_delivery_rehearsal",
            "delivery_class": "code_review_patch_proposal" if ready else None,
            "purpose": "rehearse_manual_customer_handoff_review" if ready else None,
            "allowed_next_step": [
                "manual_customer_handoff_review_outside_study_anything",
            ] if ready else [],
            "withheld_material": [
                "raw_customer_draft",
                "raw_patch_body",
                "raw_diff_body",
                "repository_file_body",
                "pr_comment_body",
                "external_publication_payload",
                "production_payload",
                "secrets",
                "model_keys",
            ],
            "requires_before_any_send": [
                "human_confirms_recipient_scope",
                "human_confirms_claim_boundary_is_visible",
                "human_confirms_no_raw_payload_or_secret_is_attached",
                "human_performs_actual_send_outside_study_anything",
            ] if ready else [],
        },
        "effect_boundary": {
            "customer_visible_payload_included": False,
            "automatic_customer_send_performed": False,
            "external_publication_performed": False,
            "production_mutation_performed": False,
            "study_anything_repository_mutation_performed": False,
            "study_anything_pr_commenting_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": (
                "A ready rehearsal permits only manual customer handoff review outside Study Anything. "
                "It does not include customer-visible prose, send messages, comment on PRs, publish externally, "
                "mutate production, or certify correctness/security."
            ),
            "not_claimed": [
                "customer-visible draft body included",
                "customer message sent",
                "PR comment created",
                "external publication approved",
                "production change approved",
                "truth or security certified",
            ],
        },
    }
    return validate_customer_delivery_rehearsal(receipt)


def validate_customer_delivery_rehearsal(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != REHEARSAL_SCHEMA_VERSION:
        raise PatchProposalCustomerDeliveryRehearsalError("customer delivery rehearsal schema_version drifted")
    _validate_privacy(receipt, label=REHEARSAL_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "rehearsal_summary", label=REHEARSAL_SCHEMA_VERSION)
    reconstruction = _require_object(receipt, "operator_reconstruction", label=REHEARSAL_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=REHEARSAL_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=REHEARSAL_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_patch_proposal_customer_delivery_rehearsal":
        raise PatchProposalCustomerDeliveryRehearsalError("rehearsal package_type must remain metadata-only")
    if reconstruction.get("mode") != "active_boundary_reconstruction":
        raise PatchProposalCustomerDeliveryRehearsalError("operator reconstruction must remain active")
    if reconstruction.get("passive_attention_only") is not False:
        raise PatchProposalCustomerDeliveryRehearsalError("passive-only attention evidence must remain rejected")
    for key in (
        "customer_visible_payload_included",
        "automatic_customer_send_performed",
        "external_publication_performed",
        "production_mutation_performed",
        "study_anything_repository_mutation_performed",
        "study_anything_pr_commenting_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalCustomerDeliveryRehearsalError(f"effect_boundary.{key} must remain false")
    if status == "ready":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalCustomerDeliveryRehearsalError("ready customer delivery rehearsal must not carry reasons")
        for key in (
            "source_envelope_ready",
            "active_reconstruction_present",
            "metadata_only_rehearsal",
            "recipient_scope_confirmed",
            "delivery_class_scope_confirmed",
            "claim_boundary_visible",
            "privacy_boundary_visible",
            "manual_send_boundary_acknowledged",
        ):
            if checks.get(key) is not True:
                raise PatchProposalCustomerDeliveryRehearsalError(f"ready customer delivery rehearsal missing check: {key}")
        for key in (
            "passive_attention_only",
            "raw_customer_draft_attached",
            "raw_patch_body_requested",
            "raw_diff_body_requested",
            "pr_comment_action_requested",
            "auto_send_requested",
            "external_publication_requested",
            "production_mutation_requested",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalCustomerDeliveryRehearsalError(
                    f"ready customer delivery rehearsal checks.{key} must remain false"
                )
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalCustomerDeliveryRehearsalError("blocked customer delivery rehearsal must carry reasons")
        if summary.get("purpose") is not None or summary.get("delivery_class") is not None:
            raise PatchProposalCustomerDeliveryRehearsalError("blocked customer delivery rehearsal must not expose purpose or class")
    else:
        raise PatchProposalCustomerDeliveryRehearsalError("customer delivery rehearsal status must be ready or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-customer-delivery-rehearsal-receipt.json": build_customer_delivery_rehearsal(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_customer_delivery_rehearsal(
            cases[case_id]["patch-proposal-customer-delivery-rehearsal-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "rehearsal_purpose": receipt["rehearsal_summary"]["purpose"],
            }
        )
    ready_count = sum(1 for row in case_reports if row["status"] == "ready")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove a patch proposal customer delivery envelope can be rehearsed as a manual handoff decision "
            "without sending, PR commenting, publishing, mutating production, or exposing raw payloads."
        ),
        "source_chain": {
            "ready_envelope_receipt": (
                "fixtures/patch-proposal-customer-delivery-envelope/pass/"
                "patch-proposal-customer-delivery-envelope.json"
            ),
            "envelope_report": "platform/generated/study-anything-patch-proposal-customer-delivery-envelope.json",
        },
        "rehearsal_matrix": {
            "ready_rehearsals": ready_count,
            "blocked_rehearsals": blocked_count,
            "total_cases": len(case_reports),
            "source_envelope_blocked_rejected": True,
            "recipient_scope_missing_rejected": True,
            "delivery_class_scope_missing_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "manual_send_boundary_missing_rejected": True,
            "raw_customer_draft_rejected": True,
            "raw_patch_and_diff_requests_rejected": True,
            "pr_comment_action_rejected": True,
            "automatic_customer_send_rejected": True,
            "external_publication_rejected": True,
            "production_mutation_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "ready_envelope_required": True,
            "active_operator_reconstruction_required": True,
            "passive_attention_only_rejected": True,
            "manual_send_boundary_required": True,
            "customer_visible_drafts_rejected": True,
            "raw_patch_and_diff_rejected": True,
            "pr_comments_rejected": True,
            "automatic_customer_send_blocked": True,
            "external_publication_blocked": True,
            "production_mutation_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The rehearsal proves only metadata-only manual customer handoff readiness. "
                "It does not send, publish, deploy, comment on PRs, or certify customer-visible content."
            ),
            "not_claimed": [
                "customer-visible draft body included",
                "customer message sent",
                "PR comment created",
                "external publication approved",
                "production change approved",
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
