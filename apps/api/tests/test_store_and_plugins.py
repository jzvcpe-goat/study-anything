from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.store import InMemorySessionStore, JsonSessionStore, create_session_store
from study_anything.core.workflow import new_session


class StoreAndPluginTests(unittest.TestCase):
    def test_session_stores_filter_tenant_before_returning_state(self) -> None:
        tenant_a = "tnt_" + "a" * 32
        tenant_b = "tnt_" + "b" * 32
        store = InMemorySessionStore()
        state_a = store.save(new_session("principal-a", tenant_id=tenant_a))
        state_b = store.save(new_session("principal-b", tenant_id=tenant_b))

        self.assertEqual(store.get(state_a.session_id, tenant_id=tenant_a), state_a)
        with self.assertRaises(KeyError):
            store.get(state_a.session_id, tenant_id=tenant_b)
        self.assertEqual(
            [item.session_id for item in store.list_sessions(tenant_id=tenant_a)],
            [state_a.session_id],
        )
        self.assertNotIn("tenant_id", state_a.public_dict())
        self.assertTrue(state_a.public_dict()["tenant_scoped"])
        self.assertNotEqual(state_a.user_hash, state_b.user_hash)

    def test_json_session_store_round_trips_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonSessionStore(Path(tmpdir))
            tenant_a = "tnt_" + "a" * 32
            tenant_b = "tnt_" + "b" * 32
            state = new_session("principal-a", tenant_id=tenant_a)

            store.save(state)
            restored = store.get(state.session_id, tenant_id=tenant_a)

            self.assertEqual(restored.session_id, state.session_id)
            self.assertEqual(restored.user_hash, state.user_hash)
            self.assertEqual(restored.tenant_id, tenant_a)
            self.assertEqual(len(store.list_sessions(tenant_id=tenant_a)), 1)
            self.assertEqual(store.list_sessions(tenant_id=tenant_b), [])
            with self.assertRaises(KeyError):
                store.get(state.session_id, tenant_id=tenant_b)

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
            public = statuses[0].public_dict()
            self.assertEqual(public["permission_details"][0]["permission"], "read:sessions")

    def test_plugin_registry_previews_local_manifest(self) -> None:
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
                        "permissions": ["read:sessions", "network:http"],
                    }
                ),
                encoding="utf-8",
            )

            status = PluginRegistry([]).preview_local(plugin_dir)

            self.assertEqual(status.status, "ready")
            self.assertEqual(len(status.public_dict()["permission_details"]), 2)

    def test_plugin_registry_reports_invalid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "bad-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text("{not-json", encoding="utf-8")

            statuses = PluginRegistry([Path(tmpdir)]).discover()

            self.assertEqual(statuses[0].status, "invalid")

    def test_plugin_registry_installs_valid_local_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "source" / "demo-plugin"
            install_dir = root / "installed"
            source_dir.mkdir(parents=True)
            (source_dir / "plugin.json").write_text(
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
            (source_dir / "plugin.py").write_text("VALUE = 'installed'\n", encoding="utf-8")
            cache_dir = source_dir / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "plugin.pyc").write_bytes(b"cache")

            status = PluginRegistry([]).install_local(source_dir, install_dir)

            self.assertEqual(status.status, "ready")
            self.assertTrue((install_dir / "demo-plugin" / "plugin.py").exists())
            self.assertFalse((install_dir / "demo-plugin" / "__pycache__").exists())
            discovered = PluginRegistry([install_dir]).discover()
            self.assertEqual(discovered[0].manifest.plugin_id if discovered[0].manifest else None, "demo-plugin")

    def test_plugin_registry_quarantines_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "source" / "demo-plugin"
            install_dir = root / "installed"
            quarantine_dir = root / "quarantine"
            source_dir.mkdir(parents=True)
            (source_dir / "plugin.json").write_text(
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
            (source_dir / "plugin.py").write_text("VALUE = 'quarantined'\n", encoding="utf-8")

            status = PluginRegistry([]).quarantine_local(source_dir, quarantine_dir)

            self.assertEqual(status.status, "ready")
            self.assertTrue((quarantine_dir / "demo-plugin" / "plugin.py").exists())
            self.assertFalse((install_dir / "demo-plugin").exists())
            self.assertEqual(PluginRegistry([install_dir]).discover(), [])

    def test_plugin_registry_refuses_implicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "source" / "demo-plugin"
            install_dir = root / "installed"
            source_dir.mkdir(parents=True)
            (source_dir / "plugin.json").write_text(
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
            registry = PluginRegistry([])
            registry.install_local(source_dir, install_dir)

            with self.assertRaises(FileExistsError):
                registry.install_local(source_dir, install_dir)

    def test_plugin_registry_rejects_traversal_id_without_deleting_sibling_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "source"
            quarantine_dir = root / "quarantine"
            sibling_data = root / "sessions"
            source_dir.mkdir()
            sibling_data.mkdir()
            sentinel = sibling_data / "session.json"
            sentinel.write_text("private session", encoding="utf-8")
            (source_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "id": "../sessions",
                        "name": "Traversal Plugin",
                        "version": "0.1.0",
                        "apiVersion": "0.1",
                        "entrypoint": "plugin.py",
                        "hooks": ["exporter"],
                        "permissions": ["read:sessions"],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "filesystem-safe"):
                PluginRegistry([]).quarantine_local(source_dir, quarantine_dir)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "private session")
            self.assertFalse(quarantine_dir.exists())

    def test_plugin_registry_rejects_symbolic_links_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "source"
            install_dir = root / "installed"
            source_dir.mkdir()
            (source_dir / "plugin.json").write_text(
                json.dumps(
                    {
                        "id": "linked-plugin",
                        "name": "Linked Plugin",
                        "version": "0.1.0",
                        "apiVersion": "0.1",
                        "entrypoint": "plugin.py",
                        "hooks": ["exporter"],
                        "permissions": ["read:sessions"],
                    }
                ),
                encoding="utf-8",
            )
            secret = root / "outside.txt"
            secret.write_text("outside", encoding="utf-8")
            (source_dir / "plugin.py").symlink_to(secret)

            with self.assertRaisesRegex(ValueError, "symbolic links"):
                PluginRegistry([]).install_local(source_dir, install_dir)

            self.assertFalse((install_dir / "linked-plugin").exists())


if __name__ == "__main__":
    unittest.main()
