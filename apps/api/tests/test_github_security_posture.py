from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_github_security_posture.py"


def load_script():
    spec = importlib.util.spec_from_file_location("verify_github_security_posture", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


posture = load_script()


class GithubSecurityPostureTests(unittest.TestCase):
    def test_deterministic_contract_passes(self) -> None:
        report = posture.verify_contract()

        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["privacy"]["metadata_only"])

    def test_force_pushes_are_rejected(self) -> None:
        repository, actions, protection = posture.deterministic_fixture()
        protection = copy.deepcopy(protection)
        protection["allow_force_pushes"]["enabled"] = True

        report = posture.assess_posture(
            repository=repository,
            actions_permissions=actions,
            branch_protection=protection,
            dependabot_alerts_enabled=True,
            dependabot_security_updates_enabled=True,
            mode="test",
        )

        self.assertEqual(report["status"], "fail")
        self.assertIn("force_pushes_disabled", report["failed_checks"])

    def test_missing_dependabot_alerts_are_rejected(self) -> None:
        repository, actions, protection = posture.deterministic_fixture()

        report = posture.assess_posture(
            repository=repository,
            actions_permissions=actions,
            branch_protection=protection,
            dependabot_alerts_enabled=False,
            dependabot_security_updates_enabled=True,
            mode="test",
        )

        self.assertEqual(report["status"], "fail")
        self.assertIn("dependabot_alerts_enabled", report["failed_checks"])


if __name__ == "__main__":
    unittest.main()
