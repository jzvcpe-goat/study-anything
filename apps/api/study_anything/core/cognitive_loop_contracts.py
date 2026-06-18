"""Cognitive Loop public contract validation.

These contracts are intentionally framework-independent. They establish the
local-first vocabulary that later Mastra, watcher, verifier, and HTML artifact
layers can consume without making Mastra or Langfuse the source of truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
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
  - id: study-anything.release-check
    command: ./scripts/release_check.sh
    blocking: true
optional:
  - id: published-image.manifest
    command: python3 scripts/verify_published_image_launch.py --tag v0.3.30-alpha --manifest-only
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
    commands = report.get("commands")
    if not isinstance(commands, Mapping):
        commands = {}
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
