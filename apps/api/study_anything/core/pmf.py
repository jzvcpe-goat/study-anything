"""Privacy-preserving PMF metrics for local-first deployments."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from uuid import uuid4

from .events import utc_now
from .plugin_registry import PluginStatus
from .security import hash_user_id, sha256_text
from .workflow import LearningState


ALLOWED_INTEREST_SERVICES = {
    "neural_sync",
    "neural_publish",
    "neural_teams",
    "catalyst",
    "plugin_marketplace",
    "hosted_alpha",
}

ALLOWED_INTEREST_SOURCES = {
    "api",
    "web-ui",
    "cli",
    "skill-mode",
    "verify_full_api_flow",
}

ALLOWED_EXPORT_DESTINATIONS = {
    "self_archive",
    "github_discussion",
    "email_to_maintainers",
    "hosted_waitlist",
    "research_report",
}

PRIVACY_EXCLUSIONS = [
    "reading_text",
    "source_title",
    "quiz_prompts",
    "answers",
    "grading_feedback",
    "insights",
    "scribe_log",
    "agent_metadata",
    "raw_contact",
    "individual_contact_hashes",
    "individual_user_hashes",
    "freeform_comments",
]

EXPORT_CONSENT_STATEMENT = (
    "I understand this PMF package is intended for explicit sharing. It contains "
    "aggregate local learning and interest signals only, and excludes source text, "
    "answers, insights, raw contact values, contact hashes, and user hashes."
)


@dataclass(frozen=True)
class PmfInterest:
    intent_id: str
    user_hash: str
    services: list[str]
    contact_hash: Optional[str]
    contact_type: Optional[str]
    source: str
    locale: Optional[str]
    comment_provided: bool
    created_at: str

    def public_dict(self) -> dict[str, object]:
        return {
            "intent_id": self.intent_id,
            "services": self.services,
            "contact_provided": self.contact_hash is not None,
            "contact_type": self.contact_type,
            "source": self.source,
            "locale": self.locale,
            "comment_provided": self.comment_provided,
            "created_at": self.created_at,
            "local_only": True,
            "raw_contact_stored": False,
        }


class LocalPmfInterestStore:
    """Append-only local intent store.

    This is deliberately not a hosted waitlist. It lets self-host users express
    interest in future convenience services while keeping raw contact data out
    of Study Anything.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(
        self,
        *,
        user_id: str,
        services: Iterable[str],
        contact: Optional[str] = None,
        source: str = "api",
        locale: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> PmfInterest:
        provided_services = {service.strip() for service in services if service.strip()}
        unknown_services = sorted(provided_services - ALLOWED_INTEREST_SERVICES)
        if unknown_services:
            raise ValueError(
                "Unsupported PMF interest service: "
                + ", ".join(unknown_services)
                + ". Supported services: "
                + ", ".join(sorted(ALLOWED_INTEREST_SERVICES))
            )
        normalized_services = sorted(provided_services)
        if not normalized_services:
            raise ValueError(
                "At least one supported service is required: "
                + ", ".join(sorted(ALLOWED_INTEREST_SERVICES))
            )
        normalized_contact = contact.strip().lower() if contact and contact.strip() else None
        intent = PmfInterest(
            intent_id=str(uuid4()),
            user_hash=hash_user_id(user_id),
            services=normalized_services,
            contact_hash=sha256_text(normalized_contact) if normalized_contact else None,
            contact_type=_contact_type(normalized_contact),
            source=_safe_source(source),
            locale=(locale.strip()[:12] if locale and locale.strip() else None),
            comment_provided=bool(comment and comment.strip()),
            created_at=utc_now(),
        )
        values = [asdict(item) for item in self.list()]
        values.append(asdict(intent))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        return intent

    def list(self) -> list[PmfInterest]:
        if not self.path.exists():
            return []
        values = json.loads(self.path.read_text(encoding="utf-8"))
        return [PmfInterest(**item) for item in values]

    def summary(self) -> dict[str, object]:
        return summarize_interests(self.list())


def summarize_interests(interests: Iterable[PmfInterest]) -> dict[str, object]:
    items = list(interests)
    service_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for item in items:
        service_counts.update(item.services)
        source_counts.update([item.source])
    return {
        "schema_version": "pmf-interest-v1",
        "generated_at": utc_now(),
        "total": len(items),
        "with_contact": sum(1 for item in items if item.contact_hash),
        "with_comment": sum(1 for item in items if item.comment_provided),
        "services": dict(sorted(service_counts.items())),
        "sources": dict(sorted(source_counts.items())),
        "local_only": True,
        "raw_contact_stored": False,
        "privacy_exclusions": PRIVACY_EXCLUSIONS,
    }


def compute_pmf_metrics(
    sessions: Iterable[LearningState],
    plugins: Iterable[PluginStatus],
    hosted_interest: Optional[Mapping[str, object]] = None,
    *,
    now: Optional[datetime] = None,
) -> dict[str, object]:
    generated_at = now or datetime.now(timezone.utc)
    session_items = list(sessions)
    plugin_items = list(plugins)
    total_sessions = len(session_items)
    completed_sessions = [state for state in session_items if state.stage == "completed"]
    discarded_sessions = [state for state in session_items if state.discarded or state.stage == "discarded"]
    answered_sessions = [state for state in session_items if state.answers]
    user_counts = Counter(state.user_hash for state in session_items)
    active_7d = {
        state.user_hash
        for state in session_items
        if _within_days(state.updated_at, generated_at, 7)
    }
    active_30d = {
        state.user_hash
        for state in session_items
        if _within_days(state.updated_at, generated_at, 30)
    }
    ready_plugins = [plugin for plugin in plugin_items if plugin.status == "ready"]
    invalid_plugins = [plugin for plugin in plugin_items if plugin.status != "ready"]
    mastery_levels = [state.mastery.level for state in session_items if state.mastery.level > 0]
    total_answers = sum(len(state.answers) for state in session_items)
    open_hitl = sum(
        1
        for state in session_items
        for interrupt in state.hitl_interrupts
        if interrupt.status == "open"
    )
    agent_interrupts = sum(
        1
        for state in session_items
        for event in state.events
        if event.type == "hitl.interrupt" and str(event.payload.get("kind", "")).startswith("agent.")
    )
    interest = dict(hosted_interest or summarize_interests([]))
    completion_rate = _ratio(len(completed_sessions), total_sessions)
    repeat_learners = sum(1 for count in user_counts.values() if count >= 2)
    repeat_rate = _ratio(repeat_learners, len(user_counts))
    plugin_install_count = len(ready_plugins)

    return {
        "schema_version": "pmf-v1",
        "generated_at": generated_at.isoformat(),
        "sessions": {
            "total": total_sessions,
            "completed": len(completed_sessions),
            "discarded": len(discarded_sessions),
            "open_hitl": open_hitl,
            "agent_interrupts": agent_interrupts,
            "completion_rate": completion_rate,
        },
        "learners": {
            "unique": len(user_counts),
            "active_7d": len(active_7d),
            "active_30d": len(active_30d),
            "repeat": repeat_learners,
            "repeat_rate": repeat_rate,
        },
        "learning": {
            "answered_sessions": len(answered_sessions),
            "total_answers": total_answers,
            "insight_sessions": sum(1 for state in session_items if state.insights),
            "average_mastery_level": _average(mastery_levels),
            "average_mastery_delta": _average(mastery_levels),
        },
        "plugins": {
            "ready": len(ready_plugins),
            "invalid": len(invalid_plugins),
        },
        "hosted_interest": interest,
        "signals": {
            "weekly_active_learners": len(active_7d),
            "completion_rate": completion_rate,
            "repeat_learning_rate": repeat_rate,
            "plugin_installs": plugin_install_count,
            "hosted_waitlist_count": int(interest.get("total", 0) or 0),
        },
        "privacy": {
            "local_only": True,
            "raw_contact_stored": False,
            "raw_user_identifiers_exposed": False,
            "privacy_exclusions": PRIVACY_EXCLUSIONS,
        },
    }


def build_pmf_export(
    metrics: Mapping[str, object],
    interest_summary: Mapping[str, object],
    *,
    consent_to_share: bool,
    destination: str = "self_archive",
    note: Optional[str] = None,
) -> dict[str, object]:
    """Build an explicit-consent PMF package safe for community PMF validation."""

    if not consent_to_share:
        raise ValueError("PMF export requires explicit consent_to_share=true.")
    safe_destination = _safe_export_destination(destination)
    sanitized_metrics = {
        "sessions": dict(metrics.get("sessions", {}) or {}),
        "learners": dict(metrics.get("learners", {}) or {}),
        "learning": dict(metrics.get("learning", {}) or {}),
        "plugins": dict(metrics.get("plugins", {}) or {}),
        "signals": dict(metrics.get("signals", {}) or {}),
    }
    sanitized_interest = {
        "schema_version": interest_summary.get("schema_version", "pmf-interest-v1"),
        "total": int(interest_summary.get("total", 0) or 0),
        "with_contact": int(interest_summary.get("with_contact", 0) or 0),
        "with_comment": int(interest_summary.get("with_comment", 0) or 0),
        "services": dict(interest_summary.get("services", {}) or {}),
        "sources": dict(interest_summary.get("sources", {}) or {}),
        "raw_contact_stored": False,
    }
    return {
        "schema_version": "pmf-export-v1",
        "generated_at": utc_now(),
        "destination": safe_destination,
        "consent": {
            "granted": True,
            "statement": EXPORT_CONSENT_STATEMENT,
            "note_provided": bool(note and note.strip()),
        },
        "metrics": sanitized_metrics,
        "hosted_interest": sanitized_interest,
        "privacy": {
            "local_only_source": True,
            "shareable_after_consent": True,
            "raw_contact_stored": False,
            "raw_user_identifiers_exposed": False,
            "individual_contact_hashes_exposed": False,
            "individual_user_hashes_exposed": False,
            "freeform_comments_exposed": False,
            "privacy_exclusions": PRIVACY_EXCLUSIONS,
        },
    }


def _contact_type(contact: Optional[str]) -> Optional[str]:
    if not contact:
        return None
    if "@" in contact:
        return "email"
    return "other"


def _safe_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized in ALLOWED_INTEREST_SOURCES:
        return normalized
    return "api"


def _safe_export_destination(destination: str) -> str:
    normalized = destination.strip().lower()
    if normalized in ALLOWED_EXPORT_DESTINATIONS:
        return normalized
    raise ValueError(
        "Unsupported PMF export destination: "
        + destination
        + ". Supported destinations: "
        + ", ".join(sorted(ALLOWED_EXPORT_DESTINATIONS))
    )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _within_days(value: str, now: datetime, days: int) -> bool:
    parsed = _parse_datetime(value)
    if parsed is None:
        return False
    return parsed >= now - timedelta(days=days)


def _parse_datetime(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
