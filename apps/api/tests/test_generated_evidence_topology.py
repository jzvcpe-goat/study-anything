from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "generated_evidence_topology.py"


def load_script():
    spec = importlib.util.spec_from_file_location("generated_evidence_topology", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


topology = load_script()


def result(node, stage, status="pass"):
    return topology.NodeRun(
        node_id=node.node_id,
        stage=stage,
        status=status,
        exit_code=0 if status == "pass" else 1,
        failure_kind=None if status == "pass" else "command_failed",
        duration_ms=1,
    )


class GeneratedEvidenceTopologyTests(unittest.TestCase):
    def test_order_places_every_hard_dependency_first(self) -> None:
        ordered = topology.validate_and_order(topology.NODES)
        positions = {node.node_id: index for index, node in enumerate(ordered)}

        for node in ordered:
            for dependency in node.dependencies:
                self.assertLess(positions[dependency], positions[node.node_id])

        adoption = next(node for node in ordered if node.node_id == "release_asset_adoption")
        self.assertIn("platform_agent_replay", adoption.dependencies)

    def test_hard_cycle_and_unknown_dependency_are_rejected(self) -> None:
        with self.assertRaises(topology.EvidenceTopologyError):
            topology.validate_and_order(
                (
                    topology.EvidenceNode("a", "a.py", (), (), dependencies=("b",)),
                    topology.EvidenceNode("b", "b.py", (), (), dependencies=("a",)),
                )
            )
        with self.assertRaises(topology.EvidenceTopologyError):
            topology.validate_and_order(
                (topology.EvidenceNode("a", "a.py", (), (), dependencies=("missing",)),)
            )

    def test_check_mode_collects_all_failures(self) -> None:
        calls = []

        def runner(node, stage, _timeout):
            calls.append(node.node_id)
            status = "failed" if node.node_id in {"platform_agent_assets", "pack_extract_smoke"} else "pass"
            return result(node, stage, status)

        receipt = topology.execute_topology(
            mode="check", runner=runner, emit_progress=False
        )

        self.assertEqual(receipt["status"], "blocked")
        self.assertEqual(len(calls), len(topology.NODES))
        self.assertEqual(
            receipt["execution"]["failed_node_ids"],
            ["pack_extract_smoke", "platform_agent_assets"],
        )

    def test_refresh_reaches_feedback_fixed_point(self) -> None:
        ordered = topology.validate_and_order(topology.NODES)
        check_round = 0

        def runner(node, stage, _timeout):
            nonlocal check_round
            if stage == "check" and node.node_id == ordered[0].node_id:
                check_round += 1
            status = "failed" if stage == "check" and check_round == 1 else "pass"
            return result(node, stage, status)

        receipt = topology.execute_topology(
            mode="refresh", max_passes=3, runner=runner, emit_progress=False
        )

        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["execution"]["passes_completed"], 2)
        self.assertTrue(receipt["execution"]["converged"])

    def test_refresh_command_failure_stops_retries(self) -> None:
        def runner(node, stage, _timeout):
            status = "failed" if stage == "refresh" and node.node_id == "platform_plugin_packs" else "pass"
            return result(node, stage, status)

        receipt = topology.execute_topology(
            mode="refresh", max_passes=3, runner=runner, emit_progress=False
        )

        self.assertEqual(receipt["status"], "blocked")
        self.assertEqual(receipt["execution"]["passes_completed"], 1)
        self.assertIn("platform_plugin_packs", receipt["execution"]["failed_node_ids"])

    def test_receipt_is_private_and_mode_marks_repository_mutation(self) -> None:
        def runner(node, stage, _timeout):
            return result(node, stage)

        checked = topology.execute_topology(
            mode="check", runner=runner, emit_progress=False
        )
        refreshed = topology.execute_topology(
            mode="refresh", runner=runner, emit_progress=False
        )

        self.assertTrue(checked["privacy"]["metadata_only"])
        self.assertFalse(checked["privacy"]["repository_generated_assets_mutated"])
        self.assertTrue(refreshed["privacy"]["repository_generated_assets_mutated"])
        self.assertFalse(refreshed["privacy"]["command_stdout_included"])

    def test_receipt_file_uses_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "receipt.json"
            topology.write_receipt(target, {"status": "pass"})

            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertIn('"status": "pass"', target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
