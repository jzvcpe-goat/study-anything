"""Deprecated model registry compatibility layer.

The MVP runtime now uses AgentRegistry/AgentRouter. These aliases keep older
imports and `/v1/models/*` compatibility tests alive for one alpha release.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from .agent_registry import (
    AgentCapability,
    AgentConfigurationRequired,
    AgentRegistry,
    AgentResult,
    AgentRouter,
)


class Capability(str, Enum):
    CHAT = "chat"
    EMBED = "embed"
    GRADING = "grading"


class ProviderKind(str, Enum):
    FAKE = "fake"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    CUSTOM_HTTP = "custom_http"


ModelConfigurationRequired = AgentConfigurationRequired
ModelProviderUnavailable = RuntimeError


@dataclass(frozen=True)
class ModelResponse:
    text: str
    provider_id: str
    model_id: str
    capability: Capability
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cache_hit: bool = False
    cost_estimate_usd: float = 0.0

    @classmethod
    def from_agent(cls, capability: Capability, result: AgentResult) -> "ModelResponse":
        text = str(result.feedback or result.content or "")
        return cls(
            text=text,
            provider_id=result.provider_id,
            model_id=str(result.metadata.get("model_id") or result.provider_id),
            capability=capability,
            prompt_tokens=0,
            completion_tokens=max(1, len(text.split())),
            latency_ms=result.latency_ms,
            cache_hit=bool(result.metadata.get("deterministic", False)),
            cost_estimate_usd=float(result.metadata.get("cost") or 0.0),
        )

    def public_metadata(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "capability": self.capability.value,
            "latency_ms": self.latency_ms,
            "cache_hit": self.cache_hit,
            "cost_estimate_usd": self.cost_estimate_usd,
            "deprecated": True,
        }


def _capability_to_agent(capability: Capability) -> AgentCapability:
    if capability == Capability.GRADING:
        return AgentCapability.ANSWER_GRADE
    if capability == Capability.EMBED:
        return AgentCapability.EMBEDDING_CREATE
    return AgentCapability.QUIZ_GENERATE


class ModelRegistry(AgentRegistry):
    def __init__(self, storage_path: Optional[Path] = None) -> None:
        super().__init__(storage_path)

    def set_default(
        self,
        user_id: str,
        capability: Capability | AgentCapability | str,
        provider_id: str,
    ) -> None:
        if isinstance(capability, AgentCapability):
            super().set_default(user_id, capability, provider_id)
            return
        cap = Capability(capability) if not isinstance(capability, Capability) else capability
        super().set_default(user_id, _capability_to_agent(cap), provider_id)

    def status(self, user_id: str) -> dict[str, object]:
        status = super().status(user_id)
        defaults = status["defaults"]
        status["legacy_defaults"] = {
            "chat": defaults.get(AgentCapability.QUIZ_GENERATE.value),
            "grading": defaults.get(AgentCapability.ANSWER_GRADE.value),
            "embed": defaults.get(AgentCapability.EMBEDDING_CREATE.value),
        }
        status["deprecated"] = True
        return status


class ModelRouter:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self.agent_router = AgentRouter(registry)

    def complete(self, *, user_id: str, capability: Capability, prompt: str) -> ModelResponse:
        agent_capability = _capability_to_agent(capability)
        from .agent_registry import AgentTask

        task = AgentTask(
            task_type=agent_capability.value,
            session_id="model-compat",
            source={"text": prompt, "reference": "compat://model", "title": "Model Compatibility"},
            answers=[{"item_id": "compat", "text": prompt}] if capability == Capability.GRADING else [],
            constraints={"prompt": prompt},
        )
        return ModelResponse.from_agent(
            capability,
            self.agent_router.invoke(user_id=user_id, capability=agent_capability, task=task),
        )
