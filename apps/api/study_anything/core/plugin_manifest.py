"""Plugin manifest validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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

PERMISSION_DETAILS = {
    "read:sessions": {
        "label": "Read learning sessions",
        "risk": "medium",
        "description": "Can read session metadata, sources, progress, answers, and mastery records exposed by plugin hooks.",
    },
    "write:sessions": {
        "label": "Modify learning sessions",
        "risk": "high",
        "description": "Can create or update learning session state when a future plugin loader enables this hook.",
    },
    "read:cards": {
        "label": "Read study cards",
        "risk": "medium",
        "description": "Can read generated cards or review items exposed by plugin hooks.",
    },
    "write:cards": {
        "label": "Modify study cards",
        "risk": "high",
        "description": "Can create or update generated cards or review items.",
    },
    "read:models": {
        "label": "Read deprecated model settings",
        "risk": "low",
        "description": "Can inspect deprecated model-provider compatibility settings.",
    },
    "write:models": {
        "label": "Modify deprecated model settings",
        "risk": "medium",
        "description": "Can change deprecated model-provider compatibility settings.",
    },
    "read:agents": {
        "label": "Read Agent settings",
        "risk": "medium",
        "description": "Can inspect configured Agent providers, capabilities, and health metadata.",
    },
    "write:agents": {
        "label": "Modify Agent settings",
        "risk": "high",
        "description": "Can add or update Agent provider configuration.",
    },
    "network:http": {
        "label": "Use HTTP network access",
        "risk": "high",
        "description": "Can call HTTP endpoints through future plugin hooks. Secrets must stay outside Study Anything.",
    },
    "ui:panel": {
        "label": "Add a UI panel",
        "risk": "low",
        "description": "Can register a frontend panel surface for status, configuration, or plugin interaction.",
    },
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


@dataclass(frozen=True)
class PluginPermissionDetail:
    permission: str
    label: str
    risk: str
    description: str

    def public_dict(self) -> dict[str, str]:
        return asdict(self)


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


def describe_permission(permission: str) -> PluginPermissionDetail:
    detail = PERMISSION_DETAILS.get(
        permission,
        {
            "label": permission,
            "risk": "unknown",
            "description": "No permission description is available.",
        },
    )
    return PluginPermissionDetail(
        permission=permission,
        label=detail["label"],
        risk=detail["risk"],
        description=detail["description"],
    )


def describe_permissions(permissions: Iterable[str]) -> List[PluginPermissionDetail]:
    return [describe_permission(permission) for permission in permissions]
