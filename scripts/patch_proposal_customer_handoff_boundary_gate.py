#!/usr/bin/env python3
"""Build metadata-only Patch Proposal Customer-Handoff Boundary Gate artifacts."""

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
import patch_proposal_external_operator_completion as completion  # noqa: E402


RECEIPT_SCHEMA_VERSION = "patch-proposal-customer-handoff-boundary-receipt-v1"
REPORT_SCHEMA_VERSION = "patch-proposal-customer-handoff-boundary-gate-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "patch-proposal-customer-handoff-boundary-gate"
COMPLETION_FIXTURE_DIR = ROOT / "fixtures" / "patch-proposal-external-operator-completion"

CASE_IDS = (
    "pass",
    "blocked-completion-blocked",
    "blocked-missing-delivery-class-scenario",
    "blocked-missing-human-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-missing-sandbox-receipt",
    "blocked-raw-customer-draft",
    "blocked-raw-patch-return",
    "blocked-production-payload",
    "blocked-auto-send",
    "blocked-external-publication",
    "blocked-secret-return",
    "blocked-model-credential-return",
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
    "raw_diff_body",
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


class PatchProposalCustomerHandoffBoundaryGateError(ValueError):
    """Raised when customer-handoff boundary artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchProposalCustomerHandoffBoundaryGateError(f"Expected JSON object: {path}")
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
        raise PatchProposalCustomerHandoffBoundaryGateError(f"{label}.{key} must be an object")
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
        raise PatchProposalCustomerHandoffBoundaryGateError(f"{label} includes forbidden raw fields: {forbidden}")
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise PatchProposalCustomerHandoffBoundaryGateError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise PatchProposalCustomerHandoffBoundaryGateError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool | str]:
    if case_id not in CASE_IDS:
        raise PatchProposalCustomerHandoffBoundaryGateError(f"Unknown case id: {case_id}")
    return {
        "completion_case": "blocked-work-order-blocked" if case_id == "blocked-completion-blocked" else "pass",
        "delivery_class_scenario_present": case_id != "blocked-missing-delivery-class-scenario",
        "human_reconstruction_present": case_id != "blocked-missing-human-reconstruction",
        "claim_boundary_present": case_id != "blocked-missing-claim-boundary",
        "privacy_boundary_present": case_id != "blocked-missing-privacy-boundary",
        "sandbox_receipt_present": case_id != "blocked-missing-sandbox-receipt",
        "raw_customer_draft_returned": case_id == "blocked-raw-customer-draft",
        "raw_patch_returned": case_id == "blocked-raw-patch-return",
        "production_payload_returned": case_id == "blocked-production-payload",
        "auto_send_requested": case_id == "blocked-auto-send",
        "external_publication_requested": case_id == "blocked-external-publication",
        "secrets_returned": case_id == "blocked-secret-return",
        "model_credentials_returned": case_id == "blocked-model-credential-return",
    }


def source_completion_receipt(case_id: str) -> dict[str, Any]:
    completion_case = str(_case_flags(case_id)["completion_case"])
    receipt = load_json(
        COMPLETION_FIXTURE_DIR / completion_case / "patch-proposal-external-operator-completion-receipt.json"
    )
    return completion.validate_completion_receipt(receipt)


def build_customer_handoff_receipt(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    completion_receipt = source_completion_receipt(case_id)
    checks = {
        "completion_accepted": completion_receipt.get("status") == "accepted",
        "delivery_class_scenario_present": bool(flags["delivery_class_scenario_present"]),
        "human_reconstruction_present": bool(flags["human_reconstruction_present"]),
        "claim_boundary_present": bool(flags["claim_boundary_present"]),
        "privacy_boundary_present": bool(flags["privacy_boundary_present"]),
        "sandbox_receipt_present": bool(flags["sandbox_receipt_present"]),
        "metadata_only_customer_handoff": True,
        "raw_customer_draft_returned": bool(flags["raw_customer_draft_returned"]),
        "raw_patch_returned": bool(flags["raw_patch_returned"]),
        "production_payload_returned": bool(flags["production_payload_returned"]),
        "auto_send_requested": bool(flags["auto_send_requested"]),
        "external_publication_requested": bool(flags["external_publication_requested"]),
        "secrets_returned": bool(flags["secrets_returned"]),
        "model_credentials_returned": bool(flags["model_credentials_returned"]),
    }
    reasons: list[str] = []
    for key, reason in (
        ("completion_accepted", "completion_not_accepted"),
        ("delivery_class_scenario_present", "delivery_class_scenario_missing"),
        ("human_reconstruction_present", "human_reconstruction_missing"),
        ("claim_boundary_present", "claim_boundary_missing"),
        ("privacy_boundary_present", "privacy_boundary_missing"),
        ("sandbox_receipt_present", "sandbox_receipt_missing"),
    ):
        if not checks[key]:
            reasons.append(reason)
    for key, reason in (
        ("raw_customer_draft_returned", "raw_customer_draft_rejected"),
        ("raw_patch_returned", "raw_patch_return_rejected"),
        ("production_payload_returned", "production_payload_rejected"),
        ("auto_send_requested", "automatic_customer_send_rejected"),
        ("external_publication_requested", "external_publication_rejected"),
        ("secrets_returned", "secret_return_rejected"),
        ("model_credentials_returned", "model_credential_return_rejected"),
    ):
        if checks[key]:
            reasons.append(reason)

    ready = not reasons
    receipt = {
        **_base(RECEIPT_SCHEMA_VERSION),
        "receipt_id": f"patch-proposal-customer-handoff-boundary-{case_id}",
        "case_id": case_id,
        "status": "ready" if ready else "blocked",
        "decision": "allow_customer_handoff_preparation" if ready else "block_customer_handoff_boundary",
        "blocked_reasons": reasons,
        "source_refs": {
            "completion_receipt_ref": (
                f"fixtures/patch-proposal-external-operator-completion/{flags['completion_case']}/"
                "patch-proposal-external-operator-completion-receipt.json"
            ),
            "completion_receipt_hash": artifact_hash(completion_receipt),
            "completion_report_ref": "platform/generated/study-anything-patch-proposal-external-operator-completion.json",
        },
        "handoff_summary": {
            "package_type": "metadata_only_customer_handoff_boundary",
            "delivery_class": "code_review_patch_proposal" if ready else None,
            "purpose": "prepare_customer_handoff_under_separate_delivery_control" if ready else None,
            "customer_handoff_refs": [
                "delivery_class_scenario_ref",
                "human_reconstruction_receipt_ref",
                "claim_boundary_receipt_ref",
                "privacy_boundary_receipt_ref",
                "sandbox_receipt_ref",
            ] if ready else [],
            "not_included": [
                "raw_customer_draft",
                "raw_patch_body",
                "raw_diff_body",
                "repository_file_body",
                "pr_comment_body",
                "customer_visible_payload",
                "external_publication_payload",
                "production_payload",
                "secrets",
                "model_keys",
            ],
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
                "A ready boundary receipt permits only preparation for a separate customer-handoff control. "
                "It does not include or send customer-visible content and does not approve publication, "
                "production mutation, correctness, or security."
            ),
            "not_claimed": [
                "customer-visible content included",
                "customer message sent",
                "external publication approved",
                "production change approved",
                "truth or security certified",
            ],
        },
    }
    return validate_customer_handoff_receipt(receipt)


def validate_customer_handoff_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise PatchProposalCustomerHandoffBoundaryGateError("customer handoff receipt schema_version drifted")
    _validate_privacy(receipt, label=RECEIPT_SCHEMA_VERSION)
    status = receipt.get("status")
    summary = _require_object(receipt, "handoff_summary", label=RECEIPT_SCHEMA_VERSION)
    effect = _require_object(receipt, "effect_boundary", label=RECEIPT_SCHEMA_VERSION)
    checks = _require_object(receipt, "checks", label=RECEIPT_SCHEMA_VERSION)
    if summary.get("package_type") != "metadata_only_customer_handoff_boundary":
        raise PatchProposalCustomerHandoffBoundaryGateError("handoff package_type must remain metadata-only")
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
            raise PatchProposalCustomerHandoffBoundaryGateError(f"effect_boundary.{key} must remain false")
    if status == "ready":
        if receipt.get("blocked_reasons") != []:
            raise PatchProposalCustomerHandoffBoundaryGateError("ready customer handoff receipt must not carry reasons")
        for key in (
            "completion_accepted",
            "delivery_class_scenario_present",
            "human_reconstruction_present",
            "claim_boundary_present",
            "privacy_boundary_present",
            "sandbox_receipt_present",
            "metadata_only_customer_handoff",
        ):
            if checks.get(key) is not True:
                raise PatchProposalCustomerHandoffBoundaryGateError(f"ready customer handoff missing check: {key}")
        for key in (
            "raw_customer_draft_returned",
            "raw_patch_returned",
            "production_payload_returned",
            "auto_send_requested",
            "external_publication_requested",
            "secrets_returned",
            "model_credentials_returned",
        ):
            if checks.get(key) is not False:
                raise PatchProposalCustomerHandoffBoundaryGateError(f"ready customer handoff checks.{key} must remain false")
    elif status == "blocked":
        if not receipt.get("blocked_reasons"):
            raise PatchProposalCustomerHandoffBoundaryGateError("blocked customer handoff receipt must carry reasons")
        if summary.get("purpose") is not None or summary.get("delivery_class") is not None:
            raise PatchProposalCustomerHandoffBoundaryGateError("blocked customer handoff must not expose purpose or class")
    else:
        raise PatchProposalCustomerHandoffBoundaryGateError("customer handoff receipt status must be ready or blocked")
    return dict(receipt)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"patch-proposal-customer-handoff-boundary-receipt.json": build_customer_handoff_receipt(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        receipt = validate_customer_handoff_receipt(
            cases[case_id]["patch-proposal-customer-handoff-boundary-receipt.json"]
        )
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt["status"],
                "decision": receipt["decision"],
                "blocked_reasons": receipt["blocked_reasons"],
                "handoff_purpose": receipt["handoff_summary"]["purpose"],
            }
        )
    ready_count = sum(1 for row in case_reports if row["status"] == "ready")
    blocked_count = sum(1 for row in case_reports if row["status"] == "blocked")
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": "Prove customer-visible handoff remains blocked unless the metadata-only boundary gate passes.",
        "source_chain": {
            "accepted_completion_receipt": (
                "fixtures/patch-proposal-external-operator-completion/pass/"
                "patch-proposal-external-operator-completion-receipt.json"
            ),
            "completion_report": "platform/generated/study-anything-patch-proposal-external-operator-completion.json",
        },
        "handoff_matrix": {
            "ready_handoffs": ready_count,
            "blocked_handoffs": blocked_count,
            "total_cases": len(case_reports),
            "completion_not_accepted_rejected": True,
            "delivery_class_scenario_missing_rejected": True,
            "human_reconstruction_missing_rejected": True,
            "claim_boundary_missing_rejected": True,
            "privacy_boundary_missing_rejected": True,
            "sandbox_receipt_missing_rejected": True,
            "raw_customer_draft_rejected": True,
            "raw_patch_return_rejected": True,
            "production_payload_rejected": True,
            "automatic_customer_send_rejected": True,
            "external_publication_rejected": True,
            "secret_return_rejected": True,
            "model_credential_return_rejected": True,
        },
        "case_reports": case_reports,
        "quality_gates": {
            "accepted_completion_required": True,
            "delivery_class_scenario_required": True,
            "human_reconstruction_required": True,
            "claim_boundary_required": True,
            "privacy_boundary_required": True,
            "sandbox_receipt_required": True,
            "customer_visible_payloads_rejected": True,
            "automatic_customer_send_blocked": True,
            "external_publication_blocked": True,
            "production_mutation_blocked": True,
            "secrets_and_model_credentials_rejected": True,
        },
        "claim_boundary": {
            "current_claim": (
                "The gate proves only customer-handoff preparation may proceed under separate controls. "
                "It does not send, publish, deploy, or certify customer-visible content."
            ),
            "not_claimed": [
                "customer-visible content included",
                "customer message sent",
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
