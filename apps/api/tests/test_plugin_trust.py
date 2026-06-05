from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.plugin_trust import (
    assess_plugin_trust,
    compute_plugin_source_digest,
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

    def test_policy_is_local_first(self) -> None:
        policy = plugin_trust_policy()

        self.assertTrue(policy["local_first"])
        self.assertFalse(policy["remote_code_downloads_allowed"])
        self.assertFalse(policy["raw_secrets_allowed"])


if __name__ == "__main__":
    unittest.main()
