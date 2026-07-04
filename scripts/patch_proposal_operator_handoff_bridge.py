#!/usr/bin/env python3
"""Build metadata-only Patch Proposal Operator Handoff Bridge artifacts."""

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
import sandboxed_patch_proposal_rehearsal as patch_rehearsal  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-operator-handoff-bridge-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-operator-handoff-bridge-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-operator-handoff-bridge"
UPSTREAM_FIXTURE_DIR = ROOT / "fixtures" / "sandboxed-patch-proposal-rehearsal"

CASE_IDS = (
    "pass",
    "blocked-sandboxed-proposal-blocked",
    "blocked-missing-operator-confirmation",
    "blocked-raw-patch-request",
    "blocked-repository-mutation",
    "blocked-customer-visible-action",
    "blocked-external-publication",
    "blocked-production-mutation",
)

DELIVERY_CLASS_REPORTS = {
    "code_review_handoff": ROOT / "platform" / "generated" / "study-anything-code-review-operator-handoff-rehearsal.json",
    "client_report_handoff": ROOT / "platform" / "generated" / "study-anything-client-report-operator-handoff-rehearsal.json",
    "support_response_handoff": ROOT / "platform" / "generated" / "study-anything-support-response-operator-handoff-rehearsal.json",
}

PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "raw_spec_eval_body_included": False,
    "raw_eval_prompt_included": False,
    "raw_patch_body_included": False,
    "raw_diff_body_included": False,
    "raw_customer_payload_included": False,
    "raw_operator_notes_included": False,
    "repository_secrets_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}

ISOLATION = dict(dual_loop.ISOLATION_BOUNDARY)
FORBIDDEN_RAW_FIELDS = {
    "raw_patch_body",
    "raw_diff_body",
    "raw_diff",
    "patch_body",
    "diff_body",
    "raw_source_text",
    "raw_customer_payload",
    "raw_operator_notes",
}


class PatchProposalOperatorHandoffBridgeError(ValueError):
    """Raised when bridge artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalOperatorHandoffBridgeError(f"Expected JSON object: {path}")
    return payload


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dump_json(payload))


def file_hash(path: Path) -> str:
    return dual_loop.sha256_text(path.read_text(encoding="utf-8"))


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
        raise PatchProposalOperatorHandoffBridgeError(f"{label}.{key} must be an object")
    return value


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.assert_metadata_only(payload, label=label)
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalOperatorHandoffBridgeError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalOperatorHandoffBridgeError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str]:
    if case_id not in CASE_IDS:
        raise PatchProposalOperatorHandoffBridgeError(f"Unknown case id: {case_id}")
    return {
        "upstream_case": "blocked-missing-test-plan" if case_id == "blocked-sandboxed-proposal-blocked" else "pass",
        "operator_confirmations_present": case_id != "blocked-missing-operator-confirmation",
        "raw_patch_or_diff_requested": case_id == "blocked-raw-patch-request",
        "repository_mutation_requested": case_id == "blocked-repository-mutation",
        "customer_visible_action_requested": case_id == "blocked-customer-visible-action",
        "external_publication_requested": case_id == "blocked-external-publication",
        "production_mutation_requested": case_id == "blocked-production-mutation",
    }


def upstream_patch_envelope(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    upstream_case = str(flags["upstream_case"])
    envelope = load_json(UPSTREAM_FIXTURE_DIR / upstream_case / "sandboxed-patch-proposal-envelope.json")
    return patch_rehearsal.validate_patch_proposal_envelope(envelope)


def delivery_class_refs() -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for delivery_class, path in DELIVERY_CLASS_REPORTS.items():
        report = load_json(path)
        rehearsal = report.get("rehearsal")
        refs.append(
            {
                "delivery_class": delivery_class,
                "report_ref": path.relative_to(ROOT).as_posix(),
                "report_hash": file_hash(path),
                "schema_version": report.get("schema_version"),
                "status": report.get("status"),
                "ready_count": rehearsal.get("ready_count") if isinstance(rehearsal, Mapping) else None,
                "raw_payload_included": False,
            }
        )
    return refs


def operator_confirmations(present: bool) -> dict[str, bool]:
    return {
        "sandboxed_patch_boundary_understood": present,
        "raw_patch_body_absent_understood": present,
        "operator_must_apply_outside_system_if_approved": present,
        "no_repository_mutation_inside_bridge": present,
        "no_customer_visible_action_inside_bridge": present,
        "no_external_publication_inside_bridge": present,
        "no_production_mutation_inside_bridge": present,
        "rollback_and_test_refs_visible": present,
    }


def build_bridge_receipt(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    envelope = upstream_patch_envelope(case_id)
    confirmations = operator_confirmations(bool(flags["operator_confirmations_present"]))
    checks = {
        "sandboxed_patch_proposal_allowed": envelope.get("status") == "allowed",
        "sandbox_local_refs_only": envelope.get("patch_boundary", {}).get("proposal_scope") == "sandbox_local_refs_only",
        "operator_active_confirmations_present": all(confirmations.values()),
        "delivery_class_refs_metadata_only": True,
        "rollback_plan_ref_present": bool(envelope.get("rollback_plan", {}).get("present")),
        "test_plan_ref_present": bool(envelope.get("test_plan", {}).get("present")),
        "raw_patch_body_requested": bool(flags["raw_patch_or_diff_requested"]),
        "raw_diff_body_requested": bool(flags["raw_patch_or_diff_requested"]),
        "repository_mutation_requested": bool(flags["repository_mutation_requested"]),
        "customer_visible_action_requested": bool(flags["customer_visible_action_requested"]),
        "external_publication_requested": bool(flags["external_publication_requested"]),
        "production_mutation_requested": bool(flags["production_mutation_requested"]),
    }
    reasons: list[str] = []
    if not checks["sandboxed_patch_proposal_allowed"]:
        reasons.append("sandboxed_patch_proposal_not_allowed")
    if not checks["sandbox_local_refs_only"]:
        reasons.append("sandbox_local_scope_missing")
    if not checks["operator_active_confirmations_present"]:
        reasons.append("operator_active_reconstruction_missing")
    if not checks["rollback_plan_ref_present"]:
        reasons.append("rollback_plan_ref_missing")
    if not checks["test_plan_ref_present"]:
        reasons.append("test_plan_ref_missing")
    if checks["raw_patch_body_requested"] or checks["raw_diff_body_requested"]:
        reasons.append("raw_patch_or_diff_request_rejected")
    if checks["repository_mutation_requested"]:
        reasons.append("repository_mutation_rejected")
    if checks["customer_visible_action_requested"]:
        reasons.append("customer_visible_action_rejected")
    if checks["external_publication_requested"]:
        reasons.append("external_publication_rejected")
    if checks["production_mutation_requested"]:
        reasons.append("production_mutation_rejected")
    allowed = not reasons
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "receipt_id": f"patch-proposal-operator-handoff-bridge-{case_id}",
        "case_id": case_id,
        "status": "ready" if allowed else "blocked",
        "decision": "prepare_operator_handoff_bridge" if allowed else "block_operator_handoff_bridge",
        "blocked_reasons": reasons,
        "source_refs": {
            "sandboxed_patch_proposal_envelope_ref": (
                f"fixtures/sandboxed-patch-proposal-rehearsal/{flags['upstream_case']}/"
                "sandboxed-patch-proposal-envelope.json"
            ),
            "sandboxed_patch_proposal_envelope_hash": artifact_hash(envelope),
            "sandboxed_patch_rehearsal_report_ref": "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.json",
        },
        "operator_confirmations": confirmations,
        "handoff_bridge": {
            "mode": "metadata_refs_only",
            "next_allowed_action": "prepare_operator_handoff_in_host_agent" if allowed else None,
            "delivery_class_refs": delivery_class_refs(),
            "patch_plan_ref_hash": envelope.get("proposal_refs", {}).get("patch_plan_ref_hash"),
            "changed_component_refs": envelope.get("proposal_refs", {}).get("changed_component_refs", []),
            "not_allowed_actions": [
                "apply_patch",
                "write_repository_files",
                "git_commit",
                "open_pr",
                "post_pr_comment",
                "send_customer_message",
                "publish_externally",
                "deploy_to_production",
            ],
        },
        "effect_boundary": {
            "patch_body_included": False,
            "diff_body_included": False,
            "implementation_execution_performed": False,
            "repository_mutation_performed": False,
            "automatic_pr_commenting_performed": False,
            "customer_visible_action_performed": False,
            "external_publication_performed": False,
            "production_mutation_performed": False,
            "irreversible_effects_performed": False,
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": "A sandbox-local patch proposal envelope can be handed to an operator only as metadata refs after active reconstruction of the boundary.",
            "not_claimed": [
                "patch content generated",
                "repository mutation performed",
                "PR comment or PR opened",
                "customer-visible delivery approved",
                "external publication approved",
                "production mutation approved",
                "truth or security certification",
            ],
        },
    }
    return validate_bridge_receipt(receipt)


def validate_bridge_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_privacy(payload, label=RECEIPT_SCHEMA_VERSION)
    forbidden_present = sorted(field for field in FORBIDDEN_RAW_FIELDS if field in payload)
    if forbidden_present:
        raise PatchProposalOperatorHandoffBridgeError(f"bridge receipt includes forbidden raw fields: {forbidden_present}")
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalOperatorHandoffBridgeError("invalid bridge receipt schema_version")
    if payload.get("status") not in ("ready", "blocked"):
        raise PatchProposalOperatorHandoffBridgeError("invalid bridge receipt status")
    bridge = _require_object(payload, "handoff_bridge", label="bridge_receipt")
    if bridge.get("mode") != "metadata_refs_only":
        raise PatchProposalOperatorHandoffBridgeError("bridge mode must remain metadata_refs_only")
    if not isinstance(bridge.get("delivery_class_refs"), list) or len(bridge["delivery_class_refs"]) != len(DELIVERY_CLASS_REPORTS):
        raise PatchProposalOperatorHandoffBridgeError("bridge must include delivery class metadata refs")
    effects = _require_object(payload, "effect_boundary", label="bridge_receipt")
    for key, value in effects.items():
        if value is not False:
            raise PatchProposalOperatorHandoffBridgeError(f"bridge effect boundary must keep {key} false")
    checks = _require_object(payload, "checks", label="bridge_receipt")
    if payload.get("status") == "ready":
        required_true = (
            "sandboxed_patch_proposal_allowed",
            "sandbox_local_refs_only",
            "operator_active_confirmations_present",
            "delivery_class_refs_metadata_only",
            "rollback_plan_ref_present",
            "test_plan_ref_present",
        )
        for key in required_true:
            if checks.get(key) is not True:
                raise PatchProposalOperatorHandoffBridgeError(f"ready bridge requires {key}")
        if bridge.get("next_allowed_action") != "prepare_operator_handoff_in_host_agent":
            raise PatchProposalOperatorHandoffBridgeError("ready bridge must only prepare host-agent operator handoff")
    blocking_requests = (
        "raw_patch_body_requested",
        "raw_diff_body_requested",
        "repository_mutation_requested",
        "customer_visible_action_requested",
        "external_publication_requested",
        "production_mutation_requested",
    )
    for key in blocking_requests:
        if checks.get(key) is True and payload.get("status") != "blocked":
            raise PatchProposalOperatorHandoffBridgeError(f"{key} must block bridge handoff")
    return dict(payload)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-operator-handoff-bridge-receipt.json": build_bridge_receipt(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_bridge_receipt(cases[case_id]["patch-proposal-operator-handoff-bridge-receipt.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "next_allowed_action": receipt["handoff_bridge"]["next_allowed_action"],
            }
        )
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": "Bridge a sandbox-local patch proposal envelope to operator handoff metadata refs without applying code, opening PRs, commenting, sending customer-visible output, publishing externally, or mutating production.",
        "source_chain": {
            "sandboxed_patch_proposal_rehearsal_report": "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.json",
            "allowed_sandboxed_patch_proposal_envelope": "fixtures/sandboxed-patch-proposal-rehearsal/pass/sandboxed-patch-proposal-envelope.json",
            "delivery_class_operator_handoff_reports": [
                path.relative_to(ROOT).as_posix() for path in DELIVERY_CLASS_REPORTS.values()
            ],
        },
        "case_reports": case_reports,
        "claim_boundary": {
            "current_claim": "A ready bridge only packages metadata refs so a host platform operator can decide whether to continue; it does not execute, apply, publish, or send anything.",
            "not_claimed": [
                "patch content generated",
                "repository changed",
                "PR opened or commented",
                "customer handoff approved",
                "external publication approved",
                "production change approved",
                "truth or security certified",
            ],
        },
        "quality_gates": {
            "sandboxed_patch_proposal_allowed_required": True,
            "operator_active_reconstruction_required": True,
            "delivery_class_refs_metadata_only": True,
            "raw_patch_or_diff_request_rejected": True,
            "repository_mutation_rejected": True,
            "customer_visible_action_rejected": True,
            "external_publication_rejected": True,
            "production_mutation_rejected": True,
        },
    }
    _validate_privacy(report, label=REPORT_SCHEMA_VERSION)
    return report


def write_artifact_set(output_dir: Path, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    for name, payload in artifacts.items():
        write_json(output_dir / name, payload)


def run_cli(case: str, output_dir: Path) -> dict[str, Any]:
    selected = CASE_IDS if case == "all" else (case,)
    cases = {}
    for case_id in selected:
        artifacts = build_case_artifacts(case_id)
        write_artifact_set(output_dir / case_id, artifacts)
        cases[case_id] = artifacts
    report = build_report(cases if case == "all" else build_all_case_artifacts())
    write_json(output_dir / "patch-proposal-operator-handoff-bridge-report.json", report)
    return {
        "schema_version": "patch-proposal-operator-handoff-bridge-cli-v1",
        "status": "ok",
        "case_ids": list(selected),
        "output_dir_ref": "configured-output-dir",
        "report": "patch-proposal-operator-handoff-bridge-report.json",
        "privacy": dict(PRIVACY_FLAGS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", *CASE_IDS), default="all")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    result = run_cli(args.case, Path(args.output_dir))
    print(dump_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
