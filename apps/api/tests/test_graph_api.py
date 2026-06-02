from __future__ import annotations

import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient

from _path import ROOT  # noqa: F401

from study_anything.api import main as api_main
from study_anything.core.agent_registry import AgentRegistry, AgentRouter
from study_anything.core.knowledge_graph import (
    KnowledgeGraphProjection,
    KnowledgeGraphStatus,
    NoopKnowledgeGraphSink,
    ProjectionResult,
    SessionTopology,
    TopologyEdge,
    TopologyNode,
)
from study_anything.core.store import InMemorySessionStore
from study_anything.core.workflow import LearningWorkflow


class RecordingApiGraphSink:
    enabled = True
    graph_name = "study-anything-test"

    def __init__(self) -> None:
        self.projections: dict[str, KnowledgeGraphProjection] = {}

    def status(self) -> KnowledgeGraphStatus:
        return KnowledgeGraphStatus(
            True,
            "healthy",
            self.graph_name,
            "Knowledge graph projection is ready.",
        )

    def project(self, projection: KnowledgeGraphProjection) -> ProjectionResult:
        self.projections[projection.session_id] = projection
        return ProjectionResult(session_id=projection.session_id)

    def topology(self, session_id: str) -> SessionTopology:
        projection = self.projections.get(session_id)
        if projection is None:
            return SessionTopology(session_id, "empty", [], [])
        learner = f"learner:{projection.user_hash}"
        session = f"session:{projection.session_id}"
        source = f"source:{projection.excerpt_hash}"
        return SessionTopology(
            session_id,
            "ready",
            [
                TopologyNode(learner, "Learner", {"user_hash": projection.user_hash}),
                TopologyNode(session, "Session", {"session_id": projection.session_id}),
                TopologyNode(source, "Source", {"excerpt_hash": projection.excerpt_hash}),
            ],
            [
                TopologyEdge("STUDIED", learner, session, {}),
                TopologyEdge("USES_SOURCE", session, source, {}),
                TopologyEdge("MASTERY", learner, source, {"level": projection.mastery_level}),
            ],
        )


class GraphApiTests(unittest.TestCase):
    def _client(self, graph_sink: object) -> tuple[TestClient, ExitStack]:
        stack = ExitStack()
        registry = AgentRegistry()
        workflow = LearningWorkflow(AgentRouter(registry), knowledge_graph_sink=graph_sink)
        stack.enter_context(patch.object(api_main, "store", InMemorySessionStore()))
        stack.enter_context(patch.object(api_main, "agent_registry", registry))
        stack.enter_context(patch.object(api_main, "workflow", workflow))
        stack.enter_context(patch.object(api_main, "knowledge_graph_sink", graph_sink))
        return TestClient(api_main.create_app()), stack

    def test_topology_status_projection_and_rebuild(self) -> None:
        client, stack = self._client(RecordingApiGraphSink())
        with stack, client:
            self.assertEqual(client.get("/v1/graph/status").json()["status"], "healthy")
            session = client.post("/v1/sessions", json={"user_id": "api-graph-user"}).json()
            session_id = session["session_id"]
            self.assertEqual(
                client.get(f"/v1/sessions/{session_id}/topology").json()["status"],
                "empty",
            )
            client.post(
                f"/v1/sessions/{session_id}/reading",
                json={
                    "source_type": "local_text",
                    "reference": "demo://graph-api",
                    "title": "Private title",
                    "text": "Private text",
                },
            )
            running = client.post(f"/v1/sessions/{session_id}/run").json()
            quiz_id = running["quiz_items"][0]["item_id"]
            completed = client.post(
                f"/v1/sessions/{session_id}/answers",
                json={"answers": {quiz_id: "Private answer"}},
            ).json()
            self.assertEqual(completed["stage"], "completed")

            topology = client.get(f"/v1/sessions/{session_id}/topology").json()
            rebuilt = client.post(f"/v1/sessions/{session_id}/topology/rebuild").json()

        self.assertEqual(topology["status"], "ready")
        self.assertEqual(rebuilt["status"], "projected")
        self.assertNotIn("Private", str(rebuilt))

    def test_graph_routes_return_expected_errors(self) -> None:
        client, stack = self._client(NoopKnowledgeGraphSink())
        with stack, client:
            session = client.post("/v1/sessions", json={"user_id": "api-graph-user"}).json()
            session_id = session["session_id"]

            self.assertEqual(client.get("/v1/sessions/missing/topology").status_code, 404)
            self.assertEqual(client.get(f"/v1/sessions/{session_id}/topology").status_code, 503)
            self.assertEqual(
                client.post(f"/v1/sessions/{session_id}/topology/rebuild").status_code,
                503,
            )

    def test_rebuild_requires_source(self) -> None:
        client, stack = self._client(RecordingApiGraphSink())
        with stack, client:
            session = client.post("/v1/sessions", json={"user_id": "api-graph-user"}).json()

            response = client.post(f"/v1/sessions/{session['session_id']}/topology/rebuild")

        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
