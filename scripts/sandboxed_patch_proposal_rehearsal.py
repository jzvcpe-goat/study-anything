#!/usr/bin/env python3
"""Build metadata-only Sandboxed Patch Proposal Rehearsal artifacts."""

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
import spec_eval_scenario_execution_rehearsal as spec_eval_rehearsal  # noqa: E402


PATCH_PROPOSAL_ENVELOPE_SCHEMA_VERSION = "sandboxed-patch-proposal-envelope-v1"
REPORT_SCHEMA_VERSION = "sandboxed-patch-proposal-rehearsal-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "sandboxed-patch-proposal-rehearsal"
UPSTREAM_FIXTURE_DIR = ROOT / "fixtures" / "spec-eval-scenario-execution-rehearsal"

CASE_IDS = (
    "pass",
    "blocked-missing-spec-eval-allowance",
    "blocked-missing-rollback-plan",
    "blocked-missing-test-plan",
    "blocked-repository-mutation",
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
    "repository_secrets_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}

ISOLATION = dict(dual_loop.ISOLATION_BOUNDARY)


class SandboxedPatchProposalError(ValueError):
    """Raised when patch proposal rehearsal artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SandboxedPatchProposalError(f"Expected JSON object: {path}")
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
        raise SandboxedPatchProposalError(f"{label}.{key} must be an object")
    return value


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.assert_metadata_only(payload, label=label)
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise SandboxedPatchProposalError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise SandboxedPatchProposalError(f"{label}.isolation.{key} must be {expected!r}")


def _case_flags(case_id: str) -> dict[str, bool]:
    if case_id not in CASE_IDS:
        raise SandboxedPatchProposalError(f"Unknown case id: {case_id}")
    return {
        "spec_eval_allowed": case_id != "blocked-missing-spec-eval-allowance",
        "rollback_plan_present": case_id != "blocked-missing-rollback-plan",
        "test_plan_present": case_id != "blocked-missing-test-plan",
        "repository_mutation_requested": case_id == "blocked-repository-mutation",
        "customer_visible_action_requested": case_id == "blocked-customer-visible-action",
        "external_publication_requested": case_id == "blocked-external-publication",
        "production_mutation_requested": case_id == "blocked-production-mutation",
    }


def upstream_execution_receipt(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    upstream_case = "pass" if flags["spec_eval_allowed"] else "blocked-missing-human-reconstruction"
    receipt = load_json(UPSTREAM_FIXTURE_DIR / upstream_case / "spec-eval-execution-rehearsal-receipt.json")
    return spec_eval_rehearsal.validate_execution_receipt(receipt)


def build_patch_proposal_envelope(case_id: str) -> dict[str, Any]:
    flags = _case_flags(case_id)
    execution = upstream_execution_receipt(case_id)
    checks = {
        "spec_eval_execution_allowed": execution.get("status") == "allowed",
        "sandbox_start_authorized": bool(execution.get("execution_boundary", {}).get("sandbox_start_authorized")),
        "rollback_plan_present": flags["rollback_plan_present"],
        "test_plan_present": flags["test_plan_present"],
        "human_reconstruction_present": bool(execution.get("checks", {}).get("human_reconstruction_present")),
        "dual_loop_gate_allowed": bool(execution.get("checks", {}).get("dual_loop_gate_allowed")),
        "raw_patch_body_absent": True,
        "raw_diff_body_absent": True,
        "repository_mutation_requested": flags["repository_mutation_requested"],
        "customer_visible_action_requested": flags["customer_visible_action_requested"],
        "external_publication_requested": flags["external_publication_requested"],
        "production_mutation_requested": flags["production_mutation_requested"],
    }
    reasons: list[str] = []
    if not checks["spec_eval_execution_allowed"]:
        reasons.append("spec_eval_execution_not_allowed")
    if not checks["sandbox_start_authorized"]:
        reasons.append("sandbox_start_not_authorized")
    if not checks["human_reconstruction_present"]:
        reasons.append("human_reconstruction_missing")
    if not checks["dual_loop_gate_allowed"]:
        reasons.append("dual_loop_gate_not_allowed")
    if not checks["rollback_plan_present"]:
        reasons.append("rollback_plan_missing")
    if not checks["test_plan_present"]:
        reasons.append("test_plan_missing")
    if checks["repository_mutation_requested"]:
        reasons.append("repository_mutation_rejected")
    if checks["customer_visible_action_requested"]:
        reasons.append("customer_visible_action_rejected")
    if checks["external_publication_requested"]:
        reasons.append("external_publication_rejected")
    if checks["production_mutation_requested"]:
        reasons.append("production_mutation_rejected")
    allowed = not reasons
    envelope = {
        **_base(PATCH_PROPOSAL_ENVELOPE_SCHEMA_VERSION),
        "envelope_id": f"sandboxed-patch-proposal-{case_id}",
        "case_id": case_id,
        "status": "allowed" if allowed else "blocked",
        "decision": "prepare_sandbox_local_patch_proposal" if allowed else "block_patch_proposal",
        "blocked_reasons": reasons,
        "source_refs": {
            "spec_eval_execution_receipt_ref": (
                "fixtures/spec-eval-scenario-execution-rehearsal/pass/"
                "spec-eval-execution-rehearsal-receipt.json"
                if flags["spec_eval_allowed"]
                else (
                    "fixtures/spec-eval-scenario-execution-rehearsal/blocked-missing-human-reconstruction/"
                    "spec-eval-execution-rehearsal-receipt.json"
                )
            ),
            "spec_eval_execution_receipt_hash": artifact_hash(execution),
            "source_chain_report_ref": "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.json",
        },
        "patch_boundary": {
            "proposal_scope": "sandbox_local_refs_only" if allowed else None,
            "sandbox_local_refs_only": True,
            "patch_body_included": False,
            "diff_body_included": False,
            "implementation_execution_performed": False,
            "repository_mutation_performed": False,
            "customer_visible_action_performed": False,
            "external_publication_performed": False,
            "production_mutation_performed": False,
            "irreversible_effects_performed": False,
        },
        "proposal_refs": {
            "proposal_ref": f"sandbox-local:patch-proposal:{case_id}",
            "patch_plan_ref_hash": dual_loop.sha256_text(f"patch-plan:{case_id}:metadata-only"),
            "changed_component_refs": [
                {
                    "component_ref": "study-anything-learning-runtime-boundary",
                    "operation": "modify",
                    "path_hash": dual_loop.sha256_text("apps/api/study_anything/runtime"),
                },
                {
                    "component_ref": "cognitive-black-box-evidence-gate",
                    "operation": "add",
                    "path_hash": dual_loop.sha256_text("platform/generated/cbb"),
                },
            ],
            "raw_patch_body_included": False,
            "raw_diff_body_included": False,
        },
        "rollback_plan": {
            "required": True,
            "present": flags["rollback_plan_present"],
            "strategy_ref": f"rollback-ref:{case_id}:metadata-only" if flags["rollback_plan_present"] else None,
            "production_restore_required": False,
        },
        "test_plan": {
            "required": True,
            "present": flags["test_plan_present"],
            "test_refs": [
                "verify_sandboxed_patch_proposal_rehearsal",
                "release_check_skip_clean_clone",
            ]
            if flags["test_plan_present"]
            else [],
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": "A sandbox-local patch proposal envelope may be prepared from an allowed Spec/Eval rehearsal without applying repository changes.",
            "not_claimed": [
                "patch body generated",
                "repository mutation performed",
                "customer-visible delivery approved",
                "external publication approved",
                "production mutation approved",
            ],
        },
    }
    return validate_patch_proposal_envelope(envelope)


def validate_patch_proposal_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_privacy(payload, label=PATCH_PROPOSAL_ENVELOPE_SCHEMA_VERSION)
    if payload.get("schema_version") != PATCH_PROPOSAL_ENVELOPE_SCHEMA_VERSION:
        raise SandboxedPatchProposalError("invalid patch proposal envelope schema_version")
    if payload.get("status") not in ("allowed", "blocked"):
        raise SandboxedPatchProposalError("invalid patch proposal envelope status")
    boundary = _require_object(payload, "patch_boundary", label="patch_proposal_envelope")
    if boundary.get("patch_body_included") is not False:
        raise SandboxedPatchProposalError("patch proposal envelope must not include patch body")
    if boundary.get("diff_body_included") is not False:
        raise SandboxedPatchProposalError("patch proposal envelope must not include diff body")
    forbidden_effects = (
        "implementation_execution_performed",
        "repository_mutation_performed",
        "customer_visible_action_performed",
        "external_publication_performed",
        "production_mutation_performed",
        "irreversible_effects_performed",
    )
    for key in forbidden_effects:
        if boundary.get(key) is not False:
            raise SandboxedPatchProposalError(f"patch proposal rehearsal must keep {key} false")
    checks = _require_object(payload, "checks", label="patch_proposal_envelope")
    if payload.get("status") == "allowed":
        required_true = (
            "spec_eval_execution_allowed",
            "sandbox_start_authorized",
            "rollback_plan_present",
            "test_plan_present",
            "human_reconstruction_present",
            "dual_loop_gate_allowed",
            "raw_patch_body_absent",
            "raw_diff_body_absent",
        )
        for key in required_true:
            if checks.get(key) is not True:
                raise SandboxedPatchProposalError(f"allowed patch proposal requires {key}")
        if boundary.get("proposal_scope") != "sandbox_local_refs_only":
            raise SandboxedPatchProposalError("allowed patch proposal must remain sandbox-local")
    if checks.get("repository_mutation_requested") is True and payload.get("status") != "blocked":
        raise SandboxedPatchProposalError("repository mutation request must block patch proposal")
    if checks.get("customer_visible_action_requested") is True and payload.get("status") != "blocked":
        raise SandboxedPatchProposalError("customer-visible action request must block patch proposal")
    if checks.get("external_publication_requested") is True and payload.get("status") != "blocked":
        raise SandboxedPatchProposalError("external publication request must block patch proposal")
    if checks.get("production_mutation_requested") is True and payload.get("status") != "blocked":
        raise SandboxedPatchProposalError("production mutation request must block patch proposal")
    return dict(payload)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    return {"sandboxed-patch-proposal-envelope.json": build_patch_proposal_envelope(case_id)}


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        envelope = validate_patch_proposal_envelope(cases[case_id]["sandboxed-patch-proposal-envelope.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": envelope["status"],
                "decision": envelope["decision"],
                "blocked_reasons": envelope["blocked_reasons"],
                "proposal_scope": envelope["patch_boundary"]["proposal_scope"],
            }
        )
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": "Prove an allowed Spec/Eval execution rehearsal can produce only a metadata-only sandbox-local patch proposal envelope before any repository mutation.",
        "source_chain": {
            "spec_eval_execution_rehearsal_report": "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.json",
            "allowed_execution_receipt": "fixtures/spec-eval-scenario-execution-rehearsal/pass/spec-eval-execution-rehearsal-receipt.json",
        },
        "case_reports": case_reports,
        "claim_boundary": {
            "current_claim": "A patch proposal can be prepared as sandbox-local metadata refs only when Spec/Eval, Controlled Failure, and Human Reconstruction gates pass.",
            "not_claimed": [
                "patch content generated",
                "repository changed",
                "customer handoff approved",
                "external publication approved",
                "production change approved",
            ],
        },
        "quality_gates": {
            "spec_eval_execution_allowed_required": True,
            "rollback_plan_required": True,
            "test_plan_required": True,
            "human_reconstruction_required": True,
            "raw_patch_body_rejected": True,
            "raw_diff_body_rejected": True,
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
    write_json(output_dir / "sandboxed-patch-proposal-rehearsal-report.json", report)
    return {
        "schema_version": "sandboxed-patch-proposal-rehearsal-cli-v1",
        "status": "ok",
        "case_ids": list(selected),
        "output_dir_ref": "configured-output-dir",
        "report": "sandboxed-patch-proposal-rehearsal-report.json",
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
