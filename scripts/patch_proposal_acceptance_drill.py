#!/usr/bin/env python3
"""Build metadata-only Patch Proposal Acceptance Drill artifacts."""

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
import patch_proposal_operator_handoff_bridge as bridge  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-acceptance-drill-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-acceptance-drill-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-acceptance-drill"
BRIDGE_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-operator-handoff-bridge"

CASE_IDS = (
    "pass",
    "blocked-bridge-blocked",
    "blocked-missing-operator-decision",
    "blocked-raw-patch-evidence-request",
    "blocked-apply-patch-request",
    "blocked-open-pr-request",
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
    "raw_decision_notes",
}


class PatchProposalAcceptanceDrillError(ValueError):
    """Raised when acceptance drill artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalAcceptanceDrillError(f"Expected JSON object: {path}")
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
        raise PatchProposalAcceptanceDrillError(f"{label}.{key} must be an object")
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
        raise PatchProposalAcceptanceDrillError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalAcceptanceDrillError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalAcceptanceDrillError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str]:
    if case_id not in CASE_IDS:
        raise PatchProposalAcceptanceDrillError(f"Unknown case id: {case_id}")
    return {
        "bridge_case": "blocked-missing-operator-confirmation" if case_id == "blocked-bridge-blocked" else "pass",
        "operator_decision_present": case_id != "blocked-missing-operator-decision",
        "raw_patch_evidence_requested": case_id == "blocked-raw-patch-evidence-request",
        "apply_patch_requested": case_id == "blocked-apply-patch-request",
        "open_pr_requested": case_id == "blocked-open-pr-request",
        "customer_visible_action_requested": case_id == "blocked-customer-visible-action",
        "external_publication_requested": case_id == "blocked-external-publication",
        "production_mutation_requested": case_id == "blocked-production-mutation",
    }


def source_bridge_receipt(case_id: str) -> dict[str, Any]:
    bridge_case = str(_case_flags(case_id)["bridge_case"])
    receipt = load_json(BRIDGE_FIXTURE_DIR / bridge_case / "patch-proposal-operator-handoff-bridge-receipt.json")
    return bridge.validate_bridge_receipt(receipt)


def operator_reconstruction(present: bool) -> dict[str, bool]:
    return {
        "metadata_refs_are_sufficient_for_decision": present,
        "raw_patch_body_must_not_be_requested": present,
        "raw_diff_body_must_not_be_requested": present,
        "study_anything_must_not_apply_changes": present,
        "host_operator_controls_external_actions": present,
        "customer_visible_output_requires_separate_approval": present,
        "production_mutation_requires_separate_approval": present,
    }


def build_acceptance_receipt(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    bridge_receipt = source_bridge_receipt(case_id)
    reconstruction = operator_reconstruction(bool(flags["operator_decision_present"]))
    checks = {
        "bridge_ready": bridge_receipt.get("status") == "ready",
        "operator_decision_present": bool(flags["operator_decision_present"]),
        "operator_active_reconstruction_present": all(reconstruction.values()),
        "metadata_only_bridge_package": True,
        "raw_patch_evidence_requested": bool(flags["raw_patch_evidence_requested"]),
        "raw_diff_evidence_requested": bool(flags["raw_patch_evidence_requested"]),
        "apply_patch_requested": bool(flags["apply_patch_requested"]),
        "open_pr_requested": bool(flags["open_pr_requested"]),
        "customer_visible_action_requested": bool(flags["customer_visible_action_requested"]),
        "external_publication_requested": bool(flags["external_publication_requested"]),
        "production_mutation_requested": bool(flags["production_mutation_requested"]),
    }
    reasons: list[str] = []
    if not checks["bridge_ready"]:
        reasons.append("bridge_not_ready")
    if not checks["operator_decision_present"]:
        reasons.append("operator_decision_missing")
    if not checks["operator_active_reconstruction_present"]:
        reasons.append("operator_active_reconstruction_missing")
    if checks["raw_patch_evidence_requested"] or checks["raw_diff_evidence_requested"]:
        reasons.append("raw_patch_or_diff_evidence_request_rejected")
    if checks["apply_patch_requested"]:
        reasons.append("apply_patch_request_rejected")
    if checks["open_pr_requested"]:
        reasons.append("open_pr_request_rejected")
    if checks["customer_visible_action_requested"]:
        reasons.append("customer_visible_action_rejected")
    if checks["external_publication_requested"]:
        reasons.append("external_publication_rejected")
    if checks["production_mutation_requested"]:
        reasons.append("production_mutation_rejected")

    allowed = not reasons
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "receipt_id": f"patch-proposal-acceptance-drill-{case_id}",
        "case_id": case_id,
        "status": "allowed" if allowed else "blocked",
        "decision": "allow_external_operator_continuation" if allowed else "block_external_operator_continuation",
        "blocked_reasons": reasons,
        "source_refs": {
            "bridge_receipt_ref": (
                f"fixtures/patch-proposal-operator-handoff-bridge/{flags['bridge_case']}/"
                "patch-proposal-operator-handoff-bridge-receipt.json"
            ),
            "bridge_receipt_hash": artifact_hash(bridge_receipt),
            "bridge_report_ref": "platform/generated/study-anything-patch-proposal-operator-handoff-bridge.json",
        },
        "operator_decision_input": {
            "mode": "metadata_refs_only",
            "operator_decision_present": checks["operator_decision_present"],
            "requested_continuation": "prepare_external_operator_work_order",
            "requested_evidence_class": "bounded_metadata_refs",
        },
        "operator_reconstruction": reconstruction,
        "acceptance_boundary": {
            "mode": "decision_receipt_only",
            "next_allowed_action": "prepare_external_operator_work_order" if allowed else None,
            "allowed_continuation": (
                "host_platform_operator_may_continue_outside_cbb_under_local_controls" if allowed else None
            ),
            "not_allowed_actions": [
                "read_raw_patch_body",
                "read_raw_diff_body",
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
            "raw_patch_or_diff_read": False,
            "implementation_execution_performed": False,
            "repository_mutation_performed": False,
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
                "A pass means the external operator can continue with a bounded work order outside "
                "Study Anything / Cognitive Black Box. It does not apply code, open PRs, comment, "
                "send customer-visible output, publish, deploy, or approve production."
            ),
            "not_claimed": [
                "patch content reviewed",
                "repository changed",
                "PR opened or commented",
                "customer communication approved",
                "external publication approved",
                "production change approved",
                "truth or security certified",
            ],
        },
    }
    return validate_acceptance_receipt(receipt)


def validate_acceptance_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalAcceptanceDrillError("acceptance receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    boundary = _require_object(receipt, "acceptance_boundary", label=RECEIPT_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=RECEIPT_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    if boundary.get("mode") != "decision_receipt_only":
        raise PatchProposalAcceptanceDrillError("acceptance boundary mode must remain decision_receipt_only")
    for key in (
        "raw_patch_or_diff_read",
        "implementation_execution_performed",
        "repository_mutation_performed",
        "automatic_pr_commenting_performed",
        "customer_visible_action_performed",
        "external_publication_performed",
        "production_mutation_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalAcceptanceDrillError(f"effect_boundary.{key} must remain false")
    if status == "allowed":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalAcceptanceDrillError("allowed acceptance receipt must not carry blocked reasons")
        if boundary.get("next_allowed_action") != "prepare_external_operator_work_order":
            raise PatchProposalAcceptanceDrillError("allowed acceptance receipt next action drifted")
        for key in (
            "bridge_ready",
            "operator_decision_present",
            "operator_active_reconstruction_present",
            "metadata_only_bridge_package",
        ):
            if checks.get(key) is not True:
                raise PatchProposalAcceptanceDrillError(f"allowed acceptance receipt missing check: {key}")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalAcceptanceDrillError("blocked acceptance receipt must carry reasons")
        if boundary.get("next_allowed_action") is not None:
            raise PatchProposalAcceptanceDrillError("blocked acceptance receipt must not expose next action")
    else:
        raise PatchProposalAcceptanceDrillError("acceptance receipt status must be allowed or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-acceptance-drill-receipt.json": build_acceptance_receipt(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_acceptance_receipt(cases[case_id]["patch-proposal-acceptance-drill-receipt.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "next_allowed_action": receipt["acceptance_boundary"]["next_allowed_action"],
            }
        )
    allowed_count = sum(1 for row in case_reports if row["status"] == "allowed")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove an operator can make allow/block continuation decisions from the "
            "Patch Proposal Operator Handoff Bridge metadata package alone."
        ),
        "source_chain": {
            "ready_bridge_receipt": (
                "fixtures/patch-proposal-operator-handoff-bridge/pass/"
                "patch-proposal-operator-handoff-bridge-receipt.json"
            ),
            "bridge_report": "platform/generated/study-anything-patch-proposal-operator-handoff-bridge.json",
        },
        "operator_decision_matrix": {
            "allowed_continuations": allowed_count,
            "blocked_continuations": blocked_count,
            "total_decisions": len(case_reports),
            "bridge_not_ready_rejected": True,
            "missing_operator_decision_rejected": True,
            "raw_patch_or_diff_evidence_rejected": True,
            "repository_mutation_rejected": True,
            "pr_action_rejected": True,
            "customer_visible_action_rejected": True,
            "external_publication_rejected": True,
            "production_mutation_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "metadata_only_bridge_package_required": True,
            "active_operator_reconstruction_required": True,
            "raw_patch_or_diff_rejected": True,
            "apply_patch_rejected": True,
            "open_pr_rejected": True,
            "customer_visible_action_rejected": True,
            "external_publication_rejected": True,
            "production_mutation_rejected": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The drill proves a bounded continuation decision can be derived from metadata-only "
                "bridge evidence. It does not execute, apply, publish, send, deploy, or certify."
            ),
            "not_claimed": [
                "patch content reviewed",
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
