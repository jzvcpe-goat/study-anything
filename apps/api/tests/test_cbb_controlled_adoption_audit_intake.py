from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from study_anything.cbb.protocol.canonical import model_payload
from study_anything.cbb.provenance.fixtures import signed_package


ROOT = Path(__file__).resolve().parents[3]
ADOPTION_FIXTURES = ROOT / "fixtures" / "cbb-controlled-adoption"
ADOPTION_ATTESTATION_FIXTURES = (
    ROOT / "fixtures" / "cbb-external-adoption-attestation"
)
AUDIT_FIXTURES = ROOT / "fixtures" / "cbb-external-audit-intake"


class CbbControlledAdoptionAuditIntakeTests(unittest.TestCase):
    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed

    def test_assets_and_verifiers_are_current(self) -> None:
        self.run_script("generate_cbb_adoption_audit_assets.py", "--check")
        adoption = self.run_script(
            "verify_cbb_controlled_adoption_outcomes.py", "--check"
        )
        attestation = self.run_script(
            "verify_cbb_external_adoption_attestation.py", "--check"
        )
        audit = self.run_script("verify_cbb_external_audit_intake.py", "--check")
        self.assertEqual(json.loads(adoption.stdout)["status"], "pass")
        self.assertEqual(json.loads(attestation.stdout)["status"], "pass")
        self.assertEqual(json.loads(audit.stdout)["status"], "pass")

    def test_adoption_fixtures_never_claim_external_evidence_or_production(self) -> None:
        states: set[str] = set()
        for path in ADOPTION_FIXTURES.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            receipt = payload["receipt"]
            states.add(receipt["status"])
            self.assertFalse(receipt["real_adopter_evidence"])
            self.assertFalse(receipt["customer_delivery_authorized"])
            self.assertFalse(receipt["production_authorized"])
            self.assertFalse(receipt["audit_completed"])
        self.assertEqual(
            states,
            {
                "observed",
                "blocked",
                "incident_recorded",
                "rolled_back",
                "revoked",
                "reopen_required",
            },
        )

    def test_audit_fixtures_never_close_or_complete_external_audit(self) -> None:
        states: set[str] = set()
        for path in AUDIT_FIXTURES.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            receipt = payload["receipt"]
            states.add(receipt["state"])
            self.assertFalse(receipt["audit_closure_accepted"])
            self.assertFalse(receipt["report_execution_completed"])
            self.assertFalse(receipt["external_identity_attested"])
            self.assertFalse(receipt["delivery_authority_granted"])
        self.assertNotIn("audit_closed", states)
        self.assertIn("remediation_pending", states)

    def test_attestation_fixtures_never_claim_real_external_adoption(self) -> None:
        states: set[str] = set()
        for path in ADOPTION_ATTESTATION_FIXTURES.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            receipt = payload["receipt"]
            states.add(receipt["state"])
            self.assertFalse(receipt["real_adopter_evidence_accepted"])
            self.assertFalse(receipt["observation_execution_completed"])
            self.assertFalse(receipt["external_identity_attested"])
            self.assertFalse(receipt["delivery_authority_granted"])
            self.assertFalse(receipt["production_authority_granted"])
        self.assertEqual(
            states,
            {"attestation_ready", "synthetic_validated", "rejected"},
        )

    def test_external_adoption_attestation_cli_preserves_synthetic_state(self) -> None:
        fixture = json.loads(
            (ADOPTION_ATTESTATION_FIXTURES / "synthetic-valid.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory(prefix="cbb-adoption-attestation-test-") as tmp:
            root = Path(tmp)
            expected = root / "expected.json"
            envelope = root / "envelope.json"
            expected.write_text(json.dumps(fixture["expected_scope"]), encoding="utf-8")
            envelope.write_text(json.dumps(fixture["envelope"]), encoding="utf-8")
            completed = self.run_script(
                "cbb_external_adoption_attestation.py",
                "evaluate",
                "--expected-scope",
                str(expected),
                "--envelope",
                str(envelope),
                "--evaluated-at",
                "2026-07-15T03:00:00Z",
            )
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["state"], "synthetic_validated")
        self.assertFalse(receipt["real_adopter_evidence_accepted"])

    def test_external_audit_cli_accepts_only_synthetic_fixture_state(self) -> None:
        fixture = json.loads(
            (AUDIT_FIXTURES / "synthetic-valid.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory(prefix="cbb-audit-intake-test-") as tmp:
            root = Path(tmp)
            expected = root / "expected.json"
            envelope = root / "envelope.json"
            expected.write_text(json.dumps(fixture["expected_scope"]), encoding="utf-8")
            envelope.write_text(json.dumps(fixture["envelope"]), encoding="utf-8")
            completed = self.run_script(
                "cbb_external_audit_intake.py",
                "evaluate",
                "--expected-scope",
                str(expected),
                "--envelope",
                str(envelope),
                "--evaluated-at",
                "2026-07-14T00:00:00Z",
            )
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["state"], "synthetic_validated")
        self.assertFalse(receipt["audit_closure_accepted"])

    def test_controlled_adoption_cli_preserves_source_scope(self) -> None:
        fixture = json.loads(
            (ADOPTION_FIXTURES / "shadow-pass.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory(prefix="cbb-adoption-test-") as tmp:
            root = Path(tmp)
            package = root / "package.json"
            case = root / "case.json"
            package.write_text(
                json.dumps(model_payload(signed_package())), encoding="utf-8"
            )
            case.write_text(json.dumps(fixture["case"]), encoding="utf-8")
            completed = self.run_script(
                "cbb_controlled_adoption.py",
                "--package",
                str(package),
                "--case",
                str(case),
                "--expected-release-commit",
                fixture["case"]["binding"]["release_scope_commit"],
                "--conformance-pack-sha256",
                fixture["case"]["binding"]["conformance_pack_sha256"],
            )
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["status"], "observed")
        self.assertEqual(receipt["resulting_scope"], "sandbox_only")

    def test_controlled_adoption_cli_replays_attestation_envelope(self) -> None:
        fixture = json.loads(
            (ADOPTION_ATTESTATION_FIXTURES / "synthetic-valid.json").read_text(
                encoding="utf-8"
            )
        )
        case_payload = fixture["controlled_adoption_case"]
        with tempfile.TemporaryDirectory(prefix="cbb-adoption-replay-test-") as tmp:
            root = Path(tmp)
            package = root / "package.json"
            case = root / "case.json"
            expected = root / "expected.json"
            envelope = root / "envelope.json"
            package.write_text(
                json.dumps(model_payload(signed_package())), encoding="utf-8"
            )
            case.write_text(json.dumps(case_payload), encoding="utf-8")
            expected.write_text(json.dumps(fixture["expected_scope"]), encoding="utf-8")
            envelope.write_text(json.dumps(fixture["envelope"]), encoding="utf-8")
            completed = self.run_script(
                "cbb_controlled_adoption.py",
                "--package",
                str(package),
                "--case",
                str(case),
                "--expected-release-commit",
                case_payload["binding"]["release_scope_commit"],
                "--conformance-pack-sha256",
                case_payload["binding"]["conformance_pack_sha256"],
                "--external-attestation-expected-scope",
                str(expected),
                "--external-attestation-envelope",
                str(envelope),
            )
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["status"], "blocked")
        self.assertFalse(receipt["real_adopter_evidence"])
        self.assertIsNotNone(receipt["external_attestation_receipt_ref"])

    def test_new_runtime_has_no_model_or_network_import(self) -> None:
        forbidden = {
            "anthropic",
            "httpx",
            "langchain",
            "openai",
            "requests",
            "socket",
            "urllib",
        }
        imports: set[str] = set()
        for directory in (
            ROOT / "apps" / "api" / "study_anything" / "cbb" / "adoption",
            ROOT / "apps" / "api" / "study_anything" / "cbb" / "audit",
        ):
            for path in directory.glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module.split(".")[0])
        self.assertFalse(imports.intersection(forbidden))


if __name__ == "__main__":
    unittest.main()
