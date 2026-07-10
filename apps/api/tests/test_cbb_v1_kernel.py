from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401

from study_anything.cbb.kernel.fixtures import passing_inputs
from study_anything.cbb.kernel.gate import evaluate_gate
from study_anything.cbb.protocol.models import (
    DeliveryScope,
    EvidenceBundleV1,
    TrustPolicyV1,
)
from study_anything.core import cbb_protocol


REPO = Path(__file__).resolve().parents[3]


class CBBV1KernelTests(unittest.TestCase):
    def test_pass_is_deterministic_and_scope_bounded(self) -> None:
        policy, evidence, reconstruction = passing_inputs()
        first = evaluate_gate(policy, evidence, reconstruction)
        second = evaluate_gate(policy, evidence, reconstruction)
        self.assertEqual(first, second)
        self.assertEqual(first.status, "allow")
        self.assertEqual(
            first.approved_scope,
            DeliveryScope.CONTROLLED_CUSTOMER_HANDOFF,
        )

    def test_decision_id_changes_when_evidence_content_changes(self) -> None:
        policy, evidence, reconstruction = passing_inputs()
        first = evaluate_gate(policy, evidence, reconstruction)
        payload = evidence.model_dump(mode="json")
        payload["evidence"][0]["metadata"]["fixture_revision"] = 2
        second = evaluate_gate(
            policy,
            EvidenceBundleV1.model_validate(payload),
            reconstruction,
        )
        self.assertNotEqual(first.decision_id, second.decision_id)

    def test_hard_deny_blocks_even_complete_evidence(self) -> None:
        policy, evidence, reconstruction = passing_inputs()
        payload = evidence.model_dump(mode="json")
        payload["evidence"].append(
            {
                "evidence_id": "evidence:hard-deny-test",
                "evidence_type": "hard_deny:production_mutation",
                "status": "passed",
                "source_schema_version": "cbb.hard-deny-signal.v1",
                "source_ref": "hard-deny-signal.json",
                "supported_scope": "blocked",
                "metadata": {"observed": True},
            }
        )
        decision = evaluate_gate(
            policy,
            EvidenceBundleV1.model_validate(payload),
            reconstruction,
        )
        self.assertEqual(decision.status, "block")
        self.assertEqual(decision.hard_denies_triggered, ["production_mutation"])

    def test_claim_boundary_can_only_narrow(self) -> None:
        policy, evidence, reconstruction = passing_inputs()
        payload = deepcopy(policy.model_dump(mode="json"))
        payload["claim_boundary"]["maximum_scope"] = "internal_handoff"
        for requirement in payload["required_evidence"]:
            if requirement["required_for_scope"] == "controlled_customer_handoff":
                requirement["required_for_scope"] = "internal_handoff"
        decision = evaluate_gate(
            TrustPolicyV1.model_validate(payload),
            evidence,
            reconstruction,
        )
        self.assertEqual(decision.status, "allow")
        self.assertEqual(decision.approved_scope, DeliveryScope.INTERNAL_HANDOFF)

    def test_legacy_gate_output_is_preserved(self) -> None:
        artifacts = cbb_protocol.build_case_artifacts("safe-controlled-handoff")
        decision = artifacts["delivery-decision-receipt.json"]
        self.assertEqual(decision["status"], "allowed")
        self.assertEqual(decision["decision"], "allow_controlled_customer_handoff")
        self.assertEqual(decision["reasons"], [])

    def test_required_verifiers_pass(self) -> None:
        for script in ("verify_cbb_v1_kernel.py", "verify_cbb_runtime_isolation.py"):
            completed = subprocess.run(
                [sys.executable, str(REPO / "scripts" / script), "--check"],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
