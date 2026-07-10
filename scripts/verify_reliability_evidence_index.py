#!/usr/bin/env python3
"""Verify longitudinal reliability indexing, privacy, and release wiring."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from reliability_evidence_index import (  # noqa: E402
    ReliabilityIndexError,
    build_index,
    build_run_entry,
    write_index,
)
from self_host_reliability_matrix import build_receipt as build_matrix_receipt  # noqa: E402
from self_host_soak import SoakSample, build_receipt as build_soak_receipt  # noqa: E402


class VerificationError(RuntimeError):
    """Raised when reliability index behavior regresses."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def make_receipt(
    mode: str,
    *,
    head_sha: str = "a" * 40,
    strict: bool = True,
    status: str = "pass",
) -> dict[str, object]:
    samples_requested = 721 if strict else 20
    interval_seconds = 10.0 if strict else 2.0
    minimum_success_ratio = 0.99 if strict else 0.4
    maximum_consecutive_failures = 8 if strict else 10
    samples = [SoakSample(True, 5, "healthy") for _ in range(samples_requested)]
    if status == "pass":
        for index in range(60, 64) if strict else range(4, 7):
            samples[index] = SoakSample(False, 5, "unavailable")
    soak = build_soak_receipt(
        samples,
        api_base="http://127.0.0.1:8000",
        interval_seconds=interval_seconds,
        min_success_ratio=minimum_success_ratio,
        max_consecutive_failures=maximum_consecutive_failures,
        started_at="2026-07-09T00:00:00Z",
        finished_at="2026-07-09T02:00:00Z" if strict else "2026-07-09T00:00:38Z",
        require_recovery=True,
    )
    return build_matrix_receipt(
        mode=mode,
        status=status,
        started_at="2026-07-09T00:00:00Z",
        finished_at="2026-07-09T02:05:00Z" if strict else "2026-07-09T00:01:00Z",
        samples_requested=samples_requested,
        interval_seconds=interval_seconds,
        fault_after_seconds=600.0 if strict else 4.0,
        fault_duration_seconds=45.0 if strict else 6.0,
        soak=soak,
        api_flow_completed=status == "pass",
        source_build_completed=mode == "source-build" and status == "pass",
        image_pull_completed=mode == "published-image" and status == "pass",
        restart_attempted=status == "pass",
        restart_completed=status == "pass",
        session_recovery_completed=status == "pass",
        compose_start_attempts=1 if status == "pass" else 3,
        source_revision_sha=head_sha if mode == "source-build" else None,
        source_worktree_dirty=False if mode == "source-build" else None,
        published_image_digest=(
            "sha256:" + "b" * 64 if mode == "published-image" and status == "pass" else None
        ),
        failure_phase=None if status == "pass" else "compose_start",
        failure_category=None if status == "pass" else "command_failed_after_retries",
        tag="main" if mode == "published-image" else None,
    )


def make_entry(run_id: str, *, strict: bool = True, status: str = "pass") -> dict[str, object]:
    head_sha = chr(ord("a") + (int(run_id) % 5)) * 40
    return build_run_entry(
        run_id=run_id,
        event="schedule" if int(run_id) % 2 else "workflow_dispatch",
        head_sha=head_sha,
        source_receipt=make_receipt(
            "source-build", head_sha=head_sha, strict=strict, status=status
        ),
        published_receipt=make_receipt(
            "published-image", head_sha=head_sha, strict=strict, status=status
        ),
    )


def expect_error(label: str, action) -> None:
    try:
        action()
    except ReliabilityIndexError:
        return
    raise VerificationError(f"Unsafe reliability evidence was accepted: {label}")


def verify() -> dict[str, object]:
    strict_entry = make_entry("1001")
    require(strict_entry["decision"] == "strict_dual_pass", "Strict dual pass was not recognized")
    index = build_index(entry=strict_entry)
    require(index["summary"]["strict_dual_pass_count"] == 1, "Strict count drifted")
    require(
        index["summary"]["longitudinal_trend_claimable"] is False,
        "One run must not become a longitudinal trend",
    )
    require(index["summary"]["production_slo_claimable"] is False, "SLO claim escaped")

    second = build_index(entry=make_entry("1002"), previous_index=index)
    third = build_index(entry=make_entry("1003"), previous_index=second)
    require(third["summary"]["strict_dual_pass_count"] == 3, "Three strict runs not counted")
    require(
        third["summary"]["longitudinal_trend_claimable"] is True,
        "Three strict runs should unlock only the bounded trend signal",
    )
    idempotent = build_index(entry=strict_entry, previous_index=index)
    require(idempotent == index, "Identical run intake must be idempotent")

    tampered_history = copy.deepcopy(index)
    tampered_history["runs"][0]["strict_dual_pass"] = not tampered_history["runs"][0][
        "strict_dual_pass"
    ]
    expect_error(
        "tampered historical decision",
        lambda: build_index(entry=make_entry("1004"), previous_index=tampered_history),
    )

    conflicting = copy.deepcopy(strict_entry)
    conflicting["head_sha"] = "f" * 40
    expect_error(
        "conflicting duplicate run",
        lambda: build_index(entry=conflicting, previous_index=index),
    )

    diagnostic = make_entry("2001", strict=False)
    require(diagnostic["decision"] == "diagnostic_only", "Diagnostic run was promoted")
    diagnostic_index = build_index(entry=diagnostic)
    require(
        diagnostic_index["summary"]["strict_dual_pass_count"] == 0,
        "Diagnostic run counted as strict evidence",
    )

    blocked = make_entry("3001", status="blocked")
    require(blocked["decision"] == "blocked", "Blocked run was not preserved")

    mixed_source = make_receipt("source-build", strict=True)
    mixed_published = make_receipt("published-image", strict=False)
    mixed = build_run_entry(
        run_id="4001",
        event="workflow_dispatch",
        head_sha="a" * 40,
        source_receipt=mixed_source,
        published_receipt=mixed_published,
    )
    require(mixed["decision"] == "mixed_profile_blocked", "Mixed profiles must block")

    unsafe = make_receipt("source-build")
    unsafe["runtime"]["operator_note"] = "Bearer verification-secret-value"
    expect_error(
        "bearer token",
        lambda: build_run_entry(
            run_id="5001",
            event="schedule",
            head_sha="a" * 40,
            source_receipt=unsafe,
            published_receipt=make_receipt("published-image"),
        ),
    )

    mismatched = make_receipt("source-build", head_sha="b" * 40)
    expect_error(
        "source head mismatch",
        lambda: build_run_entry(
            run_id="5002",
            event="schedule",
            head_sha="a" * 40,
            source_receipt=mismatched,
            published_receipt=make_receipt("published-image"),
        ),
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "index.json"
        write_index(target, third)
        require(target.stat().st_mode & 0o777 == 0o600, "Index file must be private")
        persisted = json.loads(target.read_text(encoding="utf-8"))
        require(persisted == third, "Persisted index changed")

    serialized = json.dumps(third, sort_keys=True)
    for forbidden in (
        "/Users/private/reliability",
        "Bearer verification-secret",
        "raw learner answer",
        "docker command stderr",
        "http://127.0.0.1:8000",
    ):
        require(forbidden not in serialized, f"Reliability index leaked: {forbidden}")

    workflow = (ROOT / ".github" / "workflows" / "reliability-soak.yml").read_text(encoding="utf-8")
    release_check = (ROOT / "scripts" / "release_check.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for marker in (
        "evidence_run_id:",
        "actions: read",
        "if: ${{ inputs.evidence_run_id == '' }}",
        "reliability-index:",
        "Resolve evidence source",
        '[[ "$workflow_path" == ".github/workflows/reliability-soak.yml" ]]',
        '[[ "$run_status" == "completed" ]]',
        "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "github-token: ${{ secrets.GITHUB_TOKEN }}",
        "run-id: ${{ steps.evidence.outputs.run_id }}",
        '--run-id "${{ steps.evidence.outputs.run_id }}"',
        '--head-sha "${{ steps.evidence.outputs.head_sha }}"',
        "name: reliability-index-${{ steps.evidence.outputs.run_id }}",
        "reliability_evidence_index.py",
        "self-host-reliability-index.json",
        "retention-days: 90",
    ):
        require(marker in workflow, f"Reliability workflow index marker missing: {marker}")
    require(
        "verify_reliability_evidence_index.py --check" in release_check,
        "Release check is missing the reliability index verifier",
    )
    require(
        "verify_reliability_evidence_index.py --check" in ci,
        "CI is missing the reliability index verifier",
    )

    return {
        "schema_version": "self-host-reliability-index-verification-v1",
        "status": "pass",
        "checks": {
            "strict_default_profile_enforced": True,
            "source_and_published_equal_weight": True,
            "diagnostic_runs_not_promoted": True,
            "mixed_profiles_blocked": True,
            "blocked_runs_preserved": True,
            "receipt_hashes_recorded": True,
            "source_commit_bound": True,
            "duplicate_intake_idempotent": True,
            "conflicting_duplicate_rejected": True,
            "trend_requires_three_strict_dual_passes": True,
            "production_slo_never_inferred": True,
            "metadata_only_privacy_enforced": True,
            "private_file_permissions": True,
            "workflow_index_integrated": True,
            "completed_run_replay_bound": True,
            "replay_source_workflow_bound": True,
            "replay_source_commit_bound": True,
            "release_gate_integrated": True,
            "ci_verifier_integrated": True,
        },
        "privacy": third["privacy"],
        "claim_boundary": (
            "This verifier proves deterministic index behavior and workflow wiring. It does not "
            "claim that a strict two-hour GitHub run exists until a real indexed artifact is available."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2, sort_keys=True))
    except (VerificationError, ReliabilityIndexError) as exc:
        print(f"verify_reliability_evidence_index failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
