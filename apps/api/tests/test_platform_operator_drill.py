from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


class PlatformOperatorDrillTests(unittest.TestCase):
    def test_operator_drill_transcript_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "verify_platform_operator_drill.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_operator_drill_validates_extracted_platform_directory(self) -> None:
        root = Path(__file__).resolve().parents[3]
        archive_path = root / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
        with tempfile.TemporaryDirectory(prefix="study-anything-operator-drill-test-") as tmp:
            import zipfile

            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tmp)
            pack_root = Path(tmp) / "study-anything-platform-adoption-pack"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "verify_platform_operator_drill.py"),
                    "--pack-root",
                    str(pack_root),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "study-anything-operator-drill-v1")
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["pack"]["no_frontend_required"])
        self.assertFalse(payload["pack"]["real_model_keys_stored_by_study_anything"])
        self.assertIn("kimi", payload["platforms"])
        self.assertIn("codex", payload["platforms"])
        self.assertIn("workbuddy", payload["platforms"])
        self.assertEqual(payload["handoff_contract"]["ecosystem_submission_schema"], "ecosystem-submission-v1")
        self.assertEqual(
            payload["handoff_contract"]["ecosystem_submission_verification_schema"],
            "ecosystem-submission-verification-v1",
        )
        self.assertEqual(
            payload["handoff_contract"]["platform_manual_submission_rehearsal_schema"],
            "platform-manual-submission-rehearsal-v1",
        )
        serialized = json.dumps(payload)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("MOONSHOT_API_KEY", serialized)


if __name__ == "__main__":
    unittest.main()
