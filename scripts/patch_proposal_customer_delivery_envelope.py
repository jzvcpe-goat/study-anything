#!/usr/bin/env python3
"""Build metadata-only Patch Proposal Customer Delivery Envelope artifacts."""

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
import patch_proposal_customer_handoff_boundary_gate as boundary_gate  # noqa: E402


ENVELOPE_SCHEMA_VERSION = "patch-proposal-customer-delivery-envelope-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-delivery-envelope-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-delivery-envelope"
BOUNDARY_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-handoff-boundary-gate"

CASE_IDS = (
    "pass",
    "blocked-boundary-blocked",
    "blocked-missing-manual-send-control",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-customer-draft",
    "blocked-raw-patch-body",
    "blocked-raw-diff-body",
    "blocked-pr-comment-body",
    "blocked-production-payload",
    "blocked-auto-send",
    "blocked-external-publication",
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
    "user_owned_agent_credentials_included": False,
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


class PatchProposalCustomerDeliveryEnvelopeError(ValueError):
    """Raised when customer-delivery envelope artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerDeliveryEnvelopeError(f"Expected JSON object: {path}")
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
        raise PatchProposalCustomerDeliveryEnvelopeError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerDeliveryEnvelopeError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerDeliveryEnvelopeError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerDeliveryEnvelopeError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerDeliveryEnvelopeError(f"Unknown case id: {case_id}")
    return {
        "boundary_case": "blocked-completion-blocked" if case_id == "blocked-boundary-blocked" else "pass",
        "manual_send_control_present": case_id != "blocked-missing-manual-send-control",
        "claim_boundary_present": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_present": case_id != "blocked-missing-privacy-boundary",
        "raw_customer_draft_included": case_id == "blocked-raw-customer-draft",
        "raw_patch_body_included": case_id == "blocked-raw-patch-body",
        "raw_diff_body_included": case_id == "blocked-raw-diff-body",
        "pr_comment_body_included": case_id == "blocked-pr-comment-body",
        "production_payload_included": case_id == "blocked-production-payload",
        "auto_send_requested": case_id == "blocked-auto-send",
        "external_publication_requested": case_id == "blocked-external-publication",
        "secrets_included": case_id == "blocked-secret",
        "model_credentials_included": case_id == "blocked-model-credential",
    }


def source_boundary_receipt(case_id: str) -> dict[str, Any]:
    boundary_case = str(_case_flags(case_id)["boundary_case"])
    receipt = load_json(
        BOUNDARY_FIXTURE_DIR / boundary_case / "patch-proposal-customer-handoff-boundary-receipt.json"
    )
    return boundary_gate.validate_customer_handoff_receipt(receipt)


def build_customer_delivery_envelope(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    boundary_receipt = source_boundary_receipt(case_id)
    checks = {
        "boundary_ready": boundary_receipt.get("status") == "ready",
        "manual_send_control_present": bool(flags["manual_send_control_present"]),
        "claim_boundary_present": bool(flags["claim_boundary_present"]),
        "privacy_boundary_present": bool(flags["privacy_boundary_present"]),
        "metadata_only_customer_delivery_envelope": True,
        "raw_customer_draft_included": bool(flags["raw_customer_draft_included"]),
        "raw_patch_body_included": bool(flags["raw_patch_body_included"]),
        "raw_diff_body_included": bool(flags["raw_diff_body_included"]),
        "pr_comment_body_included": bool(flags["pr_comment_body_included"]),
        "production_payload_included": bool(flags["production_payload_included"]),
        "auto_send_requested": bool(flags["auto_send_requested"]),
        "external_publication_requested": bool(flags["external_publication_requested"]),
        "secrets_included": bool(flags["secrets_included"]),
        "model_credentials_included": bool(flags["model_credentials_included"]),
    }
    reasons: list[str] = []
    for key, reason in (
        ("boundary_ready", "handoff_boundary_not_ready"),
        ("manual_send_control_present", "manual_send_control_missing"),
        ("claim_boundary_present", "claim_boundary_missing"),
        ("privacy_boundary_present", "privacy_boundary_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_customer_draft_included", "raw_customer_draft_rejected"),
        ("raw_patch_body_included", "raw_patch_body_rejected"),
        ("raw_diff_body_included", "raw_diff_body_rejected"),
        ("pr_comment_body_included", "pr_comment_body_rejected"),
        ("production_payload_included", "production_payload_rejected"),
        ("auto_send_requested", "automatic_customer_send_rejected"),
        ("external_publication_requested", "external_publication_rejected"),
        ("secrets_included", "secret_rejected"),
        ("model_credentials_included", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    ready = not reasons
    receipt = {
        **_base(ENVELOPE_SCHEMA_VERSION),
        "envelope_id": f"patch-proposal-customer-delivery-envelope-{case_id}",
        "case_id": case_id,
        "status": "ready" if ready else "blocked",
        "decision": "prepare_metadata_only_customer_delivery_envelope" if ready else "block_customer_delivery_envelope",
        "blocked_reasons": reasons,
        "source_refs": {
            "boundary_receipt_ref": (
                f"fixtures/patch-proposal-customer-handoff-boundary-gate/{flags['boundary_case']}/"
                "patch-proposal-customer-handoff-boundary-receipt.json"
            ),
            "boundary_receipt_hash": artifact_hash(boundary_receipt),
            "boundary_report_ref": "platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.json",
        },
        "envelope_summary": {
            "package_type": "metadata_only_customer_delivery_envelope",
            "delivery_class": "code_review_patch_proposal" if ready else None,
            "purpose": "prepare_manual_customer_delivery_review_packet" if ready else None,
            "allowed_customer_visible_refs": [
                "claim_boundary_summary_ref",
                "verification_command_refs",
                "metadata_receipt_refs",
                "blocked_path_summary_ref",
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
                "A ready envelope permits only metadata-only customer delivery review preparation. "
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
    return validate_customer_delivery_envelope(receipt)


def validate_customer_delivery_envelope(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        raise PatchProposalCustomerDeliveryEnvelopeError("customer delivery envelope schema_version drifted")
    _validate_privacy(receipt, label=ENVELOPE_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "envelope_summary", label=ENVELOPE_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=ENVELOPE_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=ENVELOPE_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_customer_delivery_envelope":
        raise PatchProposalCustomerDeliveryEnvelopeError("envelope package_type must remain metadata-only")
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
            raise PatchProposalCustomerDeliveryEnvelopeError(f"effect_boundary.{key} must remain false")
    if status == "ready":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalCustomerDeliveryEnvelopeError("ready customer delivery envelope must not carry reasons")
        for key in (
            "boundary_ready",
            "manual_send_control_present",
            "claim_boundary_present",
            "privacy_boundary_present",
            "metadata_only_customer_delivery_envelope",
        ):
            if checks.get(key) is not True:
                raise PatchProposalCustomerDeliveryEnvelopeError(f"ready customer delivery envelope missing check: {key}")
        for key in (
            "raw_customer_draft_included",
            "raw_patch_body_included",
            "raw_diff_body_included",
            "pr_comment_body_included",
            "production_payload_included",
            "auto_send_requested",
            "external_publication_requested",
            "secrets_included",
            "model_credentials_included",
        ):
            if checks.get(key) is not False:
                raise PatchProposalCustomerDeliveryEnvelopeError(
                    f"ready customer delivery envelope checks.{key} must remain false"
                )
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalCustomerDeliveryEnvelopeError("blocked customer delivery envelope must carry reasons")
        if summary.get("purpose") is not None or summary.get("delivery_class") is not None:
            raise PatchProposalCustomerDeliveryEnvelopeError("blocked customer delivery envelope must not expose purpose or class")
    else:
        raise PatchProposalCustomerDeliveryEnvelopeError("customer delivery envelope status must be ready or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-customer-delivery-envelope.json": build_customer_delivery_envelope(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        envelope = validate_customer_delivery_envelope(
            cases[case_id]["patch-proposal-customer-delivery-envelope.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": envelope["status"],
                "decision": envelope["decision"],
                "blocked_reasons": envelope["blocked_reasons"],
                "envelope_purpose": envelope["envelope_summary"]["purpose"],
            }
        )
    ready_count = sum(1 for row in case_reports if row["status"] == "ready")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": "Prove customer delivery envelope preparation remains metadata-only and pre-send.",
        "source_chain": {
            "ready_boundary_receipt": (
                "fixtures/patch-proposal-customer-handoff-boundary-gate/pass/"
                "patch-proposal-customer-handoff-boundary-receipt.json"
            ),
            "boundary_report": "platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.json",
        },
        "delivery_matrix": {
            "ready_envelopes": ready_count,
            "blocked_envelopes": blocked_count,
            "total_cases": len(case_reports),
            "handoff_boundary_not_ready_rejected": True,
            "manual_send_control_missing_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "raw_customer_draft_rejected": True,
            "raw_patch_body_rejected": True,
            "raw_diff_body_rejected": True,
            "pr_comment_body_rejected": True,
            "production_payload_rejected": True,
            "automatic_customer_send_rejected": True,
            "external_publication_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "ready_boundary_required": True,
            "manual_send_control_required": True,
            "claim_boundary_required": True,
            "privacy_boundary_required": True,
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
                "The envelope proves only metadata-only customer delivery review preparation. "
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
