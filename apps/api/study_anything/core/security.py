"""Security helpers for redaction and stable user hashing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REDACTED = "[redacted]"
SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "bearer",
    "cookie",
    "credential",
    "key",
    "password",
    "secret",
    "token",
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
)


def hash_user_id(user_id: str, salt: str = "study-anything-alpha") -> str:
    """Return a stable, non-reversible user hash for logs and events."""

    digest = hmac.new(salt.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, str) and looks_like_secret_value(value):
        return REDACTED
    return value


def is_secret_key(key: str) -> bool:
    value = key.lower()
    return any(marker in value for marker in SECRET_KEY_MARKERS)


def looks_like_secret_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in values.items():
        if is_secret_key(key):
            redacted[key] = REDACTED
        else:
            redacted[key] = _redact_value(value)
    return redacted


def redact_url_secrets(value: str | None) -> str | None:
    """Return a URL with credentials and secret-like query parameters removed."""

    if value is None:
        return None
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return value
    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    port = f":{parts.port}" if parts.port is not None else ""
    netloc = f"{hostname}{port}"
    safe_query = urlencode(
        [
            (key, REDACTED if is_secret_key(key) else query_value)
            for key, query_value in parse_qsl(parts.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    return urlunsplit((parts.scheme, netloc, parts.path, safe_query, parts.fragment))


def url_contains_inline_secret(value: str | None) -> bool:
    """Detect endpoint forms that would store secrets inside Study Anything."""

    if not value:
        return False
    parts = urlsplit(value)
    if parts.username or parts.password:
        return True
    return any(is_secret_key(key) for key, _query_value in parse_qsl(parts.query, keep_blank_values=True))


def make_dev_encryption_key() -> str:
    """Generate a local development key placeholder."""

    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
