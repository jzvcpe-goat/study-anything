from __future__ import annotations

import unittest
from dataclasses import asdict

from _path import ROOT  # noqa: F401

from study_anything.core.knowledge_graph import (
    FalkorDBKnowledgeGraphSink,
    KnowledgeGraphProjection,
    KnowledgeGraphUnavailable,
    NoopKnowledgeGraphSink,
)


class FakeResponse:
    def __init__(self, result_set: list[list[object]]) -> None:
        self.result_set = result_set


class FakeGraph:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, object]]] = []
        self.topology_rows: list[list[object]] = []

    def query(
        self,
        query: str,
        params: dict[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.queries.append((query, params))
        return FakeResponse([[params["session_id"]]])

    def ro_query(
        self,
        query: str,
        params: dict[str, object] | None = None,
        timeout: int = 1000,
    ) -> FakeResponse:
        if query.strip() == "RETURN 1":
            return FakeResponse([[1]])
        return FakeResponse(self.topology_rows)


class FakeClient:
    def __init__(self, graph: FakeGraph) -> None:
        self.graph = graph
        self.select_calls = 0

    def ping(self) -> bool:
        return True

    def select_graph(self, graph_name: str) -> FakeGraph:
        self.select_calls += 1
        return self.graph


def projection() -> KnowledgeGraphProjection:
    return KnowledgeGraphProjection(
        session_id="session-1",
        user_hash="user-hash",
        track="ACADEMIC",
        source_type="local_text",
        reference="demo://source",
        excerpt_hash="excerpt-hash",
        mastery_level=0.5,
        mastery_bloom="understand",
        updated_at="2026-06-01T00:00:00+00:00",
    )


class KnowledgeGraphTests(unittest.TestCase):
    def test_noop_sink_reports_disabled(self) -> None:
        sink = NoopKnowledgeGraphSink()

        self.assertEqual(sink.status().status, "disabled")
        with self.assertRaises(KnowledgeGraphUnavailable):
            sink.topology("session-1")

    def test_projection_uses_allowlisted_parameters(self) -> None:
        graph = FakeGraph()
        sink = FalkorDBKnowledgeGraphSink(
            host="localhost",
            port=6379,
            graph_name="study-anything-test",
            query_timeout_ms=1000,
            client_factory=lambda **_kwargs: FakeClient(graph),
        )

        result = sink.project(projection())

        self.assertEqual(result.status, "projected")
        self.assertEqual(graph.queries[0][1], asdict(projection()))
        self.assertTrue(
            {"text", "title", "insights", "answers", "feedback", "agent_metadata"}.isdisjoint(
                graph.queries[0][1]
            )
        )
        self.assertIn("MERGE", graph.queries[0][0])

    def test_health_check_does_not_require_an_existing_graph(self) -> None:
        graph = FakeGraph()
        client = FakeClient(graph)
        sink = FalkorDBKnowledgeGraphSink(
            host="localhost",
            port=6379,
            graph_name="study-anything-test",
            query_timeout_ms=1000,
            client_factory=lambda **_kwargs: client,
        )

        status = sink.status()

        self.assertEqual(status.status, "healthy")
        self.assertEqual(client.select_calls, 0)

    def test_topology_response_contains_only_safe_nodes_and_edges(self) -> None:
        graph = FakeGraph()
        graph.topology_rows = [
            [
                "user-hash",
                "session-1",
                "ACADEMIC",
                "2026-06-01T00:00:00+00:00",
                "excerpt-hash",
                "demo://source",
                "local_text",
                0.5,
                "understand",
                "2026-06-01T00:00:00+00:00",
            ]
        ]
        sink = FalkorDBKnowledgeGraphSink(
            host="localhost",
            port=6379,
            graph_name="study-anything-test",
            query_timeout_ms=1000,
            client_factory=lambda **_kwargs: FakeClient(graph),
        )

        topology = sink.topology("session-1").public_dict()

        self.assertEqual(topology["status"], "ready")
        self.assertEqual(
            {node["node_type"] for node in topology["nodes"]},
            {"Learner", "Session", "Source"},
        )
        self.assertEqual(
            {edge["edge_type"] for edge in topology["edges"]},
            {"STUDIED", "USES_SOURCE", "MASTERY"},
        )
        source_node = next(node for node in topology["nodes"] if node["node_type"] == "Source")
        self.assertEqual(
            set(source_node["properties"]),
            {"excerpt_hash", "reference", "source_type"},
        )

    def test_backend_error_is_sanitized(self) -> None:
        def broken_factory(**_kwargs: object) -> object:
            raise RuntimeError("redis://user:secret@example.invalid")

        sink = FalkorDBKnowledgeGraphSink(
            host="localhost",
            port=6379,
            graph_name="study-anything-test",
            query_timeout_ms=1000,
            client_factory=broken_factory,
        )

        status = sink.status()

        self.assertEqual(status.status, "unavailable")
        self.assertNotIn("secret", status.message)
        with self.assertRaisesRegex(KnowledgeGraphUnavailable, "backend is unavailable"):
            sink.project(projection())


if __name__ == "__main__":
    unittest.main()
