from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
BOOTSTRAP = REPO / "scripts" / "bootstrap_from_release.py"
GENERATOR = REPO / "scripts" / "generate_release_asset_bootstrap.py"
REPORT = REPO / "platform" / "generated" / "study-anything-release-asset-bootstrap.json"
MARKDOWN = REPO / "platform" / "generated" / "study-anything-release-asset-bootstrap.md"
ARCHIVE = REPO / "platform" / "generated" / "study-anything-release-asset-bootstrap.zip"
CHECKSUM = REPO / "platform" / "generated" / "study-anything-release-asset-bootstrap.sha256"

FORBIDDEN_MARKERS = (
    "sk-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private answer:",
    "Private source text:",
    "learner_answer=",
    "raw_source_text=",
    "AGENT_ENDPOINT=http",
    "/Users/",
)


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )


def json_from_stdout(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.strip().splitlines()):
        if line.strip().startswith("{"):
            payload = json.loads(line)
            if isinstance(payload, dict):
                return payload
    raise AssertionError(f"No JSON object found in stdout: {stdout}")


class ReleaseAssetBootstrapTests(unittest.TestCase):
    def test_generator_check_passes(self) -> None:
        completed = run_script(GENERATOR, "--check")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("release-asset bootstrap evidence assets are up to date", completed.stdout)

    def test_offline_bootstrap_transcript_passes(self) -> None:
        completed = run_script(
            BOOTSTRAP,
            "--fixture",
            "fixtures/release-asset-adoption/asset-only-pass.json",
            "--asset-dir",
            "platform/generated",
            "--runtime",
            "metadata-only",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)

        self.assertEqual(payload["schema_version"], "release-asset-bootstrap-transcript-v1")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["classification"], "release_asset_bootstrap_ready")
        self.assertEqual(payload["adoption_pack"]["schema_version"], "study-anything-platform-adoption-pack-v1")
        self.assertEqual(payload["runtime"]["proof_classification"], "release_asset_adoption_ready")
        self.assertEqual(payload["release_assets"]["asset_count"], 5)
        self.assertEqual(payload["platform_import_preflight"]["status"], "ready")
        self.assertIn("kimi", payload["platform_import_preflight"]["platforms"])
        self.assertIn("codex", payload["platform_import_preflight"]["platforms"])
        self.assertIn("workbuddy", payload["platform_import_preflight"]["platforms"])
        self.assertFalse(payload["privacy"]["real_model_keys_included"])

        serialized = json.dumps(payload)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def test_expected_failure_fixture_reports_classification(self) -> None:
        completed = run_script(
            BOOTSTRAP,
            "--fixture",
            "fixtures/release-asset-adoption/asset-missing.json",
            "--expect-failure",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["schema_version"], "release-asset-bootstrap-transcript-v1")
        self.assertEqual(payload["status"], "expected_failure")
        self.assertEqual(payload["classification"], "release_asset_missing")
        self.assertIn("release_asset_missing", payload["recovery_plan"])

    def test_report_markdown_and_checksum_are_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        markdown = MARKDOWN.read_text(encoding="utf-8")
        checksum = CHECKSUM.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "release-asset-bootstrap-v1")
        self.assertEqual(report["version"], "v0.3.25-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["schemas"]["transcript"], "release-asset-bootstrap-transcript-v1")
        self.assertIn("release_asset_bootstrap_ready", {item["classification"] for item in report["classification_matrix"]})
        self.assertRegex(report["archive"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertIn(report["archive"]["sha256"], checksum)
        self.assertTrue(ARCHIVE.is_file())
        self.assertIn("release-asset-bootstrap-v1", markdown)

        serialized = json.dumps(report) + markdown
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)
        for key, value in report["privacy_assertions"].items():
            self.assertIs(value, False, key)


if __name__ == "__main__":
    unittest.main()
