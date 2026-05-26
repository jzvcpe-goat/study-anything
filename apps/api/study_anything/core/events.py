"""Event contracts used by API, UI, and observability adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StudyEvent:
    event_id: str
    session_id: str
    user_hash: str
    type: str
    node: str
    payload: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    trace_id: Optional[str] = None
    created_at: str = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        user_hash: str,
        event_type: str,
        node: str,
        payload: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        trace_id: Optional[str] = None,
    ) -> "StudyEvent":
        return cls(
            event_id=str(uuid4()),
            session_id=session_id,
            user_hash=user_hash,
            type=event_type,
            node=node,
            payload=payload or {},
            severity=severity,
            trace_id=trace_id,
        )

