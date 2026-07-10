from __future__ import annotations

import unittest

from _path import ROOT  # noqa: F401

from study_anything.core.plugin_manifest import describe_permissions, validate_manifest


class PluginManifestTests(unittest.TestCase):
    def test_valid_manifest(self) -> None:
        manifest = validate_manifest(
            {
                "schemaVersion": "plugin-manifest-v1",
                "id": "example-exporter",
                "name": "Example Exporter",
                "description": "Exports redacted Study Anything sessions.",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["exporter"],
                "capabilities": ["export.markdown"],
                "permissions": ["read:sessions"],
            }
        )

        self.assertEqual(manifest.plugin_id, "example-exporter")
        self.assertEqual(manifest.schema_version, "plugin-manifest-v1")
        self.assertEqual(manifest.capabilities, ["export.markdown"])
        self.assertEqual(manifest.description, "Exports redacted Study Anything sessions.")

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

    def test_enrichment_hook_is_supported(self) -> None:
        manifest = validate_manifest(
            {
                "id": "enrichment-plugin",
                "name": "Enrichment Plugin",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["enrichment"],
                "capabilities": ["enrich.micro_lesson"],
                "permissions": ["read:context"],
            }
        )

        self.assertEqual(manifest.hooks, ["enrichment"])
        self.assertEqual(manifest.capabilities, ["enrich.micro_lesson"])

    def test_importer_hook_and_context_permissions_are_supported(self) -> None:
        manifest = validate_manifest(
            {
                "id": "context-importer",
                "name": "Context Importer",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["importer"],
                "permissions": ["read:context", "write:context"],
            }
        )

        self.assertEqual(manifest.hooks, ["importer"])
        details = describe_permissions(manifest.permissions)
        self.assertEqual(details[1].permission, "write:context")
        self.assertEqual(details[1].risk, "high")

    def test_accepts_optional_trust_metadata(self) -> None:
        manifest = validate_manifest(
            {
                "id": "reviewed-exporter",
                "name": "Reviewed Exporter",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["exporter"],
                "permissions": ["read:sessions"],
                "publisher": {"name": "Study Anything Labs", "url": "https://example.invalid"},
                "review": {
                    "status": "maintainer_reviewed",
                    "reviewedBy": "maintainers",
                    "reviewedAt": "2026-06-04",
                    "notesUrl": "https://example.invalid/review",
                },
                "signature": {
                    "type": "minisign",
                    "signer": "maintainers",
                    "value": "trusted-signature-metadata",
                },
                "homepage": "https://example.invalid/plugin",
                "sourceUrl": "https://example.invalid/source",
            }
        )

        publisher_name = manifest.publisher.name if manifest.publisher else None

        self.assertEqual(publisher_name, "Study Anything Labs")
        self.assertEqual(manifest.review.status if manifest.review else None, "maintainer_reviewed")
        self.assertEqual(manifest.signature.type if manifest.signature else None, "minisign")
        self.assertEqual(manifest.homepage_url, "https://example.invalid/plugin")

    def test_rejects_unknown_review_status(self) -> None:
        with self.assertRaises(ValueError):
            validate_manifest(
                {
                    "id": "bad-review",
                    "name": "Bad Review",
                    "version": "0.1.0",
                    "apiVersion": "0.1",
                    "entrypoint": "plugin.py",
                    "hooks": ["exporter"],
                    "permissions": ["read:sessions"],
                    "review": {"status": "paid"},
                }
            )

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

    def test_rejects_unknown_capability(self) -> None:
        with self.assertRaises(ValueError):
            validate_manifest(
                {
                    "id": "bad-capability",
                    "name": "Bad Capability",
                    "version": "0.1.0",
                    "apiVersion": "0.1",
                    "entrypoint": "plugin.py",
                    "hooks": ["exporter"],
                    "capabilities": ["secrets.read"],
                    "permissions": ["read:sessions"],
                }
            )

    def test_rejects_unknown_schema_version(self) -> None:
        with self.assertRaises(ValueError):
            validate_manifest(
                {
                    "schemaVersion": "plugin-manifest-v999",
                    "id": "future-plugin",
                    "name": "Future Plugin",
                    "version": "0.1.0",
                    "apiVersion": "0.1",
                    "entrypoint": "plugin.py",
                    "hooks": ["exporter"],
                    "permissions": ["read:sessions"],
                }
            )

    def test_rejects_plugin_ids_that_can_escape_storage_roots(self) -> None:
        for plugin_id in ("../sessions", "nested/plugin", ".hidden", "/tmp/plugin"):
            with self.subTest(plugin_id=plugin_id):
                with self.assertRaisesRegex(ValueError, "filesystem-safe"):
                    validate_manifest(
                        {
                            "id": plugin_id,
                            "name": "Unsafe Plugin",
                            "version": "0.1.0",
                            "apiVersion": "0.1",
                            "entrypoint": "plugin.py",
                            "hooks": ["exporter"],
                            "permissions": ["read:sessions"],
                        }
                    )

    def test_describes_permission_risk(self) -> None:
        details = describe_permissions(["read:sessions", "network:http"])

        self.assertEqual(details[0].permission, "read:sessions")
        self.assertEqual(details[0].risk, "medium")
        self.assertEqual(details[1].risk, "high")


if __name__ == "__main__":
    unittest.main()
