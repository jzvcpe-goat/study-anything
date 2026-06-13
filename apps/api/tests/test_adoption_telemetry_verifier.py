from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from _path import ROOT as API_ROOT  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "verify_adoption_telemetry",
    REPO_ROOT / "scripts" / "verify_adoption_telemetry.py",
)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class AdoptionTelemetryVerifierTests(unittest.TestCase):
    def test_core_verifier_returns_safe_contracts(self) -> None:
        telemetry, readiness = verifier.verify_core()

        self.assertEqual(telemetry["schema_version"], "adoption-telemetry-v1")
        self.assertEqual(readiness["schema_version"], "pmf-readiness-v1")
        self.assertTrue(telemetry["adoption"]["tool_import_success"])
        self.assertTrue(telemetry["quality"]["agent_eval_passed"])
        self.assertFalse(telemetry["privacy"]["source_text_included"])
        self.assertFalse(telemetry["privacy"]["agent_endpoints_included"])


if __name__ == "__main__":
    unittest.main()
