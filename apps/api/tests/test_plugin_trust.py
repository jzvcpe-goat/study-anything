from __future__ import annotations

import json
import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from _path import ROOT  # noqa: F401

from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.plugin_trust import (
    assess_plugin_trust,
    compute_plugin_source_digest,
    plugin_registry_signature_payload,
    plugin_trust_policy,
)


def write_trust_plugin(root: Path, permissions: list[str] | None = None) -> Path:
    plugin_dir = root / "trust-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "id": "trust-plugin",
                "name": "Trust Plugin",
                "version": "0.1.0",
                "apiVersion": "0.1",
                "entrypoint": "plugin.py",
                "hooks": ["exporter"],
                "permissions": permissions or ["read:sessions"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text("VALUE = 'trust'\n", encoding="utf-8")
    return plugin_dir


class PluginTrustTests(unittest.TestCase):
    def test_digest_ignores_cache_files_and_changes_with_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = write_trust_plugin(Path(tmpdir))
            cache_dir = plugin_dir / "__pycache__"
            cache_dir.mkdir()
            (cache_dir / "plugin.pyc").write_bytes(b"first-cache")

            first_digest = compute_plugin_source_digest(plugin_dir)
            (cache_dir / "plugin.pyc").write_bytes(b"changed-cache")
            self.assertEqual(first_digest, compute_plugin_source_digest(plugin_dir))

            (plugin_dir / "plugin.py").write_text("VALUE = 'changed'\n", encoding="utf-8")

            self.assertNotEqual(first_digest, compute_plugin_source_digest(plugin_dir))

    def test_assessment_reports_high_risk_unreviewed_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = write_trust_plugin(Path(tmpdir), ["read:sessions", "network:http"])
            status = PluginRegistry([]).preview_local(plugin_dir)

            self.assertIsNotNone(status.trust)
            trust = status.trust.public_dict() if status.trust else {}
            self.assertEqual(trust["risk_level"], "high")
            self.assertEqual(trust["review_status"], "unreviewed")
            self.assertEqual(trust["install_recommendation"], "review_required")
            self.assertIn("source_digest", trust)
            self.assertIn("High-risk permissions requested", " ".join(trust["warnings"]))

    def test_invalid_manifest_is_not_installable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "bad-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text("{not-json", encoding="utf-8")

            report = assess_plugin_trust(plugin_dir, None).public_dict()

            self.assertEqual(report["install_recommendation"], "do_not_install")
            self.assertEqual(report["risk_level"], "unknown")

    def test_registry_digest_match_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plugin_dir = write_trust_plugin(root)
            digest = compute_plugin_source_digest(plugin_dir)
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "apiVersion": "0.1",
                        "plugins": [
                            {
                                "id": "trust-plugin",
                                "path": "trust-plugin",
                                "sourceDigest": digest,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            status = PluginRegistry([root]).preview_local(plugin_dir)
            trust = status.trust.public_dict() if status.trust else {}

            self.assertEqual(trust["registry_status"], "digest_verified")
            self.assertEqual(trust["signature_status"], "registry_digest_verified")
            self.assertEqual(trust["install_recommendation"], "allow_with_confirmation")

    def test_registry_digest_mismatch_blocks_install_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plugin_dir = write_trust_plugin(root)
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "apiVersion": "0.1",
                        "plugins": [
                            {
                                "id": "trust-plugin",
                                "path": "trust-plugin",
                                "sourceDigest": "sha256:" + "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            status = PluginRegistry([root]).preview_local(plugin_dir)
            trust = status.trust.public_dict() if status.trust else {}

            self.assertEqual(trust["registry_status"], "digest_mismatch")
            self.assertEqual(trust["signature_status"], "registry_signature_invalid")
            self.assertEqual(trust["install_recommendation"], "do_not_install")

    def test_registry_ed25519_signature_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plugin_dir = write_trust_plugin(root)
            digest = compute_plugin_source_digest(plugin_dir)
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            signature = private_key.sign(
                plugin_registry_signature_payload("trust-plugin", "0.1.0", digest or "")
            )
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "apiVersion": "0.1",
                        "trustedKeys": [
                            {
                                "id": "test-maintainer-key",
                                "type": "ed25519",
                                "publicKey": base64.b64encode(public_key).decode("ascii"),
                            }
                        ],
                        "plugins": [
                            {
                                "id": "trust-plugin",
                                "path": "trust-plugin",
                                "sourceDigest": digest,
                                "signature": {
                                    "type": "ed25519",
                                    "keyId": "test-maintainer-key",
                                    "value": base64.b64encode(signature).decode("ascii"),
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            status = PluginRegistry([root]).preview_local(plugin_dir)
            trust = status.trust.public_dict() if status.trust else {}

            self.assertEqual(trust["registry_status"], "digest_verified")
            self.assertEqual(trust["signature_status"], "registry_signature_verified")
            self.assertNotIn("cryptographically verified", " ".join(trust["warnings"]))

    def test_registry_review_reports_updates_without_downloading_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plugin_dir = write_trust_plugin(root)
            digest = compute_plugin_source_digest(plugin_dir)
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "plugin-registry-v1",
                        "trustedKeys": [],
                        "plugins": [
                            {
                                "id": "trust-plugin",
                                "name": "Trust Plugin",
                                "version": "0.2.0",
                                "path": "trust-plugin",
                                "sourceDigest": digest,
                                "review": {"status": "community_reviewed"},
                            },
                            {
                                "id": "remote-only-plugin",
                                "name": "Remote Only Plugin",
                                "version": "0.1.0",
                                "path": "remote-only-plugin",
                                "sourceDigest": "sha256:" + "1" * 64,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            review = PluginRegistry([root]).registry_review().public_dict()
            items = {item["plugin_id"]: item for item in review["items"]}

            self.assertEqual(review["schema_version"], "plugin-registry-review-v1")
            self.assertFalse(review["remote_code_downloads_allowed"])
            self.assertFalse(review["entrypoints_executed"])
            self.assertEqual(items["trust-plugin"]["update_status"], "update_available")
            self.assertEqual(items["trust-plugin"]["action"], "confirm_update_review")
            self.assertEqual(items["remote-only-plugin"]["update_status"], "not_installed")
            self.assertEqual(items["remote-only-plugin"]["action"], "manual_review_required")
            self.assertGreaterEqual(review["review_required_count"], 1)
            self.assertEqual(review["update_available_count"], 1)

    def test_bundled_importer_plugins_are_registry_verified(self) -> None:
        review = PluginRegistry([ROOT.parents[1] / "plugins"]).registry_review().public_dict()
        items = {item["plugin_id"]: item for item in review["items"]}

        self.assertIn("example-web-importer", items)
        self.assertIn("example-note-importer", items)
        self.assertEqual(items["example-web-importer"]["registry_status"], "digest_verified")
        self.assertEqual(items["example-note-importer"]["registry_status"], "digest_verified")
        self.assertEqual(items["example-web-importer"]["review_status"], "maintainer_reviewed")
        self.assertEqual(items["example-note-importer"]["review_status"], "maintainer_reviewed")
        self.assertEqual(items["example-web-importer"]["action"], "ready")
        self.assertEqual(items["example-note-importer"]["action"], "ready")

    def test_policy_is_local_first(self) -> None:
        policy = plugin_trust_policy()

        self.assertTrue(policy["local_first"])
        self.assertFalse(policy["remote_code_downloads_allowed"])
        self.assertFalse(policy["raw_secrets_allowed"])
        self.assertEqual(policy["registry_signature"]["supported_type"], "ed25519")
        self.assertEqual(policy["default_install_action"], "quarantine")
        self.assertIn("quarantined", policy["lifecycle_statuses"])
        self.assertTrue(policy["quarantine"]["requires_explicit_approval_for_install"])


if __name__ == "__main__":
    unittest.main()
