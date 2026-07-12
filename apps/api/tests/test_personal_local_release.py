from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]


class PersonalLocalReleaseTests(unittest.TestCase):
    def test_release_receipt_is_current_and_bounded(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/verify_personal_local_release.py", "--check"],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["identity"]["product_name"], "Delivery Clearance")
        self.assertEqual(receipt["identity"]["tag"], "v0.3.32-alpha")
        self.assertEqual(receipt["claim_boundary"]["maximum_scope"], "personal_local")
        self.assertFalse(receipt["claim_boundary"]["customer_delivery_authorized"])
        self.assertFalse(receipt["claim_boundary"]["production_authorized"])
        self.assertFalse(receipt["claim_boundary"]["external_write_authorized"])

    def test_release_workflow_uses_new_public_title_and_compatibility_wheel(self) -> None:
        workflow = (ROOT / ".github/workflows/delivery-clearance-personal-release.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Delivery Clearance Personal Local Alpha", workflow)
        self.assertIn('tags: ["v0.3.32-alpha"]', workflow)
        self.assertIn("delivery-clearance-plugin-evidence --help", workflow)
        self.assertIn('test "$block_exit" -eq 4', workflow)
        self.assertIn("--prerelease", workflow)


if __name__ == "__main__":
    unittest.main()
