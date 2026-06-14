from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_published_image_evidence.py"
VERIFIER = REPO / "scripts" / "verify_published_image_evidence.py"
REPORT = REPO / "platform" / "generated" / "study-anything-published-image-evidence.json"
MARKDOWN = REPO / "platform" / "generated" / "study-anything-published-image-evidence.md"
ARCHIVE = REPO / "platform" / "generated" / "study-anything-published-image-evidence.zip"
CHECKSUM = REPO / "platform" / "generated" / "study-anything-published-image-evidence.sha256"
FIXTURES = REPO / "fixtures" / "published-image-evidence"
ADOPTION_PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

FIXTURE_IDS = {
    "manifest-pass-local-pull-timeout",
    "cached-image-missing",
    "compose-up-timeout",
    "manifest-only-runtime-unverified",
    "manifest-missing-platform",
    "docker-images-failed",
    "ghcr-unavailable",
    "remote-smoke-pass",
    "remote-smoke-failed",
}
CLASSIFICATIONS = {
    "local_pull_timeout_with_valid_release_evidence",
    "cached_image_missing",
    "compose_up_timeout",
    "manifest_available_runtime_unverified",
    "published_image_platform_gap",
    "ci_image_publish_failed",
    "registry_or_network_unavailable",
    "published_image_ready",
    "published_image_runtime_failed",
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


class PublishedImageEvidenceTests(unittest.TestCase):
    def test_generator_and_verifier_checks_pass(self) -> None:
        generated = run_script(GENERATOR, "--check")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("published-image evidence assets are up to date", generated.stdout)

        verified = run_script(VERIFIER, "--check")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        payload = json_from_stdout(verified.stdout)
        self.assertEqual(payload["schema_version"], "published-image-evidence-v1")
        self.assertEqual(payload["status"], "pass")

    def test_report_markdown_and_checksum_are_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        markdown = MARKDOWN.read_text(encoding="utf-8")
        checksum = CHECKSUM.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "published-image-evidence-v1")
        self.assertEqual(report["version"], "v0.3.26-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["release_identity"]["tag"], "v0.3.26-alpha")
        self.assertEqual(
            set(report["manifest_evidence"]["required_platforms"]),
            {"linux/amd64", "linux/arm64"},
        )
        self.assertEqual(
            report["local_smoke_evidence"]["timeout_status"],
            "blocked_by_local_ghcr_pull",
        )
        self.assertEqual(
            {item["classification"] for item in report["classification_matrix"]},
            CLASSIFICATIONS,
        )
        self.assertEqual({item["fixture_id"] for item in report["fixture_refs"]}, FIXTURE_IDS)
        self.assertRegex(report["archive"]["sha256"], r"^[a-f0-9]{64}$")
        self.assertIn(report["archive"]["sha256"], checksum)
        self.assertTrue(ARCHIVE.is_file())
        self.assertIn("published-image-evidence-v1", markdown)
        self.assertIn("Classification Matrix", markdown)

        serialized = json.dumps(report) + markdown
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)
        for key, value in report["privacy_assertions"].items():
            self.assertIs(value, False, key)

    def test_fixtures_cover_release_classifications_without_private_payloads(self) -> None:
        fixture_paths = sorted(FIXTURES.glob("*.json"))
        self.assertEqual({path.stem for path in fixture_paths}, FIXTURE_IDS)
        classifications: set[str] = set()
        for path in fixture_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "published-image-evidence-fixture-v1")
            self.assertEqual(payload["version"], "v0.3.26-alpha")
            self.assertEqual(payload["fixture_id"], path.stem)
            classifications.add(payload["classification"])
            self.assertTrue(payload["operator_next_step"])
            for key, value in payload["privacy"].items():
                self.assertIs(value, False, key)
            serialized = json.dumps(payload)
            for marker in FORBIDDEN_MARKERS:
                self.assertNotIn(marker, serialized)
        self.assertEqual(classifications, CLASSIFICATIONS)

    def test_pack_verifier_accepts_current_adoption_pack(self) -> None:
        completed = run_script(VERIFIER, "--pack", str(ADOPTION_PACK))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "published-image-evidence-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["published_image_evidence"]["fixture_count"], len(FIXTURE_IDS))

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_root = Path(tmp_dir) / "missing-pack-root"
            completed = run_script(VERIFIER, "--pack-root", str(missing_root))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Pack root does not exist", completed.stderr)


if __name__ == "__main__":
    unittest.main()
