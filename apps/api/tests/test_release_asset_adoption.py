from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_release_asset_adoption.py"
VERIFIER = REPO / "scripts" / "verify_release_asset_adoption.py"
REPORT = REPO / "platform" / "generated" / "study-anything-release-asset-adoption.json"
MARKDOWN = REPO / "platform" / "generated" / "study-anything-release-asset-adoption.md"
ARCHIVE = REPO / "platform" / "generated" / "study-anything-release-asset-adoption.zip"
CHECKSUM = REPO / "platform" / "generated" / "study-anything-release-asset-adoption.sha256"
FIXTURES = REPO / "fixtures" / "release-asset-adoption"

FIXTURE_IDS = {
    "asset-only-pass",
    "asset-missing",
    "digest-mismatch",
    "pack-corrupted",
    "published-evidence-missing",
    "network-unavailable",
}
CLASSIFICATIONS = {
    "release_asset_adoption_ready",
    "release_asset_missing",
    "release_asset_digest_mismatch",
    "release_asset_pack_corrupted",
    "release_asset_published_evidence_missing",
    "release_asset_network_unavailable",
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


class ReleaseAssetAdoptionTests(unittest.TestCase):
    def test_generator_check_passes(self) -> None:
        completed = run_script(GENERATOR, "--check")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("release-asset adoption evidence assets are up to date", completed.stdout)

    def test_offline_asset_replay_passes(self) -> None:
        completed = run_script(
            VERIFIER,
            "--fixture",
            "fixtures/release-asset-adoption/asset-only-pass.json",
            "--asset-dir",
            "platform/generated",
            "--runtime",
            "metadata-only",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["schema_version"], "release-asset-adoption-proof-v1")
        self.assertEqual(payload["classification"], "release_asset_adoption_ready")
        self.assertEqual(payload["pack"]["schema_version"], "study-anything-platform-adoption-pack-v1")
        self.assertEqual(
            payload["verifiers"]["published_image_evidence"]["schema_version"],
            "published-image-evidence-v1",
        )

    def test_report_markdown_and_checksum_are_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        markdown = MARKDOWN.read_text(encoding="utf-8")
        checksum = CHECKSUM.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "release-asset-adoption-v1")
        self.assertEqual(report["version"], "v0.3.27-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["verification"]["proof_schema"], "release-asset-adoption-proof-v1")
        self.assertEqual(
            {item["classification"] for item in report["classification_matrix"]},
            CLASSIFICATIONS,
        )
        self.assertEqual({item["fixture_id"] for item in report["fixture_refs"]}, FIXTURE_IDS)
        self.assertRegex(report["archive"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertIn(report["archive"]["sha256"], checksum)
        self.assertTrue(ARCHIVE.is_file())
        self.assertIn("release-asset-adoption-v1", markdown)
        self.assertIn("Classification Matrix", markdown)

        serialized = json.dumps(report) + markdown
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)
        for key, value in report["privacy_assertions"].items():
            self.assertIs(value, False, key)

    def test_fixtures_cover_release_asset_classifications(self) -> None:
        fixture_paths = sorted(FIXTURES.glob("*.json"))
        self.assertEqual({path.stem for path in fixture_paths}, FIXTURE_IDS)
        classifications: set[str] = set()
        for path in fixture_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "release-asset-adoption-fixture-v1")
            self.assertEqual(payload["version"], "v0.3.27-alpha")
            self.assertEqual(payload["fixture_id"], path.stem)
            classifications.add(payload["classification"])
            for key, value in payload["privacy"].items():
                self.assertIs(value, False, key)
        self.assertEqual(classifications, CLASSIFICATIONS)

    def test_expected_failure_fixture_reports_classification(self) -> None:
        completed = run_script(
            VERIFIER,
            "--fixture",
            "fixtures/release-asset-adoption/asset-missing.json",
            "--expect-failure",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["status"], "expected_failure")
        self.assertEqual(payload["classification"], "release_asset_missing")

    def test_corrupted_asset_dir_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            asset_dir = Path(tmp_dir)
            for name in (
                "study-anything-platform-adoption-pack.zip",
                "study-anything-published-image-evidence.zip",
                "study-anything-adopter-evidence-archive.zip",
                "study-anything-platform-feedback-package.zip",
                "study-anything-release-asset-bootstrap.zip",
                "study-anything-platform-agent-replay.zip",
            ):
                (asset_dir / name).write_bytes(b"not a zip archive")
            completed = run_script(
                VERIFIER,
                "--fixture",
                "fixtures/release-asset-adoption/asset-only-pass.json",
                "--asset-dir",
                str(asset_dir),
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("verify_release_asset_adoption failed:", completed.stderr)
        self.assertIn("Release adoption pack zip is corrupted", completed.stderr)


if __name__ == "__main__":
    unittest.main()
