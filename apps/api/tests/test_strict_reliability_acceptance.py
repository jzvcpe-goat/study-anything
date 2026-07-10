from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_strict_reliability_acceptance.py"


def load_script():
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("verify_strict_reliability_acceptance", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_script()


class StrictReliabilityAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.remote = verifier.load_json(verifier.REMOTE_EVIDENCE)
        cls.source = verifier.load_json(verifier.SOURCE_RECEIPT)
        cls.published = verifier.load_json(verifier.PUBLISHED_RECEIPT)
        cls.index = verifier.load_json(verifier.INDEX_RECEIPT)

    def validate(self, remote=None, source=None, published=None, index=None):
        return verifier.validate_acceptance(
            copy.deepcopy(remote if remote is not None else self.remote),
            copy.deepcopy(source if source is not None else self.source),
            copy.deepcopy(published if published is not None else self.published),
            copy.deepcopy(index if index is not None else self.index),
        )

    def test_real_evidence_rebuilds_as_strict_dual_pass(self) -> None:
        entry = self.validate()

        self.assertEqual(entry["decision"], "strict_dual_pass")
        self.assertTrue(entry["strict_dual_pass"])

    def test_report_preserves_claim_boundaries(self) -> None:
        report = verifier.build_report()

        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["index"]["longitudinal_trend_claimable"])
        self.assertFalse(report["index"]["production_slo_claimable"])

    def test_different_source_workflow_is_rejected(self) -> None:
        remote = copy.deepcopy(self.remote)
        remote["source_run"]["workflow_path"] = ".github/workflows/other.yml"

        with self.assertRaises(verifier.StrictReliabilityAcceptanceError):
            self.validate(remote=remote)

    def test_failed_mode_job_is_rejected(self) -> None:
        remote = copy.deepcopy(self.remote)
        remote["source_run"]["jobs"]["reliability-soak (source-build)"] = "failure"

        with self.assertRaises(verifier.StrictReliabilityAcceptanceError):
            self.validate(remote=remote)

    def test_failed_replay_is_rejected(self) -> None:
        remote = copy.deepcopy(self.remote)
        remote["replay_run"]["conclusion"] = "failure"

        with self.assertRaises(verifier.StrictReliabilityAcceptanceError):
            self.validate(remote=remote)

    def test_unbound_replay_run_is_rejected(self) -> None:
        remote = copy.deepcopy(self.remote)
        remote["replay_run"]["evidence_run_id"] = 1

        with self.assertRaises(verifier.StrictReliabilityAcceptanceError):
            self.validate(remote=remote)

    def test_job_log_privacy_regression_is_rejected(self) -> None:
        remote = copy.deepcopy(self.remote)
        remote["privacy"]["job_logs_included"] = True

        with self.assertRaises(verifier.StrictReliabilityAcceptanceError):
            self.validate(remote=remote)

    def test_tampered_index_is_rejected(self) -> None:
        index = copy.deepcopy(self.index)
        index["runs"][0]["modes"]["source-build"]["sampling"]["sample_count"] = 720

        with self.assertRaises(verifier.StrictReliabilityAcceptanceError):
            self.validate(index=index)

    def test_single_run_cannot_claim_longitudinal_trend(self) -> None:
        index = copy.deepcopy(self.index)
        index["summary"]["longitudinal_trend_claimable"] = True

        with self.assertRaises(verifier.StrictReliabilityAcceptanceError):
            self.validate(index=index)


if __name__ == "__main__":
    unittest.main()
