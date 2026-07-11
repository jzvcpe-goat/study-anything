from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.cbb.protocol import compat_v0
from study_anything.cbb.protocol.canonical import (
    CanonicalProtocolError,
    canonical_json_bytes,
)
from study_anything.cbb.protocol.models import (
    DeliveryScope,
    EvidenceBundleV1,
    GateDecisionV1,
    QualifiedReconstructionV1,
    ReceiptProvenanceV1,
    TrustPolicyV1,
)
from study_anything.core import delivery_trust, dual_loop


REPO = Path(__file__).resolve().parents[3]


def mapped_v0_chain() -> dict[str, object]:
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
    return compat_v0.map_v0_delivery_chain(
        contract,
        sandbox,
        attention,
        gate,
        receipt,
    )


class CBBV1ContractTests(unittest.TestCase):
    def test_canonical_bytes_ignore_input_key_order(self) -> None:
        contract = dual_loop.failure_contract_demo()
        policy = compat_v0.failure_contract_to_trust_policy(contract)
        payload = policy.model_dump(mode="json")
        reversed_policy = TrustPolicyV1.model_validate(dict(reversed(list(payload.items()))))
        self.assertEqual(canonical_json_bytes(policy), canonical_json_bytes(reversed_policy))

    def test_v0_pass_maps_without_scope_expansion(self) -> None:
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
        mapped = compat_v0.map_v0_delivery_chain(
            contract,
            sandbox,
            attention,
            gate,
            receipt,
        )
        self.assertEqual(mapped["gate_decision"].status, "allow")
        self.assertEqual(
            mapped["gate_decision"].approved_scope,
            DeliveryScope.INTERNAL_HANDOFF,
        )

    def test_stale_reconstruction_narrows_v0_allow(self) -> None:
        contract = dual_loop.failure_contract_demo()
        sandbox = dual_loop.sandbox_receipt_demo()
        attention = dual_loop.attention_summary_demo()
        attention["valid_until"] = "2026-06-27T00:00:00Z"
        gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention)
        receipt = delivery_trust.build_delivery_trust_receipt(
            contract,
            sandbox,
            gate,
            attention,
        )
        mapped = compat_v0.map_v0_delivery_chain(
            contract,
            sandbox,
            attention,
            gate,
            receipt,
        )
        self.assertEqual(receipt["status"], "allowed")
        self.assertEqual(mapped["qualified_reconstruction"].status, "stale")
        self.assertEqual(mapped["gate_decision"].status, "needs_evidence")
        self.assertEqual(mapped["gate_decision"].approved_scope, DeliveryScope.BLOCKED)

    def test_failed_v0_sandbox_maps_to_block_instead_of_schema_error(self) -> None:
        contract = dual_loop.failure_contract_demo()
        sandbox = dual_loop.sandbox_receipt_demo()
        sandbox["status"] = "failed"
        attention = dual_loop.attention_summary_demo()
        gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, attention)
        receipt = delivery_trust.build_delivery_trust_receipt(
            contract,
            sandbox,
            gate,
            attention,
        )
        mapped = compat_v0.map_v0_delivery_chain(
            contract,
            sandbox,
            attention,
            gate,
            receipt,
        )
        self.assertEqual(mapped["gate_decision"].status, "block")
        self.assertIn(
            "evidence_failed:sandbox_receipt",
            mapped["gate_decision"].reasons,
        )

    def test_required_verifiers_pass(self) -> None:
        for script in ("verify_cbb_v1_contracts.py", "verify_cbb_v0_compatibility.py"):
            completed = subprocess.run(
                [sys.executable, str(REPO / "scripts" / script), "--check"],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_timestamp_and_nested_tuple_metadata_are_strict(self) -> None:
        policy = mapped_v0_chain()["trust_policy"]
        self.assertIsInstance(policy, TrustPolicyV1)
        payload = policy.model_dump(mode="json")
        payload["created_at"] = "2026-06-28T00:00:00"
        with self.assertRaisesRegex(ValueError, "String should match pattern"):
            TrustPolicyV1.model_validate(payload)

        with self.assertRaises(CanonicalProtocolError):
            canonical_json_bytes(
                {"nested": ({"api_key": "fixture-redacted-value"},)}
            )

    def test_cross_field_state_cannot_inflate_authority(self) -> None:
        mapped = mapped_v0_chain()

        bundle = mapped["evidence_bundle"]
        self.assertIsInstance(bundle, EvidenceBundleV1)
        bundle_payload = bundle.model_dump(mode="json")
        bundle_payload["evidence"][0]["supported_scope"] = "limited_beta"
        with self.assertRaisesRegex(ValueError, "expands bundle"):
            EvidenceBundleV1.model_validate(bundle_payload)

        reconstruction = mapped["qualified_reconstruction"]
        self.assertIsInstance(reconstruction, QualifiedReconstructionV1)
        reconstruction_payload = reconstruction.model_dump(mode="json")
        reconstruction_payload["required_mrus_passed"] = (
            reconstruction_payload["required_mrus_total"] + 1
        )
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            QualifiedReconstructionV1.model_validate(reconstruction_payload)

        provenance = mapped["receipt_provenance"]
        self.assertIsInstance(provenance, ReceiptProvenanceV1)
        provenance_payload = provenance.model_dump(mode="json")
        provenance_payload["claim_boundary"]["maximum_scope"] = (
            "controlled_customer_handoff"
        )
        with self.assertRaisesRegex(ValueError, "cannot claim delivery authority"):
            ReceiptProvenanceV1.model_validate(provenance_payload)

        decision = mapped["gate_decision"]
        self.assertIsInstance(decision, GateDecisionV1)
        decision_payload = deepcopy(decision.model_dump(mode="json"))
        decision_payload.update(
            {
                "status": "needs_evidence",
                "approved_scope": "blocked",
                "reasons": ["more evidence required"],
                "hard_denies_triggered": ["production_mutation"],
                "missing_evidence_types": ["qualified_reconstruction"],
            }
        )
        decision_payload["claim_boundary"]["maximum_scope"] = "blocked"
        with self.assertRaisesRegex(ValueError, "hard denies require a block"):
            GateDecisionV1.model_validate(decision_payload)


if __name__ == "__main__":
    unittest.main()
