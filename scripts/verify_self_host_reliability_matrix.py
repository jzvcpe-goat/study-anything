#!/usr/bin/env python3
"""Verify reliability matrix receipts, workflow wiring, and privacy boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from self_host_reliability_matrix import build_receipt  # noqa: E402
from self_host_soak import SoakSample, build_receipt as build_soak_receipt  # noqa: E402


class VerificationError(RuntimeError):
    """Raised when the scheduled reliability contract regresses."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def verify() -> dict[str, object]:
    soak = build_soak_receipt(
        [
            SoakSample(True, 5, "healthy"),
            SoakSample(False, 5, "unavailable"),
            SoakSample(True, 4, "healthy"),
        ],
        api_base="http://127.0.0.1:8000",
        interval_seconds=10,
        min_success_ratio=0.5,
        max_consecutive_failures=2,
        started_at="2026-07-09T00:00:00Z",
        finished_at="2026-07-09T00:00:30Z",
        require_recovery=True,
    )
    passing = build_receipt(
        mode="source-build",
        status="pass",
        started_at="2026-07-09T00:00:00Z",
        finished_at="2026-07-09T02:00:00Z",
        samples_requested=721,
        interval_seconds=10,
        fault_after_seconds=600,
        fault_duration_seconds=45,
        soak=soak,
        api_flow_completed=True,
        source_build_completed=True,
        image_pull_completed=False,
        restart_attempted=True,
        restart_completed=True,
        session_recovery_completed=True,
        source_revision_sha="a" * 40,
        source_worktree_dirty=False,
    )
    blocked = build_receipt(
        mode="published-image",
        status="blocked",
        started_at="2026-07-09T00:00:00Z",
        finished_at="2026-07-09T00:01:00Z",
        samples_requested=721,
        interval_seconds=10,
        fault_after_seconds=600,
        fault_duration_seconds=45,
        soak=None,
        api_flow_completed=False,
        source_build_completed=False,
        image_pull_completed=False,
        restart_attempted=False,
        restart_completed=False,
        session_recovery_completed=False,
        published_image_digest=None,
        failure_phase="image_pull",
        failure_category="timeout",
        tag="main",
    )

    require(passing["status"] == "pass", "Recovered source-build receipt must pass.")
    require(
        passing["runtime"]["recovery_after_failure_observed"],
        "Passing receipt must record observed recovery.",
    )
    require(
        passing["runtime"]["pre_restart_session_recovery_completed"],
        "Passing receipt must record recovery of the pre-restart learning session.",
    )
    require(
        passing["runtime"]["source_revision_sha"] == "a" * 40
        and passing["runtime"]["source_worktree_dirty"] is False,
        "Source-build receipt must identify the clean source revision.",
    )
    require(blocked["status"] == "blocked", "Published-image pull timeout must block.")
    require(
        blocked["runtime"]["controlled_restart_attempted"] is False,
        "A pre-start pull failure must not claim restart injection was attempted.",
    )
    require(blocked["failure"]["category"] == "timeout", "Failure category drifted.")
    require(blocked["failure"]["raw_error_included"] is False, "Raw errors must be excluded.")

    serialized = json.dumps([passing, blocked], sort_keys=True)
    for forbidden in (
        "/Users/private/reliability",
        "Bearer verification-secret",
        "docker command stderr",
        "raw learner answer",
    ):
        require(forbidden not in serialized, f"Reliability receipt leaked: {forbidden}")

    workflow = (ROOT / ".github" / "workflows" / "reliability-soak.yml").read_text(
        encoding="utf-8"
    )
    release_check = (ROOT / "scripts" / "release_check.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for marker in (
        "source-build",
        "published-image",
        "schedule:",
        "timeout-minutes: 180",
        "--fault-duration-seconds",
        "actions/upload-artifact@v4",
    ):
        require(marker in workflow, f"Reliability workflow marker missing: {marker}")
    require("continue-on-error" not in workflow, "Scheduled reliability failures must block jobs.")
    require(
        "verify_self_host_reliability_matrix.py --check" in release_check,
        "Release gate is missing matrix verification.",
    )
    require(
        "verify_self_host_reliability_matrix.py --check" in ci,
        "CI is missing matrix verification.",
    )

    return {
        "schema_version": "self-host-reliability-matrix-verification-v1",
        "status": "pass",
        "checks": {
            "source_build_mode_declared": True,
            "published_image_mode_declared": True,
            "real_elapsed_time_required": True,
            "controlled_restart_required": True,
            "observed_recovery_required": True,
            "pre_restart_session_recovery_required": True,
            "source_or_image_identity_required": True,
            "scheduled_workflow_present": True,
            "workflow_failures_block": True,
            "metadata_only_receipts": True,
            "release_gate_integrated": True,
            "ci_verifier_integrated": True,
        },
        "privacy": passing["privacy"],
        "claim_boundary": (
            "This verifier proves deterministic receipt and workflow contracts. It does not claim "
            "that a scheduled two-hour run has completed until its GitHub receipt exists."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
    except VerificationError as exc:
        print(f"verify_self_host_reliability_matrix failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
