#!/usr/bin/env python3
"""Build metadata-only Patch Proposal controlled follow-up rehearsal artifacts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import cbb_protocol, dual_loop  # noqa: E402
import patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate as boundary_gate  # noqa: E402


REHEARSAL_SCHEMA_VERSION = "patch-proposal-controlled-follow-up-feedback-rehearsal-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal-v1"

DEFAULT_OUTPUT_DIR = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal"
)
SOURCE_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate"

PASS_CASE_IDS = (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
)
CASE_IDS = (
    *PASS_CASE_IDS,
    "blocked-missing-envelope-refs",
    "blocked-invalid-envelope-refs",
    "blocked-passive-rehearsal",
    "blocked-unsupported-rehearsal-source",
    "blocked-missing-active-reconstruction-ref",
    "blocked-missing-product-loop-ref",
    "blocked-missing-dual-loop-ref",
    "blocked-missing-delivery-trust-ref",
    "blocked-raw-follow-up-preview",
    "blocked-customer-visible-draft",
    "blocked-automatic-customer-send",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
)

ALLOWED_REHEARSAL_SOURCES = {"operator", "host_platform_agent"}
REQUIRED_PRODUCT_LOOP_KINDS = {"product-loop-run"}
REQUIRED_DUAL_LOOP_KINDS = {
    "failure-contract",
    "sandbox-receipt",
    "attention-reconstruction-summary",
    "dual-loop-gate-receipt",
}
REQUIRED_DELIVERY_TRUST_KINDS = {
    "delivery-trust-receipt",
    "customer-handoff-package",
    "delivery-trust-case",
}

PRIVACY_FLAGS = {
    **boundary_gate.PRIVACY_FLAGS,
    "controlled_follow_up_feedback_rehearsal_metadata_only": True,
    "follow_up_feedback_rehearsal_receipt_only": True,
    "follow_up_preview_body_included": False,
    "raw_follow_up_preview_included": False,
    "customer_visible_follow_up_draft_included": False,
    "customer_visible_follow_up_included": False,
    "customer_visible_payload_included": False,
    "raw_customer_payload_included": False,
    "raw_customer_reply_included": False,
}

FORBIDDEN_RAW_FIELDS = {
    *boundary_gate.FORBIDDEN_RAW_FIELDS,
    "raw_follow_up_preview",
    "raw_follow_up_preview_body",
    "follow_up_preview_body",
    "follow_up_preview_text",
    "customer_visible_follow_up_draft",
    "customer_visible_follow_up_body",
    "customer_visible_message",
    "customer_message_body",
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
        "Controlled follow-up envelope refs may be rehearsed locally by an "
        "operator or host-platform Agent as metadata-only review evidence. The "
        "rehearsal does not generate customer-visible text, send messages, "
        "mutate source or production, publish externally, call models, or "
        "replace human accountability."
    ),
    "not_claimed": [
        "raw follow-up body generated",
        "customer-visible draft prepared",
        "customer-visible send performed",
        "source mutation allowed",
        "production mutation allowed",
        "external publication performed",
        "model call performed",
        "customer outcome accepted",
        "truth or security certified",
    ],
}


class PatchProposalControlledFollowUpRehearsalError(ValueError):
    """Raised when controlled follow-up rehearsal artifacts are unsafe."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalControlledFollowUpRehearsalError(f"Expected JSON object: {path}")
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
        raise PatchProposalControlledFollowUpRehearsalError(f"{label}.{key} must be an object")
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
        raise PatchProposalControlledFollowUpRehearsalError(
            f"{label} includes forbidden raw fields: {forbidden}"
        )
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalControlledFollowUpRehearsalError(
                f"{label}.privacy.{key} must be {expected!r}"
            )
    dual_loop.validate_isolation(payload, label=label)


def _case_flags(case_id: str) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise PatchProposalControlledFollowUpRehearsalError(f"Unknown case id: {case_id}")
    source_case = case_id if case_id in PASS_CASE_IDS else "pass-operator-signal"
    rehearsal_source = "host_platform_agent" if case_id == "pass-host-platform-agent-signal" else "operator"
    if case_id == "blocked-unsupported-rehearsal-source":
        rehearsal_source = "customer"
    return {
        "source_case": source_case,
        "source_missing": case_id == "blocked-missing-envelope-refs",
        "source_invalid": case_id == "blocked-invalid-envelope-refs",
        "passive_rehearsal": case_id == "blocked-passive-rehearsal",
        "rehearsal_source": rehearsal_source,
        "missing_active_reconstruction_ref": case_id == "blocked-missing-active-reconstruction-ref",
        "missing_product_loop_ref": case_id == "blocked-missing-product-loop-ref",
        "missing_dual_loop_ref": case_id == "blocked-missing-dual-loop-ref",
        "missing_delivery_trust_ref": case_id == "blocked-missing-delivery-trust-ref",
        "raw_follow_up_preview_requested": case_id == "blocked-raw-follow-up-preview",
        "customer_visible_draft_requested": case_id == "blocked-customer-visible-draft",
        "automatic_customer_send_requested": case_id == "blocked-automatic-customer-send",
        "source_mutation_requested": case_id == "blocked-source-mutation",
        "production_mutation_requested": case_id == "blocked-production-mutation",
        "external_publication_requested": case_id == "blocked-external-publication",
        "model_call_requested": case_id == "blocked-model-call",
        "secret_attached": case_id == "blocked-secret",
        "model_credential_attached": case_id == "blocked-model-credential",
    }


def source_envelope_refs(case_id: str) -> dict[str, Any] | None:
    flags = _case_flags(case_id)
    if flags["source_missing"]:
        return None
    path = SOURCE_FIXTURE_DIR / str(flags["source_case"]) / "patch-proposal-controlled-follow-up-feedback-envelope-refs.json"
    refs = load_json(path)
    if flags["source_invalid"]:
        refs = copy.deepcopy(refs)
        refs["schema_version"] = "invalid-controlled-follow-up-envelope-refs-v1"
        return refs
    return boundary_gate.validate_envelope_refs(refs)


def _source_ref(case_id: str, refs: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if refs is None:
        return None
    source_case = str(_case_flags(case_id)["source_case"])
    return {
        "kind": "patch-proposal-controlled-follow-up-feedback-envelope-refs",
        "path": (
            "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate/"
            f"{source_case}/patch-proposal-controlled-follow-up-feedback-envelope-refs.json"
        ),
        "case_id": source_case,
        "schema_version": str(refs.get("schema_version")),
        "sha256": artifact_hash(refs),
        "raw_body_included": False,
    }


def _source_kinds(refs: Mapping[str, Any] | None) -> tuple[set[str], set[str]]:
    if refs is None:
        return set(), set()
    source_kinds = {
        str(item.get("kind"))
        for item in refs.get("source_evidence_refs", [])
        if isinstance(item, Mapping)
    }
    delivery_kinds = {
        str(item.get("kind"))
        for item in refs.get("delivery_trust_refs", [])
        if isinstance(item, Mapping)
    }
    return source_kinds, delivery_kinds


def build_controlled_follow_up_rehearsal(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    refs = source_envelope_refs(case_id)
    source_error = None
    if flags["source_invalid"]:
        try:
            boundary_gate.validate_envelope_refs(refs or {})
        except Exception as exc:  # noqa: BLE001
            source_error = str(exc)
        else:
            raise PatchProposalControlledFollowUpRehearsalError("invalid source refs unexpectedly passed")

    if flags["missing_active_reconstruction_ref"] and refs:
        refs = copy.deepcopy(refs)
        refs.pop("active_reconstruction_ref", None)
    if flags["missing_product_loop_ref"] and refs:
        refs = copy.deepcopy(refs)
        refs["source_evidence_refs"] = [
            item for item in refs.get("source_evidence_refs", []) if item.get("kind") != "product-loop-run"
        ]
    if flags["missing_dual_loop_ref"] and refs:
        refs = copy.deepcopy(refs)
        refs["source_evidence_refs"] = [
            item for item in refs.get("source_evidence_refs", []) if item.get("kind") != "sandbox-receipt"
        ]
    if flags["missing_delivery_trust_ref"] and refs:
        refs = copy.deepcopy(refs)
        refs["delivery_trust_refs"] = [
            item for item in refs.get("delivery_trust_refs", []) if item.get("kind") != "delivery-trust-case"
        ]

    source_ready = False
    if refs is not None and not flags["source_invalid"]:
        try:
            boundary_gate.validate_envelope_refs(refs)
            source_ready = True
        except Exception as exc:  # noqa: BLE001
            source_error = str(exc)

    source_kinds, delivery_kinds = _source_kinds(refs)
    rehearsal_source = str(flags["rehearsal_source"])
    active_rehearsal = not bool(flags["passive_rehearsal"])
    active_ref_present = isinstance(refs, Mapping) and isinstance(refs.get("active_reconstruction_ref"), Mapping)
    product_loop_ref_present = bool(REQUIRED_PRODUCT_LOOP_KINDS & source_kinds)
    dual_loop_refs_present = REQUIRED_DUAL_LOOP_KINDS <= source_kinds
    delivery_trust_refs_present = REQUIRED_DELIVERY_TRUST_KINDS <= delivery_kinds
    source_supported = rehearsal_source in ALLOWED_REHEARSAL_SOURCES

    checks = {
        "source_envelope_refs_ready": source_ready,
        "source_validation_error": source_error,
        "active_rehearsal_present": active_rehearsal,
        "passive_rehearsal_only": bool(flags["passive_rehearsal"]),
        "rehearsal_source_supported": source_supported,
        "active_reconstruction_ref_present": active_ref_present,
        "product_loop_ref_present": product_loop_ref_present,
        "dual_loop_refs_present": dual_loop_refs_present,
        "delivery_trust_refs_present": delivery_trust_refs_present,
        "metadata_only_rehearsal": True,
        "raw_follow_up_preview_requested": bool(flags["raw_follow_up_preview_requested"]),
        "customer_visible_draft_requested": bool(flags["customer_visible_draft_requested"]),
        "automatic_customer_send_requested": bool(flags["automatic_customer_send_requested"]),
        "source_mutation_requested": bool(flags["source_mutation_requested"]),
        "production_mutation_requested": bool(flags["production_mutation_requested"]),
        "external_publication_requested": bool(flags["external_publication_requested"]),
        "model_call_requested": bool(flags["model_call_requested"]),
        "secret_attached": bool(flags["secret_attached"]),
        "model_credential_attached": bool(flags["model_credential_attached"]),
    }

    reasons: list[str] = []
    for key, reason in (
        ("source_envelope_refs_ready", "source_envelope_refs_not_ready"),
        ("active_rehearsal_present", "active_rehearsal_missing"),
        ("rehearsal_source_supported", "unsupported_rehearsal_source"),
        ("active_reconstruction_ref_present", "active_reconstruction_ref_missing"),
        ("product_loop_ref_present", "product_loop_ref_missing"),
        ("dual_loop_refs_present", "dual_loop_ref_missing"),
        ("delivery_trust_refs_present", "delivery_trust_ref_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("passive_rehearsal_only", "passive_rehearsal_rejected"),
        ("raw_follow_up_preview_requested", "raw_follow_up_preview_rejected"),
        ("customer_visible_draft_requested", "customer_visible_draft_rejected"),
        ("automatic_customer_send_requested", "automatic_customer_send_rejected"),
        ("source_mutation_requested", "source_mutation_rejected"),
        ("production_mutation_requested", "production_mutation_rejected"),
        ("external_publication_requested", "external_publication_rejected"),
        ("model_call_requested", "model_call_rejected"),
        ("secret_attached", "secret_rejected"),
        ("model_credential_attached", "model_credential_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)
    reasons = list(dict.fromkeys(reasons))
    ready = not reasons

    checkpoint_ids = [
        "recipient_scope",
        "claim_boundary",
        "evidence_refs",
        "blocked_effects",
        "no_customer_visible_body",
    ]
    receipt = {
        **_base(REHEARSAL_SCHEMA_VERSION),
        "rehearsal_id": f"patch-proposal-controlled-follow-up-feedback-rehearsal-{case_id}",
        "case_id": case_id,
        "status": "ready" if ready else "blocked",
        "decision": (
            "ready_for_local_follow_up_feedback_rehearsal_review"
            if ready
            else "block_controlled_follow_up_feedback_rehearsal"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "envelope_refs_ref": _source_ref(case_id, refs),
            "boundary_gate_report_ref": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.json"
            ),
        },
        "rehearsal_actor": {
            "source": rehearsal_source,
            "mode": "active_boundary_reconstruction" if active_rehearsal else "passive_attention_only",
            "passive_attention_only": not active_rehearsal,
            "strong_evidence": ready,
            "checkpoint_ids": checkpoint_ids,
            "active_checkpoint_count": len(checkpoint_ids) if active_rehearsal else 0,
            "attention_streams_included": False,
        },
        "rehearsal_summary": {
            "package_type": "metadata_only_patch_proposal_controlled_follow_up_feedback_rehearsal",
            "purpose": "preview_follow_up_boundary_without_customer_payload" if ready else None,
            "allowed_next_step": [
                "operator_or_host_platform_agent_reviews_metadata_only_follow_up_boundary",
                "customer_visible_authoring_must_happen_outside_study_anything",
            ]
            if ready
            else [],
            "withheld_material": [
                "raw_follow_up_body",
                "customer_visible_draft",
                "customer_send_payload",
                "source_mutation_payload",
                "production_payload",
                "external_publication_payload",
                "model_call_payload",
                "secrets",
                "model_credentials",
            ],
        },
        "effect_boundary": {
            "follow_up_feedback_rehearsal_receipt_written": True,
            "follow_up_preview_body_included": False,
            "customer_visible_draft_included": False,
            "automatic_customer_send_performed": False,
            "source_mutation_performed": False,
            "production_mutation_performed": False,
            "external_publication_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
        },
        "checks": checks,
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }
    return validate_controlled_follow_up_rehearsal(receipt)


def validate_controlled_follow_up_rehearsal(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != REHEARSAL_SCHEMA_VERSION:
        raise PatchProposalControlledFollowUpRehearsalError("controlled follow-up rehearsal schema_version drifted")
    _validate_privacy(receipt, label=REHEARSAL_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "rehearsal_summary", label=REHEARSAL_SCHEMA_VERSION)
    actor = _require_object(receipt, "rehearsal_actor", label=REHEARSAL_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=REHEARSAL_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=REHEARSAL_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_patch_proposal_controlled_follow_up_feedback_rehearsal":
        raise PatchProposalControlledFollowUpRehearsalError("rehearsal package_type must remain metadata-only")
    for key in (
        "follow_up_preview_body_included",
        "customer_visible_draft_included",
        "automatic_customer_send_performed",
        "source_mutation_performed",
        "production_mutation_performed",
        "external_publication_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalControlledFollowUpRehearsalError(f"effect_boundary.{key} must remain false")
    if actor.get("source") not in ALLOWED_REHEARSAL_SOURCES and status == "ready":
        raise PatchProposalControlledFollowUpRehearsalError("ready rehearsal requires operator or host-platform Agent source")
    if status == "ready":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalControlledFollowUpRehearsalError("ready rehearsal must not carry blocked reasons")
        if actor.get("mode") != "active_boundary_reconstruction":
            raise PatchProposalControlledFollowUpRehearsalError("ready rehearsal must be active boundary reconstruction")
        if actor.get("passive_attention_only") is not False:
            raise PatchProposalControlledFollowUpRehearsalError("ready rehearsal must reject passive-only attention")
        for key in (
            "source_envelope_refs_ready",
            "active_rehearsal_present",
            "rehearsal_source_supported",
            "active_reconstruction_ref_present",
            "product_loop_ref_present",
            "dual_loop_refs_present",
            "delivery_trust_refs_present",
            "metadata_only_rehearsal",
        ):
            if checks.get(key) is not True:
                raise PatchProposalControlledFollowUpRehearsalError(f"ready rehearsal missing check: {key}")
        for key in (
            "passive_rehearsal_only",
            "raw_follow_up_preview_requested",
            "customer_visible_draft_requested",
            "automatic_customer_send_requested",
            "source_mutation_requested",
            "production_mutation_requested",
            "external_publication_requested",
            "model_call_requested",
            "secret_attached",
            "model_credential_attached",
        ):
            if checks.get(key) is not False:
                raise PatchProposalControlledFollowUpRehearsalError(f"ready rehearsal checks.{key} must remain false")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalControlledFollowUpRehearsalError("blocked rehearsal must carry reasons")
        if summary.get("purpose") is not None:
            raise PatchProposalControlledFollowUpRehearsalError("blocked rehearsal must not expose purpose")
    else:
        raise PatchProposalControlledFollowUpRehearsalError("rehearsal status must be ready or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {
        "patch-proposal-controlled-follow-up-feedback-rehearsal-receipt.json": build_controlled_follow_up_rehearsal(
            case_id
        )
    }


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_controlled_follow_up_rehearsal(
            cases[case_id]["patch-proposal-controlled-follow-up-feedback-rehearsal-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "rehearsal_source": receipt["rehearsal_actor"]["source"],
                "rehearsal_purpose": receipt["rehearsal_summary"]["purpose"],
            }
        )
    ready_count = sum(1 for row in case_reports if row["status"] == "ready")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove controlled follow-up envelope refs can be rehearsed locally as "
            "metadata-only operator or host-platform Agent review evidence without "
            "customer-visible text, sends, mutations, publication, model calls, or secrets."
        ),
        "source_chain": {
            "boundary_gate_report": (
                "platform/generated/"
                "study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.json"
            ),
            "ready_envelope_refs": [
                (
                    "fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate/"
                    f"{case_id}/patch-proposal-controlled-follow-up-feedback-envelope-refs.json"
                )
                for case_id in PASS_CASE_IDS
            ],
        },
        "rehearsal_matrix": {
            "ready_rehearsals": ready_count,
            "blocked_rehearsals": blocked_count,
            "total_cases": len(case_reports),
            "missing_or_invalid_source_rejected": True,
            "passive_rehearsal_rejected": True,
            "unsupported_rehearsal_source_rejected": True,
            "missing_active_reconstruction_ref_rejected": True,
            "missing_product_loop_ref_rejected": True,
            "missing_dual_loop_ref_rejected": True,
            "missing_delivery_trust_ref_rejected": True,
            "raw_follow_up_preview_rejected": True,
            "customer_visible_draft_rejected": True,
            "automatic_customer_send_rejected": True,
            "source_and_production_mutation_rejected": True,
            "external_publication_rejected": True,
            "model_call_rejected": True,
            "secret_and_model_credential_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "controlled_envelope_refs_required": True,
            "operator_or_host_platform_agent_rehearsal_required": True,
            "active_reconstruction_required": True,
            "passive_attention_only_rejected": True,
            "product_loop_refs_required": True,
            "dual_loop_refs_required": True,
            "delivery_trust_case_refs_required": True,
            "follow_up_preview_body_rejected": True,
            "customer_visible_drafts_rejected": True,
            "automatic_customer_send_blocked": True,
            "source_mutation_blocked": True,
            "production_mutation_blocked": True,
            "external_publication_blocked": True,
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
