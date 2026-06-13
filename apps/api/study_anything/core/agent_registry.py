"""User-owned agent configuration and task routing.

Study Anything owns learning orchestration and output validation. Real model
selection, credentials, tools, and reasoning live inside the user's agent.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4

from .security import is_secret_key, redact_mapping, redact_url_secrets, url_contains_inline_secret


class AgentCapability(str, Enum):
    TEACH_OVERVIEW = "teach.overview"
    TEACH_GLOSSARY = "teach.glossary"
    TEACH_EXAMPLES = "teach.examples"
    QUIZ_GENERATE = "quiz.generate"
    ANSWER_GRADE = "answer.grade"
    INSIGHT_SYNTHESIZE = "insight.synthesize"
    NOTE_SCRIBE = "note.scribe"
    SOURCE_VERIFY = "source.verify"
    MEMORY_RETRIEVE = "memory.retrieve"
    EMBEDDING_CREATE = "embedding.create"


class AgentProviderKind(str, Enum):
    FAKE_AGENT = "fake_agent"
    HTTP_AGENT = "http_agent"
    CLI_AGENT = "cli_agent"
    MCP_AGENT = "mcp_agent"


class AgentConfigurationRequired(RuntimeError):
    pass


class AgentProviderUnavailable(RuntimeError):
    pass


class AgentResultInvalid(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentTask:
    task_type: str
    session_id: str
    track: str = "ACADEMIC"
    source: Optional[Mapping[str, Any]] = None
    quiz_items: List[Mapping[str, Any]] = field(default_factory=list)
    answers: List[Mapping[str, Any]] = field(default_factory=list)
    rubric: Optional[str] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["metadata"] = redact_mapping(self.metadata)
        return values


@dataclass(frozen=True)
class AgentResult:
    status: str
    content: Any = ""
    citations: List[Mapping[str, Any]] = field(default_factory=list)
    score: Optional[float] = None
    feedback: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    provider_id: str = ""
    task_type: str = ""
    latency_ms: int = 0

    def public_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["metadata"] = redact_mapping(self.metadata)
        return values

    def public_metadata(self) -> dict[str, Any]:
        metadata = redact_mapping(self.metadata)
        return {
            "provider_id": self.provider_id,
            "task_type": self.task_type,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "confidence": self.confidence,
            "tokens": metadata.get("tokens"),
            "cost": metadata.get("cost"),
            "metadata": metadata,
        }


@dataclass(frozen=True)
class AgentProviderConfig:
    provider_id: str
    kind: AgentProviderKind
    label: str
    endpoint: Optional[str] = None
    command: List[str] = field(default_factory=list)
    capabilities: List[AgentCapability] = field(default_factory=list)
    timeout_seconds: int = 15
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["kind"] = self.kind.value
        values["endpoint"] = redact_url_secrets(self.endpoint)
        values["capabilities"] = [capability.value for capability in self.capabilities]
        values["metadata"] = redact_mapping(self.metadata)
        return values


@dataclass(frozen=True)
class AgentHealth:
    provider_id: str
    status: str
    message: str
    capabilities: List[str]
    diagnostic_code: str = ""
    latency_ms: Optional[int] = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "message": self.message,
            "capabilities": self.capabilities,
            "diagnostic_code": self.diagnostic_code,
            "latency_ms": self.latency_ms,
            "privacy": {
                "secrets_returned": False,
                "endpoint_secrets_returned": False,
                "raw_task_payload_returned": False,
            },
        }


ALL_AGENT_CAPABILITIES = [
    AgentCapability.TEACH_OVERVIEW,
    AgentCapability.TEACH_GLOSSARY,
    AgentCapability.TEACH_EXAMPLES,
    AgentCapability.QUIZ_GENERATE,
    AgentCapability.ANSWER_GRADE,
    AgentCapability.INSIGHT_SYNTHESIZE,
    AgentCapability.NOTE_SCRIBE,
    AgentCapability.SOURCE_VERIFY,
    AgentCapability.MEMORY_RETRIEVE,
    AgentCapability.EMBEDDING_CREATE,
]


def _keywords(text: str) -> List[str]:
    words = [word.strip(".,!?;:()[]{}").lower() for word in text.split() if word.strip()]
    return [word for word in words if len(word) > 5][:4] or ["source", "mastery"]


def _normalise_kind(kind: str) -> AgentProviderKind:
    legacy = {
        "fake": AgentProviderKind.FAKE_AGENT,
        "ollama": AgentProviderKind.HTTP_AGENT,
        "openai_compatible": AgentProviderKind.HTTP_AGENT,
        "custom_http": AgentProviderKind.HTTP_AGENT,
    }
    return legacy.get(kind, AgentProviderKind(kind))


def _normalise_capability(capability: str | AgentCapability) -> AgentCapability:
    if isinstance(capability, AgentCapability):
        return capability
    legacy = {
        "chat": AgentCapability.QUIZ_GENERATE,
        "grading": AgentCapability.ANSWER_GRADE,
        "embed": AgentCapability.EMBEDDING_CREATE,
    }
    return legacy.get(capability, AgentCapability(capability))


def _assert_safe_provider_storage(
    *,
    endpoint: Optional[str],
    metadata: Mapping[str, Any],
) -> None:
    if url_contains_inline_secret(endpoint):
        raise ValueError(
            "Agent endpoint must not contain inline credentials or secret-like query parameters. "
            "Keep real model credentials inside the user's gateway or platform Agent."
        )
    secret_metadata_keys = sorted(key for key in metadata if is_secret_key(str(key)))
    if secret_metadata_keys:
        raise ValueError(
            "Agent provider metadata must not contain secrets. "
            f"Move these fields into the user's gateway environment: {', '.join(secret_metadata_keys)}."
        )


def _health_failure_code(exc: Exception) -> str:
    if isinstance(exc, AgentConfigurationRequired):
        return "configuration_required"
    if isinstance(exc, AgentProviderUnavailable):
        return "provider_unavailable"
    if isinstance(exc, AgentResultInvalid):
        message = str(exc).lower()
        if "malformed json" in message:
            return "malformed_json"
        if "status" in message:
            return "invalid_status"
        if "score" in message:
            return "invalid_score"
        if "confidence" in message:
            return "invalid_confidence"
        if "content" in message:
            return "missing_content"
        return "invalid_schema"
    return "unknown"


class FakeAgentProvider:
    provider_id = "fake-deterministic"

    def invoke(self, task: AgentTask) -> AgentResult:
        source = task.source or {}
        source_text = str(source.get("text") or task.constraints.get("prompt") or "")
        answer_text = " ".join(str(answer.get("text", "")) for answer in task.answers)
        terms = _keywords(" ".join([source_text, answer_text]))
        content = "Focus on " + ", ".join(terms)
        score: Optional[float] = None
        feedback: Optional[str] = None
        metadata: Dict[str, Any] = {"deterministic": True, "terms": terms}

        if task.task_type == AgentCapability.ANSWER_GRADE.value:
            score = 0.82 if answer_text.strip() else 0.0
            content = "Answer is grounded and specific."
            feedback = content
        elif task.task_type == AgentCapability.TEACH_OVERVIEW.value:
            title = str(source.get("title") or "the source")
            content = {
                "summary": f"{title} explains {', '.join(terms)}.",
                "key_points": [f"Understand how {term} connects to the source." for term in terms],
                "learner_level": task.constraints.get("level", "beginner"),
            }
        elif task.task_type == AgentCapability.TEACH_GLOSSARY.value:
            content = [
                {
                    "term": term,
                    "plain_language": f"{term} is a key idea in this source.",
                    "technical_definition": f"{term} should be interpreted only within the cited source context.",
                    "example": f"Use {term} when explaining the source's main relationship.",
                }
                for term in terms
            ]
        elif task.task_type == AgentCapability.TEACH_EXAMPLES.value:
            content = {
                "examples": [
                    f"A learner can test {term} by restating it with a source-backed implication."
                    for term in terms
                ],
                "mode": task.constraints.get("example_mode", "mixed"),
            }
        elif task.task_type == AgentCapability.INSIGHT_SYNTHESIZE.value:
            title = str(source.get("title") or "the source")
            mastery = task.constraints.get("mastery_level", 0.0)
            content = f"{title} is now linked to mastery level {float(mastery):.1f}."
        elif task.task_type == AgentCapability.NOTE_SCRIBE.value:
            title = str(source.get("title") or "the source")
            content = f"# {title}\n\n- Source-bound focus: {', '.join(terms)}\n- Review with active recall."
        elif task.task_type == AgentCapability.SOURCE_VERIFY.value:
            content = "Source reference is present."
            score = 1.0 if source.get("reference") else 0.0
        elif task.task_type == AgentCapability.EMBEDDING_CREATE.value:
            content = ",".join(terms)
            metadata["embedding_terms"] = terms

        citation = {}
        if source.get("reference"):
            citation = {
                "reference": source.get("reference"),
                "excerpt_hash": source.get("excerpt_hash"),
            }

        return AgentResult(
            status="ok",
            content=content,
            citations=[citation] if citation else [],
            score=score,
            feedback=feedback,
            confidence=1.0,
            metadata=metadata,
            provider_id=self.provider_id,
            task_type=task.task_type,
            latency_ms=1,
        )


class HttpAgentProvider:
    def __init__(self, provider: AgentProviderConfig) -> None:
        self.provider = provider

    def invoke(self, task: AgentTask) -> AgentResult:
        if not self.provider.endpoint:
            raise AgentConfigurationRequired(
                f"Agent provider '{self.provider.provider_id}' requires an endpoint."
            )
        started = time.monotonic()
        payload = json.dumps(task.public_dict(), ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.provider.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.provider.timeout_seconds) as response:
                values = json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentResultInvalid(f"Agent returned malformed JSON: {exc}") from exc
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            raise AgentProviderUnavailable(f"HTTP agent unavailable: {exc}") from exc
        if not isinstance(values, dict):
            raise AgentResultInvalid("Agent response must be a JSON object.")
        latency_ms = int((time.monotonic() - started) * 1000)
        return validate_agent_result(
            values,
            provider_id=self.provider.provider_id,
            task_type=task.task_type,
            latency_ms=latency_ms,
        )


def validate_agent_result(
    values: Mapping[str, Any],
    *,
    provider_id: str,
    task_type: str,
    latency_ms: int,
) -> AgentResult:
    status = values.get("status")
    if not isinstance(status, str) or status not in {"ok", "needs_human", "error"}:
        raise AgentResultInvalid("Agent result requires status of ok, needs_human, or error.")

    citations = values.get("citations", [])
    if citations is None:
        citations = []
    if not isinstance(citations, list) or not all(isinstance(item, Mapping) for item in citations):
        raise AgentResultInvalid("Agent result citations must be a list of objects.")

    metadata = values.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise AgentResultInvalid("Agent result metadata must be an object.")

    score = values.get("score")
    if score is not None:
        if not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
            raise AgentResultInvalid("Agent result score must be a number from 0 to 1.")
        score = float(score)

    confidence = values.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise AgentResultInvalid("Agent result confidence must be a number from 0 to 1.")
        confidence = float(confidence)

    content = values.get("content", "")
    if status == "ok":
        if task_type in {
            AgentCapability.TEACH_OVERVIEW.value,
            AgentCapability.TEACH_GLOSSARY.value,
            AgentCapability.TEACH_EXAMPLES.value,
            AgentCapability.QUIZ_GENERATE.value,
            AgentCapability.INSIGHT_SYNTHESIZE.value,
            AgentCapability.NOTE_SCRIBE.value,
        } and not str(content).strip():
            raise AgentResultInvalid(f"Agent result for {task_type} requires content.")
        if task_type == AgentCapability.ANSWER_GRADE.value and score is None:
            raise AgentResultInvalid("Agent grading result requires score.")

    feedback = values.get("feedback")
    if feedback is not None and not isinstance(feedback, str):
        raise AgentResultInvalid("Agent result feedback must be a string when present.")

    return AgentResult(
        status=status,
        content=content,
        citations=list(citations),
        score=score,
        feedback=feedback,
        confidence=confidence,
        metadata=metadata,
        provider_id=provider_id,
        task_type=task_type,
        latency_ms=latency_ms,
    )


class AgentRegistry:
    """Agent provider registry with optional JSON persistence."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path
        self._save_lock = threading.Lock()
        self._suspend_save = True
        self._providers: Dict[str, AgentProviderConfig] = {}
        self._defaults: Dict[str, Dict[AgentCapability, str]] = {}
        self._fake = FakeAgentProvider()
        self.register_provider(
            AgentProviderConfig(
                provider_id=self._fake.provider_id,
                kind=AgentProviderKind.FAKE_AGENT,
                label="Deterministic Demo Agent",
                capabilities=list(ALL_AGENT_CAPABILITIES),
                enabled=True,
                metadata={"purpose": "tests and local demo"},
            )
        )
        sanitized_existing_config = False
        if self.storage_path is not None and self.storage_path.exists():
            sanitized_existing_config = self._load()
        self._suspend_save = False
        if sanitized_existing_config:
            self._save()

    def register_provider(self, provider: AgentProviderConfig) -> AgentProviderConfig:
        _assert_safe_provider_storage(endpoint=provider.endpoint, metadata=provider.metadata)
        if not provider.provider_id:
            provider = replace(provider, provider_id=str(uuid4()))
        self._providers[provider.provider_id] = provider
        self._save()
        return provider

    def configure_provider(
        self,
        *,
        kind: str,
        label: str,
        endpoint: Optional[str] = None,
        base_url: Optional[str] = None,
        command: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        timeout_seconds: int = 15,
        enabled: bool = True,
        metadata: Optional[Mapping[str, Any]] = None,
        **legacy_fields: Any,
    ) -> AgentProviderConfig:
        provider_kind = _normalise_kind(kind)
        provider_metadata = dict(metadata or {})
        storage_endpoint = endpoint or base_url
        _assert_safe_provider_storage(endpoint=storage_endpoint, metadata=provider_metadata)
        if timeout_seconds < 1 or timeout_seconds > 300:
            raise ValueError("Agent provider timeout_seconds must be between 1 and 300.")
        if kind != provider_kind.value:
            provider_metadata["legacy_kind"] = kind
            if legacy_fields.get("default_model"):
                provider_metadata["legacy_default_model"] = legacy_fields["default_model"]
        provider_capabilities = [
            _normalise_capability(capability)
            for capability in (capabilities or [item.value for item in ALL_AGENT_CAPABILITIES])
        ]
        provider = AgentProviderConfig(
            provider_id=str(uuid4()),
            kind=provider_kind,
            label=label,
            endpoint=storage_endpoint,
            command=list(command or []),
            capabilities=provider_capabilities,
            timeout_seconds=timeout_seconds,
            enabled=enabled,
            metadata=provider_metadata,
        )
        return self.register_provider(provider)

    def set_default(
        self,
        user_id: str,
        capability: AgentCapability | str,
        provider_id: str,
    ) -> None:
        capability_value = _normalise_capability(capability)
        provider = self._providers.get(provider_id)
        if provider is None:
            raise KeyError(f"Unknown provider: {provider_id}")
        if capability_value not in provider.capabilities:
            raise ValueError(
                f"Provider '{provider_id}' does not declare capability '{capability_value.value}'."
            )
        self._defaults.setdefault(user_id, {})[capability_value] = provider_id
        self._save()

    def set_demo_defaults(self, user_id: str) -> None:
        for capability in ALL_AGENT_CAPABILITIES:
            self.set_default(user_id, capability, self._fake.provider_id)

    def get_provider(self, provider_id: str) -> AgentProviderConfig:
        provider = self._providers.get(provider_id)
        if provider is None or not provider.enabled:
            raise AgentConfigurationRequired(f"Agent provider '{provider_id}' is missing or disabled.")
        return provider

    def get_default_provider(
        self,
        user_id: str,
        capability: AgentCapability | str,
    ) -> AgentProviderConfig:
        capability_value = _normalise_capability(capability)
        provider_id = self._defaults.get(user_id, {}).get(capability_value)
        if provider_id is None:
            raise AgentConfigurationRequired(
                f"No default agent configured for capability '{capability_value.value}'."
            )
        return self.get_provider(provider_id)

    def status(self, user_id: str) -> dict[str, Any]:
        defaults = {
            capability.value: self._defaults.get(user_id, {}).get(capability)
            for capability in ALL_AGENT_CAPABILITIES
        }
        return {
            "schema_version": "agent-v1",
            "providers": [provider.public_dict() for provider in self._providers.values()],
            "defaults": defaults,
        }

    def test_provider(self, provider_id: str) -> AgentHealth:
        provider = self.get_provider(provider_id)
        capabilities = [capability.value for capability in provider.capabilities]
        if provider.kind == AgentProviderKind.FAKE_AGENT:
            return AgentHealth(
                provider_id=provider.provider_id,
                status="healthy",
                message="Deterministic demo agent is available.",
                capabilities=capabilities,
                diagnostic_code="ok",
                latency_ms=1,
            )
        if provider.kind == AgentProviderKind.HTTP_AGENT:
            if not provider.endpoint:
                return AgentHealth(
                    provider_id=provider.provider_id,
                    status="configuration_required",
                    message="HTTP agent requires an endpoint.",
                    capabilities=capabilities,
                    diagnostic_code="endpoint_missing",
                )
            health_capability = (
                AgentCapability.SOURCE_VERIFY
                if AgentCapability.SOURCE_VERIFY in provider.capabilities
                else provider.capabilities[0]
            )
            task = self._health_task(health_capability)
            started = time.monotonic()
            try:
                HttpAgentProvider(provider).invoke(task)
            except (AgentConfigurationRequired, AgentProviderUnavailable, AgentResultInvalid) as exc:
                return AgentHealth(
                    provider_id=provider.provider_id,
                    status="unhealthy",
                    message=str(exc),
                    capabilities=capabilities,
                    diagnostic_code=_health_failure_code(exc),
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
            return AgentHealth(
                provider_id=provider.provider_id,
                status="healthy",
                message="HTTP agent accepted the Study Anything contract.",
                capabilities=capabilities,
                diagnostic_code="ok",
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        if provider.kind == AgentProviderKind.CLI_AGENT:
            return AgentHealth(
                provider_id=provider.provider_id,
                status="disabled",
                message="CLI agent adapter is disabled unless explicitly enabled with an allowlist.",
                capabilities=capabilities,
                diagnostic_code="cli_disabled",
            )
        return AgentHealth(
            provider_id=provider.provider_id,
            status="planned",
            message="MCP agent adapter is reserved for the plugin ecosystem.",
            capabilities=capabilities,
            diagnostic_code="mcp_planned",
        )

    @staticmethod
    def _health_task(capability: AgentCapability) -> AgentTask:
        source = {
            "reference": "health://check",
            "title": "Health Check",
            "text": "Health check source text.",
        }
        answers = [{"item_id": "health", "text": "A grounded health check answer."}]
        return AgentTask(
            task_type=capability.value,
            session_id="health-check",
            source=source,
            quiz_items=[
                {
                    "item_id": "health",
                    "prompt": "Explain the health check source.",
                    "source_ref": "health://check",
                    "excerpt_hash": "health",
                    "rubric": "Return a score from 0 to 1.",
                }
            ],
            answers=answers if capability == AgentCapability.ANSWER_GRADE else [],
            rubric="Return a score from 0 to 1.",
            constraints={"health_check": True, "mastery_level": 0.5},
        )

    def _save(self) -> None:
        if self._suspend_save or self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._save_lock:
            payload = {
                "providers": [
                    {
                        **asdict(provider),
                        "kind": provider.kind.value,
                        "capabilities": [capability.value for capability in provider.capabilities],
                    }
                    for provider in self._providers.values()
                    if provider.kind != AgentProviderKind.FAKE_AGENT
                ],
                "defaults": {
                    user_id: {
                        capability.value: provider_id for capability, provider_id in defaults.items()
                    }
                    for user_id, defaults in self._defaults.items()
                },
            }
            tmp = self.storage_path.with_name(f"{self.storage_path.name}.{uuid4().hex}.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.storage_path)

    def _load(self) -> bool:
        payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        sanitized = False
        for provider_values in payload.get("providers", []):
            endpoint = provider_values.get("endpoint")
            metadata = dict(provider_values.get("metadata", {}))
            if url_contains_inline_secret(endpoint):
                endpoint = redact_url_secrets(endpoint)
                metadata["migration_warning"] = "unsafe endpoint secrets were redacted and provider was disabled"
                provider_values["enabled"] = False
                sanitized = True
            secret_metadata_keys = [key for key in metadata if is_secret_key(str(key))]
            if secret_metadata_keys:
                for key in secret_metadata_keys:
                    metadata.pop(key, None)
                metadata["migration_warning"] = "unsafe provider metadata secrets were removed"
                provider_values["enabled"] = False
                sanitized = True
            provider = AgentProviderConfig(
                provider_id=provider_values["provider_id"],
                kind=AgentProviderKind(provider_values["kind"]),
                label=provider_values["label"],
                endpoint=endpoint,
                command=list(provider_values.get("command", [])),
                capabilities=[
                    _normalise_capability(capability)
                    for capability in provider_values.get("capabilities", [])
                ],
                timeout_seconds=int(provider_values.get("timeout_seconds", 15)),
                enabled=bool(provider_values.get("enabled", True)),
                metadata=metadata,
            )
            self._providers[provider.provider_id] = provider
        for user_id, defaults in payload.get("defaults", {}).items():
            self._defaults[user_id] = {
                _normalise_capability(capability): provider_id
                for capability, provider_id in defaults.items()
            }
        return sanitized


class AgentRouter:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self._fake = FakeAgentProvider()

    def invoke(
        self,
        *,
        user_id: str,
        capability: AgentCapability | str,
        task: AgentTask,
    ) -> AgentResult:
        capability_value = _normalise_capability(capability)
        provider = self.registry.get_default_provider(user_id, capability_value)
        return self.invoke_provider(provider.provider_id, task=replace(task, task_type=capability_value.value))

    def invoke_provider(self, provider_id: str, *, task: AgentTask) -> AgentResult:
        provider = self.registry.get_provider(provider_id)
        capability = _normalise_capability(task.task_type)
        if capability not in provider.capabilities:
            raise AgentConfigurationRequired(
                f"Agent provider '{provider_id}' does not support '{capability.value}'."
            )
        if provider.kind == AgentProviderKind.FAKE_AGENT:
            result = self._fake.invoke(replace(task, task_type=capability.value))
            return replace(result, provider_id=provider.provider_id)
        if provider.kind == AgentProviderKind.HTTP_AGENT:
            return HttpAgentProvider(provider).invoke(replace(task, task_type=capability.value))
        if provider.kind == AgentProviderKind.CLI_AGENT:
            raise AgentProviderUnavailable(
                "CLI agent adapter is disabled by default; enable it with an explicit allowlist."
            )
        raise AgentProviderUnavailable("MCP agent adapter is reserved for the plugin ecosystem.")
