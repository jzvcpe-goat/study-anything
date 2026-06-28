from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class DualLoopMvpTests(unittest.TestCase):
    def run_check(self, script: str) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--check"],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_dual_loop_expected_verifiers_pass(self) -> None:
        self.run_check("verify_dual_loop_contracts.py")
        self.run_check("verify_failure_sandbox_lite.py")
        self.run_check("verify_attention_reconstruction_lite.py")
        self.run_check("verify_dual_loop_gate.py")
