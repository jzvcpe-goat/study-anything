from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from fastapi.testclient import TestClient

from study_anything import __version__
from study_anything.api.main import create_app
from study_anything.core.commercial_readiness import build_commercial_readiness


class CommercialReadinessTests(unittest.TestCase):
    def test_core_contract_marks_local_first_alpha_ready_but_hosted_services_not_ready(self) -> None:
        report = build_commercial_readiness(version=__version__)

        self.assertEqual(report["schema_version"], "commercial-readiness-v1")
        self.assertEqual(report["status"], "architecture_ready_for_oss_platform_alpha")
        assessment = report["launch_assessment"]
        self.assertEqual(assessment["github_oss_launch"], "ready")
        self.assertEqual(assessment["platform_agent_distribution"], "ready")
        self.assertEqual(assessment["self_host_alpha"], "ready")
        self.assertEqual(assessment["hosted_paid_services"], "not_ready")
        self.assertEqual(assessment["standalone_app"], "not_in_launch_path")

        for invariant in report["local_core_invariants"]:
            self.assertTrue(invariant["required_for_oss_launch"])
            self.assertEqual(invariant["status"], "pass")

        services = {item["service_id"]: item for item in report["hosted_service_contracts"]}
        self.assertEqual(set(services), {"neural_sync", "neural_publish", "neural_teams", "catalyst"})
        for service in services.values():
            self.assertEqual(service["status"], "contract_only")
            self.assertTrue(service["required_before_sale"])
            self.assertTrue(service["must_not_block"])

    def test_contract_privacy_flags_are_safe(self) -> None:
        report = build_commercial_readiness(version=__version__)
        privacy = report["privacy"]

        self.assertFalse(privacy["real_model_keys_stored_by_study_anything"])
        self.assertFalse(privacy["hosted_account_required_for_local_core"])
        self.assertFalse(privacy["billing_required_for_local_core"])
        self.assertFalse(privacy["raw_source_text_in_readiness_report"])
        self.assertFalse(privacy["learner_answers_in_readiness_report"])
        self.assertFalse(privacy["agent_endpoints_in_readiness_report"])

        serialized = json.dumps(report, ensure_ascii=False).lower()
        self.assertNotIn("sk-", serialized)
        self.assertNotIn("bearer ", serialized)

    def test_api_exposes_readiness_and_system_summary(self) -> None:
        client = TestClient(create_app())

        response = client.get("/v1/commercial/readiness")
        system = client.get("/v1/system/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "commercial-readiness-v1")
        self.assertEqual(payload["version"], __version__)
        self.assertEqual(payload["launch_assessment"]["hosted_paid_services"], "not_ready")

        self.assertEqual(system.status_code, 200)
        summary = system.json()["commercial_readiness"]
        self.assertEqual(summary["schema_version"], "commercial-readiness-v1")
        self.assertEqual(summary["status"], "architecture_ready_for_oss_platform_alpha")
        self.assertEqual(summary["local_invariants_passed"], summary["local_invariant_count"])

    def test_verifier_script_passes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "verify_commercial_readiness.py")],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "commercial-readiness-verification-v1")
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()
