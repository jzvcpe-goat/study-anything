from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_platform_public_support_status.py"
VERIFIER = REPO / "scripts" / "verify_platform_public_support_status.py"
REPORT = REPO / "platform" / "generated" / "study-anything-public-support-status.json"
DASHBOARD = REPO / "platform" / "generated" / "study-anything-public-maintainer-dashboard.json"
DASHBOARD_MD = REPO / "platform" / "generated" / "study-anything-public-maintainer-dashboard.md"
STATUS_LINKS = REPO / "fixtures" / "platform-status-links"
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


def json_from_stdout(stdout: str) -> dict[str, object]:
    start = stdout.find("{")
    if start == -1:
        raise AssertionError(f"No JSON object found in stdout: {stdout}")
    payload = json.loads(stdout[start:])
    if not isinstance(payload, dict):
        raise AssertionError(f"JSON object expected in stdout: {stdout}")
    return payload


class PlatformPublicSupportStatusTests(unittest.TestCase):
    def test_generator_and_verifier_checks_pass(self) -> None:
        generated = run_script(GENERATOR, "--check")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("public support status assets are up to date", generated.stdout)

        verified = run_script(VERIFIER, "--check")
        self.assertEqual(verified.returncode, 0, verified.stderr)
        payload = json_from_stdout(verified.stdout)
        self.assertEqual(payload["schema_version"], "public-support-status-v1")
        self.assertEqual(payload["status"], "pass")

    def test_report_dashboard_and_linkage_are_public_only(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        dashboard_md = DASHBOARD_MD.read_text(encoding="utf-8")

        self.assertEqual(report["schema_version"], "public-support-status-v1")
        self.assertEqual(report["version"], "v0.3.20-alpha")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["source_reports"]["onboarding_readiness_schema"],
            "platform-onboarding-readiness-v1",
        )
        self.assertEqual(
            report["source_reports"]["support_triage_schema"],
            "platform-support-triage-v1",
        )
        self.assertEqual(
            {item["platform_id"] for item in report["platform_statuses"]},
            PLATFORM_IDS,
        )
        self.assertEqual(
            {item["blocker_id"] for item in report["known_blockers"]},
            RELEASE_BLOCKER_IDS,
        )
        self.assertEqual(set(report["maintainer_sla"]["labels"]), SLA_LABELS)
        self.assertEqual(
            report["maintainer_sla"]["status_linkage_schema"],
            "public-status-linkage-fixture-v1",
        )
        for item in report["known_blockers"]:
            self.assertIn("fixture_ref", item)
            self.assertRegex(item["fixture_ref"]["sha256"], r"^[a-f0-9]{64}$")
            self.assertNotIn("support_bundle", item)
        for key, value in report["privacy_assertions"].items():
            self.assertIs(value, False, key)

        self.assertEqual(dashboard["schema_version"], "public-maintainer-dashboard-v1")
        self.assertEqual(dashboard["summary"]["platform_count"], 4)
        self.assertEqual(dashboard["summary"]["known_blocker_count"], 5)
        self.assertEqual(dashboard["summary"]["status_linkage_fixture_count"], 7)
        self.assertIn("Known Blocker Fixtures", dashboard_md)
        self.assertIn("public-maintainer-dashboard-v1", dashboard_md)

        serialized = json.dumps({"report": report, "dashboard": dashboard}) + dashboard_md
        for marker in FORBIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def test_status_linkage_fixtures_map_sla_labels_without_private_fields(self) -> None:
        fixture_paths = sorted(STATUS_LINKS.glob("*.json"))
        self.assertEqual({path.stem for path in fixture_paths}, SLA_LABELS)

        for path in fixture_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "public-status-linkage-fixture-v1")
            self.assertEqual(payload["version"], "v0.3.20-alpha")
            self.assertEqual(payload["label"], path.stem)
            self.assertEqual(payload["public_fields"]["linked_schema"], "public-support-status-v1")
            self.assertIn("full_support_bundle_payload", payload["private_fields_excluded"])
            self.assertIn("real_model_keys", payload["private_fields_excluded"])
            for key, value in payload["privacy"].items():
                self.assertIs(value, False, key)
            serialized = json.dumps(payload)
            for marker in FORBIDDEN_MARKERS:
                self.assertNotIn(marker, serialized)

    def test_pack_verifier_accepts_current_adoption_pack(self) -> None:
        completed = run_script(VERIFIER, "--pack", str(ADOPTION_PACK))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "public-support-status-v1")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["public_support_status"]["platform_count"], 4)
        self.assertEqual(payload["public_support_status"]["known_blocker_count"], 5)
        self.assertEqual(payload["public_maintainer_dashboard"]["status_linkage_fixture_count"], 7)

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_root = Path(tmp_dir) / "missing-pack-root"
            completed = run_script(VERIFIER, "--pack-root", str(missing_root))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Pack root does not exist", completed.stderr)


if __name__ == "__main__":
    unittest.main()
