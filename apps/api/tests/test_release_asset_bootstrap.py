from __future__ import annotations

import argparse
import importlib.util
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

if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

SPEC = importlib.util.spec_from_file_location("bootstrap_from_release", BOOTSTRAP)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)

GENERATOR_SPEC = importlib.util.spec_from_file_location("generate_release_asset_bootstrap", GENERATOR)
assert GENERATOR_SPEC is not None and GENERATOR_SPEC.loader is not None
generator = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(generator)

FORBIDDEN_MARKERS = (
    "sk-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "Private " + "answer:",
    "Private " + "source text:",
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

    def test_generator_failure_formatter_is_actionable_and_redacted(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        temp_path = "/private/" + "tmp/study-anything/bootstrap.json"
        message = generator.format_cli_failure(
            RuntimeError(
                f"stale asset at {temp_path} "
                f"with Authorization: Bearer {secret}"
            )
        )

        self.assertIn("generate_release_asset_bootstrap failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("generate_release_asset_bootstrap.py --check", message)
        self.assertIn("verify_release_asset_adoption.py --fixture", message)
        self.assertIn("--runtime metadata-only", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/" + "tmp", message)
        self.assertNotIn(secret, message)

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
        self.assertEqual(payload["release_assets"]["asset_count"], 6)
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

    def test_failure_transcript_redacts_secret_diagnostics(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        temp_path = "/private/" + "tmp/study-anything/bootstrap.log"
        args = argparse.Namespace(
            tag="v0.3.29-alpha",
            repo="jzvcpe-goat/study-anything",
        )

        payload = bootstrap.build_failure_transcript(
            args=args,
            classification="bootstrap_failed",
            diagnostic=(
                "failed with Authorization: Bearer "
                f"{secret} at http://user:secret@example.test/v1?token={secret} "
                f"from {temp_path}"
            ),
        )

        serialized = json.dumps(payload, sort_keys=True)
        self.assertIn("Authorization: Bearer <redacted>", serialized)
        self.assertIn("http://<redacted>@example.test/v1?token=<redacted>", serialized)
        self.assertIn("<temp-path>", serialized)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("user:secret", serialized)
        self.assertNotIn("/private/" + "tmp", serialized)

    def test_sanitize_error_handles_log_punctuation_after_port(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        diagnostic = bootstrap.sanitize_error(
            "Cannot reach http://user:secret@127.0.0.1:9. "
            f"Authorization: Bearer {secret}"
        )

        self.assertIn("http://<redacted>@127.0.0.1", diagnostic)
        self.assertIn("Authorization: Bearer <redacted>", diagnostic)
        self.assertNotIn("user:secret", diagnostic)
        self.assertNotIn(secret, diagnostic)

    def test_local_api_recovery_mentions_normal_terminal(self) -> None:
        completed = run_script(
            BOOTSTRAP,
            "--fixture",
            "fixtures/release-asset-adoption/asset-only-pass.json",
            "--asset-dir",
            "platform/generated",
            "--runtime",
            "skill-mode",
            "--expect-failure",
            "--timeout-seconds",
            "2",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json_from_stdout(completed.stdout)
        self.assertEqual(payload["classification"], "local_api_unavailable")
        recovery_steps = " ".join(payload["recovery_plan"]["local_api_unavailable"])
        self.assertIn("normal terminal", recovery_steps)
        self.assertIn(".venv/bin/python", recovery_steps)

    def test_report_markdown_and_checksum_are_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        markdown = MARKDOWN.read_text(encoding="utf-8")
        checksum = CHECKSUM.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "release-asset-bootstrap-v1")
        self.assertEqual(report["version"], "v0.3.29-alpha")
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
