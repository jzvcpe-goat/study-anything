#!/usr/bin/env python3
"""Check or refresh release-facing generated evidence in dependency order."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Sequence, TypedDict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = (
    ROOT
    / ".cognitive-loop"
    / "artifacts"
    / "release"
    / "generated-evidence-topology-receipt.json"
)
SCHEMA_VERSION = "generated-evidence-topology-receipt-v1"
GRAPH_VERSION = "release-distribution-evidence-topology-v1"


class EvidenceTopologyError(RuntimeError):
    """Raised when the declared evidence graph cannot be executed safely."""


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    script: str
    refresh_args: tuple[str, ...]
    check_args: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    feedback_dependencies: tuple[str, ...] = ()

    def args_for(self, stage: str) -> tuple[str, ...]:
        if stage == "refresh":
            return (self.script, *self.refresh_args)
        if stage == "check":
            return (self.script, *self.check_args)
        raise EvidenceTopologyError(f"Unsupported execution stage: {stage}")


@dataclass(frozen=True)
class NodeRun:
    node_id: str
    stage: str
    status: str
    exit_code: int
    failure_kind: str | None
    duration_ms: int


class StageSummary(TypedDict):
    executed: int
    passed: int
    failed_node_ids: list[str]


class PassSummary(TypedDict):
    pass_index: int
    refresh: StageSummary
    check: StageSummary
    duration_ms: int


NODES: tuple[EvidenceNode, ...] = (
    EvidenceNode(
        "platform_agent_assets",
        "scripts/generate_platform_agent_assets.py",
        (),
        ("--check",),
    ),
    EvidenceNode(
        "platform_agent_replay",
        "scripts/generate_platform_agent_replay.py",
        (),
        ("--check",),
        dependencies=("platform_agent_assets",),
    ),
    EvidenceNode(
        "published_image_evidence",
        "scripts/generate_published_image_evidence.py",
        (),
        ("--check",),
    ),
    EvidenceNode(
        "release_asset_adoption",
        "scripts/generate_release_asset_adoption.py",
        (),
        ("--check",),
        dependencies=("published_image_evidence", "platform_agent_replay"),
    ),
    EvidenceNode(
        "release_asset_bootstrap",
        "scripts/generate_release_asset_bootstrap.py",
        (),
        ("--check",),
        dependencies=("release_asset_adoption",),
    ),
    EvidenceNode(
        "release_cleanroom_bootstrap",
        "scripts/generate_release_cleanroom_bootstrap.py",
        (),
        ("--check",),
        dependencies=("release_asset_bootstrap",),
    ),
    EvidenceNode(
        "platform_plugin_packs",
        "scripts/generate_platform_plugin_packs.py",
        (),
        ("--check",),
        dependencies=("platform_agent_assets",),
    ),
    EvidenceNode(
        "platform_plugin_downloads",
        "scripts/generate_platform_plugin_downloads.py",
        (),
        ("--check",),
        dependencies=("platform_plugin_packs",),
    ),
    EvidenceNode(
        "cbb_adoption_audit_assets",
        "scripts/generate_cbb_adoption_audit_assets.py",
        ("--write",),
        ("--check",),
    ),
    EvidenceNode(
        "cbb_controlled_adoption_outcomes",
        "scripts/verify_cbb_controlled_adoption_outcomes.py",
        (),
        ("--check",),
        dependencies=("cbb_adoption_audit_assets",),
    ),
    EvidenceNode(
        "cbb_external_adoption_attestation",
        "scripts/verify_cbb_external_adoption_attestation.py",
        (),
        ("--check",),
        dependencies=(
            "cbb_adoption_audit_assets",
            "cbb_controlled_adoption_outcomes",
        ),
    ),
    EvidenceNode(
        "cbb_external_audit_intake",
        "scripts/verify_cbb_external_audit_intake.py",
        (),
        ("--check",),
        dependencies=("cbb_adoption_audit_assets",),
    ),
    EvidenceNode(
        "delivery_trust_case_pack",
        "scripts/generate_delivery_trust_case_pack.py",
        (),
        ("--check",),
    ),
    EvidenceNode(
        "delivery_trust_case_pack_consumer",
        "scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py",
        ("--write",),
        ("--check",),
        dependencies=("delivery_trust_case_pack",),
    ),
    EvidenceNode(
        "trust_evidence_handoff_pack",
        "scripts/generate_trust_evidence_handoff_pack.py",
        ("--write",),
        ("--check",),
        dependencies=("delivery_trust_case_pack_consumer",),
    ),
    EvidenceNode(
        "trust_evidence_handoff_consumer",
        "scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py",
        ("--write",),
        ("--check",),
        dependencies=("trust_evidence_handoff_pack",),
    ),
    EvidenceNode(
        "trust_evidence_acceptance_drill",
        "scripts/verify_trust_evidence_acceptance_drill.py",
        ("--write",),
        ("--check",),
        dependencies=("trust_evidence_handoff_consumer",),
    ),
    EvidenceNode(
        "controlled_handoff_runbook",
        "scripts/verify_controlled_handoff_runbook.py",
        ("--write",),
        ("--check",),
        dependencies=("trust_evidence_acceptance_drill",),
    ),
    EvidenceNode(
        "customer_delivery_trust_envelope",
        "scripts/verify_customer_delivery_trust_envelope.py",
        ("--write",),
        ("--check",),
        dependencies=("controlled_handoff_runbook",),
    ),
    EvidenceNode(
        "customer_delivery_rehearsal",
        "scripts/verify_customer_delivery_rehearsal.py",
        ("--write",),
        ("--check",),
        dependencies=("customer_delivery_trust_envelope",),
    ),
    EvidenceNode(
        "code_review_operator_rehearsal",
        "scripts/verify_code_review_operator_handoff_rehearsal.py",
        ("--write",),
        ("--check",),
        dependencies=("customer_delivery_rehearsal",),
    ),
    EvidenceNode(
        "client_report_operator_rehearsal",
        "scripts/verify_client_report_operator_handoff_rehearsal.py",
        ("--write",),
        ("--check",),
        dependencies=("customer_delivery_rehearsal",),
    ),
    EvidenceNode(
        "support_response_operator_rehearsal",
        "scripts/verify_support_response_operator_handoff_rehearsal.py",
        ("--write",),
        ("--check",),
        dependencies=("customer_delivery_rehearsal",),
    ),
    EvidenceNode(
        "operator_handoff_rehearsal_contract",
        "scripts/verify_operator_handoff_rehearsal_contract.py",
        ("--write",),
        ("--check",),
        dependencies=(
            "code_review_operator_rehearsal",
            "client_report_operator_rehearsal",
            "support_response_operator_rehearsal",
        ),
    ),
    EvidenceNode(
        "external_feedback_receipt",
        "scripts/verify_external_feedback_receipt.py",
        ("--write",),
        ("--check",),
        dependencies=("operator_handoff_rehearsal_contract",),
    ),
    EvidenceNode(
        "external_feedback_backlog",
        "scripts/verify_external_feedback_backlog_bridge.py",
        ("--write",),
        ("--check",),
        dependencies=("external_feedback_receipt",),
    ),
    EvidenceNode(
        "product_owner_prioritization",
        "scripts/verify_product_owner_prioritization_gate.py",
        ("--write",),
        ("--check",),
        dependencies=("external_feedback_backlog",),
    ),
    EvidenceNode(
        "product_spec_eval_authoring",
        "scripts/verify_product_spec_eval_authoring_gate.py",
        ("--write",),
        ("--check",),
        dependencies=("product_owner_prioritization",),
    ),
    EvidenceNode(
        "product_loop_brief_intake",
        "scripts/verify_product_loop_brief_intake.py",
        ("--write",),
        ("--check",),
        dependencies=("product_spec_eval_authoring",),
    ),
    EvidenceNode(
        "end_to_end_trust_chain",
        "scripts/verify_end_to_end_trust_chain_harness.py",
        ("--write",),
        ("--check",),
        dependencies=("product_loop_brief_intake",),
    ),
    EvidenceNode(
        "real_adopter_scenario_import",
        "scripts/verify_real_adopter_scenario_import.py",
        ("--write",),
        ("--check",),
        dependencies=("end_to_end_trust_chain",),
    ),
    EvidenceNode(
        "spec_eval_scenario_rehearsal",
        "scripts/verify_spec_eval_scenario_execution_rehearsal.py",
        ("--write",),
        ("--check",),
        dependencies=("real_adopter_scenario_import",),
    ),
    EvidenceNode(
        "sandboxed_patch_proposal_rehearsal",
        "scripts/verify_sandboxed_patch_proposal_rehearsal.py",
        ("--write",),
        ("--check",),
        dependencies=("spec_eval_scenario_rehearsal",),
    ),
    EvidenceNode(
        "patch_operator_handoff_bridge",
        "scripts/verify_patch_proposal_operator_handoff_bridge.py",
        ("--write",),
        ("--check",),
        dependencies=("sandboxed_patch_proposal_rehearsal",),
    ),
    EvidenceNode(
        "patch_acceptance_drill",
        "scripts/verify_patch_proposal_acceptance_drill.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_operator_handoff_bridge",),
    ),
    EvidenceNode(
        "patch_external_work_order_pack",
        "scripts/verify_patch_proposal_external_work_order_pack.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_acceptance_drill",),
    ),
    EvidenceNode(
        "patch_external_operator_completion",
        "scripts/verify_patch_proposal_external_operator_completion.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_external_work_order_pack",),
    ),
    EvidenceNode(
        "patch_customer_handoff_boundary",
        "scripts/verify_patch_proposal_customer_handoff_boundary_gate.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_external_operator_completion",),
    ),
    EvidenceNode(
        "patch_customer_delivery_envelope",
        "scripts/verify_patch_proposal_customer_delivery_envelope.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_customer_handoff_boundary",),
    ),
    EvidenceNode(
        "patch_customer_delivery_rehearsal",
        "scripts/verify_patch_proposal_customer_delivery_rehearsal.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_customer_delivery_envelope",),
    ),
    EvidenceNode(
        "patch_customer_delivery_outcome",
        "scripts/verify_patch_proposal_customer_delivery_outcome_receipt.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_customer_delivery_rehearsal",),
    ),
    EvidenceNode(
        "patch_customer_feedback_intake",
        "scripts/verify_patch_proposal_customer_feedback_intake_receipt.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_customer_delivery_outcome",),
    ),
    EvidenceNode(
        "dual_loop_scenario_harness",
        "scripts/verify_dual_loop_scenario_harness.py",
        ("--write",),
        ("--check",),
        dependencies=("patch_customer_feedback_intake",),
    ),
    EvidenceNode(
        "dual_loop_trust_scenario_pack",
        "scripts/generate_dual_loop_trust_scenario_pack.py",
        (),
        ("--check",),
        dependencies=("dual_loop_scenario_harness",),
    ),
    EvidenceNode(
        "dual_loop_trust_scenario_pack_verification",
        "scripts/verify_dual_loop_trust_scenario_pack.py",
        ("--check",),
        ("--check",),
        dependencies=("dual_loop_trust_scenario_pack",),
    ),
    EvidenceNode(
        "dual_loop_trust_pack_consumer",
        "scripts/verify_dual_loop_trust_pack_consumer_walkthrough.py",
        ("--write",),
        ("--check",),
        dependencies=("dual_loop_trust_scenario_pack_verification",),
    ),
    EvidenceNode(
        "external_security_audit_pack",
        "scripts/generate_external_security_audit_pack.py",
        (),
        ("--check",),
        dependencies=(
            "cbb_controlled_adoption_outcomes",
            "cbb_external_adoption_attestation",
            "cbb_external_audit_intake",
        ),
    ),
    EvidenceNode(
        "platform_handoff_checklist",
        "scripts/verify_platform_handoff_checklist.py",
        ("--write",),
        ("--check",),
        dependencies=(
            "published_image_evidence",
            "release_asset_adoption",
            "platform_plugin_downloads",
        ),
    ),
    EvidenceNode(
        "platform_bundle_manifest",
        "scripts/generate_platform_bundle_manifest.py",
        (),
        ("--check",),
        dependencies=(
            "external_security_audit_pack",
            "release_cleanroom_bootstrap",
            "platform_handoff_checklist",
            "platform_plugin_downloads",
            "dual_loop_trust_pack_consumer",
        ),
        feedback_dependencies=(
            "platform_operator_drill",
            "platform_submission_dry_run",
            "schema_pack_consumer",
            "schema_pack_consumer_failures",
            "pack_extract_smoke",
            "review_agent_workflow_install_smoke",
            "review_agent_adoption_drill",
            "maintainer_acceptance_ledger",
            "adopter_evidence_archive",
        ),
    ),
    EvidenceNode(
        "platform_adoption_pack",
        "scripts/generate_platform_adoption_pack.py",
        (),
        ("--check",),
        dependencies=("platform_bundle_manifest",),
        feedback_dependencies=(
            "platform_operator_drill",
            "platform_submission_dry_run",
            "schema_pack_consumer",
            "schema_pack_consumer_failures",
            "pack_extract_smoke",
            "review_agent_workflow_install_smoke",
            "review_agent_adoption_drill",
            "maintainer_acceptance_ledger",
            "adopter_evidence_archive",
        ),
    ),
    EvidenceNode(
        "platform_operator_drill",
        "scripts/verify_platform_operator_drill.py",
        ("--write",),
        ("--check",),
        dependencies=("platform_adoption_pack",),
    ),
    EvidenceNode(
        "platform_submission_dry_run",
        "scripts/verify_platform_submission_dry_run.py",
        ("--write",),
        ("--check",),
        dependencies=("platform_adoption_pack",),
    ),
    EvidenceNode(
        "schema_pack_consumer",
        "scripts/verify_cognitive_loop_schema_pack_consumer.py",
        ("--write",),
        ("--check",),
        dependencies=("platform_adoption_pack",),
    ),
    EvidenceNode(
        "schema_pack_consumer_failures",
        "scripts/verify_cognitive_loop_schema_pack_consumer_failures.py",
        ("--write",),
        ("--check",),
        dependencies=("platform_adoption_pack",),
    ),
    EvidenceNode(
        "pack_extract_smoke",
        "scripts/verify_cognitive_loop_pack_extract_smoke.py",
        ("--write",),
        ("--check",),
        dependencies=("platform_adoption_pack",),
    ),
    EvidenceNode(
        "review_agent_workflow_install_smoke",
        "scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py",
        ("--write",),
        ("--check",),
        dependencies=("platform_adoption_pack",),
    ),
    EvidenceNode(
        "review_agent_adoption_drill",
        "scripts/verify_cognitive_loop_review_agent_adoption_drill.py",
        ("--write",),
        ("--check",),
        dependencies=("platform_adoption_pack",),
    ),
    EvidenceNode(
        "maintainer_acceptance_ledger",
        "scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py",
        ("--write",),
        ("--check",),
        dependencies=(
            "published_image_evidence",
            "platform_bundle_manifest",
            "platform_adoption_pack",
        ),
    ),
    EvidenceNode(
        "adopter_evidence_archive",
        "scripts/generate_adopter_evidence_archive.py",
        (),
        ("--check",),
        dependencies=("published_image_evidence", "platform_operator_drill"),
    ),
)


Runner = Callable[[EvidenceNode, str, int], NodeRun]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_and_order(nodes: Sequence[EvidenceNode]) -> tuple[EvidenceNode, ...]:
    by_id: dict[str, EvidenceNode] = {}
    for node in nodes:
        if node.node_id in by_id:
            raise EvidenceTopologyError(f"Duplicate evidence node: {node.node_id}")
        by_id[node.node_id] = node

    known = set(by_id)
    for node in nodes:
        missing = (set(node.dependencies) | set(node.feedback_dependencies)) - known
        if missing:
            raise EvidenceTopologyError(
                f"Evidence node {node.node_id} has unknown dependencies: {sorted(missing)}"
            )
        if node.node_id in node.dependencies or node.node_id in node.feedback_dependencies:
            raise EvidenceTopologyError(f"Evidence node {node.node_id} depends on itself")

    remaining = {node.node_id: set(node.dependencies) for node in nodes}
    ordered: list[EvidenceNode] = []
    while remaining:
        ready = [
            node.node_id
            for node in nodes
            if node.node_id in remaining and not remaining[node.node_id]
        ]
        if not ready:
            raise EvidenceTopologyError(
                f"Hard dependency cycle detected: {sorted(remaining)}"
            )
        for node_id in ready:
            ordered.append(by_id[node_id])
            del remaining[node_id]
            for dependencies in remaining.values():
                dependencies.discard(node_id)
    return tuple(ordered)


def graph_fingerprint(nodes: Sequence[EvidenceNode]) -> str:
    payload = [
        {
            "node_id": node.node_id,
            "script": node.script,
            "refresh_args": node.refresh_args,
            "check_args": node.check_args,
            "dependencies": node.dependencies,
            "feedback_dependencies": node.feedback_dependencies,
        }
        for node in nodes
    ]
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def run_subprocess(node: EvidenceNode, stage: str, timeout_seconds: int) -> NodeRun:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, *node.args_for(stage)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = completed.returncode
        failure_kind = None if exit_code == 0 else "command_failed"
    except subprocess.TimeoutExpired:
        exit_code = 124
        failure_kind = "timeout"
    duration_ms = max(0, round((time.perf_counter() - started) * 1000))
    return NodeRun(
        node_id=node.node_id,
        stage=stage,
        status="pass" if exit_code == 0 else "failed",
        exit_code=exit_code,
        failure_kind=failure_kind,
        duration_ms=duration_ms,
    )


def public_rerun(node: EvidenceNode, stage: str) -> str:
    return " ".join(("python3", *node.args_for(stage)))


def run_stage(
    nodes: Sequence[EvidenceNode],
    stage: str,
    *,
    timeout_seconds: int,
    runner: Runner,
    emit_progress: bool,
) -> list[NodeRun]:
    results: list[NodeRun] = []
    for node in nodes:
        result = runner(node, stage, timeout_seconds)
        results.append(result)
        if not emit_progress:
            continue
        if result.status == "pass":
            print(f"ok    [{stage}] {node.node_id}")
        else:
            print(
                f"fail  [{stage}] {node.node_id}: {result.failure_kind}; "
                f"rerun `{public_rerun(node, stage)}`",
                file=sys.stderr,
            )
    return results


def summarize_pass(
    pass_index: int,
    refresh: Sequence[NodeRun],
    checks: Sequence[NodeRun],
) -> PassSummary:
    return {
        "pass_index": pass_index,
        "refresh": {
            "executed": len(refresh),
            "passed": sum(result.status == "pass" for result in refresh),
            "failed_node_ids": [result.node_id for result in refresh if result.status != "pass"],
        },
        "check": {
            "executed": len(checks),
            "passed": sum(result.status == "pass" for result in checks),
            "failed_node_ids": [result.node_id for result in checks if result.status != "pass"],
        },
        "duration_ms": sum(result.duration_ms for result in (*refresh, *checks)),
    }


def execute_topology(
    *,
    mode: str,
    nodes: Sequence[EvidenceNode] = NODES,
    timeout_seconds: int = 120,
    max_passes: int = 3,
    runner: Runner = run_subprocess,
    emit_progress: bool = True,
) -> dict[str, object]:
    ordered = validate_and_order(nodes)
    started_at = utc_now()
    pass_summaries: list[PassSummary] = []
    converged = False

    if mode == "check":
        checks = run_stage(
            ordered,
            "check",
            timeout_seconds=timeout_seconds,
            runner=runner,
            emit_progress=emit_progress,
        )
        pass_summaries.append(summarize_pass(1, (), checks))
        converged = all(result.status == "pass" for result in checks)
    elif mode == "refresh":
        for pass_index in range(1, max_passes + 1):
            refresh = run_stage(
                ordered,
                "refresh",
                timeout_seconds=timeout_seconds,
                runner=runner,
                emit_progress=emit_progress,
            )
            checks = run_stage(
                ordered,
                "check",
                timeout_seconds=timeout_seconds,
                runner=runner,
                emit_progress=emit_progress,
            )
            pass_summaries.append(summarize_pass(pass_index, refresh, checks))
            refresh_passed = all(result.status == "pass" for result in refresh)
            checks_passed = all(result.status == "pass" for result in checks)
            if refresh_passed and checks_passed:
                converged = True
                break
            if not refresh_passed:
                break
    else:
        raise EvidenceTopologyError(f"Unsupported mode: {mode}")

    failed_node_ids = sorted(
        {
            node_id
            for summary in pass_summaries[-1:]
            for node_id in (
                *summary["refresh"]["failed_node_ids"],
                *summary["check"]["failed_node_ids"],
            )
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if converged else "blocked",
        "mode": mode,
        "started_at": started_at,
        "finished_at": utc_now(),
        "graph": {
            "version": GRAPH_VERSION,
            "fingerprint_sha256": graph_fingerprint(ordered),
            "node_count": len(ordered),
            "hard_dependency_count": sum(len(node.dependencies) for node in ordered),
            "feedback_dependency_count": sum(
                len(node.feedback_dependencies) for node in ordered
            ),
            "node_ids": [node.node_id for node in ordered],
        },
        "execution": {
            "max_passes": 1 if mode == "check" else max_passes,
            "passes_completed": len(pass_summaries),
            "converged": converged,
            "failed_node_ids": failed_node_ids,
            "passes": pass_summaries,
        },
        "privacy": {
            "metadata_only": True,
            "command_stdout_included": False,
            "command_stderr_included": False,
            "local_absolute_paths_included": False,
            "environment_values_included": False,
            "secrets_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "model_calls_performed": False,
            "network_required": False,
            "production_mutation_performed": False,
            "repository_generated_assets_mutated": mode == "refresh",
        },
        "claim_boundary": (
            "This receipt covers the declared release-distribution evidence topology only. "
            "It does not prove every generated repository artifact, product correctness, "
            "production availability, or commercial readiness."
        ),
    }


def write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check every declared evidence node once.")
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh in hard-dependency order until feedback edges converge.",
    )
    parser.add_argument("--max-passes", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()

    if args.max_passes < 1:
        parser.error("--max-passes must be at least 1")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be at least 1")
    receipt_path = args.receipt
    if not receipt_path.is_absolute():
        receipt_path = ROOT / receipt_path
    try:
        receipt = execute_topology(
            mode="refresh" if args.refresh else "check",
            timeout_seconds=args.timeout_seconds,
            max_passes=args.max_passes,
        )
    except EvidenceTopologyError as exc:
        print(f"generated_evidence_topology failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    write_receipt(receipt_path, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if receipt["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
