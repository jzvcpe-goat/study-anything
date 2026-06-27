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
VERIFIER = REPO / "scripts" / "verify_platform_operator_drill.py"

if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_platform_operator_drill",
    VERIFIER,
)
assert VERIFIER_SPEC is not None and VERIFIER_SPEC.loader is not None
verifier = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(verifier)


class PlatformOperatorDrillTests(unittest.TestCase):
    def test_verifier_failure_formatter_is_actionable_and_redacted(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        temp_path = "/private/" + "tmp/study-anything/operator-drill.json"
        message = verifier.format_cli_failure(
            RuntimeError(
                f"operator drill stale at {temp_path} "
                f"with Authorization: Bearer {secret}"
            )
        )

        self.assertIn("verify_platform_operator_drill failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("generate_platform_adoption_pack.py", message)
        self.assertIn("verify_platform_operator_drill.py --write", message)
        self.assertIn("verify_platform_operator_drill.py --check", message)
        self.assertIn("verify_ecosystem_submission_pack.py", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/" + "tmp", message)
        self.assertNotIn(secret, message)

    def test_operator_drill_transcript_is_current(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(VERIFIER),
                "--check",
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_operator_drill_validates_extracted_platform_directory(self) -> None:
        archive_path = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
        with tempfile.TemporaryDirectory(prefix="study-anything-operator-drill-test-") as tmp:
            import zipfile

            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(tmp)
            pack_root = Path(tmp) / "study-anything-platform-adoption-pack"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER),
                    "--pack-root",
                    str(pack_root),
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "study-anything-operator-drill-v1")
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["pack"]["no_frontend_required"])
        self.assertFalse(payload["pack"]["real_model_keys_stored_by_study_anything"])
        self.assertIn("kimi", payload["platforms"])
        self.assertIn("codex", payload["platforms"])
        self.assertIn("workbuddy", payload["platforms"])
        self.assertEqual(payload["handoff_contract"]["ecosystem_submission_schema"], "ecosystem-submission-v1")
        self.assertEqual(
            payload["handoff_contract"]["ecosystem_submission_verification_schema"],
            "ecosystem-submission-verification-v1",
        )
        self.assertEqual(
            payload["handoff_contract"]["platform_manual_submission_rehearsal_schema"],
            "platform-manual-submission-rehearsal-v1",
        )
        self.assertEqual(
            payload["handoff_contract"]["first_lesson_authoring_kit_schema"],
            "first-run-lesson-authoring-kit-v1",
        )
        self.assertEqual(
            payload["handoff_contract"]["learning_enrichment_bridge_schema"],
            "learning-enrichment-bridge-verification-v1",
        )
        self.assertEqual(
            payload["handoff_contract"]["agent_eval_marketplace_enforcement_schema"],
            "agent-eval-marketplace-enforcement-v1",
        )
        self.assertEqual(
            payload["handoff_contract"]["platform_adoption_feedback_diagnostics_schema"],
            "platform-adoption-feedback-diagnostics-v1",
        )
        self.assertEqual(
            payload["handoff_contract"]["platform_feedback_package_schema"],
            "platform-feedback-package-v1",
        )
        serialized = json.dumps(payload)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("MOONSHOT_API_KEY", serialized)


if __name__ == "__main__":
    unittest.main()
