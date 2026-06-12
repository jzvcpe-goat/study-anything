from __future__ import annotations

import json
import unittest
from pathlib import Path

from _path import ROOT  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "platform" / "study-anything-platform-tools.json"
GENERATED_DIR = REPO_ROOT / "platform" / "generated"
OPENAPI_PATH = GENERATED_DIR / "study-anything-platform-openapi.json"
OPENAI_TOOLS_PATH = GENERATED_DIR / "study-anything-openai-tools.json"
CATALOG_PATH = GENERATED_DIR / "study-anything-tool-catalog.md"
REQUIRED_TOOLS = {
    "study_anything_health",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_append_context_package",
    "study_anything_run_importer",
    "study_anything_retrieval_status",
    "study_anything_retrieval_rebuild",
    "study_anything_retrieval_search",
    "study_anything_create_session_from_retrieval",
    "study_anything_append_retrieval_context",
    "study_anything_add_enrichment",
    "study_anything_teaching_layers",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_agent_quality_eval",
    "study_anything_obsidian_export",
    "study_anything_learning_package_export",
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

    def test_generated_openapi_matches_manifest_tools(self) -> None:
        manifest = self._manifest()
        openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
        self.assertEqual(openapi["openapi"], "3.1.0")
        self.assertEqual(
            openapi["x-study-anything-manifest"]["schema_version"],
            manifest["schema_version"],
        )
        for tool in manifest["tools"]:
            with self.subTest(tool=tool["name"]):
                operation = openapi["paths"][tool["path_template"]][tool["method"].lower()]
                self.assertEqual(operation["operationId"], tool["name"])
                self.assertEqual(
                    operation["x-study-anything-output-requirements"],
                    tool["output_requirements"],
                )
                self.assertEqual(operation["x-study-anything-privacy"], tool["privacy"])

    def test_generated_openai_tools_match_manifest_tools(self) -> None:
        manifest = self._manifest()
        openai_tools = json.loads(OPENAI_TOOLS_PATH.read_text(encoding="utf-8"))
        by_name = {tool["function"]["name"]: tool for tool in openai_tools}
        self.assertEqual(set(by_name), {tool["name"] for tool in manifest["tools"]})
        for tool in manifest["tools"]:
            with self.subTest(tool=tool["name"]):
                generated = by_name[tool["name"]]
                self.assertEqual(generated["type"], "function")
                self.assertEqual(generated["function"]["parameters"], tool["input_schema"])
                self.assertIn(tool["path_template"], generated["function"]["description"])

    def test_generated_catalog_mentions_acceptance_and_privacy(self) -> None:
        catalog = CATALOG_PATH.read_text(encoding="utf-8")
        self.assertIn("verify_platform_agent_tools.py", catalog)
        self.assertIn("raw source text", catalog)
        self.assertIn("study_anything_agent_eval_artifact", catalog)
        self.assertIn("study_anything_run_importer", catalog)
        self.assertIn("study_anything_retrieval_search", catalog)


if __name__ == "__main__":
    unittest.main()
