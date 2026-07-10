"""Canonical JSON and safe metadata validation for CBB Protocol v1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, TypeVar

from pydantic import BaseModel

from study_anything.cbb.protocol.models import PROTOCOL_MODELS, StrictProtocolModel


ModelT = TypeVar("ModelT", bound=StrictProtocolModel)

FORBIDDEN_KEYS = {
    "api_key",
    "bearer_token",
    "cookie",
    "credentials",
    "eye_tracking",
    "keystrokes",
    "model_api_key",
    "mouse_coordinates",
    "password",
    "prompt_text",
    "raw_attention_stream",
    "raw_customer_payload",
    "raw_report_text",
    "raw_source_text",
    "screenshots",
    "secret",
    "signed_url",
    "source_text",
    "token",
    "user_owned_agent_credentials",
}

FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/private/(?:tmp|var/folders)/[^\s\"']+"),
)


class CanonicalProtocolError(ValueError):
    """Raised when canonical protocol input is unsafe or unsupported."""


def _normalize_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def assert_safe_metadata(value: Any, *, label: str = "protocol payload") -> None:
    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if _normalize_key(key) in FORBIDDEN_KEYS and child is not False:
                    raise CanonicalProtocolError(f"{label}:{path}.{key} uses forbidden field")
                walk(child, f"{path}.{key}")
            return
        if isinstance(node, (list, tuple)):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(node, str):
            if any(pattern.search(node) for pattern in FORBIDDEN_PATTERNS):
                raise CanonicalProtocolError(f"{label}:{path} contains secret-like data")

    walk(value, "$")


def model_payload(value: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json")
    else:
        payload = dict(value)
    assert_safe_metadata(payload)
    return payload


def canonical_json_bytes(value: BaseModel | Mapping[str, Any]) -> bytes:
    payload = model_payload(value)
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalProtocolError(f"payload is not canonical JSON data: {exc}") from exc
    return encoded.encode("utf-8")


def canonical_sha256(value: BaseModel | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def pretty_json(value: BaseModel | Mapping[str, Any]) -> str:
    return json.dumps(
        model_payload(value),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def validate_payload(model_type: type[ModelT], payload: Mapping[str, Any]) -> ModelT:
    assert_safe_metadata(payload, label=model_type.__name__)
    return model_type.model_validate(payload)


def schema_document(model_type: type[StrictProtocolModel]) -> dict[str, Any]:
    schema = model_type.model_json_schema(ref_template="#/$defs/{model}")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = str(schema.get("$id") or "")
    return schema


def schema_text(model_type: type[StrictProtocolModel]) -> str:
    return json.dumps(
        schema_document(model_type),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def schema_outputs(root: Path) -> dict[Path, str]:
    schema_dir = root / "platform" / "schemas" / "cbb"
    return {
        schema_dir / f"{schema_version}.schema.json": schema_text(model_type)
        for schema_version, model_type in PROTOCOL_MODELS.items()
    }
