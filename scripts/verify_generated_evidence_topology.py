#!/usr/bin/env python3
"""Verify generated-evidence topology, convergence, and privacy behavior."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generated_evidence_topology import (  # noqa: E402
    GRAPH_VERSION,
    NODES,
    EvidenceNode,
    EvidenceTopologyError,
    NodeRun,
    execute_topology,
    graph_fingerprint,
    validate_and_order,
)


class VerificationError(RuntimeError):
    """Raised when evidence topology behavior regresses."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def run_result(node: EvidenceNode, stage: str, status: str) -> NodeRun:
    return NodeRun(
        node_id=node.node_id,
        stage=stage,
        status=status,
        exit_code=0 if status == "pass" else 1,
        failure_kind=None if status == "pass" else "command_failed",
        duration_ms=1,
    )


def verify() -> dict[str, object]:
    ordered = validate_and_order(NODES)
    positions = {node.node_id: index for index, node in enumerate(ordered)}
    for node in ordered:
        for dependency in node.dependencies:
            require(
                positions[dependency] < positions[node.node_id],
                f"Hard dependency order drifted: {dependency} -> {node.node_id}",
            )

    try:
        validate_and_order(
            (
                EvidenceNode("a", "scripts/a.py", (), (), dependencies=("b",)),
                EvidenceNode("b", "scripts/b.py", (), (), dependencies=("a",)),
            )
        )
    except EvidenceTopologyError:
        pass
    else:
        raise VerificationError("Hard dependency cycles must be rejected.")

    try:
        validate_and_order(
            (EvidenceNode("a", "scripts/a.py", (), (), dependencies=("missing",)),)
        )
    except EvidenceTopologyError:
        pass
    else:
        raise VerificationError("Unknown dependencies must be rejected.")

    check_calls: list[str] = []

    def multi_failure_runner(node: EvidenceNode, stage: str, _timeout: int) -> NodeRun:
        check_calls.append(node.node_id)
        status = "failed" if node.node_id in {"platform_agent_assets", "schema_pack_consumer"} else "pass"
        return run_result(node, stage, status)

    blocked = execute_topology(
        mode="check", runner=multi_failure_runner, emit_progress=False
    )
    require(blocked["status"] == "blocked", "Multiple stale nodes must block check mode.")
    require(len(check_calls) == len(NODES), "Check mode must inspect every node after failures.")
    require(
        blocked["execution"]["failed_node_ids"]
        == ["platform_agent_assets", "schema_pack_consumer"],
        "Check mode must report every stale node.",
    )

    check_round = 0

    def converging_runner(node: EvidenceNode, stage: str, _timeout: int) -> NodeRun:
        nonlocal check_round
        if stage == "check" and node.node_id == ordered[0].node_id:
            check_round += 1
        status = "failed" if stage == "check" and check_round == 1 else "pass"
        return run_result(node, stage, status)

    converged = execute_topology(
        mode="refresh", max_passes=3, runner=converging_runner, emit_progress=False
    )
    require(converged["status"] == "pass", "Feedback refresh must converge.")
    require(converged["execution"]["passes_completed"] == 2, "Refresh pass count drifted.")
    require(converged["execution"]["converged"], "Convergence marker is missing.")

    refresh_round = 0

    def refresh_failure_runner(node: EvidenceNode, stage: str, _timeout: int) -> NodeRun:
        nonlocal refresh_round
        if stage == "refresh" and node.node_id == ordered[0].node_id:
            refresh_round += 1
        status = "failed" if stage == "refresh" and node.node_id == "platform_plugin_packs" else "pass"
        return run_result(node, stage, status)

    refresh_blocked = execute_topology(
        mode="refresh",
        max_passes=3,
        runner=refresh_failure_runner,
        emit_progress=False,
    )
    require(refresh_blocked["status"] == "blocked", "Refresh command failure must block.")
    require(
        refresh_blocked["execution"]["passes_completed"] == 1,
        "A command failure must not be hidden by repeated refresh attempts.",
    )

    serialized = json.dumps([blocked, converged, refresh_blocked], sort_keys=True)
    for forbidden in (
        "/Users/private/repository",
        "Bearer verification-secret",
        "raw learner answer",
        "command stdout",
    ):
        require(forbidden not in serialized, f"Topology receipt leaked forbidden data: {forbidden}")
    require(converged["privacy"]["metadata_only"], "Receipt must remain metadata-only.")
    require(
        not converged["privacy"]["command_stdout_included"],
        "Command stdout must stay outside the receipt.",
    )

    release_check = (ROOT / "scripts" / "release_check.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    require(
        "generated_evidence_topology.py --check" in release_check,
        "Release check is missing the topology gate.",
    )
    require(
        "verify_generated_evidence_topology.py --check" in ci,
        "CI is missing the deterministic topology verifier.",
    )

    return {
        "schema_version": "generated-evidence-topology-verification-v1",
        "status": "pass",
        "graph_version": GRAPH_VERSION,
        "graph_fingerprint_sha256": graph_fingerprint(ordered),
        "checks": {
            "hard_dependencies_topologically_sorted": True,
            "hard_cycles_rejected": True,
            "unknown_dependencies_rejected": True,
            "check_mode_reports_all_stale_nodes": True,
            "feedback_edges_converge_across_passes": True,
            "refresh_failure_blocks_without_retry_masking": True,
            "metadata_only_receipt": True,
            "release_gate_integrated": True,
            "ci_verifier_integrated": True,
        },
        "privacy": {
            "metadata_only": True,
            "command_output_included": False,
            "local_absolute_paths_included": False,
            "secrets_included": False,
            "model_calls_performed": False,
            "network_required": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This verifier covers the declared release-distribution evidence topology and its "
            "feedback convergence. It does not prove every generated artifact in the repository."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
    except (VerificationError, EvidenceTopologyError) as exc:
        print(f"verify_generated_evidence_topology failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
