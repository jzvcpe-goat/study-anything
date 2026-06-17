from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
BOOTLOADER = REPO / "platform" / "bootstrap" / "study_anything_release_bootstrap.py"
GENERATOR = REPO / "scripts" / "generate_release_cleanroom_bootstrap.py"
REPORT = REPO / "platform" / "generated" / "study-anything-release-cleanroom-bootstrap.json"
MARKDOWN = REPO / "platform" / "generated" / "study-anything-release-cleanroom-bootstrap.md"
ARCHIVE = REPO / "platform" / "generated" / "study-anything-release-cleanroom-bootstrap.zip"
CHECKSUM = REPO / "platform" / "generated" / "study-anything-release-cleanroom-bootstrap.sha256"

FORBIDDEN_MARKERS = (
    "sk-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "Private platform replay source text",
    "Private platform replay learner answer",
    "AGENT_ENDPOINT=http",
    "/Users/",
)


def run_script(script: Path, *args: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def json_from_stdout(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.strip().splitlines()):
        if line.strip().startswith("{"):
            payload = json.loads(line)
            if isinstance(payload, dict):
                return payload
    raise AssertionError(f"No JSON object found in stdout: {stdout}")


class ReleaseCleanroomBootstrapTests(unittest.TestCase):
    def test_generator_check_passes(self) -> None:
        completed = run_script(GENERATOR, "--check")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("release cleanroom bootstrap assets are up to date", completed.stdout)

    def test_metadata_fixture_bootloader_passes_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            completed = run_script(
                BOOTLOADER,
                "--fixture",
                "fixtures/release-asset-adoption/asset-only-pass.json",
                "--asset-dir",
                "platform/generated",
                "--runtime",
                "metadata-only",
                "--platform",
                "kimi",
                "--output-dir",
                tmp_dir,
            )
            json_report = Path(tmp_dir) / "study-anything-cleanroom-bootstrap-report.json"
            md_report = Path(tmp_dir) / "study-anything-cleanroom-bootstrap-report.md"
            self.assertTrue(json_report.is_file())
            self.assertTrue(md_report.is_file())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["schema_version"], "release-cleanroom-bootstrap-v1")
        self.assertEqual(payload["classification"], "cleanroom_bootstrap_ready")
        self.assertEqual(payload["release_assets"]["asset_count"], 6)
        self.assertEqual(payload["tool_import"]["platforms"]["kimi"]["status"], "ready")
        self.assertFalse(payload["acceptance"]["runtime_verified"])
        self.assertIn("issue_body", payload)
        serialized = json.dumps(payload)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def test_skill_mode_fixture_bootloader_delegates_to_replay(self) -> None:
        completed = run_script(
            BOOTLOADER,
            "--fixture",
            "fixtures/release-asset-adoption/asset-only-pass.json",
            "--asset-dir",
            "platform/generated",
            "--runtime",
            "skill-mode",
            "--platform",
            "kimi",
            "--source-dir",
            ".",
            "--timeout-seconds",
            "180",
            timeout=210,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["classification"], "cleanroom_bootstrap_ready")
        self.assertTrue(payload["acceptance"]["runtime_verified"])
        self.assertEqual(payload["runtime"]["payload"]["classification"], "platform_agent_replay_ready")
        self.assertEqual(payload["runtime"]["payload"]["tool_call_count"], 9)

    def test_expected_failure_fixtures_are_redacted_and_classified(self) -> None:
        cases = [
            ("asset-missing.json", "release_asset_missing", []),
            ("digest-mismatch.json", "release_asset_digest_mismatch", ["--asset-dir", "platform/generated"]),
        ]
        for fixture_name, classification, extra_args in cases:
            with self.subTest(fixture=fixture_name):
                completed = run_script(
                    BOOTLOADER,
                    "--fixture",
                    f"fixtures/release-asset-adoption/{fixture_name}",
                    "--runtime",
                    "metadata-only",
                    "--expect-failure",
                    *extra_args,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json_from_stdout(completed.stdout)
                self.assertEqual(payload["status"], "expected_failure")
                self.assertEqual(payload["classification"], classification)
                self.assertIn(classification, payload["recovery_plan"])
                serialized = json.dumps(payload)
                for marker in FORBIDDEN_MARKERS:
                    self.assertNotIn(marker, serialized)

    def test_generated_evidence_is_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        markdown = MARKDOWN.read_text(encoding="utf-8")
        checksum = CHECKSUM.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "release-cleanroom-bootstrap-evidence-v1")
        self.assertEqual(report["version"], "v0.3.30-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["example_report"]["schema_version"], "release-cleanroom-bootstrap-v1")
        self.assertIn("cleanroom_bootstrap_ready", {item["classification"] for item in report["classification_matrix"]})
        self.assertRegex(report["archive"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertIn(report["archive"]["sha256"], checksum)
        self.assertTrue(ARCHIVE.is_file())
        self.assertIn("release-cleanroom-bootstrap-evidence-v1", markdown)

        serialized = json.dumps(report) + markdown
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)
        for key, value in report["privacy_assertions"].items():
            self.assertIs(value, False, key)


if __name__ == "__main__":
    unittest.main()
