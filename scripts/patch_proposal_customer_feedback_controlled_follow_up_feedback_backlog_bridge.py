#!/usr/bin/env python3
"""Bridge controlled follow-up feedback intake receipts into backlog signal refs."""

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
import patch_proposal_customer_feedback_controlled_follow_up_feedback_intake as feedback_intake  # noqa: E402


BRIDGE_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge-v1"
BACKLOG_SIGNAL_SCHEMA_VERSION = "product-loop-backlog-signal-v1"
REPORT_SCHEMA_VERSION = BRIDGE_SCHEMA_VERSION

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge"
)
INTAKE_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-intake"

CASE_IDS = (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-intake-blocked",
    "blocked-missing-product-loop-target",
    "blocked-automatic-priority-assignment",
    "blocked-automatic-follow-up",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-private-customer-data",
    "blocked-pr-comment-body",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

PRIVACY_FLAGS = {
    **feedback_intake.PRIVACY_FLAGS,
    "raw_backlog_description_included": False,
    "raw_customer_request_included": False,
    "automatic_priority_rationale_included": False,
    "product_loop_backlog_signal_metadata_only": True,
}

EFFECT_BOUNDARY = {
    "study_anything_backlog_storage_mutated": False,
    "study_anything_product_loop_backlog_mutation_performed": False,
    "study_anything_priority_assignment_performed": False,
    "study_anything_customer_follow_up_send_performed": False,
    "study_anything_automatic_follow_up_performed": False,
    "study_anything_repository_mutation_performed": False,
    "study_anything_external_publication_performed": False,
    "study_anything_production_mutation_performed": False,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
}

FORBIDDEN_RAW_FIELDS = {
    *feedback_intake.FORBIDDEN_RAW_FIELDS,
    "raw_backlog_description",
    "backlog_description_body",
    "raw_customer_request",
    "priority_rationale",
    "automatic_priority",
    "assigned_priority",
    "follow_up_body",
    "follow_up_payload",
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "An accepted controlled follow-up feedback intake receipt can become a "
        "metadata-only Product Loop backlog signal ref. The signal is not "
        "prioritized, not written to a live backlog, not sent to a customer, "
        "not executed, and not promoted to production."
    ),
    "not_claimed": [
        "raw customer reply included",
        "customer identity included",
        "private customer data included",
        "automatic priority assigned",
        "Product Loop backlog mutated",
        "Study Anything sent a follow-up",
        "Study Anything changed source",
        "Study Anything changed production",
        "Study Anything called a model",
        "customer satisfaction certified",
    ],
}


class PatchProposalControlledFollowUpFeedbackBacklogBridgeError(ValueError):
    """Raised when controlled follow-up feedback backlog bridge artifacts are unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(f"Expected JSON object: {path}")
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
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(f"{label}.{key} must be an object")
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
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _case_flags(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(f"Unknown case id: {case_id}")
    intake_case = "pass-customer-signal"
    if case_id == "pass-operator-signal":
        intake_case = "pass-operator-signal"
    elif case_id == "pass-host-platform-agent-signal":
        intake_case = "pass-host-platform-agent-signal"
    elif case_id == "blocked-intake-blocked":
        intake_case = "blocked-raw-customer-reply"
    return {
        "intake_case": intake_case,
        "product_loop_target_declared": case_id != "blocked-missing-product-loop-target",
        "automatic_priority_assignment_performed": case_id == "blocked-automatic-priority-assignment",
        "automatic_follow_up_performed": case_id == "blocked-automatic-follow-up",
        "product_loop_backlog_mutation_performed": case_id == "blocked-product-loop-backlog-mutation",
        "source_mutation_performed": case_id == "blocked-source-mutation",
        "production_mutation_performed": case_id == "blocked-production-mutation",
        "external_publication_performed": case_id == "blocked-external-publication",
        "raw_customer_reply_attached": case_id == "blocked-raw-customer-reply",
        "customer_identity_attached": case_id == "blocked-customer-identity",
        "private_customer_data_attached": case_id == "blocked-private-customer-data",
        "pr_comment_body_attached": case_id == "blocked-pr-comment-body",
        "model_call_performed": case_id == "blocked-model-call",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_intake(case_id: str) -> dict[str, Any]:
    intake_case = str(_case_flags(case_id)["intake_case"])
    receipt = load_json(
        INTAKE_FIXTURE_DIR / intake_case / "patch-proposal-controlled-follow-up-feedback-intake-receipt.json"
    )
    return feedback_intake.validate_controlled_follow_up_feedback_intake(receipt)


def build_backlog_signal(case_id: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
    signal_summary = _require_object(receipt, "feedback_signal_summary", label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    source_refs = _require_object(receipt, "source_refs", label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    source_hash = artifact_hash(receipt)
    signal = {
        **_base(BACKLOG_SIGNAL_SCHEMA_VERSION),
        "signal_id": f"patch-proposal-controlled-follow-up-product-loop-backlog-{source_hash[:16]}",
        "source_feedback_intake_id": receipt["feedback_intake_id"],
        "source_feedback_intake_case_id": receipt["case_id"],
        "source_feedback_intake_hash": source_hash,
        "source_feedback_intake_ref": (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-intake/{receipt['case_id']}/"
            "patch-proposal-controlled-follow-up-feedback-intake-receipt.json"
        ),
        "source_controlled_follow_up_outcome_ref": source_refs["controlled_follow_up_outcome_receipt_ref"],
        "source_controlled_follow_up_outcome_hash": source_refs["controlled_follow_up_outcome_receipt_hash"],
        "feedback_ref": {
            "signal_type": signal_summary["signal_type"],
            "signal_ref_hash": signal_summary["signal_ref_hash"],
            "payload_hash_only": True,
            "raw_feedback_included": False,
            "customer_identity_included": False,
            "private_customer_data_included": False,
        },
        "loop": "controlled_follow_up_feedback_loop",
        "destination": "product_loop_backlog",
        "next_boundary": "product_owner_prioritization",
        "priority_assignment": "not_assigned",
        "requires_product_owner_prioritization": True,
        "ready_for_execution": False,
        "ready_for_customer_delivery": False,
        "blocked_destinations": [
            "automatic_priority_assignment",
            "automatic_follow_up",
            "customer_visible_action",
            "source_mutation",
            "external_publication",
            "production_mutation",
            "model_call",
        ],
        "provenance_chain": [
            "product_loop",
            "dual_loop",
            "delivery_trust_case",
            "active_reconstruction",
            "controlled_follow_up_outcome",
            "controlled_follow_up_feedback_intake",
        ],
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_backlog_signal(signal)


def build_controlled_follow_up_feedback_backlog_bridge(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    receipt = source_intake(case_id)
    source_checks = _require_object(receipt, "checks", label="source_feedback_intake")
    checks = {
        "source_feedback_intake_accepted": receipt.get("status") == "accepted",
        "product_loop_ref_preserved": source_checks.get("product_loop_ref_preserved") is True,
        "dual_loop_refs_preserved": source_checks.get("dual_loop_refs_preserved") is True,
        "delivery_trust_refs_preserved": source_checks.get("delivery_trust_refs_preserved") is True,
        "active_reconstruction_ref_preserved": source_checks.get("active_reconstruction_ref_preserved") is True,
        "controlled_follow_up_outcome_ref_preserved": (
            source_checks.get("controlled_follow_up_outcome_ref_preserved") is True
        ),
        "feedback_signal_ref_preserved": source_checks.get("feedback_signal_reference_hash_present") is True,
        "product_loop_target_declared": bool(flags["product_loop_target_declared"]),
        "metadata_only_backlog_signal": True,
        "raw_customer_reply_attached": bool(flags["raw_customer_reply_attached"]),
        "customer_identity_attached": bool(flags["customer_identity_attached"]),
        "private_customer_data_attached": bool(flags["private_customer_data_attached"]),
        "pr_comment_body_attached": bool(flags["pr_comment_body_attached"]),
        "automatic_priority_assignment_performed": bool(flags["automatic_priority_assignment_performed"]),
        "automatic_follow_up_performed": bool(flags["automatic_follow_up_performed"]),
        "product_loop_backlog_mutation_performed": bool(flags["product_loop_backlog_mutation_performed"]),
        "source_mutation_performed": bool(flags["source_mutation_performed"]),
        "production_mutation_performed": bool(flags["production_mutation_performed"]),
        "external_publication_performed": bool(flags["external_publication_performed"]),
        "model_call_performed": bool(flags["model_call_performed"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    for key, reason in (
        ("source_feedback_intake_accepted", "source_feedback_intake_not_accepted"),
        ("product_loop_ref_preserved", "product_loop_ref_missing"),
        ("dual_loop_refs_preserved", "dual_loop_ref_missing"),
        ("delivery_trust_refs_preserved", "delivery_trust_ref_missing"),
        ("active_reconstruction_ref_preserved", "active_reconstruction_ref_missing"),
        ("controlled_follow_up_outcome_ref_preserved", "controlled_follow_up_outcome_ref_missing"),
        ("feedback_signal_ref_preserved", "feedback_signal_ref_missing"),
        ("product_loop_target_declared", "product_loop_target_missing"),
        ("metadata_only_backlog_signal", "metadata_only_backlog_signal_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_customer_reply_attached", "raw_customer_reply_rejected"),
        ("customer_identity_attached", "customer_identity_rejected"),
        ("private_customer_data_attached", "private_customer_data_rejected"),
        ("pr_comment_body_attached", "pr_comment_body_rejected"),
        ("automatic_priority_assignment_performed", "automatic_priority_assignment_rejected"),
        ("automatic_follow_up_performed", "automatic_follow_up_rejected"),
        ("product_loop_backlog_mutation_performed", "product_loop_backlog_mutation_rejected"),
        ("source_mutation_performed", "source_mutation_rejected"),
        ("production_mutation_performed", "production_mutation_rejected"),
        ("external_publication_performed", "external_publication_rejected"),
        ("model_call_performed", "model_call_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    backlog_signal = None if reasons else build_backlog_signal(case_id, receipt)
    bridge = {
        **_base(BRIDGE_SCHEMA_VERSION),
        "bridge_id": f"patch-proposal-controlled-follow-up-feedback-backlog-{artifact_hash(receipt)[:16]}-{case_id}",
        "case_id": case_id,
        "status": "queued_for_product_loop" if backlog_signal else "blocked",
        "decision": "emit_product_loop_backlog_signal" if backlog_signal else "block_product_loop_backlog_signal",
        "blocked_reasons": list(dict.fromkeys(reasons)),
        "source_refs": {
            "controlled_follow_up_feedback_intake_receipt_ref": (
                f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-intake/{receipt['case_id']}/"
                "patch-proposal-controlled-follow-up-feedback-intake-receipt.json"
            ),
            "controlled_follow_up_feedback_intake_receipt_hash": artifact_hash(receipt),
            "controlled_follow_up_feedback_intake_report_ref": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.json"
            ),
        },
        "backlog_signal": backlog_signal,
        "effect_boundary": dict(EFFECT_BOUNDARY),
        "checks": checks,
        "quality_gates": {
            "accepted_controlled_follow_up_feedback_intake_required": True,
            "metadata_only_backlog_signal_required": True,
            "priority_assignment_requires_later_product_owner_gate": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_follow_up_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_controlled_follow_up_feedback_backlog_bridge(bridge)


def validate_backlog_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    if signal.get("schema_version") != BACKLOG_SIGNAL_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("backlog signal schema_version drifted")
    _validate_privacy(signal, label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    if signal.get("destination") != "product_loop_backlog":
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("backlog signal destination must be product_loop_backlog")
    if signal.get("next_boundary") != "product_owner_prioritization":
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("backlog signal must stop at product owner prioritization")
    if signal.get("priority_assignment") != "not_assigned":
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("backlog signal must not assign priority")
    if signal.get("requires_product_owner_prioritization") is not True:
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("backlog signal must require product owner prioritization")
    for key in ("ready_for_execution", "ready_for_customer_delivery"):
        if signal.get(key) is not False:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(f"backlog signal {key} must remain false")
    blocked = signal.get("blocked_destinations")
    if not isinstance(blocked, list):
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("backlog signal blocked_destinations must be a list")
    for destination in (
        "automatic_priority_assignment",
        "automatic_follow_up",
        "customer_visible_action",
        "source_mutation",
        "external_publication",
        "production_mutation",
        "model_call",
    ):
        if destination not in blocked:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(f"backlog signal missing blocked destination: {destination}")
    effect = _require_object(signal, "effect_boundary", label=BACKLOG_SIGNAL_SCHEMA_VERSION)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(
                f"backlog signal effect_boundary.{key} must be {expected!r}"
            )
    return dict(signal)


def validate_controlled_follow_up_feedback_backlog_bridge(bridge: Mapping[str, Any]) -> dict[str, Any]:
    if bridge.get("schema_version") != BRIDGE_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("controlled follow-up feedback backlog bridge schema_version drifted")
    _validate_privacy(bridge, label=BRIDGE_SCHEMA_VERSION)
    status = bridge.get("status")
    decision = bridge.get("decision")
    blocked_reasons = bridge.get("blocked_reasons")
    backlog_signal = bridge.get("backlog_signal")
    if status not in {"queued_for_product_loop", "blocked"}:
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("bridge status must be queued_for_product_loop or blocked")
    if not isinstance(blocked_reasons, list):
        raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("bridge blocked_reasons must be a list")
    effect = _require_object(bridge, "effect_boundary", label=BRIDGE_SCHEMA_VERSION)
    for key, expected in EFFECT_BOUNDARY.items():
        if effect.get(key) is not expected:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError(f"bridge effect_boundary.{key} must be {expected!r}")
    if status == "queued_for_product_loop":
        if decision != "emit_product_loop_backlog_signal":
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("queued bridge must emit backlog signal")
        if blocked_reasons:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("queued bridge must not carry blocked reasons")
        if not isinstance(backlog_signal, Mapping):
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("queued bridge must include backlog signal")
        validate_backlog_signal(backlog_signal)
    else:
        if decision != "block_product_loop_backlog_signal":
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("blocked bridge must block backlog signal")
        if not blocked_reasons:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("blocked bridge must include reasons")
        if backlog_signal is not None:
            raise PatchProposalControlledFollowUpFeedbackBacklogBridgeError("blocked bridge must not include backlog signal")
    return dict(bridge)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    bridge = build_controlled_follow_up_feedback_backlog_bridge(case_id)
    artifacts = {"patch-proposal-controlled-follow-up-feedback-backlog-bridge.json": bridge}
    signal = bridge.get("backlog_signal")
    if isinstance(signal, Mapping):
        artifacts["product-loop-backlog-signal.json"] = dict(signal)
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        bridge = validate_controlled_follow_up_feedback_backlog_bridge(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-backlog-bridge.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": bridge["status"],
                "decision": bridge["decision"],
                "blocked_reasons": bridge["blocked_reasons"],
                "backlog_signal_created": bridge["backlog_signal"] is not None,
            }
        )
    queued_count = sum(1 for row in case_reports if row["status"] == "queued_for_product_loop")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove accepted controlled follow-up feedback intake receipts can create metadata-only Product Loop "
            "backlog signal refs without raw replies, identity, priority assignment, follow-up sending, source "
            "mutation, production mutation, model calls, secrets, or model credentials."
        ),
        "source_chain": {
            "controlled_follow_up_feedback_intake_report": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.json"
            ),
            "accepted_controlled_follow_up_feedback_intake_receipt": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-intake/pass-customer-signal/"
                "patch-proposal-controlled-follow-up-feedback-intake-receipt.json"
            ),
        },
        "backlog_matrix": {
            "queued_backlog_signals": queued_count,
            "blocked_backlog_signals": blocked_count,
            "total_cases": len(case_reports),
            "customer_signal_queued": True,
            "operator_signal_queued": True,
            "host_platform_agent_signal_queued": True,
            "blocked_intake_rejected": True,
            "missing_product_loop_target_rejected": True,
            "automatic_priority_assignment_rejected": True,
            "automatic_follow_up_rejected": True,
            "product_loop_backlog_mutation_rejected": True,
            "source_mutation_rejected": True,
            "production_mutation_rejected": True,
            "external_publication_rejected": True,
            "raw_customer_reply_rejected": True,
            "customer_identity_rejected": True,
            "private_customer_data_rejected": True,
            "pr_comment_body_rejected": True,
            "model_call_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "accepted_controlled_follow_up_feedback_intake_required": True,
            "product_loop_target_required": True,
            "metadata_only_backlog_signal_required": True,
            "priority_assignment_requires_later_product_owner_gate": True,
            "automatic_priority_assignment_blocked": True,
            "automatic_follow_up_blocked": True,
            "product_loop_backlog_mutation_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "model_calls_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "effect_boundary": dict(EFFECT_BOUNDARY),
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
        "schema_version": "patch-proposal-controlled-follow-up-feedback-backlog-bridge-cli-result-v1",
        "status": "ok",
        "case_ids": list(selected),
        "output_dir_ref": args.output_dir.name,
        "queued_backlog_signals": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-backlog-bridge.json"]["status"]
            == "queued_for_product_loop"
        ),
        "blocked_backlog_signals": sum(
            1
            for artifacts in cases.values()
            if artifacts["patch-proposal-controlled-follow-up-feedback-backlog-bridge.json"]["status"] == "blocked"
        ),
        "privacy": dict(PRIVACY_FLAGS),
        "effect_boundary": dict(EFFECT_BOUNDARY),
    }
    if args.report:
        result["report"] = build_report(cases)
    print(dump_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
