from __future__ import annotations

import importlib.util
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
            "ghcr.io/jzvcpe-goat/study-anything/api:v0.2.21-alpha",
        )

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


if __name__ == "__main__":
    unittest.main()
