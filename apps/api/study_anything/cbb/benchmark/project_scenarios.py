"""Replay real repository delivery states into bounded review packets."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.benchmark.adapters import benchmark_privacy
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)
from study_anything.cbb.protocol.models import StrictProtocolModel


REAL_PROJECT_SUITE_ID: Literal["real-project-v0.1"] = "real-project-v0.1"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_SHA_PATTERN = r"^[0-9a-f]{40}$"
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._:-]{0,159}$"


class ProjectScenarioCheckV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    check_id: str = Field(pattern=IDENTIFIER_PATTERN)
    argv: list[str] = Field(min_length=1, max_length=40)
    timeout_seconds: int = Field(ge=1, le=600)
    expected_exit_code: int = Field(ge=0, le=255)
    expected_output_markers: list[str] = Field(default_factory=list, max_length=20)
    expected_failed_node_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_check(self) -> ProjectScenarioCheckV1:
        if any(not item or len(item) > 500 for item in self.argv):
            raise ValueError("project scenario argv entries must be bounded")
        if any(not item or len(item) > 240 for item in self.expected_output_markers):
            raise ValueError("project scenario output markers must be bounded")
        if len(self.expected_failed_node_ids) != len(set(self.expected_failed_node_ids)):
            raise ValueError("project scenario contains duplicate failed node ids")
        return self


class RealProjectScenarioV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["real-project-scenario-v1"]
    case_id: str = Field(pattern=IDENTIFIER_PATTERN)
    source_commit_sha: str = Field(pattern=GIT_SHA_PATTERN)
    scenario_type: str = Field(pattern=IDENTIFIER_PATTERN)
    task_summary_code: str = Field(pattern=IDENTIFIER_PATTERN)
    declared_risk_level: Literal["low", "medium", "high", "critical"]
    target_scope: Literal["personal_local"]
    intended_recipient_role: str = Field(pattern=IDENTIFIER_PATTERN)
    risk_owner_role: str = Field(pattern=IDENTIFIER_PATTERN)
    prohibited_use_codes: list[str] = Field(min_length=1, max_length=20)
    rollback_summary_code: str = Field(pattern=IDENTIFIER_PATTERN)
    check: ProjectScenarioCheckV1
    expected_machine_status: Literal["blocked", "ready_for_human_review"]
    pass_summary_code: str = Field(pattern=IDENTIFIER_PATTERN)
    failure_summary_code: str = Field(pattern=IDENTIFIER_PATTERN)
    historical_evidence: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_scenario(self) -> RealProjectScenarioV1:
        if len(self.prohibited_use_codes) != len(set(self.prohibited_use_codes)):
            raise ValueError("project scenario contains duplicate prohibited uses")
        expected = "ready_for_human_review" if self.check.expected_exit_code == 0 else "blocked"
        if self.expected_machine_status != expected:
            raise ValueError("expected machine status disagrees with expected check exit code")
        return self


class RealProjectScenarioSetV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["real-project-scenario-set-v1"]
    suite_id: Literal["real-project-v0.1"]
    source_repository: str = Field(min_length=1, max_length=240)
    evaluation_perspective: Literal["local_project_owner"]
    cases: list[RealProjectScenarioV1] = Field(min_length=1, max_length=100)
    claim_boundary: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def validate_set(self) -> RealProjectScenarioSetV1:
        case_ids = [item.case_id for item in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("real project scenario set contains duplicate case ids")
        return self


class RealProjectCheckReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["real-project-check-receipt-v1"]
    receipt_id: str = Field(pattern=IDENTIFIER_PATTERN)
    suite_id: Literal["real-project-v0.1"]
    case_id: str = Field(pattern=IDENTIFIER_PATTERN)
    source_repository: str = Field(min_length=1, max_length=240)
    source_commit_sha: str = Field(pattern=GIT_SHA_PATTERN)
    source_tree_sha: str = Field(pattern=GIT_SHA_PATTERN)
    check_id: str = Field(pattern=IDENTIFIER_PATTERN)
    command_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    exit_code: int | None = Field(default=None, ge=0, le=255)
    execution_status: Literal["passed", "failed", "timeout", "infrastructure_error"]
    machine_gate_status: Literal["blocked", "ready_for_human_review"]
    duration_ms: int = Field(ge=0, le=3_600_000)
    started_at: str = Field(min_length=1, max_length=64)
    completed_at: str = Field(min_length=1, max_length=64)
    stdout_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    stderr_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    observed_failed_node_ids: list[str] = Field(default_factory=list, max_length=100)
    expected_output_markers_matched: bool
    git_visible_state_mutated: bool
    oracle_match: bool
    raw_stdout_included: Literal[False] = False
    raw_stderr_included: Literal[False] = False
    local_absolute_paths_included: Literal[False] = False
    model_calls_performed: Literal[False] = False
    network_required: Literal[False] = False


class RealProjectCaseResultV1(StrictProtocolModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    case_id: str = Field(pattern=IDENTIFIER_PATTERN)
    scenario_type: str = Field(pattern=IDENTIFIER_PATTERN)
    source_commit_sha: str = Field(pattern=GIT_SHA_PATTERN)
    expected_machine_status: Literal["blocked", "ready_for_human_review"]
    observed_machine_status: Literal["blocked", "ready_for_human_review"]
    recommended_disposition: Literal["held", "restricted"]
    release_authorized: Literal[False] = False
    maximum_scope_without_human_review: Literal["blocked"] = "blocked"
    receipt_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewer_packet_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    oracle_match: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_scenario_set(path: Path) -> RealProjectScenarioSetV1:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load real project scenario set: {path}") from exc
    assert_safe_metadata(payload, label="real project scenario set")
    return RealProjectScenarioSetV1.model_validate(payload)


def _git(repo: Path, *args: str, timeout: int = 60) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(args)}")
    return completed.stdout.strip()


def _materialize_checkout(source_repo: Path, commit_sha: str, checkout: Path) -> None:
    completed = subprocess.run(
        ["git", "clone", "--quiet", "--shared", "--no-checkout", str(source_repo), str(checkout)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError("could not create isolated scenario checkout")
    _git(checkout, "checkout", "--detach", "--quiet", commit_sha, timeout=120)


def _resolve_argv(argv: list[str], python_executable: Path) -> list[str]:
    return [str(python_executable) if item == "{python}" else item for item in argv]


def _parse_failed_nodes(stdout: str, stderr: str) -> list[str]:
    for line in reversed((stdout + "\n" + stderr).splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        execution = payload.get("execution") if isinstance(payload, dict) else None
        failed = execution.get("failed_node_ids") if isinstance(execution, dict) else None
        if isinstance(failed, list) and all(isinstance(item, str) for item in failed):
            return sorted(set(failed))
    return []


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _run_scenario_check(
    *,
    source_repo: Path,
    source_repository: str,
    scenario: RealProjectScenarioV1,
    python_executable: Path,
) -> RealProjectCheckReceiptV1:
    started_at = _utc_now()
    started = time.monotonic()
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    execution_status: Literal["passed", "failed", "timeout", "infrastructure_error"]
    tree_sha = _git(source_repo, "rev-parse", f"{scenario.source_commit_sha}^{{tree}}")
    before_state = ""
    after_state = ""
    try:
        with tempfile.TemporaryDirectory(prefix=f"delivery-clearance-{scenario.case_id}-") as temp:
            checkout = Path(temp) / "checkout"
            _materialize_checkout(source_repo, scenario.source_commit_sha, checkout)
            before_state = _git(checkout, "status", "--porcelain=v1", "--untracked-files=all")
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            argv = _resolve_argv(scenario.check.argv, python_executable)
            try:
                completed = subprocess.run(
                    argv,
                    cwd=checkout,
                    env=env,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=scenario.check.timeout_seconds,
                )
                stdout = completed.stdout
                stderr = completed.stderr
                exit_code = completed.returncode
                execution_status = "passed" if exit_code == 0 else "failed"
            except subprocess.TimeoutExpired as exc:
                stdout = (
                    exc.stdout.decode("utf-8", errors="replace")
                    if isinstance(exc.stdout, bytes)
                    else (exc.stdout or "")
                )
                stderr = (
                    exc.stderr.decode("utf-8", errors="replace")
                    if isinstance(exc.stderr, bytes)
                    else (exc.stderr or "")
                )
                execution_status = "timeout"
            after_state = _git(checkout, "status", "--porcelain=v1", "--untracked-files=all")
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        stderr = f"{type(exc).__name__}: scenario infrastructure failed"
        execution_status = "infrastructure_error"

    combined = stdout + "\n" + stderr
    markers_matched = all(marker in combined for marker in scenario.check.expected_output_markers)
    observed_failed_nodes = _parse_failed_nodes(stdout, stderr)
    state_mutated = before_state != after_state
    observed_machine_status: Literal["blocked", "ready_for_human_review"] = (
        "ready_for_human_review"
        if execution_status == "passed" and not state_mutated
        else "blocked"
    )
    failed_nodes_match = observed_failed_nodes == sorted(scenario.check.expected_failed_node_ids)
    oracle_match = (
        exit_code == scenario.check.expected_exit_code
        and observed_machine_status == scenario.expected_machine_status
        and markers_matched
        and failed_nodes_match
        and not state_mutated
    )
    completed_at = _utc_now()
    receipt = RealProjectCheckReceiptV1(
        schema_version="real-project-check-receipt-v1",
        receipt_id=f"real-project-check:{scenario.case_id}",
        suite_id=REAL_PROJECT_SUITE_ID,
        case_id=scenario.case_id,
        source_repository=source_repository,
        source_commit_sha=scenario.source_commit_sha,
        source_tree_sha=tree_sha,
        check_id=scenario.check.check_id,
        command_digest_sha256=canonical_sha256(
            {"argv": scenario.check.argv, "timeout_seconds": scenario.check.timeout_seconds}
        ),
        exit_code=exit_code,
        execution_status=execution_status,
        machine_gate_status=observed_machine_status,
        duration_ms=int((time.monotonic() - started) * 1000),
        started_at=started_at,
        completed_at=completed_at,
        stdout_digest_sha256=_digest_text(stdout),
        stderr_digest_sha256=_digest_text(stderr),
        observed_failed_node_ids=observed_failed_nodes,
        expected_output_markers_matched=markers_matched,
        git_visible_state_mutated=state_mutated,
        oracle_match=oracle_match,
    )
    assert_safe_metadata(receipt.model_dump(mode="json"), label="real project check receipt")
    return receipt


def _evidence_item(
    *,
    scenario: RealProjectScenarioV1,
    evidence_type: str,
    status: Literal["passed", "failed"],
    summary_code: str,
    blocking: bool,
) -> dict[str, Any]:
    payload = {
        "evidence_ref": f"real-project:{scenario.case_id}:{evidence_type}",
        "evidence_type": evidence_type,
        "status": status,
        "summary_code": summary_code,
        "blocking": blocking,
    }
    payload["evidence_digest_sha256"] = canonical_sha256(payload)
    return payload


def build_reviewer_packet(
    scenario: RealProjectScenarioV1,
    receipt: RealProjectCheckReceiptV1,
) -> dict[str, Any]:
    check_passed = receipt.machine_gate_status == "ready_for_human_review"
    visible_evidence = [
        _evidence_item(
            scenario=scenario,
            evidence_type="source-provenance",
            status="passed",
            summary_code="repository-commit-and-tree-bound",
            blocking=True,
        ),
        _evidence_item(
            scenario=scenario,
            evidence_type="project-release-check",
            status="passed" if check_passed else "failed",
            summary_code=(
                scenario.pass_summary_code if check_passed else scenario.failure_summary_code
            ),
            blocking=True,
        ),
        _evidence_item(
            scenario=scenario,
            evidence_type="scope-boundary",
            status="passed",
            summary_code="personal-local-only",
            blocking=True,
        ),
        _evidence_item(
            scenario=scenario,
            evidence_type="rollback-or-containment",
            status="passed",
            summary_code=scenario.rollback_summary_code,
            blocking=True,
        ),
        _evidence_item(
            scenario=scenario,
            evidence_type="responsibility-boundary",
            status="passed",
            summary_code="local-project-owner-responsible",
            blocking=True,
        ),
    ]
    candidate: dict[str, Any] = {
        "schema_version": "reviewer-candidate-view-v1",
        "suite_id": REAL_PROJECT_SUITE_ID,
        "case_id": scenario.case_id,
        "candidate_id": f"candidate:{scenario.case_id}",
        "task_summary_code": scenario.task_summary_code,
        "declared_risk_level": scenario.declared_risk_level,
        "target_scope": scenario.target_scope,
        "intended_recipient_role": scenario.intended_recipient_role,
        "risk_owner_role": scenario.risk_owner_role,
        "prohibited_use_codes": scenario.prohibited_use_codes,
        "tool_permission_ids": [
            "read_candidate_metadata",
            "read_evidence_metadata",
            "request_additional_evidence",
            "emit_clearance_decision",
        ],
        "subject_digest_sha256": canonical_sha256(
            {
                "source_repository": receipt.source_repository,
                "source_commit_sha": receipt.source_commit_sha,
                "source_tree_sha": receipt.source_tree_sha,
            }
        ),
        "source_snapshot_digest_sha256": canonical_sha256(
            {
                "source_commit_sha": receipt.source_commit_sha,
                "source_tree_sha": receipt.source_tree_sha,
            }
        ),
        "context_digest_sha256": canonical_sha256(
            {
                "scenario_type": scenario.scenario_type,
                "check_id": receipt.check_id,
                "command_digest_sha256": receipt.command_digest_sha256,
            }
        ),
        "visible_evidence": visible_evidence,
        "official_scorer_result_included": False,
        "reference_label_included": False,
        "hidden_tests_included": False,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    candidate["candidate_digest_sha256"] = canonical_sha256(candidate)
    packet = {
        "schema_version": "reviewer-case-packet-v1",
        "suite_id": REAL_PROJECT_SUITE_ID,
        "case_id": scenario.case_id,
        "candidate": candidate,
        "official_scorer_result_included": False,
        "reference_label_included": False,
        "hidden_tests_included": False,
    }
    assert_safe_metadata(packet, label="real project reviewer packet")
    return packet


def _report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Real Project Delivery Evaluation v0.1",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is a replay of real repository delivery states. It is not a user-effectiveness or production-safety claim.",
        "",
        "| Case | Historical state | Expected | Observed | Oracle |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["cases"]:
        lines.append(
            "| {case_id} | {scenario_type} | {expected_machine_status} | "
            "{observed_machine_status} | {oracle} |".format(
                **item,
                oracle="match" if item["oracle_match"] else "mismatch",
            )
        )
    lines.extend(
        [
            "",
            "A machine pass only creates a human-review candidate. It never authorizes release by itself.",
            "",
        ]
    )
    return "\n".join(lines)


def run_real_project_scenarios(
    *,
    source_repo: Path,
    scenario_set: RealProjectScenarioSetV1,
    output_dir: Path,
    python_executable: Path,
    replace: bool = False,
) -> dict[str, Any]:
    source_repo = source_repo.resolve()
    output_dir = output_dir.resolve()
    if not (source_repo / ".git").exists():
        raise ValueError("real project scenario replay requires a Git repository")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not replace:
            raise ValueError("real project scenario output is not empty; pass replace=True")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    receipts_dir = output_dir / "check-receipts"
    packets_dir = output_dir / "reviewer-packets"
    receipts_dir.mkdir()
    packets_dir.mkdir()

    case_results: list[RealProjectCaseResultV1] = []
    for scenario in scenario_set.cases:
        receipt = _run_scenario_check(
            source_repo=source_repo,
            source_repository=scenario_set.source_repository,
            scenario=scenario,
            python_executable=python_executable,
        )
        packet = build_reviewer_packet(scenario, receipt)
        receipt_path = receipts_dir / f"{scenario.case_id}.json"
        packet_path = packets_dir / f"{scenario.case_id}.json"
        receipt_path.write_text(pretty_json(receipt), encoding="utf-8")
        packet_path.write_text(
            json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        case_results.append(
            RealProjectCaseResultV1(
                case_id=scenario.case_id,
                scenario_type=scenario.scenario_type,
                source_commit_sha=scenario.source_commit_sha,
                expected_machine_status=scenario.expected_machine_status,
                observed_machine_status=receipt.machine_gate_status,
                recommended_disposition=(
                    "restricted"
                    if receipt.machine_gate_status == "ready_for_human_review"
                    else "held"
                ),
                receipt_digest_sha256=canonical_sha256(receipt),
                reviewer_packet_digest_sha256=canonical_sha256(packet),
                oracle_match=receipt.oracle_match,
            )
        )

    all_match = all(item.oracle_match for item in case_results)
    report: dict[str, Any] = {
        "schema_version": "real-project-scenario-result-v1",
        "suite_id": REAL_PROJECT_SUITE_ID,
        "status": "pass" if all_match else "blocked",
        "source_repository": scenario_set.source_repository,
        "scenario_set_digest_sha256": canonical_sha256(scenario_set),
        "case_count": len(case_results),
        "blocked_case_count": sum(
            item.observed_machine_status == "blocked" for item in case_results
        ),
        "ready_for_human_review_count": sum(
            item.observed_machine_status == "ready_for_human_review" for item in case_results
        ),
        "human_review_completed": False,
        "release_authorized": False,
        "maximum_scope_without_human_review": "blocked",
        "cases": [item.model_dump(mode="json") for item in case_results],
        "execution_environment": {
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
        },
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_check_output_included": False,
            "local_absolute_paths_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": scenario_set.claim_boundary,
    }
    assert_safe_metadata(report, label="real project scenario result")
    (output_dir / "scenario-set.json").write_text(pretty_json(scenario_set), encoding="utf-8")
    (output_dir / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(_report_markdown(report), encoding="utf-8")
    return report


def default_python_executable(repo_root: Path) -> Path:
    candidate = repo_root / ".venv" / "bin" / "python"
    return candidate.resolve() if candidate.is_file() else Path(sys.executable).resolve()
