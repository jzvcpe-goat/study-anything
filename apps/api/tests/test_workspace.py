from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.core.workspace import (
    LocalWorkspaceStore,
    WorkspaceAccessDenied,
    WorkspaceError,
)


class WorkspaceStoreTests(unittest.TestCase):
    def test_default_workspace_is_local_only_and_hashes_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalWorkspaceStore(Path(tmpdir) / "workspaces.json")

            status = store.status("alice@example.com")
            persisted = Path(tmpdir, "workspaces.json").read_text(encoding="utf-8")

        self.assertEqual(status["schema_version"], "workspace-v2")
        self.assertTrue(status["local_only"])
        self.assertFalse(status["account_required"])
        self.assertFalse(status["raw_user_ids_stored"])
        self.assertEqual(status["default_workspace"]["name"], "Personal Workspace")
        self.assertNotIn("alice@example.com", json.dumps(status))
        self.assertNotIn("alice@example.com", persisted)

    def test_create_workspace_rejects_duplicate_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalWorkspaceStore(Path(tmpdir) / "workspaces.json")

            store.create_workspace(owner_user_id="owner", name="Research Lab", slug="research")
            with self.assertRaises(WorkspaceError):
                store.create_workspace(owner_user_id="owner", name="Research Two", slug="research")

    def test_owner_can_add_member_but_viewer_cannot_manage_members(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalWorkspaceStore(Path(tmpdir) / "workspaces.json")
            workspace = store.create_workspace(owner_user_id="owner", name="Course Team")

            updated = store.add_member(
                workspace_id=workspace.workspace_id,
                acting_user_id="owner",
                member_user_id="viewer",
                role="viewer",
                display_name="Viewer",
            )
            self.assertIn("Viewer", {member.display_name for member in updated.members.values()})

            with self.assertRaises(WorkspaceAccessDenied):
                store.add_member(
                    workspace_id=workspace.workspace_id,
                    acting_user_id="viewer",
                    member_user_id="other",
                    role="member",
                )

    def test_tenant_identity_and_workspace_are_isolated(self) -> None:
        tenant_a = "tnt_" + "a" * 32
        tenant_b = "tnt_" + "b" * 32
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalWorkspaceStore(Path(tmpdir) / "workspaces.json")
            workspace_a = store.create_workspace(
                owner_user_id="prn_owner",
                name="Research",
                slug="shared",
                tenant_id=tenant_a,
            )
            workspace_b = store.create_workspace(
                owner_user_id="prn_owner",
                name="Research",
                slug="shared",
                tenant_id=tenant_b,
            )

            store.assert_permission(
                "prn_owner",
                workspace_a.workspace_id,
                "read_sessions",
                tenant_id=tenant_a,
            )
            with self.assertRaisesRegex(WorkspaceAccessDenied, "outside"):
                store.assert_permission(
                    "prn_owner",
                    workspace_a.workspace_id,
                    "read_sessions",
                    tenant_id=tenant_b,
                )

        self.assertNotEqual(workspace_a.owner_hash, workspace_b.owner_hash)
        self.assertTrue(workspace_a.public_dict()["tenant_scoped"])
        self.assertFalse(workspace_a.public_dict()["tenant_id_included"])

    def test_workspace_v1_payload_migrates_to_local_tenant(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "workspaces.json"
            legacy = LocalWorkspaceStore(path)
            workspace = legacy.create_workspace(owner_user_id="owner", name="Legacy")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["schema_version"] = "workspace-v1"
            for identity in payload["identities"].values():
                identity.pop("tenant_id", None)
            for item in payload["workspaces"].values():
                item.pop("tenant_id", None)
            path.write_text(json.dumps(payload), encoding="utf-8")

            restored = LocalWorkspaceStore(path).list_for_user("owner")

        self.assertEqual([item.workspace_id for item in restored], [workspace.workspace_id])
        self.assertTrue(restored[0].public_dict()["local_only"])


if __name__ == "__main__":
    unittest.main()
