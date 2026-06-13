from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from _path import ROOT  # noqa: F401


class PlatformManualSubmissionRehearsalTests(unittest.TestCase):
    def test_manual_submission_rehearsal_report_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "verify_platform_manual_submission_rehearsal.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_manual_submission_rehearsal_report_privacy_and_schema(self) -> None:
        root = Path(__file__).resolve().parents[3]
        report = json.loads(
            (
                root
                / "platform"
                / "generated"
                / "study-anything-platform-manual-submission-rehearsal.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "platform-manual-submission-rehearsal-v1")
        self.assertEqual(report["version"], "v0.3.13-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertGreaterEqual(len(report["operator_steps"]), 7)
        self.assertEqual(report["time_budget"]["target_minutes"], 30)
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        self.assertFalse(report["privacy_assertions"]["raw_source_text_returned"])
        self.assertFalse(report["privacy_assertions"]["learner_answers_returned"])
        self.assertFalse(report["privacy_assertions"]["agent_endpoint_secrets_returned"])
        self.assertFalse(report["privacy_assertions"]["real_model_keys_stored_by_study_anything"])
        self.assertIn("tool_import_failed", report["failure_remediation"])
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("Private answer:", serialized)
        self.assertNotIn("http://127.0.0.1:8787", serialized)

    def test_manual_submission_rehearsal_validates_extracted_pack(self) -> None:
        root = Path(__file__).resolve().parents[3]
        archive_path = root / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
        with tempfile.TemporaryDirectory(prefix="study-anything-manual-rehearsal-test-") as tmp:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tmp)
            pack_root = Path(tmp) / "study-anything-platform-adoption-pack"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "verify_platform_manual_submission_rehearsal.py"),
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
        self.assertEqual(payload["schema_version"], "platform-manual-submission-rehearsal-v1")
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()
