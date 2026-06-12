"""Optional local retrieval projection backed by LanceDB."""

from __future__ import annotations

import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from .learning_context import LEARNING_CONTEXT_SCHEMA_VERSION
from .security import sha256_text


class RetrievalUnavailable(RuntimeError):
    """Raised when retrieval is disabled or unavailable."""


class RetrievalProjectionRequired(ValueError):
    """Raised when a session does not contain indexable material."""


@dataclass(frozen=True)
class RetrievalStatus:
    enabled: bool
    status: str
    index_name: Optional[str]
    message: str
    document_count: Optional[int] = None

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalDocument:
    document_id: str
    session_id: str
    source_type: str
    reference: str
    excerpt_hash: str
    locator: Optional[str]
    snippet: str
    vector: list[float]
    updated_at: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "session_id": self.session_id,
            "source_type": self.source_type,
            "reference": self.reference,
            "excerpt_hash": self.excerpt_hash,
            "locator": self.locator,
            "snippet": self.snippet,
            "vector_dimensions": len(self.vector),
            "updated_at": self.updated_at,
        }

    def storage_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    document_id: str
    session_id: str
    source_type: str
    reference: str
    excerpt_hash: str
    locator: Optional[str]
    snippet: str
    score: float

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalRebuildResult:
    session_id: str
    status: str
    indexed_count: int
    index_name: str

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalSearchResultSet:
    session_id: str
    query: str
    status: str
    results: list[RetrievalResult]

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "retrieval-search-v1",
            "session_id": self.session_id,
            "query": self.query,
            "status": self.status,
            "results": [result.public_dict() for result in self.results],
            "privacy": {
                "agent_secrets_allowed": False,
                "full_source_text_returned": False,
                "canonical_source": "session_state",
            },
        }

    def context_package(self, *, title: str, reference: str) -> dict[str, Any]:
        if not self.results:
            raise RetrievalProjectionRequired("Retrieval returned no results to import.")
        return {
            "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
            "package_id": f"retrieval-{sha256_text(reference + self.query)[:12]}",
            "title": title,
            "reference": reference,
            "producer": "study-anything-retrieval",
            "items": [
                {
                    "source_type": _context_source_type(result.source_type),
                    "reference": result.reference,
                    "title": f"Retrieval result {index}",
                    "text": result.snippet,
                    "locator": result.locator,
                    "metadata": {
                        "source_session_id": result.session_id,
                        "retrieval_document_id": result.document_id,
                        "source_excerpt_hash": result.excerpt_hash,
                        "retrieval_score": result.score,
                    },
                }
                for index, result in enumerate(self.results, start=1)
            ],
        }


class RetrievalIndex:
    enabled = False
    index_name: Optional[str] = None

    def status(self) -> RetrievalStatus:
        raise NotImplementedError

    def rebuild_session(self, state: Any) -> RetrievalRebuildResult:
        raise NotImplementedError

    def search(self, *, session_id: str, query: str, limit: int = 5) -> RetrievalSearchResultSet:
        raise NotImplementedError


class NoopRetrievalIndex(RetrievalIndex):
    def status(self) -> RetrievalStatus:
        return RetrievalStatus(
            enabled=False,
            status="disabled",
            index_name=None,
            message="Retrieval projection is disabled.",
        )

    def rebuild_session(self, state: Any) -> RetrievalRebuildResult:
        raise RetrievalUnavailable("Retrieval projection is disabled.")

    def search(self, *, session_id: str, query: str, limit: int = 5) -> RetrievalSearchResultSet:
        raise RetrievalUnavailable("Retrieval projection is disabled.")


class InMemoryRetrievalIndex(RetrievalIndex):
    """Test and fallback retrieval index with the same privacy boundary."""

    enabled = True

    def __init__(self, *, index_name: str = "study_anything_memory", dimensions: int = 32) -> None:
        self.index_name = index_name
        self.dimensions = dimensions
        self._documents: dict[str, list[RetrievalDocument]] = {}

    def status(self) -> RetrievalStatus:
        return RetrievalStatus(
            enabled=True,
            status="healthy",
            index_name=self.index_name,
            message="In-memory retrieval projection is ready.",
            document_count=sum(len(items) for items in self._documents.values()),
        )

    def rebuild_session(self, state: Any) -> RetrievalRebuildResult:
        documents = documents_from_state(state, dimensions=self.dimensions)
        self._documents[state.session_id] = documents
        return RetrievalRebuildResult(
            session_id=state.session_id,
            status="rebuilt",
            indexed_count=len(documents),
            index_name=str(self.index_name),
        )

    def search(self, *, session_id: str, query: str, limit: int = 5) -> RetrievalSearchResultSet:
        query_vector = deterministic_vector(query, dimensions=self.dimensions)
        rows = sorted(
            (
                _result_from_document(document, _cosine(query_vector, document.vector))
                for document in self._documents.get(session_id, [])
            ),
            key=lambda result: result.score,
            reverse=True,
        )[: _bounded_limit(limit)]
        return RetrievalSearchResultSet(
            session_id=session_id,
            query=query,
            status="ready" if rows else "empty",
            results=rows,
        )


class LanceDBRetrievalIndex(RetrievalIndex):
    enabled = True

    def __init__(
        self,
        *,
        uri: str,
        table_name: str,
        dimensions: int = 32,
        connector: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.uri = uri
        self.index_name = table_name
        self.dimensions = dimensions
        self._connector = connector
        self._db: Optional[Any] = None

    def status(self) -> RetrievalStatus:
        try:
            table = self._table(required=False)
            count = table.count_rows() if table is not None and hasattr(table, "count_rows") else None
        except Exception:
            return RetrievalStatus(
                enabled=True,
                status="unavailable",
                index_name=self.index_name,
                message="LanceDB retrieval backend is unavailable.",
            )
        return RetrievalStatus(
            enabled=True,
            status="healthy",
            index_name=self.index_name,
            message="LanceDB retrieval projection is ready.",
            document_count=count,
        )

    def rebuild_session(self, state: Any) -> RetrievalRebuildResult:
        documents = documents_from_state(state, dimensions=self.dimensions)
        rows = [document.storage_dict() for document in documents]
        try:
            table = self._table(required=False)
            if table is None:
                self._db_connection().create_table(self.index_name, data=rows)
            else:
                table.delete(_session_filter(state.session_id))
                table.add(rows)
        except Exception as exc:
            raise RetrievalUnavailable("LanceDB retrieval backend is unavailable.") from exc
        return RetrievalRebuildResult(
            session_id=state.session_id,
            status="rebuilt",
            indexed_count=len(rows),
            index_name=str(self.index_name),
        )

    def search(self, *, session_id: str, query: str, limit: int = 5) -> RetrievalSearchResultSet:
        vector = deterministic_vector(query, dimensions=self.dimensions)
        try:
            table = self._table(required=True)
            rows = (
                table.search(vector)
                .where(_session_filter(session_id), prefilter=True)
                .limit(_bounded_limit(limit))
                .to_list()
            )
        except RetrievalUnavailable:
            raise
        except Exception as exc:
            raise RetrievalUnavailable("LanceDB retrieval backend is unavailable.") from exc
        results = [_result_from_row(row) for row in rows]
        return RetrievalSearchResultSet(
            session_id=session_id,
            query=query,
            status="ready" if results else "empty",
            results=results,
        )

    def _db_connection(self) -> Any:
        if self._db is None:
            connector = self._connector or _load_lancedb_connector()
            self._db = connector(self.uri)
        return self._db

    def _table(self, *, required: bool) -> Optional[Any]:
        db = self._db_connection()
        try:
            return db.open_table(self.index_name)
        except Exception as exc:
            if required:
                raise RetrievalUnavailable("Retrieval index has not been built yet.") from exc
            return None


def build_retrieval_index(*, data_dir: Path) -> RetrievalIndex:
    backend = os.getenv("STUDY_ANYTHING_RETRIEVAL_BACKEND", "lancedb").strip().lower()
    if backend == "memory":
        return InMemoryRetrievalIndex(
            index_name=os.getenv("LANCEDB_TABLE", "study_anything_retrieval"),
            dimensions=_int_env("LANCEDB_VECTOR_DIMENSIONS", 32),
        )
    enabled = os.getenv("LANCEDB_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return NoopRetrievalIndex()
    uri = os.getenv("LANCEDB_URI") or str(data_dir / "lancedb")
    table_name = os.getenv("LANCEDB_TABLE", "study_anything_retrieval")
    dimensions = _int_env("LANCEDB_VECTOR_DIMENSIONS", 32)
    return LanceDBRetrievalIndex(uri=uri, table_name=table_name, dimensions=dimensions)


def documents_from_state(state: Any, *, dimensions: int = 32) -> list[RetrievalDocument]:
    documents: list[RetrievalDocument] = []
    if getattr(state, "enrichment_items", None):
        for index, item in enumerate(state.enrichment_items, start=1):
            documents.append(
                RetrievalDocument(
                    document_id=f"{state.session_id}:enrichment:{index}:{item.excerpt_hash[:12]}",
                    session_id=state.session_id,
                    source_type=item.source_type,
                    reference=item.reference,
                    excerpt_hash=item.excerpt_hash,
                    locator=item.locator,
                    snippet=minimal_snippet(item.text),
                    vector=deterministic_vector(item.text, dimensions=dimensions),
                    updated_at=state.updated_at,
                )
            )
    elif getattr(state, "source", None) is not None:
        source = state.source
        documents.append(
            RetrievalDocument(
                document_id=f"{state.session_id}:source:{source.excerpt_hash[:12]}",
                session_id=state.session_id,
                source_type=source.source_type,
                reference=source.reference,
                excerpt_hash=source.excerpt_hash,
                locator=None,
                snippet=minimal_snippet(source.text),
                vector=deterministic_vector(source.text, dimensions=dimensions),
                updated_at=state.updated_at,
            )
        )
    if not documents:
        raise RetrievalProjectionRequired("A reading source or enrichment item is required.")
    return documents


def deterministic_vector(text: str, *, dimensions: int = 32) -> list[float]:
    if dimensions < 4:
        raise ValueError("Retrieval vector dimensions must be at least 4.")
    vector = [0.0 for _ in range(dimensions)]
    for token in _tokens(text):
        digest = int(sha256_text(token)[:8], 16)
        vector[digest % dimensions] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 8) for value in vector]


def minimal_snippet(text: str, *, max_chars: int = 480) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    compact = _redact_secret_like_text(compact)
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


def _load_lancedb_connector() -> Callable[[str], Any]:
    try:
        import lancedb
    except ImportError as exc:
        raise RetrievalUnavailable("Install lancedb to enable LanceDB retrieval.") from exc
    return lancedb.connect


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower())


def _cosine(left: list[float], right: list[float]) -> float:
    return round(sum(a * b for a, b in zip(left, right)), 6)


def _result_from_document(document: RetrievalDocument, score: float) -> RetrievalResult:
    return RetrievalResult(
        document_id=document.document_id,
        session_id=document.session_id,
        source_type=document.source_type,
        reference=document.reference,
        excerpt_hash=document.excerpt_hash,
        locator=document.locator,
        snippet=document.snippet,
        score=score,
    )


def _result_from_row(row: dict[str, Any]) -> RetrievalResult:
    raw_score = row.get("_distance", row.get("_score", 0.0))
    score = 0.0
    if isinstance(raw_score, (int, float)):
        score = round(1.0 / (1.0 + float(raw_score)), 6)
    return RetrievalResult(
        document_id=str(row.get("document_id") or ""),
        session_id=str(row.get("session_id") or ""),
        source_type=str(row.get("source_type") or "context"),
        reference=str(row.get("reference") or ""),
        excerpt_hash=str(row.get("excerpt_hash") or ""),
        locator=str(row["locator"]) if row.get("locator") is not None else None,
        snippet=str(row.get("snippet") or ""),
        score=score,
    )


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), 20))


def _context_source_type(source_type: str) -> str:
    allowed = {"web", "document", "video_slice", "app_context", "markdown_note", "obsidian_note"}
    return source_type if source_type in allowed else "document"


def _session_filter(session_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9:_-]+", session_id):
        raise RetrievalUnavailable("Session id cannot be used in a retrieval filter.")
    return f"session_id = '{session_id}'"


def _redact_secret_like_text(text: str) -> str:
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "[redacted]", text)
    return re.sub(
        r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}",
        r"\1=[redacted]",
        text,
    )


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
