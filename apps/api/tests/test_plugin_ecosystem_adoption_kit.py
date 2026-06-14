from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = ROOT.parents[1]
SCRIPT = REPO / "scripts" / "verify_plugin_ecosystem_adoption_kit.py"
PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


class PluginEcosystemAdoptionKitTests(unittest.TestCase):
    def test_source_tree_report_lists_bundled_plugins_and_trust_boundary(self) -> None:
        completed = run_script()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "plugin-ecosystem-adoption-kit-v1")
        self.assertEqual(report["version"], "v0.3.23-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["plugin_registry"]["digest_verified_count"], 5)
        self.assertFalse(report["trust_policy"]["entrypoints_executed_during_preview"])
        self.assertFalse(report["trust_policy"]["automatic_remote_plugin_downloads_enabled"])
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        plugin_ids = {item["plugin_id"] for item in report["bundled_plugins"]}
        self.assertEqual(
            plugin_ids,
            {
                "example-note-importer",
                "example-web-importer",
                "example-enrichment-importer",
                "example-exporter",
                "example-agent-provider",
            },
        )

    def test_pack_report_validates_copy_ready_plugin_assets(self) -> None:
        completed = run_script("--pack", str(PACK))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "plugin-ecosystem-adoption-kit-v1")
        self.assertEqual(report["submission"]["plugin_assets_declared"], 17)
        self.assertEqual(report["plugin_registry"]["digest_verified_count"], 5)

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "platform").mkdir()
            completed = run_script("--pack-root", str(root))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Required plugin ecosystem asset is missing", completed.stderr)


if __name__ == "__main__":
    unittest.main()
