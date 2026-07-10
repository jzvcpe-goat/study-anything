from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
RECEIPT = ROOT / ".cognitive-loop" / "artifacts" / "release" / "release-check-receipt.json"


class ReleaseCheckScriptTests(unittest.TestCase):
    def test_release_check_declares_phases_and_pip_bounds(self) -> None:
        script = RELEASE_CHECK.read_text(encoding="utf-8")

        for phase in (
            "repository sanity",
            "clean-clone setup",
            "dependency install",
            "existing release gates",
            "Dual-Loop verifier gates",
            "release receipt summary",
        ):
            self.assertIn(phase, script)
        self.assertIn("PIP_INSTALL_TIMEOUT_SECONDS:-900", script)
        self.assertIn("PIP_DEFAULT_TIMEOUT:-60", script)
        self.assertIn("PIP_RETRIES:-3", script)
        self.assertIn("--dual-loop-only", script)
        self.assertIn("--skip-clean-clone", script)
        self.assertIn("import fastapi, mypy, pytest, ruff", script)
        self.assertIn("requirements/locked-dev-full.txt", script)
        self.assertIn("generate_python_supply_chain.py --check", script)
        self.assertIn("verify_cbb_v1_kernel.py --check", script)
        self.assertIn("verify_cbb_runtime_isolation.py --check", script)
        self.assertIn('release_python_prefix="$("$python_bin" -c', script)
        self.assertIn('--venv "$release_python_prefix"', script)

    def test_dual_loop_only_mode_writes_partial_receipt(self) -> None:
        completed = subprocess.run(
            ["sh", str(RELEASE_CHECK), "--dual-loop-only"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("NOT full release validation", completed.stdout)
        self.assertIn("== Phase: repository sanity ==", completed.stdout)
        self.assertIn("== Phase: Dual-Loop verifier gates ==", completed.stdout)
        self.assertIn("== Phase: release receipt summary ==", completed.stdout)

        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema_version"], "release-check-receipt-v1")
        self.assertFalse(receipt["full_release_check_completed"])
        self.assertFalse(receipt["clean_clone_completed"])
        self.assertFalse(receipt["dependency_install_completed"])
        self.assertTrue(receipt["dual_loop_verifiers_integrated"])
        self.assertTrue(receipt["dual_loop_verifiers_passed_individually"])
        self.assertTrue(receipt["delivery_trust_verifiers_integrated"])
        self.assertTrue(receipt["delivery_trust_verifiers_passed_individually"])
        self.assertTrue(receipt["customer_handoff_verifiers_integrated"])
        self.assertTrue(receipt["customer_handoff_verifiers_passed_individually"])
        self.assertTrue(receipt["cbb_v1_contract_verifiers_integrated"])
        self.assertFalse(receipt["cbb_v1_contract_verifiers_passed_individually"])
        self.assertTrue(receipt["cbb_v1_kernel_verifiers_integrated"])
        self.assertFalse(receipt["cbb_v1_kernel_verifiers_passed_individually"])
        self.assertTrue(receipt["partial_modes"]["dual_loop_only"])
        self.assertTrue(receipt["partial_modes"]["skip_clean_clone"])
        self.assertIn("do not claim full", receipt["claim_boundary"])
        self.assertEqual(receipt["dependency_install_bounds"]["pip_install_timeout_seconds"], 900)
        self.assertEqual(receipt["dependency_install_bounds"]["pip_default_timeout"], 60)
        self.assertEqual(receipt["dependency_install_bounds"]["pip_retries"], 3)
        self.assertFalse(receipt["privacy"]["raw_logs_included"])
        self.assertFalse(receipt["privacy"]["real_secrets_included"])


if __name__ == "__main__":
    unittest.main()
