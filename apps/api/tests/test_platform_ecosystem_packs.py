from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
VERIFIER = REPO / "scripts" / "verify_platform_ecosystem_packs.py"

if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_platform_ecosystem_packs",
    VERIFIER,
)
assert VERIFIER_SPEC is not None and VERIFIER_SPEC.loader is not None
verifier = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(verifier)


class PlatformEcosystemPackTests(unittest.TestCase):
    def test_verifier_failure_formatter_is_actionable_and_redacted(self) -> None:
        secret = "sk-proj-" + "abcdefghijklmnop123456"
        temp_path = "/private/" + "tmp/study-anything/platform-pack.json"
        message = verifier.format_cli_failure(
            RuntimeError(
                f"platform pack stale at {temp_path} "
                f"with Authorization: Bearer {secret}"
            )
        )

        self.assertIn("verify_platform_ecosystem_packs failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("generate_platform_adoption_pack.py", message)
        self.assertIn("generate_platform_bundle_manifest.py", message)
        self.assertIn("verify_platform_ecosystem_packs.py", message)
        self.assertIn("verify_ecosystem_submission_pack.py", message)
        self.assertIn("diagnose_adoption.py", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/" + "tmp", message)
        self.assertNotIn(secret, message)

    def test_platform_ecosystem_pack_verifier_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(VERIFIER)],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"status": "ok"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
