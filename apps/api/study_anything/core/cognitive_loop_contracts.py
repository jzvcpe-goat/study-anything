"""Cognitive Loop public contract validation.

These contracts are intentionally framework-independent. They establish the
local-first vocabulary that later Mastra, watcher, verifier, and HTML artifact
layers can consume without making Mastra or Langfuse the source of truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
