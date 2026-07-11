from __future__ import annotations

from copy import deepcopy
import unittest

from pydantic import ValidationError

from _path import ROOT  # noqa: F401
from study_anything.cbb.kernel.gate import evaluate_gate
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    EvidenceBundleV1,
    QualifiedReconstructionV1,
    TrustPolicyV1,
)
from study_anything.cbb.scenarios.fixtures import build_scenario_cases


class CBBV1ScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = build_scenario_cases()

    def _models(
        self,
        case_id: str,
    ) -> tuple[TrustPolicyV1, EvidenceBundleV1, QualifiedReconstructionV1]:
        inputs = self.cases[case_id]["inputs"]
        return (
            TrustPolicyV1.model_validate(inputs["trust_policy"]),
            EvidenceBundleV1.model_validate(inputs["evidence_bundle"]),
            QualifiedReconstructionV1.model_validate(
                inputs["qualified_reconstruction"]
            ),
        )

    def test_required_scenario_decisions(self) -> None:
        expected = {
            "personal-local-prototype": ("allow", "personal_local"),
            "public-fake-data-demo": ("allow", "public_demo"),
            "limited-beta": ("allow", "limited_beta"),
            "paid-customer-candidate": (
                "allow",
                "controlled_customer_handoff",
            ),
            "production-candidate-blocked": ("needs_evidence", "blocked"),
            "regulated-or-irreversible-blocked": ("block", "blocked"),
        }
        self.assertEqual(set(self.cases), set(expected))
        for case_id, expected_decision in expected.items():
            policy, evidence, reconstruction = self._models(case_id)
            decision = evaluate_gate(policy, evidence, reconstruction)
            self.assertEqual(
                (decision.status, decision.approved_scope.value),
                expected_decision,
                case_id,
            )

    def test_production_candidate_names_missing_external_controls(self) -> None:
        policy, evidence, reconstruction = self._models(
            "production-candidate-blocked"
        )
        decision = evaluate_gate(policy, evidence, reconstruction)
        self.assertEqual(decision.status, "needs_evidence")
        self.assertEqual(
            set(decision.missing_evidence_types),
            {
                "domain_review",
                "security_review",
                "deployment_approval",
                "affected_party_protection",
            },
        )

    def test_regulated_scenario_hard_deny_beats_human_reconstruction(self) -> None:
        policy, evidence, reconstruction = self._models(
            "regulated-or-irreversible-blocked"
        )
        self.assertEqual(reconstruction.status, "passed")
        decision = evaluate_gate(policy, evidence, reconstruction)
        self.assertEqual(decision.status, "block")
        self.assertIn(
            "irreversible_external_effect",
            decision.hard_denies_triggered,
        )

    def test_recipient_change_changes_policy_and_decision_identity(self) -> None:
        policy, evidence, reconstruction = self._models("limited-beta")
        payload = policy.model_dump(mode="json")
        payload["scenario"]["recipient"]["recipient_ref"] = "recipient:changed"
        changed = TrustPolicyV1.model_validate(payload)
        self.assertNotEqual(canonical_sha256(policy), canonical_sha256(changed))
        self.assertNotEqual(
            evaluate_gate(policy, evidence, reconstruction).decision_id,
            evaluate_gate(changed, evidence, reconstruction).decision_id,
        )

    def test_model_change_must_update_bound_profile(self) -> None:
        policy, _, _ = self._models("limited-beta")
        payload = policy.model_dump(mode="json")
        payload["scenario"]["model_ref"] = "model:changed"
        with self.assertRaisesRegex(ValidationError, "model capability"):
            TrustPolicyV1.model_validate(payload)

    def test_policy_cannot_exceed_risk_owner_scope_ceiling(self) -> None:
        policy, _, _ = self._models("paid-customer-candidate")
        payload = policy.model_dump(mode="json")
        payload["scenario"]["risk_owner"]["accepted_scope_ceiling"] = (
            "internal_handoff"
        )
        with self.assertRaisesRegex(ValidationError, "risk-owner accepted"):
            TrustPolicyV1.model_validate(payload)

    def test_passive_attention_cannot_be_qualified_reconstruction(self) -> None:
        _, _, reconstruction = self._models("paid-customer-candidate")
        payload = reconstruction.model_dump(mode="json")
        payload["passive_attention_only"] = True
        with self.assertRaises(ValidationError):
            QualifiedReconstructionV1.model_validate(payload)

    def test_global_or_permanent_human_qualification_is_rejected(self) -> None:
        _, _, reconstruction = self._models("paid-customer-candidate")
        global_payload = reconstruction.model_dump(mode="json")
        global_payload["project_ref"] = "global"
        global_payload["human_capability_profile"]["project_ref"] = "global"
        with self.assertRaisesRegex(ValidationError, "project and scenario scoped"):
            QualifiedReconstructionV1.model_validate(global_payload)

        permanent = reconstruction.model_dump(mode="json")
        permanent["human_capability_profile"]["permanent_global_label"] = True
        with self.assertRaises(ValidationError):
            QualifiedReconstructionV1.model_validate(permanent)

    def test_counter_evidence_invalidates_active_human_profile(self) -> None:
        _, _, reconstruction = self._models("paid-customer-candidate")
        payload = reconstruction.model_dump(mode="json")
        payload["human_capability_profile"]["counter_evidence_refs"] = [
            "counter-evidence:incident"
        ]
        with self.assertRaisesRegex(ValidationError, "counter-evidence"):
            QualifiedReconstructionV1.model_validate(payload)

    def test_scenario_mismatch_blocks_instead_of_reusing_qualification(self) -> None:
        policy, evidence, reconstruction = self._models("paid-customer-candidate")
        payload = reconstruction.model_dump(mode="json")
        payload["scenario_ref"] = "scenario:different"
        payload["human_capability_profile"]["scenario_refs"] = [
            "scenario:different"
        ]
        changed = QualifiedReconstructionV1.model_validate(payload)
        decision = evaluate_gate(policy, evidence, changed)
        self.assertEqual(decision.status, "block")
        self.assertIn("reconstruction_scenario_ref_mismatch", decision.reasons)

    def test_missing_mru_cannot_be_hidden_by_aggregate_counts(self) -> None:
        _, _, reconstruction = self._models("paid-customer-candidate")
        payload = deepcopy(reconstruction.model_dump(mode="json"))
        payload["required_mrus_passed"] -= 1
        with self.assertRaisesRegex(ValidationError, "passed count"):
            QualifiedReconstructionV1.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
