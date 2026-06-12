from __future__ import annotations

import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import LearningWorkflow
from study_anything.core.workspace import LocalWorkspaceStore


class EnrichmentQualityExportApiTests(unittest.TestCase):
    def _client(self, root: Path) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        registry = AgentRegistry(root / "agents.json")
        workflow = LearningWorkflow(AgentRouter(registry))
        stack.enter_context(patch.object(api_main, "store", InMemorySessionStore()))
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "workflow", workflow))
        stack.enter_context(
            patch.object(api_main, "workspace_store", LocalWorkspaceStore(root / "workspaces.json"))
        )
        return TestClient(api_main.create_app()), stack

    def test_enrichment_drives_quality_eval_and_obsidian_export(self) -> None:
        private_web_text = "Private web excerpt about retrieval practice and durable recall."
        private_video_text = "Private video slice explaining desirable difficulty."
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                session = client.post(
                    "/v1/sessions",
                    json={"user_id": "enrichment-export-user"},
                ).json()
                session_id = session["session_id"]
                enrichment = client.post(
                    f"/v1/sessions/{session_id}/enrichment",
                    json={
                        "title": "Retrieval Practice Enrichment",
                        "items": [
                            {
                                "source_type": "web",
                                "reference": "https://example.test/retrieval",
                                "title": "Retrieval Article",
                                "locator": "section=retrieval",
                                "text": private_web_text,
                                "provenance": {
                                    "collector": "test-platform-agent",
                                    "capture_method": "browser_excerpt",
                                    "source_owner": "user",
                                },
                                "redaction_policy": "reference_only",
                            },
                            {
                                "source_type": "video_slice",
                                "reference": "video://lesson/1",
                                "title": "Lesson Clip",
                                "locator": "00:01:12-00:02:04",
                                "text": private_video_text,
                                "provenance": {
                                    "collector": "test-platform-agent",
                                    "capture_method": "video_transcript_slice",
                                    "source_owner": "user",
                                },
                                "redaction_policy": "reference_only",
                            },
                        ],
                    },
                )
                self.assertEqual(enrichment.status_code, 200, enrichment.text)
                teaching = client.post(
                    f"/v1/sessions/{session_id}/teaching-layers",
                    json={"layers": ["overview", "glossary", "scribe"]},
                )
                self.assertEqual(teaching.status_code, 200, teaching.text)
                running = client.post(f"/v1/sessions/{session_id}/run").json()
                quiz_id = running["quiz_items"][0]["item_id"]
                completed = client.post(
                    f"/v1/sessions/{session_id}/answers",
                    json={"answers": {quiz_id: "Retrieval practice uses effortful recall."}},
                )
                self.assertEqual(completed.status_code, 200, completed.text)
                quality = client.get(f"/v1/sessions/{session_id}/agent-eval/quality")
                obsidian = client.get(f"/v1/sessions/{session_id}/exports/obsidian")
                package = client.get(f"/v1/sessions/{session_id}/exports/learning-package")
                artifact = client.get(f"/v1/sessions/{session_id}/exports/enrichment-artifact")

        quality_body = quality.json()
        self.assertEqual(quality.status_code, 200)
        self.assertEqual(quality_body["schema_version"], "agent-quality-eval-v1")
        self.assertEqual(quality_body["status"], "pass")
        self.assertGreaterEqual(quality_body["quality_score"], quality_body["threshold"])
        gate_ids = {gate["gate_id"] for gate in quality_body["gates"]}
        self.assertIn("enrichment_ready", gate_ids)
        self.assertNotIn(private_web_text, quality.text)
        self.assertNotIn(private_video_text, quality.text)

        obsidian_body = obsidian.json()
        self.assertEqual(obsidian.status_code, 200)
        self.assertEqual(obsidian_body["schema_version"], "obsidian-markdown-export-v1")
        self.assertTrue(obsidian_body["filename"].endswith(".md"))
        self.assertIn("## Quiz Review", obsidian_body["markdown"])
        self.assertIn("https://example.test/retrieval", obsidian_body["markdown"])
        self.assertIn("video://lesson/1", obsidian_body["markdown"])
        self.assertNotIn(private_web_text, obsidian_body["markdown"])
        self.assertNotIn(private_video_text, obsidian_body["markdown"])

        package_body = package.json()
        self.assertEqual(package.status_code, 200)
        self.assertEqual(package_body["schema_version"], "learning-package-v1")
        self.assertIn("notebooklm_bridge", package_body)
        self.assertIn("notebooklm_bridge", package_body["intended_consumers"])
        self.assertEqual(package_body["privacy"]["raw_source_text_included"], False)
        self.assertEqual(package_body["privacy"]["raw_enrichment_text_included"], False)
        self.assertNotIn(private_web_text, package.text)
        self.assertNotIn(private_video_text, package.text)
        references = package_body["source_references"]
        self.assertTrue(any(item["reference"] == "https://example.test/retrieval" for item in references))
        self.assertTrue(any(item["reference"] == "video://lesson/1" for item in references))
        enrichment_ref = next(item for item in references if item["reference"] == "https://example.test/retrieval")
        self.assertEqual(enrichment_ref["provenance"]["capture_method"], "browser_excerpt")
        self.assertEqual(enrichment_ref["redaction_policy"], "reference_only")

        artifact_body = artifact.json()
        self.assertEqual(artifact.status_code, 200)
        self.assertEqual(artifact_body["schema_version"], "learning-enrichment-artifact-v1")
        self.assertIn("markdown", artifact_body)
        self.assertIn("html", artifact_body)
        self.assertIn("https://example.test/retrieval", artifact_body["markdown"])
        self.assertIn('data-schema="learning-enrichment-artifact-v1"', artifact_body["html"])
        self.assertEqual(artifact_body["privacy"]["raw_enrichment_text_included"], False)
        self.assertNotIn(private_web_text, artifact.text)
        self.assertNotIn(private_video_text, artifact.text)

    def test_quality_cases_endpoint_is_fixed_dataset_contract(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                response = client.get("/v1/evals/quality/cases")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["schema_version"], "study-anything-quality-cases-v1")
        case_ids = {item["case_id"] for item in body["cases"]}
        self.assertIn("overview_layer", case_ids)
        self.assertIn("glossary_layer", case_ids)
        self.assertIn("answer_grading", case_ids)

    def test_obsidian_export_has_stable_frontmatter_backlinks_and_safe_filename(self) -> None:
        title = 'CON:/Unsafe [Learning] #Note ^ With "Quotes" And A Very Long Title ' * 3
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                created = client.post(
                    "/v1/sessions/from-context-package",
                    json={
                        "user_id": "obsidian-stability-user",
                        "package": {
                            "schema_version": "learning-context-package-v1",
                            "title": title,
                            "reference": "obsidian://vault/unsafe",
                            "track": "PRODUCT",
                            "items": [
                                {
                                    "source_type": "obsidian_note",
                                    "reference": "obsidian://vault/unsafe",
                                    "title": "Unsafe Learning Note",
                                    "text": "A bounded excerpt about stable backlinks.",
                                    "locator": "heading=Stable backlinks",
                                    "provenance": {
                                        "collector": "test-platform-agent",
                                        "capture_method": "obsidian_excerpt",
                                        "source_owner": "user",
                                    },
                                    "redaction_policy": "reference_only",
                                    "metadata": {
                                        "obsidian_backlinks": [
                                            "[[AI PM]]",
                                            "Concept | Alias",
                                            "AI PM",
                                        ]
                                    },
                                }
                            ],
                        },
                    },
                )
                self.assertEqual(created.status_code, 200, created.text)
                session_id = created.json()["session"]["session_id"]
                obsidian = client.get(f"/v1/sessions/{session_id}/exports/obsidian")

        self.assertEqual(obsidian.status_code, 200, obsidian.text)
        body = obsidian.json()
        filename = body["filename"]
        markdown = body["markdown"]

        self.assertTrue(filename.endswith(".md"))
        self.assertLessEqual(len(filename), 128)
        for character in '<>:"/\\|?*#^[]':
            self.assertNotIn(character, filename)
        self.assertIn('source_reference: "obsidian://vault/unsafe"', markdown)
        self.assertIn("  - study-anything/product", markdown)
        self.assertIn("related_notes:", markdown)
        self.assertIn('  - "[[AI PM]]"', markdown)
        self.assertIn("- [[Concept - Alias]]", markdown)
        self.assertEqual(markdown.count("[[AI PM]]"), 2)


if __name__ == "__main__":
    unittest.main()
