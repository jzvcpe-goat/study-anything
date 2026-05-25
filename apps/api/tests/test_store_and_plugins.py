from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from neural_console.core.plugin_registry import PluginRegistry
from neural_console.core.store import JsonSessionStore, create_session_store
from neural_console.core.workflow import new_session


class StoreAndPluginTests(unittest.TestCase):
    def test_json_session_store_round_trips_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonSessionStore(Path(tmpdir))
            state = new_session("local-user")

            store.save(state)
            restored = store.get(state.session_id)

            self.assertEqual(restored.session_id, state.session_id)
            self.assertEqual(restored.user_hash, state.user_hash)
            self.assertEqual(len(store.list_sessions()), 1)

    def test_create_session_store_defaults_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = create_session_store(data_dir=Path(tmpdir), backend="json")

            self.assertIsInstance(store, JsonSessionStore)

    def test_create_session_store_rejects_unknown_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                create_session_store(data_dir=Path(tmpdir), backend="unknown")

    def test_plugin_registry_discovers_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "demo-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "id": "demo-plugin",
                        "name": "Demo Plugin",
                        "version": "0.1.0",
                        "apiVersion": "0.1",
                        "entrypoint": "plugin.py",
                        "hooks": ["exporter"],
                        "permissions": ["read:sessions"],
                    }
                ),
                encoding="utf-8",
            )

            statuses = PluginRegistry([Path(tmpdir)]).discover()

            self.assertEqual(len(statuses), 1)
            self.assertEqual(statuses[0].status, "ready")
            self.assertEqual(statuses[0].manifest.plugin_id if statuses[0].manifest else None, "demo-plugin")

    def test_plugin_registry_reports_invalid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "bad-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text("{not-json", encoding="utf-8")

            statuses = PluginRegistry([Path(tmpdir)]).discover()

            self.assertEqual(statuses[0].status, "invalid")


if __name__ == "__main__":
    unittest.main()
