from __future__ import annotations

import json
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "platform" / "study-anything-platform-tools.json"
REQUIRED_TOOLS = {
    "study_anything_health",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
}
DISALLOWED_PATH_FRAGMENTS = (
    "/v1/agents/providers",
    "/v1/agents/defaults",
    "/v1/models/",
    "/v1/plugins/install",
    "/v1/sync/export",
    "/v1/sync/inspect",
    "/v1/sync/restore-preview",
    "/v1/pmf/export",
)


class PlatformAgentToolsManifestTests(unittest.TestCase):
    def _manifest(self) -> dict[str, object]:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_declares_required_learning_tools(self) -> None:
        manifest = self._manifest()
        self.assertEqual(manifest["schema_version"], "study-anything-platform-tools-v1")
        tools = {tool["name"]: tool for tool in manifest["tools"]}
        self.assertEqual(set(tools), REQUIRED_TOOLS)
        self.assertIn("verify_platform_agent_tools.py", manifest["acceptance_evidence"]["local_verification_command"])

    def test_manifest_does_not_expose_management_or_secret_surfaces(self) -> None:
        manifest = self._manifest()
        for tool in manifest["tools"]:
            with self.subTest(tool=tool["name"]):
                path = tool["path_template"]
                self.assertTrue(path.startswith("/v1/"))
                self.assertFalse(
                    any(fragment in path for fragment in DISALLOWED_PATH_FRAGMENTS),
                    path,
                )
                self.assertIn(tool["method"], {"GET", "POST"})
                self.assertEqual(tool["input_schema"]["type"], "object")

        privacy = manifest["privacy_contract"]
        forbidden = set(privacy["must_not_log_or_share"])
        self.assertIn("raw source text", forbidden)
        self.assertIn("API keys or model secrets", forbidden)
        self.assertIn("agent endpoints", forbidden)

    def test_audit_and_eval_tools_are_marked_redacted(self) -> None:
        manifest = self._manifest()
        tools = {tool["name"]: tool for tool in manifest["tools"]}
        for name in ["study_anything_agent_audit", "study_anything_agent_eval_artifact"]:
            with self.subTest(tool=name):
                privacy = tools[name]["privacy"]
                self.assertFalse(privacy["returns_private_learning_data"])
                must_not_return = set(privacy["must_not_return"])
                self.assertIn("source text", must_not_return)
                self.assertIn("answers", must_not_return)
                self.assertIn("agent endpoints", must_not_return)
                self.assertIn("secrets", must_not_return)


if __name__ == "__main__":
    unittest.main()
