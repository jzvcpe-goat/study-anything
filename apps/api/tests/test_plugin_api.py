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


def write_plugin(root: Path, plugin_id: str = "demo-plugin") -> Path:
    plugin_dir = root / plugin_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "id": plugin_id,
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
    (plugin_dir / "plugin.py").write_text("VALUE = 'demo'\n", encoding="utf-8")
    return plugin_dir


class PluginApiTests(unittest.TestCase):
    def _client(self, install_dir: Path) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([install_dir])))
        stack.enter_context(patch.object(api_main, "plugin_install_dir", install_dir))
        return TestClient(api_main.create_app()), stack

    def test_preview_plugin_returns_permission_details_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            client, stack = self._client(install_dir)

            with stack, client:
                response = client.post("/v1/plugins/preview", json={"source_path": str(source)})

            body = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(body["status"], "ready")
            self.assertTrue(body["requires_confirmation"])
            self.assertEqual(body["manifest"]["plugin_id"], "demo-plugin")
            self.assertEqual(body["permission_details"][1]["permission"], "network:http")
            self.assertFalse((install_dir / "demo-plugin").exists())

    def test_install_plugin_requires_exact_permission_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            client, stack = self._client(install_dir)

            with stack, client:
                response = client.post(
                    "/v1/plugins/install",
                    json={
                        "source_path": str(source),
                        "confirmed_permissions": ["read:sessions"],
                    },
                )

            body = response.json()
            self.assertEqual(response.status_code, 409)
            self.assertIn("network:http", body["detail"]["expected_permissions"])
            self.assertFalse((install_dir / "demo-plugin").exists())

    def test_install_plugin_copies_after_permission_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            client, stack = self._client(install_dir)

            with stack, client:
                installed = client.post(
                    "/v1/plugins/install",
                    json={
                        "source_path": str(source),
                        "confirmed_permissions": ["network:http", "read:sessions"],
                    },
                )
                listed = client.get("/v1/plugins")

            self.assertEqual(installed.status_code, 200)
            self.assertEqual(installed.json()["status"], "ready")
            self.assertTrue((install_dir / "demo-plugin" / "plugin.py").exists())
            self.assertEqual(listed.json()[0]["manifest"]["plugin_id"], "demo-plugin")


if __name__ == "__main__":
    unittest.main()
