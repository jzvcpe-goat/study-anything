"""Optional privacy-preserving FalkorDB topology projection."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Callable, Optional


class KnowledgeGraphUnavailable(RuntimeError):
    """Raised when an enabled topology projection cannot reach its backend."""


class KnowledgeGraphProjectionRequired(ValueError):
    """Raised when canonical state does not yet contain projection inputs."""


@dataclass(frozen=True)
class KnowledgeGraphProjection:
    """Allowlisted graph fields. Source prose must never cross this boundary."""

    session_id: str
    user_hash: str
    track: str
    source_type: str
    reference: str
    excerpt_hash: str
    mastery_level: float
    mastery_bloom: str
    updated_at: str


@dataclass(frozen=True)
class KnowledgeGraphStatus:
    enabled: bool
    status: str
    graph_name: Optional[str]
    message: str

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TopologyNode:
    node_id: str
    node_type: str
    properties: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TopologyEdge:
    edge_type: str
    source: str
    target: str
    properties: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SessionTopology:
    session_id: str
    status: str
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]

    def public_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "nodes": [node.public_dict() for node in self.nodes],
            "edges": [edge.public_dict() for edge in self.edges],
        }


@dataclass(frozen=True)
class ProjectionResult:
    session_id: str
    status: str = "projected"

    def public_dict(self) -> dict[str, str]:
        return asdict(self)


def projection_from_state(state: Any) -> KnowledgeGraphProjection:
    """Build the only object allowed to cross into the graph adapter."""

    if state.source is None:
        raise KnowledgeGraphProjectionRequired(
            "A reading source is required before topology projection."
        )
    if not state.updated_at:
        raise KnowledgeGraphProjectionRequired(
            "The session update timestamp is required for projection."
        )
    return KnowledgeGraphProjection(
        session_id=state.session_id,
        user_hash=state.user_hash,
        track=state.track,
        source_type=state.source.source_type,
        reference=state.source.reference,
        excerpt_hash=state.source.excerpt_hash,
        mastery_level=state.mastery.level,
        mastery_bloom=state.mastery.bloom,
        updated_at=state.updated_at,
    )


class KnowledgeGraphSink:
    enabled = False
    graph_name: Optional[str] = None

    def status(self) -> KnowledgeGraphStatus:
        raise NotImplementedError

    def project(self, projection: KnowledgeGraphProjection) -> ProjectionResult:
        raise NotImplementedError

    def topology(self, session_id: str) -> SessionTopology:
        raise NotImplementedError


class NoopKnowledgeGraphSink(KnowledgeGraphSink):
    def status(self) -> KnowledgeGraphStatus:
        return KnowledgeGraphStatus(
            enabled=False,
            status="disabled",
            graph_name=None,
            message="Knowledge graph projection is disabled.",
        )

    def project(self, projection: KnowledgeGraphProjection) -> ProjectionResult:
        raise KnowledgeGraphUnavailable("Knowledge graph projection is disabled.")

    def topology(self, session_id: str) -> SessionTopology:
        raise KnowledgeGraphUnavailable("Knowledge graph projection is disabled.")


class FalkorDBKnowledgeGraphSink(KnowledgeGraphSink):
    enabled = True

    PROJECT_QUERY = """
    MERGE (learner:Learner {user_hash: $user_hash})
    MERGE (session:Session {session_id: $session_id})
    SET session.track = $track, session.updated_at = $updated_at
    MERGE (source:Source {excerpt_hash: $excerpt_hash})
    SET source.reference = $reference, source.source_type = $source_type
    MERGE (learner)-[:STUDIED]->(session)
    MERGE (session)-[:USES_SOURCE]->(source)
    MERGE (learner)-[mastery:MASTERY {session_id: $session_id}]->(source)
    SET mastery.level = $mastery_level,
        mastery.bloom = $mastery_bloom,
        mastery.updated_at = $updated_at
    RETURN session.session_id
    """

    TOPOLOGY_QUERY = """
    MATCH (session:Session {session_id: $session_id})
    OPTIONAL MATCH (learner:Learner)-[:STUDIED]->(session)
    OPTIONAL MATCH (session)-[:USES_SOURCE]->(source:Source)
    OPTIONAL MATCH (learner)-[mastery:MASTERY {session_id: $session_id}]->(source)
    RETURN learner.user_hash,
           session.session_id,
           session.track,
           session.updated_at,
           source.excerpt_hash,
           source.reference,
           source.source_type,
           mastery.level,
           mastery.bloom,
           mastery.updated_at
    LIMIT 1
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        graph_name: str,
        query_timeout_ms: int,
        client_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.graph_name = graph_name
        self.query_timeout_ms = query_timeout_ms
        self._client_factory = client_factory
        self._client: Optional[Any] = None
        self._graph: Optional[Any] = None

    def status(self) -> KnowledgeGraphStatus:
        try:
            self._select_client().ping()
        except Exception:
            return KnowledgeGraphStatus(
                enabled=True,
                status="unavailable",
                graph_name=self.graph_name,
                message="Knowledge graph backend is unavailable.",
            )
        return KnowledgeGraphStatus(
            enabled=True,
            status="healthy",
            graph_name=self.graph_name,
            message="Knowledge graph projection is ready.",
        )

    def project(self, projection: KnowledgeGraphProjection) -> ProjectionResult:
        try:
            self._select_graph().query(
                self.PROJECT_QUERY,
                params=asdict(projection),
                timeout=self.query_timeout_ms,
            )
        except Exception as exc:
            raise KnowledgeGraphUnavailable("Knowledge graph backend is unavailable.") from exc
        return ProjectionResult(session_id=projection.session_id)

    def topology(self, session_id: str) -> SessionTopology:
        try:
            response = self._select_graph().ro_query(
                self.TOPOLOGY_QUERY,
                params={"session_id": session_id},
                timeout=self.query_timeout_ms,
            )
        except Exception as exc:
            raise KnowledgeGraphUnavailable("Knowledge graph backend is unavailable.") from exc
        rows = response.result_set
        if not rows:
            return SessionTopology(session_id=session_id, status="empty", nodes=[], edges=[])
        return self._topology_from_row(rows[0])

    def _select_graph(self) -> Any:
        if self._graph is None:
            self._graph = self._select_client().select_graph(self.graph_name)
        return self._graph

    def _select_client(self) -> Any:
        if self._client is None:
            factory = self._client_factory
            if factory is None:
                from falkordb import FalkorDB

                factory = FalkorDB
            self._client = factory(host=self.host, port=self.port)
        return self._client

    @staticmethod
    def _topology_from_row(row: list[Any]) -> SessionTopology:
        (
            user_hash,
            session_id,
            track,
            session_updated_at,
            excerpt_hash,
            reference,
            source_type,
            mastery_level,
            mastery_bloom,
            mastery_updated_at,
        ) = row
        learner_id = f"learner:{user_hash}"
        session_node_id = f"session:{session_id}"
        source_id = f"source:{excerpt_hash}"
        nodes = [
            TopologyNode(learner_id, "Learner", {"user_hash": user_hash}),
            TopologyNode(
                session_node_id,
                "Session",
                {"session_id": session_id, "track": track, "updated_at": session_updated_at},
            ),
            TopologyNode(
                source_id,
                "Source",
                {
                    "excerpt_hash": excerpt_hash,
                    "reference": reference,
                    "source_type": source_type,
                },
            ),
        ]
        edges = [
            TopologyEdge("STUDIED", learner_id, session_node_id, {}),
            TopologyEdge("USES_SOURCE", session_node_id, source_id, {}),
            TopologyEdge(
                "MASTERY",
                learner_id,
                source_id,
                {
                    "session_id": session_id,
                    "level": mastery_level,
                    "bloom": mastery_bloom,
                    "updated_at": mastery_updated_at,
                },
            ),
        ]
        return SessionTopology(session_id=session_id, status="ready", nodes=nodes, edges=edges)


def build_knowledge_graph_sink() -> KnowledgeGraphSink:
    if os.getenv("FALKORDB_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return NoopKnowledgeGraphSink()
    return FalkorDBKnowledgeGraphSink(
        host=os.getenv("FALKORDB_HOST", "127.0.0.1"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        graph_name=os.getenv("FALKORDB_GRAPH", "study_anything"),
        query_timeout_ms=int(os.getenv("FALKORDB_QUERY_TIMEOUT_MS", "1000")),
    )
