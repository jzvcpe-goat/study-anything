#!/usr/bin/env python3
"""Build metadata-only Spec/Eval Scenario Execution Rehearsal artifacts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_protocol, dual_loop, product_loop_harness  # noqa: E402


ACCEPTANCE_RECEIPT_SCHEMA_VERSION = "spec-eval-acceptance-receipt-v1"
EXECUTION_RECEIPT_SCHEMA_VERSION = "spec-eval-execution-rehearsal-receipt-v1"
REPORT_SCHEMA_VERSION = "spec-eval-scenario-execution-rehearsal-v1"

DEFAULT_OUTPUT_DIR = ROOT / ".cognitive-loop" / "artifacts" / "spec-eval-scenario-execution-rehearsal"
UPSTREAM_FIXTURE_DIR = ROOT / "fixtures" / "real-adopter-scenario-import" / "pass"

CASE_IDS = (
    "pass",
    "blocked-missing-sandbox",
    "blocked-missing-human-reconstruction",
    "blocked-ai-review-only",
    "blocked-customer-visible-action",
    "blocked-production-mutation",
)

PRIVACY_FLAGS = {
    **dual_loop.PRIVACY_FLAGS,
    "raw_spec_eval_body_included": False,
    "raw_eval_prompt_included": False,
    "raw_adopter_feedback_included": False,
    "customer_payload_included": False,
    "production_payload_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}

ISOLATION = dict(dual_loop.ISOLATION_BOUNDARY)


class SpecEvalRehearsalError(ValueError):
    """Raised when rehearsal artifacts are unsafe or invalid."""


def dump_json(payload: Mapping[str, Any]) -> str:
    return cbb_protocol.dump_json(dict(payload))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SpecEvalRehearsalError(f"Expected JSON object: {path}")
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
        raise SpecEvalRehearsalError(f"{label}.{key} must be an object")
    return value


def _validate_privacy(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.assert_metadata_only(payload, label=label)
    privacy = _require_object(payload, "privacy", label=label)
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise SpecEvalRehearsalError(f"{label}.privacy.{key} must be {expected!r}")
    isolation = _require_object(payload, "isolation", label=label)
    for key, expected in ISOLATION.items():
        if isolation.get(key) is not expected:
            raise SpecEvalRehearsalError(f"{label}.isolation.{key} must be {expected!r}")


def upstream_artifacts() -> dict[str, dict[str, Any]]:
    brief = load_json(UPSTREAM_FIXTURE_DIR / "product-spec-eval-brief.json")
    product_loop_run = product_loop_harness.validate_product_loop_run(
        load_json(UPSTREAM_FIXTURE_DIR / "product-loop-run.json")
    )
    scenario = product_loop_harness.validate_product_loop_scenario(
        load_json(UPSTREAM_FIXTURE_DIR / "product-loop-scenario.json")
    )
    if product_loop_run["status"] != "allowed":
        raise SpecEvalRehearsalError("Upstream Product Loop run must be allowed")
    return {
        "product_spec_eval_brief": brief,
        "product_loop_run": product_loop_run,
        "product_loop_scenario": scenario,
    }


def _case_flags(case_id: str) -> dict[str, bool]:
    if case_id not in CASE_IDS:
        raise SpecEvalRehearsalError(f"Unknown case id: {case_id}")
    return {
        "sandbox_present": case_id != "blocked-missing-sandbox",
        "human_reconstruction_present": case_id != "blocked-missing-human-reconstruction",
        "ai_review_only": case_id == "blocked-ai-review-only",
        "customer_visible_action_requested": case_id == "blocked-customer-visible-action",
        "production_mutation_requested": case_id == "blocked-production-mutation",
    }


def build_acceptance_receipt(case_id: str, upstream: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    flags = _case_flags(case_id)
    product_loop_run = upstream["product_loop_run"]
    brief = upstream["product_spec_eval_brief"]
    gates = {
        "product_loop_run_allowed": product_loop_run.get("status") == "allowed",
        "real_agent_quality_gate_defined": True,
        "version_drift_gate_defined": True,
        "proxy_workaround_gate_defined": True,
        "deterministic_quality_gap_covered": True,
        "ai_review_only_evidence": flags["ai_review_only"],
        "customer_visible_action_requested": flags["customer_visible_action_requested"],
        "production_mutation_requested": flags["production_mutation_requested"],
    }
    blocked_reasons: list[str] = []
    if not gates["product_loop_run_allowed"]:
        blocked_reasons.append("product_loop_run_not_allowed")
    if gates["ai_review_only_evidence"]:
        blocked_reasons.append("ai_review_only_evidence_rejected")
    if gates["customer_visible_action_requested"]:
        blocked_reasons.append("customer_visible_action_rejected")
    if gates["production_mutation_requested"]:
        blocked_reasons.append("production_mutation_rejected")
    status = "passed" if not blocked_reasons else "blocked"
    receipt = {
        **_base(ACCEPTANCE_RECEIPT_SCHEMA_VERSION),
        "receipt_id": f"spec-eval-acceptance-{case_id}",
        "case_id": case_id,
        "source": {
            "source_type": "real_adopter_scenario_import",
            "brief_ref": "fixtures/real-adopter-scenario-import/pass/product-spec-eval-brief.json",
            "brief_hash": artifact_hash(brief),
            "product_loop_run_ref": "fixtures/real-adopter-scenario-import/pass/product-loop-run.json",
            "product_loop_run_hash": artifact_hash(product_loop_run),
        },
        "status": status,
        "decision": "accept_spec_eval_execution_candidate" if status == "passed" else "block_spec_eval_execution_candidate",
        "blocked_reasons": blocked_reasons,
        "eval_scenario": {
            "scenario_ref": "real-agent-quality-and-version-drift-gate",
            "acceptance_receipt_only": True,
            "raw_eval_prompt_included": False,
            "execution_authority_granted": False,
        },
        "gates": gates,
        "claim_boundary": {
            "current_claim": "The metadata-only spec/eval brief is eligible for sandboxed execution rehearsal.",
            "not_claimed": [
                "real implementation completed",
                "customer-visible reply approved",
                "production deployment approved",
                "general model quality certified",
            ],
        },
    }
    return validate_acceptance_receipt(receipt)


def _dual_loop_artifacts(case_id: str, flags: Mapping[str, bool]) -> dict[str, dict[str, Any] | None]:
    contract = dual_loop.failure_contract_demo()
    contract["contract_id"] = f"failure-contract-spec-eval-{case_id}"
    contract["task_ref"] = f"task:spec-eval-execution-rehearsal:{case_id}"
    contract["candidate_artifact_ref"] = "artifact:spec-eval-brief-metadata-only"
    contract = dual_loop.validate_failure_contract(contract)

    sandbox = None
    if flags["sandbox_present"]:
        sandbox_payload = dual_loop.sandbox_receipt_demo(within_budget=True, status="passed")
        sandbox_payload["contract_id"] = contract["contract_id"]
        sandbox_payload["receipt_id"] = f"sandbox-receipt-spec-eval-{case_id}"
        sandbox_payload["sandbox_run_id"] = f"sandbox-run-spec-eval-{case_id}"
        sandbox = dual_loop.validate_sandbox_receipt(sandbox_payload)

    trace = None
    summary = None
    if flags["human_reconstruction_present"]:
        trace_payload = dual_loop.attention_trace_demo()
        trace_payload["contract_id"] = contract["contract_id"]
        trace_payload["trace_id"] = f"attention-trace-spec-eval-{case_id}"
        trace = dual_loop.validate_attention_trace(trace_payload)
        summary_payload = dual_loop.attention_summary_demo(status="passed")
        summary_payload["contract_id"] = contract["contract_id"]
        summary_payload["trace_id"] = trace["trace_id"]
        summary_payload["summary_id"] = f"attention-summary-spec-eval-{case_id}"
        summary = dual_loop.validate_attention_summary(summary_payload)

    gate = None
    if sandbox is not None:
        gate_payload = dual_loop.evaluate_dual_loop_gate(contract, sandbox, summary)
        gate_payload["gate_id"] = f"dual-loop-gate-spec-eval-{case_id}"
        gate = dual_loop.validate_gate_receipt(gate_payload)

    return {
        "failure-contract.json": contract,
        "sandbox-receipt.json": sandbox,
        "attention-reconstruction-trace.json": trace,
        "attention-reconstruction-summary.json": summary,
        "dual-loop-gate-receipt.json": gate,
    }


def build_execution_receipt(
    case_id: str,
    acceptance: Mapping[str, Any],
    dual_loop_artifacts: Mapping[str, Mapping[str, Any] | None],
) -> dict[str, Any]:
    flags = _case_flags(case_id)
    sandbox = dual_loop_artifacts.get("sandbox-receipt.json")
    attention_summary = dual_loop_artifacts.get("attention-reconstruction-summary.json")
    gate = dual_loop_artifacts.get("dual-loop-gate-receipt.json")
    checks = {
        "acceptance_receipt_passed": acceptance.get("status") == "passed",
        "controlled_failure_sandbox_present": sandbox is not None,
        "sandbox_within_budget": bool(sandbox and sandbox["risk_budget"]["within_budget"]),
        "sandbox_failures_contained": bool(
            sandbox
            and sandbox.get("status") == "passed"
            and all(item.get("propagated") is False for item in sandbox.get("observed_failures", []))
        ),
        "human_reconstruction_present": attention_summary is not None,
        "human_reconstruction_passed": bool(attention_summary and attention_summary.get("status") == "passed"),
        "dual_loop_gate_allowed": bool(gate and gate.get("status") == "allowed"),
        "ai_review_only_evidence": flags["ai_review_only"],
        "customer_visible_action_requested": flags["customer_visible_action_requested"],
        "production_mutation_requested": flags["production_mutation_requested"],
    }
    reasons: list[str] = []
    if not checks["acceptance_receipt_passed"]:
        reasons.extend(acceptance.get("blocked_reasons", ["acceptance_receipt_blocked"]))
    if not checks["controlled_failure_sandbox_present"]:
        reasons.append("controlled_failure_sandbox_missing")
    if sandbox is not None and not checks["sandbox_within_budget"]:
        reasons.append("sandbox_risk_outside_budget")
    if sandbox is not None and not checks["sandbox_failures_contained"]:
        reasons.append("sandbox_failures_not_contained")
    if not checks["human_reconstruction_present"]:
        reasons.append("human_reconstruction_missing")
    elif not checks["human_reconstruction_passed"]:
        reasons.append("human_reconstruction_failed")
    if gate is not None and not checks["dual_loop_gate_allowed"]:
        reasons.extend(gate.get("reasons", ["dual_loop_gate_blocked"]))
    if checks["customer_visible_action_requested"]:
        reasons.append("customer_visible_action_rejected")
    if checks["production_mutation_requested"]:
        reasons.append("production_mutation_rejected")
    if checks["ai_review_only_evidence"]:
        reasons.append("ai_review_only_evidence_rejected")
    unique_reasons = list(dict.fromkeys(reasons))
    allowed = not unique_reasons
    receipt = {
        **_base(EXECUTION_RECEIPT_SCHEMA_VERSION),
        "receipt_id": f"spec-eval-execution-rehearsal-{case_id}",
        "case_id": case_id,
        "status": "allowed" if allowed else "blocked",
        "decision": "start_sandboxed_implementation_rehearsal" if allowed else "block_spec_eval_execution",
        "blocked_reasons": unique_reasons,
        "source_refs": {
            "acceptance_receipt_ref": "spec-eval-acceptance-receipt.json",
            "failure_contract_ref": "failure-contract.json",
            "sandbox_receipt_ref": "sandbox-receipt.json" if sandbox is not None else None,
            "attention_summary_ref": "attention-reconstruction-summary.json" if attention_summary is not None else None,
            "dual_loop_gate_ref": "dual-loop-gate-receipt.json" if gate is not None else None,
        },
        "execution_boundary": {
            "authorized_boundary": "controlled_failure_sandbox" if allowed else None,
            "implementation_execution_performed": False,
            "sandbox_start_authorized": allowed,
            "customer_visible_action_performed": False,
            "production_mutation_performed": False,
            "external_publication_performed": False,
        },
        "checks": checks,
        "claim_boundary": {
            "current_claim": "Sandboxed implementation rehearsal may start only when Product Loop and Dual Loop gates both pass.",
            "not_claimed": [
                "implementation completed",
                "customer delivery approved",
                "production mutation approved",
                "model output globally correct",
            ],
        },
    }
    return validate_execution_receipt(receipt)


def validate_acceptance_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_privacy(payload, label=ACCEPTANCE_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != ACCEPTANCE_RECEIPT_SCHEMA_VERSION:
        raise SpecEvalRehearsalError("invalid acceptance receipt schema_version")
    if payload.get("status") not in ("passed", "blocked"):
        raise SpecEvalRehearsalError("invalid acceptance receipt status")
    gates = _require_object(payload, "gates", label="acceptance_receipt")
    if gates.get("customer_visible_action_requested") is True and payload.get("status") != "blocked":
        raise SpecEvalRehearsalError("customer-visible action must block acceptance")
    if gates.get("production_mutation_requested") is True and payload.get("status") != "blocked":
        raise SpecEvalRehearsalError("production mutation must block acceptance")
    if gates.get("ai_review_only_evidence") is True and payload.get("status") != "blocked":
        raise SpecEvalRehearsalError("AI-review-only evidence must block acceptance")
    return dict(payload)


def validate_execution_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    _validate_privacy(payload, label=EXECUTION_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != EXECUTION_RECEIPT_SCHEMA_VERSION:
        raise SpecEvalRehearsalError("invalid execution receipt schema_version")
    if payload.get("status") not in ("allowed", "blocked"):
        raise SpecEvalRehearsalError("invalid execution receipt status")
    checks = _require_object(payload, "checks", label="execution_receipt")
    boundary = _require_object(payload, "execution_boundary", label="execution_receipt")
    if boundary.get("implementation_execution_performed") is not False:
        raise SpecEvalRehearsalError("rehearsal must not execute implementation work")
    if boundary.get("customer_visible_action_performed") is not False:
        raise SpecEvalRehearsalError("rehearsal must not perform customer-visible action")
    if boundary.get("production_mutation_performed") is not False:
        raise SpecEvalRehearsalError("rehearsal must not mutate production")
    if payload.get("status") == "allowed":
        required_true = (
            "acceptance_receipt_passed",
            "controlled_failure_sandbox_present",
            "sandbox_within_budget",
            "sandbox_failures_contained",
            "human_reconstruction_present",
            "human_reconstruction_passed",
            "dual_loop_gate_allowed",
        )
        for key in required_true:
            if checks.get(key) is not True:
                raise SpecEvalRehearsalError(f"allowed execution receipt requires {key}")
        if boundary.get("authorized_boundary") != "controlled_failure_sandbox":
            raise SpecEvalRehearsalError("allowed execution must start only in controlled failure sandbox")
    return dict(payload)


def build_case_artifacts(case_id: str) -> dict[str, dict[str, Any]]:
    upstream = upstream_artifacts()
    acceptance = build_acceptance_receipt(case_id, upstream)
    flags = _case_flags(case_id)
    dual_artifacts = _dual_loop_artifacts(case_id, flags)
    execution = build_execution_receipt(case_id, acceptance, dual_artifacts)
    artifacts: dict[str, dict[str, Any]] = {
        "spec-eval-acceptance-receipt.json": acceptance,
        "spec-eval-execution-rehearsal-receipt.json": execution,
    }
    for name, payload in dual_artifacts.items():
        if payload is not None:
            artifacts[name] = payload
    return artifacts


def build_all_case_artifacts() -> dict[str, dict[str, dict[str, Any]]]:
    return {case_id: build_case_artifacts(case_id) for case_id in CASE_IDS}


def build_report(cases: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    case_reports = []
    for case_id in CASE_IDS:
        artifacts = cases[case_id]
        execution = validate_execution_receipt(artifacts["spec-eval-execution-rehearsal-receipt.json"])
        case_reports.append(
            {
                "case_id": case_id,
                "status": execution["status"],
                "decision": execution["decision"],
                "blocked_reasons": execution["blocked_reasons"],
                "artifact_count": len(artifacts),
                "sandbox_start_authorized": execution["execution_boundary"]["sandbox_start_authorized"],
            }
        )
    report = {
        **_base(REPORT_SCHEMA_VERSION),
        "status": "pass",
        "purpose": "Prove Product Spec/Eval execution can start only as a controlled failure sandbox rehearsal with active human boundary reconstruction.",
        "source_chain": {
            "real_adopter_import_report": "platform/generated/study-anything-real-adopter-scenario-import.json",
            "product_spec_eval_brief": "fixtures/real-adopter-scenario-import/pass/product-spec-eval-brief.json",
            "product_loop_run": "fixtures/real-adopter-scenario-import/pass/product-loop-run.json",
        },
        "case_reports": case_reports,
        "claim_boundary": {
            "current_claim": "A metadata-only spec/eval brief can authorize sandboxed implementation rehearsal only after Product Loop and Dual Loop gates pass.",
            "not_claimed": [
                "implementation was executed",
                "customer-visible action was performed",
                "production mutation was performed",
                "real model call was performed",
            ],
        },
        "quality_gates": {
            "product_loop_run_required": True,
            "controlled_failure_sandbox_required": True,
            "human_reconstruction_required": True,
            "ai_review_only_rejected": True,
            "customer_visible_action_rejected": True,
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
    write_json(output_dir / "spec-eval-scenario-execution-rehearsal-report.json", report)
    return {
        "schema_version": "spec-eval-scenario-execution-rehearsal-cli-v1",
        "status": "ok",
        "case_ids": list(selected),
        "output_dir": str(output_dir),
        "report": "spec-eval-scenario-execution-rehearsal-report.json",
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
