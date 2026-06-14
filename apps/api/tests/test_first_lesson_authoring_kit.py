from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from _path import ROOT  # noqa: F401


class FirstLessonAuthoringKitTests(unittest.TestCase):
    def test_first_lesson_authoring_kit_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "verify_first_lesson_authoring_kit.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_first_lesson_authoring_kit_schema_prompts_and_privacy(self) -> None:
        root = Path(__file__).resolve().parents[3]
        report = json.loads(
            (
                root / "platform" / "generated" / "study-anything-first-lesson-authoring-kit.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(report["schema_version"], "first-run-lesson-authoring-kit-v1")
        self.assertEqual(report["version"], "v0.3.28-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(set(report["copyable_prompts"]), {"en", "zh"})
        self.assertIn("第一课", report["copyable_prompts"]["zh"]["title"])
        self.assertIn("first lesson", report["copyable_prompts"]["en"]["title"].lower())
        self.assertEqual(report["context_package_template"]["schema_version"], "learning-context-package-v1")
        self.assertGreaterEqual(len(report["tool_call_sequence"]), 10)
        self.assertIn("study_anything_validate_context_package", [step["tool"] for step in report["tool_call_sequence"]])
        self.assertIn("learning-package-v1", report["expected_outputs"])
        self.assertIn("platform_cannot_call_localhost", report["failure_remediation"])
        self.assertEqual(report["time_budget"]["target_minutes"], 20)
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])
        self.assertFalse(report["privacy_assertions"]["copyable_prompts_include_real_model_keys"])
        self.assertFalse(report["privacy_assertions"]["context_template_contains_raw_source"])
        self.assertFalse(report["privacy_assertions"]["agent_endpoint_secrets_returned"])
        serialized = json.dumps(report)
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("OPENAI_API_KEY=", serialized)
        self.assertNotIn("MOONSHOT_API_KEY=", serialized)
        self.assertNotIn("Private answer:", serialized)
        self.assertNotIn("http://127.0.0.1:8787", serialized)

    def test_first_lesson_authoring_kit_validates_extracted_pack(self) -> None:
        root = Path(__file__).resolve().parents[3]
        archive_path = root / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
        with tempfile.TemporaryDirectory(prefix="study-anything-first-lesson-kit-test-") as tmp:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tmp)
            pack_root = Path(tmp) / "study-anything-platform-adoption-pack"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "verify_first_lesson_authoring_kit.py"),
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
        self.assertEqual(payload["schema_version"], "first-run-lesson-authoring-kit-v1")
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()
