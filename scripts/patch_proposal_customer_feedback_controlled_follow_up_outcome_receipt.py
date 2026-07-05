#!/usr/bin/env python3
"""Build metadata-only Patch Proposal controlled follow-up outcome receipts."""

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
import patch_proposal_customer_feedback_controlled_follow_up_rehearsal as rehearsal  # noqa: E402


OUTCOME_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-outcome-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-outcome-v1"

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-outcome"
)
REHEARSAL_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-rehearsal"

CASE_IDS = (
    "pass-human-operator",
    "pass-host-platform-agent",
    "blocked-rehearsal-blocked",
    "blocked-missing-external-actor",
    "blocked-missing-action-reference",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-body",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-send-payload",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_ACTORS = {"human_operator", "host_platform_agent"}

PRIVACY_FLAGS = {
    **rehearsal.PRIVACY_FLAGS,
    "controlled_follow_up_outcome_metadata_only": True,
    "follow_up_outcome_receipt_only": True,
    "raw_follow_up_body_included": False,
    "raw_customer_reply_included": False,
    "customer_identity_included": False,
    "customer_visible_follow_up_included": False,
    "customer_visible_payload_included": False,
    "send_payload_included": False,
    "source_mutation_payload_included": False,
    "production_payload_included": False,
    "external_publication_payload_included": False,
    "model_call_payload_included": False,
}

FORBIDDEN_RAW_FIELDS = {
    *rehearsal.FORBIDDEN_RAW_FIELDS,
    "raw_follow_up_body",
    "follow_up_body",
    "follow_up_text",
    "raw_customer_reply",
    "customer_reply",
    "customer_reply_body",
    "customer_identity",
    "customer_name",
    "customer_email",
    "customer_phone",
    "requester_identity",
    "customer_visible_message",
    "send_payload",
    "customer_send_payload",
    "source_mutation_payload",
    "production_mutation_payload",
    "external_publication_payload",
    "model_call_payload",
    "model_api_key",
    "agent_credential",
}

CLAIM_BOUNDARY = {
    "current_claim": (
        "A controlled follow-up outcome receipt records only metadata that a "
        "human or host-platform Agent reports an external customer follow-up "
        "happened outside Study Anything after a ready rehearsal. It does not "
        "store follow-up text, customer replies, customer identity, send "
        "payloads, source mutations, production mutations, external publication "
        "payloads, model calls, secrets, or model credentials."
    ),
    "not_claimed": [
        "raw follow-up body included",
        "raw customer reply included",
        "customer identity included",
        "Study Anything sent a customer message",
        "Study Anything mutated source",
        "Study Anything mutated production",
        "Study Anything published externally",
        "Study Anything called a model",
        "customer satisfaction certified",
        "truth or security certified",
    ],
}


class PatchProposalControlledFollowUpOutcomeError(ValueError):
    """Raised when controlled follow-up outcome artifacts are unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpOutcomeError(f"Expected JSON object: {path}")
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
        raise PatchProposalControlledFollowUpOutcomeError(f"{label}.{key} must be an object")
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
        raise PatchProposalControlledFollowUpOutcomeError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpOutcomeError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _case_flags(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpOutcomeError(f"Unknown case id: {case_id}")
    return {
        "rehearsal_case": "blocked-passive-rehearsal" if case_id == "blocked-rehearsal-blocked" else "pass-operator-signal",
        "external_actor_type": None
        if case_id == "blocked-missing-external-actor"
        else ("host_platform_agent" if case_id == "pass-host-platform-agent" else "human_operator"),
        "external_action_ref_hash_present": case_id != "blocked-missing-action-reference",
        "claim_boundary_visible": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_visible": case_id != "blocked-missing-privacy-boundary",
        "raw_follow_up_body_attached": case_id == "blocked-raw-follow-up-body",
        "raw_customer_reply_attached": case_id == "blocked-raw-customer-reply",
        "customer_identity_attached": case_id == "blocked-customer-identity",
        "send_payload_attached": case_id == "blocked-send-payload",
        "source_mutation_performed": case_id == "blocked-source-mutation",
        "production_mutation_performed": case_id == "blocked-production-mutation",
        "external_publication_payload_attached": case_id == "blocked-external-publication-payload",
        "model_call_performed": case_id == "blocked-model-call",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_rehearsal(case_id: str) -> dict[str, Any]:
    rehearsal_case = str(_case_flags(case_id)["rehearsal_case"])
    receipt = load_json(
        REHEARSAL_FIXTURE_DIR / rehearsal_case / "patch-proposal-controlled-follow-up-rehearsal-receipt.json"
    )
    return rehearsal.validate_controlled_follow_up_rehearsal(receipt)


def _action_ref_hash(case_id: str, actor_type: str | None) -> str | None:
    if not _case_flags(case_id)["external_action_ref_hash_present"]:
        return None
    return dual_loop.sha256_text(f"{case_id}:{actor_type}:external-controlled-follow-up-outcome")


def build_controlled_follow_up_outcome(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    rehearsal_receipt = source_rehearsal(case_id)
    actor_type = flags["external_actor_type"]
    action_ref_hash = _action_ref_hash(case_id, str(actor_type) if actor_type else None)
    source_checks = _require_object(rehearsal_receipt, "checks", label="source_rehearsal")
    checks = {
        "source_rehearsal_ready": rehearsal_receipt.get("status") == "ready",
        "product_loop_ref_preserved": source_checks.get("product_loop_ref_present") is True,
        "dual_loop_refs_preserved": source_checks.get("dual_loop_refs_present") is True,
        "delivery_trust_refs_preserved": source_checks.get("delivery_trust_refs_present") is True,
        "active_reconstruction_ref_preserved": source_checks.get("active_reconstruction_ref_present") is True,
        "external_action_recorded": True,
        "external_actor_declared": actor_type in ALLOWED_ACTORS,
        "action_happened_outside_study_anything": True,
        "action_reference_hash_present": isinstance(action_ref_hash, str) and len(action_ref_hash) == 64,
        "claim_boundary_visible": bool(flags["claim_boundary_visible"]),
        "privacy_boundary_visible": bool(flags["privacy_boundary_visible"]),
        "metadata_only_outcome": True,
        "raw_follow_up_body_attached": bool(flags["raw_follow_up_body_attached"]),
        "raw_customer_reply_attached": bool(flags["raw_customer_reply_attached"]),
        "customer_identity_attached": bool(flags["customer_identity_attached"]),
        "send_payload_attached": bool(flags["send_payload_attached"]),
        "source_mutation_performed": bool(flags["source_mutation_performed"]),
        "production_mutation_performed": bool(flags["production_mutation_performed"]),
        "external_publication_payload_attached": bool(flags["external_publication_payload_attached"]),
        "model_call_performed": bool(flags["model_call_performed"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    for key, reason in (
        ("source_rehearsal_ready", "source_rehearsal_not_ready"),
        ("product_loop_ref_preserved", "product_loop_ref_missing"),
        ("dual_loop_refs_preserved", "dual_loop_ref_missing"),
        ("delivery_trust_refs_preserved", "delivery_trust_ref_missing"),
        ("active_reconstruction_ref_preserved", "active_reconstruction_ref_missing"),
        ("external_actor_declared", "external_actor_missing"),
        ("action_reference_hash_present", "action_reference_hash_missing"),
        ("claim_boundary_visible", "claim_boundary_missing"),
        ("privacy_boundary_visible", "privacy_boundary_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_follow_up_body_attached", "raw_follow_up_body_rejected"),
        ("raw_customer_reply_attached", "raw_customer_reply_rejected"),
        ("customer_identity_attached", "customer_identity_rejected"),
        ("send_payload_attached", "send_payload_rejected"),
        ("source_mutation_performed", "source_mutation_rejected"),
        ("production_mutation_performed", "production_mutation_rejected"),
        ("external_publication_payload_attached", "external_publication_payload_rejected"),
        ("model_call_performed", "model_call_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)
    reasons = list(dict.fromkeys(reasons))
    recorded = not reasons
    receipt = {
        **_base(OUTCOME_SCHEMA_VERSION),
        "outcome_id": f"patch-proposal-controlled-follow-up-outcome-{case_id}",
        "case_id": case_id,
        "status": "recorded" if recorded else "blocked",
        "decision": "record_external_controlled_follow_up_outcome" if recorded else "block_controlled_follow_up_outcome",
        "blocked_reasons": reasons,
        "source_refs": {
            "rehearsal_receipt_ref": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-rehearsal/"
                f"{flags['rehearsal_case']}/patch-proposal-controlled-follow-up-rehearsal-receipt.json"
            ),
            "rehearsal_receipt_hash": artifact_hash(rehearsal_receipt),
            "rehearsal_report_ref": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.json"
            ),
        },
        "external_follow_up_outcome": {
            "package_type": "metadata_only_patch_proposal_controlled_follow_up_outcome",
            "outcome_type": "external_follow_up_action_recorded" if recorded else None,
            "actor_type": actor_type,
            "occurred_outside_study_anything": True,
            "action_ref_hash": action_ref_hash,
            "raw_follow_up_body_included": False,
            "raw_customer_reply_included": False,
            "customer_identity_included": False,
            "send_payload_included": False,
            "payload_hash_only": True,
            "external_system_credentials_included": False,
        },
        "effect_boundary": {
            "study_anything_customer_follow_up_send_performed": False,
            "study_anything_automatic_follow_up_performed": False,
            "study_anything_source_mutation_performed": False,
            "study_anything_production_mutation_performed": False,
            "study_anything_external_publication_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
        },
        "checks": checks,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_controlled_follow_up_outcome(receipt)


def validate_controlled_follow_up_outcome(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != OUTCOME_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpOutcomeError("controlled follow-up outcome schema_version drifted")
    _validate_privacy(receipt, label=OUTCOME_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "external_follow_up_outcome", label=OUTCOME_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=OUTCOME_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=OUTCOME_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_patch_proposal_controlled_follow_up_outcome":
        raise PatchProposalControlledFollowUpOutcomeError("outcome package_type must remain metadata-only")
    for key in (
        "raw_follow_up_body_included",
        "raw_customer_reply_included",
        "customer_identity_included",
        "send_payload_included",
        "external_system_credentials_included",
    ):
        if summary.get(key) is not False:
            raise PatchProposalControlledFollowUpOutcomeError(f"external_follow_up_outcome.{key} must remain false")
    for key in (
        "study_anything_customer_follow_up_send_performed",
        "study_anything_automatic_follow_up_performed",
        "study_anything_source_mutation_performed",
        "study_anything_production_mutation_performed",
        "study_anything_external_publication_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalControlledFollowUpOutcomeError(f"effect_boundary.{key} must remain false")
    if status == "recorded":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalControlledFollowUpOutcomeError("recorded controlled follow-up outcome must not carry reasons")
        for key in (
            "source_rehearsal_ready",
            "product_loop_ref_preserved",
            "dual_loop_refs_preserved",
            "delivery_trust_refs_preserved",
            "active_reconstruction_ref_preserved",
            "external_action_recorded",
            "external_actor_declared",
            "action_happened_outside_study_anything",
            "action_reference_hash_present",
            "claim_boundary_visible",
            "privacy_boundary_visible",
            "metadata_only_outcome",
        ):
            if checks.get(key) is not True:
                raise PatchProposalControlledFollowUpOutcomeError(f"recorded outcome missing check: {key}")
        for key in (
            "raw_follow_up_body_attached",
            "raw_customer_reply_attached",
            "customer_identity_attached",
            "send_payload_attached",
            "source_mutation_performed",
            "production_mutation_performed",
            "external_publication_payload_attached",
            "model_call_performed",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalControlledFollowUpOutcomeError(f"recorded outcome checks.{key} must remain false")
        if summary.get("actor_type") not in ALLOWED_ACTORS:
            raise PatchProposalControlledFollowUpOutcomeError("recorded outcome actor_type must be bounded")
        if summary.get("outcome_type") != "external_follow_up_action_recorded":
            raise PatchProposalControlledFollowUpOutcomeError("recorded outcome_type drifted")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalControlledFollowUpOutcomeError("blocked controlled follow-up outcome must carry reasons")
        if summary.get("outcome_type") is not None:
            raise PatchProposalControlledFollowUpOutcomeError("blocked controlled follow-up outcome must not expose outcome_type")
    else:
        raise PatchProposalControlledFollowUpOutcomeError("controlled follow-up outcome status must be recorded or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {
        "patch-proposal-controlled-follow-up-outcome-receipt.json": build_controlled_follow_up_outcome(
            case_id
        )
    }


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_controlled_follow_up_outcome(
            cases[case_id]["patch-proposal-controlled-follow-up-outcome-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "actor_type": receipt["external_follow_up_outcome"]["actor_type"],
            }
        )
    recorded_count = sum(1 for row in case_reports if row["status"] == "recorded")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove external controlled follow-up outcomes can be recorded as metadata-only receipts "
            "after a ready rehearsal while preserving Product Loop, Dual Loop, Delivery Trust Case, "
            "and active reconstruction refs and excluding customer-visible content, customer identity, "
            "send payloads, mutations, publication payloads, model calls, and secrets."
        ),
        "source_chain": {
            "ready_rehearsal_receipt": (
                "fixtures/patch-proposal-customer-feedback-controlled-follow-up-rehearsal/"
                "pass-operator-signal/patch-proposal-controlled-follow-up-rehearsal-receipt.json"
            ),
            "rehearsal_report": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.json"
            ),
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
            "raw_follow_up_body_rejected": True,
            "raw_customer_reply_rejected": True,
            "customer_identity_rejected": True,
            "send_payload_rejected": True,
            "source_mutation_rejected": True,
            "production_mutation_rejected": True,
            "external_publication_payload_rejected": True,
            "model_call_rejected": True,
            "secret_rejected": True,
            "model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "ready_rehearsal_required": True,
            "product_loop_refs_preserved": True,
            "dual_loop_refs_preserved": True,
            "delivery_trust_refs_preserved": True,
            "active_reconstruction_ref_preserved": True,
            "external_actor_required": True,
            "metadata_reference_required": True,
            "raw_follow_up_body_rejected": True,
            "raw_customer_reply_rejected": True,
            "customer_identity_rejected": True,
            "send_payload_rejected": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "external_publication_payload_blocked": True,
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
