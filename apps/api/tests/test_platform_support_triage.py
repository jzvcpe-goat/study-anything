from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_platform_support_triage.py"
VERIFIER = REPO / "scripts" / "verify_platform_support_triage.py"
REPORT = REPO / "platform" / "generated" / "study-anything-platform-support-triage.json"
TICKET_DIR = REPO / "fixtures" / "platform-support-tickets"
ADOPTION_PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
SUPPORT_CATEGORY_IDS = {
    "platform_import_failure",
    "local_gateway_failure",
    "published_image_pull_failure",
    "agent_eval_evidence_failure",
    "docs_confusion",
}
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
REQUIRED_SUPPORT_FIELDS = {
    "release_version",
    "platform_id",
    "command_ran",
    "diagnostic_code",
    "fixture_id",
    "redacted_log_excerpt",
    "next_commands_tried",
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


class PlatformSupportTriageTests(unittest.TestCase):
    def test_generator_and_verifier_checks_pass(self) -> None:
        generated = run_script(GENERATOR, "--check")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("generated platform support triage assets are up to date", generated.stdout)

        verified = run_script(VERIFIER, "--check")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("platform support triage assets are valid", verified.stdout)

    def test_report_covers_templates_tickets_playbook_and_privacy(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], "platform-support-triage-v1")
        self.assertEqual(report["version"], "v0.3.27-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            {item["category_id"] for item in report["issue_templates"]},
            SUPPORT_CATEGORY_IDS,
        )
        self.assertEqual(
            {item["ticket_id"] for item in report["support_ticket_fixtures"]},
            SUPPORT_CATEGORY_IDS,
        )
        self.assertEqual(
            set(report["support_bundle_contract"]["required_fields"]),
            REQUIRED_SUPPORT_FIELDS,
        )
        self.assertFalse(report["support_bundle_contract"]["automatic_upload"])
        self.assertTrue(report["support_bundle_contract"]["safe_handoff_only"])
        self.assertEqual({item["failure_id"] for item in report["maintainer_playbook"]}, QUIRK_IDS)
        for item in report["maintainer_playbook"]:
            self.assertTrue(item["first_response"])
            self.assertTrue(item["reproduction_steps"])
            self.assertTrue(item["close_when"])
            self.assertTrue(item["escalate_when"])
        self.assertTrue(report["privacy_assertions"]["fixtures_are_mock_only"])
        for key, value in report["privacy_assertions"].items():
            if key != "fixtures_are_mock_only":
                self.assertIs(value, False, key)
        serialized = json.dumps(report)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def test_ticket_fixtures_are_actionable_redacted_and_linked(self) -> None:
        fixture_paths = sorted(TICKET_DIR.glob("*.json"))
        self.assertEqual({path.stem for path in fixture_paths}, SUPPORT_CATEGORY_IDS)

        for path in fixture_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "platform-support-ticket-fixture-v1")
            self.assertEqual(payload["version"], "v0.3.27-alpha")
            self.assertEqual(payload["ticket_id"], path.stem)
            self.assertEqual(payload["status"], "mock_ticket_ready")
            self.assertTrue(payload["linked_import_failure_fixture"].startswith("fixtures/platform-import-failures/"))
            self.assertEqual(set(payload["support_bundle"]), REQUIRED_SUPPORT_FIELDS)
            self.assertTrue(payload["support_bundle"]["next_commands_tried"])
            self.assertTrue(payload["triage"]["first_response"])
            self.assertTrue(payload["triage"]["close_when"])
            for value in payload["privacy"].values():
                self.assertIs(value, False)
            serialized = json.dumps(payload)
            for marker in FORBIDDEN_MARKERS:
                self.assertNotIn(marker, serialized)

    def test_pack_verifier_accepts_current_adoption_pack(self) -> None:
        completed = run_script(VERIFIER, "--pack", str(ADOPTION_PACK))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "platform-support-triage-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["support_triage"]["issue_template_count"], 5)
        self.assertEqual(payload["support_triage"]["ticket_fixture_count"], 5)
        self.assertEqual(payload["support_triage"]["playbook_entry_count"], 8)

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_root = Path(tmp_dir) / "missing-pack-root"
            completed = run_script(VERIFIER, "--pack-root", str(missing_root))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Pack root does not exist", completed.stderr)


if __name__ == "__main__":
    unittest.main()
