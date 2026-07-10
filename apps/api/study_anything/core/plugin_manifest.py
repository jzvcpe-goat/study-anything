"""Plugin manifest validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Iterable, List, Mapping, Optional


PLUGIN_MANIFEST_SCHEMA_VERSION = "plugin-manifest-v1"
PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")

ALLOWED_HOOKS = {
    "importer",
    "model_provider",
    "agent_provider",
    "agent_tool",
    "agent_panel",
    "enrichment",
    "source_verifier",
    "quiz_generator",
    "grader",
    "exporter",
    "ui_panel",
}

ALLOWED_PLUGIN_CAPABILITIES = {
    "agent.invoke_tool",
    "agent.register_provider",
    "enrich.micro_lesson",
    "enrich.visual_html",
    "export.markdown",
    "export.obsidian_note",
    "export.second_brain_handoff",
    "import.context",
    "import.markdown_note",
    "import.obsidian_note",
    "import.web_excerpt",
    "quiz.generate",
    "answer.grade",
    "source.verify_reference",
    "ui.register_panel",
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
    "read:context",
    "write:context",
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
    "read:context": {
        "label": "Read Learning Context Packages",
        "risk": "medium",
        "description": "Can read bounded source excerpts and metadata inside Learning Context Packages.",
    },
    "write:context": {
        "label": "Create Learning Context Packages",
        "risk": "high",
        "description": "Can create or expand Learning Context Packages that become learning session material.",
    },
    "network:http": {
        "label": "Use HTTP network access",
        "risk": "high",
        "description": "Can call HTTP endpoints through future plugin hooks. Secrets must stay outside Study Anything.",
    },
    "ui:panel": {
        "label": "Add a UI panel",
        "risk": "low",
        "description": "Can register a future client panel surface for status, configuration, or plugin interaction.",
    },
}


ALLOWED_REVIEW_STATUSES = {
    "unreviewed",
    "self_reviewed",
    "community_reviewed",
    "maintainer_reviewed",
}


@dataclass(frozen=True)
class PluginPublisher:
    name: str
    url: Optional[str] = None


@dataclass(frozen=True)
class PluginReview:
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    notes_url: Optional[str] = None


@dataclass(frozen=True)
class PluginSignature:
    type: str
    value: str
    signer: Optional[str] = None


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    api_version: str
    entrypoint: str
    hooks: List[str]
    permissions: List[str]
    schema_version: str = PLUGIN_MANIFEST_SCHEMA_VERSION
    capabilities: List[str] = field(default_factory=list)
    description: Optional[str] = None
    publisher: Optional[PluginPublisher] = None
    review: Optional[PluginReview] = None
    signature: Optional[PluginSignature] = None
    homepage_url: Optional[str] = None
    source_url: Optional[str] = None


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


def _require_plugin_id(values: Mapping[str, object]) -> str:
    plugin_id = _require_string(values, "id")
    if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        raise ValueError(
            "Plugin manifest 'id' must be a single lowercase filesystem-safe name "
            "using only letters, numbers, '.', '_', or '-'."
        )
    return plugin_id


def _optional_string(values: Mapping[str, object], key: str) -> Optional[str]:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Plugin manifest field '{key}' must be a string when present.")
    stripped = value.strip()
    return stripped or None


def _require_list(values: Mapping[str, object], key: str) -> List[str]:
    value = values.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Plugin manifest requires string list '{key}'.")
    return list(value)


def _optional_list(values: Mapping[str, object], key: str) -> List[str]:
    value = values.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Plugin manifest field '{key}' must be a string list when present.")
    return list(value)


def _validate_members(values: Iterable[str], allowed: set[str], field_name: str) -> None:
    unsupported = sorted(set(values) - allowed)
    if unsupported:
        raise ValueError(f"Unsupported {field_name}: {', '.join(unsupported)}")


def _optional_mapping(values: Mapping[str, object], key: str) -> Optional[Mapping[str, object]]:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"Plugin manifest field '{key}' must be an object when present.")
    return value


def _validate_publisher(values: Mapping[str, object]) -> PluginPublisher:
    return PluginPublisher(
        name=_require_string(values, "name"),
        url=_optional_string(values, "url"),
    )


def _validate_review(values: Mapping[str, object]) -> PluginReview:
    status = _require_string(values, "status")
    if status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError(
            "Unsupported review status: "
            + status
            + ". Supported statuses: "
            + ", ".join(sorted(ALLOWED_REVIEW_STATUSES))
        )
    return PluginReview(
        status=status,
        reviewed_by=_optional_string(values, "reviewedBy"),
        reviewed_at=_optional_string(values, "reviewedAt"),
        notes_url=_optional_string(values, "notesUrl"),
    )


def _validate_signature(values: Mapping[str, object]) -> PluginSignature:
    return PluginSignature(
        type=_require_string(values, "type"),
        value=_require_string(values, "value"),
        signer=_optional_string(values, "signer"),
    )


def validate_manifest(values: Mapping[str, object]) -> PluginManifest:
    hooks = _require_list(values, "hooks")
    permissions = _require_list(values, "permissions")
    capabilities = _optional_list(values, "capabilities")
    schema_version = _optional_string(values, "schemaVersion") or PLUGIN_MANIFEST_SCHEMA_VERSION
    if schema_version != PLUGIN_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported plugin manifest schemaVersion: "
            + schema_version
            + ". Supported schemaVersion: "
            + PLUGIN_MANIFEST_SCHEMA_VERSION
        )
    _validate_members(hooks, ALLOWED_HOOKS, "hooks")
    _validate_members(permissions, ALLOWED_PERMISSIONS, "permissions")
    _validate_members(capabilities, ALLOWED_PLUGIN_CAPABILITIES, "capabilities")
    publisher_values = _optional_mapping(values, "publisher")
    review_values = _optional_mapping(values, "review")
    signature_values = _optional_mapping(values, "signature")
    return PluginManifest(
        plugin_id=_require_plugin_id(values),
        name=_require_string(values, "name"),
        version=_require_string(values, "version"),
        api_version=_require_string(values, "apiVersion"),
        entrypoint=_require_string(values, "entrypoint"),
        hooks=hooks,
        permissions=permissions,
        schema_version=schema_version,
        capabilities=capabilities,
        description=_optional_string(values, "description"),
        publisher=_validate_publisher(publisher_values) if publisher_values else None,
        review=_validate_review(review_values) if review_values else None,
        signature=_validate_signature(signature_values) if signature_values else None,
        homepage_url=_optional_string(values, "homepage"),
        source_url=_optional_string(values, "sourceUrl"),
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
