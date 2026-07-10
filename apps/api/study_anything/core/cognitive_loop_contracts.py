"""Cognitive Loop public contract validation.

These contracts are intentionally framework-independent. They establish the
local-first vocabulary that later Mastra, watcher, verifier, and HTML artifact
layers can consume without making Mastra or Langfuse the source of truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import posixpath
import re
from typing import Any, Callable, Iterable, Mapping, Optional

try:  # pragma: no cover - exercised indirectly when PyYAML is unavailable.
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


CONFIG_SCHEMA_VERSION = "cognitive-loop-config-v1"
PERMISSIONS_SCHEMA_VERSION = "cognitive-loop-permissions-v1"
EVALS_SCHEMA_VERSION = "cognitive-loop-evals-v1"
RISK_SCHEMA_VERSION = "cognitive-loop-risk-v1"
BOOTSTRAP_SCHEMA_VERSION = "cognitive-loop-contract-bootstrap-v1"
CLI_ARTIFACT_SCHEMA_VERSION = "cognitive-loop-cli-artifact-v1"
RUN_ONCE_ARTIFACT_SCHEMA_VERSION = "cognitive-loop-run-once-artifact-v1"
PROJECT_SNAPSHOT_SCHEMA_VERSION = "cognitive-loop-project-snapshot-v1"
HUMAN_GATE_ARTIFACT_SCHEMA_VERSION = "cognitive-loop-human-gate-v1"
EVIDENCE_BUNDLE_SCHEMA_VERSION = "cognitive-loop-evidence-bundle-v1"
EVENT_INDEX_SCHEMA_VERSION = "cognitive-loop-event-index-v1"
WATCHER_CONFIG_SCHEMA_VERSION = "cognitive-loop-watchers-v1"
WATCHER_INGEST_SCHEMA_VERSION = "cognitive-loop-watcher-ingest-v1"
ARTIFACT_DOCTOR_SCHEMA_VERSION = "cognitive-loop-artifact-doctor-v1"
REPAIR_PLAN_SCHEMA_VERSION = "cognitive-loop-repair-plan-v1"
ARTIFACT_INDEX_SCHEMA_VERSION = "cognitive-loop-artifact-index-v1"

CONTRACT_FILES = {
    "config": ("config.yaml", CONFIG_SCHEMA_VERSION),
    "permissions": ("permissions.yaml", PERMISSIONS_SCHEMA_VERSION),
    "evals": ("evals.yaml", EVALS_SCHEMA_VERSION),
    "risk": ("risk.yaml", RISK_SCHEMA_VERSION),
}

ALLOWED_EVENT_ACTORS = {"human", "ai", "agent", "ci", "github", "runtime", "system"}
ALLOWED_EVENT_TYPES = {
    "file_changed",
    "git_diff_changed",
    "pre_commit",
    "post_commit",
    "pull_request_opened",
    "ci_failed",
    "test_failed",
    "agent_tool_called",
    "runtime_error",
    "dependency_changed",
    "config_changed",
    "schema_changed",
    "human_note",
    "verification_completed",
}
ALLOWED_DECISION_STATUSES = {
    "proposed",
    "needs_human_mastery",
    "approved",
    "rejected",
    "implemented",
    "rolled_back",
}
ALLOWED_LOOP_STATUSES = {
    "created",
    "running",
    "suspended",
    "verifying",
    "succeeded",
    "failed",
    "rolled_back",
    "rejected",
}
ALLOWED_BLOOM_LEVELS = {
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
}
ALLOWED_EVOLUTION_STATUSES = {
    "draft",
    "needs_review",
    "approved",
    "rejected",
    "applied",
}
ALLOWED_RISK_LEVELS = {"low", "medium", "high", "blocked"}
ALLOWED_HUMAN_GATE_STATUSES = {"not_required", "pending", "approved", "rejected"}
ALLOWED_VERIFICATION_STATUSES = {"not_run", "passed", "failed", "skipped"}
ALLOWED_SENSITIVITY = {"public", "internal"}
ALLOWED_WATCHER_KINDS = {
    "file",
    "git_diff",
    "test",
    "ci",
    "agent_tool",
    "runtime_log",
    "config",
}
WATCHER_EVENT_TYPES = {
    "file": "file_changed",
    "git_diff": "git_diff_changed",
    "test": "test_failed",
    "ci": "ci_failed",
    "agent_tool": "agent_tool_called",
    "runtime_log": "runtime_error",
    "config": "config_changed",
}

FORBIDDEN_FIELD_NAMES = {
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "credential",
    "credentials",
    "raw_source_text",
    "source_text",
    "learner_answer",
    "learner_answers",
    "answer_text",
    "grading_feedback",
    "generated_insight",
    "agent_endpoint",
    "agent_metadata",
    "prompt",
    "raw_payload",
    "raw",
    "excerpt",
}

SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"https?://[^/\s:]+:[^@\s]+@"),
)


class CognitiveLoopContractError(ValueError):
    """Raised when a Cognitive Loop contract is unsafe or malformed."""


@dataclass(frozen=True)
class ProjectEvent:
    event_id: str
    project_id: str
    actor: str
    event_type: str
    summary: str
    timestamp: str
    target: Optional[str] = None
    refs: list[str] = field(default_factory=list)
    sensitivity: str = "internal"
    schema_version: str = "project-event-v1"

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DecisionCard:
    decision_id: str
    project_id: str
    title: str
    status: str
    summary: str
    event_ids: list[str]
    evidence_refs: list[str]
    risk: dict[str, Any]
    human_mastery_gate: dict[str, Any]
    verification: dict[str, Any]
    rollback: dict[str, Any]
    schema_version: str = "decision-card-v1"

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoopRun:
    run_id: str
    project_id: str
    objective: str
    status: str
    started_at: str
    project_event_ids: list[str]
    decision_card_ids: list[str] = field(default_factory=list)
    trace_refs: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    completed_at: Optional[str] = None
    schema_version: str = "loop-run-v1"

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MasteryRecord:
    record_id: str
    project_id: str
    subject: str
    level: float
    bloom: str
    evidence_refs: list[str]
    updated_at: str
    schema_version: str = "mastery-record-v1"

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvolutionReport:
    report_id: str
    project_id: str
    status: str
    proposed_changes: list[str]
    decision_card_ids: list[str]
    verification_refs: list[str]
    risk_summary: str
    created_at: str
    schema_version: str = "evolution-report-v1"

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContractFileReport:
    name: str
    path: str
    schema_version: str
    status: str

    def public_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ContractInitReport:
    name: str
    path: str
    status: str

    def public_dict(self) -> dict[str, str]:
        return asdict(self)


def _schema_version(values: Mapping[str, Any]) -> str:
    raw = values.get("schemaVersion", values.get("schema_version"))
    if not isinstance(raw, str) or not raw.strip():
        raise CognitiveLoopContractError("Contract requires non-empty schemaVersion.")
    return raw.strip()


def _require_schema(values: Mapping[str, Any], expected: str) -> None:
    observed = _schema_version(values)
    if observed != expected:
        raise CognitiveLoopContractError(
            f"Unsupported schemaVersion: expected {expected}, got {observed}."
        )


def _require_string(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CognitiveLoopContractError(f"Contract requires non-empty '{key}'.")
    _assert_public_value(key, value)
    return value.strip()


def _optional_string(values: Mapping[str, Any], key: str) -> Optional[str]:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CognitiveLoopContractError(f"Contract field '{key}' must be a string.")
    stripped = value.strip()
    if not stripped:
        return None
    _assert_public_value(key, stripped)
    return stripped


def _require_list(values: Mapping[str, Any], key: str) -> list[str]:
    value = values.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise CognitiveLoopContractError(f"Contract requires non-empty string list '{key}'.")
    for item in value:
        _assert_public_value(key, item)
    return list(value)


def _optional_list(values: Mapping[str, Any], key: str) -> list[str]:
    value = values.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CognitiveLoopContractError(f"Contract field '{key}' must be a string list.")
    for item in value:
        _assert_public_value(key, item)
    return list(value)


def _require_mapping(values: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = values.get(key)
    if not isinstance(value, Mapping):
        raise CognitiveLoopContractError(f"Contract requires object '{key}'.")
    _assert_public_value(key, value)
    return value


def _require_members(values: Iterable[str], allowed: set[str], field_name: str) -> None:
    unsupported = sorted(set(values) - allowed)
    if unsupported:
        raise CognitiveLoopContractError(f"Unsupported {field_name}: {', '.join(unsupported)}")


def _require_number(value: Any, key: str, *, minimum: float, maximum: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CognitiveLoopContractError(f"Contract field '{key}' must be numeric.")
    number = float(value)
    if not minimum <= number <= maximum:
        raise CognitiveLoopContractError(
            f"Contract field '{key}' must be between {minimum} and {maximum}."
        )
    return number


def _assert_public_value(key: str, value: Any) -> None:
    normalized_key = key.lower().replace("-", "_")
    if normalized_key in FORBIDDEN_FIELD_NAMES or normalized_key.endswith("_secret"):
        raise CognitiveLoopContractError(f"Forbidden private field in public contract: {key}.")
    if isinstance(value, str):
        for pattern in SECRET_PATTERNS:
            if pattern.search(value):
                raise CognitiveLoopContractError(f"Secret-like value found in public contract: {key}.")
    elif isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if not isinstance(child_key, str):
                raise CognitiveLoopContractError("Contract object keys must be strings.")
            _assert_public_value(child_key, child_value)
    elif isinstance(value, list):
        for item in value:
            _assert_public_value(key, item)


def _load_yaml(path: Path) -> Mapping[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is None:
        loaded = _load_simple_yaml(text, path)
        _assert_public_value(path.name, loaded)
        return loaded
    try:
        loaded = yaml.safe_load(text)
    except Exception as exc:
        raise CognitiveLoopContractError(f"Cannot read YAML contract {path}: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise CognitiveLoopContractError(f"YAML contract must be an object: {path}")
    _assert_public_value(path.name, loaded)
    return loaded


def _load_simple_yaml(text: str, path: Path) -> Mapping[str, Any]:
    """Parse the small YAML subset used by repo-local contract files.

    This keeps ``python3 scripts/verify_cognitive_loop_contracts.py`` usable on
    macOS system Python before the project virtualenv has installed PyYAML. It
    intentionally supports only dictionaries, lists, booleans, numbers, and
    plain scalars.
    """

    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            raise CognitiveLoopContractError(f"Unsupported YAML indentation in {path}: {raw!r}")
        lines.append((indent, raw.strip()))

    def scalar(value: str) -> Any:
        value = value.strip()
        if value == "true":
            return True
        if value == "false":
            return False
        if value in {"null", "~"}:
            return None
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value.strip("\"'")

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        current_indent, content = lines[index]
        if current_indent < indent:
            return {}, index
        if current_indent > indent:
            raise CognitiveLoopContractError(f"Unexpected YAML indentation in {path}: {content!r}")
        if content.startswith("- "):
            items: list[Any] = []
            while index < len(lines):
                item_indent, item_content = lines[index]
                if item_indent != indent or not item_content.startswith("- "):
                    break
                remainder = item_content[2:].strip()
                index += 1
                if not remainder:
                    child, index = parse_block(index, indent + 2)
                    items.append(child)
                    continue
                if ":" in remainder:
                    key, raw_value = remainder.split(":", 1)
                    item: dict[str, Any] = {}
                    if raw_value.strip():
                        item[key.strip()] = scalar(raw_value.strip())
                    else:
                        child, index = parse_block(index, indent + 2)
                        item[key.strip()] = child
                    while index < len(lines):
                        next_indent, next_content = lines[index]
                        if next_indent <= indent:
                            break
                        if next_indent != indent + 2:
                            raise CognitiveLoopContractError(
                                f"Unsupported nested YAML list item in {path}: {next_content!r}"
                            )
                        if next_content.startswith("- "):
                            break
                        child_key, child_raw = next_content.split(":", 1)
                        index += 1
                        if child_raw.strip():
                            item[child_key.strip()] = scalar(child_raw.strip())
                        else:
                            child, index = parse_block(index, indent + 4)
                            item[child_key.strip()] = child
                    items.append(item)
                else:
                    items.append(scalar(remainder))
            return items, index

        mapping: dict[str, Any] = {}
        while index < len(lines):
            line_indent, content = lines[index]
            if line_indent != indent or content.startswith("- "):
                break
            if ":" not in content:
                raise CognitiveLoopContractError(f"Unsupported YAML line in {path}: {content!r}")
            key, raw_value = content.split(":", 1)
            key = key.strip()
            index += 1
            if raw_value.strip():
                mapping[key] = scalar(raw_value.strip())
            else:
                child, index = parse_block(index, indent + 2)
                mapping[key] = child
        return mapping, index

    parsed, next_index = parse_block(0, lines[0][0] if lines else 0)
    if next_index != len(lines):
        raise CognitiveLoopContractError(f"Could not parse complete YAML contract: {path}")
    if not isinstance(parsed, Mapping):
        raise CognitiveLoopContractError(f"YAML contract must be an object: {path}")
    return parsed


def validate_project_event(values: Mapping[str, Any]) -> ProjectEvent:
    _assert_public_value("project_event", values)
    actor = _require_string(values, "actor")
    event_type = _require_string(values, "event_type")
    sensitivity = _optional_string(values, "sensitivity") or "internal"
    _require_members([actor], ALLOWED_EVENT_ACTORS, "ProjectEvent actor")
    _require_members([event_type], ALLOWED_EVENT_TYPES, "ProjectEvent event_type")
    _require_members([sensitivity], ALLOWED_SENSITIVITY, "ProjectEvent sensitivity")
    return ProjectEvent(
        event_id=_require_string(values, "event_id"),
        project_id=_require_string(values, "project_id"),
        actor=actor,
        event_type=event_type,
        summary=_require_string(values, "summary"),
        timestamp=_require_string(values, "timestamp"),
        target=_optional_string(values, "target"),
        refs=_optional_list(values, "refs"),
        sensitivity=sensitivity,
    )


def validate_decision_card(values: Mapping[str, Any]) -> DecisionCard:
    _assert_public_value("decision_card", values)
    status = _require_string(values, "status")
    _require_members([status], ALLOWED_DECISION_STATUSES, "DecisionCard status")
    event_ids = _require_list(values, "event_ids")
    evidence_refs = _require_list(values, "evidence_refs")
    risk = dict(_require_mapping(values, "risk"))
    risk_level = risk.get("level")
    if not isinstance(risk_level, str):
        raise CognitiveLoopContractError("DecisionCard risk.level must be a string.")
    _require_members([risk_level], ALLOWED_RISK_LEVELS, "DecisionCard risk.level")
    risk_score = _require_number(risk.get("score"), "risk.score", minimum=0, maximum=1)
    risk["score"] = risk_score
    reasons = risk.get("reasons")
    if not isinstance(reasons, list) or not reasons:
        raise CognitiveLoopContractError("DecisionCard risk.reasons must be a non-empty list.")

    human_gate = dict(_require_mapping(values, "human_mastery_gate"))
    required = human_gate.get("required")
    if not isinstance(required, bool):
        raise CognitiveLoopContractError("DecisionCard human_mastery_gate.required must be boolean.")
    gate_status = human_gate.get("status")
    if not isinstance(gate_status, str):
        raise CognitiveLoopContractError("DecisionCard human_mastery_gate.status must be a string.")
    _require_members([gate_status], ALLOWED_HUMAN_GATE_STATUSES, "human gate status")
    if risk_level in {"high", "blocked"} and not required:
        raise CognitiveLoopContractError("High or blocked risk decisions require a human mastery gate.")

    verification = dict(_require_mapping(values, "verification"))
    verification_status = verification.get("status")
    if not isinstance(verification_status, str):
        raise CognitiveLoopContractError("DecisionCard verification.status must be a string.")
    _require_members([verification_status], ALLOWED_VERIFICATION_STATUSES, "verification status")
    commands = verification.get("commands")
    if not isinstance(commands, list):
        raise CognitiveLoopContractError("DecisionCard verification.commands must be a list.")

    rollback = dict(_require_mapping(values, "rollback"))
    _require_string(rollback, "strategy")
    return DecisionCard(
        decision_id=_require_string(values, "decision_id"),
        project_id=_require_string(values, "project_id"),
        title=_require_string(values, "title"),
        status=status,
        summary=_require_string(values, "summary"),
        event_ids=event_ids,
        evidence_refs=evidence_refs,
        risk=risk,
        human_mastery_gate=human_gate,
        verification=verification,
        rollback=rollback,
    )


def validate_loop_run(values: Mapping[str, Any]) -> LoopRun:
    _assert_public_value("loop_run", values)
    status = _require_string(values, "status")
    _require_members([status], ALLOWED_LOOP_STATUSES, "LoopRun status")
    return LoopRun(
        run_id=_require_string(values, "run_id"),
        project_id=_require_string(values, "project_id"),
        objective=_require_string(values, "objective"),
        status=status,
        started_at=_require_string(values, "started_at"),
        completed_at=_optional_string(values, "completed_at"),
        project_event_ids=_require_list(values, "project_event_ids"),
        decision_card_ids=_optional_list(values, "decision_card_ids"),
        trace_refs=_optional_list(values, "trace_refs"),
        artifact_refs=_optional_list(values, "artifact_refs"),
    )


def validate_mastery_record(values: Mapping[str, Any]) -> MasteryRecord:
    _assert_public_value("mastery_record", values)
    bloom = _require_string(values, "bloom")
    _require_members([bloom], ALLOWED_BLOOM_LEVELS, "MasteryRecord bloom")
    return MasteryRecord(
        record_id=_require_string(values, "record_id"),
        project_id=_require_string(values, "project_id"),
        subject=_require_string(values, "subject"),
        level=_require_number(values.get("level"), "level", minimum=0, maximum=1),
        bloom=bloom,
        evidence_refs=_require_list(values, "evidence_refs"),
        updated_at=_require_string(values, "updated_at"),
    )


def validate_evolution_report(values: Mapping[str, Any]) -> EvolutionReport:
    _assert_public_value("evolution_report", values)
    status = _require_string(values, "status")
    _require_members([status], ALLOWED_EVOLUTION_STATUSES, "EvolutionReport status")
    return EvolutionReport(
        report_id=_require_string(values, "report_id"),
        project_id=_require_string(values, "project_id"),
        status=status,
        proposed_changes=_require_list(values, "proposed_changes"),
        decision_card_ids=_require_list(values, "decision_card_ids"),
        verification_refs=_require_list(values, "verification_refs"),
        risk_summary=_require_string(values, "risk_summary"),
        created_at=_require_string(values, "created_at"),
    )


def _validate_config(values: Mapping[str, Any]) -> None:
    _require_schema(values, CONFIG_SCHEMA_VERSION)
    project = _require_mapping(values, "project")
    if _require_string(project, "mode") != "local_first":
        raise CognitiveLoopContractError("config.project.mode must be local_first.")
    storage = _require_mapping(values, "storage")
    _require_string(storage, "eventStore")
    _require_string(storage, "artifactDir")
    privacy = _require_mapping(values, "privacy")
    if privacy.get("realModelKeys") != "external":
        raise CognitiveLoopContractError("config.privacy.realModelKeys must be external.")
    if privacy.get("agentEndpoints") != "external":
        raise CognitiveLoopContractError("config.privacy.agentEndpoints must be external.")
    if privacy.get("rawSourceText") != "forbidden":
        raise CognitiveLoopContractError("config.privacy.rawSourceText must be forbidden.")


def _validate_permissions(values: Mapping[str, Any]) -> None:
    _require_schema(values, PERMISSIONS_SCHEMA_VERSION)
    if _require_string(values, "defaultMode") != "read_only":
        raise CognitiveLoopContractError("permissions.defaultMode must be read_only.")
    human_approval = _require_mapping(values, "humanApproval")
    required_for = human_approval.get("requiredFor")
    if not isinstance(required_for, list) or "high_risk_decision" not in required_for:
        raise CognitiveLoopContractError("permissions.humanApproval.requiredFor must include high_risk_decision.")
    agent = _require_mapping(values, "agent")
    denied = agent.get("deniedActions")
    if not isinstance(denied, list):
        raise CognitiveLoopContractError("permissions.agent.deniedActions must be a list.")
    required_denials = {"store_model_keys", "upload_raw_sources", "execute_unreviewed_plugins"}
    if not required_denials.issubset(set(denied)):
        raise CognitiveLoopContractError(
            "permissions.agent.deniedActions must include model-key, raw-source, and unreviewed-plugin denials."
        )


def _validate_evals(values: Mapping[str, Any]) -> None:
    _require_schema(values, EVALS_SCHEMA_VERSION)
    required = values.get("required")
    if not isinstance(required, list) or not required:
        raise CognitiveLoopContractError("evals.required must be a non-empty list.")
    commands = []
    for item in required:
        if not isinstance(item, Mapping):
            raise CognitiveLoopContractError("Each eval requirement must be an object.")
        if item.get("blocking") is not True:
            raise CognitiveLoopContractError("Each required eval must be blocking.")
        commands.append(_require_string(item, "command"))
    if "python3 scripts/verify_cognitive_loop_contracts.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop contract verifier.")
    if "python3 scripts/verify_cognitive_loop_cli.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop CLI artifact verifier.")
    if "python3 scripts/verify_cognitive_loop_run_once.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop run-once verifier.")
    if "python3 scripts/verify_cognitive_loop_snapshot.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop snapshot verifier.")
    if "python3 scripts/verify_cognitive_loop_human_gate.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop human gate verifier.")
    if "python3 scripts/verify_cognitive_loop_evidence_bundle.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop evidence bundle verifier.")
    if "python3 scripts/verify_cognitive_loop_event_index.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop event index verifier.")
    if "python3 scripts/verify_cognitive_loop_event_store.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop Event Store verifier.")
    if "python3 scripts/verify_cognitive_loop_watcher_ingest.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop watcher ingest verifier.")
    if "python3 scripts/verify_cognitive_loop_mastra_adapter.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop Mastra adapter verifier.")
    if "python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop Mastra dry-run verifier.")
    if "python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop Mastra runtime service verifier.")
    if "python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop durable Mastra verifier.")
    if "python3 scripts/verify_cognitive_loop_langfuse_observability.py --check" not in commands:
        raise CognitiveLoopContractError(
            "evals.required must include the Cognitive Loop Langfuse observability verifier."
        )
    if "python3 scripts/verify_cognitive_loop_artifact_doctor.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop artifact doctor verifier.")
    if "python3 scripts/verify_cognitive_loop_repair_plan.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop repair plan verifier.")
    if "python3 scripts/verify_cognitive_loop_artifact_index.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop artifact index verifier.")
    if "python3 scripts/verify_cognitive_loop_review.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop advisory review verifier.")
    if "python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop Review Agent prompt verifier.")
    if "python3 scripts/verify_cognitive_loop_review_agent_report.py --check" not in commands:
        raise CognitiveLoopContractError("evals.required must include the Cognitive Loop Review Agent report handoff verifier.")


def _validate_risk(values: Mapping[str, Any]) -> None:
    _require_schema(values, RISK_SCHEMA_VERSION)
    levels = values.get("levels")
    if not isinstance(levels, list) or not ALLOWED_RISK_LEVELS.issubset(set(levels)):
        raise CognitiveLoopContractError("risk.levels must include low, medium, high, and blocked.")
    rules = values.get("rules")
    if not isinstance(rules, list) or not rules:
        raise CognitiveLoopContractError("risk.rules must be a non-empty list.")
    has_high_gate = False
    for item in rules:
        if not isinstance(item, Mapping):
            raise CognitiveLoopContractError("Each risk rule must be an object.")
        risk_level = _require_string(item, "riskLevel")
        _require_members([risk_level], ALLOWED_RISK_LEVELS, "risk rule level")
        if risk_level in {"high", "blocked"} and item.get("humanMasteryGate") == "required":
            has_high_gate = True
    if not has_high_gate:
        raise CognitiveLoopContractError("risk.rules must gate at least one high/blocked risk rule.")


FILE_VALIDATORS: dict[str, Callable[[Mapping[str, Any]], None]] = {
    "config": _validate_config,
    "permissions": _validate_permissions,
    "evals": _validate_evals,
    "risk": _validate_risk,
}


def contract_dir(root: Path) -> Path:
    root = root.resolve()
    if root.name == ".cognitive-loop":
        return root
    return root / ".cognitive-loop"


def validate_contract_files(root: Path) -> list[ContractFileReport]:
    directory = contract_dir(root)
    if not directory.is_dir():
        raise CognitiveLoopContractError(f"Cognitive Loop contract directory is missing: {directory}")
    reports: list[ContractFileReport] = []
    for name, (file_name, schema_version) in CONTRACT_FILES.items():
        path = directory / file_name
        if not path.is_file():
            raise CognitiveLoopContractError(f"Cognitive Loop contract file is missing: {path}")
        values = _load_yaml(path)
        FILE_VALIDATORS[name](values)
        reports.append(
            ContractFileReport(
                name=name,
                path=str(path.relative_to(directory.parent)),
                schema_version=schema_version,
                status="pass",
            )
        )
    return reports


def validate_all_public_objects(values: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "project_event": validate_project_event(values["project_event"]).public_dict(),
        "decision_card": validate_decision_card(values["decision_card"]).public_dict(),
        "loop_run": validate_loop_run(values["loop_run"]).public_dict(),
        "mastery_record": validate_mastery_record(values["mastery_record"]).public_dict(),
        "evolution_report": validate_evolution_report(values["evolution_report"]).public_dict(),
    }


def _safe_yaml_scalar(key: str, value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise CognitiveLoopContractError(f"Contract init requires non-empty {key}.")
    if "\n" in stripped or "\r" in stripped:
        raise CognitiveLoopContractError(f"Contract init value cannot contain newlines: {key}.")
    _assert_public_value(key, stripped)
    return json.dumps(stripped, ensure_ascii=False)


def default_contract_texts(
    *,
    project_id: str = "study-anything",
    project_name: str = "Study Anything",
) -> dict[str, str]:
    """Return the default repo-local Cognitive Loop contract files."""

    project_id_yaml = _safe_yaml_scalar("project_id", project_id)
    project_name_yaml = _safe_yaml_scalar("project_name", project_name)
    return {
        "config": f"""schemaVersion: {CONFIG_SCHEMA_VERSION}
project:
  id: {project_id_yaml}
  name: {project_name_yaml}
  mode: local_first
storage:
  eventStore: .cognitive-loop/events
  artifactDir: .cognitive-loop/artifacts
privacy:
  rawSourceText: forbidden
  learnerAnswers: redacted
  realModelKeys: external
  agentEndpoints: external
  observabilityMetadata: redacted
""",
        "permissions": f"""schemaVersion: {PERMISSIONS_SCHEMA_VERSION}
defaultMode: read_only
humanApproval:
  requiredFor:
    - write_files
    - run_network
    - high_risk_decision
    - rollback_change
agent:
  allowedActions:
    - read_repo
    - propose_decision_card
    - run_verifier
    - write_static_report
  deniedActions:
    - store_model_keys
    - upload_raw_sources
    - execute_unreviewed_plugins
    - bypass_human_mastery_gate
""",
        "evals": f"""schemaVersion: {EVALS_SCHEMA_VERSION}
required:
  - id: cognitive-loop.contracts
    command: python3 scripts/verify_cognitive_loop_contracts.py --check
    blocking: true
  - id: cognitive-loop.cli-artifact
    command: python3 scripts/verify_cognitive_loop_cli.py --check
    blocking: true
  - id: cognitive-loop.run-once-evidence
    command: python3 scripts/verify_cognitive_loop_run_once.py --check
    blocking: true
  - id: cognitive-loop.project-snapshot
    command: python3 scripts/verify_cognitive_loop_snapshot.py --check
    blocking: true
  - id: cognitive-loop.human-gate
    command: python3 scripts/verify_cognitive_loop_human_gate.py --check
    blocking: true
  - id: cognitive-loop.evidence-bundle
    command: python3 scripts/verify_cognitive_loop_evidence_bundle.py --check
    blocking: true
  - id: cognitive-loop.event-index
    command: python3 scripts/verify_cognitive_loop_event_index.py --check
    blocking: true
  - id: cognitive-loop.event-store
    command: python3 scripts/verify_cognitive_loop_event_store.py --check
    blocking: true
  - id: cognitive-loop.watcher-ingest
    command: python3 scripts/verify_cognitive_loop_watcher_ingest.py --check
    blocking: true
  - id: cognitive-loop.mastra-adapter
    command: python3 scripts/verify_cognitive_loop_mastra_adapter.py --check
    blocking: true
  - id: cognitive-loop.mastra-runtime-dry-run
    command: python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check
    blocking: true
  - id: cognitive-loop.mastra-runtime-service
    command: python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check
    blocking: true
  - id: cognitive-loop.mastra-runtime-durable
    command: python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check
    blocking: true
  - id: cognitive-loop.langfuse-observability
    command: python3 scripts/verify_cognitive_loop_langfuse_observability.py --check
    blocking: true
  - id: cognitive-loop.artifact-doctor
    command: python3 scripts/verify_cognitive_loop_artifact_doctor.py --check
    blocking: true
  - id: cognitive-loop.repair-plan
    command: python3 scripts/verify_cognitive_loop_repair_plan.py --check
    blocking: true
  - id: cognitive-loop.artifact-index
    command: python3 scripts/verify_cognitive_loop_artifact_index.py --check
    blocking: true
  - id: cognitive-loop.code-review-advisory
    command: python3 scripts/verify_cognitive_loop_review.py --check
    blocking: true
  - id: cognitive-loop.review-agent-prompt
    command: python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check
    blocking: true
  - id: cognitive-loop.review-agent-report
    command: python3 scripts/verify_cognitive_loop_review_agent_report.py --check
    blocking: true
  - id: study-anything.release-check
    command: ./scripts/release_check.sh
    blocking: true
optional:
  - id: published-image.manifest
    command: python3 scripts/verify_published_image_launch.py --tag v0.3.31-alpha --manifest-only
    blocking: false
""",
        "risk": f"""schemaVersion: {RISK_SCHEMA_VERSION}
levels:
  - low
  - medium
  - high
  - blocked
rules:
  - id: docs-only
    riskLevel: low
    when:
      - docs
      - comments
    humanMasteryGate: optional
  - id: runtime-contract
    riskLevel: medium
    when:
      - public_contract
      - verifier
      - release_asset
    humanMasteryGate: recommended
  - id: sensitive-runtime
    riskLevel: high
    when:
      - auth
      - billing
      - secrets
      - plugin_execution
      - destructive_file_write
    humanMasteryGate: required
  - id: external-data-exfiltration
    riskLevel: blocked
    when:
      - raw_source_upload
      - model_key_storage
      - hidden_instruction_transfer
    humanMasteryGate: required
""",
    }


def default_watcher_config_text() -> str:
    """Return the default optional watcher ingest contract."""

    return f"""schemaVersion: {WATCHER_CONFIG_SCHEMA_VERSION}
mode: manual_ingest
daemon:
  enabled: false
  shipped: false
defaults:
  debounceMs: 750
  maxRefs: 12
  contentMode: metadata_only
watchers:
  - id: file-change
    kind: file
    enabled: true
    eventType: file_changed
    include:
      - "**/*.py"
      - "**/*.ts"
      - "**/*.tsx"
      - "**/*.md"
      - ".cognitive-loop/*.yaml"
    exclude:
      - ".env"
      - "**/.env"
      - "**/.git/**"
      - "**/node_modules/**"
      - "**/.venv/**"
  - id: git-diff
    kind: git_diff
    enabled: true
    eventType: git_diff_changed
    include:
      - "**/*"
    exclude:
      - ".env"
      - "**/.env"
      - "**/node_modules/**"
  - id: test-failure
    kind: test
    enabled: true
    eventType: test_failed
    include:
      - "apps/**"
      - "scripts/**"
      - "tests/**"
    exclude:
      - "**/node_modules/**"
  - id: runtime-log
    kind: runtime_log
    enabled: true
    eventType: runtime_error
    include:
      - "runtime-*"
      - "mastra-*"
      - "api-*"
"""


def _safe_watcher_globs(values: Any, *, field_name: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise CognitiveLoopContractError(f"watchers.{field_name} must be a string list.")
    safe: list[str] = []
    for raw in values:
        value = raw.strip().replace("\\", "/")
        if not value:
            continue
        if value.startswith("/") or value.startswith("../") or "/../" in value:
            raise CognitiveLoopContractError(f"watcher glob must stay repo-relative: {raw}.")
        _assert_public_value(f"watcher_{field_name}", value)
        safe.append(value)
    if len(safe) > 50:
        raise CognitiveLoopContractError(f"watchers.{field_name} is limited to 50 globs.")
    return safe


def validate_watcher_config(values: Mapping[str, Any]) -> dict[str, Any]:
    """Validate optional watcher ingest config without requiring a daemon."""

    _require_schema(values, WATCHER_CONFIG_SCHEMA_VERSION)
    if _require_string(values, "mode") != "manual_ingest":
        raise CognitiveLoopContractError("watchers.mode must be manual_ingest for the MVP.")
    daemon = _require_mapping(values, "daemon")
    if daemon.get("enabled") is not False or daemon.get("shipped") is not False:
        raise CognitiveLoopContractError("watcher daemon must be disabled and unshipped in this MVP.")
    defaults = dict(_require_mapping(values, "defaults"))
    if defaults.get("contentMode") != "metadata_only":
        raise CognitiveLoopContractError("watchers.defaults.contentMode must be metadata_only.")
    max_refs = defaults.get("maxRefs")
    if not isinstance(max_refs, int) or isinstance(max_refs, bool) or max_refs < 1 or max_refs > 50:
        raise CognitiveLoopContractError("watchers.defaults.maxRefs must be an integer between 1 and 50.")
    debounce_ms = defaults.get("debounceMs")
    if (
        not isinstance(debounce_ms, int)
        or isinstance(debounce_ms, bool)
        or debounce_ms < 0
        or debounce_ms > 10000
    ):
        raise CognitiveLoopContractError("watchers.defaults.debounceMs must be 0..10000.")

    raw_watchers = values.get("watchers")
    if not isinstance(raw_watchers, list) or not raw_watchers:
        raise CognitiveLoopContractError("watchers must be a non-empty list.")
    normalized_watchers: list[dict[str, Any]] = []
    ids: set[str] = set()
    for item in raw_watchers:
        if not isinstance(item, Mapping):
            raise CognitiveLoopContractError("Each watcher must be an object.")
        watcher_id = _require_string(item, "id")
        if watcher_id in ids:
            raise CognitiveLoopContractError(f"Duplicate watcher id: {watcher_id}.")
        ids.add(watcher_id)
        kind = _require_string(item, "kind")
        _require_members([kind], ALLOWED_WATCHER_KINDS, "watcher kind")
        event_type = _require_string(item, "eventType")
        expected_event_type = WATCHER_EVENT_TYPES[kind]
        if event_type != expected_event_type:
            raise CognitiveLoopContractError(
                f"watcher {watcher_id} eventType must be {expected_event_type} for kind {kind}."
            )
        if item.get("enabled") is not True:
            raise CognitiveLoopContractError(f"watcher {watcher_id} must explicitly set enabled: true.")
        normalized_watchers.append(
            {
                "id": watcher_id,
                "kind": kind,
                "enabled": True,
                "eventType": event_type,
                "include": _safe_watcher_globs(item.get("include"), field_name="include"),
                "exclude": _safe_watcher_globs(item.get("exclude"), field_name="exclude"),
            }
        )
    return {
        "schemaVersion": WATCHER_CONFIG_SCHEMA_VERSION,
        "mode": "manual_ingest",
        "daemon": {"enabled": False, "shipped": False},
        "defaults": {
            "debounceMs": debounce_ms,
            "maxRefs": max_refs,
            "contentMode": "metadata_only",
        },
        "watchers": normalized_watchers,
    }


def validate_watcher_config_file(root: Path) -> dict[str, Any]:
    path = contract_dir(root) / "watchers.yaml"
    if not path.is_file():
        raise CognitiveLoopContractError(f"Cognitive Loop watcher config is missing: {path}")
    return validate_watcher_config(_load_yaml(path))


def write_default_watcher_config(root: Path, *, overwrite: bool = False) -> ContractInitReport:
    directory = contract_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "watchers.yaml"
    status = "exists"
    if overwrite or not path.exists():
        path.write_text(default_watcher_config_text(), encoding="utf-8")
        status = "written"
    validate_watcher_config_file(root)
    return ContractInitReport(
        name="watchers",
        path=str(path.relative_to(directory.parent)),
        status=status,
    )


def write_default_contract_files(
    root: Path,
    *,
    project_id: str = "study-anything",
    project_name: str = "Study Anything",
    overwrite: bool = False,
) -> list[ContractInitReport]:
    """Create `.cognitive-loop` contract files if they are missing."""

    directory = contract_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    texts = default_contract_texts(project_id=project_id, project_name=project_name)
    reports: list[ContractInitReport] = []
    for name, (file_name, _schema_version) in CONTRACT_FILES.items():
        path = directory / file_name
        status = "exists"
        if overwrite or not path.exists():
            path.write_text(texts[name], encoding="utf-8")
            status = "written"
        reports.append(
            ContractInitReport(
                name=name,
                path=str(path.relative_to(directory.parent)),
                status=status,
            )
        )
    validate_contract_files(root)
    return reports


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_metadata(root: Path) -> dict[str, str]:
    config = _load_yaml(contract_dir(root) / "config.yaml")
    _validate_config(config)
    project = _require_mapping(config, "project")
    return {
        "id": _require_string(project, "id"),
        "name": _require_string(project, "name"),
    }


def build_cli_artifact_report(
    root: Path,
    *,
    objective: str = "Validate Cognitive Loop local contracts and create a shareable HTML artifact.",
    title: str = "Cognitive Loop Local Readiness",
    risk_level: str = "medium",
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    """Build the local, redacted report that the CLI can render as JSON or HTML."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("title", title)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-cli-report",
            "project_id": "study-anything",
            "actor": "agent",
            "event_type": "verification_completed",
            "summary": "Cognitive Loop local contracts were verified and rendered as a static artifact.",
            "timestamp": generated_at,
            "target": ".cognitive-loop",
            "refs": ["script:scripts/cognitive_loop_cli.py", "doc:docs/cognitive-loop-contracts.md"],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-cli-artifact",
            "project_id": "study-anything",
            "title": title,
            "status": "approved",
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [
                "contract:.cognitive-loop/config.yaml",
                "contract:.cognitive-loop/permissions.yaml",
                "contract:.cognitive-loop/evals.yaml",
                "contract:.cognitive-loop/risk.yaml",
            ],
            "risk": {
                "level": risk_level,
                "score": 0.42 if risk_level == "medium" else 0.2,
                "reasons": ["local contract verification", "static report generation"],
            },
            "human_mastery_gate": {
                "required": risk_level in {"high", "blocked"},
                "status": "pending" if risk_level in {"high", "blocked"} else "not_required",
                "questions": [
                    "Can the operator explain what is shipped versus planned?",
                    "Can the operator run the verifier before changing runtime behavior?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py verify",
                    "python3 scripts/cognitive_loop_cli.py report --html",
                    "python3 scripts/verify_cognitive_loop_cli.py --check",
                ],
            },
            "rollback": {"strategy": "delete_generated_artifact", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-cli-artifact",
            "project_id": "study-anything",
            "objective": objective,
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [".cognitive-loop/artifacts/cognitive-loop-report.html"],
        }
    ).public_dict()
    mastery = validate_mastery_record(
        {
            "record_id": "mastery-cognitive-loop-cli-artifact",
            "project_id": "study-anything",
            "subject": "Cognitive Loop local contract usage",
            "level": 0.74,
            "bloom": "apply",
            "evidence_refs": [decision["decision_id"], loop["run_id"]],
            "updated_at": generated_at,
        }
    ).public_dict()
    evolution = validate_evolution_report(
        {
            "report_id": "evo-cognitive-loop-cli-artifact",
            "project_id": "study-anything",
            "status": "approved",
            "proposed_changes": [
                "Initialize repo-local Cognitive Loop contracts",
                "Verify contracts without a runtime daemon",
                "Render a local static HTML artifact for platform-agent handoff",
            ],
            "decision_card_ids": [decision["decision_id"]],
            "verification_refs": ["python3 scripts/verify_cognitive_loop_cli.py --check"],
            "risk_summary": "No model key custody, raw source upload, watcher, or Mastra runtime is introduced.",
            "created_at": generated_at,
        }
    ).public_dict()
    report = {
        "schema_version": CLI_ARTIFACT_SCHEMA_VERSION,
        "status": "ready",
        "generated_at": generated_at,
        "title": title,
        "objective": objective,
        "contract_files": contract_reports,
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "mastery_record": mastery,
        "evolution_report": evolution,
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "real_model_keys_included": False,
            "standalone_frontend_required": False,
        },
        "current_limits": [
            "Mastra runtime is planned, not started by this artifact.",
            "Project watcher is planned, not started by this artifact.",
            "The full HTML console is planned; this is a static local report.",
        ],
        "commands": {
            "init": "python3 scripts/cognitive_loop_cli.py init",
            "verify": "python3 scripts/cognitive_loop_cli.py verify",
            "html_report": "python3 scripts/cognitive_loop_cli.py report --html",
        },
    }
    _assert_public_value("cli_artifact_report", report)
    return report


def build_run_once_artifact(
    root: Path,
    *,
    objective: str = "Run a bounded local Cognitive Loop evidence cycle.",
    change_summary: str = "Validate local contracts and produce one governed run artifact.",
    risk_level: str = "medium",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-run-once.html",
) -> dict[str, Any]:
    """Build a governed single-run artifact without a watcher, model call, or daemon."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("change_summary", change_summary)
    _assert_public_value("artifact_ref", artifact_ref)
    _require_members([risk_level], ALLOWED_RISK_LEVELS, "run-once risk level")
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    needs_gate = risk_level in {"high", "blocked"}
    risk_score = {
        "low": 0.18,
        "medium": 0.44,
        "high": 0.82,
        "blocked": 1.0,
    }[risk_level]
    decision_status = "needs_human_mastery" if needs_gate else "approved"
    loop_status = "suspended" if needs_gate else "succeeded"
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-run-once",
            "project_id": project["id"],
            "actor": "agent",
            "event_type": "verification_completed",
            "summary": change_summary,
            "timestamp": generated_at,
            "target": ".cognitive-loop",
            "refs": [
                "script:scripts/cognitive_loop_cli.py",
                "doc:docs/cognitive-loop-contracts.md",
            ],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-run-once",
            "project_id": project["id"],
            "title": "Run one local Cognitive Loop cycle",
            "status": decision_status,
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [
                "contract:.cognitive-loop/config.yaml",
                "contract:.cognitive-loop/permissions.yaml",
                "contract:.cognitive-loop/evals.yaml",
                "contract:.cognitive-loop/risk.yaml",
                f"artifact:{artifact_ref}",
            ],
            "risk": {
                "level": risk_level,
                "score": risk_score,
                "reasons": [
                    "local-only run evidence",
                    "no watcher daemon",
                    "no model key custody",
                ],
            },
            "human_mastery_gate": {
                "required": needs_gate,
                "status": "pending" if needs_gate else "not_required",
                "questions": [
                    "Can the operator explain the objective and risk level?",
                    "Can the operator identify what evidence is redacted?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py verify",
                    "python3 scripts/cognitive_loop_cli.py run-once --html",
                    "python3 scripts/verify_cognitive_loop_run_once.py --check",
                ],
            },
            "rollback": {"strategy": "delete_run_once_artifacts", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-run-once",
            "project_id": project["id"],
            "objective": objective,
            "status": loop_status,
            "started_at": generated_at,
            "completed_at": None if needs_gate else generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    mastery = validate_mastery_record(
        {
            "record_id": "mastery-cognitive-loop-run-once",
            "project_id": project["id"],
            "subject": "Cognitive Loop run evidence",
            "level": 0.68 if needs_gate else 0.78,
            "bloom": "apply",
            "evidence_refs": [decision["decision_id"], loop["run_id"]],
            "updated_at": generated_at,
        }
    ).public_dict()
    evolution = validate_evolution_report(
        {
            "report_id": "evo-cognitive-loop-run-once",
            "project_id": project["id"],
            "status": "needs_review" if needs_gate else "approved",
            "proposed_changes": [
                "Record one bounded local LoopRun",
                "Bind a DecisionCard to contract evidence",
                "Render a static HTML handoff artifact",
            ],
            "decision_card_ids": [decision["decision_id"]],
            "verification_refs": ["python3 scripts/verify_cognitive_loop_run_once.py --check"],
            "risk_summary": "The run stores only redacted governance evidence and no raw source, Agent endpoint, or model key.",
            "created_at": generated_at,
        }
    ).public_dict()
    report = {
        "schema_version": RUN_ONCE_ARTIFACT_SCHEMA_VERSION,
        "status": loop_status,
        "generated_at": generated_at,
        "title": "Cognitive Loop Run-Once Evidence",
        "objective": objective,
        "change_summary": change_summary,
        "project": project,
        "contract_files": contract_reports,
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "mastery_record": mastery,
        "evolution_report": evolution,
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "real_model_keys_included": False,
            "standalone_frontend_required": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This is a single local run artifact, not a watcher daemon.",
            "Mastra runtime remains planned and is not invoked.",
            "The full realtime HTML console remains planned.",
        ],
        "commands": {
            "init": "python3 scripts/cognitive_loop_cli.py init",
            "verify": "python3 scripts/cognitive_loop_cli.py verify",
            "run_once": "python3 scripts/cognitive_loop_cli.py run-once --html",
            "run_once_check": "python3 scripts/verify_cognitive_loop_run_once.py --check",
        },
    }
    _assert_public_value("run_once_artifact", report)
    return report


def _safe_snapshot_paths(paths: Iterable[str]) -> list[str]:
    safe: list[str] = []
    for raw_path in paths:
        if not isinstance(raw_path, str):
            raise CognitiveLoopContractError("Snapshot paths must be strings.")
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
            raise CognitiveLoopContractError(f"Snapshot path must be repo-relative: {raw_path}.")
        _assert_public_value("snapshot_path", normalized)
        safe.append(normalized)
    deduped = sorted(dict.fromkeys(safe))
    if len(deduped) > 100:
        raise CognitiveLoopContractError("Snapshot path count is limited to 100.")
    return deduped


def build_project_snapshot_artifact(
    root: Path,
    *,
    paths: Iterable[str],
    objective: str = "Capture a redacted local project snapshot as Cognitive Loop evidence.",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-snapshot.html",
) -> dict[str, Any]:
    """Build a path-level project snapshot artifact without reading file contents."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("artifact_ref", artifact_ref)
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    safe_paths = _safe_snapshot_paths(paths)
    changed_count = len(safe_paths)
    summary = (
        f"Captured {changed_count} repo-relative changed path"
        f"{'' if changed_count == 1 else 's'} without file contents."
        if changed_count
        else "Captured a project snapshot with no changed paths."
    )
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-project-snapshot",
            "project_id": project["id"],
            "actor": "system",
            "event_type": "git_diff_changed" if changed_count else "human_note",
            "summary": summary,
            "timestamp": generated_at,
            "target": "git:worktree",
            "refs": [f"path:{path}" for path in safe_paths[:20]],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-project-snapshot",
            "project_id": project["id"],
            "title": "Review local project snapshot",
            "status": "proposed",
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [
                f"event:{event['event_id']}",
                f"artifact:{artifact_ref}",
            ],
            "risk": {
                "level": "low",
                "score": 0.2,
                "reasons": [
                    "path-level snapshot only",
                    "no diff body",
                    "no source text",
                ],
            },
            "human_mastery_gate": {
                "required": False,
                "status": "not_required",
                "questions": [
                    "Can the operator identify which areas changed?",
                    "Can the operator decide whether a deeper review is needed?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py snapshot --html",
                    "python3 scripts/verify_cognitive_loop_snapshot.py --check",
                ],
            },
            "rollback": {"strategy": "delete_snapshot_artifacts", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-project-snapshot",
            "project_id": project["id"],
            "objective": objective,
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    report = {
        "schema_version": PROJECT_SNAPSHOT_SCHEMA_VERSION,
        "status": "ready",
        "generated_at": generated_at,
        "title": "Cognitive Loop Project Snapshot",
        "objective": objective,
        "project": project,
        "contract_files": contract_reports,
        "snapshot": {
            "changed_path_count": changed_count,
            "paths": safe_paths,
            "max_paths_recorded": 100,
            "diff_body_included": False,
            "file_contents_included": False,
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "privacy": {
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "real_model_keys_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This is a manual snapshot, not a watcher daemon.",
            "Only repo-relative paths and counts are recorded.",
            "File contents and diff bodies are intentionally excluded.",
        ],
        "commands": {
            "snapshot": "python3 scripts/cognitive_loop_cli.py snapshot --html",
            "snapshot_check": "python3 scripts/verify_cognitive_loop_snapshot.py --check",
        },
    }
    _assert_public_value("project_snapshot_artifact", report)
    return report


def build_human_gate_artifact(
    root: Path,
    *,
    decision_id: str = "dec-cognitive-loop-human-gate",
    resolution: str = "approved",
    rationale: str = "Operator reviewed the decision, evidence, risk, and rollback plan.",
    operator_id: str = "local-operator",
    objective: str = "Record a local Human Mastery Gate resolution for a high-risk Cognitive Loop decision.",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-human-gate.html",
    evidence_refs: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """Build a local human gate resolution artifact without storing private context."""

    generated_at = generated_at or _utc_now()
    _require_members([resolution], {"approved", "rejected"}, "human gate resolution")
    _assert_public_value("decision_id", decision_id)
    _assert_public_value("rationale", rationale)
    _assert_public_value("operator_id", operator_id)
    _assert_public_value("objective", objective)
    _assert_public_value("artifact_ref", artifact_ref)
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    safe_evidence = list(evidence_refs or [])
    if not safe_evidence:
        safe_evidence = [
            "contract:.cognitive-loop/permissions.yaml",
            "contract:.cognitive-loop/risk.yaml",
            "command:python3 scripts/cognitive_loop_cli.py verify",
        ]
    for evidence_ref in safe_evidence:
        _assert_public_value("evidence_ref", evidence_ref)
    event_suffix = hashlib.sha256(
        "\0".join((project["id"], decision_id, resolution, artifact_ref)).encode("utf-8")
    ).hexdigest()[:16]

    event = validate_project_event(
        {
            "event_id": f"evt-cognitive-loop-human-gate-{event_suffix}",
            "project_id": project["id"],
            "actor": "human",
            "event_type": "human_note",
            "summary": f"Human Mastery Gate {resolution} for {decision_id}.",
            "timestamp": generated_at,
            "target": decision_id,
            "refs": [f"decision:{decision_id}", f"artifact:{artifact_ref}", *safe_evidence[:8]],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": decision_id,
            "project_id": project["id"],
            "title": "Resolve Human Mastery Gate",
            "status": resolution,
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [f"event:{event['event_id']}", f"artifact:{artifact_ref}", *safe_evidence],
            "risk": {
                "level": "high",
                "score": 0.82,
                "reasons": [
                    "human mastery gate required",
                    "operator decision changes runtime or project state",
                    "rollback plan must be understood before execution",
                ],
            },
            "human_mastery_gate": {
                "required": True,
                "status": resolution,
                "resolved_at": generated_at,
                "resolved_by": operator_id,
                "rationale": rationale,
                "approval_scope": [
                    "objective",
                    "evidence_refs",
                    "risk_level",
                    "rollback_strategy",
                    "verification_commands",
                ],
                "questions": [
                    "Can the operator explain the decision and its rollback path?",
                    "Can the operator identify what private data is intentionally excluded?",
                ],
            },
            "verification": {
                "status": "passed" if resolution == "approved" else "skipped",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py verify",
                    "python3 scripts/cognitive_loop_cli.py gate --approve --html",
                    "python3 scripts/verify_cognitive_loop_human_gate.py --check",
                ],
            },
            "rollback": {
                "strategy": "keep_resolution_artifact_and_stop_execution"
                if resolution == "rejected"
                else "revert_followup_change_before_reusing_gate",
                "checkpoint_ref": "git",
            },
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-human-gate",
            "project_id": project["id"],
            "objective": objective,
            "status": "succeeded" if resolution == "approved" else "rejected",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    mastery = validate_mastery_record(
        {
            "record_id": "mastery-cognitive-loop-human-gate",
            "project_id": project["id"],
            "subject": "Human Mastery Gate resolution",
            "level": 0.82 if resolution == "approved" else 0.76,
            "bloom": "evaluate",
            "evidence_refs": [decision["decision_id"], loop["run_id"]],
            "updated_at": generated_at,
        }
    ).public_dict()
    evolution = validate_evolution_report(
        {
            "report_id": "evo-cognitive-loop-human-gate",
            "project_id": project["id"],
            "status": resolution,
            "proposed_changes": [
                "Record a local Human Mastery Gate resolution",
                "Bind the resolution to DecisionCard evidence",
                "Keep the artifact local, redacted, and reviewable by platform Agents",
            ],
            "decision_card_ids": [decision["decision_id"]],
            "verification_refs": ["python3 scripts/verify_cognitive_loop_human_gate.py --check"],
            "risk_summary": "The gate records human approval metadata only; it excludes raw source, answers, Agent endpoints, and model keys.",
            "created_at": generated_at,
        }
    ).public_dict()
    report = {
        "schema_version": HUMAN_GATE_ARTIFACT_SCHEMA_VERSION,
        "status": resolution,
        "generated_at": generated_at,
        "title": "Cognitive Loop Human Mastery Gate",
        "objective": objective,
        "project": project,
        "contract_files": contract_reports,
        "gate_resolution": {
            "decision_id": decision_id,
            "status": resolution,
            "resolved_at": generated_at,
            "resolved_by": operator_id,
            "rationale": rationale,
            "evidence_ref_count": len(safe_evidence),
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "mastery_record": mastery,
        "evolution_report": evolution,
        "privacy": {
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This records a local human gate decision; it does not execute the gated change.",
            "It does not read source files, diff bodies, learner answers, or Agent metadata.",
            "Mastra runtime and watcher automation remain planned, not started here.",
        ],
        "commands": {
            "init": "python3 scripts/cognitive_loop_cli.py init",
            "verify": "python3 scripts/cognitive_loop_cli.py verify",
            "approve_gate": "python3 scripts/cognitive_loop_cli.py gate --approve --html",
            "reject_gate": "python3 scripts/cognitive_loop_cli.py gate --reject --html",
            "gate_check": "python3 scripts/verify_cognitive_loop_human_gate.py --check",
        },
    }
    _assert_public_value("human_gate_artifact", report)
    return report


def _safe_bundle_artifact_paths(paths: Iterable[str]) -> list[str]:
    safe: list[str] = []
    for raw_path in paths:
        if not isinstance(raw_path, str):
            raise CognitiveLoopContractError("Evidence bundle artifact paths must be strings.")
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
            raise CognitiveLoopContractError(f"Evidence bundle path must be repo-relative: {raw_path}.")
        _assert_public_value("artifact_path", normalized)
        safe.append(normalized)
    deduped = sorted(dict.fromkeys(safe))
    if len(deduped) > 50:
        raise CognitiveLoopContractError("Evidence bundle artifact count is limited to 50.")
    return deduped


def _bundle_artifact_kind(path: str) -> str:
    if path.endswith(".json"):
        return "event_json"
    if path.endswith(".html"):
        return "html_artifact"
    if path.endswith(".md"):
        return "markdown_artifact"
    return "artifact"


def build_evidence_bundle_artifact(
    root: Path,
    *,
    artifact_paths: Iterable[str],
    objective: str = "Create a redacted local Cognitive Loop evidence bundle manifest.",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-evidence-bundle.html",
) -> dict[str, Any]:
    """Build a manifest for local evidence artifacts without embedding artifact contents."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("artifact_ref", artifact_ref)
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    safe_paths = _safe_bundle_artifact_paths(artifact_paths)
    artifacts: list[dict[str, Any]] = []
    total_bytes = 0
    for relative_path in safe_paths:
        path = root / relative_path
        if not path.is_file():
            raise CognitiveLoopContractError(f"Evidence bundle artifact is missing: {relative_path}.")
        data = path.read_bytes()
        size = len(data)
        total_bytes += size
        artifacts.append(
            {
                "path": relative_path,
                "kind": _bundle_artifact_kind(relative_path),
                "size_bytes": size,
                "sha256": hashlib.sha256(data).hexdigest(),
                "content_included": False,
            }
        )
    artifact_count = len(artifacts)
    summary = (
        f"Bundled metadata for {artifact_count} local Cognitive Loop artifact"
        f"{'' if artifact_count == 1 else 's'} without embedding contents."
    )
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-evidence-bundle",
            "project_id": project["id"],
            "actor": "system",
            "event_type": "verification_completed",
            "summary": summary,
            "timestamp": generated_at,
            "target": ".cognitive-loop",
            "refs": [f"artifact:{item['path']}" for item in artifacts[:12]],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-evidence-bundle",
            "project_id": project["id"],
            "title": "Publish local evidence bundle manifest",
            "status": "approved",
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [f"event:{event['event_id']}", f"artifact:{artifact_ref}"],
            "risk": {
                "level": "low",
                "score": 0.24,
                "reasons": [
                    "metadata-only evidence manifest",
                    "artifact contents excluded",
                    "local operator controlled export",
                ],
            },
            "human_mastery_gate": {
                "required": False,
                "status": "not_required",
                "questions": [
                    "Can the operator inspect artifact hashes without exposing contents?",
                    "Can the operator rerun the verifier before sharing the manifest?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py bundle --html",
                    "python3 scripts/verify_cognitive_loop_evidence_bundle.py --check",
                ],
            },
            "rollback": {"strategy": "delete_evidence_bundle_manifest", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-evidence-bundle",
            "project_id": project["id"],
            "objective": objective,
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    report = {
        "schema_version": EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "status": "ready",
        "generated_at": generated_at,
        "title": "Cognitive Loop Evidence Bundle",
        "objective": objective,
        "project": project,
        "contract_files": contract_reports,
        "evidence_bundle": {
            "artifact_count": artifact_count,
            "total_bytes": total_bytes,
            "max_artifacts_recorded": 50,
            "content_included": False,
            "artifacts": artifacts,
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "privacy": {
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "artifact_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This is a metadata manifest, not an archive containing artifact contents.",
            "Operators can share hashes and paths while keeping local evidence files private.",
            "Realtime HTML console and watcher automation remain planned layers.",
        ],
        "commands": {
            "bundle": "python3 scripts/cognitive_loop_cli.py bundle --html",
            "bundle_check": "python3 scripts/verify_cognitive_loop_evidence_bundle.py --check",
        },
    }
    _assert_public_value("evidence_bundle_artifact", report)
    return report


def _safe_event_index_paths(paths: Iterable[str]) -> list[str]:
    safe: list[str] = []
    for raw_path in paths:
        if not isinstance(raw_path, str):
            raise CognitiveLoopContractError("Event index paths must be strings.")
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
            raise CognitiveLoopContractError(f"Event index path must be repo-relative: {raw_path}.")
        if not normalized.endswith(".json"):
            raise CognitiveLoopContractError(f"Event index only accepts JSON event artifacts: {raw_path}.")
        _assert_public_value("event_path", normalized)
        safe.append(normalized)
    deduped = sorted(dict.fromkeys(safe))
    if len(deduped) > 100:
        raise CognitiveLoopContractError("Event index entry count is limited to 100.")
    return deduped


def _event_index_kind(schema_version: str) -> str:
    if schema_version == RUN_ONCE_ARTIFACT_SCHEMA_VERSION:
        return "loop_run"
    if schema_version == PROJECT_SNAPSHOT_SCHEMA_VERSION:
        return "project_snapshot"
    if schema_version == WATCHER_INGEST_SCHEMA_VERSION:
        return "watcher_ingest"
    if schema_version == HUMAN_GATE_ARTIFACT_SCHEMA_VERSION:
        return "human_gate"
    if schema_version == EVIDENCE_BUNDLE_SCHEMA_VERSION:
        return "evidence_bundle"
    if schema_version == CLI_ARTIFACT_SCHEMA_VERSION:
        return "readiness_report"
    return "event_artifact"


def _optional_artifact_string(values: Mapping[str, Any], key: str) -> Optional[str]:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    _assert_public_value(key, value)
    return value


def build_event_index_artifact(
    root: Path,
    *,
    event_paths: Iterable[str],
    objective: str = "Create a redacted local Cognitive Loop event index.",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-event-index.html",
) -> dict[str, Any]:
    """Build a chronological metadata index of local Cognitive Loop event artifacts."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("artifact_ref", artifact_ref)
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    safe_paths = _safe_event_index_paths(event_paths)
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for relative_path in safe_paths:
        path = root / relative_path
        if not path.is_file():
            raise CognitiveLoopContractError(f"Event index artifact is missing: {relative_path}.")
        data = path.read_bytes()
        total_bytes += len(data)
        try:
            artifact = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CognitiveLoopContractError(f"Event index artifact is not valid JSON: {relative_path}.") from exc
        if not isinstance(artifact, Mapping):
            raise CognitiveLoopContractError(f"Event index artifact must be a JSON object: {relative_path}.")
        _assert_public_value("event_artifact_metadata", artifact)
        schema_version = _optional_artifact_string(artifact, "schema_version") or "unknown"
        entry: dict[str, Any] = {
            "path": relative_path,
            "kind": _event_index_kind(schema_version),
            "schema_version": schema_version,
            "status": _optional_artifact_string(artifact, "status") or "unknown",
            "generated_at": _optional_artifact_string(artifact, "generated_at"),
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_included": False,
        }
        project_event = artifact.get("project_event")
        if isinstance(project_event, Mapping):
            entry["project_event_id"] = _optional_artifact_string(project_event, "event_id")
            entry["project_event_type"] = _optional_artifact_string(project_event, "event_type")
        decision_card = artifact.get("decision_card")
        if isinstance(decision_card, Mapping):
            entry["decision_id"] = _optional_artifact_string(decision_card, "decision_id")
            entry["decision_status"] = _optional_artifact_string(decision_card, "status")
        loop_run = artifact.get("loop_run")
        if isinstance(loop_run, Mapping):
            entry["loop_run_id"] = _optional_artifact_string(loop_run, "run_id")
            entry["loop_status"] = _optional_artifact_string(loop_run, "status")
        entries.append({key: value for key, value in entry.items() if value is not None})
    entries.sort(key=lambda item: (str(item.get("generated_at", "")), str(item.get("path", ""))))
    entry_count = len(entries)
    summary = (
        f"Indexed {entry_count} local Cognitive Loop event artifact"
        f"{'' if entry_count == 1 else 's'} without embedding JSON contents."
    )
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-event-index",
            "project_id": project["id"],
            "actor": "system",
            "event_type": "verification_completed",
            "summary": summary,
            "timestamp": generated_at,
            "target": ".cognitive-loop/events",
            "refs": [f"event-artifact:{item['path']}" for item in entries[:12]],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-event-index",
            "project_id": project["id"],
            "title": "Publish local event index manifest",
            "status": "approved",
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [f"event:{event['event_id']}", f"artifact:{artifact_ref}"],
            "risk": {
                "level": "low",
                "score": 0.22,
                "reasons": [
                    "metadata-only event index",
                    "event contents excluded",
                    "manual local command before watcher automation",
                ],
            },
            "human_mastery_gate": {
                "required": False,
                "status": "not_required",
                "questions": [
                    "Can the operator inspect event order without exposing event payloads?",
                    "Can the operator rebuild the index before sharing evidence?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py index --html",
                    "python3 scripts/verify_cognitive_loop_event_index.py --check",
                ],
            },
            "rollback": {"strategy": "delete_event_index_manifest", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-event-index",
            "project_id": project["id"],
            "objective": objective,
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    report = {
        "schema_version": EVENT_INDEX_SCHEMA_VERSION,
        "status": "ready",
        "generated_at": generated_at,
        "title": "Cognitive Loop Event Index",
        "objective": objective,
        "project": project,
        "contract_files": contract_reports,
        "event_index": {
            "entry_count": entry_count,
            "total_bytes": total_bytes,
            "max_events_recorded": 100,
            "content_included": False,
            "entries": entries,
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "privacy": {
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "event_contents_included": False,
            "artifact_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This is a manually rebuilt local event index, not a watcher daemon.",
            "It records event artifact metadata and hashes, not event payload contents.",
            "Realtime HTML console and Mastra runtime orchestration remain planned layers.",
        ],
        "commands": {
            "index": "python3 scripts/cognitive_loop_cli.py index --html",
            "index_check": "python3 scripts/verify_cognitive_loop_event_index.py --check",
        },
    }
    _assert_public_value("event_index_artifact", report)
    return report


def _doctor_file_kind(relative_path: str) -> str:
    if relative_path.startswith(".cognitive-loop/events/") and relative_path.endswith(".json"):
        return "event_json"
    if relative_path.startswith(".cognitive-loop/artifacts/") and relative_path.endswith(".html"):
        return "html_artifact"
    if relative_path.startswith(".cognitive-loop/artifacts/") and relative_path.endswith(".md"):
        return "markdown_artifact"
    return "artifact"


def _doctor_public_path(relative_path: str) -> str:
    try:
        _assert_public_value("artifact_doctor_path", relative_path)
    except CognitiveLoopContractError:
        return "[redacted-sensitive-path]"
    return relative_path


def _doctor_is_safe_filename(path: Path) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", path.name))


def _doctor_issue(
    issues: list[dict[str, Any]],
    *,
    code: str,
    severity: str,
    message: str,
    path: Optional[str] = None,
    repair_command: str,
) -> None:
    issue = {
        "issue_id": f"issue-{len(issues) + 1:03d}",
        "severity": severity,
        "code": code,
        "message": message,
        "repair_command": repair_command,
    }
    if path is not None:
        issue["path"] = _doctor_public_path(path)
    issues.append(issue)


def _scan_doctor_artifacts(root: Path) -> list[str]:
    paths: list[str] = []
    for directory in (root / ".cognitive-loop" / "events", root / ".cognitive-loop" / "artifacts"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            if path.suffix not in {".json", ".html", ".md"}:
                continue
            relative_path = path.relative_to(root).as_posix()
            paths.append(relative_path)
    return paths[:200]


def build_artifact_doctor_artifact(
    root: Path,
    *,
    objective: str = "Check local Cognitive Loop artifacts for metadata consistency before watcher automation.",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-artifact-doctor.html",
) -> dict[str, Any]:
    """Build a metadata-only doctor report for local Cognitive Loop event and HTML artifacts."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("artifact_ref", artifact_ref)
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    issues: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    payloads: dict[str, Mapping[str, Any]] = {}
    hashes: dict[str, list[str]] = {}

    for relative_path in _scan_doctor_artifacts(root):
        path = root / relative_path
        stat = path.stat()
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        hashes.setdefault(sha256, []).append(relative_path)
        record: dict[str, Any] = {
            "path": _doctor_public_path(relative_path),
            "kind": _doctor_file_kind(relative_path),
            "stem": path.stem,
            "suffix": path.suffix,
            "size_bytes": len(data),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "sha256": sha256,
            "content_included": False,
        }
        if not _doctor_is_safe_filename(path):
            _doctor_issue(
                issues,
                code="unsafe_filename",
                severity="warning",
                message="Artifact filename should use letters, numbers, dot, dash, or underscore only.",
                path=relative_path,
                repair_command="Rename the artifact to a safe local filename and rerun the doctor.",
            )
        if relative_path.endswith(".json"):
            try:
                payload = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                record["json_status"] = "invalid_json"
                _doctor_issue(
                    issues,
                    code="invalid_json",
                    severity="error",
                    message="Event artifact is not valid JSON.",
                    path=relative_path,
                    repair_command="Rebuild the event with scripts/cognitive_loop_cli.py and rerun the doctor.",
                )
            else:
                if isinstance(payload, Mapping):
                    payloads[relative_path] = payload
                    record["json_status"] = "valid_json"
                    schema_version = _optional_artifact_string(payload, "schema_version")
                    status = _optional_artifact_string(payload, "status")
                    generated = _optional_artifact_string(payload, "generated_at")
                    if schema_version:
                        record["schema_version"] = schema_version
                    if status:
                        record["status"] = status
                    if generated:
                        record["generated_at"] = generated
                    try:
                        _assert_public_value("artifact_doctor_json_metadata", payload)
                    except CognitiveLoopContractError:
                        _doctor_issue(
                            issues,
                            code="private_metadata_detected",
                            severity="error",
                            message="JSON artifact contains private-looking metadata and was not expanded in the report.",
                            path=relative_path,
                            repair_command="Rebuild the artifact without raw text, answers, endpoints, Agent metadata, or secrets.",
                        )
                else:
                    record["json_status"] = "invalid_json"
                    _doctor_issue(
                        issues,
                        code="invalid_json_object",
                        severity="error",
                        message="Event artifact JSON must be an object.",
                        path=relative_path,
                        repair_command="Rebuild the event with scripts/cognitive_loop_cli.py and rerun the doctor.",
                    )
        records.append(record)

    event_json_paths = {
        path
        for path in payloads
        if path.startswith(".cognitive-loop/events/")
        and path not in {
            ".cognitive-loop/events/cognitive-loop-event-index.json",
            ".cognitive-loop/events/cognitive-loop-artifact-doctor.json",
        }
    }
    html_paths = {
        record["path"]
        for record in records
        if record.get("kind") == "html_artifact" and isinstance(record.get("path"), str)
    }
    for event_path in sorted(event_json_paths):
        expected_html = f".cognitive-loop/artifacts/{Path(event_path).stem}.html"
        if expected_html not in html_paths:
            _doctor_issue(
                issues,
                code="missing_html_pair",
                severity="warning",
                message="Event JSON does not have a same-stem HTML artifact.",
                path=event_path,
                repair_command="Rerun the producing cognitive_loop_cli.py command with --html.",
            )

    for sha256, paths in sorted(hashes.items()):
        if len(paths) < 2:
            continue
        public_paths = [_doctor_public_path(path) for path in paths]
        _doctor_issue(
            issues,
            code="duplicate_hash",
            severity="warning",
            message=f"{len(paths)} local artifacts share the same SHA-256 hash.",
            repair_command="Review duplicate artifacts and delete or rename superseded local evidence.",
        )
        issues[-1]["paths"] = public_paths

    index_payload = payloads.get(".cognitive-loop/events/cognitive-loop-event-index.json")
    if event_json_paths and not isinstance(index_payload, Mapping):
        _doctor_issue(
            issues,
            code="missing_event_index",
            severity="warning",
            message="Event artifacts exist but the local event index is missing.",
            repair_command="python3 scripts/cognitive_loop_cli.py index --html",
        )
    elif isinstance(index_payload, Mapping):
        index = index_payload.get("event_index")
        index_entries = index.get("entries") if isinstance(index, Mapping) else None
        entry_hashes: dict[str, str] = {}
        if isinstance(index_entries, list):
            for item in index_entries:
                if not isinstance(item, Mapping):
                    continue
                path_value = item.get("path")
                hash_value = item.get("sha256")
                if isinstance(path_value, str) and isinstance(hash_value, str):
                    entry_hashes[path_value] = hash_value
        for event_path in sorted(event_json_paths):
            current_hash = hashlib.sha256((root / event_path).read_bytes()).hexdigest()
            if event_path not in entry_hashes:
                _doctor_issue(
                    issues,
                    code="stale_event_index_missing_event",
                    severity="warning",
                    message="Event index does not list a current event artifact.",
                    path=event_path,
                    repair_command="python3 scripts/cognitive_loop_cli.py index --html",
                )
            elif entry_hashes[event_path] != current_hash:
                _doctor_issue(
                    issues,
                    code="stale_event_index_hash_mismatch",
                    severity="warning",
                    message="Event index hash does not match the current event artifact.",
                    path=event_path,
                    repair_command="python3 scripts/cognitive_loop_cli.py index --html",
                )

    for bundle_path, payload in sorted(payloads.items()):
        if _optional_artifact_string(payload, "schema_version") != EVIDENCE_BUNDLE_SCHEMA_VERSION:
            continue
        bundle = payload.get("evidence_bundle")
        artifacts = bundle.get("artifacts") if isinstance(bundle, Mapping) else None
        if not isinstance(artifacts, list):
            continue
        for item in artifacts:
            if not isinstance(item, Mapping):
                continue
            listed_path = item.get("path")
            listed_hash = item.get("sha256")
            if not isinstance(listed_path, str) or not isinstance(listed_hash, str):
                continue
            target = root / listed_path
            if not target.is_file():
                _doctor_issue(
                    issues,
                    code="stale_evidence_bundle_missing_artifact",
                    severity="warning",
                    message="Evidence bundle lists an artifact that is no longer present.",
                    path=bundle_path,
                    repair_command="python3 scripts/cognitive_loop_cli.py bundle --html",
                )
                continue
            current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if current_hash != listed_hash:
                _doctor_issue(
                    issues,
                    code="stale_evidence_bundle_hash_mismatch",
                    severity="warning",
                    message="Evidence bundle hash does not match a current local artifact.",
                    path=bundle_path,
                    repair_command="python3 scripts/cognitive_loop_cli.py bundle --html",
                )

    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    report_status = "pass" if not issues else "needs_attention"
    summary = (
        "Checked local Cognitive Loop artifacts with no consistency issues."
        if not issues
        else f"Checked local Cognitive Loop artifacts and found {len(issues)} issue"
        f"{'' if len(issues) == 1 else 's'}."
    )
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-artifact-doctor",
            "project_id": project["id"],
            "actor": "system",
            "event_type": "verification_completed",
            "summary": summary,
            "timestamp": generated_at,
            "target": ".cognitive-loop",
            "refs": [f"artifact:{record['path']}" for record in records[:12]],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-artifact-doctor",
            "project_id": project["id"],
            "title": "Run local Cognitive Loop artifact doctor",
            "status": "approved",
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [f"event:{event['event_id']}", f"artifact:{artifact_ref}"],
            "risk": {
                "level": "low" if not issues else "medium",
                "score": 0.2 if not issues else 0.48,
                "reasons": [
                    "metadata-only local artifact scan",
                    "artifact contents excluded",
                    "manual repair commands only",
                ],
            },
            "human_mastery_gate": {
                "required": False,
                "status": "not_required",
                "questions": [
                    "Can the operator identify stale or missing local evidence before sharing?",
                    "Can the operator rebuild the index and bundle without exposing artifact contents?",
                ],
            },
            "verification": {
                "status": "passed" if not error_count else "needs_review",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py doctor --html",
                    "python3 scripts/verify_cognitive_loop_artifact_doctor.py --check",
                ],
            },
            "rollback": {"strategy": "delete_artifact_doctor_manifest", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-artifact-doctor",
            "project_id": project["id"],
            "objective": objective,
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    report = {
        "schema_version": ARTIFACT_DOCTOR_SCHEMA_VERSION,
        "status": report_status,
        "generated_at": generated_at,
        "title": "Cognitive Loop Artifact Doctor",
        "objective": objective,
        "project": project,
        "contract_files": contract_reports,
        "artifact_doctor": {
            "status": report_status,
            "file_count": len(records),
            "issue_count": len(issues),
            "error_count": error_count,
            "warning_count": warning_count,
            "content_included": False,
            "records": records,
            "issues": issues,
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "privacy": {
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "event_contents_included": False,
            "artifact_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
        },
        "current_limits": [
            "This is a manual local consistency check, not a watcher daemon.",
            "It records artifact metadata, hashes, and repair commands, not file or event contents.",
            "Realtime HTML console and Mastra runtime orchestration remain planned layers.",
        ],
        "commands": {
            "doctor": "python3 scripts/cognitive_loop_cli.py doctor --html",
            "doctor_check": "python3 scripts/verify_cognitive_loop_artifact_doctor.py --check",
            "rebuild_index": "python3 scripts/cognitive_loop_cli.py index --html",
            "rebuild_bundle": "python3 scripts/cognitive_loop_cli.py bundle --html",
        },
    }
    _assert_public_value("artifact_doctor_artifact", report)
    return report


def _repair_plan_risk(issue: Mapping[str, Any]) -> tuple[str, str, str]:
    code = str(issue.get("code", "unknown_issue"))
    if code == "private_metadata_detected":
        return ("high", "required", "privacy")
    if code in {"invalid_json", "invalid_json_object"}:
        return ("medium", "recommended", "artifact_rebuild")
    if code == "duplicate_hash":
        return ("medium", "recommended", "evidence_cleanup")
    if code in {
        "missing_html_pair",
        "missing_event_index",
        "stale_event_index_missing_event",
        "stale_event_index_hash_mismatch",
        "stale_evidence_bundle_missing_artifact",
        "stale_evidence_bundle_hash_mismatch",
    }:
        return ("low", "not_required", "metadata_rebuild")
    if code == "unsafe_filename":
        return ("low", "not_required", "filename_hygiene")
    return ("medium", "recommended", "manual_review")


def _repair_plan_action(issue: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    risk_level, human_gate, category = _repair_plan_risk(issue)
    command = str(issue.get("repair_command") or "Review the issue and rerun the artifact doctor.")
    action: dict[str, Any] = {
        "action_id": f"repair-{index:03d}",
        "issue_id": str(issue.get("issue_id", f"issue-{index:03d}")),
        "issue_code": str(issue.get("code", "unknown_issue")),
        "severity": str(issue.get("severity", "warning")),
        "category": category,
        "risk_level": risk_level,
        "human_gate": human_gate,
        "execution_mode": "manual_only",
        "auto_apply": False,
        "recommended_command": command,
        "verification_command": "python3 scripts/cognitive_loop_cli.py doctor --html",
        "rationale": str(issue.get("message", "Review local artifact metadata before sharing evidence.")),
        "content_included": False,
    }
    path = issue.get("path")
    if isinstance(path, str):
        action["path"] = _doctor_public_path(path)
    paths = issue.get("paths")
    if isinstance(paths, list):
        action["paths"] = [_doctor_public_path(str(item)) for item in paths if isinstance(item, str)]
    return action


def build_repair_plan_artifact(
    root: Path,
    *,
    objective: str = "Create a manual-only repair plan from local Cognitive Loop artifact doctor issues.",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-repair-plan.html",
) -> dict[str, Any]:
    """Build a metadata-only repair plan from doctor issues without executing repairs."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("artifact_ref", artifact_ref)
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    doctor_report = build_artifact_doctor_artifact(
        root,
        generated_at=generated_at,
        artifact_ref=".cognitive-loop/artifacts/cognitive-loop-artifact-doctor.html",
    )
    artifact_doctor = doctor_report.get("artifact_doctor")
    if not isinstance(artifact_doctor, Mapping):
        artifact_doctor = {}
    issues = artifact_doctor.get("issues")
    if not isinstance(issues, list):
        issues = []
    actions = [
        _repair_plan_action(issue, index=index)
        for index, issue in enumerate(issues, start=1)
        if isinstance(issue, Mapping)
    ]
    risk_order = {"low": 0, "medium": 1, "high": 2, "blocked": 3}
    highest_risk = "low"
    if actions:
        highest_risk = max((str(action["risk_level"]) for action in actions), key=lambda item: risk_order[item])
    gate_required = any(action.get("human_gate") == "required" for action in actions)
    gate_recommended = any(action.get("human_gate") == "recommended" for action in actions)
    report_status = "pass" if not actions else "needs_attention"
    summary = (
        "No local Cognitive Loop repair actions are currently needed."
        if not actions
        else f"Prepared {len(actions)} manual repair action"
        f"{'' if len(actions) == 1 else 's'} from artifact doctor metadata."
    )
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-repair-plan",
            "project_id": project["id"],
            "actor": "system",
            "event_type": "verification_completed",
            "summary": summary,
            "timestamp": generated_at,
            "target": ".cognitive-loop",
            "refs": [f"artifact:{artifact_ref}", "artifact:.cognitive-loop/artifacts/cognitive-loop-artifact-doctor.html"],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-repair-plan",
            "project_id": project["id"],
            "title": "Review local Cognitive Loop repair plan",
            "status": "approved" if not actions else "proposed",
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [f"event:{event['event_id']}", f"artifact:{artifact_ref}"],
            "risk": {
                "level": highest_risk,
                "score": 0.15 if not actions else (0.72 if highest_risk == "high" else 0.43),
                "reasons": [
                    "metadata-only repair planning",
                    "no automatic file writes",
                    "artifact contents excluded",
                ],
            },
            "human_mastery_gate": {
                "required": gate_required,
                "status": "pending" if gate_required else "not_required",
                "questions": [
                    "Can the operator explain which local evidence artifact will be rebuilt or removed?",
                    "Can the operator rerun doctor and release checks after manual repair?",
                ],
                "recommendation": "recommended" if gate_recommended else "not_required",
            },
            "verification": {
                "status": "passed" if not gate_required else "needs_review",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py repair-plan --html",
                    "python3 scripts/verify_cognitive_loop_repair_plan.py --check",
                    "python3 scripts/cognitive_loop_cli.py doctor --html",
                ],
            },
            "rollback": {"strategy": "delete_repair_plan_manifest", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-repair-plan",
            "project_id": project["id"],
            "objective": objective,
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    report = {
        "schema_version": REPAIR_PLAN_SCHEMA_VERSION,
        "status": report_status,
        "generated_at": generated_at,
        "title": "Cognitive Loop Repair Plan",
        "objective": objective,
        "project": project,
        "contract_files": contract_reports,
        "repair_plan": {
            "status": report_status,
            "action_count": len(actions),
            "manual_only": True,
            "auto_apply": False,
            "content_included": False,
            "source_doctor": {
                "schema_version": doctor_report.get("schema_version"),
                "status": doctor_report.get("status"),
                "issue_count": artifact_doctor.get("issue_count", 0),
                "error_count": artifact_doctor.get("error_count", 0),
                "warning_count": artifact_doctor.get("warning_count", 0),
                "content_included": False,
            },
            "actions": actions,
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "privacy": {
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "event_contents_included": False,
            "artifact_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
            "repair_actions_executed": False,
        },
        "current_limits": [
            "This is a manual repair plan, not an automatic fixer.",
            "It maps doctor issue metadata to suggested commands without reading artifact contents.",
            "Realtime watcher, Mastra orchestration, and full HTML console remain planned layers.",
        ],
        "commands": {
            "repair_plan": "python3 scripts/cognitive_loop_cli.py repair-plan --html",
            "repair_plan_check": "python3 scripts/verify_cognitive_loop_repair_plan.py --check",
            "doctor": "python3 scripts/cognitive_loop_cli.py doctor --html",
            "release_check": "./scripts/release_check.sh",
        },
    }
    _assert_public_value("repair_plan_artifact", report)
    return report


def _safe_artifact_index_paths(paths: Iterable[str]) -> list[str]:
    safe: list[str] = []
    for raw_path in paths:
        if not isinstance(raw_path, str):
            raise CognitiveLoopContractError("Artifact index paths must be strings.")
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
            raise CognitiveLoopContractError(f"Artifact index path must be repo-relative: {raw_path}.")
        if not (
            normalized.startswith(".cognitive-loop/events/")
            or normalized.startswith(".cognitive-loop/artifacts/")
        ):
            raise CognitiveLoopContractError(
                f"Artifact index only accepts local Cognitive Loop artifact paths: {raw_path}."
            )
        if not normalized.endswith((".json", ".html", ".md")):
            raise CognitiveLoopContractError(f"Artifact index only accepts JSON, HTML, or Markdown artifacts: {raw_path}.")
        _assert_public_value("artifact_index_path", normalized)
        safe.append(normalized)
    deduped = sorted(dict.fromkeys(safe))
    if len(deduped) > 120:
        raise CognitiveLoopContractError("Artifact index entry count is limited to 120.")
    return deduped


def _artifact_index_href(relative_path: str, *, artifact_ref: str) -> str:
    base_dir = posixpath.dirname(artifact_ref) or "."
    href = posixpath.relpath(relative_path, base_dir)
    if href.startswith("../.."):
        href = relative_path
    _assert_public_value("artifact_index_href", href)
    return href


def _artifact_index_json_metadata(data: bytes, *, relative_path: str) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"json_status": "invalid_json"}
    if not isinstance(payload, Mapping):
        return {"json_status": "invalid_json_object"}
    metadata: dict[str, Any] = {"json_status": "valid_json"}
    for source_key, target_key in (
        ("schema_version", "schema_version"),
        ("status", "status"),
        ("generated_at", "generated_at"),
        ("title", "title"),
    ):
        value = _optional_artifact_string(payload, source_key)
        if value is not None:
            metadata[target_key] = value
    project_event = payload.get("project_event")
    if isinstance(project_event, Mapping):
        event_id = _optional_artifact_string(project_event, "event_id")
        event_type = _optional_artifact_string(project_event, "event_type")
        if event_id:
            metadata["project_event_id"] = event_id
        if event_type:
            metadata["project_event_type"] = event_type
    decision_card = payload.get("decision_card")
    if isinstance(decision_card, Mapping):
        decision_id = _optional_artifact_string(decision_card, "decision_id")
        decision_status = _optional_artifact_string(decision_card, "status")
        if decision_id:
            metadata["decision_id"] = decision_id
        if decision_status:
            metadata["decision_status"] = decision_status
    loop_run = payload.get("loop_run")
    if isinstance(loop_run, Mapping):
        run_id = _optional_artifact_string(loop_run, "run_id")
        loop_status = _optional_artifact_string(loop_run, "status")
        if run_id:
            metadata["loop_run_id"] = run_id
        if loop_status:
            metadata["loop_status"] = loop_status
    _assert_public_value(f"artifact_index_metadata:{relative_path}", metadata)
    return metadata


def build_artifact_index_artifact(
    root: Path,
    *,
    artifact_paths: Iterable[str],
    objective: str = "Create a static local HTML index for Cognitive Loop artifacts.",
    generated_at: Optional[str] = None,
    artifact_ref: str = ".cognitive-loop/artifacts/cognitive-loop-artifact-index.html",
) -> dict[str, Any]:
    """Build a static local artifact navigation index without embedding artifact contents."""

    generated_at = generated_at or _utc_now()
    _assert_public_value("objective", objective)
    _assert_public_value("artifact_ref", artifact_ref)
    project = _project_metadata(root)
    contract_reports = [report.public_dict() for report in validate_contract_files(root)]
    safe_paths = _safe_artifact_index_paths(artifact_paths)
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for relative_path in safe_paths:
        path = root / relative_path
        if not path.is_file():
            raise CognitiveLoopContractError(f"Artifact index target is missing: {relative_path}.")
        data = path.read_bytes()
        stat = path.stat()
        total_bytes += len(data)
        entry: dict[str, Any] = {
            "path": relative_path,
            "href": _artifact_index_href(relative_path, artifact_ref=artifact_ref),
            "kind": _doctor_file_kind(relative_path),
            "stem": path.stem,
            "suffix": path.suffix,
            "size_bytes": len(data),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_included": False,
        }
        if relative_path.endswith(".json"):
            entry.update(_artifact_index_json_metadata(data, relative_path=relative_path))
        entries.append(entry)
    html_count = sum(1 for item in entries if item.get("suffix") == ".html")
    event_json_count = sum(1 for item in entries if item.get("suffix") == ".json")
    markdown_count = sum(1 for item in entries if item.get("suffix") == ".md")
    summary = (
        f"Indexed {len(entries)} local Cognitive Loop artifact"
        f"{'' if len(entries) == 1 else 's'} for static navigation without embedding contents."
    )
    event = validate_project_event(
        {
            "event_id": "evt-cognitive-loop-artifact-index",
            "project_id": project["id"],
            "actor": "system",
            "event_type": "verification_completed",
            "summary": summary,
            "timestamp": generated_at,
            "target": ".cognitive-loop/artifacts",
            "refs": [f"artifact:{item['path']}" for item in entries[:12]],
            "sensitivity": "internal",
        }
    ).public_dict()
    decision = validate_decision_card(
        {
            "decision_id": "dec-cognitive-loop-artifact-index",
            "project_id": project["id"],
            "title": "Publish local static artifact index",
            "status": "approved",
            "summary": objective,
            "event_ids": [event["event_id"]],
            "evidence_refs": [f"event:{event['event_id']}", f"artifact:{artifact_ref}"],
            "risk": {
                "level": "low",
                "score": 0.18,
                "reasons": [
                    "static local navigation only",
                    "artifact contents excluded",
                    "no daemon or standalone frontend",
                ],
            },
            "human_mastery_gate": {
                "required": False,
                "status": "not_required",
                "questions": [
                    "Can the operator open the local index without starting a server?",
                    "Can the operator confirm the index records hashes rather than artifact bodies?",
                ],
            },
            "verification": {
                "status": "passed",
                "commands": [
                    "python3 scripts/cognitive_loop_cli.py artifact-index --html",
                    "python3 scripts/verify_cognitive_loop_artifact_index.py --check",
                ],
            },
            "rollback": {"strategy": "delete_artifact_index_manifest", "checkpoint_ref": "git"},
        }
    ).public_dict()
    loop = validate_loop_run(
        {
            "run_id": "loop-cognitive-loop-artifact-index",
            "project_id": project["id"],
            "objective": objective,
            "status": "succeeded",
            "started_at": generated_at,
            "completed_at": generated_at,
            "project_event_ids": [event["event_id"]],
            "decision_card_ids": [decision["decision_id"]],
            "artifact_refs": [artifact_ref],
        }
    ).public_dict()
    report = {
        "schema_version": ARTIFACT_INDEX_SCHEMA_VERSION,
        "status": "ready",
        "generated_at": generated_at,
        "title": "Cognitive Loop Artifact Index",
        "objective": objective,
        "project": project,
        "contract_files": contract_reports,
        "artifact_index": {
            "entry_count": len(entries),
            "html_count": html_count,
            "event_json_count": event_json_count,
            "markdown_count": markdown_count,
            "total_bytes": total_bytes,
            "max_artifacts_recorded": 120,
            "content_included": False,
            "standalone_frontend_required": False,
            "entries": entries,
        },
        "project_event": event,
        "decision_card": decision,
        "loop_run": loop,
        "privacy": {
            "raw_source_text_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "event_contents_included": False,
            "artifact_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "real_model_keys_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
            "standalone_frontend_required": False,
        },
        "current_limits": [
            "This is a static local artifact index, not a realtime HTML console.",
            "It links to local files and records metadata without embedding artifact contents.",
            "Watcher automation, Mastra orchestration, and a full HTML Artifact console remain planned layers.",
        ],
        "commands": {
            "artifact_index": "python3 scripts/cognitive_loop_cli.py artifact-index --html",
            "artifact_index_check": "python3 scripts/verify_cognitive_loop_artifact_index.py --check",
            "doctor": "python3 scripts/cognitive_loop_cli.py doctor --html",
            "repair_plan": "python3 scripts/cognitive_loop_cli.py repair-plan --html",
        },
    }
    _assert_public_value("artifact_index_artifact", report)
    return report


def render_cli_artifact_html(report: Mapping[str, Any]) -> str:
    """Render a compact static HTML artifact for local review and platform handoff."""

    _assert_public_value("cli_artifact_html", report)

    def value(path: str, fallback: str = "") -> str:
        current: Any = report
        for part in path.split("."):
            if not isinstance(current, Mapping):
                return fallback
            current = current.get(part)
        return fallback if current is None else str(current)

    def list_items(items: Iterable[Any]) -> str:
        return "\n".join(f"<li>{escape(str(item))}</li>" for item in items)

    contract_files = report.get("contract_files")
    if not isinstance(contract_files, list):
        contract_files = []
    contract_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('name', '')))}</td>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td>{escape(str(item.get('schema_version', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        "</tr>"
        for item in contract_files
        if isinstance(item, Mapping)
    )
    limits = report.get("current_limits")
    if not isinstance(limits, list):
        limits = []
    snapshot = report.get("snapshot")
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    snapshot_paths = snapshot.get("paths")
    if not isinstance(snapshot_paths, list):
        snapshot_paths = []
    snapshot_path_items = list_items(snapshot_paths[:20])
    evidence_bundle = report.get("evidence_bundle")
    if not isinstance(evidence_bundle, Mapping):
        evidence_bundle = {}
    bundle_artifacts = evidence_bundle.get("artifacts")
    if not isinstance(bundle_artifacts, list):
        bundle_artifacts = []
    bundle_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td>{escape(str(item.get('kind', '')))}</td>"
        f"<td>{escape(str(item.get('size_bytes', '')))}</td>"
        f"<td><code>{escape(str(item.get('sha256', ''))[:16])}</code></td>"
        "</tr>"
        for item in bundle_artifacts
        if isinstance(item, Mapping)
    )
    event_index = report.get("event_index")
    if not isinstance(event_index, Mapping):
        event_index = {}
    event_entries = event_index.get("entries")
    if not isinstance(event_entries, list):
        event_entries = []
    event_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('generated_at', '')))}</td>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td>{escape(str(item.get('kind', '')))}</td>"
        f"<td>{escape(str(item.get('status', '')))}</td>"
        f"<td><code>{escape(str(item.get('sha256', ''))[:16])}</code></td>"
        "</tr>"
        for item in event_entries
        if isinstance(item, Mapping)
    )
    artifact_doctor = report.get("artifact_doctor")
    if not isinstance(artifact_doctor, Mapping):
        artifact_doctor = {}
    doctor_records = artifact_doctor.get("records")
    if not isinstance(doctor_records, list):
        doctor_records = []
    doctor_issues = artifact_doctor.get("issues")
    if not isinstance(doctor_issues, list):
        doctor_issues = []
    doctor_record_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td>{escape(str(item.get('kind', '')))}</td>"
        f"<td>{escape(str(item.get('schema_version', '')))}</td>"
        f"<td>{escape(str(item.get('status', item.get('json_status', ''))))}</td>"
        f"<td><code>{escape(str(item.get('sha256', ''))[:16])}</code></td>"
        "</tr>"
        for item in doctor_records
        if isinstance(item, Mapping)
    )
    doctor_issue_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('severity', '')))}</td>"
        f"<td>{escape(str(item.get('code', '')))}</td>"
        f"<td>{escape(str(item.get('path', '')))}</td>"
        f"<td><code>{escape(str(item.get('repair_command', '')))}</code></td>"
        "</tr>"
        for item in doctor_issues
        if isinstance(item, Mapping)
    )
    repair_plan = report.get("repair_plan")
    if not isinstance(repair_plan, Mapping):
        repair_plan = {}
    repair_actions = repair_plan.get("actions")
    if not isinstance(repair_actions, list):
        repair_actions = []
    repair_action_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(item.get('action_id', '')))}</td>"
        f"<td>{escape(str(item.get('issue_code', '')))}</td>"
        f"<td>{escape(str(item.get('risk_level', '')))}</td>"
        f"<td>{escape(str(item.get('human_gate', '')))}</td>"
        f"<td><code>{escape(str(item.get('recommended_command', '')))}</code></td>"
        "</tr>"
        for item in repair_actions
        if isinstance(item, Mapping)
    )
    artifact_index = report.get("artifact_index")
    if not isinstance(artifact_index, Mapping):
        artifact_index = {}
    artifact_index_entries = artifact_index.get("entries")
    if not isinstance(artifact_index_entries, list):
        artifact_index_entries = []
    artifact_index_rows = "\n".join(
        "<tr>"
        f"<td><a href=\"{escape(str(item.get('href', '')))}\">{escape(str(item.get('path', '')))}</a></td>"
        f"<td>{escape(str(item.get('kind', '')))}</td>"
        f"<td>{escape(str(item.get('schema_version', item.get('suffix', ''))))}</td>"
        f"<td>{escape(str(item.get('status', item.get('json_status', ''))))}</td>"
        f"<td>{escape(str(item.get('size_bytes', '')))}</td>"
        f"<td><code>{escape(str(item.get('sha256', ''))[:16])}</code></td>"
        "</tr>"
        for item in artifact_index_entries
        if isinstance(item, Mapping)
    )
    gate_resolution = report.get("gate_resolution")
    if not isinstance(gate_resolution, Mapping):
        gate_resolution = {}
    gate_scope = value("decision_card.human_mastery_gate.approval_scope")
    if isinstance(report.get("decision_card"), Mapping):
        human_gate = report["decision_card"].get("human_mastery_gate")  # type: ignore[index]
        if isinstance(human_gate, Mapping):
            scope_items = human_gate.get("approval_scope")
            gate_scope = list_items(scope_items) if isinstance(scope_items, list) else ""
        else:
            gate_scope = ""
    else:
        gate_scope = ""
    commands = report.get("commands")
    if not isinstance(commands, Mapping):
        commands = {}
    command_rows = "\n".join(
        f"<tr><td>{escape(str(key))}</td><td><code>{escape(str(command))}</code></td></tr>"
        for key, command in sorted(commands.items())
    )
    loop_run = report.get("loop_run")
    if not isinstance(loop_run, Mapping):
        loop_run = {}
    json_blob = escape(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(value('title', 'Cognitive Loop Report'))}</title>
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
    main {{
      width: min(980px, calc(100% - 32px));
      margin: 0 auto;
      padding: 56px 0;
    }}
    header {{ margin-bottom: 40px; }}
    .brand {{
      font-size: clamp(42px, 7vw, 86px);
      line-height: 0.95;
      letter-spacing: 0;
      margin: 0 0 18px;
    }}
    .summary {{
      max-width: 760px;
      font-size: 20px;
      color: var(--muted);
      margin: 0;
    }}
    section {{
      border-top: 1px solid var(--line);
      padding: 28px 0;
    }}
    h2 {{
      font-size: 24px;
      margin: 0 0 14px;
    }}
    .status {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 14px;
    }}
    .status div {{
      border-left: 3px solid var(--accent);
      padding-left: 12px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 15px;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      vertical-align: top;
    }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }}
    a {{
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}
    pre {{
      overflow: auto;
      max-height: 420px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.52);
      border: 1px solid var(--line);
    }}
    .risk {{ color: var(--accent-2); font-weight: 700; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1 class="brand">Cognitive Loop System</h1>
      <p class="summary">{escape(value('objective'))}</p>
    </header>
    <section>
      <h2>Local Artifact Status</h2>
      <div class="status">
        <div>Status<br><strong>{escape(value('status'))}</strong></div>
        <div>Schema<br><strong>{escape(value('schema_version'))}</strong></div>
        <div>Generated<br><strong>{escape(value('generated_at'))}</strong></div>
        <div>Risk<br><strong class="risk">{escape(value('decision_card.risk.level'))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Decision Card</h2>
      <p><strong>{escape(value('decision_card.title'))}</strong></p>
      <p>{escape(value('decision_card.summary'))}</p>
      <p>Human Mastery Gate: <strong>{escape(value('decision_card.human_mastery_gate.status'))}</strong></p>
    </section>
    <section>
      <h2>Loop Run</h2>
      <div class="status">
        <div>Run<br><strong>{escape(str(loop_run.get('run_id', '')))}</strong></div>
        <div>Status<br><strong>{escape(str(loop_run.get('status', '')))}</strong></div>
        <div>Started<br><strong>{escape(str(loop_run.get('started_at', '')))}</strong></div>
        <div>Completed<br><strong>{escape(str(loop_run.get('completed_at', 'pending')))}</strong></div>
      </div>
    </section>
    <section>
      <h2>Project Snapshot</h2>
      <p>Changed paths recorded: <strong>{escape(str(snapshot.get('changed_path_count', 0)))}</strong></p>
      <ul>{snapshot_path_items}</ul>
    </section>
    <section>
      <h2>Human Mastery Gate</h2>
      <div class="status">
        <div>Decision<br><strong>{escape(str(gate_resolution.get('decision_id', value('decision_card.decision_id'))))}</strong></div>
        <div>Resolution<br><strong>{escape(str(gate_resolution.get('status', value('decision_card.human_mastery_gate.status'))))}</strong></div>
        <div>Resolved By<br><strong>{escape(str(gate_resolution.get('resolved_by', 'pending')))}</strong></div>
        <div>Evidence Refs<br><strong>{escape(str(gate_resolution.get('evidence_ref_count', 0)))}</strong></div>
      </div>
      <p>{escape(str(gate_resolution.get('rationale', 'No local human gate resolution recorded.')))}</p>
      <ul>{gate_scope}</ul>
    </section>
    <section>
      <h2>Evidence Bundle</h2>
      <p>Artifact metadata records: <strong>{escape(str(evidence_bundle.get('artifact_count', 0)))}</strong></p>
      <table>
        <thead><tr><th>Path</th><th>Kind</th><th>Bytes</th><th>SHA-256</th></tr></thead>
        <tbody>{bundle_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Event Index</h2>
      <p>Event metadata records: <strong>{escape(str(event_index.get('entry_count', 0)))}</strong></p>
      <table>
        <thead><tr><th>Generated</th><th>Path</th><th>Kind</th><th>Status</th><th>SHA-256</th></tr></thead>
        <tbody>{event_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Artifact Doctor</h2>
      <div class="status">
        <div>Files<br><strong>{escape(str(artifact_doctor.get('file_count', 0)))}</strong></div>
        <div>Issues<br><strong>{escape(str(artifact_doctor.get('issue_count', 0)))}</strong></div>
        <div>Errors<br><strong>{escape(str(artifact_doctor.get('error_count', 0)))}</strong></div>
        <div>Warnings<br><strong>{escape(str(artifact_doctor.get('warning_count', 0)))}</strong></div>
      </div>
      <table>
        <thead><tr><th>Severity</th><th>Code</th><th>Path</th><th>Repair</th></tr></thead>
        <tbody>{doctor_issue_rows}</tbody>
      </table>
      <table>
        <thead><tr><th>Path</th><th>Kind</th><th>Schema</th><th>Status</th><th>SHA-256</th></tr></thead>
        <tbody>{doctor_record_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Repair Plan</h2>
      <div class="status">
        <div>Actions<br><strong>{escape(str(repair_plan.get('action_count', 0)))}</strong></div>
        <div>Manual Only<br><strong>{escape(str(repair_plan.get('manual_only', False)))}</strong></div>
        <div>Auto Apply<br><strong>{escape(str(repair_plan.get('auto_apply', False)))}</strong></div>
        <div>Status<br><strong>{escape(str(repair_plan.get('status', '')))}</strong></div>
      </div>
      <table>
        <thead><tr><th>Action</th><th>Issue</th><th>Risk</th><th>Gate</th><th>Command</th></tr></thead>
        <tbody>{repair_action_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Artifact Index</h2>
      <div class="status">
        <div>Entries<br><strong>{escape(str(artifact_index.get('entry_count', 0)))}</strong></div>
        <div>HTML<br><strong>{escape(str(artifact_index.get('html_count', 0)))}</strong></div>
        <div>JSON<br><strong>{escape(str(artifact_index.get('event_json_count', 0)))}</strong></div>
        <div>Standalone Frontend<br><strong>{escape(str(artifact_index.get('standalone_frontend_required', False)))}</strong></div>
      </div>
      <table>
        <thead><tr><th>Artifact</th><th>Kind</th><th>Schema</th><th>Status</th><th>Bytes</th><th>SHA-256</th></tr></thead>
        <tbody>{artifact_index_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Contract Files</h2>
      <table>
        <thead><tr><th>Name</th><th>Path</th><th>Schema</th><th>Status</th></tr></thead>
        <tbody>{contract_rows}</tbody>
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
      <h2>Current Limits</h2>
      <ul>{list_items(limits)}</ul>
    </section>
    <section>
      <h2>Redacted JSON</h2>
      <pre>{json_blob}</pre>
    </section>
  </main>
</body>
</html>
"""
