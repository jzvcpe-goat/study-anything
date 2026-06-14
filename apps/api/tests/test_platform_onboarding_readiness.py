from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_platform_onboarding_readiness.py"
VERIFIER = REPO / "scripts" / "verify_platform_onboarding_readiness.py"
REPORT = REPO / "platform" / "generated" / "study-anything-platform-onboarding-readiness.json"
DASHBOARD = REPO / "platform" / "generated" / "study-anything-platform-triage-dashboard.json"
RELEASE_BLOCKER_DIR = REPO / "fixtures" / "platform-release-blockers"
ADOPTION_PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
PLATFORM_IDS = {"kimi", "codex", "workbuddy", "generic"}
SLA_LABELS = {
    "intake",
    "needs-repro",
    "confirmed",
    "blocked-by-platform",
    "docs-fix",
    "release-blocker",
    "resolved",
}
RELEASE_BLOCKER_IDS = {
    "tool_import_blocker",
    "local_gateway_blocker",
    "published_image_blocker",
    "agent_eval_blocker",
    "support_bundle_privacy_blocker",
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


class PlatformOnboardingReadinessTests(unittest.TestCase):
    def test_generator_and_verifier_checks_pass(self) -> None:
        generated = run_script(GENERATOR, "--check")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("generated platform onboarding readiness assets are up to date", generated.stdout)

        verified = run_script(VERIFIER, "--check")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("platform onboarding readiness assets are valid", verified.stdout)

    def test_report_covers_walkthrough_sla_rotation_release_blockers_and_privacy(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], "platform-onboarding-readiness-v1")
        self.assertEqual(report["version"], "v0.3.22-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["walkthrough"]["schema_version"], "first-external-adopter-walkthrough-v1")
        self.assertEqual(
            {item["platform_id"] for item in report["walkthrough"]["platforms"]},
            PLATFORM_IDS,
        )
        for item in report["walkthrough"]["platforms"]:
            self.assertTrue(item["shortest_success_path"])
            self.assertTrue(item["failure_fallback_path"])
            self.assertIn("platform-onboarding-readiness-v1", item["success_evidence"])

        self.assertEqual(report["maintainer_sla"]["schema_version"], "maintainer-sla-labels-v1")
        self.assertEqual(
            {item["label"] for item in report["maintainer_sla"]["labels"]},
            SLA_LABELS,
        )
        self.assertEqual(
            report["maintainer_rotation"]["schema_version"],
            "maintainer-rotation-checklist-v1",
        )
        self.assertGreaterEqual(len(report["maintainer_rotation"]["checklist"]), 5)
        self.assertEqual(set(report["maintainer_rotation"]["required_labels"]), SLA_LABELS)
        self.assertEqual(
            {item["blocker_id"] for item in report["release_blocker_fixtures"]},
            RELEASE_BLOCKER_IDS,
        )
        self.assertTrue(report["privacy_assertions"]["fixtures_are_mock_only"])
        for key, value in report["privacy_assertions"].items():
            if key != "fixtures_are_mock_only":
                self.assertIs(value, False, key)
        serialized = json.dumps(report)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def test_dashboard_is_deterministic_and_privacy_safe(self) -> None:
        dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))

        self.assertEqual(dashboard["schema_version"], "platform-triage-dashboard-v1")
        self.assertEqual(dashboard["version"], "v0.3.22-alpha")
        self.assertEqual(dashboard["status"], "pass")
        self.assertEqual(
            set(dashboard["support_bundle_completeness"]["required_fields"]),
            REQUIRED_SUPPORT_FIELDS,
        )
        self.assertEqual(dashboard["support_bundle_completeness"]["release_blocker_fixture_count"], 5)
        self.assertEqual(set(dashboard["fixture_coverage"]["platform_walkthroughs"]), PLATFORM_IDS)
        self.assertEqual(
            {item["blocker_id"] for item in dashboard["release_blockers"]},
            RELEASE_BLOCKER_IDS,
        )
        for value in dashboard["privacy_scan"].values():
            if isinstance(value, bool):
                self.assertIs(value, False)
        serialized = json.dumps(dashboard)
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def test_release_blocker_fixtures_are_actionable_redacted_and_linked(self) -> None:
        fixture_paths = sorted(RELEASE_BLOCKER_DIR.glob("*.json"))
        self.assertEqual({path.stem for path in fixture_paths}, RELEASE_BLOCKER_IDS)

        for path in fixture_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "platform-release-blocker-fixture-v1")
            self.assertEqual(payload["version"], "v0.3.22-alpha")
            self.assertEqual(payload["blocker_id"], path.stem)
            self.assertEqual(payload["status"], "mock_release_blocker_ready")
            self.assertIn(payload["linked_support_category"], {
                "platform_import_failure",
                "local_gateway_failure",
                "published_image_pull_failure",
                "agent_eval_evidence_failure",
                "docs_confusion",
            })
            self.assertEqual(set(payload["support_bundle"]), REQUIRED_SUPPORT_FIELDS)
            self.assertTrue(payload["support_bundle"]["next_commands_tried"])
            self.assertIn("release-blocker", payload["required_labels"])
            self.assertTrue(payload["close_when"])
            for value in payload["privacy"].values():
                self.assertIs(value, False)
            serialized = json.dumps(payload)
            for marker in FORBIDDEN_MARKERS:
                self.assertNotIn(marker, serialized)

    def test_pack_verifier_accepts_current_adoption_pack(self) -> None:
        completed = run_script(VERIFIER, "--pack", str(ADOPTION_PACK))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "platform-onboarding-readiness-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["onboarding_readiness"]["walkthrough_count"], 4)
        self.assertEqual(payload["onboarding_readiness"]["sla_label_count"], 7)
        self.assertEqual(payload["onboarding_readiness"]["release_blocker_fixture_count"], 5)

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_root = Path(tmp_dir) / "missing-pack-root"
            completed = run_script(VERIFIER, "--pack-root", str(missing_root))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Pack root does not exist", completed.stderr)


if __name__ == "__main__":
    unittest.main()
