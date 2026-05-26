from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from study_anything.core.plugin_manifest import validate_manifest


class PluginManifestTests(unittest.TestCase):
    def test_valid_manifest(self) -> None:
        manifest = validate_manifest(
            {
                "id": "example-exporter",
                "name": "Example Exporter",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["exporter"],
                "permissions": ["read:sessions"],
            }
        )

        self.assertEqual(manifest.plugin_id, "example-exporter")

    def test_agent_hooks_are_supported(self) -> None:
        manifest = validate_manifest(
            {
                "id": "agent-panel",
                "name": "Agent Panel",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["agent_provider", "agent_tool", "agent_panel"],
                "permissions": ["read:agents", "write:agents", "ui:panel"],
            }
        )

        self.assertIn("agent_provider", manifest.hooks)

    def test_rejects_unknown_hook(self) -> None:
        with self.assertRaises(ValueError):
            validate_manifest(
                {
                    "id": "bad",
                    "name": "Bad",
                    "version": "0.1.0",
                    "apiVersion": "0.1",
                    "entrypoint": "plugin.py",
                    "hooks": ["superuser"],
                    "permissions": ["read:sessions"],
                }
            )

    def test_rejects_unknown_permission(self) -> None:
        with self.assertRaises(ValueError):
            validate_manifest(
                {
                    "id": "bad",
                    "name": "Bad",
                    "version": "0.1.0",
                    "apiVersion": "0.1",
                    "entrypoint": "plugin.py",
                    "hooks": ["exporter"],
                    "permissions": ["root"],
                }
            )


if __name__ == "__main__":
    unittest.main()
