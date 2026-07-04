#!/usr/bin/env python3
"""Build metadata-only Patch Proposal External Work Order Pack artifacts."""

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
import patch_proposal_acceptance_drill as acceptance  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-external-work-order-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-external-work-order-pack-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-external-work-order-pack"
ACCEPTANCE_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-acceptance-drill"

CASE_IDS = (
    "pass",
    "blocked-acceptance-blocked",
    "blocked-missing-work-order-purpose",
    "blocked-raw-patch-request",
    "blocked-apply-patch-request",
    "blocked-open-pr-request",
    "blocked-pr-comment-request",
    "blocked-customer-visible-action",
    "blocked-external-publication",
    "blocked-production-mutation",
)

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
    "raw_work_order_body",
}


class PatchProposalExternalWorkOrderPackError(ValueError):
    """Raised when external work-order pack artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalExternalWorkOrderPackError(f"Expected JSON object: {path}")
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
        raise PatchProposalExternalWorkOrderPackError(f"{label}.{key} must be an object")
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
        raise PatchProposalExternalWorkOrderPackError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalExternalWorkOrderPackError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalExternalWorkOrderPackError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str]:
    if case_id not in CASE_IDS:
        raise PatchProposalExternalWorkOrderPackError(f"Unknown case id: {case_id}")
    return {
        "acceptance_case": "blocked-open-pr-request" if case_id == "blocked-acceptance-blocked" else "pass",
        "work_order_purpose_present": case_id != "blocked-missing-work-order-purpose",
        "raw_patch_requested": case_id == "blocked-raw-patch-request",
        "apply_patch_requested": case_id == "blocked-apply-patch-request",
        "open_pr_requested": case_id == "blocked-open-pr-request",
        "pr_comment_requested": case_id == "blocked-pr-comment-request",
        "customer_visible_action_requested": case_id == "blocked-customer-visible-action",
        "external_publication_requested": case_id == "blocked-external-publication",
        "production_mutation_requested": case_id == "blocked-production-mutation",
    }


def source_acceptance_receipt(case_id: str) -> dict[str, Any]:
    acceptance_case = str(_case_flags(case_id)["acceptance_case"])
    receipt = load_json(ACCEPTANCE_FIXTURE_DIR / acceptance_case / "patch-proposal-acceptance-drill-receipt.json")
    return acceptance.validate_acceptance_receipt(receipt)


def operator_work_order_reconstruction(present: bool) -> dict[str, bool]:
    return {
        "work_order_is_metadata_only": present,
        "host_operator_controls_execution": present,
        "raw_patch_and_diff_are_absent": present,
        "study_anything_does_not_apply_changes": present,
        "study_anything_does_not_open_or_comment_on_prs": present,
        "customer_visible_output_requires_separate_control": present,
        "production_mutation_requires_separate_control": present,
    }


def build_work_order_receipt(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    acceptance_receipt = source_acceptance_receipt(case_id)
    reconstruction = operator_work_order_reconstruction(bool(flags["work_order_purpose_present"]))
    checks = {
        "acceptance_allowed": acceptance_receipt.get("status") == "allowed",
        "work_order_purpose_present": bool(flags["work_order_purpose_present"]),
        "operator_reconstruction_present": all(reconstruction.values()),
        "metadata_only_work_order": True,
        "raw_patch_requested": bool(flags["raw_patch_requested"]),
        "raw_diff_requested": bool(flags["raw_patch_requested"]),
        "apply_patch_requested": bool(flags["apply_patch_requested"]),
        "open_pr_requested": bool(flags["open_pr_requested"]),
        "pr_comment_requested": bool(flags["pr_comment_requested"]),
        "customer_visible_action_requested": bool(flags["customer_visible_action_requested"]),
        "external_publication_requested": bool(flags["external_publication_requested"]),
        "production_mutation_requested": bool(flags["production_mutation_requested"]),
    }
    reasons: list[str] = []
    if not checks["acceptance_allowed"]:
        reasons.append("acceptance_not_allowed")
    if not checks["work_order_purpose_present"]:
        reasons.append("work_order_purpose_missing")
    if not checks["operator_reconstruction_present"]:
        reasons.append("operator_reconstruction_missing")
    if checks["raw_patch_requested"] or checks["raw_diff_requested"]:
        reasons.append("raw_patch_or_diff_request_rejected")
    if checks["apply_patch_requested"]:
        reasons.append("apply_patch_request_rejected")
    if checks["open_pr_requested"]:
        reasons.append("open_pr_request_rejected")
    if checks["pr_comment_requested"]:
        reasons.append("pr_comment_request_rejected")
    if checks["customer_visible_action_requested"]:
        reasons.append("customer_visible_action_rejected")
    if checks["external_publication_requested"]:
        reasons.append("external_publication_rejected")
    if checks["production_mutation_requested"]:
        reasons.append("production_mutation_rejected")

    allowed = not reasons
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "receipt_id": f"patch-proposal-external-work-order-pack-{case_id}",
        "case_id": case_id,
        "status": "ready" if allowed else "blocked",
        "decision": "emit_external_operator_work_order_pack" if allowed else "block_external_operator_work_order_pack",
        "blocked_reasons": reasons,
        "source_refs": {
            "acceptance_receipt_ref": (
                f"fixtures/patch-proposal-acceptance-drill/{flags['acceptance_case']}/"
                "patch-proposal-acceptance-drill-receipt.json"
            ),
            "acceptance_receipt_hash": artifact_hash(acceptance_receipt),
            "acceptance_report_ref": "platform/generated/study-anything-patch-proposal-acceptance-drill.json",
        },
        "work_order": {
            "package_type": "metadata_only_external_operator_work_order",
            "handoff_target": "host_platform_operator_or_human_developer",
            "purpose": "continue_patch_proposal_outside_cbb_under_local_controls" if allowed else None,
            "source_chain_refs": [
                "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.json",
                "platform/generated/study-anything-patch-proposal-operator-handoff-bridge.json",
                "platform/generated/study-anything-patch-proposal-acceptance-drill.json",
            ],
            "suggested_operator_steps": [
                "inspect_metadata_refs",
                "reconstruct_boundary",
                "decide_external_execution_path",
                "run_platform_or_local_controls_outside_cbb",
            ] if allowed else [],
            "not_included": [
                "raw_patch_body",
                "raw_diff_body",
                "raw_source_text",
                "customer_payload",
                "agent_secrets",
                "model_keys",
            ],
        },
        "operator_reconstruction": reconstruction,
        "effect_boundary": {
            "raw_patch_or_diff_read": False,
            "patch_body_included": False,
            "diff_body_included": False,
            "implementation_execution_performed": False,
            "repository_mutation_performed": False,
            "automatic_pr_opening_performed": False,
            "automatic_pr_commenting_performed": False,
            "customer_visible_action_performed": False,
            "external_publication_performed": False,
            "production_mutation_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": (
                "A ready work-order pack gives a host operator enough metadata refs to continue "
                "outside Study Anything / Cognitive Black Box under separate controls. It does "
                "not contain patch bodies, execute code, open PRs, send, publish, deploy, or certify."
            ),
            "not_claimed": [
                "patch content included",
                "repository changed",
                "PR opened or commented",
                "customer communication approved",
                "external publication approved",
                "production change approved",
                "truth or security certified",
            ],
        },
    }
    return validate_work_order_receipt(receipt)


def validate_work_order_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalExternalWorkOrderPackError("work-order receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    work_order = _require_object(receipt, "work_order", label=RECEIPT_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=RECEIPT_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    if work_order.get("package_type") != "metadata_only_external_operator_work_order":
        raise PatchProposalExternalWorkOrderPackError("work order package_type must remain metadata-only")
    for key in (
        "raw_patch_or_diff_read",
        "implementation_execution_performed",
        "repository_mutation_performed",
        "automatic_pr_opening_performed",
        "automatic_pr_commenting_performed",
        "customer_visible_action_performed",
        "external_publication_performed",
        "production_mutation_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalExternalWorkOrderPackError(f"effect_boundary.{key} must remain false")
    if status == "ready":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalExternalWorkOrderPackError("ready work-order receipt must not carry blocked reasons")
        if work_order.get("purpose") != "continue_patch_proposal_outside_cbb_under_local_controls":
            raise PatchProposalExternalWorkOrderPackError("ready work-order purpose drifted")
        for key in (
            "acceptance_allowed",
            "work_order_purpose_present",
            "operator_reconstruction_present",
            "metadata_only_work_order",
        ):
            if checks.get(key) is not True:
                raise PatchProposalExternalWorkOrderPackError(f"ready work-order receipt missing check: {key}")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalExternalWorkOrderPackError("blocked work-order receipt must carry reasons")
        if work_order.get("purpose") is not None:
            raise PatchProposalExternalWorkOrderPackError("blocked work-order receipt must not expose purpose")
    else:
        raise PatchProposalExternalWorkOrderPackError("work-order receipt status must be ready or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-external-work-order-receipt.json": build_work_order_receipt(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_work_order_receipt(cases[case_id]["patch-proposal-external-work-order-receipt.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "work_order_purpose": receipt["work_order"]["purpose"],
            }
        )
    ready_count = sum(1 for row in case_reports if row["status"] == "ready")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove an allowed Patch Proposal Acceptance Drill can become a metadata-only "
            "external operator work-order package without executing or publishing anything."
        ),
        "source_chain": {
            "allowed_acceptance_receipt": (
                "fixtures/patch-proposal-acceptance-drill/pass/"
                "patch-proposal-acceptance-drill-receipt.json"
            ),
            "acceptance_report": "platform/generated/study-anything-patch-proposal-acceptance-drill.json",
        },
        "work_order_matrix": {
            "ready_work_orders": ready_count,
            "blocked_work_orders": blocked_count,
            "total_cases": len(case_reports),
            "acceptance_not_allowed_rejected": True,
            "missing_purpose_rejected": True,
            "raw_patch_or_diff_rejected": True,
            "apply_patch_rejected": True,
            "open_pr_rejected": True,
            "pr_comment_rejected": True,
            "customer_visible_action_rejected": True,
            "external_publication_rejected": True,
            "production_mutation_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "allowed_acceptance_required": True,
            "metadata_only_work_order_required": True,
            "operator_reconstruction_required": True,
            "raw_patch_or_diff_rejected": True,
            "apply_patch_rejected": True,
            "pr_actions_rejected": True,
            "customer_visible_action_rejected": True,
            "external_publication_rejected": True,
            "production_mutation_rejected": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The pack proves a bounded work-order package can be emitted for a host operator. "
                "It does not execute, apply, open PRs, comment, publish, send, deploy, or certify."
            ),
            "not_claimed": [
                "patch content included",
                "repository changed",
                "PR opened or commented",
                "customer handoff approved",
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
