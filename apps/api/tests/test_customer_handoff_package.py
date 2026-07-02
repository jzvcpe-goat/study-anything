from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from study_anything.core import customer_handoff, delivery_trust, dual_loop


REPO = Path(__file__).resolve().parents[3]


def build_package() -> dict:
    contract = dual_loop.failure_contract_demo()
    sandbox = dual_loop.sandbox_receipt_demo()
    attention = dual_loop.attention_summary_demo()
    gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention)
    receipt = delivery_trust.build_delivery_trust_receipt(
        contract,
        sandbox,
        gate,
        attention,
    )
    return customer_handoff.build_customer_handoff_package(
        receipt,
        contract,
        sandbox,
        attention,
        gate,
    )


class CustomerHandoffPackageTests(unittest.TestCase):
    def test_allowed_delivery_trust_builds_package(self) -> None:
        package = build_package()

        self.assertEqual(package["schema_version"], "customer-handoff-package-v1")
        self.assertEqual(package["status"], "ready_for_controlled_customer_handoff")
        self.assertEqual(
            package["external_eval_receipts"]["role"],
            "supporting_only_not_sufficient",
        )
        self.assertFalse(package["customer_delivery_scope"]["production_mutation_allowed"])
        self.assertFalse(package["privacy"]["automatic_customer_sending_performed"])
        self.assertEqual(
            {item["platform_id"] for item in package["agent_handoff_instructions"]},
            {"workbuddy", "hermes", "codex"},
        )

    def test_blocked_delivery_trust_cannot_build_package(self) -> None:
        contract = dual_loop.failure_contract_demo()
        sandbox = dual_loop.sandbox_receipt_demo()
        gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, None)
        receipt = delivery_trust.build_delivery_trust_receipt(contract, sandbox, gate, None)

        with self.assertRaises(customer_handoff.CustomerHandoffError):
            customer_handoff.build_customer_handoff_package(
                receipt,
                contract,
                sandbox,
                dual_loop.attention_summary_demo(),
                gate,
            )

    def test_scope_expansion_is_rejected(self) -> None:
        package = build_package()
        package["customer_delivery_scope"]["allowed_material_refs"].append(
            "production_deployment_approval"
        )

        with self.assertRaises(customer_handoff.CustomerHandoffError):
            customer_handoff.validate_customer_handoff_package(package)

    def test_zip_validates_offline(self) -> None:
        package = build_package()
        with tempfile.TemporaryDirectory(prefix="customer-handoff-test-") as tmp:
            zip_path = Path(tmp) / "customer-handoff.zip"
            customer_handoff.write_zip_package(zip_path, package)
            self.assertEqual(customer_handoff.validate_zip_package(zip_path), package)

    def test_customer_handoff_verifier_passes(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "verify_customer_handoff_package.py"),
                "--check",
            ],
            cwd=REPO,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
