"""Local-first identity and workspace boundaries.

This is not a hosted account system. It gives self-host installs a stable
ownership model that future Sync, Publish, and Teams services can build on
without changing the core local data contract.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .events import utc_now
from .security import hash_user_id


WORKSPACE_SCHEMA_VERSION = "workspace-v1"

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "owner": [
        "read_sessions",
        "create_sessions",
        "manage_workspace",
        "manage_members",
        "configure_agents",
        "install_plugins",
        "export_pmf",
    ],
    "admin": [
        "read_sessions",
        "create_sessions",
        "manage_members",
        "configure_agents",
        "install_plugins",
        "export_pmf",
    ],
    "member": ["read_sessions", "create_sessions", "export_pmf"],
    "viewer": ["read_sessions"],
}


class WorkspaceError(ValueError):
    """Raised when a workspace request is invalid."""


class WorkspaceAccessDenied(PermissionError):
    """Raised when a local user hash does not have a workspace permission."""


@dataclass(frozen=True)
class LocalIdentity:
    user_hash: str
    display_name: str
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def public_dict(self) -> dict[str, object]:
        return {
            "user_hash": self.user_hash,
            "display_name": self.display_name,
            "raw_user_id_stored": False,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class WorkspaceMember:
    user_hash: str
    role: str
    display_name: str
    joined_at: str = field(default_factory=utc_now)

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    name: str
    slug: str
    owner_hash: str
    members: dict[str, WorkspaceMember]
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def public_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "slug": self.slug,
            "owner_hash": self.owner_hash,
            "members": [
                member.public_dict()
                for member in sorted(self.members.values(), key=lambda item: item.user_hash)
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "local_only": True,
        }


class LocalWorkspaceStore:
    """JSON-backed local identity and workspace store."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def ensure_default_workspace(
        self,
        user_id: str,
        display_name: Optional[str] = None,
    ) -> Workspace:
        identity = self.ensure_identity(user_id, display_name)
        payload = self._load()
        defaults = payload.setdefault("defaults", {})
        default_workspace_id = defaults.get(identity.user_hash)
        workspaces = self._workspaces_from_payload(payload)
        if default_workspace_id and default_workspace_id in workspaces:
            return workspaces[default_workspace_id]

        workspace = self._new_workspace(
            owner=identity,
            name="Personal Workspace",
            slug="personal",
        )
        workspaces[workspace.workspace_id] = workspace
        defaults[identity.user_hash] = workspace.workspace_id
        payload["workspaces"] = {
            key: _workspace_to_payload(value) for key, value in workspaces.items()
        }
        self._save(payload)
        return workspace

    def ensure_identity(self, user_id: str, display_name: Optional[str] = None) -> LocalIdentity:
        user_hash = hash_user_id(_require_user_id(user_id))
        payload = self._load()
        identities = self._identities_from_payload(payload)
        existing = identities.get(user_hash)
        normalized_name = _normalize_display_name(display_name) or "Local learner"
        if existing is None:
            identity = LocalIdentity(user_hash=user_hash, display_name=normalized_name)
        elif display_name and _normalize_display_name(display_name) != existing.display_name:
            identity = replace(
                existing,
                display_name=_normalize_display_name(display_name) or existing.display_name,
                updated_at=utc_now(),
            )
        else:
            return existing
        identities[user_hash] = identity
        payload["identities"] = {key: asdict(value) for key, value in identities.items()}
        self._save(payload)
        return identity

    def status(self, user_id: str) -> dict[str, object]:
        identity = self.ensure_identity(user_id)
        default_workspace = self.ensure_default_workspace(user_id)
        memberships = [
            workspace
            for workspace in self.list_for_user(user_id)
            if identity.user_hash in workspace.members
        ]
        return {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "local_only": True,
            "account_required": False,
            "raw_user_ids_stored": False,
            "identity": identity.public_dict(),
            "default_workspace": default_workspace.public_dict(),
            "workspaces": [workspace.public_dict() for workspace in memberships],
            "role_permissions": ROLE_PERMISSIONS,
            "commercial_boundary": {
                "hosted_sync_enabled": False,
                "billing_enabled": False,
                "remote_identity_provider": None,
            },
        }

    def list_for_user(self, user_id: str) -> list[Workspace]:
        user_hash = hash_user_id(_require_user_id(user_id))
        return [
            workspace
            for workspace in self._workspaces_from_payload(self._load()).values()
            if user_hash in workspace.members
        ]

    def create_workspace(
        self,
        *,
        owner_user_id: str,
        name: str,
        slug: Optional[str] = None,
        owner_display_name: Optional[str] = None,
    ) -> Workspace:
        owner = self.ensure_identity(owner_user_id, owner_display_name)
        payload = self._load()
        workspaces = self._workspaces_from_payload(payload)
        normalized_slug = _normalize_slug(slug or name)
        if any(workspace.slug == normalized_slug for workspace in workspaces.values()):
            raise WorkspaceError(f"Workspace slug '{normalized_slug}' already exists.")
        workspace = self._new_workspace(owner=owner, name=name, slug=normalized_slug)
        workspaces[workspace.workspace_id] = workspace
        payload["workspaces"] = {
            key: _workspace_to_payload(value) for key, value in workspaces.items()
        }
        payload.setdefault("defaults", {}).setdefault(owner.user_hash, workspace.workspace_id)
        self._save(payload)
        return workspace

    def add_member(
        self,
        *,
        workspace_id: str,
        acting_user_id: str,
        member_user_id: str,
        role: str,
        display_name: Optional[str] = None,
    ) -> Workspace:
        normalized_role = _require_role(role)
        self.assert_permission(acting_user_id, workspace_id, "manage_members")
        member = self.ensure_identity(member_user_id, display_name)
        payload = self._load()
        workspaces = self._workspaces_from_payload(payload)
        workspace = self._require_workspace(workspaces, workspace_id)
        if member.user_hash == workspace.owner_hash and normalized_role != "owner":
            raise WorkspaceError("The workspace owner must keep the owner role.")
        members = dict(workspace.members)
        members[member.user_hash] = WorkspaceMember(
            user_hash=member.user_hash,
            role=normalized_role,
            display_name=member.display_name,
        )
        updated = replace(workspace, members=members, updated_at=utc_now())
        workspaces[workspace.workspace_id] = updated
        payload["workspaces"] = {
            key: _workspace_to_payload(value) for key, value in workspaces.items()
        }
        self._save(payload)
        return updated

    def assert_permission(self, user_id: str, workspace_id: str, permission: str) -> None:
        user_hash = hash_user_id(_require_user_id(user_id))
        workspace = self._require_workspace(
            self._workspaces_from_payload(self._load()),
            workspace_id,
        )
        member = workspace.members.get(user_hash)
        if member is None:
            raise WorkspaceAccessDenied("User is not a member of this workspace.")
        if permission not in ROLE_PERMISSIONS.get(member.role, []):
            raise WorkspaceAccessDenied(
                f"Role '{member.role}' cannot perform workspace action '{permission}'."
            )

    def _new_workspace(self, *, owner: LocalIdentity, name: str, slug: str) -> Workspace:
        clean_name = _normalize_name(name)
        owner_member = WorkspaceMember(
            user_hash=owner.user_hash,
            role="owner",
            display_name=owner.display_name,
        )
        return Workspace(
            workspace_id="ws_" + uuid4().hex[:16],
            name=clean_name,
            slug=slug,
            owner_hash=owner.user_hash,
            members={owner.user_hash: owner_member},
        )

    def _require_workspace(
        self,
        workspaces: dict[str, Workspace],
        workspace_id: str,
    ) -> Workspace:
        workspace = workspaces.get(workspace_id)
        if workspace is None:
            raise KeyError(workspace_id)
        return workspace

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {
                "schema_version": WORKSPACE_SCHEMA_VERSION,
                "identities": {},
                "workspaces": {},
                "defaults": {},
            }
        values = json.loads(self.path.read_text(encoding="utf-8"))
        if values.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceError("Unsupported workspace store schema.")
        values.setdefault("identities", {})
        values.setdefault("workspaces", {})
        values.setdefault("defaults", {})
        return values

    def _save(self, values: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _identities_from_payload(self, payload: dict[str, object]) -> dict[str, LocalIdentity]:
        identities = payload.get("identities", {})
        if not isinstance(identities, dict):
            raise WorkspaceError("Workspace identities payload is invalid.")
        return {
            user_hash: LocalIdentity(**value)
            for user_hash, value in identities.items()
            if isinstance(user_hash, str) and isinstance(value, dict)
        }

    def _workspaces_from_payload(self, payload: dict[str, object]) -> dict[str, Workspace]:
        workspaces = payload.get("workspaces", {})
        if not isinstance(workspaces, dict):
            raise WorkspaceError("Workspace payload is invalid.")
        return {
            workspace_id: _workspace_from_payload(value)
            for workspace_id, value in workspaces.items()
            if isinstance(workspace_id, str) and isinstance(value, dict)
        }


def _workspace_from_payload(values: dict[str, object]) -> Workspace:
    member_values = values.get("members", {})
    if isinstance(member_values, list):
        members = {
            item["user_hash"]: WorkspaceMember(**item)
            for item in member_values
            if isinstance(item, dict) and isinstance(item.get("user_hash"), str)
        }
    elif isinstance(member_values, dict):
        members = {
            user_hash: WorkspaceMember(**item)
            for user_hash, item in member_values.items()
            if isinstance(user_hash, str) and isinstance(item, dict)
        }
    else:
        members = {}
    return Workspace(
        workspace_id=str(values["workspace_id"]),
        name=str(values["name"]),
        slug=str(values["slug"]),
        owner_hash=str(values["owner_hash"]),
        members=members,
        created_at=str(values.get("created_at") or utc_now()),
        updated_at=str(values.get("updated_at") or utc_now()),
    )


def _workspace_to_payload(workspace: Workspace) -> dict[str, object]:
    values = workspace.public_dict()
    values["members"] = {
        user_hash: asdict(member) for user_hash, member in workspace.members.items()
    }
    values.pop("local_only", None)
    return values


def _require_user_id(user_id: str) -> str:
    value = user_id.strip()
    if not value:
        raise WorkspaceError("user_id is required.")
    return value


def _normalize_display_name(display_name: Optional[str]) -> Optional[str]:
    if display_name is None:
        return None
    value = display_name.strip()
    if not value:
        return None
    return value[:80]


def _normalize_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise WorkspaceError("Workspace name is required.")
    return value[:80]


def _normalize_slug(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", lowered).strip("-")
    if not slug:
        slug = "workspace"
    return slug[:48]


def _require_role(role: str) -> str:
    value = role.strip().lower()
    if value not in ROLE_PERMISSIONS:
        raise WorkspaceError(
            "Unsupported workspace role: "
            + role
            + ". Supported roles: "
            + ", ".join(sorted(ROLE_PERMISSIONS))
        )
    return value
