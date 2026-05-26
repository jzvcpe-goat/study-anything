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
            status="adapter_ready" if package_available("langgraph") else "declared_dependency",
            runtime_check="import langgraph",
            product_surface="/v1/system/status.langgraph_available",
            next_step="Replace deterministic executor with compiled StateGraph and checkpoint resume.",
        ),
        IntegrationStatus(
            name="Langfuse",
            category="observability",
            target="Self-hosted traces",
            status="compose_and_optional_client"
            if package_available("langfuse")
            else "compose_only",
            runtime_check="LANGFUSE_HOST plus optional SDK import",
            product_surface="Docker Compose + trace sink boundary",
            next_step="Emit node observations when keys are configured.",
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
            target="Knowledge topology",
            status="compose_service",
            runtime_check="falkordb service on 6379",
            product_surface="Docker Compose",
            next_step="Persist source/mastery edges from synthesist_node.",
        ),
        IntegrationStatus(
            name="LanceDB",
            category="semantic_retrieval",
            target="Local vector index",
            status="adapter_stub" if package_available("lancedb") else "not_installed",
            runtime_check="import lancedb",
            product_surface="Roadmap",
            next_step="Add reading embedding index and retrieval API.",
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
            product_surface="Docker Compose + SESSION_STORE=postgres",
            next_step="Add LangGraph checkpoint tables when the compiled graph executor replaces the alpha runner.",
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
