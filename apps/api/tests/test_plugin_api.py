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
        quarantine_dir = install_dir.parent / "quarantine"
        stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([install_dir])))
        stack.enter_context(patch.object(api_main, "plugin_install_dir", install_dir))
        stack.enter_context(patch.object(api_main, "plugin_quarantine_dir", quarantine_dir))
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
            self.assertEqual(body["trust"]["risk_level"], "high")
            self.assertEqual(body["trust"]["install_recommendation"], "review_required")
            self.assertTrue(str(body["trust"]["source_digest"]).startswith("sha256:"))
            self.assertFalse((install_dir / "demo-plugin").exists())
            self.assertEqual(body["default_action"], "quarantine")

    def test_plugin_trust_policy_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "installed"
            client, stack = self._client(install_dir)

            with stack, client:
                response = client.get("/v1/plugins/trust-policy")

            body = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(body["schema_version"], "plugin-trust-v1")
            self.assertTrue(body["local_first"])
            self.assertFalse(body["remote_code_downloads_allowed"])

    def test_plugin_registry_review_endpoint_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root)
            installed_root = root / "installed"
            installed_root.mkdir()
            registry = {
                "schemaVersion": "plugin-registry-v1",
                "trustedKeys": [],
                "plugins": [
                    {
                        "id": "demo-plugin",
                        "name": "Demo Plugin",
                        "version": "0.1.0",
                        "path": source.name,
                        "sourceDigest": "sha256:" + "0" * 64,
                    }
                ],
            }
            (root / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            client, stack = self._client(root)

            with stack, client:
                response = client.get("/v1/plugins/registry-review")

            body = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(body["schema_version"], "plugin-registry-review-v1")
            self.assertFalse(body["remote_code_downloads_allowed"])
            self.assertFalse(body["entrypoints_executed"])
            self.assertEqual(body["plugin_count"], 1)
            self.assertEqual(body["items"][0]["action"], "block_install")
            self.assertEqual(body["registry_files"], ["registry.json"])
            self.assertEqual(body["items"][0]["registry_path"], "registry.json")
            self.assertFalse((installed_root / "demo-plugin").exists())

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

    def test_install_plugin_quarantines_after_permission_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            quarantine_dir = root / "quarantine"
            client, stack = self._client(install_dir)

            with stack, client:
                quarantined = client.post(
                    "/v1/plugins/install",
                    json={
                        "source_path": str(source),
                        "confirmed_permissions": ["network:http", "read:sessions"],
                    },
                )
                listed = client.get("/v1/plugins")

            self.assertEqual(quarantined.status_code, 200, quarantined.text)
            body = quarantined.json()
            self.assertEqual(body["schema_version"], "plugin-install-result-v1")
            self.assertEqual(body["lifecycle_status"], "quarantined")
            self.assertTrue(body["quarantined"])
            self.assertFalse(body["installed"])
            self.assertTrue(body["manual_approval_required"])
            self.assertFalse(body["entrypoints_executed"])
            self.assertTrue((quarantine_dir / "demo-plugin" / "plugin.py").exists())
            self.assertFalse((install_dir / "demo-plugin").exists())
            self.assertEqual(listed.json(), [])

    def test_install_plugin_copies_only_after_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            client, stack = self._client(install_dir)

            with stack, client:
                quarantined = client.post(
                    "/v1/plugins/install",
                    json={
                        "source_path": str(source),
                        "confirmed_permissions": ["network:http", "read:sessions"],
                    },
                )
                installed = client.post(
                    "/v1/plugins/install",
                    json={
                        "source_path": str(source),
                        "confirmed_permissions": ["network:http", "read:sessions"],
                        "approve_install": True,
                        "approval_note": "Local operator approved this high-risk test plugin.",
                    },
                )
                listed = client.get("/v1/plugins")

            self.assertEqual(quarantined.status_code, 200, quarantined.text)
            self.assertEqual(installed.status_code, 200, installed.text)
            body = installed.json()
            self.assertEqual(body["lifecycle_status"], "installed")
            self.assertTrue(body["installed"])
            self.assertFalse(body["quarantined"])
            self.assertTrue(body["manual_approval_recorded"])
            self.assertTrue(body["approval_note_recorded"])
            self.assertTrue((install_dir / "demo-plugin" / "plugin.py").exists())
            self.assertEqual(listed.json()[0]["manifest"]["plugin_id"], "demo-plugin")

    def test_approved_install_requires_existing_quarantine_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root / "source")
            install_dir = root / "installed"
            quarantine_dir = root / "quarantine"
            client, stack = self._client(install_dir)

            with stack, client:
                response = client.post(
                    "/v1/plugins/install",
                    json={
                        "source_path": str(source),
                        "confirmed_permissions": ["network:http", "read:sessions"],
                        "approve_install": True,
                    },
                )

            self.assertEqual(response.status_code, 409)
            self.assertIn("must be quarantined", response.json()["detail"])
            self.assertFalse((install_dir / "demo-plugin").exists())
            self.assertFalse((quarantine_dir / "demo-plugin").exists())

    def test_install_plugin_blocks_do_not_install_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = write_plugin(root)
            install_dir = root / "installed"
            quarantine_dir = root / "quarantine"
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "plugin-registry-v1",
                        "plugins": [
                            {
                                "id": "demo-plugin",
                                "name": "Demo Plugin",
                                "version": "0.1.0",
                                "path": "demo-plugin",
                                "sourceDigest": "sha256:" + "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            client, stack = self._client(install_dir)

            with stack, client:
                response = client.post(
                    "/v1/plugins/install",
                    json={
                        "source_path": str(source),
                        "confirmed_permissions": ["network:http", "read:sessions"],
                        "approve_install": True,
                    },
                )

            self.assertEqual(response.status_code, 409)
            self.assertIn("trust policy blocks", response.json()["detail"])
            self.assertFalse((install_dir / "demo-plugin").exists())
            self.assertFalse((quarantine_dir / "demo-plugin").exists())


if __name__ == "__main__":
    unittest.main()
