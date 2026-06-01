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
from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.store import create_session_store
from study_anything.core.tracing import build_trace_sink
from study_anything.core.workflow import Answer, new_session, submit_answers, submit_reading


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="local-user")
    track: str = Field(default="ACADEMIC")
    use_demo_provider: bool = Field(default=True)
    use_demo_agent: Optional[bool] = None


class ReadingRequest(BaseModel):
    source_type: str = Field(default="local_text")
    reference: str = Field(default="demo://source")
    title: str
    text: str


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


def _env(primary: str, legacy: str, default: str) -> str:
    return os.getenv(primary) or os.getenv(legacy) or default


data_dir = Path(_env("STUDY_ANYTHING_DATA_DIR", "NEURAL_CONSOLE_DATA_DIR", "data/api"))
agent_registry = AgentRegistry(data_dir / "agent_registry.json")
agent_router = AgentRouter(agent_registry)
trace_sink = build_trace_sink()
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
    engine=workflow_engine,
    checkpointer=langgraph_checkpoint.saver if langgraph_checkpoint else None,
)
store = create_session_store(
    data_dir=data_dir,
    database_url=os.getenv("DATABASE_URL"),
    backend=os.getenv("SESSION_STORE", "json"),
)
plugin_dirs = [
    Path(value)
    for value in _env(
        "STUDY_ANYTHING_PLUGIN_DIRS",
        "NEURAL_CONSOLE_PLUGIN_DIRS",
        f"plugins{os.pathsep}data/plugins",
    ).split(os.pathsep)
    if value.strip()
]
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
            "agent_status": agent_registry.status(user_id),
            "model_status": {**agent_registry.status(user_id), "deprecated": True},
            "plugin_count": len(plugins.discover()),
        }

    @app.get("/v1/system/integrations")
    def system_integrations() -> list[dict[str, str]]:
        return [item.public_dict() for item in integration_matrix()]

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
        use_demo = payload.use_demo_agent if payload.use_demo_agent is not None else payload.use_demo_provider
        if use_demo:
            agent_registry.set_demo_defaults(payload.user_id)
        state = store.save(new_session(payload.user_id, payload.track, trace_sink=trace_sink))
        return state.public_dict()

    @app.get("/v1/sessions")
    def list_sessions() -> list[dict[str, object]]:
        return [state.public_dict() for state in store.list_sessions()]

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

    @app.get("/v1/plugins")
    def list_plugins() -> list[dict[str, object]]:
        return [status.public_dict() for status in plugins.discover()]

    return app


app = create_app()
