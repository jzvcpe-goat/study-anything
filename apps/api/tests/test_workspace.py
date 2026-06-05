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

        self.assertEqual(status["schema_version"], "workspace-v1")
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


if __name__ == "__main__":
    unittest.main()
