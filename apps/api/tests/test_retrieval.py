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
from study_anything.core.retrieval import (
    InMemoryRetrievalIndex,
    NoopRetrievalIndex,
    RetrievalUnavailable,
    documents_from_state,
    minimal_snippet,
)
from study_anything.core.retrieval_eval import (
    RetrievalQualityInput,
    build_retrieval_quality_eval,
    retrieval_quality_case_export,
)
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import LearningWorkflow, new_session, submit_reading
from study_anything.core.workspace import LocalWorkspaceStore


class RetrievalTests(unittest.TestCase):
    def test_documents_from_state_use_minimal_redacted_snippets(self) -> None:
        state = new_session("retrieval-user")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="local://private",
            title="Private source",
            text="API token=super-secret-token-value should not be indexed as raw secret.",
        )

        documents = documents_from_state(state, dimensions=8)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].source_type, "local_text")
        self.assertNotIn("super-secret-token-value", documents[0].snippet)
        self.assertEqual(len(documents[0].vector), 8)

    def test_in_memory_rebuild_search_and_context_package(self) -> None:
        index = InMemoryRetrievalIndex(dimensions=16)
        state = new_session("retrieval-user")
        state = submit_reading(
            state,
            source_type="local_text",
            reference="local://retrieval",
            title="Retrieval",
            text="Active recall improves learning when feedback and repetition are connected.",
        )

        rebuilt = index.rebuild_session(state)
        results = index.search(session_id=state.session_id, query="active recall feedback")
        package = results.context_package(
            title="Retrieval package",
            reference=f"retrieval://{state.session_id}",
        )

        self.assertEqual(rebuilt.indexed_count, 1)
        self.assertEqual(results.status, "ready")
        self.assertIn("Active recall", results.results[0].snippet)
        self.assertEqual(package["schema_version"], "learning-context-package-v1")
        self.assertEqual(package["items"][0]["source_type"], "document")

    def test_noop_retrieval_is_disabled(self) -> None:
        index = NoopRetrievalIndex()

        self.assertEqual(index.status().status, "disabled")
        with self.assertRaises(RetrievalUnavailable):
            index.search(session_id="missing", query="anything")

    def test_retrieval_quality_eval_is_redacted_and_passes(self) -> None:
        index = InMemoryRetrievalIndex(dimensions=16)
        state = new_session("retrieval-user")
        private_text = (
            "Private source body about active recall and feedback should only appear "
            "as a minimal retrieval snippet, not inside the eval report."
        )
        state = submit_reading(
            state,
            source_type="local_text",
            reference="local://retrieval-eval",
            title="Retrieval Eval",
            text=private_text,
        )
        index.rebuild_session(state)
        result_set = index.search(session_id=state.session_id, query="active recall feedback")

        report = build_retrieval_quality_eval(
            RetrievalQualityInput(
                session_id=state.session_id,
                query="active recall feedback",
                retrieval_status=index.status().public_dict(),
                result_set=result_set,
            )
        )

        self.assertEqual(report["schema_version"], "retrieval-quality-eval-v1")
        self.assertEqual(report["status"], "pass")
        self.assertNotIn(private_text, str(report))
        self.assertNotIn("snippet", report["retrieval"]["result_summaries"][0])
        self.assertEqual(
            retrieval_quality_case_export()["schema_version"],
            "study-anything-retrieval-quality-cases-v1",
        )


class RetrievalApiTests(unittest.TestCase):
    def _client(self, retrieval_index: object, root: Path) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        registry = AgentRegistry(root / "agents.json")
        workflow = LearningWorkflow(AgentRouter(registry))
        stack.enter_context(patch.object(api_main, "store", InMemorySessionStore()))
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "workflow", workflow))
        stack.enter_context(patch.object(api_main, "retrieval_index", retrieval_index))
        stack.enter_context(
            patch.object(api_main, "workspace_store", LocalWorkspaceStore(root / "workspaces.json"))
        )
        return TestClient(api_main.create_app()), stack

    def test_retrieval_disabled_routes_return_503(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(NoopRetrievalIndex(), Path(tmpdir))
            with stack, client:
                session = client.post("/v1/sessions", json={"user_id": "retrieval-api"}).json()
                response = client.post(f"/v1/sessions/{session['session_id']}/retrieval/rebuild")

        self.assertEqual(response.status_code, 503)

    def test_rebuild_search_and_create_session_from_retrieval(self) -> None:
        with TemporaryDirectory() as tmpdir:
            client, stack = self._client(InMemoryRetrievalIndex(dimensions=16), Path(tmpdir))
            with stack, client:
                session = client.post("/v1/sessions", json={"user_id": "retrieval-api"}).json()
                session_id = session["session_id"]
                client.post(
                    f"/v1/sessions/{session_id}/reading",
                    json={
                        "source_type": "local_text",
                        "reference": "local://retrieval-api",
                        "title": "Retrieval API",
                        "text": "Retrieval connects source snippets with focused follow-up lessons.",
                    },
                )
                rebuilt = client.post(f"/v1/sessions/{session_id}/retrieval/rebuild")
                searched = client.get(
                    f"/v1/sessions/{session_id}/retrieval/search",
                    params={"q": "source snippets follow-up", "limit": 2},
                )
                evaled = client.get(
                    f"/v1/sessions/{session_id}/retrieval/eval",
                    params={"q": "source snippets follow-up", "limit": 2},
                )
                created = client.post(
                    "/v1/sessions/from-retrieval",
                    json={
                        "source_session_id": session_id,
                        "query": "source snippets follow-up",
                        "user_id": "retrieval-import-api",
                    },
                )

        self.assertEqual(rebuilt.status_code, 200, rebuilt.text)
        self.assertEqual(rebuilt.json()["indexed_count"], 1)
        self.assertEqual(searched.status_code, 200, searched.text)
        self.assertEqual(searched.json()["status"], "ready")
        self.assertEqual(evaled.status_code, 200, evaled.text)
        self.assertEqual(evaled.json()["schema_version"], "retrieval-quality-eval-v1")
        self.assertEqual(evaled.json()["status"], "pass")
        self.assertFalse(evaled.json()["privacy"]["result_snippets_included"])
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["status"], "session_created")
        self.assertEqual(created.json()["session"]["stage"], "enrichment_attached")


if __name__ == "__main__":
    unittest.main()
