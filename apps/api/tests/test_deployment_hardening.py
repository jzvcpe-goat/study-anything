from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = ROOT.parents[1]
SCRIPT = REPO / "scripts" / "verify_deployment_hardening.py"
PACK = REPO / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


class DeploymentHardeningTests(unittest.TestCase):
    def test_source_tree_report_covers_three_runtime_modes_and_fallback(self) -> None:
        completed = run_script()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "deployment-hardening-verification-v1")
        self.assertEqual(report["version"], "v0.3.16-alpha")
        self.assertEqual(report["status"], "pass")
        modes = {item["id"] for item in report["deployment_modes"]}
        self.assertEqual(modes, {"skill_mode", "published_image", "source_build"})
        self.assertTrue(
            report["published_image_smoke"][
                "fallback_is_acceptance_when_ci_manifest_and_release_check_pass"
            ]
        )
        self.assertEqual(
            set(report["published_image_smoke"]["required_platforms"]),
            {"linux/amd64", "linux/arm64"},
        )
        self.assertTrue(report["privacy_assertions"]["report_is_redacted"])

    def test_pack_report_validates_copy_ready_deployment_assets(self) -> None:
        completed = run_script("--pack", str(PACK))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "deployment-hardening-verification-v1")
        self.assertEqual(report["adoption_pack"]["version"], "v0.3.16-alpha")
        self.assertIn("manifest.json", {item["path"] for item in report["checked_assets"]})

    def test_missing_pack_root_fails_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir()
            completed = run_script("--pack-root", str(root))

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Required deployment asset is missing", completed.stderr)


if __name__ == "__main__":
    unittest.main()
