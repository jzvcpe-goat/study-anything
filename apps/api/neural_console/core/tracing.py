"""Optional Langfuse tracing boundary."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


class TraceSink:
    def capture_event(
        self,
        *,
        name: str,
        session_id: str,
        user_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        raise NotImplementedError


class NoopTraceSink(TraceSink):
    def capture_event(
        self,
        *,
        name: str,
        session_id: str,
        user_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        return None


class LangfuseTraceSink(TraceSink):
    def __init__(self) -> None:
        self.enabled = os.getenv("TELEMETRY_ENABLED", "false").lower() == "true"
        self.host = os.getenv("LANGFUSE_HOST")
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        self._client = None
        if self.enabled and self.host and self.public_key and self.secret_key:
            try:
                from langfuse import Langfuse
            except ImportError:
                self.enabled = False
            else:
                self._client = Langfuse(
                    host=self.host,
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                )

    def capture_event(
        self,
        *,
        name: str,
        session_id: str,
        user_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled or self._client is None:
            return None
        self._client.trace(
            name=name,
            session_id=session_id,
            user_id=user_hash,
            metadata=metadata or {},
        )


def build_trace_sink() -> TraceSink:
    sink = LangfuseTraceSink()
    if sink.enabled:
        return sink
    return NoopTraceSink()
