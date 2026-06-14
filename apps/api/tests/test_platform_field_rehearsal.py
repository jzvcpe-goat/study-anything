from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_platform_field_rehearsal.py"
VERIFIER = REPO / "scripts" / "verify_platform_field_rehearsal.py"
REPORT = REPO / "platform" / "generated" / "study-anything-platform-field-rehearsal.json"
FIXTURE_DIR = REPO / "fixtures" / "platform-import-failures"
ADOPTION_PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
PLATFORM_IDS = {"kimi", "codex", "workbuddy", "generic"}
QUIRK_IDS = {
    "schema_mismatch",
    "missing_local_gateway",
    "unsupported_auth_mode",
    "tool_naming_drift",
    "timeout",
    "cors_localhost",
    "package_corruption",
    "version_drift",
}
FORBIDDEN_MARKERS = (
    "sk-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "learner_answer=",
    "raw_source_text=",
    "AGENT_ENDPOINT=http",
    "http://127.0.0.1:8787",
)


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )


class PlatformFieldRehearsalTests(unittest.TestCase):
    def test_generator_and_verifier_checks_pass(self) -> None:
        generated = run_script(GENERATOR, "--check")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("generated platform field rehearsal assets are up to date", generated.stdout)

        verified = run_script(VERIFIER, "--check")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("platform field rehearsal assets are valid", verified.stdout)

    def test_report_covers_platforms_quirks_fixtures_and_privacy(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], "platform-field-adoption-rehearsal-v1")
        self.assertEqual(report["version"], "v0.3.20-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual({item["platform_id"] for item in report["platforms"]}, PLATFORM_IDS)
        self.assertEqual({item["id"] for item in report["quirks_catalog"]}, QUIRK_IDS)
        self.assertEqual(len(report["failed_import_fixtures"]), len(QUIRK_IDS))
        self.assertTrue(report["privacy_assertions"]["fixtures_are_mock_only"])
        for key, value in report["privacy_assertions"].items():
            if key != "fixtures_are_mock_only":
                self.assertIs(value, False, key)
        for platform in report["platforms"]:
            self.assertGreaterEqual(len(platform["events"]), 5)
            self.assertIn("import_asset", platform)
            self.assertIn("expected_evidence", platform)
        for quirk in report["quirks_catalog"]:
            self.assertTrue(quirk["detection_signal"])
            self.assertTrue(quirk["likely_cause"])
            self.assertTrue(quirk["next_commands"])
            self.assertTrue(quirk["safe_feedback_fields"])
        serialized = json.dumps(report)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def test_failed_import_fixtures_are_actionable_and_redacted(self) -> None:
        fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))
        self.assertEqual({path.stem for path in fixture_paths}, QUIRK_IDS)

        for path in fixture_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "platform-import-failure-fixture-v1")
            self.assertEqual(payload["version"], "v0.3.20-alpha")
            self.assertEqual(payload["failure_id"], path.stem)
            self.assertEqual(payload["status"], "mock_failure_ready")
            self.assertEqual(set(payload["platform_ids"]), PLATFORM_IDS)
            self.assertTrue(payload["diagnosis"]["detection_signal"])
            self.assertTrue(payload["diagnosis"]["likely_cause"])
            self.assertTrue(payload["diagnosis"]["next_commands"])
            self.assertTrue(payload["safe_feedback_fields"])
            self.assertTrue(payload["observed_error"]["raw_error_redacted"])
            for value in payload["privacy"].values():
                self.assertIs(value, False)
            serialized = json.dumps(payload)
            for marker in FORBIDDEN_MARKERS:
                self.assertNotIn(marker, serialized)

    def test_pack_verifier_accepts_current_adoption_pack(self) -> None:
        completed = run_script(VERIFIER, "--pack", str(ADOPTION_PACK))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "platform-field-adoption-rehearsal-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["field_rehearsal"]["platform_count"], 4)
        self.assertEqual(payload["field_rehearsal"]["quirk_count"], 8)
        self.assertEqual(payload["field_rehearsal"]["fixture_count"], 8)
        self.assertEqual(
            payload["adoption_pack"]["schema_version"],
            "study-anything-platform-adoption-pack-v1",
        )

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_root = Path(tmp_dir) / "missing-pack-root"
            completed = run_script(VERIFIER, "--pack-root", str(missing_root))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Pack root does not exist", completed.stderr)


if __name__ == "__main__":
    unittest.main()
