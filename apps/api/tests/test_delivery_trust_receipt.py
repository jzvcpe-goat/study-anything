from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401
from study_anything.core import delivery_trust, dual_loop


REPO = Path(__file__).resolve().parents[3]


class DeliveryTrustReceiptTests(unittest.TestCase):
    def test_allowed_receipt_requires_both_dual_loop_sides(self) -> None:
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

        self.assertEqual(receipt["schema_version"], "delivery-trust-receipt-v1")
        self.assertEqual(receipt["status"], "allowed")
        self.assertEqual(receipt["decision"], "allow_controlled_customer_handoff")
        self.assertTrue(receipt["checks"]["controlled_failure_environment_passed"])
        self.assertTrue(receipt["checks"]["human_reconstruction_passed"])
        self.assertTrue(receipt["checks"]["no_ai_review_black_box_as_sole_basis"])
        self.assertTrue(receipt["checks"]["no_excessive_manual_re_review_required"])
        self.assertFalse(receipt["customer_delivery_scope"]["production_mutation_allowed"])

    def test_missing_attention_blocks_customer_handoff(self) -> None:
        contract = dual_loop.failure_contract_demo()
        sandbox = dual_loop.sandbox_receipt_demo()
        gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, None)

        receipt = delivery_trust.build_delivery_trust_receipt(contract, sandbox, gate, None)

        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("human_reconstruction_missing", receipt["reasons"])
        self.assertIn("dual_loop_gate_blocked", receipt["reasons"])
        self.assertFalse(receipt["customer_delivery_scope"]["allowed_handoff"])

    def test_ai_review_only_basis_is_rejected(self) -> None:
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
        receipt["checks"]["no_ai_review_black_box_as_sole_basis"] = False

        with self.assertRaises(delivery_trust.DeliveryTrustError):
            delivery_trust.validate_delivery_trust_receipt(receipt)

    def test_delivery_trust_verifier_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "verify_delivery_trust_receipt.py"), "--check"],
            cwd=REPO,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
