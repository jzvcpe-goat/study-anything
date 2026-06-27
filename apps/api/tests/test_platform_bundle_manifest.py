from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "scripts" / "generate_platform_bundle_manifest.py"

sys.path.insert(0, str(REPO / "scripts"))
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "generate_platform_bundle_manifest",
    GENERATOR,
)
assert GENERATOR_SPEC is not None and GENERATOR_SPEC.loader is not None
generator = importlib.util.module_from_spec(GENERATOR_SPEC)
GENERATOR_SPEC.loader.exec_module(generator)


class PlatformBundleManifestTests(unittest.TestCase):
    def run_generator_check(self, script_name: str) -> None:
        root = REPO
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / script_name),
                "--check",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_platform_bundle_manifest_is_current(self) -> None:
        self.run_generator_check("generate_platform_bundle_manifest.py")

    def test_generator_failure_formatter_is_actionable_and_redacted(self) -> None:
        message = generator.format_cli_failure(
            RuntimeError(
                "bundle manifest stale at /private/tmp/study-anything/bundle.json "
                "with Authorization: Bearer sk-proj-abcdefghijklmnop123456"
            )
        )

        self.assertIn("generate_platform_bundle_manifest failed:", message)
        self.assertIn("Next steps:", message)
        self.assertIn("generate_platform_bundle_manifest.py --check", message)
        self.assertIn("generate_platform_adoption_pack.py --check", message)
        self.assertIn("verify_ecosystem_submission_pack.py", message)
        self.assertIn("<temp-path>", message)
        self.assertIn("Authorization: Bearer <redacted>", message)
        self.assertNotIn("/private/tmp", message)
        self.assertNotIn("sk-proj-abcdefghijklmnop123456", message)

    def test_generated_platform_manifests_are_order_stable(self) -> None:
        self.run_generator_check("generate_platform_adoption_pack.py")
        self.run_generator_check("generate_platform_bundle_manifest.py")
        self.run_generator_check("generate_platform_adoption_pack.py")

    def test_platform_bundle_manifest_points_to_expected_assets(self) -> None:
        root = REPO
        manifest_path = root / "platform" / "generated" / "study-anything-platform-bundle.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        adoption_path = root / "platform" / "generated" / "study-anything-platform-adoption-pack.json"
        adoption = json.loads(adoption_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], "study-anything-platform-bundle-v1")
        self.assertEqual(payload["platforms"], ["codex", "kimi", "workbuddy"])
        file_paths = {item["path"] for item in payload["files"]}
        bundle_forbidden_recursive_outputs = {
            "platform/generated/study-anything-platform-bundle.json",
            "platform/generated/study-anything-platform-adoption-pack.json",
            "platform/generated/study-anything-platform-adoption-pack.zip",
        }
        adoption_forbidden_recursive_outputs = {
            "platform/generated/study-anything-platform-adoption-pack.json",
            "platform/generated/study-anything-platform-adoption-pack.zip",
        }
        adoption_file_paths = {item["path"] for item in adoption["files"]}
        self.assertFalse(file_paths.intersection(bundle_forbidden_recursive_outputs))
        self.assertFalse(adoption_file_paths.intersection(adoption_forbidden_recursive_outputs))
        self.assertIn("platform/study-anything-platform-tools.json", file_paths)
        self.assertIn("platform/ecosystem-submission.json", file_paths)
        self.assertIn("platform/packs/codex/pack.json", file_paths)
        self.assertIn("platform/packs/kimi/pack.json", file_paths)
        self.assertIn("platform/packs/workbuddy/pack.json", file_paths)
        self.assertIn("scripts/doctor.sh", file_paths)
        self.assertIn("scripts/launch_self_host.sh", file_paths)
        self.assertIn("scripts/localhost_diagnostics.py", file_paths)
        self.assertIn("scripts/verify_published_image_launch.py", file_paths)
        self.assertIn("scripts/verify_commercial_readiness.py", file_paths)
        self.assertIn("scripts/verify_ecosystem_submission_pack.py", file_paths)
        self.assertIn("scripts/verify_external_eval_marketplace_harness.py", file_paths)
        self.assertIn("scripts/verify_agent_eval_marketplace_enforcement.py", file_paths)
        self.assertIn("scripts/verify_platform_adoption_feedback_diagnostics.py", file_paths)
        self.assertIn("scripts/generate_platform_feedback_package.py", file_paths)
        self.assertIn("scripts/verify_learning_enrichment_bridge.py", file_paths)
        self.assertIn("scripts/verify_importer_lesson_flow.py", file_paths)
        self.assertIn("scripts/verify_platform_ecosystem_eval_flow.py", file_paths)
        self.assertIn("platform/generated/study-anything-external-eval-harness.json", file_paths)
        self.assertIn(
            "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
            file_paths,
        )
        self.assertIn(
            "platform/generated/study-anything-platform-adoption-feedback-diagnostics.json",
            file_paths,
        )
        self.assertIn("platform/generated/study-anything-platform-feedback-package.json", file_paths)
        self.assertIn("platform/generated/study-anything-platform-feedback-package.zip", file_paths)
        self.assertIn("platform/generated/study-anything-codex-plugin-pack.json", file_paths)
        self.assertIn("platform/generated/study-anything-codex-plugin-pack.zip", file_paths)
        self.assertIn("platform/generated/study-anything-codex-plugin-pack.sha256", file_paths)
        self.assertIn("platform/generated/study-anything-kimi-plugin-pack.json", file_paths)
        self.assertIn("platform/generated/study-anything-kimi-plugin-pack.zip", file_paths)
        self.assertIn("platform/generated/study-anything-kimi-plugin-pack.sha256", file_paths)
        self.assertIn("platform/generated/study-anything-workbuddy-plugin-pack.json", file_paths)
        self.assertIn("platform/generated/study-anything-workbuddy-plugin-pack.zip", file_paths)
        self.assertIn("platform/generated/study-anything-workbuddy-plugin-pack.sha256", file_paths)
        self.assertIn("scripts/generate_platform_plugin_packs.py", file_paths)
        self.assertIn("scripts/verify_platform_plugin_packs.py", file_paths)
        self.assertIn("platform/generated/study-anything-learning-enrichment-bridge.json", file_paths)
        self.assertIn("platform/generated/study-anything-okf-alignment.json", file_paths)
        self.assertIn("docs/okf-alignment.md", file_paths)
        self.assertIn("platform/okf/examples/demo-session.json", file_paths)
        self.assertIn("platform/okf/examples/demo-okf-bundle/manifest.json", file_paths)
        self.assertIn("platform/okf/examples/demo-okf-bundle/overview.md", file_paths)
        self.assertIn("platform/okf/examples/demo-okf-bundle/questions/review.md", file_paths)
        self.assertIn("scripts/export_okf_bundle.py", file_paths)
        self.assertIn("scripts/verify_okf_bundle.py", file_paths)
        self.assertIn("docs/commercial-readiness.md", file_paths)
        self.assertIn("docs/ecosystem-submission.md", file_paths)
        self.assertIn("docs/eval-frameworks.md", file_paths)
        self.assertIn("docs/skill-mode.md", file_paths)
        self.assertIn("fixtures/notebooklm/notebooklm-style-context-package.json", file_paths)
        self.assertIn("skills/study-anything/SKILL.md", file_paths)
        for item in payload["files"]:
            self.assertRegex(item["sha256"], r"^[a-f0-9]{64}$")
            self.assertGreater(item["bytes"], 0)


if __name__ == "__main__":
    unittest.main()
