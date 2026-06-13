from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from _path import ROOT as API_ROOT  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "diagnose_adoption",
    REPO_ROOT / "scripts" / "diagnose_adoption.py",
)
assert SPEC is not None and SPEC.loader is not None
diagnose = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnose)


class AdoptionDiagnosticsTests(unittest.TestCase):
    def test_default_image_tracks_release_tag(self) -> None:
        self.assertEqual(
            diagnose.DEFAULT_IMAGE,
            "ghcr.io/jzvcpe-goat/study-anything/api:v0.3.7-alpha",
        )

    def test_env_file_check_reports_copyable_setup_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = diagnose.check_env_file(Path(tmp) / ".env")

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["code"], "env_missing")
        self.assertEqual(result["next_command"], "python3 scripts/setup_env.py")

    def test_health_url_for_agent_invoke_endpoint(self) -> None:
        self.assertEqual(
            diagnose.health_url_for_agent("http://127.0.0.1:8787/invoke"),
            "http://127.0.0.1:8787/health",
        )

    def test_health_url_preserves_gateway_base_path(self) -> None:
        self.assertEqual(
            diagnose.health_url_for_agent("https://agent.example.test/study/invoke"),
            "https://agent.example.test/study/health",
        )

    def test_provider_capability_check_reports_missing_defaults(self) -> None:
        status = {
            "defaults": {"quiz.generate": "provider-1"},
            "providers": [
                {
                    "provider_id": "provider-1",
                    "capabilities": ["quiz.generate"],
                }
            ],
        }

        result = diagnose.provider_capability_report(
            status,
            required_capabilities=["quiz.generate", "answer.grade"],
        )

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["missing_defaults"], ["answer.grade"])

    def test_recovery_plan_prefers_skill_mode_without_docker(self) -> None:
        checks = [
            {"status": "warning", "code": "docker_missing"},
            {"status": "warning", "code": "api_unreachable"},
        ]

        plan = diagnose.build_recovery_plan(
            api_base="http://127.0.0.1:8000",
            image=diagnose.DEFAULT_IMAGE,
            checks=checks,
        )

        self.assertEqual(plan["schema_version"], "adoption-diagnostic-plan-v1")
        self.assertEqual(plan["recommended_order"], ["prepare_env", "skill_mode", "api_smoke"])
        self.assertIn("./scripts/launch_skill_mode.sh", plan["commands"]["skill_mode"])
        self.assertIn("v0.3.7-alpha", plan["commands"]["docker_published_image"])
        self.assertIn("verify_adoption_telemetry.py", plan["commands"]["adoption_telemetry"])


if __name__ == "__main__":
    unittest.main()
