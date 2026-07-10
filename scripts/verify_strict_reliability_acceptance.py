#!/usr/bin/env python3
"""Verify one real strict dual-path reliability run and its bounded index replay."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from reliability_evidence_index import (
    ReliabilityIndexError,
    assert_metadata_only,
    build_index,
    build_run_entry,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "reliability" / "run-29060766261"
SOURCE_RECEIPT = FIXTURE_DIR / "source-build-receipt.json"
PUBLISHED_RECEIPT = FIXTURE_DIR / "published-image-receipt.json"
INDEX_RECEIPT = FIXTURE_DIR / "reliability-index.json"
REMOTE_EVIDENCE = FIXTURE_DIR / "remote-evidence.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-strict-reliability-acceptance.json"
REPORT_SCHEMA_VERSION = "strict-reliability-acceptance-v1"
REMOTE_SCHEMA_VERSION = "strict-reliability-remote-evidence-v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class StrictReliabilityAcceptanceError(RuntimeError):
    """Raised when stored strict reliability evidence is unsafe or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StrictReliabilityAcceptanceError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StrictReliabilityAcceptanceError(f"Cannot read {path.name}") from exc
    require(isinstance(value, dict), f"{path.name} must contain a JSON object")
    return value


def parse_time(value: Any, field: str) -> datetime:
    require(isinstance(value, str), f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StrictReliabilityAcceptanceError(f"{field} must be an ISO timestamp") from exc
    require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    require(set(value) == expected, f"{label} keys drifted: {sorted(set(value) ^ expected)}")


def validate_run_url(value: Any, run_id: int, label: str) -> None:
    require(
        value == f"https://github.com/jzvcpe-goat/study-anything/actions/runs/{run_id}",
        f"{label} URL is not bound to its run ID",
    )


def validate_artifact(
    payload: Mapping[str, Any],
    *,
    expected_name: str,
    fixture_path: Path,
    minimum_retention_days: int,
    label: str,
) -> None:
    require_exact_keys(
        payload,
        {
            "archive_digest",
            "created_at",
            "expired",
            "expires_at",
            "file_sha256",
            "id",
            "name",
            "size_in_bytes",
        },
        label,
    )
    require(payload.get("name") == expected_name, f"{label} name drifted")
    require(payload.get("expired") is False, f"{label} is recorded as expired")
    require(isinstance(payload.get("id"), int) and payload["id"] > 0, f"{label} ID invalid")
    require(
        isinstance(payload.get("size_in_bytes"), int) and payload["size_in_bytes"] > 0,
        f"{label} size invalid",
    )
    require(
        isinstance(payload.get("archive_digest"), str)
        and DIGEST_RE.fullmatch(payload["archive_digest"]) is not None,
        f"{label} archive digest invalid",
    )
    require(
        isinstance(payload.get("file_sha256"), str)
        and HASH_RE.fullmatch(payload["file_sha256"]) is not None,
        f"{label} file hash invalid",
    )
    require(file_sha256(fixture_path) == payload["file_sha256"], f"{label} fixture hash mismatch")
    created = parse_time(payload.get("created_at"), f"{label}.created_at")
    expires = parse_time(payload.get("expires_at"), f"{label}.expires_at")
    require(
        (expires - created).total_seconds() >= minimum_retention_days * 86400,
        f"{label} retention is shorter than {minimum_retention_days} days",
    )


def validate_remote_evidence(payload: Mapping[str, Any]) -> None:
    require_exact_keys(
        payload,
        {
            "artifacts",
            "claim_boundary",
            "failure_classification",
            "privacy",
            "replay_run",
            "repository",
            "schema_version",
            "source_run",
        },
        "remote evidence",
    )
    require(payload.get("schema_version") == REMOTE_SCHEMA_VERSION, "Remote evidence schema drifted")
    require(payload.get("repository") == "jzvcpe-goat/study-anything", "Repository drifted")
    require(isinstance(payload.get("claim_boundary"), str), "Claim boundary missing")

    source = payload.get("source_run")
    replay = payload.get("replay_run")
    artifacts = payload.get("artifacts")
    failure = payload.get("failure_classification")
    privacy = payload.get("privacy")
    for label, value in (
        ("source_run", source),
        ("replay_run", replay),
        ("artifacts", artifacts),
        ("failure_classification", failure),
        ("privacy", privacy),
    ):
        require(isinstance(value, Mapping), f"{label} must be an object")

    source_id = source.get("run_id")
    replay_id = replay.get("run_id")
    require(source_id == 29060766261, "Source run ID drifted")
    require(replay_id == 29066220685, "Replay run ID drifted")
    validate_run_url(source.get("url"), source_id, "source run")
    validate_run_url(replay.get("url"), replay_id, "replay run")
    for label, run in (("source", source), ("replay", replay)):
        require(run.get("workflow_path") == ".github/workflows/reliability-soak.yml", f"{label} workflow drifted")
        require(run.get("status") == "completed", f"{label} run is not completed")
        require(run.get("event") == "workflow_dispatch", f"{label} event drifted")
        require(isinstance(run.get("head_sha"), str) and SHA_RE.fullmatch(run["head_sha"]), f"{label} head SHA invalid")
        require(run.get("run_attempt") == 1, f"{label} run attempt drifted")
        parse_time(run.get("created_at"), f"{label}.created_at")
        parse_time(run.get("updated_at"), f"{label}.updated_at")

    require(source.get("conclusion") == "failure", "Original run must retain its failed index conclusion")
    require(
        source.get("jobs")
        == {
            "reliability-index": "failure",
            "reliability-soak (published-image)": "success",
            "reliability-soak (source-build)": "success",
        },
        "Original run job conclusions drifted",
    )
    require(replay.get("conclusion") == "success", "Replay run did not succeed")
    require(replay.get("evidence_run_id") == source_id, "Replay is not bound to the source run")
    require(
        replay.get("jobs") == {"reliability-index": "success", "reliability-soak": "skipped"},
        "Replay must build only the index",
    )
    require(
        failure.get("type") == "index_job_blocked_by_action_pin_policy_transition",
        "Failure classification drifted",
    )
    require(failure.get("mode_receipts_affected") is False, "Mode receipts were marked affected")
    require(failure.get("raw_job_logs_included") is False, "Raw job logs escaped")

    require_exact_keys(
        artifacts,
        {"published_image_receipt", "reliability_index", "source_build_receipt"},
        "artifacts",
    )
    validate_artifact(
        artifacts["source_build_receipt"],
        expected_name=f"reliability-source-build-{source_id}",
        fixture_path=SOURCE_RECEIPT,
        minimum_retention_days=13,
        label="source-build artifact",
    )
    validate_artifact(
        artifacts["published_image_receipt"],
        expected_name=f"reliability-published-image-{source_id}",
        fixture_path=PUBLISHED_RECEIPT,
        minimum_retention_days=13,
        label="published-image artifact",
    )
    validate_artifact(
        artifacts["reliability_index"],
        expected_name=f"reliability-index-{source_id}",
        fixture_path=INDEX_RECEIPT,
        minimum_retention_days=89,
        label="reliability-index artifact",
    )

    expected_privacy = {
        "api_urls_included": False,
        "command_output_included": False,
        "github_tokens_included": False,
        "job_logs_included": False,
        "learner_answers_included": False,
        "local_absolute_paths_included": False,
        "metadata_only": True,
        "model_calls_performed": False,
        "production_mutation_performed": False,
        "raw_source_text_included": False,
        "secrets_included": False,
    }
    require(dict(privacy) == expected_privacy, "Remote evidence privacy boundary drifted")
    assert_metadata_only(payload)


def validate_acceptance(
    remote: Mapping[str, Any],
    source_receipt: Mapping[str, Any],
    published_receipt: Mapping[str, Any],
    index: Mapping[str, Any],
) -> dict[str, Any]:
    validate_remote_evidence(remote)
    source_run = remote["source_run"]
    entry = build_run_entry(
        run_id=str(source_run["run_id"]),
        event=source_run["event"],
        head_sha=source_run["head_sha"],
        source_receipt=source_receipt,
        published_receipt=published_receipt,
    )
    rebuilt = build_index(entry=entry)
    require(index == rebuilt, "Stored reliability index does not match the exact mode receipts")
    require(entry.get("decision") == "strict_dual_pass", "Run is not a strict dual pass")
    require(entry.get("strict_dual_pass") is True, "Strict dual pass flag missing")
    require(index.get("status") == "pass", "Reliability index status is not pass")
    summary = index.get("summary")
    require(isinstance(summary, Mapping), "Reliability index summary missing")
    require(summary.get("strict_dual_pass_count") == 1, "Strict run count drifted")
    require(summary.get("longitudinal_trend_claimable") is False, "One run claimed a trend")
    require(summary.get("production_slo_claimable") is False, "Reliability evidence claimed an SLO")
    assert_metadata_only(index)
    return entry


def negative_checks(
    remote: Mapping[str, Any],
    source: Mapping[str, Any],
    published: Mapping[str, Any],
    index: Mapping[str, Any],
) -> dict[str, str]:
    cases: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]] = {}

    bad_workflow = copy.deepcopy(remote)
    bad_workflow["replay_run"]["workflow_path"] = ".github/workflows/other.yml"
    cases["different_workflow"] = (bad_workflow, copy.deepcopy(source), copy.deepcopy(published), copy.deepcopy(index))

    bad_replay = copy.deepcopy(remote)
    bad_replay["replay_run"]["conclusion"] = "failure"
    cases["failed_replay"] = (bad_replay, copy.deepcopy(source), copy.deepcopy(published), copy.deepcopy(index))

    leaked_logs = copy.deepcopy(remote)
    leaked_logs["privacy"]["job_logs_included"] = True
    cases["job_log_leak"] = (leaked_logs, copy.deepcopy(source), copy.deepcopy(published), copy.deepcopy(index))

    failed_mode = copy.deepcopy(remote)
    failed_mode["source_run"]["jobs"]["reliability-soak (source-build)"] = "failure"
    cases["failed_mode_job"] = (failed_mode, copy.deepcopy(source), copy.deepcopy(published), copy.deepcopy(index))

    fake_trend = copy.deepcopy(index)
    fake_trend["summary"]["longitudinal_trend_claimable"] = True
    cases["single_run_trend_claim"] = (copy.deepcopy(remote), copy.deepcopy(source), copy.deepcopy(published), fake_trend)

    results: dict[str, str] = {}
    for case_id, values in cases.items():
        try:
            validate_acceptance(*values)
        except (StrictReliabilityAcceptanceError, ReliabilityIndexError) as exc:
            results[case_id] = str(exc)
            continue
        raise StrictReliabilityAcceptanceError(f"Negative case was accepted: {case_id}")
    return results


def build_report() -> dict[str, Any]:
    remote = load_json(REMOTE_EVIDENCE)
    source = load_json(SOURCE_RECEIPT)
    published = load_json(PUBLISHED_RECEIPT)
    index = load_json(INDEX_RECEIPT)
    entry = validate_acceptance(remote, source, published, index)
    modes = entry["modes"]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "source_run": {
            "run_id": entry["run_id"],
            "head_sha": entry["head_sha"],
            "event": entry["event"],
            "decision": entry["decision"],
            "strict_dual_pass": entry["strict_dual_pass"],
        },
        "replay_run": {
            "run_id": str(remote["replay_run"]["run_id"]),
            "status": remote["replay_run"]["conclusion"],
            "mode_jobs_skipped": True,
            "index_job_passed": True,
        },
        "modes": {
            name: {
                "elapsed_seconds": value["elapsed_seconds"],
                "sample_count": value["sampling"]["sample_count"],
                "success_ratio": value["sampling"]["success_ratio"],
                "longest_consecutive_failure_run": value["sampling"]["longest_consecutive_failure_run"],
                "recovery_count": value["sampling"]["recovery_count"],
                "recovery_after_failure_observed": value["runtime"]["recovery_after_failure_observed"],
                "receipt_sha256": value["receipt_sha256"],
                "strict_evidence": value["strict_evidence"],
            }
            for name, value in sorted(modes.items())
        },
        "index": {
            "artifact_name": remote["artifacts"]["reliability_index"]["name"],
            "artifact_archive_digest": remote["artifacts"]["reliability_index"]["archive_digest"],
            "artifact_expires_at": remote["artifacts"]["reliability_index"]["expires_at"],
            "file_sha256": remote["artifacts"]["reliability_index"]["file_sha256"],
            "longitudinal_trend_claimable": index["summary"]["longitudinal_trend_claimable"],
            "production_slo_claimable": index["summary"]["production_slo_claimable"],
        },
        "negative_fixtures": negative_checks(remote, source, published, index),
        "privacy": remote["privacy"],
        "claim_boundary": remote["claim_boundary"],
    }


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        report = build_report()
        rendered = dump_json(report)
        if args.write:
            REPORT.write_text(rendered, encoding="utf-8")
            print(f"wrote {REPORT.relative_to(ROOT)}")
        elif args.check:
            require(REPORT.exists(), f"Generated report missing: {REPORT.relative_to(ROOT)}")
            require(REPORT.read_text(encoding="utf-8") == rendered, "Strict reliability report is stale")
            print("ok    strict reliability acceptance report is up to date")
        else:
            print(rendered, end="")
    except (StrictReliabilityAcceptanceError, ReliabilityIndexError) as exc:
        print(f"verify_strict_reliability_acceptance failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
