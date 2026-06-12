"""FastAPI app for Study Anything self-host alpha."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from study_anything import __version__
from study_anything.core.agent_audit import build_agent_audit
from study_anything.core.agent_eval import build_agent_eval_artifact
from study_anything.core.agent_registry import (
    AgentCapability,
    AgentRegistry,
    AgentRouter,
    AgentTask,
)
from study_anything.core.integrations import integration_matrix
from study_anything.core.langgraph_adapter import (
    LangGraphCheckpointResource,
    build_learning_workflow,
    langgraph_available,
)
from study_anything.core.knowledge_graph import (
    KnowledgeGraphProjectionRequired,
    KnowledgeGraphUnavailable,
    build_knowledge_graph_sink,
    projection_from_state,
)
from study_anything.core.learning_package import build_learning_package_export
from study_anything.core.pmf import LocalPmfInterestStore, build_pmf_export, compute_pmf_metrics
from study_anything.core.obsidian_export import build_obsidian_markdown_export
from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.plugin_trust import plugin_trust_policy
from study_anything.core.quality_eval import build_agent_quality_eval, quality_eval_case_export
from study_anything.core.recovery import recovery_status
from study_anything.core.store import create_session_store
from study_anything.core.sync_package import (
    MIN_PASSPHRASE_LENGTH,
    SyncPackageError,
    build_sync_payload,
    encrypt_sync_package,
    inspect_sync_package,
    preview_sync_restore,
    sync_status,
)
from study_anything.core.tracing import build_trace_sink
from study_anything.core.workflow import (
    Answer,
    new_session,
    submit_answers,
    submit_enrichment,
    submit_reading,
)
from study_anything.core.workspace import (
    LocalWorkspaceStore,
    WorkspaceAccessDenied,
    WorkspaceError,
)


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="local-user")
    track: str = Field(default="ACADEMIC")
    use_demo_provider: bool = Field(default=True)
    use_demo_agent: Optional[bool] = None
    workspace_id: Optional[str] = None


class ReadingRequest(BaseModel):
    source_type: str = Field(default="local_text")
    reference: str = Field(default="demo://source")
    title: str
    text: str


class EnrichmentItemRequest(BaseModel):
    source_type: str = Field(default="context")
    reference: str
    title: str
    text: str
    locator: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EnrichmentRequest(BaseModel):
    title: str = Field(default="Learning Enrichment Bundle")
    reference: Optional[str] = None
    items: List[EnrichmentItemRequest]


class TeachingLayersRequest(BaseModel):
    layers: List[str] = Field(default_factory=lambda: ["overview", "glossary"])
    language: str = Field(default="zh")
    level: str = Field(default="beginner")
    max_terms: int = Field(default=8)
    example_mode: str = Field(default="mixed")
    constraints: Dict[str, Any] = Field(default_factory=dict)


class AgentProviderRequest(BaseModel):
    kind: str
    label: str
    endpoint: Optional[str] = None
    base_url: Optional[str] = None
    command: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=15)
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Deprecated `/v1/models/*` compatibility fields.
    model_ids: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    secret_configured: bool = False


class AgentDefaultsRequest(BaseModel):
    user_id: str = Field(default="local-user")
    capability: str
    provider_id: str


class TestAgentProviderRequest(BaseModel):
    provider_id: str


class AgentInvokeRequest(BaseModel):
    task_type: str
    session_id: str = Field(default="manual")
    track: str = Field(default="ACADEMIC")
    source: Optional[Dict[str, Any]] = None
    quiz_items: List[Dict[str, Any]] = Field(default_factory=list)
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    rubric: Optional[str] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnswersRequest(BaseModel):
    answers: Dict[str, str]


class ResolveHitlRequest(BaseModel):
    session_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class PluginPreviewRequest(BaseModel):
    source_path: str


class PluginInstallRequest(BaseModel):
    source_path: str
    confirmed_permissions: List[str] = Field(default_factory=list)
    replace_existing: bool = False


class PmfInterestRequest(BaseModel):
    user_id: str = Field(default="local-user")
    services: List[str] = Field(default_factory=lambda: ["neural_sync"])
    contact: Optional[str] = None
    source: str = Field(default="api")
    locale: Optional[str] = None
    comment: Optional[str] = None


class PmfExportRequest(BaseModel):
    consent_to_share: bool = False
    destination: str = Field(default="self_archive")
    note: Optional[str] = None


class SyncExportRequest(BaseModel):
    passphrase: str = Field(min_length=MIN_PASSPHRASE_LENGTH)
    include_pmf: bool = True
    include_plugin_inventory: bool = True


class SyncInspectRequest(BaseModel):
    passphrase: str
    package: Dict[str, Any]


class SyncRestorePreviewRequest(BaseModel):
    passphrase: str
    package: Dict[str, Any]


class WorkspaceCreateRequest(BaseModel):
    owner_user_id: str = Field(default="local-user")
    name: str = Field(default="Personal Workspace")
    slug: Optional[str] = None
    owner_display_name: Optional[str] = None


class WorkspaceMemberRequest(BaseModel):
    acting_user_id: str = Field(default="local-user")
    member_user_id: str
    role: str = Field(default="member")
    display_name: Optional[str] = None


def _env(primary: str, legacy: str, default: str) -> str:
    return os.getenv(primary) or os.getenv(legacy) or default


data_dir = Path(_env("STUDY_ANYTHING_DATA_DIR", "NEURAL_CONSOLE_DATA_DIR", "data/api"))
project_root = Path(__file__).resolve().parents[4]
agent_registry = AgentRegistry(data_dir / "agent_registry.json")
agent_router = AgentRouter(agent_registry)
workspace_store = LocalWorkspaceStore(data_dir / "workspace_state.json")
trace_sink = build_trace_sink()
knowledge_graph_sink = build_knowledge_graph_sink()
workflow_engine = os.getenv("WORKFLOW_ENGINE", "langgraph")
langgraph_checkpoint: Optional[LangGraphCheckpointResource] = None
if workflow_engine == "langgraph":
    langgraph_checkpoint = LangGraphCheckpointResource(
        backend=os.getenv("LANGGRAPH_CHECKPOINTER", "memory"),
        database_url=os.getenv("DATABASE_URL"),
    )
    atexit.register(langgraph_checkpoint.close)
workflow = build_learning_workflow(
    agent_router,
    trace_sink=trace_sink,
    knowledge_graph_sink=knowledge_graph_sink,
    engine=workflow_engine,
    checkpointer=langgraph_checkpoint.saver if langgraph_checkpoint else None,
)
store = create_session_store(
    data_dir=data_dir,
    database_url=os.getenv("DATABASE_URL"),
    backend=os.getenv("SESSION_STORE", "json"),
)
pmf_interest_store = LocalPmfInterestStore(data_dir / "pmf_interests.json")
plugin_install_dir = Path(os.getenv("STUDY_ANYTHING_PLUGIN_INSTALL_DIR") or data_dir / "plugins")
plugin_dirs = [
    Path(value)
    for value in _env(
        "STUDY_ANYTHING_PLUGIN_DIRS",
        "NEURAL_CONSOLE_PLUGIN_DIRS",
        f"plugins{os.pathsep}data/plugins",
    ).split(os.pathsep)
    if value.strip()
]
if plugin_install_dir not in plugin_dirs:
    plugin_dirs.append(plugin_install_dir)
plugins = PluginRegistry(plugin_dirs)


def _legacy_capability(capability: str) -> AgentCapability:
    legacy = {
        "chat": AgentCapability.QUIZ_GENERATE,
        "grading": AgentCapability.ANSWER_GRADE,
        "embed": AgentCapability.EMBEDDING_CREATE,
    }
    return legacy.get(capability, AgentCapability(capability))


def create_app() -> FastAPI:
    app = FastAPI(title="Study Anything", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/v1/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/system/status")
    def system_status(user_id: str = "local-user") -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "data_dir": str(data_dir),
            "session_store": getattr(store, "backend", "unknown"),
            "session_count": len(store.list_sessions()),
            "open_hitl_count": len(store.list_hitl()),
            "langgraph_available": langgraph_available(),
            "workflow_engine": workflow.engine,
            "langgraph_checkpointer": langgraph_checkpoint.backend if langgraph_checkpoint else None,
            "telemetry_enabled": trace_sink.enabled,
            "knowledge_graph": knowledge_graph_sink.status().public_dict(),
            "sync": sync_status(),
            "agent_status": agent_registry.status(user_id),
            "model_status": {**agent_registry.status(user_id), "deprecated": True},
            "workspace_status": workspace_store.status(user_id),
            "recovery": recovery_status(project_root),
            "plugin_count": len(plugins.discover()),
            "pmf_metrics": compute_pmf_metrics(
                store.list_sessions(),
                plugins.discover(),
                pmf_interest_store.summary(),
            )["signals"],
        }

    @app.get("/v1/system/integrations")
    def system_integrations() -> list[dict[str, str]]:
        return [item.public_dict() for item in integration_matrix()]

    @app.get("/v1/recovery/status")
    def get_recovery_status() -> dict[str, object]:
        return recovery_status(project_root)

    @app.get("/v1/workspaces/status")
    def workspace_status(user_id: str = "local-user") -> dict[str, object]:
        try:
            return workspace_store.status(user_id)
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/workspaces")
    def list_workspaces(user_id: str = "local-user") -> list[dict[str, object]]:
        try:
            workspace_store.ensure_default_workspace(user_id)
            return [
                workspace.public_dict()
                for workspace in workspace_store.list_for_user(user_id)
            ]
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/workspaces")
    def create_workspace(payload: WorkspaceCreateRequest) -> dict[str, object]:
        try:
            return workspace_store.create_workspace(
                owner_user_id=payload.owner_user_id,
                name=payload.name,
                slug=payload.slug,
                owner_display_name=payload.owner_display_name,
            ).public_dict()
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/workspaces/{workspace_id}/members")
    def add_workspace_member(
        workspace_id: str,
        payload: WorkspaceMemberRequest,
    ) -> dict[str, object]:
        try:
            return workspace_store.add_member(
                workspace_id=workspace_id,
                acting_user_id=payload.acting_user_id,
                member_user_id=payload.member_user_id,
                role=payload.role,
                display_name=payload.display_name,
            ).public_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        except WorkspaceAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/metrics/pmf")
    def pmf_metrics() -> dict[str, object]:
        return compute_pmf_metrics(
            store.list_sessions(),
            plugins.discover(),
            pmf_interest_store.summary(),
        )

    @app.get("/v1/evals/quality/cases")
    def get_quality_eval_cases() -> dict[str, object]:
        return quality_eval_case_export()

    @app.get("/v1/pmf/summary")
    def pmf_interest_summary() -> dict[str, object]:
        return pmf_interest_store.summary()

    @app.post("/v1/pmf/interest")
    def record_pmf_interest(payload: PmfInterestRequest) -> dict[str, object]:
        try:
            intent = pmf_interest_store.record(
                user_id=payload.user_id,
                services=payload.services,
                contact=payload.contact,
                source=payload.source,
                locale=payload.locale,
                comment=payload.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return intent.public_dict()

    @app.post("/v1/pmf/export")
    def export_pmf(payload: PmfExportRequest) -> dict[str, object]:
        interest_summary = pmf_interest_store.summary()
        metrics = compute_pmf_metrics(
            store.list_sessions(),
            plugins.discover(),
            interest_summary,
        )
        try:
            return build_pmf_export(
                metrics,
                interest_summary,
                consent_to_share=payload.consent_to_share,
                destination=payload.destination,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/sync/status")
    def get_sync_status() -> dict[str, object]:
        return sync_status()

    @app.post("/v1/sync/export")
    def export_sync_package(payload: SyncExportRequest) -> dict[str, object]:
        sync_payload = build_sync_payload(
            sessions=store.list_sessions(),
            data_dir=data_dir,
            plugin_statuses=plugins.discover(),
            include_pmf=payload.include_pmf,
            include_plugin_inventory=payload.include_plugin_inventory,
        )
        try:
            return encrypt_sync_package(
                sync_payload,
                passphrase=payload.passphrase,
            ).public_dict()
        except SyncPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/sync/inspect")
    def inspect_sync_package_endpoint(payload: SyncInspectRequest) -> dict[str, object]:
        try:
            return inspect_sync_package(
                payload.package,
                passphrase=payload.passphrase,
            )
        except SyncPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/sync/restore-preview")
    def preview_sync_restore_endpoint(payload: SyncRestorePreviewRequest) -> dict[str, object]:
        try:
            return preview_sync_restore(
                payload.package,
                passphrase=payload.passphrase,
                current_sessions=store.list_sessions(),
            )
        except SyncPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/graph/status")
    def knowledge_graph_status() -> dict[str, object]:
        return knowledge_graph_sink.status().public_dict()

    @app.get("/v1/agents/status")
    def agent_status(user_id: str = "local-user") -> dict[str, object]:
        return agent_registry.status(user_id)

    @app.post("/v1/agents/providers")
    def add_agent_provider(payload: AgentProviderRequest) -> dict[str, object]:
        provider = agent_registry.configure_provider(**payload.model_dump())
        return provider.public_dict()

    @app.post("/v1/agents/defaults")
    def set_agent_default(payload: AgentDefaultsRequest) -> dict[str, object]:
        try:
            agent_registry.set_default(payload.user_id, payload.capability, payload.provider_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return agent_registry.status(payload.user_id)

    @app.post("/v1/agents/test")
    def test_agent_provider(payload: TestAgentProviderRequest) -> dict[str, object]:
        try:
            return agent_registry.test_provider(payload.provider_id).__dict__
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/agents/{provider_id}/invoke")
    def invoke_agent(
        provider_id: str,
        payload: AgentInvokeRequest,
    ) -> dict[str, object]:
        try:
            result = agent_router.invoke_provider(
                provider_id,
                task=AgentTask(
                    task_type=payload.task_type,
                    session_id=payload.session_id,
                    track=payload.track,
                    source=payload.source,
                    quiz_items=payload.quiz_items,
                    answers=payload.answers,
                    rubric=payload.rubric,
                    constraints=payload.constraints,
                    metadata=payload.metadata,
                ),
            )
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result.public_dict()

    @app.get("/v1/models/status")
    def model_status(user_id: str = "local-user") -> dict[str, object]:
        return {**agent_registry.status(user_id), "deprecated": True}

    @app.post("/v1/models/providers")
    def add_model_provider(payload: AgentProviderRequest) -> dict[str, object]:
        provider = agent_registry.configure_provider(**payload.model_dump())
        values = provider.public_dict()
        values["deprecated"] = True
        return values

    @app.post("/v1/models/defaults")
    def set_model_default(payload: AgentDefaultsRequest) -> dict[str, object]:
        try:
            agent_registry.set_default(payload.user_id, _legacy_capability(payload.capability), payload.provider_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {**agent_registry.status(payload.user_id), "deprecated": True}

    @app.post("/v1/models/test")
    def test_model_provider(payload: TestAgentProviderRequest) -> dict[str, object]:
        try:
            values = agent_registry.test_provider(payload.provider_id).__dict__
            values["deprecated"] = True
            return values
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/sessions")
    def create_session(payload: CreateSessionRequest) -> dict[str, object]:
        use_demo = (
            payload.use_demo_agent
            if payload.use_demo_agent is not None
            else payload.use_demo_provider
        )
        try:
            if payload.workspace_id:
                workspace_store.assert_permission(
                    payload.user_id,
                    payload.workspace_id,
                    "create_sessions",
                )
                workspace_id = payload.workspace_id
            else:
                workspace_id = workspace_store.ensure_default_workspace(
                    payload.user_id
                ).workspace_id
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        except WorkspaceAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if use_demo:
            agent_registry.set_demo_defaults(payload.user_id)
        state = store.save(
            new_session(
                payload.user_id,
                payload.track,
                workspace_id=workspace_id,
                trace_sink=trace_sink,
            )
        )
        return state.public_dict()

    @app.get("/v1/sessions")
    def list_sessions(
        user_id: str = "local-user",
        workspace_id: Optional[str] = None,
    ) -> list[dict[str, object]]:
        sessions = store.list_sessions()
        if workspace_id:
            try:
                workspace_store.assert_permission(
                    user_id,
                    workspace_id,
                    "read_sessions",
                )
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Workspace not found") from exc
            except WorkspaceAccessDenied as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            sessions = [state for state in sessions if state.workspace_id == workspace_id]
        return [state.public_dict() for state in sessions]

    @app.get("/v1/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, object]:
        try:
            return store.get(session_id).public_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc

    @app.post("/v1/sessions/{session_id}/reading")
    def add_reading(session_id: str, payload: ReadingRequest) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        state = submit_reading(
            state,
            source_type=payload.source_type,
            reference=payload.reference,
            title=payload.title,
            text=payload.text,
            trace_sink=trace_sink,
        )
        return store.save(state).public_dict()

    @app.post("/v1/sessions/{session_id}/enrichment")
    def add_enrichment(session_id: str, payload: EnrichmentRequest) -> dict[str, object]:
        try:
            state = store.get(session_id)
            state = submit_enrichment(
                state,
                items=[item.model_dump() for item in payload.items],
                title=payload.title,
                reference=payload.reference,
                trace_sink=trace_sink,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = store.save(state)
        return {
            "schema_version": "learning-enrichment-v1",
            "session_id": state.session_id,
            "source": {
                "source_type": state.source.source_type,
                "reference": state.source.reference,
                "title": state.source.title,
                "excerpt_hash": state.source.excerpt_hash,
                "verified": state.source.verified,
            } if state.source else None,
            "item_count": len(state.enrichment_items),
            "items": [
                {
                    "source_type": item.source_type,
                    "reference": item.reference,
                    "title": item.title,
                    "excerpt_hash": item.excerpt_hash,
                    "locator": item.locator,
                    "metadata": item.metadata,
                }
                for item in state.enrichment_items
            ],
            "stage": state.stage,
        }

    @app.post("/v1/sessions/{session_id}/teaching-layers")
    def generate_teaching_layers(
        session_id: str,
        payload: TeachingLayersRequest,
    ) -> dict[str, object]:
        try:
            state = store.get(session_id)
            state = workflow.teaching_layers(
                state,
                layers=payload.layers,
                constraints={
                    "language": payload.language,
                    "level": payload.level,
                    "max_terms": payload.max_terms,
                    "example_mode": payload.example_mode,
                    **payload.constraints,
                },
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = store.save(state)
        return {
            "schema_version": "teaching-layers-v1",
            "session_id": state.session_id,
            "layers": state.teaching_layers,
            "stage": state.stage,
            "open_hitl": [item.__dict__ for item in state.hitl_interrupts if item.status == "open"],
        }

    @app.post("/v1/sessions/{session_id}/run")
    def run_session(session_id: str) -> dict[str, object]:
        try:
            state = workflow.run(store.get(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        return store.save(state).public_dict()

    @app.post("/v1/sessions/{session_id}/resume")
    def resume_session(session_id: str) -> dict[str, object]:
        return run_session(session_id)

    @app.post("/v1/sessions/{session_id}/answers")
    def answer_session(session_id: str, payload: AnswersRequest) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        answers = [Answer(item_id=item_id, text=text) for item_id, text in payload.answers.items()]
        state = submit_answers(state, answers, trace_sink=trace_sink)
        state = workflow.run(state)
        return store.save(state).public_dict()

    @app.post("/v1/sessions/{session_id}/discard")
    def discard_session(session_id: str) -> dict[str, object]:
        try:
            state = workflow.discard(store.get(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        return store.save(state).public_dict()

    @app.get("/v1/sessions/{session_id}/mastery")
    def get_mastery(session_id: str) -> dict[str, object]:
        try:
            mastery = store.get(session_id).mastery
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        return {"level": mastery.level, "bloom": mastery.bloom}

    @app.get("/v1/sessions/{session_id}/topology")
    def get_topology(session_id: str) -> dict[str, object]:
        try:
            store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        try:
            return knowledge_graph_sink.topology(session_id).public_dict()
        except KnowledgeGraphUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/sessions/{session_id}/topology/rebuild")
    def rebuild_topology(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        if not knowledge_graph_sink.enabled:
            raise HTTPException(status_code=503, detail="Knowledge graph projection is disabled.")
        try:
            result = knowledge_graph_sink.project(projection_from_state(state))
            topology = knowledge_graph_sink.topology(session_id)
        except KnowledgeGraphProjectionRequired as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KnowledgeGraphUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {**result.public_dict(), "topology": topology.public_dict()}

    @app.get("/v1/hitl")
    def list_hitl() -> list[dict[str, object]]:
        return [item.__dict__ for item in store.list_hitl()]

    @app.post("/v1/hitl/{task_id}/resolve")
    def resolve_hitl(task_id: str, payload: ResolveHitlRequest) -> dict[str, object]:
        try:
            state = workflow.resolve_hitl(store.get(payload.session_id), task_id, payload.payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return store.save(state).public_dict()

    @app.get("/v1/sessions/{session_id}/events")
    def get_events(session_id: str) -> list[dict[str, object]]:
        try:
            return [event.__dict__ for event in store.get(session_id).events]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc

    @app.get("/v1/sessions/{session_id}/agent-audit")
    def get_agent_audit(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        return build_agent_audit(
            state,
            agent_status=agent_registry.status(state.user_id),
        )

    @app.get("/v1/sessions/{session_id}/agent-eval")
    def get_deprecated_agent_eval(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        return build_agent_audit(
            state,
            agent_status=agent_registry.status(state.user_id),
            deprecated_alias=True,
        )

    @app.get("/v1/sessions/{session_id}/agent-eval/artifact")
    def get_agent_eval_artifact(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        audit = build_agent_audit(
            state,
            agent_status=agent_registry.status(state.user_id),
        )
        return build_agent_eval_artifact(audit)

    @app.get("/v1/sessions/{session_id}/agent-eval/quality")
    def get_agent_quality_eval(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        audit = build_agent_audit(
            state,
            agent_status=agent_registry.status(state.user_id),
        )
        artifact = build_agent_eval_artifact(audit)
        return build_agent_quality_eval(
            state,
            agent_audit=audit,
            agent_eval_artifact=artifact,
        )

    @app.get("/v1/sessions/{session_id}/exports/obsidian")
    def get_obsidian_export(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
            return build_obsidian_markdown_export(state)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/sessions/{session_id}/exports/learning-package")
    def get_learning_package_export(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
            return build_learning_package_export(state)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/plugins")
    def list_plugins() -> list[dict[str, object]]:
        return [status.public_dict() for status in plugins.discover()]

    @app.get("/v1/plugins/trust-policy")
    def get_plugin_trust_policy() -> dict[str, object]:
        return plugin_trust_policy()

    @app.get("/v1/plugins/registry-review")
    def get_plugin_registry_review() -> dict[str, object]:
        return plugins.registry_review().public_dict()

    @app.post("/v1/plugins/preview")
    def preview_plugin(payload: PluginPreviewRequest) -> dict[str, object]:
        status = plugins.preview_local(Path(payload.source_path).expanduser())
        return {
            **status.public_dict(),
            "install_dir": str(plugin_install_dir),
            "requires_confirmation": bool(status.manifest and status.manifest.permissions),
        }

    @app.post("/v1/plugins/install")
    def install_plugin(payload: PluginInstallRequest) -> dict[str, object]:
        source_path = Path(payload.source_path).expanduser()
        preview = plugins.preview_local(source_path)
        if preview.manifest is None:
            raise HTTPException(status_code=400, detail=preview.message)
        expected_permissions = sorted(preview.manifest.permissions)
        confirmed_permissions = sorted(set(payload.confirmed_permissions))
        if confirmed_permissions != expected_permissions:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Plugin permissions must be explicitly confirmed before installation.",
                    "expected_permissions": expected_permissions,
                    "confirmed_permissions": confirmed_permissions,
                },
            )
        try:
            status = plugins.install_local(
                source_path,
                plugin_install_dir,
                replace_existing=payload.replace_existing,
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            **status.public_dict(),
            "install_dir": str(plugin_install_dir),
            "requires_confirmation": False,
        }

    return app


app = create_app()
