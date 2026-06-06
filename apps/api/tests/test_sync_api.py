from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import Answer, new_session, submit_answers, submit_reading


class SyncApiTests(unittest.TestCase):
    def _client(self, root: Path, store: InMemorySessionStore) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        stack.enter_context(patch.object(api_main, "data_dir", root))
        stack.enter_context(patch.object(api_main, "store", store))
        stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([])))
        return TestClient(api_main.create_app()), stack

    def test_sync_export_and_inspect_return_encrypted_summary_only(self) -> None:
        store = InMemorySessionStore()
        state = new_session("api-sync-user@example.com")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="demo://sync-api",
            title="API Sync Private Title",
            text="API sync private source text.",
        )
        state = submit_answers(
            state,
            [Answer(item_id="q1", text="API sync private answer.")],
        )
        store.save(state)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "agent_registry.json").write_text(
                json.dumps(
                    {
                        "providers": [
                            {
                                "provider_id": "agent-api",
                                "endpoint": "http://127.0.0.1:8787/private",
                            }
                        ],
                        "defaults": {},
                    }
                ),
                encoding="utf-8",
            )
            client, stack = self._client(root, store)
            with stack, client:
                status = client.get("/v1/sync/status")
                exported = client.post(
                    "/v1/sync/export",
                    json={"passphrase": "local encrypted sync passphrase"},
                )
                inspected = client.post(
                    "/v1/sync/inspect",
                    json={
                        "passphrase": "local encrypted sync passphrase",
                        "package": exported.json()["package"],
                    },
                )
                restore_preview = client.post(
                    "/v1/sync/restore-preview",
                    json={
                        "passphrase": "local encrypted sync passphrase",
                        "package": exported.json()["package"],
                    },
                )
                rejected = client.post(
                    "/v1/sync/inspect",
                    json={
                        "passphrase": "wrong passphrase",
                        "package": exported.json()["package"],
                    },
                )

        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["hosted_sync_enabled"])
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()["package"]["schema_version"], "sync-package-v1")
        self.assertEqual(exported.json()["payload_summary"]["session_count"], 1)
        self.assertEqual(exported.json()["payload_summary"]["agent_provider_count"], 1)
        self.assertEqual(inspected.status_code, 200)
        self.assertEqual(inspected.json()["payload_summary"]["session_count"], 1)
        self.assertFalse(inspected.json()["privacy"]["plaintext_returned"])
        self.assertEqual(restore_preview.status_code, 200)
        self.assertEqual(restore_preview.json()["schema_version"], "sync-restore-preview-v1")
        self.assertFalse(restore_preview.json()["restore_api_enabled"])
        self.assertFalse(restore_preview.json()["privacy"]["plaintext_returned"])
        self.assertEqual(restore_preview.json()["changes"]["sessions_to_overwrite"], 1)
        self.assertEqual(restore_preview.json()["changes"]["sessions_to_add"], 0)
        self.assertEqual(rejected.status_code, 400)

        combined = exported.text + inspected.text + restore_preview.text
        self.assertNotIn("api-sync-user@example.com", combined)
        self.assertNotIn("API sync private source text", combined)
        self.assertNotIn("API sync private answer", combined)
        self.assertNotIn("127.0.0.1:8787/private", combined)

    def test_sync_export_rejects_short_passphrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir), InMemorySessionStore())
            with stack, client:
                response = client.post(
                    "/v1/sync/export",
                    json={"passphrase": "short"},
                )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
