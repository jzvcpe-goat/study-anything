"""Security helpers for redaction and stable user hashing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any, Mapping


REDACTED = "[redacted]"


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
    return value


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    secret_markers = ("key", "secret", "token", "password", "credential")
    redacted: dict[str, object] = {}
    for key, value in values.items():
        if any(marker in key.lower() for marker in secret_markers):
            redacted[key] = REDACTED
        else:
            redacted[key] = _redact_value(value)
    return redacted


def make_dev_encryption_key() -> str:
    """Generate a local development key placeholder."""

    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
