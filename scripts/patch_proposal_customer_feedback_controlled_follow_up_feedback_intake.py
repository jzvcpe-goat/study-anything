#!/usr/bin/env python3
"""Build metadata-only controlled follow-up feedback intake receipts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_outcome_receipt as outcome  # noqa: E402


INTAKE_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-intake-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-intake-v1"

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-intake"
)
OUTCOME_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-outcome"

CASE_IDS = (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-outcome-blocked",
    "blocked-missing-response-signal",
    "blocked-missing-signal-reference",
    "blocked-missing-product-loop-target",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-private-customer-data",
    "blocked-pr-comment-body",
    "blocked-external-publication-payload",
    "blocked-automatic-follow-up",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_SIGNAL_TYPES = {"customer_signal", "operator_signal", "host_platform_agent_signal"}

PRIVACY_FLAGS = {
    **outcome.PRIVACY_FLAGS,
    "controlled_follow_up_feedback_intake_metadata_only": True,
    "product_loop_backlog_candidate_only": True,
    "raw_customer_reply_included": False,
    "customer_identity_included": False,
    "private_customer_data_included": False,
    "raw_pr_comment_included": False,
    "external_publication_payload_included": False,
    "product_loop_backlog_body_included": False,
    "repository_secrets_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}

FORBIDDEN_RAW_FIELDS = {
    *outcome.FORBIDDEN_RAW_FIELDS,
    "raw_customer_reply",
    "customer_reply",
    "customer_reply_body",
    "customer_identity",
    "customer_name",
    "customer_email",
    "customer_phone",
    "private_customer_data",
    "requester_identity",
    "raw_pr_comment",
    "pr_comment_body",
    "external_publication_payload",
    "product_loop_backlog_body",
    "raw_backlog_description",
    "backlog_description_body",
    "source_mutation_payload",
    "production_mutation_payload",
    "model_call_payload",
    "secret",
    "secrets",
    "model_key",
    "model_keys",
    "agent_credentials",
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "A controlled follow-up feedback intake receipt records only metadata "
        "that an external customer, operator, or host-platform Agent response "
        "signal exists after a recorded controlled follow-up outcome. It may "
        "point toward a Product Loop backlog candidate, but it does not store "
        "raw replies, identify customers, comment on PRs, publish externally, "
        "mutate source, mutate production, call models, or store secrets."
    ),
    "not_claimed": [
        "raw customer reply included",
        "customer identity included",
        "private customer data included",
        "PR comment body included",
        "external publication payload included",
        "Product Loop backlog was mutated",
        "automatic priority was assigned",
        "Study Anything sent a follow-up",
        "Study Anything changed source",
        "Study Anything changed production",
        "Study Anything called a model",
        "customer satisfaction certified",
    ],
}


class PatchProposalControlledFollowUpFeedbackIntakeError(ValueError):
    """Raised when controlled follow-up feedback intake artifacts are unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpFeedbackIntakeError(f"Expected JSON object: {path}")
    return payload


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dump_json(payload))


def _base(schema_version: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "created_at": dual_loop.DETERMINISTIC_TIMESTAMP,
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY_FLAGS),
    }


def _require_object(payload: Mapping[str, Any], key: str, *, label: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise PatchProposalControlledFollowUpFeedbackIntakeError(f"{label}.{key} must be an object")
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
        raise PatchProposalControlledFollowUpFeedbackIntakeError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackIntakeError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _case_flags(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpFeedbackIntakeError(f"Unknown case id: {case_id}")
    signal_type = "customer_signal"
    if case_id == "pass-operator-signal":
        signal_type = "operator_signal"
    elif case_id == "pass-host-platform-agent-signal":
        signal_type = "host_platform_agent_signal"
    elif case_id == "blocked-missing-response-signal":
        signal_type = None
    return {
        "outcome_case": (
            "blocked-rehearsal-blocked"
            if case_id == "blocked-outcome-blocked"
            else ("pass-host-platform-agent" if case_id == "pass-host-platform-agent-signal" else "pass-human-operator")
        ),
        "signal_type": signal_type,
        "signal_ref_hash_present": case_id != "blocked-missing-signal-reference",
        "product_loop_target_declared": case_id != "blocked-missing-product-loop-target",
        "claim_boundary_visible": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_visible": case_id != "blocked-missing-privacy-boundary",
        "raw_customer_reply_attached": case_id == "blocked-raw-customer-reply",
        "customer_identity_attached": case_id == "blocked-customer-identity",
        "private_customer_data_attached": case_id == "blocked-private-customer-data",
        "pr_comment_body_attached": case_id == "blocked-pr-comment-body",
        "external_publication_payload_attached": case_id == "blocked-external-publication-payload",
        "automatic_follow_up_performed": case_id == "blocked-automatic-follow-up",
        "product_loop_backlog_mutation_performed": case_id == "blocked-product-loop-backlog-mutation",
        "source_mutation_performed": case_id == "blocked-source-mutation",
        "production_mutation_performed": case_id == "blocked-production-mutation",
        "model_call_performed": case_id == "blocked-model-call",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_outcome(case_id: str) -> dict[str, Any]:
    outcome_case = str(_case_flags(case_id)["outcome_case"])
    receipt = load_json(
        OUTCOME_FIXTURE_DIR / outcome_case / "patch-proposal-controlled-follow-up-outcome-receipt.json"
    )
    return outcome.validate_controlled_follow_up_outcome(receipt)


def _signal_ref_hash(case_id: str, signal_type: str | None) -> str | None:
    if not _case_flags(case_id)["signal_ref_hash_present"]:
        return None
    return dual_loop.sha256_text(f"{case_id}:{signal_type}:controlled-follow-up-feedback-signal")


def _product_loop_candidate_ref_hash(case_id: str, signal_ref_hash: str | None) -> str | None:
    if not _case_flags(case_id)["product_loop_target_declared"] or not signal_ref_hash:
        return None
    return dual_loop.sha256_text(f"{case_id}:{signal_ref_hash}:product-loop-backlog-candidate")


def build_controlled_follow_up_feedback_intake(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    outcome_receipt = source_outcome(case_id)
    signal_type = flags["signal_type"]
    signal_ref_hash = _signal_ref_hash(case_id, str(signal_type) if signal_type else None)
    candidate_ref_hash = _product_loop_candidate_ref_hash(case_id, signal_ref_hash)
    outcome_checks = _require_object(outcome_receipt, "checks", label="source_outcome")
    checks = {
        "source_outcome_recorded": outcome_receipt.get("status") == "recorded",
        "product_loop_ref_preserved": outcome_checks.get("product_loop_ref_preserved") is True,
        "dual_loop_refs_preserved": outcome_checks.get("dual_loop_refs_preserved") is True,
        "delivery_trust_refs_preserved": outcome_checks.get("delivery_trust_refs_preserved") is True,
        "active_reconstruction_ref_preserved": outcome_checks.get("active_reconstruction_ref_preserved") is True,
        "controlled_follow_up_outcome_ref_preserved": outcome_checks.get("action_reference_hash_present") is True,
        "feedback_signal_declared": signal_type in ALLOWED_SIGNAL_TYPES,
        "feedback_signal_reference_hash_present": isinstance(signal_ref_hash, str) and len(signal_ref_hash) == 64,
        "feedback_signal_happened_outside_study_anything": True,
        "product_loop_backlog_candidate_path_declared": isinstance(candidate_ref_hash, str)
        and len(candidate_ref_hash) == 64,
        "claim_boundary_visible": bool(flags["claim_boundary_visible"]),
        "privacy_boundary_visible": bool(flags["privacy_boundary_visible"]),
        "metadata_only_feedback": True,
        "raw_customer_reply_attached": bool(flags["raw_customer_reply_attached"]),
        "customer_identity_attached": bool(flags["customer_identity_attached"]),
        "private_customer_data_attached": bool(flags["private_customer_data_attached"]),
        "pr_comment_body_attached": bool(flags["pr_comment_body_attached"]),
        "external_publication_payload_attached": bool(flags["external_publication_payload_attached"]),
        "automatic_follow_up_performed": bool(flags["automatic_follow_up_performed"]),
        "product_loop_backlog_mutation_performed": bool(flags["product_loop_backlog_mutation_performed"]),
        "source_mutation_performed": bool(flags["source_mutation_performed"]),
        "production_mutation_performed": bool(flags["production_mutation_performed"]),
        "model_call_performed": bool(flags["model_call_performed"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    for key, reason in (
        ("source_outcome_recorded", "source_outcome_not_recorded"),
        ("product_loop_ref_preserved", "product_loop_ref_missing"),
        ("dual_loop_refs_preserved", "dual_loop_ref_missing"),
        ("delivery_trust_refs_preserved", "delivery_trust_ref_missing"),
        ("active_reconstruction_ref_preserved", "active_reconstruction_ref_missing"),
        ("controlled_follow_up_outcome_ref_preserved", "controlled_follow_up_outcome_ref_missing"),
        ("feedback_signal_declared", "feedback_signal_missing"),
        ("feedback_signal_reference_hash_present", "feedback_signal_reference_hash_missing"),
        ("product_loop_backlog_candidate_path_declared", "product_loop_target_missing"),
        ("claim_boundary_visible", "claim_boundary_missing"),
        ("privacy_boundary_visible", "privacy_boundary_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_customer_reply_attached", "raw_customer_reply_rejected"),
        ("customer_identity_attached", "customer_identity_rejected"),
        ("private_customer_data_attached", "private_customer_data_rejected"),
        ("pr_comment_body_attached", "pr_comment_body_rejected"),
        ("external_publication_payload_attached", "external_publication_payload_rejected"),
        ("automatic_follow_up_performed", "automatic_follow_up_rejected"),
        ("product_loop_backlog_mutation_performed", "product_loop_backlog_mutation_rejected"),
        ("source_mutation_performed", "source_mutation_rejected"),
        ("production_mutation_performed", "production_mutation_rejected"),
        ("model_call_performed", "model_call_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    accepted = not reasons
    receipt = {
        **_base(INTAKE_SCHEMA_VERSION),
        "feedback_intake_id": f"patch-proposal-controlled-follow-up-feedback-intake-{case_id}",
        "case_id": case_id,
        "status": "accepted" if accepted else "blocked",
        "decision": (
            "record_controlled_follow_up_feedback_intake"
            if accepted
            else "block_controlled_follow_up_feedback_intake"
        ),
        "blocked_reasons": list(dict.fromkeys(reasons)),
        "source_refs": {
            "controlled_follow_up_outcome_receipt_ref": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-outcome/"
                f"{flags['outcome_case']}/patch-proposal-controlled-follow-up-outcome-receipt.json"
            ),
            "controlled_follow_up_outcome_receipt_hash": artifact_hash(outcome_receipt),
            "controlled_follow_up_outcome_report_ref": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-outcome.json"
            ),
        },
        "feedback_signal_summary": {
            "package_type": "metadata_only_patch_proposal_controlled_follow_up_feedback_intake",
            "signal_type": signal_type,
            "signal_ref_hash": signal_ref_hash,
            "raw_feedback_included": False,
            "raw_customer_reply_included": False,
            "customer_identity_included": False,
            "private_customer_data_included": False,
            "pr_comment_body_included": False,
            "payload_hash_only": True,
            "external_system_credentials_included": False,
        },
        "product_loop_destination": {
            "package_type": "metadata_only_product_loop_backlog_candidate_ref",
            "destination": "product_loop_backlog_candidate",
            "candidate_ref_hash": candidate_ref_hash,
            "priority_assignment": "not_assigned",
            "ready_for_execution": False,
            "ready_for_customer_delivery": False,
            "product_loop_storage_mutated": False,
        },
        "effect_boundary": {
            "study_anything_customer_follow_up_send_performed": False,
            "study_anything_automatic_follow_up_performed": False,
            "study_anything_product_loop_backlog_mutation_performed": False,
            "study_anything_repository_mutation_performed": False,
            "study_anything_pr_commenting_performed": False,
            "study_anything_external_publication_performed": False,
            "study_anything_production_mutation_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
        },
        "checks": checks,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_controlled_follow_up_feedback_intake(receipt)


def validate_controlled_follow_up_feedback_intake(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != INTAKE_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackIntakeError(
            "controlled follow-up feedback intake schema_version drifted"
        )
    _validate_privacy(receipt, label=INTAKE_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "feedback_signal_summary", label=INTAKE_SCHEMA_VERSION)
    destination = _require_object(receipt, "product_loop_destination", label=INTAKE_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=INTAKE_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=INTAKE_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_patch_proposal_controlled_follow_up_feedback_intake":
        raise PatchProposalControlledFollowUpFeedbackIntakeError("feedback intake package_type must remain metadata-only")
    for key in (
        "raw_feedback_included",
        "raw_customer_reply_included",
        "customer_identity_included",
        "private_customer_data_included",
        "pr_comment_body_included",
        "external_system_credentials_included",
    ):
        if summary.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackIntakeError(f"feedback_signal_summary.{key} must remain false")
    if destination.get("package_type") != "metadata_only_product_loop_backlog_candidate_ref":
        raise PatchProposalControlledFollowUpFeedbackIntakeError("product loop destination package_type drifted")
    for key in ("ready_for_execution", "ready_for_customer_delivery", "product_loop_storage_mutated"):
        if destination.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackIntakeError(f"product_loop_destination.{key} must remain false")
    for key in (
        "study_anything_customer_follow_up_send_performed",
        "study_anything_automatic_follow_up_performed",
        "study_anything_product_loop_backlog_mutation_performed",
        "study_anything_repository_mutation_performed",
        "study_anything_pr_commenting_performed",
        "study_anything_external_publication_performed",
        "study_anything_production_mutation_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackIntakeError(f"effect_boundary.{key} must remain false")
    if status == "accepted":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalControlledFollowUpFeedbackIntakeError("accepted feedback intake must not carry reasons")
        for key in (
            "source_outcome_recorded",
            "product_loop_ref_preserved",
            "dual_loop_refs_preserved",
            "delivery_trust_refs_preserved",
            "active_reconstruction_ref_preserved",
            "controlled_follow_up_outcome_ref_preserved",
            "feedback_signal_declared",
            "feedback_signal_reference_hash_present",
            "feedback_signal_happened_outside_study_anything",
            "product_loop_backlog_candidate_path_declared",
            "claim_boundary_visible",
            "privacy_boundary_visible",
            "metadata_only_feedback",
        ):
            if checks.get(key) is not True:
                raise PatchProposalControlledFollowUpFeedbackIntakeError(f"accepted feedback intake missing check: {key}")
        for key in (
            "raw_customer_reply_attached",
            "customer_identity_attached",
            "private_customer_data_attached",
            "pr_comment_body_attached",
            "external_publication_payload_attached",
            "automatic_follow_up_performed",
            "product_loop_backlog_mutation_performed",
            "source_mutation_performed",
            "production_mutation_performed",
            "model_call_performed",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalControlledFollowUpFeedbackIntakeError(
                    f"accepted feedback intake checks.{key} must remain false"
                )
        if summary.get("signal_type") not in ALLOWED_SIGNAL_TYPES:
            raise PatchProposalControlledFollowUpFeedbackIntakeError("accepted feedback signal_type must be bounded")
        candidate_ref_hash = destination.get("candidate_ref_hash")
        if not isinstance(candidate_ref_hash, str) or len(candidate_ref_hash) != 64:
            raise PatchProposalControlledFollowUpFeedbackIntakeError("accepted feedback intake missing candidate ref hash")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalControlledFollowUpFeedbackIntakeError("blocked feedback intake must carry reasons")
    else:
        raise PatchProposalControlledFollowUpFeedbackIntakeError(
            "controlled follow-up feedback intake status must be accepted or blocked"
        )
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {
        "patch-proposal-controlled-follow-up-feedback-intake-receipt.json": (
            build_controlled_follow_up_feedback_intake(case_id)
        )
    }


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_controlled_follow_up_feedback_intake(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-intake-receipt.json"]
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
            "Prove metadata-only response signals after controlled follow-up outcomes can be "
            "recorded as Product Loop backlog candidate refs while preserving Product Loop, "
            "Dual Loop, Delivery Trust Case, active reconstruction, and controlled follow-up evidence."
        ),
        "source_chain": {
            "recorded_controlled_follow_up_outcome_receipt": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-outcome/"
                "pass-human-operator/patch-proposal-controlled-follow-up-outcome-receipt.json"
            ),
            "controlled_follow_up_outcome_report": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-outcome.json"
            ),
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
            "missing_product_loop_target_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "raw_customer_reply_rejected": True,
            "customer_identity_rejected": True,
            "private_customer_data_rejected": True,
            "pr_comment_body_rejected": True,
            "external_publication_payload_rejected": True,
            "automatic_follow_up_rejected": True,
            "product_loop_backlog_mutation_rejected": True,
            "source_mutation_rejected": True,
            "production_mutation_rejected": True,
            "model_call_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "recorded_controlled_follow_up_outcome_required": True,
            "product_loop_refs_preserved": True,
            "dual_loop_refs_preserved": True,
            "delivery_trust_refs_preserved": True,
            "active_reconstruction_ref_preserved": True,
            "controlled_follow_up_outcome_ref_preserved": True,
            "feedback_signal_required": True,
            "product_loop_backlog_candidate_ref_required": True,
            "raw_customer_reply_rejected": True,
            "customer_identity_rejected": True,
            "private_customer_data_rejected": True,
            "pr_comment_body_rejected": True,
            "external_publication_payload_blocked": True,
            "automatic_follow_up_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
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
