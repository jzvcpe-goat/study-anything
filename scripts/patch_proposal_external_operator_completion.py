#!/usr/bin/env python3
"""Build metadata-only Patch Proposal External Operator Completion artifacts."""

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
import patch_proposal_external_work_order_pack as work_order_pack  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-external-operator-completion-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-external-operator-completion-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-external-operator-completion"
WORK_ORDER_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-external-work-order-pack"

CASE_IDS = (
    "pass",
    "blocked-work-order-blocked",
    "blocked-missing-completion-purpose",
    "blocked-missing-reconstruction",
    "blocked-raw-patch-return",
    "blocked-raw-diff-return",
    "blocked-repository-file-body-return",
    "blocked-pr-comment-return",
    "blocked-customer-visible-payload",
    "blocked-external-publication-payload",
    "blocked-production-payload",
    "blocked-secret-return",
    "blocked-model-credential-return",
)

PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "raw_spec_eval_body_included": False,
    "raw_eval_prompt_included": False,
    "raw_patch_body_included": False,
    "raw_diff_body_included": False,
    "raw_repository_file_body_included": False,
    "raw_pr_comment_included": False,
    "raw_customer_payload_included": False,
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
    "raw_diff_body",
    "raw_repository_file_body",
    "repository_file_body",
    "raw_source_text",
    "raw_completion_body",
    "raw_operator_notes",
    "pr_comment_body",
    "raw_pr_comment",
    "customer_visible_content",
    "raw_customer_payload",
    "external_publication_payload",
    "production_payload",
    "secret",
    "secrets",
    "model_key",
    "model_keys",
    "agent_credentials",
}


class PatchProposalExternalOperatorCompletionError(ValueError):
    """Raised when external operator completion artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalExternalOperatorCompletionError(f"Expected JSON object: {path}")
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
        raise PatchProposalExternalOperatorCompletionError(f"{label}.{key} must be an object")
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
        raise PatchProposalExternalOperatorCompletionError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalExternalOperatorCompletionError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalExternalOperatorCompletionError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str]:
    if case_id not in CASE_IDS:
        raise PatchProposalExternalOperatorCompletionError(f"Unknown case id: {case_id}")
    return {
        "work_order_case": "blocked-open-pr-request" if case_id == "blocked-work-order-blocked" else "pass",
        "completion_purpose_present": case_id != "blocked-missing-completion-purpose",
        "reconstruction_present": case_id != "blocked-missing-reconstruction",
        "raw_patch_returned": case_id == "blocked-raw-patch-return",
        "raw_diff_returned": case_id == "blocked-raw-diff-return",
        "repository_file_body_returned": case_id == "blocked-repository-file-body-return",
        "pr_comment_payload_returned": case_id == "blocked-pr-comment-return",
        "customer_visible_payload_returned": case_id == "blocked-customer-visible-payload",
        "external_publication_payload_returned": case_id == "blocked-external-publication-payload",
        "production_payload_returned": case_id == "blocked-production-payload",
        "secrets_returned": case_id == "blocked-secret-return",
        "model_credentials_returned": case_id == "blocked-model-credential-return",
    }


def source_work_order_receipt(case_id: str) -> dict[str, Any]:
    work_order_case = str(_case_flags(case_id)["work_order_case"])
    receipt = load_json(WORK_ORDER_FIXTURE_DIR / work_order_case / "patch-proposal-external-work-order-receipt.json")
    return work_order_pack.validate_work_order_receipt(receipt)


def operator_completion_reconstruction(present: bool) -> dict[str, bool]:
    return {
        "completion_is_metadata_only": present,
        "external_operator_controls_execution": present,
        "raw_patch_and_diff_are_absent": present,
        "repository_file_bodies_are_absent": present,
        "pr_comment_payloads_are_absent": present,
        "customer_visible_payloads_are_absent": present,
        "production_payloads_are_absent": present,
        "secrets_and_model_credentials_are_absent": present,
        "study_anything_records_summary_only": present,
    }


def build_completion_receipt(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    source_receipt = source_work_order_receipt(case_id)
    reconstruction = operator_completion_reconstruction(bool(flags["reconstruction_present"]))
    checks = {
        "work_order_ready": source_receipt.get("status") == "ready",
        "completion_purpose_present": bool(flags["completion_purpose_present"]),
        "operator_reconstruction_present": all(reconstruction.values()),
        "metadata_only_completion": True,
        "raw_patch_returned": bool(flags["raw_patch_returned"]),
        "raw_diff_returned": bool(flags["raw_diff_returned"]),
        "repository_file_body_returned": bool(flags["repository_file_body_returned"]),
        "pr_comment_payload_returned": bool(flags["pr_comment_payload_returned"]),
        "customer_visible_payload_returned": bool(flags["customer_visible_payload_returned"]),
        "external_publication_payload_returned": bool(flags["external_publication_payload_returned"]),
        "production_payload_returned": bool(flags["production_payload_returned"]),
        "secrets_returned": bool(flags["secrets_returned"]),
        "model_credentials_returned": bool(flags["model_credentials_returned"]),
    }
    reasons: list[str] = []
    if not checks["work_order_ready"]:
        reasons.append("work_order_not_ready")
    if not checks["completion_purpose_present"]:
        reasons.append("completion_purpose_missing")
    if not checks["operator_reconstruction_present"]:
        reasons.append("operator_reconstruction_missing")
    for key, reason in (
        ("raw_patch_returned", "raw_patch_return_rejected"),
        ("raw_diff_returned", "raw_diff_return_rejected"),
        ("repository_file_body_returned", "repository_file_body_return_rejected"),
        ("pr_comment_payload_returned", "pr_comment_payload_return_rejected"),
        ("customer_visible_payload_returned", "customer_visible_payload_return_rejected"),
        ("external_publication_payload_returned", "external_publication_payload_return_rejected"),
        ("production_payload_returned", "production_payload_return_rejected"),
        ("secrets_returned", "secret_return_rejected"),
        ("model_credentials_returned", "model_credential_return_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    accepted = not reasons
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "receipt_id": f"patch-proposal-external-operator-completion-{case_id}",
        "case_id": case_id,
        "status": "accepted" if accepted else "blocked",
        "decision": (
            "accept_metadata_only_external_operator_completion"
            if accepted
            else "block_external_operator_completion"
        ),
        "blocked_reasons": reasons,
        "source_refs": {
            "work_order_receipt_ref": (
                f"fixtures/patch-proposal-external-work-order-pack/{flags['work_order_case']}/"
                "patch-proposal-external-work-order-receipt.json"
            ),
            "work_order_receipt_hash": artifact_hash(source_receipt),
            "work_order_report_ref": "platform/generated/study-anything-patch-proposal-external-work-order-pack.json",
        },
        "completion_summary": {
            "package_type": "metadata_only_external_operator_completion",
            "result_status": "completed_under_external_controls" if accepted else None,
            "purpose": "record_external_operator_completion_without_raw_payloads" if accepted else None,
            "external_operator_ref": "host-operator-run-ref-0001" if accepted else None,
            "completion_refs": [
                "external_operator_completion_summary_hash",
                "external_platform_control_receipt_ref",
                "local_operator_audit_ref",
            ] if accepted else [],
            "not_included": [
                "raw_patch_body",
                "raw_diff_body",
                "repository_file_body",
                "pr_comment_body",
                "customer_visible_content",
                "external_publication_payload",
                "production_payload",
                "secrets",
                "model_keys",
                "agent_credentials",
            ],
        },
        "operator_reconstruction": reconstruction,
        "effect_boundary": {
            "study_anything_read_raw_patch_or_diff": False,
            "study_anything_read_repository_file_body": False,
            "study_anything_read_pr_comment_payload": False,
            "study_anything_read_customer_visible_payload": False,
            "study_anything_read_external_publication_payload": False,
            "study_anything_read_production_payload": False,
            "study_anything_repository_mutation_performed": False,
            "study_anything_automatic_pr_opening_performed": False,
            "study_anything_automatic_pr_commenting_performed": False,
            "study_anything_customer_visible_action_performed": False,
            "study_anything_external_publication_performed": False,
            "study_anything_production_mutation_performed": False,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "external_effects_summarized_only": True,
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": (
                "An accepted completion receipt records only metadata-level evidence that a host operator "
                "completed work outside Study Anything / Cognitive Black Box. It does not import raw "
                "patches, diffs, repository file bodies, PR comments, customer payloads, production "
                "payloads, secrets, or model credentials."
            ),
            "not_claimed": [
                "patch content imported",
                "repository file bodies imported",
                "PR comments imported",
                "customer-visible delivery approved",
                "external publication approved",
                "production mutation approved",
                "truth or security certified",
            ],
        },
    }
    return validate_completion_receipt(receipt)


def validate_completion_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalExternalOperatorCompletionError("completion receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "completion_summary", label=RECEIPT_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=RECEIPT_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_external_operator_completion":
        raise PatchProposalExternalOperatorCompletionError("completion package_type must remain metadata-only")
    for key in (
        "study_anything_read_raw_patch_or_diff",
        "study_anything_read_repository_file_body",
        "study_anything_read_pr_comment_payload",
        "study_anything_read_customer_visible_payload",
        "study_anything_read_external_publication_payload",
        "study_anything_read_production_payload",
        "study_anything_repository_mutation_performed",
        "study_anything_automatic_pr_opening_performed",
        "study_anything_automatic_pr_commenting_performed",
        "study_anything_customer_visible_action_performed",
        "study_anything_external_publication_performed",
        "study_anything_production_mutation_performed",
        "model_calls_performed",
        "daemon_or_hosted_service_started",
    ):
        if effect.get(key) is not False:
            raise PatchProposalExternalOperatorCompletionError(f"effect_boundary.{key} must remain false")
    if effect.get("external_effects_summarized_only") is not True:
        raise PatchProposalExternalOperatorCompletionError("external effects must remain summarized only")
    if status == "accepted":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalExternalOperatorCompletionError("accepted completion receipt must not carry blocked reasons")
        for key in (
            "raw_patch_returned",
            "raw_diff_returned",
            "repository_file_body_returned",
            "pr_comment_payload_returned",
            "customer_visible_payload_returned",
            "external_publication_payload_returned",
            "production_payload_returned",
            "secrets_returned",
            "model_credentials_returned",
        ):
            if checks.get(key) is not False:
                raise PatchProposalExternalOperatorCompletionError(f"accepted completion checks.{key} must remain false")
        for key in (
            "work_order_ready",
            "completion_purpose_present",
            "operator_reconstruction_present",
            "metadata_only_completion",
        ):
            if checks.get(key) is not True:
                raise PatchProposalExternalOperatorCompletionError(f"accepted completion missing check: {key}")
        if summary.get("purpose") != "record_external_operator_completion_without_raw_payloads":
            raise PatchProposalExternalOperatorCompletionError("accepted completion purpose drifted")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalExternalOperatorCompletionError("blocked completion receipt must carry reasons")
        if summary.get("purpose") is not None or summary.get("result_status") is not None:
            raise PatchProposalExternalOperatorCompletionError("blocked completion must not expose purpose or result status")
    else:
        raise PatchProposalExternalOperatorCompletionError("completion receipt status must be accepted or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-external-operator-completion-receipt.json": build_completion_receipt(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_completion_receipt(
            cases[case_id]["patch-proposal-external-operator-completion-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "completion_purpose": receipt["completion_summary"]["purpose"],
            }
        )
    accepted_count = sum(1 for row in case_reports if row["status"] == "accepted")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": (
            "Prove a host-operator completion can re-enter Study Anything / Cognitive Black Box "
            "only as metadata-level evidence."
        ),
        "source_chain": {
            "ready_work_order_receipt": (
                "fixtures/patch-proposal-external-work-order-pack/pass/"
                "patch-proposal-external-work-order-receipt.json"
            ),
            "work_order_report": "platform/generated/study-anything-patch-proposal-external-work-order-pack.json",
        },
        "completion_matrix": {
            "accepted_completions": accepted_count,
            "blocked_completions": blocked_count,
            "total_cases": len(case_reports),
            "work_order_not_ready_rejected": True,
            "missing_completion_purpose_rejected": True,
            "missing_reconstruction_rejected": True,
            "raw_patch_return_rejected": True,
            "raw_diff_return_rejected": True,
            "repository_file_body_return_rejected": True,
            "pr_comment_payload_return_rejected": True,
            "customer_visible_payload_return_rejected": True,
            "external_publication_payload_return_rejected": True,
            "production_payload_return_rejected": True,
            "secret_return_rejected": True,
            "model_credential_return_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "ready_work_order_required": True,
            "metadata_only_completion_required": True,
            "operator_reconstruction_required": True,
            "raw_patch_or_diff_rejected": True,
            "repository_file_bodies_rejected": True,
            "pr_comment_payloads_rejected": True,
            "customer_visible_payloads_rejected": True,
            "external_publication_payloads_rejected": True,
            "production_payloads_rejected": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The receipt proves only metadata-level completion evidence may re-enter the system. "
                "It does not approve customer delivery, public publication, production mutation, or correctness."
            ),
            "not_claimed": [
                "patch content imported",
                "repository file body imported",
                "PR comment imported",
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
