from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


class PlatformBundleManifestTests(unittest.TestCase):
    def test_platform_bundle_manifest_is_current(self) -> None:
        root = Path(__file__).resolve().parents[3]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "generate_platform_bundle_manifest.py"),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_platform_bundle_manifest_points_to_expected_assets(self) -> None:
        root = Path(__file__).resolve().parents[3]
        manifest_path = root / "platform" / "generated" / "study-anything-platform-bundle.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], "study-anything-platform-bundle-v1")
        self.assertEqual(payload["platforms"], ["codex", "kimi", "workbuddy"])
        file_paths = {item["path"] for item in payload["files"]}
        self.assertIn("platform/study-anything-platform-tools.json", file_paths)
        self.assertIn("platform/ecosystem-submission.json", file_paths)
        self.assertIn("platform/packs/codex/pack.json", file_paths)
        self.assertIn("platform/packs/kimi/pack.json", file_paths)
        self.assertIn("platform/packs/workbuddy/pack.json", file_paths)
        self.assertIn("scripts/doctor.sh", file_paths)
        self.assertIn("scripts/launch_self_host.sh", file_paths)
        self.assertIn("scripts/verify_published_image_launch.py", file_paths)
        self.assertIn("scripts/verify_commercial_readiness.py", file_paths)
        self.assertIn("scripts/verify_ecosystem_submission_pack.py", file_paths)
        self.assertIn("scripts/verify_external_eval_marketplace_harness.py", file_paths)
        self.assertIn("scripts/verify_agent_eval_marketplace_enforcement.py", file_paths)
        self.assertIn("scripts/verify_learning_enrichment_bridge.py", file_paths)
        self.assertIn("scripts/verify_importer_lesson_flow.py", file_paths)
        self.assertIn("scripts/verify_platform_ecosystem_eval_flow.py", file_paths)
        self.assertIn("platform/generated/study-anything-external-eval-harness.json", file_paths)
        self.assertIn(
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            file_paths,
        )
        self.assertIn("platform/generated/study-anything-learning-enrichment-bridge.json", file_paths)
        self.assertIn("docs/commercial-readiness.md", file_paths)
        self.assertIn("docs/ecosystem-submission.md", file_paths)
        self.assertIn("docs/eval-frameworks.md", file_paths)
        self.assertIn("fixtures/notebooklm/notebooklm-style-context-package.json", file_paths)
        self.assertIn("skills/study-anything/SKILL.md", file_paths)
        for item in payload["files"]:
            self.assertRegex(item["sha256"], r"^[a-f0-9]{64}$")
            self.assertGreater(item["bytes"], 0)


if __name__ == "__main__":
    unittest.main()
