"""Optional, privacy-preserving Langfuse tracing boundary."""

from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any, Dict, Mapping, Optional

from .security import REDACTED


OMITTED = "[omitted]"
SECRET_MARKERS = ("key", "secret", "token", "password", "credential")
SAFE_TRACE_KEYS = {
    "agent",
    "agents",
    "answer_count",
    "average",
    "average_score",
    "bloom",
    "confidence",
    "cost",
    "count",
    "discarded",
    "entries",
    "excerpt_hash",
    "has_reference",
    "kind",
    "latency_ms",
    "level",
    "node",
    "provider_id",
    "severity",
    "source_type",
    "stage",
    "status",
    "task_id",
    "task_type",
    "tokens",
    "track",
}


def sanitize_trace_metadata(values: Mapping[str, Any]) -> dict[str, Any]:
    """Keep operational fields while omitting source, answer, and agent prose."""

    sanitized: dict[str, Any] = {}
    for key, value in values.items():
        normalized = key.lower()
        if any(marker in normalized for marker in SECRET_MARKERS):
            sanitized[key] = REDACTED
        elif normalized not in SAFE_TRACE_KEYS:
            sanitized[key] = OMITTED
        elif isinstance(value, Mapping):
            sanitized[key] = sanitize_trace_metadata(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_trace_metadata(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


class TraceSink:
    enabled = False

    def capture_event(
        self,
        *,
        name: str,
        session_id: str,
        user_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        raise NotImplementedError


class NoopTraceSink(TraceSink):
    def capture_event(
        self,
        *,
        name: str,
        session_id: str,
        user_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        return None


class LangfuseTraceSink(TraceSink):
    def __init__(self, *, client: Optional[Any] = None) -> None:
        self.enabled = client is not None or os.getenv("TELEMETRY_ENABLED", "false").lower() == "true"
        self.host = os.getenv("LANGFUSE_HOST")
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        self._client = client
        self._propagate_attributes = None
        if client is not None:
            return
        if not self.enabled or not self.host or not self.public_key or not self.secret_key:
            self.enabled = False
            return
        try:
            from langfuse import Langfuse, propagate_attributes
        except ImportError:
            self.enabled = False
        else:
            self._client = Langfuse(
                host=self.host,
                public_key=self.public_key,
                secret_key=self.secret_key,
            )
            self._propagate_attributes = propagate_attributes

    def capture_event(
        self,
        *,
        name: str,
        session_id: str,
        user_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.enabled or self._client is None:
            return None
        safe_metadata = sanitize_trace_metadata(metadata or {})
        context = (
            self._propagate_attributes(user_id=user_hash, session_id=session_id)
            if self._propagate_attributes is not None
            else nullcontext()
        )
        try:
            with context:
                observation = self._client.start_observation(
                    name=name,
                    as_type="span",
                    metadata=safe_metadata,
                )
                trace_id = getattr(observation, "trace_id", None)
                observation.end()
                return trace_id
        except Exception:
            # Observability must never interrupt a local learning session.
            return None


def build_trace_sink() -> TraceSink:
    sink = LangfuseTraceSink()
    if sink.enabled:
        return sink
    return NoopTraceSink()
