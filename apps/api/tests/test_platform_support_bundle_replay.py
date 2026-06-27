from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_platform_support_bundle_replay.py"
VERIFIER = REPO / "scripts" / "verify_platform_support_bundle_replay.py"
REPLAY = REPO / "scripts" / "replay_support_bundle.py"
REPORT = REPO / "platform" / "generated" / "study-anything-platform-support-bundle-replay.json"
FIXTURE_DIR = REPO / "fixtures" / "platform-support-bundles"
ADOPTION_PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

sys.path.insert(0, str(REPO / "scripts"))
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "generate_platform_support_bundle_replay",
    GENERATOR,
)
assert GENERATOR_SPEC is not None and GENERATOR_SPEC.loader is not None
generator = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(generator)

FIXTURE_EXPECTATIONS = {
    "local-ghcr-pull-timeout": "local_ghcr_pull_timeout",
    "cleanroom-runtime-launch-failed": "runtime_launch_failed",
    "privacy-contract-violation": "privacy_contract_violation",
}

REQUIRED_FIELDS = {
    "release_version",
    "platform_id",
    "runtime",
    "failure_class",
    "workflow_stage",
    "command_ran",
    "diagnostic_code",
    "redacted_log_excerpt",
    "next_commands_tried",
    "recommended_next_steps",
    "replay_command",
    "redaction_flags",
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
        timeout=60,
    )


class PlatformSupportBundleReplayTests(unittest.TestCase):
    def test_generator_and_verifier_checks_pass(self) -> None:
        generated = run_script(GENERATOR, "--check")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("support bundle replay assets are up to date", generated.stdout)

        verified = run_script(VERIFIER, "--check")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        payload = json.loads(verified.stdout)
        self.assertEqual(payload["schema_version"], "platform-support-bundle-replay-evidence-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["support_bundle_replay"]["fixture_count"], 3)
        self.assertTrue(payload["support_bundle_replay"]["blocked_privacy_fixture"])

    def test_generator_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = generator.format_cli_failure(
            RuntimeError(
                "stale support bundle at /private/tmp/study-anything/support.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("generate_platform_support_bundle_replay failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("generate_platform_support_bundle_replay.py --check", message)
        self.assertIn("verify_platform_support_bundle_replay.py --check", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)

    def test_report_and_fixtures_are_actionable(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], "platform-support-bundle-replay-evidence-v1")
        self.assertEqual(report["version"], "v0.3.29-alpha")
        self.assertEqual(report["schemas"]["support_bundle"], "platform-support-bundle-v1")
        self.assertEqual(report["schemas"]["maintainer_replay"], "platform-support-bundle-replay-v1")
        self.assertEqual(set(report["required_bundle_fields"]), REQUIRED_FIELDS)
        self.assertEqual(
            {item["fixture_id"] for item in report["fixture_refs"]},
            set(FIXTURE_EXPECTATIONS),
        )
        self.assertFalse(report["privacy_assertions"]["automatic_upload"])
        self.assertTrue(report["privacy_assertions"]["fixtures_are_mock_only"])
        serialized = json.dumps(report)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

        for fixture_id, expected in FIXTURE_EXPECTATIONS.items():
            payload = json.loads((FIXTURE_DIR / f"{fixture_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "platform-support-bundle-v1")
            self.assertEqual(payload["release_version"], "v0.3.29-alpha")
            self.assertEqual(set(payload) & REQUIRED_FIELDS, REQUIRED_FIELDS)
            self.assertTrue(payload["next_commands_tried"])
            self.assertTrue(payload["recommended_next_steps"])
            replay = run_script(
                REPLAY,
                "--bundle",
                str(FIXTURE_DIR / f"{fixture_id}.json"),
                "--expect-classification",
                expected,
            )
            if expected == "privacy_contract_violation":
                self.assertEqual(replay.returncode, 2, replay.stderr)
            else:
                self.assertEqual(replay.returncode, 0, replay.stderr)
                replay_payload = json.loads(replay.stdout)
                self.assertEqual(replay_payload["classification"], expected)
                self.assertIn("## Study Anything support bundle replay", replay_payload["issue_body"])
                replay_serialized = json.dumps(replay_payload)
                for marker in FORBIDDEN_MARKERS:
                    self.assertNotIn(marker, replay_serialized)

    def test_replay_accepts_cleanroom_report_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "cleanroom.json"
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": "release-cleanroom-bootstrap-v1",
                        "tag": "v0.3.29-alpha",
                        "platform": "kimi",
                        "status": "ok",
                        "classification": "cleanroom_bootstrap_ready",
                        "diagnostic": "Cleanroom bootloader completed.",
                        "privacy": {
                            "raw_source_text_included": False,
                            "learner_answers_included": False,
                            "agent_prompts_included": False,
                            "agent_endpoint_secrets_included": False,
                            "real_model_keys_included": False,
                            "local_absolute_paths_included": False,
                            "automatic_upload": False,
                        },
                        "release_assets": {
                            "asset_count": 6,
                            "github_digest_verified_count": 6,
                        },
                        "tool_import": {"status": "ready"},
                        "runtime": {"requested": "metadata-only"},
                        "recovery_plan": {"cleanroom_bootstrap_ready": ["No action required."]},
                    }
                ),
                encoding="utf-8",
            )
            replay = run_script(
                REPLAY,
                "--bundle",
                str(report_path),
                "--expect-classification",
                "no_action_required",
            )
        self.assertEqual(replay.returncode, 0, replay.stderr)
        payload = json.loads(replay.stdout)
        self.assertEqual(payload["schema_version"], "platform-support-bundle-replay-v1")
        self.assertEqual(payload["classification"], "no_action_required")

    def test_replay_unsupported_schema_failure_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "unsupported.json"
            report_path.write_text(
                json.dumps({"schema_version": "unexpected-report-v1"}),
                encoding="utf-8",
            )
            replay = run_script(REPLAY, "--bundle", str(report_path))

        self.assertEqual(replay.returncode, 1)
        self.assertIn("Unsupported support bundle schema", replay.stderr)
        self.assertIn("Supported inputs:", replay.stderr)
        self.assertIn("platform-support-bundle-v1", replay.stderr)
        self.assertIn("release-cleanroom-bootstrap-v1", replay.stderr)
        self.assertIn("diagnose_adoption.py", replay.stderr)
        self.assertIn("Do not paste raw source text", replay.stderr)
        self.assertNotIn("OPENAI_API_KEY", replay.stderr)

    def test_replay_missing_bundle_failure_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "missing.json"
            replay = run_script(REPLAY, "--bundle", str(missing))

        self.assertEqual(replay.returncode, 1)
        self.assertIn("replay_support_bundle failed:", replay.stderr)
        self.assertIn("Next steps:", replay.stderr)
        self.assertIn("diagnose_adoption.py", replay.stderr)
        self.assertIn("<temp-path>", replay.stderr)
        self.assertNotIn(tmp_dir, replay.stderr)

    def test_verifier_missing_pack_root_failure_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "missing-pack-root"
            verified = run_script(VERIFIER, "--pack-root", str(missing))

        self.assertEqual(verified.returncode, 1)
        self.assertIn("verify_platform_support_bundle_replay failed:", verified.stderr)
        self.assertIn("Next steps:", verified.stderr)
        self.assertIn("generate_platform_support_bundle_replay.py", verified.stderr)
        self.assertIn("replay_support_bundle.py", verified.stderr)
        self.assertIn("diagnose_adoption.py", verified.stderr)
        self.assertIn("<temp-path>", verified.stderr)
        self.assertNotIn(tmp_dir, verified.stderr)

    def test_pack_verifier_accepts_current_adoption_pack(self) -> None:
        completed = run_script(VERIFIER, "--pack", str(ADOPTION_PACK))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "platform-support-bundle-replay-evidence-v1")
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()
