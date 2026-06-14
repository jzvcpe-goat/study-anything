from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_adopter_evidence_archive.py"
VERIFIER = REPO / "scripts" / "verify_adopter_evidence_archive.py"
REPORT = REPO / "platform" / "generated" / "study-anything-adopter-evidence-archive.json"
MARKDOWN = REPO / "platform" / "generated" / "study-anything-adopter-evidence-archive.md"
ARCHIVE = REPO / "platform" / "generated" / "study-anything-adopter-evidence-archive.zip"
CHECKSUM = REPO / "platform" / "generated" / "study-anything-adopter-evidence-archive.sha256"
FIXTURES = REPO / "fixtures" / "adopter-evidence-archive"
ADOPTION_PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

FIXTURE_IDS = {
    "successful-release",
    "local-ghcr-pull-timeout",
    "needs-repro-issue",
    "release-blocker",
    "platform-blocked",
    "resolved-support-case",
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
    start = stdout.find("{")
    if start == -1:
        raise AssertionError(f"No JSON object found in stdout: {stdout}")
    payload = json.loads(stdout[start:])
    if not isinstance(payload, dict):
        raise AssertionError(f"JSON object expected in stdout: {stdout}")
    return payload


class AdopterEvidenceArchiveTests(unittest.TestCase):
    def test_generator_and_verifier_checks_pass(self) -> None:
        generated = run_script(GENERATOR, "--check")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("adopter evidence archive assets are up to date", generated.stdout)

        verified = run_script(VERIFIER, "--check")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        payload = json_from_stdout(verified.stdout)
        self.assertEqual(payload["schema_version"], "adopter-evidence-archive-v1")
        self.assertEqual(payload["status"], "pass")

    def test_archive_report_markdown_and_checksum_are_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        markdown = MARKDOWN.read_text(encoding="utf-8")
        checksum = CHECKSUM.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "adopter-evidence-archive-v1")
        self.assertEqual(report["version"], "v0.3.28-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["release_identity"]["tag"], "v0.3.28-alpha")
        self.assertEqual(
            report["source_schemas"]["public_support_status"]["schema_version"],
            "public-support-status-v1",
        )
        self.assertEqual(
            report["source_schemas"]["platform_adoption_pack"]["schema_version"],
            "study-anything-platform-adoption-pack-v1",
        )
        self.assertEqual(
            report["source_schemas"]["release_asset_adoption"]["schema_version"],
            "release-asset-adoption-v1",
        )
        self.assertNotIn("ref", report["source_schemas"]["platform_adoption_pack"])
        self.assertNotIn("archive_ref", report["source_schemas"]["platform_adoption_pack"])
        self.assertIn(
            "verify_external_adoption.py --pack",
            report["source_schemas"]["platform_adoption_pack"]["verification_command"],
        )
        public_asset_paths = {item["path"] for item in report["public_asset_refs"]}
        self.assertNotIn(
            "platform/generated/study-anything-platform-adoption-pack.zip",
            public_asset_paths,
        )
        self.assertNotIn(
            "platform/generated/study-anything-platform-adoption-pack.json",
            public_asset_paths,
        )
        self.assertNotIn("platform/generated/study-anything-platform-bundle.json", public_asset_paths)
        self.assertEqual({item["fixture_id"] for item in report["fixture_refs"]}, FIXTURE_IDS)
        self.assertRegex(report["archive"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertIn(report["archive"]["sha256"], checksum)
        self.assertTrue(ARCHIVE.is_file())
        self.assertIn("adopter-evidence-archive-v1", markdown)
        self.assertIn("Fixture Hashes", markdown)

        serialized = json.dumps(report) + markdown
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)
        for key, value in report["privacy_assertions"].items():
            self.assertIs(value, False, key)

    def test_fixtures_map_public_support_states_without_private_payloads(self) -> None:
        fixture_paths = sorted(FIXTURES.glob("*.json"))
        self.assertEqual({path.stem for path in fixture_paths}, FIXTURE_IDS)
        for path in fixture_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "adopter-evidence-fixture-v1")
            self.assertEqual(payload["version"], "v0.3.28-alpha")
            self.assertEqual(payload["fixture_id"], path.stem)
            self.assertEqual(
                payload["evidence_mapping"]["linked_archive_schema"],
                "adopter-evidence-archive-v1",
            )
            self.assertTrue(payload["evidence_mapping"]["required_public_command"])
            for key, value in payload["privacy"].items():
                self.assertIs(value, False, key)
            serialized = json.dumps(payload)
            for marker in FORBIDDEN_MARKERS:
                self.assertNotIn(marker, serialized)

    def test_pack_verifier_accepts_current_adoption_pack(self) -> None:
        completed = run_script(VERIFIER, "--pack", str(ADOPTION_PACK))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "adopter-evidence-archive-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["adopter_evidence_archive"]["fixture_count"], 6)

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_root = Path(tmp_dir) / "missing-pack-root"
            completed = run_script(VERIFIER, "--pack-root", str(missing_root))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Pack root does not exist", completed.stderr)


if __name__ == "__main__":
    unittest.main()
