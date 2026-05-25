"""Plugin manifest validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping


ALLOWED_HOOKS = {
    "importer",
    "model_provider",
    "agent_provider",
    "agent_tool",
    "agent_panel",
    "source_verifier",
    "quiz_generator",
    "grader",
    "exporter",
    "ui_panel",
}

ALLOWED_PERMISSIONS = {
    "read:sessions",
    "write:sessions",
    "read:cards",
    "write:cards",
    "read:models",
    "write:models",
    "read:agents",
    "write:agents",
    "network:http",
    "ui:panel",
}


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    api_version: str
    entrypoint: str
    hooks: List[str]
    permissions: List[str]


def _require_string(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Plugin manifest requires non-empty '{key}'.")
    return value


def _require_list(values: Mapping[str, object], key: str) -> List[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Plugin manifest requires string list '{key}'.")
    return list(value)


def _validate_members(values: Iterable[str], allowed: set[str], field_name: str) -> None:
    unsupported = sorted(set(values) - allowed)
    if unsupported:
        raise ValueError(f"Unsupported {field_name}: {', '.join(unsupported)}")


def validate_manifest(values: Mapping[str, object]) -> PluginManifest:
    hooks = _require_list(values, "hooks")
    permissions = _require_list(values, "permissions")
    _validate_members(hooks, ALLOWED_HOOKS, "hooks")
    _validate_members(permissions, ALLOWED_PERMISSIONS, "permissions")
    return PluginManifest(
        plugin_id=_require_string(values, "id"),
        name=_require_string(values, "name"),
        version=_require_string(values, "version"),
        api_version=_require_string(values, "apiVersion"),
        entrypoint=_require_string(values, "entrypoint"),
        hooks=hooks,
        permissions=permissions,
    )
