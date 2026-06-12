"""Open-source integration matrix for product/runtime visibility."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
from typing import List


@dataclass(frozen=True)
class IntegrationStatus:
    name: str
    category: str
    target: str
    status: str
    runtime_check: str
    product_surface: str
    next_step: str

    def public_dict(self) -> dict[str, str]:
        return asdict(self)


def package_available(module_name: str) -> bool:
    return find_spec(module_name) is not None


def integration_matrix() -> List[IntegrationStatus]:
    return [
        IntegrationStatus(
            name="LangGraph",
            category="orchestration",
            target="StateGraph + Postgres checkpointer",
            status="compiled_adapter" if package_available("langgraph") else "declared_dependency",
            runtime_check="import langgraph",
            product_surface="/v1/system/status.workflow_engine",
            next_step="Soak the compiled graph and Postgres checkpointer under real self-host usage.",
        ),
        IntegrationStatus(
            name="Langfuse",
            category="observability",
            target="Self-hosted traces",
            status="compose_and_optional_client"
            if package_available("langfuse")
            else "compose_only",
            runtime_check="LANGFUSE_HOST plus optional SDK import",
            product_surface="Docker Compose + privacy-preserving node observations",
            next_step="Add retention guidance and inspect traces under a configured local project.",
        ),
        IntegrationStatus(
            name="Agent Gateway",
            category="reasoning_boundary",
            target="User-owned local/private HTTP agent",
            status="runtime_adapter",
            runtime_check="POST /v1/agents/providers kind=http_agent",
            product_surface="Agent Registry + Web provider panel",
            next_step="Add CLI and MCP adapters behind explicit plugin permissions.",
        ),
        IntegrationStatus(
            name="Ollama",
            category="user_agent_runtime",
            target="Supported through a user-owned agent gateway",
            status="external_agent_supported",
            runtime_check="User agent may call Ollama internally",
            product_surface="Docs only; no first-class model runtime in Study Anything",
            next_step="Publish an example Ollama HTTP agent plugin/gateway.",
        ),
        IntegrationStatus(
            name="FalkorDB",
            category="knowledge_graph",
            target="Privacy-preserving learning topology projection",
            status="optional_runtime_adapter"
            if package_available("falkordb")
            else "declared_dependency",
            runtime_check="GET /v1/graph/status",
            product_surface="Docker Compose + topology APIs",
            next_step="Soak idempotent projections under real self-host usage.",
        ),
        IntegrationStatus(
            name="LanceDB",
            category="semantic_retrieval",
            target="Local vector index",
            status="optional_runtime_adapter"
            if package_available("lancedb")
            else "declared_dependency",
            runtime_check="GET /v1/retrieval/status",
            product_surface="Retrieval rebuild/search APIs",
            next_step="Soak LanceDB retrieval under real self-host usage and add external Agent embeddings.",
        ),
        IntegrationStatus(
            name="Mem0",
            category="user_memory",
            target="User profile memory",
            status="adapter_stub" if package_available("mem0") else "not_installed",
            runtime_check="import mem0",
            product_surface="Roadmap",
            next_step="Add opt-in user profile memory adapter.",
        ),
        IntegrationStatus(
            name="LangMem",
            category="working_memory",
            target="Session working memory",
            status="adapter_stub" if package_available("langmem") else "not_installed",
            runtime_check="import langmem",
            product_surface="Roadmap",
            next_step="Use for graph-local memory once LangGraph executor is active.",
        ),
        IntegrationStatus(
            name="py-fsrs",
            category="spaced_repetition",
            target="Card scheduling",
            status="adapter_stub" if package_available("fsrs") else "not_installed",
            runtime_check="import fsrs",
            product_surface="Discard/keep card boundary",
            next_step="Replace mastery-only scheduling with FSRS review dates.",
        ),
        IntegrationStatus(
            name="Postgres",
            category="data",
            target="Business data + LangGraph checkpointing",
            status="session_store_ready" if package_available("psycopg") else "compose_service",
            runtime_check="app-postgres service + psycopg",
            product_surface="Docker Compose + sessions + optional LangGraph checkpoints",
            next_step="Load-test checkpoint cleanup and backup behavior.",
        ),
        IntegrationStatus(
            name="ClickHouse",
            category="observability_storage",
            target="Langfuse analytics store",
            status="compose_service",
            runtime_check="clickhouse service",
            product_surface="Langfuse dependency",
            next_step="No direct app calls; managed by Langfuse.",
        ),
        IntegrationStatus(
            name="Redis",
            category="queue_cache",
            target="Langfuse queue/cache",
            status="compose_service",
            runtime_check="redis service",
            product_surface="Langfuse dependency",
            next_step="No direct app calls until async jobs are introduced.",
        ),
        IntegrationStatus(
            name="MinIO",
            category="object_storage",
            target="Langfuse object storage",
            status="compose_service",
            runtime_check="minio service",
            product_surface="Langfuse dependency",
            next_step="No direct app calls until artifact storage is needed.",
        ),
    ]
