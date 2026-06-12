"""Learning Context Package validation and import helpers."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional
from uuid import uuid4

from .security import sha256_text


LEARNING_CONTEXT_SCHEMA_VERSION = "learning-context-package-v1"
LEARNING_ENRICHMENT_SCHEMA_VERSION = "learning-enrichment-v1"
ALLOWED_CONTEXT_SOURCE_TYPES = {
    "web",
    "document",
    "video_slice",
    "app_context",
    "markdown_note",
    "obsidian_note",
}
CONTEXT_SOURCE_TYPE_ALIASES = {
    "pdf": "document",
    "video": "video_slice",
    "markdown": "markdown_note",
    "obsidian": "obsidian_note",
}
ALLOWED_REDACTION_POLICIES = {
    "reference_only",
    "hash_and_locator",
    "summary_only",
}
ALLOWED_CAPTURE_METHODS = {
    "browser_excerpt",
    "document_excerpt",
    "video_transcript_slice",
    "app_selection",
    "markdown_excerpt",
    "obsidian_excerpt",
    "manual_excerpt",
    "retrieval_result",
    "importer_plugin",
}
MAX_CONTEXT_ITEMS = 50
MAX_CONTEXT_TEXT_CHARS = 20000
SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{16,}"),
]


@dataclass(frozen=True)
class LearningContextItem:
    item_id: str
    source_type: str
    reference: str
    title: str
    text: str
    excerpt_hash: str
    locator: Optional[str] = None
    provenance: dict[str, Any] = field(default_factory=dict)
    redaction_policy: str = "reference_only"
    metadata: dict[str, Any] = field(default_factory=dict)

    def enrichment_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "reference": self.reference,
            "title": self.title,
            "text": self.text,
            "locator": self.locator,
            "provenance": dict(self.provenance),
            "redaction_policy": self.redaction_policy,
            "metadata": {
                **self.metadata,
                "learning_context_item_id": self.item_id,
                "learning_context_excerpt_hash": self.excerpt_hash,
                "provenance": dict(self.provenance),
                "redaction_policy": self.redaction_policy,
            },
        }

    def public_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_text:
            data.pop("text", None)
            data["text_included"] = False
        else:
            data["text_included"] = True
        return data


@dataclass(frozen=True)
class LearningContextPackage:
    package_id: str
    title: str
    reference: str
    items: list[LearningContextItem]
    producer: str = "platform-agent"
    language: Optional[str] = None
    track: Optional[str] = None
    created_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def public_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        return {
            "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
            "package_id": self.package_id,
            "title": self.title,
            "reference": self.reference,
            "producer": self.producer,
            "language": self.language,
            "track": self.track,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "item_count": len(self.items),
            "source_types": sorted({item.source_type for item in self.items}),
            "items": [item.public_dict(include_text=include_text) for item in self.items],
            "privacy": {
                "bounded_excerpts_included": include_text,
                "agent_secrets_allowed": False,
                "notebooklm_official_api_required": False,
            },
        }

    def enrichment_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "reference": self.reference,
            "items": [item.enrichment_dict() for item in self.items],
        }


def validate_learning_context_package(values: Mapping[str, Any]) -> LearningContextPackage:
    """Validate a platform-collected Learning Context Package.

    The package intentionally contains bounded source excerpts because it is the
    import boundary into Study Anything. Validation keeps Agent credentials,
    broad app dumps, and malformed source records out of session state.
    """

    schema_version = _string(values, "schema_version", required=True)
    if schema_version != LEARNING_CONTEXT_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported Learning Context Package schema_version: "
            f"{schema_version!r}. Expected {LEARNING_CONTEXT_SCHEMA_VERSION}."
        )

    title = _string(values, "title", default="Learning Context Package")
    reference = _string(values, "reference", default=f"learning-context://{uuid4()}")
    package_id = _string(values, "package_id", default=_stable_package_id(title, reference))
    producer = _string(values, "producer", default="platform-agent")
    language = _optional_string(values, "language")
    track = _optional_string(values, "track")
    created_at = _optional_string(values, "created_at")
    metadata = _mapping(values, "metadata")
    _reject_secret_like_values("metadata", metadata)

    raw_items = values.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Learning Context Package requires an 'items' list.")
    if not raw_items:
        raise ValueError("Learning Context Package requires at least one item.")
    if len(raw_items) > MAX_CONTEXT_ITEMS:
        raise ValueError(f"Learning Context Package supports at most {MAX_CONTEXT_ITEMS} items.")

    items: list[LearningContextItem] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, Mapping):
            raise ValueError(f"Learning Context item {index} must be an object.")
        items.append(_validate_item(raw_item, index))

    return LearningContextPackage(
        package_id=package_id,
        title=title,
        reference=reference,
        items=items,
        producer=producer,
        language=language,
        track=track,
        created_at=created_at,
        metadata=metadata,
    )


def validate_enrichment_items(raw_items: Iterable[Mapping[str, Any]]) -> list[LearningContextItem]:
    """Validate direct platform enrichment items with the same contract as packages."""

    values = list(raw_items)
    if not values:
        raise ValueError("At least one enrichment item is required.")
    if len(values) > MAX_CONTEXT_ITEMS:
        raise ValueError(f"Learning enrichment supports at most {MAX_CONTEXT_ITEMS} items.")
    items: list[LearningContextItem] = []
    for index, raw_item in enumerate(values, start=1):
        if not isinstance(raw_item, Mapping):
            raise ValueError(f"Learning enrichment item {index} must be an object.")
        items.append(_validate_item(raw_item, index))
    return items


def _validate_item(values: Mapping[str, Any], index: int) -> LearningContextItem:
    source_type = _normalize_source_type(_string(values, "source_type", required=True))
    if source_type not in ALLOWED_CONTEXT_SOURCE_TYPES:
        raise ValueError(
            f"Unsupported Learning Context item source_type {source_type!r}; "
            f"expected one of {', '.join(sorted(ALLOWED_CONTEXT_SOURCE_TYPES))}."
        )
    reference = _string(values, "reference", required=True)
    title = _string(values, "title", default=f"Context Item {index}")
    text = _string(values, "text", required=True)
    if len(text) > MAX_CONTEXT_TEXT_CHARS:
        raise ValueError(
            f"Learning Context item {index} text is too large; "
            f"limit is {MAX_CONTEXT_TEXT_CHARS} characters."
        )
    _reject_secret_like_text(f"items[{index}].text", text)
    locator = _optional_string(values, "locator")
    if locator is None:
        raise ValueError(f"Learning Context item {index} requires non-empty 'locator'.")
    provenance = _provenance(values, index)
    redaction_policy = _redaction_policy(values, index)
    metadata = _mapping(values, "metadata")
    _reject_secret_like_values(f"items[{index}].metadata", metadata)
    item_id = _string(
        values,
        "item_id",
        default=f"{source_type}-{sha256_text(reference + title + text)[:12]}",
    )
    excerpt_hash = sha256_text(text[:2000])
    supplied_hash = _optional_string(values, "excerpt_hash")
    if supplied_hash and supplied_hash != excerpt_hash:
        raise ValueError(f"Learning Context item {index} excerpt_hash does not match text.")
    return LearningContextItem(
        item_id=item_id,
        source_type=source_type,
        reference=reference,
        title=title,
        text=text,
        excerpt_hash=excerpt_hash,
        locator=locator,
        provenance=provenance,
        redaction_policy=redaction_policy,
        metadata=metadata,
    )


def _normalize_source_type(source_type: str) -> str:
    return CONTEXT_SOURCE_TYPE_ALIASES.get(source_type, source_type)


def _provenance(values: Mapping[str, Any], index: int) -> dict[str, Any]:
    provenance = _mapping(values, "provenance")
    if not provenance:
        raise ValueError(f"Learning Context item {index} requires non-empty 'provenance'.")
    _reject_secret_like_values(f"items[{index}].provenance", provenance)
    collector = str(provenance.get("collector") or "").strip()
    capture_method = str(provenance.get("capture_method") or "").strip()
    if not collector:
        raise ValueError(f"Learning Context item {index} provenance requires 'collector'.")
    if capture_method not in ALLOWED_CAPTURE_METHODS:
        raise ValueError(
            f"Learning Context item {index} provenance.capture_method must be one of "
            f"{', '.join(sorted(ALLOWED_CAPTURE_METHODS))}."
        )
    for forbidden_key in ("raw_browser_trace", "agent_secret", "api_key", "token"):
        if forbidden_key in provenance:
            raise ValueError(
                f"Learning Context item {index} provenance contains forbidden key '{forbidden_key}'."
            )
    return dict(provenance)


def _redaction_policy(values: Mapping[str, Any], index: int) -> str:
    policy = _string(values, "redaction_policy", required=True)
    if policy not in ALLOWED_REDACTION_POLICIES:
        raise ValueError(
            f"Learning Context item {index} redaction_policy must be one of "
            f"{', '.join(sorted(ALLOWED_REDACTION_POLICIES))}."
        )
    return policy


def _stable_package_id(title: str, reference: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower() or "context"
    return f"lcp-{slug}-{sha256_text(reference)[:10]}"


def _string(
    values: Mapping[str, Any],
    key: str,
    *,
    required: bool = False,
    default: Optional[str] = None,
) -> str:
    value = values.get(key)
    if value is None:
        if required:
            raise ValueError(f"Learning Context Package requires non-empty '{key}'.")
        return default or ""
    if not isinstance(value, str) or not value.strip():
        if required:
            raise ValueError(f"Learning Context Package requires non-empty '{key}'.")
        return default or ""
    return value.strip()


def _optional_string(values: Mapping[str, Any], key: str) -> Optional[str]:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Learning Context Package field '{key}' must be a string.")
    stripped = value.strip()
    return stripped or None


def _mapping(values: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = values.get(key)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"Learning Context Package field '{key}' must be an object.")
    return dict(value)


def _reject_secret_like_values(label: str, values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        if _secret_like_key(str(key)):
            raise ValueError(f"Learning Context Package {label} contains secret-like key '{key}'.")
        if isinstance(value, str):
            _reject_secret_like_text(f"{label}.{key}", value)


def _reject_secret_like_text(label: str, text: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"Learning Context Package {label} contains secret-like text.")


def _secret_like_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in {
        "api_key",
        "apikey",
        "secret",
        "access_token",
        "refresh_token",
        "authorization",
        "password",
    }
