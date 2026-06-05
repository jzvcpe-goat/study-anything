from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.agent_registry import AgentRegistry
from study_anything.core.store import JsonSessionStore
from study_anything.core.workspace import LocalWorkspaceStore


class WorkspaceApiTests(unittest.TestCase):
    def _client(self, root: Path) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        stack.enter_context(patch.object(api_main, "store", JsonSessionStore(root / "sessions")))
        stack.enter_context(
            patch.object(api_main, "workspace_store", LocalWorkspaceStore(root / "workspaces.json"))
        )
        stack.enter_context(
            patch.object(api_main, "agent_registry", AgentRegistry(root / "agents.json"))
        )
        return TestClient(api_main.create_app()), stack

    def test_workspace_status_creates_local_default_without_raw_user_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))

            with stack, client:
                response = client.get(
                    "/v1/workspaces/status",
                    params={"user_id": "person@example.com"},
                )

            body = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertTrue(body["local_only"])
            self.assertEqual(body["default_workspace"]["name"], "Personal Workspace")
            self.assertNotIn("person@example.com", response.text)

    def test_create_session_assigns_default_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))

            with stack, client:
                created = client.post("/v1/sessions", json={"user_id": "learner"})
                listed = client.get(
                    "/v1/sessions",
                    params={
                        "user_id": "learner",
                        "workspace_id": created.json()["workspace_id"],
                    },
                )

            self.assertEqual(created.status_code, 200)
            self.assertTrue(created.json()["workspace_id"].startswith("ws_"))
            self.assertEqual(len(listed.json()), 1)
            self.assertEqual(listed.json()[0]["session_id"], created.json()["session_id"])

    def test_non_member_cannot_create_session_in_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))

            with stack, client:
                workspace = client.post(
                    "/v1/workspaces",
                    json={"owner_user_id": "owner", "name": "Private Course"},
                ).json()
                denied = client.post(
                    "/v1/sessions",
                    json={
                        "user_id": "outsider",
                        "workspace_id": workspace["workspace_id"],
                    },
                )

            self.assertEqual(denied.status_code, 403)

    def test_owner_can_add_workspace_member(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))

            with stack, client:
                workspace = client.post(
                    "/v1/workspaces",
                    json={"owner_user_id": "owner", "name": "Team Course"},
                ).json()
                updated = client.post(
                    f"/v1/workspaces/{workspace['workspace_id']}/members",
                    json={
                        "acting_user_id": "owner",
                        "member_user_id": "member",
                        "role": "member",
                        "display_name": "Member",
                    },
                )

            self.assertEqual(updated.status_code, 200)
            roles = {
                member["display_name"]: member["role"]
                for member in updated.json()["members"]
            }
            self.assertEqual(roles["Member"], "member")


if __name__ == "__main__":
    unittest.main()
