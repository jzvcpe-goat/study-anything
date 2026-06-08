from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


class PlatformEcosystemPackTests(unittest.TestCase):
    def test_platform_ecosystem_pack_verifier_passes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / "verify_platform_ecosystem_packs.py")],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"status": "ok"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
