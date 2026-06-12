from __future__ import annotations

import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.importer_runtime import ImporterRuntime, ImporterRuntimeError
from study_anything.core.plugin_registry import PluginRegistry


PLUGIN_ROOT = ROOT.parents[1] / "plugins"


class ImporterRuntimeTests(unittest.TestCase):
    def test_note_importer_creates_valid_context_package(self) -> None:
        result = ImporterRuntime(PluginRegistry([PLUGIN_ROOT])).run(
            "example-note-importer",
            inputs={
                "note_reference": "obsidian://vault/Product/AI PM",
                "title": "AI PM first lesson",
                "markdown_excerpt": "用户研究、技术边界和迭代节奏共同决定 AI 产品质量。",
                "obsidian_backlinks": ["MOC/AI Products"],
            },
            confirmed_permissions=["write:context"],
        )

        body = result.public_dict()
        self.assertEqual(body["schema_version"], "importer-run-v1")
        self.assertEqual(body["status"], "package_created")
        self.assertEqual(body["package"]["items"][0]["source_type"], "obsidian_note")
        self.assertIn("AI 产品质量", body["package"]["items"][0]["text"])
        self.assertFalse(body["redacted_package"]["items"][0]["text_included"])

    def test_permission_confirmation_must_match_manifest(self) -> None:
        with self.assertRaisesRegex(ImporterRuntimeError, "permissions"):
            ImporterRuntime(PluginRegistry([PLUGIN_ROOT])).run(
                "example-note-importer",
                inputs={
                    "note_reference": "note://missing-permission",
                    "title": "Missing permission",
                    "markdown_excerpt": "content",
                },
                confirmed_permissions=[],
            )

    def test_web_importer_network_is_denied_by_default(self) -> None:
        with self.assertRaisesRegex(ImporterRuntimeError, "network:http"):
            ImporterRuntime(PluginRegistry([PLUGIN_ROOT])).run(
                "example-web-importer",
                inputs={
                    "url": "https://example.test/lesson",
                    "title": "Network boundary",
                    "excerpt": "The platform agent fetched this excerpt outside Study Anything.",
                },
                confirmed_permissions=["write:context", "network:http"],
            )

    def test_web_importer_runs_after_explicit_network_review(self) -> None:
        result = ImporterRuntime(PluginRegistry([PLUGIN_ROOT])).run(
            "example-web-importer",
            inputs={
                "url": "https://example.test/lesson",
                "title": "Network boundary",
                "excerpt": "The platform agent fetched this excerpt outside Study Anything.",
            },
            confirmed_permissions=["write:context", "network:http"],
            allow_network=True,
        )

        self.assertTrue(result.public_dict()["network_allowed"])
        self.assertEqual(result.package.items[0].source_type, "web")


class ImporterRuntimeApiTests(unittest.TestCase):
    def test_importer_run_endpoint_returns_validated_package(self) -> None:
        stack = ExitStack()
        stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([PLUGIN_ROOT])))
        client = TestClient(api_main.create_app())

        with stack, client:
            response = client.post(
                "/v1/importers/example-note-importer/run",
                json={
                    "inputs": {
                        "note_reference": "obsidian://vault/AI PM/Lesson 1",
                        "title": "AI PM first lesson",
                        "markdown_excerpt": "结构化学习需要材料、问题、反馈和复习。",
                    },
                    "confirmed_permissions": ["write:context"],
                },
            )

        body = response.json()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(body["schema_version"], "importer-run-v1")
        self.assertEqual(body["package"]["schema_version"], "learning-context-package-v1")
        self.assertEqual(body["package"]["items"][0]["source_type"], "markdown_note")
        self.assertFalse(body["redacted_package"]["privacy"]["bounded_excerpts_included"])

    def test_importer_run_endpoint_rejects_missing_confirmation(self) -> None:
        stack = ExitStack()
        stack.enter_context(patch.object(api_main, "plugins", PluginRegistry([PLUGIN_ROOT])))
        client = TestClient(api_main.create_app())

        with stack, client:
            response = client.post(
                "/v1/importers/example-note-importer/run",
                json={
                    "inputs": {
                        "note_reference": "note://missing-confirmation",
                        "title": "Missing confirmation",
                        "markdown_excerpt": "content",
                    },
                    "confirmed_permissions": [],
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("permissions", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
