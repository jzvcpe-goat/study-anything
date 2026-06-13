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
DIAGNOSTICS_SCRIPT = REPO / "scripts" / "verify_platform_adoption_feedback_diagnostics.py"
FEEDBACK_SCRIPT = REPO / "scripts" / "generate_platform_feedback_package.py"
PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
FEEDBACK_MANIFEST = REPO / "platform" / "generated" / "study-anything-platform-feedback-package.json"
FEEDBACK_ARCHIVE = REPO / "platform" / "generated" / "study-anything-platform-feedback-package.zip"


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )


class PlatformAdoptionFeedbackDiagnosticsTests(unittest.TestCase):
    def test_source_tree_report_covers_import_diagnostics_and_feedback_privacy(self) -> None:
        completed = run_script(DIAGNOSTICS_SCRIPT)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(
            report["schema_version"],
            "platform-adoption-feedback-diagnostics-v1",
        )
        self.assertEqual(report["version"], "v0.3.17-alpha")
        self.assertEqual(report["status"], "pass")
        categories = set(report["diagnostic_contract"]["diagnostic_categories"])
        self.assertIn("openapi_import_missing_operation", categories)
        self.assertIn("agent_endpoint_unreachable", categories)
        self.assertIn("version_drift", categories)
        self.assertTrue(report["feedback_package"]["included"])
        self.assertTrue(report["adoption_pack"]["included"])
        privacy = report["privacy_assertions"]
        self.assertFalse(privacy["automatic_feedback_upload"])
        self.assertFalse(privacy["raw_source_text_in_feedback"])
        self.assertFalse(privacy["learner_answers_in_feedback"])
        self.assertFalse(privacy["agent_prompts_in_feedback"])
        self.assertTrue(privacy["feedback_package_is_redacted"])
        serialized = json.dumps(report)
        self.assertNotIn("OPENAI_API_KEY=", serialized)
        self.assertNotIn("Private answer:", serialized)
        self.assertNotIn("AGENT_ENDPOINT=http", serialized)

    def test_report_and_feedback_package_are_current(self) -> None:
        diagnostics = run_script(DIAGNOSTICS_SCRIPT, "--check")
        feedback = run_script(FEEDBACK_SCRIPT, "--check")

        self.assertEqual(diagnostics.returncode, 0, diagnostics.stderr)
        self.assertEqual(feedback.returncode, 0, feedback.stderr)

    def test_feedback_package_manifest_and_archive_are_redacted(self) -> None:
        payload = json.loads(FEEDBACK_MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], "platform-feedback-package-v1")
        self.assertEqual(payload["version"], "v0.3.17-alpha")
        self.assertTrue(payload["privacy"]["redacted"])
        self.assertFalse(payload["privacy"]["automatic_upload"])
        self.assertFalse(payload["privacy"]["raw_source_text_included"])
        self.assertFalse(payload["privacy"]["learner_answers_included"])
        self.assertFalse(payload["privacy"]["agent_prompts_included"])
        with zipfile.ZipFile(FEEDBACK_ARCHIVE) as archive:
            names = set(archive.namelist())
        self.assertIn("study-anything-platform-feedback-package/manifest.json", names)
        self.assertIn(
            "study-anything-platform-feedback-package/diagnostics-summary.json",
            names,
        )
        self.assertIn("study-anything-platform-feedback-package/redacted-log-sample.txt", names)

    def test_pack_report_validates_feedback_assets(self) -> None:
        completed = run_script(DIAGNOSTICS_SCRIPT, "--pack", str(PACK))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["feedback_package"]["included"])
        self.assertTrue(report["adoption_pack"]["included"])
        self.assertEqual(report["feedback_package"]["version"], "v0.3.17-alpha")

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            completed = run_script(DIAGNOSTICS_SCRIPT, "--pack-root", str(root))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Required platform adoption diagnostics asset is missing", completed.stderr)


if __name__ == "__main__":
    unittest.main()
