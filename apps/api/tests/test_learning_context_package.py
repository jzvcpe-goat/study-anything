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
from study_anything.core.learning_context import (
    LEARNING_CONTEXT_SCHEMA_VERSION,
    ALLOWED_CONTEXT_SOURCE_TYPES,
    validate_learning_context_package,
)
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import LearningWorkflow
from study_anything.core.workspace import LocalWorkspaceStore


def context_package() -> dict[str, object]:
    return {
        "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
        "package_id": "lcp-all-source-types",
        "title": "Importer Coverage Pack",
        "reference": "learning-context://tests/all-source-types",
        "producer": "test-platform-agent",
        "language": "zh",
        "track": "PRODUCT",
        "items": [
            {
                "source_type": source_type,
                "reference": f"{source_type}://example",
                "title": f"{source_type} item",
                "text": f"Bounded excerpt for {source_type} learning.",
                "locator": "section=1",
                "metadata": {"importer": "test"},
            }
            for source_type in sorted(ALLOWED_CONTEXT_SOURCE_TYPES)
        ],
    }


class LearningContextPackageTests(unittest.TestCase):
    def test_validates_all_required_source_types(self) -> None:
        package = validate_learning_context_package(context_package())

        self.assertEqual(package.public_dict()["schema_version"], LEARNING_CONTEXT_SCHEMA_VERSION)
        self.assertEqual(
            set(package.public_dict()["source_types"]),
            ALLOWED_CONTEXT_SOURCE_TYPES,
        )
        self.assertEqual(len(package.enrichment_payload()["items"]), len(ALLOWED_CONTEXT_SOURCE_TYPES))
        self.assertFalse(package.public_dict()["privacy"]["bounded_excerpts_included"])

    def test_rejects_unknown_source_type(self) -> None:
        values = context_package()
        values["items"] = [
            {
                "source_type": "rss",
                "reference": "rss://feed",
                "title": "RSS",
                "text": "unsupported",
            }
        ]

        with self.assertRaises(ValueError):
            validate_learning_context_package(values)

    def test_rejects_secret_like_metadata(self) -> None:
        values = context_package()
        values["metadata"] = {"api_key": "placeholder-secret-value"}

        with self.assertRaises(ValueError):
            validate_learning_context_package(values)

    def test_rejects_mismatched_hash(self) -> None:
        values = context_package()
        item = dict(values["items"][0])  # type: ignore[index]
        item["excerpt_hash"] = "sha256:wrong"
        values["items"] = [item]

        with self.assertRaises(ValueError):
            validate_learning_context_package(values)


class LearningContextPackageApiTests(unittest.TestCase):
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

    def test_validate_create_and_expand_session_from_context_package(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(Path(tmpdir))
            with stack, client:
                package = context_package()
                validated = client.post("/v1/context-packages/validate", json={"package": package})
                self.assertEqual(validated.status_code, 200, validated.text)
                self.assertEqual(validated.json()["status"], "valid")
                self.assertNotIn("Bounded excerpt for web learning.", validated.text)

                created = client.post(
                    "/v1/sessions/from-context-package",
                    json={
                        "package": package,
                        "user_id": "context-api-user",
                        "use_demo_agent": True,
                    },
                )
                self.assertEqual(created.status_code, 200, created.text)
                created_body = created.json()
                session = created_body["session"]
                self.assertEqual(created_body["status"], "session_created")
                self.assertEqual(session["track"], "PRODUCT")
                self.assertEqual(session["stage"], "enrichment_attached")
                self.assertEqual(len(session["enrichment_items"]), len(ALLOWED_CONTEXT_SOURCE_TYPES))

                append_package = context_package()
                append_package["package_id"] = "lcp-append"
                appended = client.post(
                    f"/v1/sessions/{session['session_id']}/context-package",
                    json={"package": append_package},
                )
                self.assertEqual(appended.status_code, 200, appended.text)
                self.assertEqual(appended.json()["status"], "session_expanded")
                self.assertEqual(
                    len(appended.json()["session"]["enrichment_items"]),
                    len(ALLOWED_CONTEXT_SOURCE_TYPES) * 2,
                )


if __name__ == "__main__":
    unittest.main()
