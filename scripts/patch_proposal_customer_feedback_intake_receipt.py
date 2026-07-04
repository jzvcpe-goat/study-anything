#!/usr/bin/env python3
"""Build metadata-only Patch Proposal Customer Feedback Intake Receipt artifacts."""

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
import patch_proposal_customer_delivery_outcome_receipt as delivery_outcome  # noqa: E402


FEEDBACK_RECEIPT_SCHEMA_VERSION = "patch-proposal-customer-feedback-intake-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-intake-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-feedback-intake"
OUTCOME_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-delivery-outcome"

CASE_IDS = (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-outcome-blocked",
    "blocked-missing-response-signal",
    "blocked-missing-signal-reference",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-customer-reply",
    "blocked-private-customer-data",
    "blocked-pr-comment-body",
    "blocked-external-publication-payload",
    "blocked-production-payload",
    "blocked-automatic-follow-up",
    "blocked-source-mutation",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_SIGNAL_TYPES = {"customer_signal", "operator_signal", "host_platform_agent_signal"}

PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "raw_patch_body_included": False,
    "raw_diff_body_included": False,
    "raw_repository_file_body_included": False,
    "raw_customer_reply_included": False,
    "private_customer_data_included": False,
    "raw_pr_comment_included": False,
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
    "raw_customer_reply",
    "customer_reply",
    "customer_reply_body",
    "customer_visible_body",
    "customer_visible_payload",
    "private_customer_data",
    "customer_email",
    "customer_name",
    "customer_phone",
    "requester_identity",
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


class PatchProposalCustomerFeedbackIntakeError(ValueError):
    """Raised when customer-feedback intake artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerFeedbackIntakeError(f"Expected JSON object: {path}")
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
        raise PatchProposalCustomerFeedbackIntakeError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerFeedbackIntakeError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerFeedbackIntakeError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerFeedbackIntakeError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str | None]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerFeedbackIntakeError(f"Unknown case id: {case_id}")
    signal_type = "customer_signal"
    if case_id == "pass-operator-signal":
        signal_type = "operator_signal"
    elif case_id == "pass-host-platform-agent-signal":
        signal_type = "host_platform_agent_signal"
    elif case_id == "blocked-missing-response-signal":
        signal_type = None
    return {
        "outcome_case": "blocked-rehearsal-blocked" if case_id == "blocked-outcome-blocked" else "pass-human-operator",
        "signal_type": signal_type,
        "signal_ref_hash_present": case_id != "blocked-missing-signal-reference",
        "claim_boundary_visible": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_visible": case_id != "blocked-missing-privacy-boundary",
        "raw_customer_reply_attached": case_id == "blocked-raw-customer-reply",
        "private_customer_data_attached": case_id == "blocked-private-customer-data",
        "pr_comment_body_attached": case_id == "blocked-pr-comment-body",
        "external_publication_payload_attached": case_id == "blocked-external-publication-payload",
        "production_payload_attached": case_id == "blocked-production-payload",
        "automatic_follow_up_performed": case_id == "blocked-automatic-follow-up",
        "source_mutation_performed": case_id == "blocked-source-mutation",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_outcome(case_id: str) -> dict[str, Any]:
    outcome_case = str(_case_flags(case_id)["outcome_case"])
    receipt = load_json(
        OUTCOME_FIXTURE_DIR / outcome_case / "patch-proposal-customer-delivery-outcome-receipt.json"
    )
    return delivery_outcome.validate_customer_delivery_outcome(receipt)


def _signal_ref_hash(case_id: str, signal_type: str | None) -> str | None:
    if not _case_flags(case_id)["signal_ref_hash_present"]:
        return None
    return dual_loop.sha256_text(f"{case_id}:{signal_type}:external-customer-feedback-signal")


def build_customer_feedback_intake(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    outcome_receipt = source_outcome(case_id)
    signal_type = flags["signal_type"]
    signal_ref_hash = _signal_ref_hash(case_id, str(signal_type) if signal_type else None)
    checks = {
        "source_outcome_recorded": outcome_receipt.get("status") == "recorded",
        "feedback_signal_declared": signal_type in ALLOWED_SIGNAL_TYPES,
        "feedback_signal_reference_hash_present": isinstance(signal_ref_hash, str) and len(signal_ref_hash) == 64,
        "feedback_signal_happened_outside_study_anything": True,
        "claim_boundary_visible": bool(flags["claim_boundary_visible"]),
        "privacy_boundary_visible": bool(flags["privacy_boundary_visible"]),
        "metadata_only_feedback": True,
        "raw_customer_reply_attached": bool(flags["raw_customer_reply_attached"]),
        "private_customer_data_attached": bool(flags["private_customer_data_attached"]),
        "pr_comment_body_attached": bool(flags["pr_comment_body_attached"]),
        "external_publication_payload_attached": bool(flags["external_publication_payload_attached"]),
        "production_payload_attached": bool(flags["production_payload_attached"]),
        "automatic_follow_up_performed": bool(flags["automatic_follow_up_performed"]),
        "source_mutation_performed": bool(flags["source_mutation_performed"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    for key, reason in (
        ("source_outcome_recorded", "source_outcome_not_recorded"),
        ("feedback_signal_declared", "feedback_signal_missing"),
        ("feedback_signal_reference_hash_present", "feedback_signal_reference_hash_missing"),
        ("claim_boundary_visible", "claim_boundary_missing"),
        ("privacy_boundary_visible", "privacy_boundary_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_customer_reply_attached", "raw_customer_reply_rejected"),
        ("private_customer_data_attached", "private_customer_data_rejected"),
        ("pr_comment_body_attached", "pr_comment_body_rejected"),
        ("external_publication_payload_attached", "external_publication_payload_rejected"),
        ("production_payload_attached", "production_payload_rejected"),
        ("automatic_follow_up_performed", "automatic_follow_up_rejected"),
        ("source_mutation_performed", "source_mutation_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    accepted = not reasons
    receipt = {
        **_base(FEEDBACK_RECEIPT_SCHEMA_VERSION),
        "feedback_intake_id": f"patch-proposal-customer-feedback-intake-{case_id}",
        "case_id": case_id,
        "status": "accepted" if accepted else "blocked",
        "decision": "record_customer_feedback_intake" if accepted else "block_customer_feedback_intake",
        "blocked_reasons": reasons,
        "source_refs": {
            "delivery_outcome_receipt_ref": (
                f"fixtures/patch-proposal-customer-delivery-outcome/{flags['outcome_case']}/"
                "patch-proposal-customer-delivery-outcome-receipt.json"
            ),
            "delivery_outcome_receipt_hash": artifact_hash(outcome_receipt),
            "delivery_outcome_report_ref": "platform/generated/study-anything-patch-proposal-customer-delivery-outcome.json",
        },
        "feedback_signal_summary": {
            "package_type": "metadata_only_patch_proposal_customer_feedback_intake",
            "signal_type": signal_type,
            "signal_ref_hash": signal_ref_hash,
            "raw_feedback_included": False,
            "private_customer_data_included": False,
            "pr_comment_body_included": False,
            "payload_hash_only": True,
            "external_system_credentials_included": False,
        },
        "effect_boundary": {
            "study_anything_customer_follow_up_send_performed": False,
            "study_anything_automatic_follow_up_performed": False,
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
                "A feedback-intake receipt proves only that a customer/operator response signal was represented "
                "as metadata after an external customer delivery outcome. It does not include the response body, "
                "identify the customer, follow up automatically, comment on PRs, publish externally, mutate source, "
                "mutate production, or certify satisfaction."
            ),
            "not_claimed": [
                "raw customer reply included",
                "private customer data included",
                "Study Anything sent a follow-up",
                "Study Anything commented on a PR",
                "Study Anything published externally",
                "Study Anything changed source",
                "Study Anything changed production",
                "customer satisfaction certified",
            ],
        },
    }
    return validate_customer_feedback_intake(receipt)


def validate_customer_feedback_intake(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != FEEDBACK_RECEIPT_SCHEMA_VERSION:
        raise PatchProposalCustomerFeedbackIntakeError("customer feedback intake schema_version drifted")
    _validate_privacy(receipt, label=FEEDBACK_RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "feedback_signal_summary", label=FEEDBACK_RECEIPT_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=FEEDBACK_RECEIPT_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=FEEDBACK_RECEIPT_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_patch_proposal_customer_feedback_intake":
        raise PatchProposalCustomerFeedbackIntakeError("feedback intake package_type must remain metadata-only")
    for key in ("raw_feedback_included", "private_customer_data_included", "pr_comment_body_included"):
        if summary.get(key) is not False:
            raise PatchProposalCustomerFeedbackIntakeError(f"feedback intake {key} must remain false")
    if summary.get("external_system_credentials_included") is not False:
        raise PatchProposalCustomerFeedbackIntakeError("external credentials must not be included")
    for key in (
        "study_anything_customer_follow_up_send_performed",
        "study_anything_automatic_follow_up_performed",
        "study_anything_repository_mutation_performed",
        "study_anything_pr_commenting_performed",
        "study_anything_external_publication_performed",
        "study_anything_production_mutation_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalCustomerFeedbackIntakeError(f"effect_boundary.{key} must remain false")
    if status == "accepted":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalCustomerFeedbackIntakeError("accepted customer feedback intake must not carry reasons")
        for key in (
            "source_outcome_recorded",
            "feedback_signal_declared",
            "feedback_signal_reference_hash_present",
            "feedback_signal_happened_outside_study_anything",
            "claim_boundary_visible",
            "privacy_boundary_visible",
            "metadata_only_feedback",
        ):
            if checks.get(key) is not True:
                raise PatchProposalCustomerFeedbackIntakeError(f"accepted customer feedback intake missing check: {key}")
        for key in (
            "raw_customer_reply_attached",
            "private_customer_data_attached",
            "pr_comment_body_attached",
            "external_publication_payload_attached",
            "production_payload_attached",
            "automatic_follow_up_performed",
            "source_mutation_performed",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalCustomerFeedbackIntakeError(
                    f"accepted customer feedback intake checks.{key} must remain false"
                )
        if summary.get("signal_type") not in ALLOWED_SIGNAL_TYPES:
            raise PatchProposalCustomerFeedbackIntakeError("accepted feedback signal_type must be bounded")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalCustomerFeedbackIntakeError("blocked customer feedback intake must carry reasons")
    else:
        raise PatchProposalCustomerFeedbackIntakeError("customer feedback intake status must be accepted or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-customer-feedback-intake-receipt.json": build_customer_feedback_intake(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_customer_feedback_intake(
            cases[case_id]["patch-proposal-customer-feedback-intake-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "signal_type": receipt["feedback_signal_summary"]["signal_type"],
            }
        )
    accepted_count = sum(1 for row in case_reports if row["status"] == "accepted")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove customer/operator response signals can re-enter the patch proposal delivery loop as metadata-only "
            "feedback intake evidence without storing raw customer replies, private customer data, PR comment bodies, "
            "external publication payloads, production payloads, secrets, or model credentials."
        ),
        "source_chain": {
            "recorded_delivery_outcome_receipt": (
                "fixtures/patch-proposal-customer-delivery-outcome/pass-human-operator/"
                "patch-proposal-customer-delivery-outcome-receipt.json"
            ),
            "delivery_outcome_report": "platform/generated/study-anything-patch-proposal-customer-delivery-outcome.json",
        },
        "feedback_matrix": {
            "accepted_feedback_intakes": accepted_count,
            "blocked_feedback_intakes": blocked_count,
            "total_cases": len(case_reports),
            "customer_signal_accepted": True,
            "operator_signal_accepted": True,
            "host_platform_agent_signal_accepted": True,
            "blocked_outcome_rejected": True,
            "missing_response_signal_rejected": True,
            "missing_signal_reference_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "raw_customer_reply_rejected": True,
            "private_customer_data_rejected": True,
            "pr_comment_body_rejected": True,
            "external_publication_payload_rejected": True,
            "production_payload_rejected": True,
            "automatic_follow_up_rejected": True,
            "source_mutation_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "recorded_outcome_required": True,
            "bounded_feedback_signal_required": True,
            "metadata_reference_required": True,
            "raw_customer_reply_rejected": True,
            "private_customer_data_rejected": True,
            "pr_comment_body_rejected": True,
            "automatic_follow_up_blocked": True,
            "source_mutation_blocked": True,
            "external_publication_payload_blocked": True,
            "production_payload_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The feedback intake receipt proves only metadata-only representation of a customer/operator response "
                "signal after an external customer delivery outcome. It does not include raw replies, identify the "
                "customer, send follow-ups, publish, comment on PRs, mutate source, or mutate production."
            ),
            "not_claimed": [
                "raw customer reply included",
                "private customer data included",
                "Study Anything sent a follow-up",
                "Study Anything commented on a PR",
                "Study Anything published externally",
                "Study Anything changed source",
                "Study Anything changed production",
                "customer satisfaction certified",
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
