from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pydantic import ValidationError

from _path import ROOT  # noqa: F401
from study_anything.cbb.outcomes.evaluator import (
    evaluate_delivery_outcome,
    revocation_registry_updates,
)
from study_anything.cbb.outcomes.fixtures import (
    ISSUED_AT,
    build_outcome_cases,
    fixture_private_key,
)
from study_anything.cbb.protocol.models import (
    DeliveryOutcomeReceiptV1,
    DeliveryScope,
    OutcomeEventV1,
    PostDeliverySamplingV1,
    RollbackOutcomeV1,
)
from study_anything.cbb.protocol.canonical import model_payload
from study_anything.cbb.provenance.fixtures import signed_package
from study_anything.cbb.provenance.signing import (
    generate_private_key,
    verify_offline_package,
)
from study_anything.cbb.outcomes.signing import (
    sign_outcome_envelope,
    verify_outcome_receipt,
    verify_outcome_source_binding,
)


REPO = Path(__file__).resolve().parents[3]


class CBBV1OutcomeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = build_outcome_cases()

    def test_required_outcome_decisions(self) -> None:
        expected = {
            "monitored-no-adverse-signal": (
                "monitored",
                "maintain_current_ceiling",
                "internal_handoff",
            ),
            "near-miss-narrows-scope": (
                "degraded",
                "narrow_scope",
                "sandbox_only",
            ),
            "affected-party-challenge-freezes": (
                "frozen",
                "freeze_recipe",
                "blocked",
            ),
            "claim-violation-revokes": (
                "revoked",
                "revoke_clearance",
                "blocked",
            ),
            "failed-rollback-revokes": (
                "revoked",
                "revoke_clearance",
                "blocked",
            ),
        }
        self.assertEqual(set(self.cases), set(expected))
        for case_id, values in expected.items():
            receipt = DeliveryOutcomeReceiptV1.model_validate(self.cases[case_id]["receipt"])
            self.assertEqual(
                (
                    receipt.status,
                    receipt.trust_update.action.value,
                    receipt.trust_update.resulting_scope.value,
                ),
                values,
            )
            self.assertFalse(receipt.trust_update.trust_increase_allowed)

    def test_revocation_outcome_blocks_original_signed_package(self) -> None:
        package = signed_package()
        receipt = DeliveryOutcomeReceiptV1.model_validate(
            self.cases["claim-violation-revokes"]["receipt"]
        )
        outcome_verification = verify_outcome_receipt(
            package,
            receipt,
            now=ISSUED_AT,
        )
        self.assertTrue(outcome_verification.passed)
        handles = revocation_registry_updates(
            receipt,
            package,
            now=ISSUED_AT,
        )
        self.assertEqual(
            handles,
            (package.receipt_provenance.revocation.handle,),
        )
        result = verify_offline_package(
            package,
            now=receipt.issued_at,
            revoked_handles=handles,
        )
        self.assertEqual(result.status, "fail")
        self.assertIn("not_revoked", result.reasons)

    def test_source_binding_tamper_is_detected(self) -> None:
        package = signed_package()
        payload = deepcopy(self.cases["monitored-no-adverse-signal"]["receipt"])
        payload["source_delivery_receipt_digest_sha256"] = "0" * 64
        receipt = DeliveryOutcomeReceiptV1.model_validate(payload)
        self.assertEqual(
            verify_outcome_source_binding(package, receipt),
            ("source_delivery_receipt_digest_sha256",),
        )

    def test_trust_scope_increase_is_invalid(self) -> None:
        payload = deepcopy(self.cases["monitored-no-adverse-signal"]["receipt"])
        payload["trust_update"]["resulting_scope"] = "production_candidate"
        payload["claim_boundary"]["maximum_scope"] = "production_candidate"
        with self.assertRaisesRegex(ValidationError, "cannot increase"):
            DeliveryOutcomeReceiptV1.model_validate(payload)

    def test_resolved_adverse_event_cannot_restore_the_previous_ceiling(self) -> None:
        package = signed_package()
        inputs = self.cases["near-miss-narrows-scope"]["inputs"]
        event_payload = deepcopy(inputs["events"][0])
        event_payload["status"] = "resolved"
        event_payload["resolution_refs"] = ["resolution:near-miss-corrected"]
        receipt = evaluate_delivery_outcome(
            package,
            sampling=PostDeliverySamplingV1.model_validate(inputs["sampling"]),
            events=[OutcomeEventV1.model_validate(event_payload)],
            rollback=RollbackOutcomeV1.model_validate(inputs["rollback"]),
            recipe_ref=inputs["recipe_ref"],
            issued_at=ISSUED_AT,
            private_key=fixture_private_key(),
            signer_id="test-local-outcome-signer",
            key_id="test-local-outcome-key",
            expires_at="2026-08-10T00:00:00Z",
            replay_nonce="outcome-replay-nonce:resolved-adverse",
        )
        self.assertEqual(receipt.status, "degraded")
        self.assertEqual(receipt.trust_update.action.value, "narrow_scope")

    def test_expired_source_can_record_outcome_without_restoring_delivery_scope(self) -> None:
        package = signed_package()
        inputs = self.cases["near-miss-narrows-scope"]["inputs"]
        issued_at = "2026-09-28T00:00:00Z"
        self.assertIn(
            "not_expired",
            verify_offline_package(package, now=issued_at).reasons,
        )
        receipt = evaluate_delivery_outcome(
            package,
            sampling=PostDeliverySamplingV1.model_validate(inputs["sampling"]),
            events=[OutcomeEventV1.model_validate(inputs["events"][0])],
            rollback=RollbackOutcomeV1.model_validate(inputs["rollback"]),
            recipe_ref=inputs["recipe_ref"],
            issued_at=issued_at,
            private_key=fixture_private_key(),
            signer_id="test-local-outcome-signer",
            key_id="test-local-outcome-key",
            expires_at="2026-10-28T00:00:00Z",
            replay_nonce="outcome-replay-nonce:expired-source-history",
        )
        self.assertEqual(
            receipt.source_verification.clearance_valid_at,
            package.receipt_provenance.created_at,
        )
        self.assertEqual(receipt.trust_update.resulting_scope, DeliveryScope.SANDBOX_ONLY)
        self.assertTrue(verify_outcome_receipt(package, receipt, now=issued_at).passed)

    def test_locally_signed_under_degradation_fails_deterministic_replay(self) -> None:
        package = signed_package()
        payload = deepcopy(self.cases["near-miss-narrows-scope"]["receipt"])
        provenance_payload = payload.pop("outcome_provenance")
        payload["trust_update"]["policy_reconstruction_required"] = False
        forged_provenance = sign_outcome_envelope(
            payload,
            source_package_digest_sha256=(package.receipt_provenance.package_digest_sha256),
            private_key=fixture_private_key(),
            signer_id="test-local-outcome-signer",
            key_id="test-local-outcome-key",
            created_at=payload["issued_at"],
            expires_at=provenance_payload["expires_at"],
            replay_nonce="outcome-replay-nonce:under-degradation",
            outcome_receipt_id=payload["outcome_receipt_id"],
            maximum_scope=DeliveryScope.SANDBOX_ONLY,
        )
        forged = DeliveryOutcomeReceiptV1.model_validate(
            {
                **payload,
                "outcome_provenance": forged_provenance.model_dump(mode="json"),
            }
        )
        verification = verify_outcome_receipt(package, forged, now=ISSUED_AT)
        self.assertFalse(verification.passed)
        self.assertIn("deterministic_trust_update", verification.reasons)

    def test_assets_verifier_and_demo_cli(self) -> None:
        commands = (
            ("generate_cbb_v1_contract_assets.py", "--check"),
            ("generate_cbb_v1_outcome_assets.py", "--check"),
            ("verify_cbb_v1_outcomes.py", "--check"),
        )
        for script, mode in commands:
            completed = subprocess.run(
                [sys.executable, str(REPO / "scripts" / script), mode],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "outcome.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_delivery_outcome.py"),
                    "demo",
                    "--case",
                    "claim-violation-revokes",
                    "--output",
                    str(output),
                ],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            receipt = DeliveryOutcomeReceiptV1.model_validate(
                json.loads(output.read_text(encoding="utf-8"))
            )
            self.assertEqual(receipt.status, "revoked")

            package = signed_package()
            package_path = Path(directory) / "source-package.json"
            observations = Path(directory) / "observations.json"
            key_path = Path(directory) / "outcome.key"
            built_output = Path(directory) / "built-outcome.json"
            package_path.write_text(
                json.dumps(model_payload(package), sort_keys=True),
                encoding="utf-8",
            )
            observations.write_text(
                json.dumps(
                    self.cases["near-miss-narrows-scope"]["inputs"],
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            generate_private_key(key_path)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_delivery_outcome.py"),
                    "build",
                    "--package",
                    str(package_path),
                    "--observations",
                    str(observations),
                    "--private-key",
                    str(key_path),
                    "--signer-id",
                    "test-local-outcome-signer",
                    "--key-id",
                    "test-local-outcome-key",
                    "--expires-at",
                    "2026-08-10T00:00:00Z",
                    "--replay-nonce",
                    "outcome-replay-nonce-cli-test",
                    "--output",
                    str(built_output),
                ],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            built_receipt = DeliveryOutcomeReceiptV1.model_validate(
                json.loads(built_output.read_text(encoding="utf-8"))
            )
            self.assertTrue(
                verify_outcome_receipt(
                    package,
                    built_receipt,
                    now=ISSUED_AT,
                ).passed
            )


if __name__ == "__main__":
    unittest.main()
