#!/usr/bin/env python3
"""Build a metadata-only longitudinal index from reliability matrix receipts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / ".cognitive-loop" / "artifacts" / "reliability" / "self-host-reliability-index.json"
)
INDEX_SCHEMA_VERSION = "self-host-reliability-index-v1"
MATRIX_SCHEMA_VERSION = "self-host-reliability-matrix-receipt-v1"
STRICT_SAMPLES = 721
STRICT_INTERVAL_SECONDS = 10.0
STRICT_FAULT_AFTER_SECONDS = 600.0
STRICT_FAULT_DURATION_SECONDS = 45.0
STRICT_MIN_SUCCESS_RATIO = 0.99
STRICT_MAX_CONSECUTIVE_FAILURES = 8
STRICT_MIN_ELAPSED_SECONDS = (STRICT_SAMPLES - 1) * STRICT_INTERVAL_SECONDS
LONGITUDINAL_TREND_MIN_RUNS = 3
ENTRY_CLAIM_BOUNDARY = (
    "A strict dual pass proves only this isolated default-duration workflow run. "
    "Diagnostic or mixed profiles cannot satisfy strict reliability evidence."
)
INDEX_CLAIM_BOUNDARY = (
    "This index records validated metadata from isolated reliability workflow receipts. "
    "One strict dual pass is not a longitudinal trend, and no number of these runs alone "
    "proves a production SLO, incident response, disaster recovery, or customer availability."
)
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"https?://(?:127\.0\.0\.1|localhost)(?::[0-9]+)?[^\s\"']*"),
)
FORBIDDEN_KEYS = {
    "api_key",
    "token",
    "secret",
    "raw_source_text",
    "learner_answer",
    "docker_logs",
    "command_stdout",
    "command_stderr",
    "api_url",
    "env_file_path",
    "compose_project_name",
    "image_reference",
}


class ReliabilityIndexError(RuntimeError):
    """Readable reliability evidence validation failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReliabilityIndexError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReliabilityIndexError(f"Cannot read JSON receipt: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ReliabilityIndexError(f"JSON object expected: {path.name}")
    return payload


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_timestamp(value: Any, field: str) -> datetime:
    require(isinstance(value, str), f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReliabilityIndexError(f"{field} must be an ISO timestamp") from exc
    require(parsed.tzinfo is not None, f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def require_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    require(isinstance(value, Mapping), f"Matrix receipt {key} must be an object")
    return value


def require_exact_keys(payload: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unexpected = set(payload) - allowed
    require(not unexpected, f"{label} contains unknown fields: {sorted(unexpected)}")


def assert_metadata_only(payload: Any) -> None:
    def inspect(value: Any, path: str = "root") -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                normalized = str(key).lower()
                if normalized in FORBIDDEN_KEYS and item not in (False, None):
                    raise ReliabilityIndexError(
                        f"Forbidden reliability evidence field: {path}.{key}"
                    )
                inspect(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                inspect(item, f"{path}[{index}]")
        elif isinstance(value, str):
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(value):
                    raise ReliabilityIndexError(f"Private reliability evidence detected at {path}")

    inspect(payload)


def number(value: Any, field: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{field} must be numeric",
    )
    return float(value)


def strict_profile(receipt: Mapping[str, Any]) -> bool:
    schedule = require_mapping(receipt, "schedule")
    soak = receipt.get("soak")
    if not isinstance(soak, Mapping):
        return False
    sampling = require_mapping(soak, "sampling")
    thresholds = require_mapping(soak, "thresholds")
    return (
        schedule.get("samples_requested") == STRICT_SAMPLES
        and number(schedule.get("interval_seconds"), "schedule.interval_seconds")
        == STRICT_INTERVAL_SECONDS
        and number(schedule.get("fault_after_seconds"), "schedule.fault_after_seconds")
        == STRICT_FAULT_AFTER_SECONDS
        and number(schedule.get("fault_duration_seconds"), "schedule.fault_duration_seconds")
        == STRICT_FAULT_DURATION_SECONDS
        and schedule.get("real_elapsed_time_required") is True
        and schedule.get("accelerated_clock_used") is False
        and sampling.get("sample_count") == STRICT_SAMPLES
        and number(sampling.get("interval_seconds"), "soak.sampling.interval_seconds")
        == STRICT_INTERVAL_SECONDS
        and number(
            thresholds.get("minimum_success_ratio"),
            "soak.thresholds.minimum_success_ratio",
        )
        == STRICT_MIN_SUCCESS_RATIO
        and thresholds.get("maximum_consecutive_failures") == STRICT_MAX_CONSECUTIVE_FAILURES
        and thresholds.get("recovery_after_failure_required") is True
    )


def validate_matrix_receipt(
    payload: Mapping[str, Any], *, expected_mode: str, expected_head_sha: str
) -> dict[str, Any]:
    require_exact_keys(
        payload,
        {
            "schema_version",
            "status",
            "mode",
            "started_at",
            "finished_at",
            "schedule",
            "runtime",
            "soak",
            "failure",
            "privacy",
            "claim_boundary",
        },
        "Matrix receipt",
    )
    require(payload.get("schema_version") == MATRIX_SCHEMA_VERSION, "Matrix schema drifted")
    require(payload.get("mode") == expected_mode, f"Expected {expected_mode} receipt")
    require(payload.get("status") in {"pass", "blocked"}, "Matrix status is invalid")
    started = parse_timestamp(payload.get("started_at"), "started_at")
    finished = parse_timestamp(payload.get("finished_at"), "finished_at")
    elapsed_seconds = int((finished - started).total_seconds())
    require(elapsed_seconds >= 0, "Matrix receipt finished before it started")

    schedule = require_mapping(payload, "schedule")
    runtime = require_mapping(payload, "runtime")
    soak = payload.get("soak")
    failure = require_mapping(payload, "failure")
    privacy = require_mapping(payload, "privacy")
    require_exact_keys(
        schedule,
        {
            "samples_requested",
            "interval_seconds",
            "fault_after_seconds",
            "fault_duration_seconds",
            "real_elapsed_time_required",
            "accelerated_clock_used",
        },
        "Matrix schedule",
    )
    require_exact_keys(
        runtime,
        {
            "api_flow_completed",
            "source_build_completed",
            "published_image_pull_completed",
            "controlled_restart_attempted",
            "controlled_restart_completed",
            "recovery_after_failure_observed",
            "pre_restart_session_recovery_completed",
            "compose_start_attempts",
            "published_tag",
            "published_image_digest",
            "source_revision_sha",
            "source_worktree_dirty",
            "image_reference_included",
            "compose_project_included",
        },
        "Matrix runtime",
    )
    require_exact_keys(
        failure,
        {"phase", "category", "raw_error_included", "command_output_included"},
        "Matrix failure",
    )
    require_exact_keys(
        privacy,
        {
            "metadata_only",
            "api_url_included",
            "env_file_path_included",
            "compose_project_name_included",
            "docker_logs_included",
            "command_stdout_included",
            "command_stderr_included",
            "local_absolute_paths_included",
            "secrets_included",
            "raw_source_text_included",
            "learner_answers_included",
            "model_calls_performed",
            "production_mutation_performed",
            "disposable_test_volumes_only",
        },
        "Matrix privacy",
    )
    require(privacy.get("metadata_only") is True, "Matrix receipt is not metadata-only")
    for flag in (
        "api_url_included",
        "env_file_path_included",
        "compose_project_name_included",
        "docker_logs_included",
        "command_stdout_included",
        "command_stderr_included",
        "local_absolute_paths_included",
        "secrets_included",
        "raw_source_text_included",
        "learner_answers_included",
        "model_calls_performed",
        "production_mutation_performed",
    ):
        require(privacy.get(flag) is False, f"Unsafe matrix privacy flag: {flag}")
    require(failure.get("raw_error_included") is False, "Raw errors must be excluded")
    require(failure.get("command_output_included") is False, "Command output must be excluded")
    assert_metadata_only(payload)

    profile = "strict-default" if strict_profile(payload) else "diagnostic"
    sampling: Mapping[str, Any] = {}
    thresholds: Mapping[str, Any] = {}
    if isinstance(soak, Mapping):
        require_exact_keys(
            soak,
            {
                "schema_version",
                "status",
                "classification",
                "started_at",
                "finished_at",
                "endpoint",
                "sampling",
                "thresholds",
                "latency_ms",
                "blocked_reasons",
                "privacy",
                "claim_boundary",
            },
            "Soak receipt",
        )
        sampling = require_mapping(soak, "sampling")
        thresholds = require_mapping(soak, "thresholds")
        endpoint = require_mapping(soak, "endpoint")
        latency = require_mapping(soak, "latency_ms")
        soak_privacy = require_mapping(soak, "privacy")
        require_exact_keys(
            endpoint,
            {"scope", "tls_enabled", "host_included", "url_included"},
            "Soak endpoint",
        )
        require_exact_keys(
            sampling,
            {
                "sample_count",
                "interval_seconds",
                "success_count",
                "failure_count",
                "success_ratio",
                "longest_consecutive_failure_run",
                "recovery_count",
                "recovered_after_failure",
                "failure_categories",
            },
            "Soak sampling",
        )
        require_exact_keys(
            thresholds,
            {
                "minimum_success_ratio",
                "maximum_consecutive_failures",
                "recovery_after_failure_required",
            },
            "Soak thresholds",
        )
        require_exact_keys(
            latency,
            {"minimum", "maximum", "p50", "p95"},
            "Soak latency",
        )
        require_exact_keys(
            soak_privacy,
            {
                "metadata_only",
                "health_response_body_included",
                "api_url_included",
                "api_token_included",
                "docker_logs_included",
                "local_absolute_paths_included",
                "raw_source_text_included",
                "learner_answers_included",
                "agent_metadata_included",
                "model_calls_performed",
                "production_mutation_performed",
            },
            "Soak privacy",
        )

    if payload.get("status") == "pass":
        require(isinstance(soak, Mapping), "Passing receipt must include soak evidence")
        require(soak.get("status") == "pass", "Passing matrix has blocked soak evidence")
        for flag in (
            "api_flow_completed",
            "controlled_restart_attempted",
            "controlled_restart_completed",
            "recovery_after_failure_observed",
            "pre_restart_session_recovery_completed",
        ):
            require(runtime.get(flag) is True, f"Passing receipt is missing runtime proof: {flag}")
        require(
            isinstance(runtime.get("compose_start_attempts"), int)
            and not isinstance(runtime.get("compose_start_attempts"), bool)
            and 1 <= runtime["compose_start_attempts"] <= 3,
            "Passing receipt has invalid Compose start attempts",
        )
        require(sampling.get("recovered_after_failure") is True, "Recovery was not observed")
        success_ratio = number(sampling.get("success_ratio"), "soak.sampling.success_ratio")
        minimum_ratio = number(
            thresholds.get("minimum_success_ratio"),
            "soak.thresholds.minimum_success_ratio",
        )
        require(success_ratio >= minimum_ratio, "Passing receipt is below its success threshold")
        longest_failures = sampling.get("longest_consecutive_failure_run")
        maximum_failures = thresholds.get("maximum_consecutive_failures")
        require(
            isinstance(longest_failures, int)
            and not isinstance(longest_failures, bool)
            and isinstance(maximum_failures, int)
            and not isinstance(maximum_failures, bool)
            and longest_failures <= maximum_failures,
            "Passing receipt exceeds its consecutive failure budget",
        )
        if thresholds.get("recovery_after_failure_required") is True:
            require(
                isinstance(sampling.get("recovery_count"), int)
                and not isinstance(sampling.get("recovery_count"), bool)
                and sampling["recovery_count"] >= 1,
                "Passing receipt is missing the required recovery count",
            )

    identity: dict[str, Any]
    if expected_mode == "source-build":
        source_sha = runtime.get("source_revision_sha")
        require(
            isinstance(source_sha, str) and SHA_PATTERN.fullmatch(source_sha) is not None,
            "Source receipt must include a valid revision SHA",
        )
        require(
            source_sha == expected_head_sha, "Source receipt revision does not match workflow head"
        )
        if payload.get("status") == "pass":
            require(runtime.get("source_build_completed") is True, "Source build did not complete")
            require(runtime.get("source_worktree_dirty") is False, "Source build was not clean")
        identity = {
            "source_revision_sha": source_sha,
            "source_worktree_dirty": runtime.get("source_worktree_dirty"),
        }
    else:
        digest = runtime.get("published_image_digest")
        if payload.get("status") == "pass":
            require(
                isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest) is not None,
                "Published receipt must include a valid image digest",
            )
            require(
                runtime.get("published_image_pull_completed") is True, "Image pull did not complete"
            )
        elif digest is not None:
            require(
                isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest) is not None,
                "Published receipt image digest is invalid",
            )
        identity = {"published_image_digest": digest}

    strict_evidence = (
        profile == "strict-default"
        and payload.get("status") == "pass"
        and elapsed_seconds >= STRICT_MIN_ELAPSED_SECONDS
    )
    return {
        "mode": expected_mode,
        "status": payload["status"],
        "profile": profile,
        "strict_evidence": strict_evidence,
        "started_at": payload["started_at"],
        "finished_at": payload["finished_at"],
        "elapsed_seconds": elapsed_seconds,
        "receipt_sha256": canonical_sha256(payload),
        "schedule": {
            "samples_requested": schedule.get("samples_requested"),
            "interval_seconds": schedule.get("interval_seconds"),
            "fault_after_seconds": schedule.get("fault_after_seconds"),
            "fault_duration_seconds": schedule.get("fault_duration_seconds"),
        },
        "sampling": {
            "sample_count": sampling.get("sample_count"),
            "success_ratio": sampling.get("success_ratio"),
            "longest_consecutive_failure_run": sampling.get("longest_consecutive_failure_run"),
            "recovery_count": sampling.get("recovery_count"),
        },
        "thresholds": {
            "minimum_success_ratio": thresholds.get("minimum_success_ratio"),
            "maximum_consecutive_failures": thresholds.get("maximum_consecutive_failures"),
            "recovery_after_failure_required": thresholds.get("recovery_after_failure_required"),
        },
        "runtime": {
            "compose_start_attempts": runtime.get("compose_start_attempts"),
            "controlled_restart_completed": runtime.get("controlled_restart_completed"),
            "recovery_after_failure_observed": runtime.get("recovery_after_failure_observed"),
            "pre_restart_session_recovery_completed": runtime.get(
                "pre_restart_session_recovery_completed"
            ),
            **identity,
        },
        "failure": {
            "phase": failure.get("phase"),
            "category": failure.get("category"),
        },
    }


def build_run_entry(
    *,
    run_id: str,
    event: str,
    head_sha: str,
    source_receipt: Mapping[str, Any],
    published_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    require(RUN_ID_PATTERN.fullmatch(run_id) is not None, "run_id must be a positive integer")
    require(event in {"schedule", "workflow_dispatch"}, "Unsupported workflow event")
    require(SHA_PATTERN.fullmatch(head_sha) is not None, "head_sha must be a lowercase SHA")
    source = validate_matrix_receipt(
        source_receipt,
        expected_mode="source-build",
        expected_head_sha=head_sha,
    )
    published = validate_matrix_receipt(
        published_receipt,
        expected_mode="published-image",
        expected_head_sha=head_sha,
    )
    if source["strict_evidence"] and published["strict_evidence"]:
        decision = "strict_dual_pass"
    elif source["status"] != "pass" or published["status"] != "pass":
        decision = "blocked"
    elif source["profile"] == "diagnostic" and published["profile"] == "diagnostic":
        decision = "diagnostic_only"
    else:
        decision = "mixed_profile_blocked"
    entry = {
        "run_id": run_id,
        "event": event,
        "head_sha": head_sha,
        "decision": decision,
        "strict_dual_pass": decision == "strict_dual_pass",
        "modes": {"source-build": source, "published-image": published},
        "claim_boundary": ENTRY_CLAIM_BOUNDARY,
    }
    assert_metadata_only(entry)
    return entry


def validate_existing_index(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    require_exact_keys(
        payload,
        {
            "schema_version",
            "status",
            "strict_contract",
            "summary",
            "runs",
            "privacy",
            "claim_boundary",
        },
        "Reliability index",
    )
    require(payload.get("schema_version") == INDEX_SCHEMA_VERSION, "Index schema drifted")
    require(payload.get("status") == "pass", "Index status must be pass")
    require(payload.get("claim_boundary") == INDEX_CLAIM_BOUNDARY, "Index claim boundary drifted")
    strict_contract = require_mapping(payload, "strict_contract")
    summary = require_mapping(payload, "summary")
    privacy = require_mapping(payload, "privacy")
    require_exact_keys(
        strict_contract,
        {
            "samples",
            "interval_seconds",
            "minimum_elapsed_seconds",
            "fault_after_seconds",
            "fault_duration_seconds",
            "minimum_success_ratio",
            "maximum_consecutive_failures",
            "recovery_after_failure_required",
            "source_and_published_modes_equal_weight",
        },
        "Index strict contract",
    )
    require_exact_keys(
        summary,
        {
            "runs_total",
            "strict_dual_pass_count",
            "diagnostic_only_count",
            "blocked_count",
            "latest_strict_dual_pass_run_id",
            "longitudinal_trend_minimum_runs",
            "longitudinal_trend_claimable",
            "production_slo_claimable",
        },
        "Index summary",
    )
    require_exact_keys(
        privacy,
        {
            "metadata_only",
            "receipt_hashes_included",
            "workflow_logs_included",
            "api_urls_included",
            "image_references_included",
            "local_absolute_paths_included",
            "raw_source_text_included",
            "learner_answers_included",
            "secrets_included",
            "model_calls_performed",
            "production_mutation_performed",
        },
        "Index privacy",
    )
    require(privacy.get("metadata_only") is True, "Index must remain metadata-only")
    for flag in (
        "workflow_logs_included",
        "api_urls_included",
        "image_references_included",
        "local_absolute_paths_included",
        "raw_source_text_included",
        "learner_answers_included",
        "secrets_included",
        "model_calls_performed",
        "production_mutation_performed",
    ):
        require(privacy.get(flag) is False, f"Unsafe historical index privacy flag: {flag}")
    entries = payload.get("runs")
    require(isinstance(entries, list), "Index runs must be a list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        require(isinstance(entry, dict), "Index run entry must be an object")
        validate_index_entry(entry)
        run_id = entry["run_id"]
        require(run_id not in seen, "Index contains duplicate run IDs")
        seen.add(run_id)
        normalized.append(dict(entry))
    require(
        [item["run_id"] for item in normalized]
        == sorted((item["run_id"] for item in normalized), key=int),
        "Historical index runs must be sorted by run_id",
    )
    require(
        dict(strict_contract)
        == {
            "samples": STRICT_SAMPLES,
            "interval_seconds": STRICT_INTERVAL_SECONDS,
            "minimum_elapsed_seconds": STRICT_MIN_ELAPSED_SECONDS,
            "fault_after_seconds": STRICT_FAULT_AFTER_SECONDS,
            "fault_duration_seconds": STRICT_FAULT_DURATION_SECONDS,
            "minimum_success_ratio": STRICT_MIN_SUCCESS_RATIO,
            "maximum_consecutive_failures": STRICT_MAX_CONSECUTIVE_FAILURES,
            "recovery_after_failure_required": True,
            "source_and_published_modes_equal_weight": True,
        },
        "Historical strict contract drifted",
    )
    strict_runs = [item for item in normalized if item.get("strict_dual_pass") is True]
    diagnostic_runs = [item for item in normalized if item.get("decision") == "diagnostic_only"]
    blocked_runs = [
        item for item in normalized if item.get("decision") in {"blocked", "mixed_profile_blocked"}
    ]
    expected_summary = {
        "runs_total": len(normalized),
        "strict_dual_pass_count": len(strict_runs),
        "diagnostic_only_count": len(diagnostic_runs),
        "blocked_count": len(blocked_runs),
        "latest_strict_dual_pass_run_id": strict_runs[-1]["run_id"] if strict_runs else None,
        "longitudinal_trend_minimum_runs": LONGITUDINAL_TREND_MIN_RUNS,
        "longitudinal_trend_claimable": len(strict_runs) >= LONGITUDINAL_TREND_MIN_RUNS,
        "production_slo_claimable": False,
    }
    require(dict(summary) == expected_summary, "Historical index summary is inconsistent")
    assert_metadata_only(payload)
    return normalized


def expected_decision(source: Mapping[str, Any], published: Mapping[str, Any]) -> str:
    if source.get("strict_evidence") is True and published.get("strict_evidence") is True:
        return "strict_dual_pass"
    if source.get("status") != "pass" or published.get("status") != "pass":
        return "blocked"
    if source.get("profile") == "diagnostic" and published.get("profile") == "diagnostic":
        return "diagnostic_only"
    return "mixed_profile_blocked"


def validate_index_mode(
    mode: Mapping[str, Any], *, expected_mode: str, expected_head_sha: str
) -> None:
    require_exact_keys(
        mode,
        {
            "mode",
            "status",
            "profile",
            "strict_evidence",
            "started_at",
            "finished_at",
            "elapsed_seconds",
            "receipt_sha256",
            "schedule",
            "sampling",
            "thresholds",
            "runtime",
            "failure",
        },
        "Indexed mode",
    )
    require(mode.get("mode") == expected_mode, "Indexed mode identity drifted")
    require(mode.get("status") in {"pass", "blocked"}, "Indexed mode status is invalid")
    require(mode.get("profile") in {"strict-default", "diagnostic"}, "Indexed profile is invalid")
    require(isinstance(mode.get("strict_evidence"), bool), "Indexed strict flag is invalid")
    require(
        isinstance(mode.get("receipt_sha256"), str)
        and HASH_PATTERN.fullmatch(mode["receipt_sha256"]) is not None,
        "Indexed receipt hash is invalid",
    )
    require(
        isinstance(mode.get("elapsed_seconds"), int)
        and not isinstance(mode.get("elapsed_seconds"), bool)
        and mode["elapsed_seconds"] >= 0,
        "Indexed elapsed time is invalid",
    )
    schedule = require_mapping(mode, "schedule")
    sampling = require_mapping(mode, "sampling")
    thresholds = require_mapping(mode, "thresholds")
    runtime = require_mapping(mode, "runtime")
    failure = require_mapping(mode, "failure")
    require_exact_keys(
        schedule,
        {
            "samples_requested",
            "interval_seconds",
            "fault_after_seconds",
            "fault_duration_seconds",
        },
        "Indexed schedule",
    )
    require_exact_keys(
        sampling,
        {
            "sample_count",
            "success_ratio",
            "longest_consecutive_failure_run",
            "recovery_count",
        },
        "Indexed sampling",
    )
    require_exact_keys(
        thresholds,
        {
            "minimum_success_ratio",
            "maximum_consecutive_failures",
            "recovery_after_failure_required",
        },
        "Indexed thresholds",
    )
    runtime_keys = {
        "compose_start_attempts",
        "controlled_restart_completed",
        "recovery_after_failure_observed",
        "pre_restart_session_recovery_completed",
    }
    runtime_keys.update(
        {"source_revision_sha", "source_worktree_dirty"}
        if expected_mode == "source-build"
        else {"published_image_digest"}
    )
    require_exact_keys(runtime, runtime_keys, "Indexed runtime")
    require_exact_keys(failure, {"phase", "category"}, "Indexed failure")
    started = parse_timestamp(mode.get("started_at"), "indexed started_at")
    finished = parse_timestamp(mode.get("finished_at"), "indexed finished_at")
    require(
        int((finished - started).total_seconds()) == mode.get("elapsed_seconds"),
        "Indexed elapsed time does not match timestamps",
    )

    if mode.get("strict_evidence") is True:
        require(mode.get("status") == "pass", "Strict indexed evidence must pass")
        require(mode.get("profile") == "strict-default", "Strict indexed profile drifted")
        require(
            mode["elapsed_seconds"] >= STRICT_MIN_ELAPSED_SECONDS, "Strict indexed run is too short"
        )
        require(
            schedule.get("samples_requested") == STRICT_SAMPLES,
            "Strict indexed sample count drifted",
        )
        require(
            number(schedule.get("interval_seconds"), "indexed interval") == STRICT_INTERVAL_SECONDS,
            "Strict indexed interval drifted",
        )
        require(
            number(schedule.get("fault_after_seconds"), "indexed fault start")
            == STRICT_FAULT_AFTER_SECONDS,
            "Strict indexed fault start drifted",
        )
        require(
            number(schedule.get("fault_duration_seconds"), "indexed fault duration")
            == STRICT_FAULT_DURATION_SECONDS,
            "Strict indexed fault duration drifted",
        )
        require(sampling.get("sample_count") == STRICT_SAMPLES, "Strict completed samples drifted")
        require(
            number(thresholds.get("minimum_success_ratio"), "indexed ratio")
            == STRICT_MIN_SUCCESS_RATIO,
            "Strict indexed ratio drifted",
        )
        require(
            thresholds.get("maximum_consecutive_failures") == STRICT_MAX_CONSECUTIVE_FAILURES,
            "Strict indexed failure budget drifted",
        )
        require(
            thresholds.get("recovery_after_failure_required") is True,
            "Strict indexed recovery gate drifted",
        )
        for flag in (
            "controlled_restart_completed",
            "recovery_after_failure_observed",
            "pre_restart_session_recovery_completed",
        ):
            require(runtime.get(flag) is True, f"Strict indexed runtime proof missing: {flag}")

    if expected_mode == "source-build":
        source_sha = runtime.get("source_revision_sha")
        require(
            isinstance(source_sha, str)
            and SHA_PATTERN.fullmatch(source_sha) is not None
            and source_sha == expected_head_sha,
            "Indexed source revision does not match workflow head",
        )
        if mode.get("strict_evidence") is True:
            require(
                runtime.get("source_worktree_dirty") is False, "Strict indexed source was dirty"
            )
    elif mode.get("strict_evidence") is True:
        digest = runtime.get("published_image_digest")
        require(
            isinstance(digest, str) and DIGEST_PATTERN.fullmatch(digest) is not None,
            "Strict indexed image digest is invalid",
        )


def validate_index_entry(entry: Mapping[str, Any]) -> None:
    require_exact_keys(
        entry,
        {
            "run_id",
            "event",
            "head_sha",
            "decision",
            "strict_dual_pass",
            "modes",
            "claim_boundary",
        },
        "Indexed run",
    )
    run_id = entry.get("run_id")
    require(
        isinstance(run_id, str) and RUN_ID_PATTERN.fullmatch(run_id) is not None,
        "Invalid indexed run_id",
    )
    require(entry.get("event") in {"schedule", "workflow_dispatch"}, "Indexed event is invalid")
    require(entry.get("claim_boundary") == ENTRY_CLAIM_BOUNDARY, "Indexed claim boundary drifted")
    head_sha = entry.get("head_sha")
    require(
        isinstance(head_sha, str) and SHA_PATTERN.fullmatch(head_sha) is not None,
        "Indexed head SHA is invalid",
    )
    modes = require_mapping(entry, "modes")
    require(set(modes) == {"source-build", "published-image"}, "Indexed modes drifted")
    source = require_mapping(modes, "source-build")
    published = require_mapping(modes, "published-image")
    validate_index_mode(source, expected_mode="source-build", expected_head_sha=head_sha)
    validate_index_mode(published, expected_mode="published-image", expected_head_sha=head_sha)
    decision = expected_decision(source, published)
    require(entry.get("decision") == decision, "Indexed run decision is inconsistent")
    require(
        entry.get("strict_dual_pass") is (decision == "strict_dual_pass"),
        "Indexed strict dual pass flag is inconsistent",
    )
    assert_metadata_only(entry)


def build_index(
    *,
    entry: Mapping[str, Any],
    previous_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    runs = validate_existing_index(previous_index) if previous_index else []
    existing = next((item for item in runs if item.get("run_id") == entry.get("run_id")), None)
    if existing is not None:
        require(existing == entry, "Conflicting evidence exists for this run_id")
    else:
        runs.append(dict(entry))
    runs.sort(key=lambda item: int(item["run_id"]))
    strict_runs = [item for item in runs if item.get("strict_dual_pass") is True]
    diagnostic_runs = [item for item in runs if item.get("decision") == "diagnostic_only"]
    blocked_runs = [
        item for item in runs if item.get("decision") in {"blocked", "mixed_profile_blocked"}
    ]
    index = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "status": "pass",
        "strict_contract": {
            "samples": STRICT_SAMPLES,
            "interval_seconds": STRICT_INTERVAL_SECONDS,
            "minimum_elapsed_seconds": STRICT_MIN_ELAPSED_SECONDS,
            "fault_after_seconds": STRICT_FAULT_AFTER_SECONDS,
            "fault_duration_seconds": STRICT_FAULT_DURATION_SECONDS,
            "minimum_success_ratio": STRICT_MIN_SUCCESS_RATIO,
            "maximum_consecutive_failures": STRICT_MAX_CONSECUTIVE_FAILURES,
            "recovery_after_failure_required": True,
            "source_and_published_modes_equal_weight": True,
        },
        "summary": {
            "runs_total": len(runs),
            "strict_dual_pass_count": len(strict_runs),
            "diagnostic_only_count": len(diagnostic_runs),
            "blocked_count": len(blocked_runs),
            "latest_strict_dual_pass_run_id": strict_runs[-1]["run_id"] if strict_runs else None,
            "longitudinal_trend_minimum_runs": LONGITUDINAL_TREND_MIN_RUNS,
            "longitudinal_trend_claimable": len(strict_runs) >= LONGITUDINAL_TREND_MIN_RUNS,
            "production_slo_claimable": False,
        },
        "runs": runs,
        "privacy": {
            "metadata_only": True,
            "receipt_hashes_included": True,
            "workflow_logs_included": False,
            "api_urls_included": False,
            "image_references_included": False,
            "local_absolute_paths_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "secrets_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": INDEX_CLAIM_BOUNDARY,
    }
    assert_metadata_only(index)
    return index


def write_index(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--event", choices=("schedule", "workflow_dispatch"), required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--published-receipt", type=Path, required=True)
    parser.add_argument("--previous-index", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-strict-pass",
        action="store_true",
        help="Exit non-zero unless the newly added run is a strict dual pass.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        source = read_json(args.source_receipt)
        published = read_json(args.published_receipt)
        previous = read_json(args.previous_index) if args.previous_index else None
        entry = build_run_entry(
            run_id=args.run_id,
            event=args.event,
            head_sha=args.head_sha,
            source_receipt=source,
            published_receipt=published,
        )
        index = build_index(entry=entry, previous_index=previous)
        output = args.output if args.output.is_absolute() else ROOT / args.output
        write_index(output, index)
        print(json.dumps(index, ensure_ascii=False, sort_keys=True))
        if args.require_strict_pass and entry["strict_dual_pass"] is not True:
            raise SystemExit(2)
    except ReliabilityIndexError as exc:
        print(f"reliability_evidence_index failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
