"""Official TUA-Bench Harbor-result adapter for fixed-candidate smoke cases."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
from typing import Any

from study_anything.cbb.benchmark.adapters import benchmark_privacy
from study_anything.cbb.benchmark.fixtures import pilot_assets
from study_anything.cbb.benchmark.models import (
    BenchmarkSource,
    CandidateDeliveryV1,
    EvidenceObservationV1,
    EvidenceStatus,
    OfficialScorerOutcome,
    ScorerExecutionReceiptV1,
)
from study_anything.cbb.benchmark.runner import reviewer_candidate_view
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)


TUA_REVISION = "3497fd320abcafaf4797424192c891a593fd7964"
ADAPTER_VERSION = "tua-harbor-result-adapter-v0.1"
HARBOR_RUNTIME_VERSION = "0.6.3"


class TuaHarborScorerError(RuntimeError):
    """Raised when a Harbor job cannot prove one completed official TUA scorer trial."""


@dataclass(frozen=True)
class HarborTrialObservation:
    task_name: str
    task_checksum_sha256: str
    agent_name: str
    numeric_reward: float
    started_at: str
    completed_at: str
    job_result_digest_sha256: str
    trial_result_digest_sha256: str
    job_config_digest_sha256: str


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git_value(checkout: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=checkout,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or len(value) not in {40, 64}:
        raise TuaHarborScorerError(f"cannot resolve pinned TUA-Bench object: {ref}")
    return value


def _fixture(case_id: str) -> tuple[Any, CandidateDeliveryV1]:
    for case, candidate in pilot_assets():
        if case.case_id == case_id and case.source.benchmark_id == BenchmarkSource.TUA_BENCH:
            return case, candidate
    raise TuaHarborScorerError(f"case is not a preregistered TUA-Bench pilot case: {case_id}")


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise TuaHarborScorerError(f"{label} is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TuaHarborScorerError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TuaHarborScorerError(f"{label} must be a JSON object")
    return value


def _integer(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TuaHarborScorerError(f"{label} must be an integer")
    return value


def parse_harbor_job(
    job_dir: Path,
    *,
    expected_task_name: str,
    expected_agent_name: str,
) -> HarborTrialObservation:
    """Validate one completed Harbor job without trusting its process exit code."""

    job_result_path = job_dir / "result.json"
    job_config_path = job_dir / "config.json"
    job = _read_object(job_result_path, label="Harbor job result")
    _read_object(job_config_path, label="Harbor job config")
    if job.get("finished_at") is None:
        raise TuaHarborScorerError("Harbor job is not finished")
    if _integer(job.get("n_total_trials"), label="Harbor total trial count") != 1:
        raise TuaHarborScorerError("Harbor scorer import requires exactly one trial")

    stats = job.get("stats")
    if not isinstance(stats, dict):
        raise TuaHarborScorerError("Harbor job stats are missing")
    expected_counts = {
        "n_completed_trials": 1,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
    }
    for field_name, expected in expected_counts.items():
        observed = _integer(stats.get(field_name), label=f"Harbor {field_name}")
        if observed != expected:
            raise TuaHarborScorerError(
                f"Harbor job is not a clean completed scorer trial: {field_name}={observed}"
            )

    evals = stats.get("evals")
    if not isinstance(evals, dict) or len(evals) != 1:
        raise TuaHarborScorerError("Harbor job requires exactly one evaluation summary")
    eval_stats = next(iter(evals.values()))
    if not isinstance(eval_stats, dict):
        raise TuaHarborScorerError("Harbor evaluation summary is invalid")
    if _integer(eval_stats.get("n_trials"), label="Harbor scored trial count") != 1:
        raise TuaHarborScorerError("Harbor job did not produce one scored trial")
    if _integer(eval_stats.get("n_errors"), label="Harbor evaluation error count") != 0:
        raise TuaHarborScorerError("Harbor evaluation contains an error")

    trial_result_paths = sorted(
        path for path in job_dir.glob("*/result.json") if path.parent != job_dir
    )
    if len(trial_result_paths) != 1:
        raise TuaHarborScorerError("Harbor job requires exactly one trial result file")
    trial_result_path = trial_result_paths[0]
    trial = _read_object(trial_result_path, label="Harbor trial result")
    if trial.get("exception_info") is not None:
        raise TuaHarborScorerError("Harbor trial contains an exception")
    if trial.get("task_name") != expected_task_name:
        raise TuaHarborScorerError("Harbor trial task does not match the preregistered case")
    if trial.get("finished_at") is None or trial.get("started_at") is None:
        raise TuaHarborScorerError("Harbor trial timing is incomplete")

    agent_info = trial.get("agent_info")
    if not isinstance(agent_info, dict) or agent_info.get("name") != expected_agent_name:
        raise TuaHarborScorerError("Harbor trial agent does not match the fixed candidate")
    task_checksum = trial.get("task_checksum")
    if (
        not isinstance(task_checksum, str)
        or len(task_checksum) != 64
        or any(character not in "0123456789abcdef" for character in task_checksum)
    ):
        raise TuaHarborScorerError("Harbor trial omitted a valid task checksum")

    verifier_result = trial.get("verifier_result")
    if not isinstance(verifier_result, dict):
        raise TuaHarborScorerError("Harbor trial has no verifier result")
    rewards = verifier_result.get("rewards")
    if not isinstance(rewards, dict) or set(rewards) != {"reward"}:
        raise TuaHarborScorerError("Harbor verifier must emit exactly one reward")
    reward_value = rewards.get("reward")
    if not isinstance(reward_value, (int, float)) or isinstance(reward_value, bool):
        raise TuaHarborScorerError("Harbor verifier reward must be numeric")
    reward = float(reward_value)
    if not math.isfinite(reward) or not 0.0 <= reward <= 1.0:
        raise TuaHarborScorerError("Harbor verifier reward is outside [0, 1]")

    return HarborTrialObservation(
        task_name=expected_task_name,
        task_checksum_sha256=task_checksum,
        agent_name=expected_agent_name,
        numeric_reward=reward,
        started_at=str(trial["started_at"]),
        completed_at=str(trial["finished_at"]),
        job_result_digest_sha256=_sha256_file(job_result_path),
        trial_result_digest_sha256=_sha256_file(trial_result_path),
        job_config_digest_sha256=_sha256_file(job_config_path),
    )


def score_tua_case(
    case_id: str,
    *,
    checkout: Path,
    harbor_job_dir: Path,
) -> tuple[CandidateDeliveryV1, ScorerExecutionReceiptV1, dict[str, Any]]:
    case, fixture_candidate = _fixture(case_id)
    observed_revision = _git_value(checkout, "HEAD")
    if observed_revision != TUA_REVISION:
        raise TuaHarborScorerError("TUA-Bench checkout does not match the pinned revision")
    dependency_lock = checkout / "uv.lock"
    if not dependency_lock.is_file():
        raise TuaHarborScorerError("pinned TUA-Bench dependency lock is missing")

    task_id = case.source.upstream_task_id
    expected_agent = "oracle" if case.candidate_assignment == "known_safe_control" else "nop"
    observation = parse_harbor_job(
        harbor_job_dir,
        expected_task_name=f"local/{task_id}",
        expected_agent_name=expected_agent,
    )
    task_tree_id = _git_value(checkout, f"HEAD:tasks/{task_id}")
    tests_tree_id = _git_value(checkout, f"HEAD:tasks/{task_id}/tests")
    source_environment_digest = canonical_sha256(
        {
            "benchmark_id": BenchmarkSource.TUA_BENCH.value,
            "revision": observed_revision,
            "task_tree_id": task_tree_id,
            "tests_tree_id": tests_tree_id,
            "task_checksum_sha256": observation.task_checksum_sha256,
            "harbor_runtime_version": HARBOR_RUNTIME_VERSION,
        }
    )
    subject_digest = canonical_sha256(
        {
            "case_id": case_id,
            "candidate_recipe_code": case.candidate_recipe_code,
            "source_environment_digest_sha256": source_environment_digest,
            "scorer_adapter": ADAPTER_VERSION,
        }
    )
    scorer_output_digest = canonical_sha256(
        {
            "job_result_digest_sha256": observation.job_result_digest_sha256,
            "trial_result_digest_sha256": observation.trial_result_digest_sha256,
        }
    )
    outcome = (
        OfficialScorerOutcome.PASSED
        if observation.numeric_reward == 1.0
        else OfficialScorerOutcome.FAILED
    )
    command_digest = canonical_sha256(
        {
            "adapter_version": ADAPTER_VERSION,
            "harbor_runtime_version": HARBOR_RUNTIME_VERSION,
            "job_config_digest_sha256": observation.job_config_digest_sha256,
            "task_id": task_id,
            "agent_name": expected_agent,
        }
    )
    receipt_payload = {
        "schema_version": "scorer-execution-receipt-v1",
        "receipt_id": f"scorer:{case_id}",
        "suite_id": case.suite_id,
        "case_id": case_id,
        "benchmark_id": BenchmarkSource.TUA_BENCH.value,
        "upstream_task_id": task_id,
        "subject_digest_sha256": subject_digest,
        "source_environment_digest_sha256": source_environment_digest,
        "scorer_source_uri": case.source.scorer_source_uri,
        "scorer_source_revision": observed_revision,
        "official_scorer_ref": case.source.official_scorer_ref,
        "dependency_lock_digest_sha256": _sha256_file(dependency_lock),
        "asset_manifest_digest_sha256": canonical_sha256(
            {"task_tree_id": task_tree_id, "tests_tree_id": tests_tree_id}
        ),
        "runtime_image_digests_sha256": [],
        "command_digest_sha256": command_digest,
        "scorer_output_digest_sha256": scorer_output_digest,
        "outcome": outcome.value,
        "numeric_reward": observation.numeric_reward,
        "utility_passed": None,
        "security_passed": None,
        "exit_code": 0,
        "official_scorer_executed": True,
        "started_at": observation.started_at,
        "completed_at": observation.completed_at,
        "raw_scorer_output_included": False,
        "raw_hidden_tests_included": False,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    receipt = ScorerExecutionReceiptV1.model_validate(
        {**receipt_payload, "trace_digest_sha256": canonical_sha256(receipt_payload)}
    )
    scorer_passed = outcome == OfficialScorerOutcome.PASSED
    evidence = [
        EvidenceObservationV1(
            evidence_type="source-provenance",
            status=EvidenceStatus.PASSED,
            evidence_ref=f"observed-source:{case_id}",
            evidence_digest_sha256=source_environment_digest,
            summary_code="acquired-source-scorer-revision-verified",
            blocking=True,
        ),
        EvidenceObservationV1(
            evidence_type="scorer-result",
            status=EvidenceStatus.PASSED if scorer_passed else EvidenceStatus.FAILED,
            evidence_ref=f"observed-scorer:{case_id}",
            evidence_digest_sha256=canonical_sha256(receipt),
            summary_code=(
                "official-harbor-verifier-passed"
                if scorer_passed
                else "official-harbor-verifier-failed"
            ),
            blocking=True,
        ),
        *[
            item
            for item in fixture_candidate.evidence
            if item.evidence_type
            in {
                "scope-boundary",
                "rollback-or-containment",
                "responsibility-boundary",
            }
        ],
    ]
    candidate = CandidateDeliveryV1(
        schema_version="candidate-delivery-v1",
        suite_id=case.suite_id,
        case_id=case_id,
        candidate_id=fixture_candidate.candidate_id,
        subject_digest_sha256=subject_digest,
        source_snapshot_digest_sha256=source_environment_digest,
        context_digest_sha256=fixture_candidate.context_digest_sha256,
        task_summary_code=fixture_candidate.task_summary_code,
        evidence_origin="observed_agent_run",
        declared_risk_level=fixture_candidate.declared_risk_level,
        target_scope=fixture_candidate.target_scope,
        intended_recipient_role=fixture_candidate.intended_recipient_role,
        risk_owner_role=fixture_candidate.risk_owner_role,
        prohibited_use_codes=list(fixture_candidate.prohibited_use_codes),
        scorer_outcome=outcome,
        scorer_execution_origin="observed_official_scorer",
        official_scorer_executed=True,
        scorer_trace_digest_sha256=receipt.trace_digest_sha256,
        evidence=evidence,
        tool_permission_ids=list(fixture_candidate.tool_permission_ids),
        reference_label_included=False,
        hidden_tests_included=False,
        privacy=benchmark_privacy(),
    )
    packet = {
        "schema_version": "reviewer-case-packet-v1",
        "suite_id": case.suite_id,
        "case_id": case_id,
        "candidate": reviewer_candidate_view(candidate),
        "official_scorer_result_included": False,
        "reference_label_included": False,
        "hidden_tests_included": False,
    }
    assert_safe_metadata(packet, label=f"TUA-Bench reviewer packet {case_id}")
    return candidate, receipt, packet


def write_tua_smoke(
    output_dir: Path,
    *,
    checkout: Path,
    case_jobs: dict[str, Path],
) -> dict[str, Any]:
    candidates_dir = output_dir / "observed-candidates"
    packets_dir = output_dir / "reviewer-packets"
    receipts_dir = output_dir / "scorer-receipts"
    for directory in (candidates_dir, packets_dir, receipts_dir):
        directory.mkdir(parents=True, exist_ok=True)
    manifest_cases = []
    for case_id, job_dir in sorted(case_jobs.items()):
        candidate, receipt, packet = score_tua_case(
            case_id,
            checkout=checkout,
            harbor_job_dir=job_dir,
        )
        (candidates_dir / f"{case_id}.json").write_text(pretty_json(candidate), encoding="utf-8")
        (packets_dir / f"{case_id}.json").write_text(pretty_json(packet), encoding="utf-8")
        (receipts_dir / f"{case_id}.json").write_text(pretty_json(receipt), encoding="utf-8")
        manifest_cases.append(
            {
                "case_id": case_id,
                "candidate_digest_sha256": canonical_sha256(candidate),
                "scorer_receipt_digest_sha256": canonical_sha256(receipt),
                "scorer_outcome": receipt.outcome.value,
                "numeric_reward": receipt.numeric_reward,
            }
        )
    manifest = {
        "schema_version": "tua-harbor-scorer-smoke-manifest-v1",
        "suite_id": "pilot-v0.1",
        "case_count": len(manifest_cases),
        "cases": manifest_cases,
        "official_scorer_executed": True,
        "harbor_process_exit_code_trusted_as_scorer_result": False,
        "model_calls_performed": False,
        "four_arm_review_executed": False,
        "human_reconstruction_completed": False,
        "claim_boundary": (
            "This adapter accepts only clean, completed TUA-Bench Harbor trials with an "
            "official verifier reward. It does not establish the 40-case treatment effect, "
            "production readiness, or professional certification."
        ),
    }
    assert_safe_metadata(manifest, label="TUA-Bench scorer smoke manifest")
    (output_dir / "manifest.json").write_text(pretty_json(manifest), encoding="utf-8")
    return manifest
