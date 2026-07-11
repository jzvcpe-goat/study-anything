from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization

from study_anything.cbb.agentic.fixtures import (
    ISSUED_AT,
    build_agentic_evolution_cases,
    fixture_private_key,
    memory_entries,
)
from study_anything.cbb.agentic.memory import query_quarantined_memory
from study_anything.cbb.agentic.tools import default_tool_registry
from study_anything.cbb.agentic.signing import verify_evolution_receipt
from study_anything.cbb.protocol.models import (
    AgenticPlanV1,
    EvolutionGateReceiptV1,
    QuarantinedMemoryEntryV1,
)


REPO = Path(__file__).resolve().parents[3]


class CbbV1AgenticEvolutionTests(unittest.TestCase):
    def test_fixture_decisions_and_signatures(self) -> None:
        expected = {
            "approved-local-candidate": "approved_for_local_candidate",
            "hard-deny-change-blocked": "block",
            "missing-human-reconstruction": "needs_evidence",
            "poisoned-memory-needs-evidence": "needs_evidence",
            "self-authorization-blocked": "block",
            "tool-authority-expansion-blocked": "block",
        }
        for case_id, case in build_agentic_evolution_cases().items():
            with self.subTest(case_id=case_id):
                receipt = EvolutionGateReceiptV1.model_validate(case["receipt"])
                self.assertEqual(receipt.decision.status.value, expected[case_id])
                self.assertTrue(verify_evolution_receipt(receipt, now=ISSUED_AT).passed)
                self.assertFalse(receipt.automatic_apply_performed)

    def test_tool_registry_rejects_unknown_gate_tool(self) -> None:
        case = build_agentic_evolution_cases()["approved-local-candidate"]
        plan = deepcopy(case["inputs"]["agentic_evidence"]["plan"])
        plan["calls"][0]["tool_id"] = "cbb.gate.approve"
        reasons = default_tool_registry().validate_plan(AgenticPlanV1.model_validate(plan))
        self.assertIn("unknown_tool:cbb.gate.approve", reasons)

    def test_agentic_plan_cannot_request_policy_mutation(self) -> None:
        case = build_agentic_evolution_cases()["approved-local-candidate"]
        plan = deepcopy(case["inputs"]["agentic_evidence"]["plan"])
        plan["policy_mutation_requested"] = True
        with self.assertRaises(ValueError):
            AgenticPlanV1.model_validate(plan)

    def test_memory_query_is_deterministic_and_quarantines_counter_evidence(self) -> None:
        entries = memory_entries()
        first = query_quarantined_memory(
            entries.values(),
            query_id="query:test",
            as_of="2026-07-11T06:55:00Z",
        )
        second = query_quarantined_memory(
            reversed(list(entries.values())),
            query_id="query:test",
            as_of="2026-07-11T06:55:00Z",
        )
        self.assertEqual(first, second)
        self.assertEqual(first.eligible_memory_ids, [entries["safe"].memory_id])
        self.assertEqual(
            first.unresolved_counter_evidence_refs,
            ["counter-evidence:challenge-1"],
        )
        dispositions = {item.memory_id: item.reason for item in first.ignored_entries}
        self.assertEqual(dispositions[entries["future"].memory_id], "not_yet_observed")

    def test_injected_memory_cannot_be_promoted_to_evidence(self) -> None:
        payload = memory_entries()["poisoned"].model_dump(mode="json")
        payload["eligible_as_supporting_evidence"] = True
        with self.assertRaises(ValueError):
            QuarantinedMemoryEntryV1.model_validate(payload)

    def test_approved_candidate_has_no_delivery_or_apply_authority(self) -> None:
        receipt = EvolutionGateReceiptV1.model_validate(
            build_agentic_evolution_cases()["approved-local-candidate"]["receipt"]
        )
        self.assertEqual(receipt.claim_boundary.maximum_scope.value, "blocked")
        self.assertEqual(receipt.provenance.claim_boundary.maximum_scope.value, "blocked")
        self.assertFalse(receipt.decision.automatic_apply_allowed)
        self.assertFalse(receipt.decision.production_apply_allowed)
        self.assertFalse(receipt.decision.release_performed)

    def test_future_agentic_evidence_is_rejected(self) -> None:
        payload = deepcopy(
            build_agentic_evolution_cases()["approved-local-candidate"]["receipt"]
        )
        payload["agentic_evidence"]["plan"]["created_at"] = "2026-07-12T00:00:00Z"
        with self.assertRaises(ValueError):
            EvolutionGateReceiptV1.model_validate(payload)

    def test_cli_demo_and_build(self) -> None:
        case = build_agentic_evolution_cases()["approved-local-candidate"]
        with tempfile.TemporaryDirectory(prefix="cbb-agentic-evolution-test-") as tmpdir:
            root = Path(tmpdir)
            demo_output = root / "demo.json"
            demo = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_evolution_gate.py"),
                    "demo",
                    "--case",
                    "approved-local-candidate",
                    "--output",
                    str(demo_output),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(demo.returncode, 0, demo.stderr)
            self.assertEqual(json.loads(demo_output.read_text())["decision"]["status"], "approved_for_local_candidate")

            input_path = root / "input.json"
            input_path.write_text(json.dumps(case["inputs"]), encoding="utf-8")
            key_path = root / "key.raw"
            key_path.write_bytes(
                fixture_private_key().private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
            key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            build_output = root / "built.json"
            built = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "cbb_evolution_gate.py"),
                    "build",
                    "--input",
                    str(input_path),
                    "--private-key",
                    str(key_path),
                    "--signer-id",
                    "maintainer:cli-test",
                    "--key-id",
                    "key:cli-test",
                    "--expires-at",
                    case["inputs"]["expires_at"],
                    "--replay-nonce",
                    "evolution-cli-test-replay-nonce",
                    "--output",
                    str(build_output),
                ],
                cwd=REPO,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            receipt = EvolutionGateReceiptV1.model_validate(json.loads(build_output.read_text()))
            self.assertTrue(verify_evolution_receipt(receipt, now=ISSUED_AT).passed)


if __name__ == "__main__":
    unittest.main()
