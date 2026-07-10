from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/verify_dependency_risk_acceptance.py"


def load_script():
    spec = importlib.util.spec_from_file_location("verify_dependency_risk_acceptance", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


risk = load_script()


class DependencyRiskAcceptanceTests(unittest.TestCase):
    def test_repository_acceptance_passes_before_review_date(self) -> None:
        report = risk.verify(today=date(2026, 7, 10))

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["decision"], "tolerable_risk")
        self.assertFalse(report["reachability"]["affected_handlers_called"])
        self.assertTrue(report["automation"]["scheduled_review_gate"])

    def test_expired_acceptance_fails_closed(self) -> None:
        with self.assertRaisesRegex(risk.DependencyRiskAcceptanceError, "expired"):
            risk.verify(today=date(2026, 8, 11))

    def test_new_direct_runtime_import_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir)
            (source / "runtime.ts").write_text(
                'import { x } from "@ai-sdk/provider-utils";\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(risk.DependencyRiskAcceptanceError, "reachable"):
                risk.verify(today=date(2026, 7, 10), runtime_source=source)


if __name__ == "__main__":
    unittest.main()
