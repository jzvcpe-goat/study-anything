"""Cognitive Loop advisory code review contracts and renderer.

The review loop is intentionally local-first and advisory-only. It consumes
path-level git metadata or a redacted PR summary, then produces public DTOs and
static artifacts that platform Agents can read without Study Anything storing
model keys, Agent endpoints, raw diffs, or file contents.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping, Optional

try:
    from . import cognitive_loop_contracts as contracts
except Exception:  # pragma: no cover - exercised by standalone script loaders.
    CONTRACT_MODULE_PATH = Path(__file__).with_name("cognitive_loop_contracts.py")
    spec = importlib.util.spec_from_file_location(
        "study_anything_cognitive_loop_contracts", CONTRACT_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise
    contracts = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = contracts
    spec.loader.exec_module(contracts)


REVIEW_ARTIFACT_SCHEMA_VERSION = "cognitive-loop-code-review-artifact-v1"
REVIEW_RUN_SCHEMA_VERSION = "cognitive-loop-review-run-v1"
REVIEW_FINDING_SCHEMA_VERSION = "cognitive-loop-review-finding-v1"
REVIEW_TEST_GAP_SCHEMA_VERSION = "cognitive-loop-review-test-gap-v1"
REVIEW_SECURITY_GATE_SCHEMA_VERSION = "cognitive-loop-review-security-gate-v1"
REVIEW_DECISION_SCHEMA_VERSION = "cognitive-loop-review-decision-v1"
REVIEW_METRICS_SCHEMA_VERSION = "cognitive-loop-review-metrics-v1"

MAX_REVIEW_FINDINGS = 5
ALLOWED_REVIEW_SOURCES = {"git_diff", "worktree_diff", "pr_summary"}
ALLOWED_REVIEW_STATUSES = {"pass", "attention", "needs_human_review"}
ALLOWED_REVIEW_STAGES = {
    "contract",
    "implementation",
    "security",
    "testing",
    "documentation",
    "release",
}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "blocked": 3}


@dataclass(frozen=True)
class ReviewChange:
    file_path: str
    status: str
    diff_ref: str
    insertions: int = 0
    deletions: int = 0

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    title: str
    summary: str
    file_path: str
    diff_ref: str
    risk_level: str
    risk_rule_id: str
    stage: str
    confidence: float
    verification_command: str
    schema_version: str = REVIEW_FINDING_SCHEMA_VERSION

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewTestGap:
    gap_id: str
    summary: str
    file_path: str
    expected_test_area: str
    risk_level: str
    verification_command: str
    schema_version: str = REVIEW_TEST_GAP_SCHEMA_VERSION

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewSecurityGate:
    gate_id: str
    mode: str
    status: str
    blocking: bool
    hard_gate_enabled: bool
    merge_blocked: bool
    highest_risk: str
    reasons: list[str]
    schema_version: str = REVIEW_SECURITY_GATE_SCHEMA_VERSION

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewDecision:
    decision_id: str
    status: str
    recommendation: str
    merge_blocked: bool
    requires_human_review: bool
    verification_commands: list[str]
    schema_version: str = REVIEW_DECISION_SCHEMA_VERSION

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewMetrics:
    changed_file_count: int
    finding_count: int
    test_gap_count: int
    highest_risk: str
    max_findings: int
    reviewer_id: str
    deterministic: bool
    raw_diff_included: bool
    file_contents_included: bool
    model_keys_stored: bool
    agent_endpoints_stored: bool
    schema_version: str = REVIEW_METRICS_SCHEMA_VERSION

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewRun:
    run_id: str
    project_id: str
    source: str
    base_ref: Optional[str]
    head_ref: Optional[str]
    status: str
    started_at: str
    completed_at: str
    changed_files: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    test_gaps: list[dict[str, Any]]
    security_gate: dict[str, Any]
    decision: dict[str, Any]
    metrics: dict[str, Any]
    schema_version: str = REVIEW_RUN_SCHEMA_VERSION

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


class CognitiveLoopReviewError(ValueError):
    """Raised when review input or output is unsafe."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(
        json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _assert_public(value: Any, label: str = "review") -> None:
    try:
        contracts._assert_public_value(label, value)  # type: ignore[attr-defined]
    except contracts.CognitiveLoopContractError as exc:
        raise CognitiveLoopReviewError(str(exc)) from exc


def _safe_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def _safe_repo_path(raw_path: str) -> str:
    if not isinstance(raw_path, str):
        raise CognitiveLoopReviewError("Review change path must be a string.")
    normalized = raw_path.strip().replace("\\", "/")
    if not normalized:
        raise CognitiveLoopReviewError("Review change path cannot be empty.")
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise CognitiveLoopReviewError(f"Review change path must be repo-relative: {raw_path}.")
    if "\n" in normalized or "\r" in normalized:
        raise CognitiveLoopReviewError("Review change path cannot contain newlines.")
    _assert_public(normalized, "review_change_path")
    return normalized


def _diff_ref(base_ref: Optional[str], head_ref: Optional[str], file_path: str) -> str:
    if base_ref and head_ref:
        ref = f"git:{base_ref}...{head_ref}:{file_path}"
    elif base_ref:
        ref = f"git:{base_ref}..worktree:{file_path}"
    else:
        ref = f"git:worktree:{file_path}"
    _assert_public(ref, "review_diff_ref")
    return ref


def _change_from_mapping(
    values: Mapping[str, Any],
    *,
    base_ref: Optional[str],
    head_ref: Optional[str],
) -> ReviewChange:
    file_path = _safe_repo_path(str(values.get("file_path") or values.get("path") or ""))
    status = str(values.get("status") or "M").strip()[:20] or "M"
    _assert_public(status, "review_change_status")
    diff_ref = str(values.get("diff_ref") or _diff_ref(base_ref, head_ref, file_path))
    _assert_public(diff_ref, "review_change_diff_ref")
    return ReviewChange(
        file_path=file_path,
        status=status,
        diff_ref=diff_ref,
        insertions=_safe_int(values.get("insertions")),
        deletions=_safe_int(values.get("deletions")),
    )


def load_pr_summary_changes(
    summary_path: Path,
    *,
    base_ref: Optional[str] = None,
    head_ref: Optional[str] = None,
) -> list[ReviewChange]:
    """Load a redacted PR summary file without accepting raw diff bodies."""

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise CognitiveLoopReviewError("PR summary must be a JSON object.")
    forbidden = {"diff", "patch", "raw_diff", "raw_payload", "file_contents", "source_text"}
    present = forbidden.intersection(str(key) for key in data.keys())
    if present:
        raise CognitiveLoopReviewError(
            f"PR summary cannot include raw diff or file content fields: {sorted(present)}"
        )
    files = data.get("changed_files", data.get("files"))
    if not isinstance(files, list):
        raise CognitiveLoopReviewError("PR summary must include changed_files or files.")
    changes = [
        _change_from_mapping(item, base_ref=base_ref, head_ref=head_ref)
        for item in files
        if isinstance(item, Mapping)
    ]
    if len(changes) != len(files):
        raise CognitiveLoopReviewError("Every PR summary file entry must be an object.")
    return _dedupe_changes(changes)


def _run_git(root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CognitiveLoopReviewError(f"Cannot collect git review metadata: {exc}") from exc
    return completed.stdout


def _parse_name_status(output: str, *, base_ref: Optional[str], head_ref: Optional[str]) -> dict[str, ReviewChange]:
    changes: dict[str, ReviewChange] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0].strip()
        raw_path = parts[-1] if len(parts) > 1 else ""
        file_path = _safe_repo_path(raw_path)
        changes[file_path] = ReviewChange(
            file_path=file_path,
            status=status,
            diff_ref=_diff_ref(base_ref, head_ref, file_path),
        )
    return changes


def _apply_numstat(changes: dict[str, ReviewChange], output: str) -> None:
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        insertions = 0 if parts[0] == "-" else _safe_int(parts[0])
        deletions = 0 if parts[1] == "-" else _safe_int(parts[1])
        file_path = _safe_repo_path(parts[-1])
        existing = changes.get(file_path)
        if existing is None:
            changes[file_path] = ReviewChange(
                file_path=file_path,
                status="M",
                diff_ref=_diff_ref(None, None, file_path),
                insertions=insertions,
                deletions=deletions,
            )
        else:
            changes[file_path] = ReviewChange(
                file_path=existing.file_path,
                status=existing.status,
                diff_ref=existing.diff_ref,
                insertions=insertions,
                deletions=deletions,
            )


def _untracked_changes(root: Path) -> list[ReviewChange]:
    output = _run_git(root, ["status", "--short", "--untracked-files=all"])
    changes: list[ReviewChange] = []
    for line in output.splitlines():
        if not line.startswith("?? "):
            continue
        file_path = _safe_repo_path(line[3:].strip())
        changes.append(
            ReviewChange(
                file_path=file_path,
                status="A",
                diff_ref=_diff_ref(None, None, file_path),
            )
        )
    return changes


def collect_git_review_changes(
    root: Path,
    *,
    base_ref: Optional[str] = None,
    head_ref: Optional[str] = None,
) -> list[ReviewChange]:
    """Collect path-level git metadata without reading diff bodies."""

    if base_ref and head_ref:
        range_ref = f"{base_ref}...{head_ref}"
        name_status = _run_git(root, ["diff", "--name-status", "--find-renames", range_ref])
        numstat = _run_git(root, ["diff", "--numstat", range_ref])
    elif base_ref:
        name_status = _run_git(root, ["diff", "--name-status", "--find-renames", base_ref])
        numstat = _run_git(root, ["diff", "--numstat", base_ref])
    else:
        name_status = _run_git(root, ["diff", "--name-status", "--find-renames", "HEAD"])
        numstat = _run_git(root, ["diff", "--numstat", "HEAD"])

    changes = _parse_name_status(name_status, base_ref=base_ref, head_ref=head_ref)
    _apply_numstat(changes, numstat)
    if not base_ref and not head_ref:
        for change in _untracked_changes(root):
            changes.setdefault(change.file_path, change)
    return _dedupe_changes(changes.values())


def _dedupe_changes(changes: Iterable[ReviewChange]) -> list[ReviewChange]:
    by_path: dict[str, ReviewChange] = {}
    for change in changes:
        by_path[_safe_repo_path(change.file_path)] = change
    return [by_path[path] for path in sorted(by_path)]


def _risk_rules(root: Path) -> dict[str, Mapping[str, Any]]:
    risk_path = contracts.contract_dir(root) / "risk.yaml"
    data = contracts._load_yaml(risk_path)  # type: ignore[attr-defined]
    contracts._validate_risk(data)  # type: ignore[attr-defined]
    rules = data.get("rules")
    if not isinstance(rules, list):
        return {}
    return {
        str(item.get("id")): item
        for item in rules
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }


def _classify_change(root: Path, change: ReviewChange) -> tuple[str, str, str, str]:
    rules = _risk_rules(root)
    path = change.file_path.lower()
    if any(marker in path for marker in ("raw_source_upload", "model_key_storage", "hidden_instruction_transfer")):
        return ("blocked", "external-data-exfiltration", "security", "external-data-exfiltration")
    if any(marker in path for marker in ("auth", "billing", "secret", "credential", "permissions", ".env", "plugin")):
        return ("high", "sensitive-runtime", "security", "sensitive runtime or secret-handling path")
    if (
        path.startswith("apps/api/")
        or path.startswith("scripts/")
        or path.startswith(".cognitive-loop/")
        or path.startswith("infra/")
        or path.startswith("platform/generated/")
        or path in {"pyproject.toml", "docker-compose.yml"}
        or "compose" in path
        or "docker" in path
    ):
        rule_id = "runtime-contract" if "runtime-contract" in rules else "docs-only"
        return ("medium", rule_id, "implementation", "runtime, verifier, or release asset boundary")
    if path.startswith("docs/") or path.endswith(".md"):
        return ("low", "docs-only", "documentation", "documentation-only change")
    return ("low", "docs-only", "implementation", "path-level change")


def _verification_command(change: ReviewChange, *, stage: str) -> str:
    path = change.file_path
    if path.startswith("apps/api/") or path.startswith("scripts/"):
        return ".venv/bin/python -m unittest discover apps/api/tests"
    if path.startswith(".cognitive-loop/"):
        return "python3 scripts/verify_cognitive_loop_contracts.py --check"
    if path.startswith("docs/") or path.endswith(".md"):
        return "python3 scripts/generate_platform_adoption_pack.py --check"
    if path.startswith("infra/") or "compose" in path or "docker" in path:
        return "docker compose -f infra/compose/docker-compose.yml config"
    if stage == "security":
        return "python3 scripts/verify_security_recovery_hardening.py"
    return "./scripts/release_check.sh"


def _finding_title(change: ReviewChange, *, risk_level: str, stage: str) -> str:
    if risk_level in {"high", "blocked"}:
        return "Review sensitive boundary before merge"
    if stage == "documentation":
        return "Verify public docs remain aligned with generated adoption assets"
    if change.file_path.startswith("scripts/"):
        return "Verify script change has deterministic evidence"
    if change.file_path.startswith("apps/api/"):
        return "Verify backend contract or runtime behavior with tests"
    return "Review changed path with Cognitive Loop advisory evidence"


def fake_deterministic_review_findings(
    root: Path,
    *,
    changes: Iterable[ReviewChange],
    max_findings: int = MAX_REVIEW_FINDINGS,
) -> list[ReviewFinding]:
    """Generate deterministic advisory findings from path-level metadata."""

    findings: list[ReviewFinding] = []
    for change in _dedupe_changes(changes):
        risk_level, rule_id, stage, reason = _classify_change(root, change)
        contracts._require_members([risk_level], contracts.ALLOWED_RISK_LEVELS, "ReviewFinding risk")  # type: ignore[attr-defined]
        if stage not in ALLOWED_REVIEW_STAGES:
            stage = "implementation"
        confidence = {
            "blocked": 0.92,
            "high": 0.88,
            "medium": 0.82,
            "low": 0.72,
        }[risk_level]
        finding = ReviewFinding(
            finding_id=_stable_id("finding", change.file_path, change.status, risk_level),
            title=_finding_title(change, risk_level=risk_level, stage=stage),
            summary=(
                f"{change.file_path} maps to .cognitive-loop/risk.yaml rule "
                f"{rule_id} because it touches {reason}."
            ),
            file_path=change.file_path,
            diff_ref=change.diff_ref,
            risk_level=risk_level,
            risk_rule_id=rule_id,
            stage=stage,
            confidence=confidence,
            verification_command=_verification_command(change, stage=stage),
        )
        validate_review_finding(finding.public_dict())
        findings.append(finding)
    findings.sort(key=lambda item: (-RISK_ORDER[item.risk_level], item.file_path))
    return findings[:max_findings]


def deterministic_test_gaps(changes: Iterable[ReviewChange]) -> list[ReviewTestGap]:
    change_list = _dedupe_changes(changes)
    has_test_change = any(
        path.file_path.startswith("apps/api/tests/") or "/tests/" in path.file_path
        for path in change_list
    )
    if has_test_change:
        return []
    gaps: list[ReviewTestGap] = []
    for change in change_list:
        path = change.file_path
        if not (path.startswith("apps/api/study_anything/") or path.startswith("scripts/")):
            continue
        gap = ReviewTestGap(
            gap_id=_stable_id("testgap", path),
            summary="Runtime or script change has no paired test path in this diff metadata.",
            file_path=path,
            expected_test_area="apps/api/tests",
            risk_level="medium",
            verification_command=".venv/bin/python -m unittest discover apps/api/tests",
        )
        validate_review_test_gap(gap.public_dict())
        gaps.append(gap)
    return gaps[:MAX_REVIEW_FINDINGS]


def _highest_risk(*levels: str) -> str:
    if not levels:
        return "low"
    return max(levels, key=lambda level: RISK_ORDER.get(level, 0))


def validate_review_finding(values: Mapping[str, Any]) -> ReviewFinding:
    _assert_public(values, "review_finding")
    risk_level = str(values.get("risk_level") or "")
    contracts._require_members([risk_level], contracts.ALLOWED_RISK_LEVELS, "ReviewFinding risk")  # type: ignore[attr-defined]
    stage = str(values.get("stage") or "")
    if stage not in ALLOWED_REVIEW_STAGES:
        raise CognitiveLoopReviewError(f"Unsupported ReviewFinding stage: {stage}")
    confidence = float(values.get("confidence", -1))
    if not 0 <= confidence <= 1:
        raise CognitiveLoopReviewError("ReviewFinding confidence must be between 0 and 1.")
    return ReviewFinding(
        finding_id=str(values["finding_id"]),
        title=str(values["title"]),
        summary=str(values["summary"]),
        file_path=_safe_repo_path(str(values["file_path"])),
        diff_ref=str(values["diff_ref"]),
        risk_level=risk_level,
        risk_rule_id=str(values["risk_rule_id"]),
        stage=stage,
        confidence=confidence,
        verification_command=str(values["verification_command"]),
    )


def validate_review_test_gap(values: Mapping[str, Any]) -> ReviewTestGap:
    _assert_public(values, "review_test_gap")
    risk_level = str(values.get("risk_level") or "")
    contracts._require_members([risk_level], contracts.ALLOWED_RISK_LEVELS, "ReviewTestGap risk")  # type: ignore[attr-defined]
    return ReviewTestGap(
        gap_id=str(values["gap_id"]),
        summary=str(values["summary"]),
        file_path=_safe_repo_path(str(values["file_path"])),
        expected_test_area=str(values["expected_test_area"]),
        risk_level=risk_level,
        verification_command=str(values["verification_command"]),
    )


def validate_review_artifact(report: Mapping[str, Any]) -> Mapping[str, Any]:
    _assert_public(report, "review_artifact")
    if report.get("schema_version") != REVIEW_ARTIFACT_SCHEMA_VERSION:
        raise CognitiveLoopReviewError("Unsupported review artifact schema.")
    review_run = report.get("review_run")
    if not isinstance(review_run, Mapping):
        raise CognitiveLoopReviewError("Review artifact requires review_run.")
    findings = review_run.get("findings")
    if not isinstance(findings, list):
        raise CognitiveLoopReviewError("ReviewRun findings must be a list.")
    if len(findings) > MAX_REVIEW_FINDINGS:
        raise CognitiveLoopReviewError("ReviewRun findings exceed the max finding cap.")
    for finding in findings:
        if not isinstance(finding, Mapping):
            raise CognitiveLoopReviewError("Each ReviewFinding must be an object.")
        validate_review_finding(finding)
    security_gate = review_run.get("security_gate")
    if not isinstance(security_gate, Mapping):
        raise CognitiveLoopReviewError("ReviewRun requires security_gate.")
    if security_gate.get("blocking") is not False or security_gate.get("merge_blocked") is not False:
        raise CognitiveLoopReviewError("Code Review Loop v0.1 must remain advisory-only.")
    metrics = review_run.get("metrics")
    if not isinstance(metrics, Mapping):
        raise CognitiveLoopReviewError("ReviewRun requires metrics.")
    if metrics.get("raw_diff_included") is not False or metrics.get("file_contents_included") is not False:
        raise CognitiveLoopReviewError("Review artifact cannot include raw diffs or file contents.")
    if metrics.get("model_keys_stored") is not False or metrics.get("agent_endpoints_stored") is not False:
        raise CognitiveLoopReviewError("Review artifact cannot store model keys or Agent endpoints.")
    return report


def build_review_artifact(
    root: Path,
    *,
    changes: Iterable[ReviewChange],
    source: str = "git_diff",
    base_ref: Optional[str] = None,
    head_ref: Optional[str] = None,
    reviewer_id: str = "fake-deterministic-reviewer",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-review.html",
) -> dict[str, Any]:
    """Build a public advisory ReviewRun plus DecisionCard evidence."""

    if source not in ALLOWED_REVIEW_SOURCES:
        raise CognitiveLoopReviewError(f"Unsupported review source: {source}")
    generated_at = generated_at or _utc_now()
    _assert_public(reviewer_id, "reviewer_id")
    _assert_public(artifact_ref, "artifact_ref")
    project = contracts._project_metadata(root)  # type: ignore[attr-defined]
    contract_reports = [report.public_dict() for report in contracts.validate_contract_files(root)]
    change_list = _dedupe_changes(changes)
    findings = fake_deterministic_review_findings(root, changes=change_list)
    test_gaps = deterministic_test_gaps(change_list)
    highest = _highest_risk(
        *[finding.risk_level for finding in findings],
        *[gap.risk_level for gap in test_gaps],
    )
    review_status = "pass" if not findings and not test_gaps else (
        "needs_human_review" if highest in {"high", "blocked"} else "attention"
    )
    verification_commands = sorted(
        {
            "python3 scripts/cognitive_loop_review.py --base main --head HEAD --html",
            "python3 scripts/verify_cognitive_loop_review.py --check",
            *[finding.verification_command for finding in findings],
            *[gap.verification_command for gap in test_gaps],
        }
    )
    security_reasons = (
        [f"{highest} advisory findings require operator review"]
        if findings or test_gaps
        else ["no advisory findings generated"]
    )
    security_gate = ReviewSecurityGate(
        gate_id=_stable_id("reviewgate", generated_at, highest),
        mode="advisory",
        status="attention" if findings or test_gaps else "pass",
        blocking=False,
        hard_gate_enabled=False,
        merge_blocked=False,
        highest_risk=highest,
        reasons=security_reasons,
    )
    review_decision = ReviewDecision(
        decision_id=_stable_id("reviewdecision", generated_at, highest),
        status=review_status,
        recommendation=(
            "Review findings before merge; v0.1 does not block."
            if findings or test_gaps
            else "No advisory findings; continue with normal verification."
        ),
        merge_blocked=False,
        requires_human_review=highest in {"high", "blocked"},
        verification_commands=verification_commands,
    )
    metrics = ReviewMetrics(
        changed_file_count=len(change_list),
        finding_count=len(findings),
        test_gap_count=len(test_gaps),
        highest_risk=highest,
        max_findings=MAX_REVIEW_FINDINGS,
        reviewer_id=reviewer_id,
        deterministic=reviewer_id == "fake-deterministic-reviewer",
        raw_diff_included=False,
        file_contents_included=False,
        model_keys_stored=False,
        agent_endpoints_stored=False,
    )
    run_id = _stable_id(
        "reviewrun",
        project["id"],
        base_ref,
        head_ref,
        [change.public_dict() for change in change_list],
    )
    event = contracts.validate_project_event(
        {
            "event_id": _stable_id("evt-review", run_id),
            "project_id": project["id"],
            "actor": "agent",
            "event_type": "git_diff_changed" if change_list else "human_note",
            "summary": (
                f"Code Review Loop inspected {len(change_list)} changed path"
                f"{'' if len(change_list) == 1 else 's'} in advisory mode."
            ),
            "timestamp": generated_at,
            "target": "git:diff" if source != "pr_summary" else "pr:summary",
            "refs": [f"path:{change.file_path}" for change in change_list[:12]],
            "sensitivity": "internal",
        }
    ).public_dict()
    needs_gate = highest in {"high", "blocked"}
    decision_card = contracts.validate_decision_card(
        {
            "decision_id": _stable_id("dec-review", run_id),
            "project_id": project["id"],
            "title": "Review Code Review Loop advisory findings",
            "status": "needs_human_mastery" if needs_gate else "approved",
            "summary": (
                "ReviewRun, findings, test gaps, and security gate are advisory-only evidence. "
                "No merge is blocked by v0.1."
            ),
            "event_ids": [event["event_id"]],
            "evidence_refs": [
                f"artifact:{artifact_ref}",
                "contract:.cognitive-loop/risk.yaml",
                "contract:.cognitive-loop/evals.yaml",
                "script:scripts/cognitive_loop_review.py",
                "script:scripts/verify_cognitive_loop_review.py",
            ],
            "risk": {
                "level": highest,
                "score": {"low": 0.2, "medium": 0.48, "high": 0.82, "blocked": 1.0}[highest],
                "reasons": [
                    "advisory review evidence",
                    "risk mapped from .cognitive-loop/risk.yaml",
                    "no hard gate in v0.1",
                ],
            },
            "human_mastery_gate": {
                "required": needs_gate,
                "status": "pending" if needs_gate else "not_required",
                "questions": [
                    "Can the operator explain each high-confidence finding?",
                    "Can the operator run the suggested verification commands?",
                    "Can the operator confirm no raw diff, secrets, or Agent endpoint is stored?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": verification_commands,
            },
            "rollback": {"strategy": "delete_review_artifacts", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop_run = contracts.validate_loop_run(
        {
            "run_id": _stable_id("loop-review", run_id),
            "project_id": project["id"],
            "objective": "Generate local-first advisory code review evidence.",
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision_card["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    evolution_report = contracts.validate_evolution_report(
        {
            "report_id": _stable_id("evo-review", run_id),
            "project_id": project["id"],
            "status": "needs_review" if findings or test_gaps else "approved",
            "proposed_changes": [
                "Inspect changed path metadata",
                "Map review findings to local risk rules",
                "Run suggested verification commands before merge",
            ],
            "decision_card_ids": [decision_card["decision_id"]],
            "verification_refs": ["python3 scripts/verify_cognitive_loop_review.py --check"],
            "risk_summary": (
                "Code Review Loop v0.1 is advisory-only and stores no raw diff, file contents, "
                "model keys, Agent endpoints, or Agent reasoning."
            ),
            "created_at": generated_at,
        }
    ).public_dict()
    review_run = ReviewRun(
        run_id=run_id,
        project_id=project["id"],
        source=source,
        base_ref=base_ref,
        head_ref=head_ref,
        status=review_status,
        started_at=generated_at,
        completed_at=generated_at,
        changed_files=[change.public_dict() for change in change_list],
        findings=[finding.public_dict() for finding in findings],
        test_gaps=[gap.public_dict() for gap in test_gaps],
        security_gate=security_gate.public_dict(),
        decision=review_decision.public_dict(),
        metrics=metrics.public_dict(),
    ).public_dict()
    report = {
        "schema_version": REVIEW_ARTIFACT_SCHEMA_VERSION,
        "status": review_status,
        "generated_at": generated_at,
        "title": "Cognitive Loop Code Review Advisory",
        "project": project,
        "source": source,
        "contract_files": contract_reports,
        "project_event": event,
        "decision_card": decision_card,
        "loop_run": loop_run,
        "evolution_report": evolution_report,
        "review_run": review_run,
        "risk_mapping": {
            "source": ".cognitive-loop/risk.yaml",
            "levels": list(contracts.ALLOWED_RISK_LEVELS),
            "highest_risk": highest,
        },
        "privacy": {
            "raw_diff_included": False,
            "file_contents_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "real_model_keys_included": False,
            "agent_reasoning_included": False,
            "standalone_frontend_required": False,
        },
        "current_limits": [
            "v0.1 is advisory-only and does not block merges.",
            "The built-in reviewer is deterministic and path-metadata based.",
            "Real review Agents must be external BYO Agent or platform Agent integrations.",
            "No standalone frontend is introduced; the output is local JSON plus static HTML.",
        ],
        "commands": {
            "review": "python3 scripts/cognitive_loop_review.py --base main --head HEAD --html",
            "verify_review": "python3 scripts/verify_cognitive_loop_review.py --check",
            "tests": ".venv/bin/python -m unittest discover apps/api/tests",
        },
    }
    validate_review_artifact(report)
    return report


def render_review_artifact_html(report: Mapping[str, Any]) -> str:
    """Render a static advisory review artifact without embedding private data."""

    validate_review_artifact(report)
    review_run = report["review_run"]
    assert isinstance(review_run, Mapping)
    findings = review_run.get("findings")
    if not isinstance(findings, list):
        findings = []
    gaps = review_run.get("test_gaps")
    if not isinstance(gaps, list):
        gaps = []
    changes = review_run.get("changed_files")
    if not isinstance(changes, list):
        changes = []
    gate = review_run.get("security_gate")
    if not isinstance(gate, Mapping):
        gate = {}
    decision = review_run.get("decision")
    if not isinstance(decision, Mapping):
        decision = {}
    commands = report.get("commands")
    if not isinstance(commands, Mapping):
        commands = {}

    def value(path: str, fallback: str = "") -> str:
        current: Any = report
        for part in path.split("."):
            if not isinstance(current, Mapping):
                return fallback
            current = current.get(part)
        return fallback if current is None else str(current)

    finding_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('risk_level', '')))}</td>"
        f"<td>{escape(str(item.get('stage', '')))}</td>"
        f"<td>{escape(str(item.get('file_path', '')))}</td>"
        f"<td><code>{escape(str(item.get('diff_ref', '')))}</code></td>"
        f"<td>{escape(str(item.get('confidence', '')))}</td>"
        f"<td><code>{escape(str(item.get('verification_command', '')))}</code></td>"
        "</tr>"
        for item in findings
        if isinstance(item, Mapping)
    )
    gap_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('file_path', '')))}</td>"
        f"<td>{escape(str(item.get('expected_test_area', '')))}</td>"
        f"<td>{escape(str(item.get('risk_level', '')))}</td>"
        f"<td><code>{escape(str(item.get('verification_command', '')))}</code></td>"
        "</tr>"
        for item in gaps
        if isinstance(item, Mapping)
    )
    change_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td>{escape(str(item.get('file_path', '')))}</td>"
        f"<td>{escape(str(item.get('insertions', '')))}</td>"
        f"<td>{escape(str(item.get('deletions', '')))}</td>"
        f"<td><code>{escape(str(item.get('diff_ref', '')))}</code></td>"
        "</tr>"
        for item in changes[:50]
        if isinstance(item, Mapping)
    )
    command_rows = "\n".join(
        f"<tr><td>{escape(str(key))}</td><td><code>{escape(str(command))}</code></td></tr>"
        for key, command in sorted(commands.items())
    )
    json_blob = escape(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(value('title'))}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #182019;
      --muted: #5f6d61;
      --line: #dbe3d5;
      --paper: #faf8f1;
      --wash: #eef5e7;
      --accent: #245f3b;
      --accent-2: #a6542b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, 'Times New Roman', serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(166, 84, 43, 0.15), transparent 30rem),
        linear-gradient(135deg, var(--paper), var(--wash));
      line-height: 1.5;
    }}
    main {{ width: min(1080px, calc(100% - 32px)); margin: 0 auto; padding: 56px 0; }}
    header {{ margin-bottom: 40px; }}
    .brand {{ font-size: clamp(40px, 7vw, 82px); line-height: 0.95; letter-spacing: 0; margin: 0 0 18px; }}
    .summary {{ max-width: 780px; font-size: 20px; color: var(--muted); margin: 0; }}
    section {{ border-top: 1px solid var(--line); padding: 28px 0; }}
    h2 {{ font-size: 24px; margin: 0 0 14px; }}
    .status {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 14px; }}
    .status div {{ border-left: 3px solid var(--accent); padding-left: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    pre {{ overflow: auto; max-height: 420px; padding: 16px; background: rgba(255, 255, 255, 0.52); border: 1px solid var(--line); }}
    .risk {{ color: var(--accent-2); font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1 class="brand">Cognitive Loop Code Review</h1>
      <p class="summary">Advisory local review evidence for platform Agents. No raw diff, file contents, model keys, or Agent endpoints are stored.</p>
    </header>
    <section>
      <h2>ReviewRun Status</h2>
      <div class="status">
        <div>Status<br><strong>{escape(value('status'))}</strong></div>
        <div>Schema<br><strong>{escape(value('schema_version'))}</strong></div>
        <div>Generated<br><strong>{escape(value('generated_at'))}</strong></div>
        <div>Highest Risk<br><strong class="risk">{escape(value('review_run.metrics.highest_risk'))}</strong></div>
      </div>
    </section>
    <section>
      <h2>DecisionCard</h2>
      <p><strong>{escape(value('decision_card.title'))}</strong></p>
      <p>{escape(value('decision_card.summary'))}</p>
      <div class="status">
        <div>Hard Gate<br><strong>{escape(str(gate.get('hard_gate_enabled', False)))}</strong></div>
        <div>Merge Blocked<br><strong>{escape(str(gate.get('merge_blocked', False)))}</strong></div>
        <div>Mode<br><strong>{escape(str(gate.get('mode', 'advisory')))}</strong></div>
        <div>Human Review<br><strong>{escape(str(decision.get('requires_human_review', False)))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Findings</h2>
      <table>
        <thead><tr><th>Risk</th><th>Stage</th><th>File</th><th>Diff Ref</th><th>Confidence</th><th>Verify</th></tr></thead>
        <tbody>{finding_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Test Gaps</h2>
      <table>
        <thead><tr><th>File</th><th>Expected Area</th><th>Risk</th><th>Verify</th></tr></thead>
        <tbody>{gap_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Changed Files</h2>
      <table>
        <thead><tr><th>Status</th><th>File</th><th>+</th><th>-</th><th>Diff Ref</th></tr></thead>
        <tbody>{change_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Next Commands</h2>
      <table>
        <thead><tr><th>Action</th><th>Command</th></tr></thead>
        <tbody>{command_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Redacted JSON</h2>
      <pre>{json_blob}</pre>
    </section>
  </main>
</body>
</html>
"""
