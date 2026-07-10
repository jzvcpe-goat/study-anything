from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from _path import ROOT  # noqa: F401

from fastapi.testclient import TestClient

from study_anything import __version__
from study_anything.api.main import create_app
from study_anything.core.commercial_readiness import build_commercial_readiness


REPO = Path(__file__).resolve().parents[3]
VERIFIER_PATH = REPO / "scripts" / "verify_commercial_readiness.py"
SPEC = importlib.util.spec_from_file_location("verify_commercial_readiness", VERIFIER_PATH)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class CommercialReadinessTests(unittest.TestCase):
    def test_runtime_failure_payload_is_machine_readable(self) -> None:
        payload = verifier.runtime_failure_payload(
            classification="python_dependency_missing",
            diagnostic="missing module at /Users/example/project token=secretToken123456",
            details={"missing_module": "tomllib"},
        )

        self.assertEqual(payload["schema_version"], "commercial-readiness-error-v1")
        self.assertEqual(payload["classification"], "python_dependency_missing")
        self.assertEqual(payload["details"]["missing_module"], "tomllib")
        self.assertIn(".venv/bin/python", " ".join(payload["next_steps"]))
        serialized = json.dumps(payload, sort_keys=True)
        self.assertIn("<local-path>", serialized)
        self.assertIn("token=<redacted>", serialized)
        self.assertNotIn("/Users/example", serialized)
        self.assertNotIn("secretToken123456", serialized)

    def test_runtime_failure_prints_json(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                verifier.runtime_failure(
                    "verify_commercial_readiness requires Python 3.11 or newer.",
                    classification="python_version_unsupported",
                    details={"python_version": "3.9.6"},
                )

        self.assertEqual(raised.exception.code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["classification"], "python_version_unsupported")
        self.assertEqual(payload["details"]["python_version"], "3.9.6")

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
        foundation = report["hosted_foundation"]
        self.assertEqual(foundation["status"], "application_layer_foundation")
        self.assertEqual(foundation["principal_binding"], "issuer_tenant_subject")
        self.assertIn("database row-level security", foundation["not_proven"])
        security_audit = report["security_audit"]
        self.assertEqual(security_audit["status"], "ready_for_independent_audit")
        self.assertFalse(security_audit["audit_completed"])
        self.assertFalse(security_audit["self_certification_allowed"])
        self.assertTrue(security_audit["human_security_reviewer_required"])
        self.assertFalse(security_audit["ai_only_review_sufficient"])

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
        self.assertEqual(summary["security_audit_status"], "ready_for_independent_audit")
        self.assertFalse(summary["security_audit_completed"])

    def test_verifier_script_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VERIFIER_PATH)],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema_version"], "commercial-readiness-verification-v1")
        self.assertEqual(payload["status"], "pass")

    def test_failure_formatter_is_actionable_and_redacted(self) -> None:
        local_home = "/Users/" + "james"
        secret = "sk-" + "proj-private-commercial-token"
        message = verifier.format_cli_failure(
            verifier.CommercialReadinessError(
                f"Generated tool stale at {local_home}/project with token={secret}"
            )
        )

        self.assertIn("verify_commercial_readiness failed.", message)
        self.assertIn("Next steps:", message)
        self.assertIn("generate_platform_agent_assets.py", message)
        self.assertIn("generate_platform_bundle_manifest.py", message)
        self.assertNotIn(local_home, message)
        self.assertNotIn(secret, message)
        self.assertIn("<redacted>", message)


if __name__ == "__main__":
    unittest.main()
