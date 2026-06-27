from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = ROOT.parents[1]
SCRIPT = REPO / "scripts" / "verify_learning_enrichment_bridge.py"
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


class LearningEnrichmentBridgeTests(unittest.TestCase):
    def test_source_tree_report_covers_operator_bridge(self) -> None:
        completed = run_script()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "learning-enrichment-bridge-verification-v1")
        self.assertEqual(report["version"], "v0.3.31-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            set(report["context_contract"]["source_types"]),
            {"app_context", "document", "markdown_note", "obsidian_note", "video_slice", "web"},
        )
        self.assertFalse(report["context_contract"]["public_dict_includes_text"])
        html = report["exports"]["html_artifact"]
        self.assertEqual(html["article_schema"], "learning-enrichment-artifact-v1")
        self.assertFalse(html["contains_script_tag"])
        self.assertIn("Source Map", html["headings"])
        self.assertEqual(report["exports"]["notebooklm_bridge"]["manual_steps"], 4)
        self.assertFalse(report["exports"]["notebooklm_bridge"]["official_notebooklm_api_required"])
        self.assertFalse(report["privacy_assertions"]["learner_answers_in_strict_handoff"])
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])

    def test_report_is_current_after_pack_generation(self) -> None:
        completed = run_script("--check")

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_pack_report_validates_copy_ready_bridge_assets(self) -> None:
        completed = run_script("--pack", str(PACK))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["adoption_pack"]["included"])
        self.assertEqual(report["adoption_pack"]["version"], "v0.3.31-alpha")

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            completed = run_script("--pack-root", str(root))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Required bridge asset is missing", completed.stderr)

    def test_extracted_pack_contains_bridge_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="study-anything-bridge-pack-test-") as tmp:
            with zipfile.ZipFile(PACK) as archive:
                archive.extractall(tmp)
            pack_root = Path(tmp) / "study-anything-platform-adoption-pack"
            manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))

        paths = {item["path"] for item in manifest["files"]}
        self.assertIn("scripts/verify_learning_enrichment_bridge.py", paths)
        self.assertIn("platform/generated/study-anything-learning-enrichment-bridge.json", paths)
        self.assertIn(
            "learning-enrichment-bridge-verification-v1",
            manifest["acceptance"]["must_verify"],
        )


if __name__ == "__main__":
    unittest.main()
