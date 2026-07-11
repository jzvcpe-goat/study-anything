"""FastAPI reference harness with the Study Anything adapter."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from study_anything import __version__
from study_anything.core.agent_audit import build_agent_audit
from study_anything.core.agent_eval import (
    agent_eval_policy,
    build_agent_eval_artifact,
    build_agent_eval_report,
)
from study_anything.core.agent_registry import (
    AgentCapability,
    AgentConfigurationRequired,
    AgentProviderUnavailable,
    AgentRegistry,
    AgentResultInvalid,
    AgentRouter,
    AgentTask,
)
from study_anything.core.agent_endpoint_policy import load_agent_endpoint_policy
from study_anything.core.api_security import load_api_security_config
from study_anything.core.hosted_identity import (
    HostedAuthenticationError,
    HostedPrincipal,
)
from study_anything.core.commercial_readiness import (
    build_commercial_readiness,
    summarize_commercial_readiness,
)
from study_anything.core.deployment import build_deployment_guide
from study_anything.core.integrations import integration_matrix
from study_anything.core.importer_runtime import ImporterRuntime, ImporterRuntimeError
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
from study_anything.core.learning_enrichment import build_learning_enrichment_artifact
from study_anything.core.learning_context import (
    LEARNING_ENRICHMENT_SCHEMA_VERSION,
    LEARNING_CONTEXT_SCHEMA_VERSION,
    validate_learning_context_package,
)
from study_anything.core.learning_package import build_learning_package_export
from study_anything.core.pmf import (
    LocalPmfInterestStore,
    build_adoption_telemetry,
    build_pmf_export,
    build_pmf_readiness,
    compute_pmf_metrics,
)
from study_anything.core.obsidian_export import build_obsidian_markdown_export
from study_anything.core.plugin_registry import PluginRegistry
from study_anything.core.plugin_sdk import (
    plugin_capability_index,
    plugin_sdk_contract,
    validate_plugin_package,
)
from study_anything.core.plugin_trust import plugin_trust_policy
from study_anything.core.quality_eval import build_agent_quality_eval, quality_eval_case_export
from study_anything.core.recovery import recovery_status
from study_anything.core.retrieval import (
    RetrievalProjectionRequired,
    RetrievalUnavailable,
    build_retrieval_index,
)
from study_anything.core.retrieval_eval import (
    RetrievalQualityInput,
    build_retrieval_quality_eval,
    retrieval_quality_case_export,
)
from study_anything.core.second_brain_handoff import build_second_brain_handoff
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
    LOCAL_TENANT_ID,
    LocalWorkspaceStore,
    WorkspaceAccessDenied,
    WorkspaceError,
)


SESSION_PATH_PATTERN = re.compile(r"^/v1/sessions/([^/]+)(?:/|$)")
SESSION_CREATION_ROUTES = {"from-context-package", "from-retrieval"}
HOSTED_BLOCKED_PREFIXES = (
    "/v1/adoption",
    "/v1/importers",
    "/v1/metrics",
    "/v1/pmf",
    "/v1/plugins",
    "/v1/recovery",
    "/v1/sync",
)
HOSTED_PRINCIPAL_ID_PATTERN = re.compile(r"^prn_[0-9a-f]{32}$")


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
    source_type: str = Field(default="web")
    reference: str
    title: str
    text: str
    locator: Optional[str] = None
    excerpt_hash: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    redaction_policy: str = Field(default="reference_only")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EnrichmentRequest(BaseModel):
    title: str = Field(default="Learning Enrichment Bundle")
    reference: Optional[str] = None
    items: List[EnrichmentItemRequest]


class LearningContextPackageRequest(BaseModel):
    package: Dict[str, Any]


class LearningContextSessionRequest(BaseModel):
    package: Dict[str, Any]
    user_id: str = Field(default="local-user")
    track: Optional[str] = None
    use_demo_provider: bool = Field(default=True)
    use_demo_agent: Optional[bool] = None
    workspace_id: Optional[str] = None


class ImporterRunRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    confirmed_permissions: List[str] = Field(default_factory=list)
    allow_network: bool = Field(default=False)
    include_text: bool = Field(default=True)


class RetrievalSessionRequest(BaseModel):
    source_session_id: str
    query: str
    limit: int = Field(default=5, ge=1, le=20)
    user_id: str = Field(default="retrieval-user")
    track: Optional[str] = None
    use_demo_provider: bool = Field(default=True)
    use_demo_agent: Optional[bool] = None
    workspace_id: Optional[str] = None


class RetrievalSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=20)


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


class PluginValidatePackageRequest(BaseModel):
    source_path: str


class PluginInstallRequest(BaseModel):
    source_path: str
    confirmed_permissions: List[str] = Field(default_factory=list)
    replace_existing: bool = False
    approve_install: bool = False
    approval_note: Optional[str] = None


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
agent_endpoint_policy = load_agent_endpoint_policy(os.environ)
agent_registry = AgentRegistry(
    data_dir / "agent_registry.json",
    endpoint_policy=agent_endpoint_policy,
)
agent_router = AgentRouter(agent_registry)
workspace_store = LocalWorkspaceStore(data_dir / "workspace_state.json")
trace_sink = build_trace_sink()
knowledge_graph_sink = build_knowledge_graph_sink()
retrieval_index = build_retrieval_index(data_dir=data_dir)
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
plugin_quarantine_dir = Path(
    os.getenv("STUDY_ANYTHING_PLUGIN_QUARANTINE_DIR") or data_dir / "plugins-quarantine"
)
plugin_source_dirs = [
    Path(value)
    for value in (
        os.getenv("STUDY_ANYTHING_PLUGIN_SOURCE_DIRS")
        or f"{project_root / 'plugins'}{os.pathsep}{data_dir / 'plugin-intake'}"
    ).split(os.pathsep)
    if value.strip()
]
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


def _plugin_source_from_intake(source_name: str) -> Path:
    normalized = source_name.strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or Path(normalized).name != normalized
        or "/" in normalized
        or "\\" in normalized
    ):
        raise HTTPException(
            status_code=400,
            detail="Plugin source_path must be one intake directory name, not a filesystem path.",
        )

    matches: list[Path] = []
    for configured_root in plugin_source_dirs:
        try:
            root = configured_root.expanduser().resolve(strict=True)
            candidates = list(root.iterdir())
        except OSError:
            continue
        for candidate in candidates:
            if candidate.name != normalized:
                continue
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                continue
            if resolved.parent == root and resolved.is_dir():
                matches.append(resolved)

    unique_matches = list(dict.fromkeys(matches))
    if not unique_matches:
        raise HTTPException(
            status_code=404,
            detail="Plugin source was not found in a configured intake directory.",
        )
    if len(unique_matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Plugin source name is ambiguous across configured intake directories.",
        )
    return unique_matches[0]


def _hosted_principal(request: Request) -> HostedPrincipal | None:
    principal = getattr(request.state, "hosted_principal", None)
    return principal if isinstance(principal, HostedPrincipal) else None


def _actor_context(
    request: Request,
    requested_user_id: str,
) -> tuple[str, Optional[str], Optional[str]]:
    principal = _hosted_principal(request)
    if principal is None:
        return requested_user_id, None, None
    return principal.principal_id, principal.tenant_id, principal.display_name


def _session_id_from_path(path: str) -> str | None:
    match = SESSION_PATH_PATTERN.match(path)
    if match is None or match.group(1) in SESSION_CREATION_ROUTES:
        return None
    return match.group(1)


def _hosted_error(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "schema_version": "study-anything-hosted-authorization-error-v1",
            "status": "not_found" if status_code == 404 else "forbidden",
            "code": code,
            "detail": detail,
            "raw_identity_claims_included": False,
            "tenant_id_included": False,
        },
    )


def create_app() -> FastAPI:
    api_security = load_api_security_config(os.environ)
    runtime_agent_endpoint_policy = load_agent_endpoint_policy(os.environ)
    agent_registry.endpoint_policy = runtime_agent_endpoint_policy
    app = FastAPI(title="Delivery Clearance: Study Anything Adapter", version=__version__)
    app.state.api_security = api_security
    app.state.agent_endpoint_policy = runtime_agent_endpoint_policy
    if api_security.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(api_security.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @app.middleware("http")
    async def enforce_api_security(request: Request, call_next: Any) -> Any:
        is_public_health = request.url.path == "/v1/health"
        request.state.hosted_principal = None
        if request.method != "OPTIONS" and not is_public_health:
            authorization = request.headers.get("Authorization")
            if api_security.token_required and not api_security.authorises(authorization):
                return JSONResponse(
                    status_code=401,
                    content={
                        "schema_version": "study-anything-api-auth-error-v1",
                        "status": "unauthorized",
                        "detail": "A valid local API bearer token is required.",
                        "secret_values_included": False,
                    },
                    headers={
                        "WWW-Authenticate": "Bearer",
                        "X-Study-Anything-Auth-Mode": api_security.auth_mode,
                    },
                )
            if api_security.hosted_identity is not None:
                try:
                    request.state.hosted_principal = api_security.hosted_identity.authenticate(
                        authorization
                    )
                except HostedAuthenticationError:
                    return JSONResponse(
                        status_code=401,
                        content={
                            "schema_version": "study-anything-api-auth-error-v1",
                            "status": "unauthorized",
                            "detail": "A valid hosted bearer token is required.",
                            "secret_values_included": False,
                            "raw_token_claims_included": False,
                        },
                        headers={
                            "WWW-Authenticate": "Bearer",
                            "X-Study-Anything-Auth-Mode": api_security.auth_mode,
                        },
                    )

        principal = _hosted_principal(request)
        if principal is not None and request.method != "OPTIONS":
            if any(request.url.path.startswith(prefix) for prefix in HOSTED_BLOCKED_PREFIXES):
                return _hosted_error(
                    403,
                    "hosted_route_not_tenant_scoped",
                    "This route is unavailable until its storage is tenant-scoped.",
                )
            session_id = _session_id_from_path(request.url.path)
            if session_id is not None:
                try:
                    state = store.get(session_id, tenant_id=principal.tenant_id)
                except KeyError:
                    return _hosted_error(404, "session_not_found", "Session not found.")
                if state.workspace_id is None:
                    return _hosted_error(404, "session_not_found", "Session not found.")
                permission = (
                    "read_sessions" if request.method in {"GET", "HEAD"} else "write_sessions"
                )
                try:
                    workspace_store.assert_permission(
                        principal.principal_id,
                        state.workspace_id,
                        permission,
                        tenant_id=principal.tenant_id,
                    )
                except KeyError:
                    return _hosted_error(404, "session_not_found", "Session not found.")
                except WorkspaceAccessDenied:
                    return _hosted_error(
                        403,
                        "workspace_permission_denied",
                        "The authenticated principal cannot perform this session action.",
                    )
        response = await call_next(request)
        response.headers["X-Study-Anything-Auth-Mode"] = api_security.auth_mode
        return response

    @app.get("/v1/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "api_security": api_security.public_dict(),
        }

    @app.get("/v1/identity/me")
    def identity_me(request: Request) -> dict[str, object]:
        principal = _hosted_principal(request)
        if principal is None:
            return {
                "schema_version": "study-anything-hosted-identity-v1",
                "authentication_mode": api_security.auth_mode,
                "hosted_principal": False,
                "local_operator": True,
                "raw_identity_claims_included": False,
            }
        workspace_store.ensure_identity(
            principal.principal_id,
            principal.display_name,
            tenant_id=principal.tenant_id,
        )
        return principal.public_dict()

    @app.get("/v1/system/status")
    def system_status(request: Request, user_id: str = "local-user") -> dict[str, object]:
        actor_user_id, tenant_id, display_name = _actor_context(request, user_id)
        sessions = store.list_sessions(tenant_id=tenant_id)
        commercial_readiness = build_commercial_readiness(version=__version__)
        return {
            "status": "ok",
            "version": __version__,
            "data_dir": "<local-data-dir>",
            "data_dir_path_included": False,
            "api_security": api_security.public_dict(),
            "session_store": getattr(store, "backend", "unknown"),
            "session_count": len(sessions),
            "open_hitl_count": len(store.list_hitl(tenant_id=tenant_id)),
            "langgraph_available": langgraph_available(),
            "workflow_engine": workflow.engine,
            "langgraph_checkpointer": langgraph_checkpoint.backend if langgraph_checkpoint else None,
            "telemetry_enabled": trace_sink.enabled,
            "knowledge_graph": knowledge_graph_sink.status().public_dict(),
            "retrieval": retrieval_index.status().public_dict(),
            "sync": sync_status(),
            "agent_status": agent_registry.status(
                actor_user_id,
                scope_id=actor_user_id if tenant_id is not None else None,
            ),
            "model_status": {
                **agent_registry.status(
                    actor_user_id,
                    scope_id=actor_user_id if tenant_id is not None else None,
                ),
                "deprecated": True,
            },
            "workspace_status": workspace_store.status(
                actor_user_id,
                tenant_id=tenant_id or LOCAL_TENANT_ID,
                display_name=display_name,
            ),
            "recovery": recovery_status(project_root),
            "commercial_readiness": summarize_commercial_readiness(commercial_readiness),
            "plugin_count": len(plugins.discover()),
            "pmf_metrics": compute_pmf_metrics(
                sessions,
                plugins.discover(),
                None if tenant_id is not None else pmf_interest_store.summary(),
            )["signals"],
        }

    @app.get("/v1/system/integrations")
    def system_integrations() -> list[dict[str, str]]:
        return [item.public_dict() for item in integration_matrix()]

    @app.get("/v1/deployment/guide")
    def deployment_guide() -> dict[str, object]:
        return build_deployment_guide(project_root, version=__version__)

    @app.get("/v1/commercial/readiness")
    def commercial_readiness() -> dict[str, object]:
        return build_commercial_readiness(version=__version__)

    @app.get("/v1/recovery/status")
    def get_recovery_status() -> dict[str, object]:
        return recovery_status(project_root)

    @app.get("/v1/workspaces/status")
    def workspace_status(request: Request, user_id: str = "local-user") -> dict[str, object]:
        actor_user_id, tenant_id, display_name = _actor_context(request, user_id)
        try:
            return workspace_store.status(
                actor_user_id,
                tenant_id=tenant_id or LOCAL_TENANT_ID,
                display_name=display_name,
            )
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/workspaces")
    def list_workspaces(
        request: Request,
        user_id: str = "local-user",
    ) -> list[dict[str, object]]:
        actor_user_id, tenant_id, display_name = _actor_context(request, user_id)
        workspace_tenant_id = tenant_id or LOCAL_TENANT_ID
        try:
            workspace_store.ensure_default_workspace(
                actor_user_id,
                display_name,
                tenant_id=workspace_tenant_id,
            )
            return [
                workspace.public_dict()
                for workspace in workspace_store.list_for_user(
                    actor_user_id,
                    tenant_id=workspace_tenant_id,
                )
            ]
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/workspaces")
    def create_workspace(
        request: Request,
        payload: WorkspaceCreateRequest,
    ) -> dict[str, object]:
        owner_user_id, tenant_id, display_name = _actor_context(
            request,
            payload.owner_user_id,
        )
        try:
            return workspace_store.create_workspace(
                owner_user_id=owner_user_id,
                name=payload.name,
                slug=payload.slug,
                owner_display_name=display_name or payload.owner_display_name,
                tenant_id=tenant_id or LOCAL_TENANT_ID,
            ).public_dict()
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/workspaces/{workspace_id}/members")
    def add_workspace_member(
        request: Request,
        workspace_id: str,
        payload: WorkspaceMemberRequest,
    ) -> dict[str, object]:
        acting_user_id, tenant_id, _ = _actor_context(request, payload.acting_user_id)
        if tenant_id is not None and not HOSTED_PRINCIPAL_ID_PATTERN.fullmatch(
            payload.member_user_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Hosted workspace members must use an opaque principal_id from /v1/identity/me.",
            )
        try:
            return workspace_store.add_member(
                workspace_id=workspace_id,
                acting_user_id=acting_user_id,
                member_user_id=payload.member_user_id,
                role=payload.role,
                display_name=payload.display_name,
                tenant_id=tenant_id or LOCAL_TENANT_ID,
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

    @app.get("/v1/adoption/telemetry")
    def adoption_telemetry() -> dict[str, object]:
        interest_summary = pmf_interest_store.summary()
        metrics = compute_pmf_metrics(
            store.list_sessions(),
            plugins.discover(),
            interest_summary,
        )
        return build_adoption_telemetry(metrics, interest_summary)

    @app.get("/v1/pmf/readiness")
    def pmf_readiness() -> dict[str, object]:
        interest_summary = pmf_interest_store.summary()
        metrics = compute_pmf_metrics(
            store.list_sessions(),
            plugins.discover(),
            interest_summary,
        )
        telemetry = build_adoption_telemetry(metrics, interest_summary)
        return build_pmf_readiness(telemetry)

    @app.get("/v1/evals/quality/cases")
    def get_quality_eval_cases() -> dict[str, object]:
        return quality_eval_case_export()

    @app.get("/v1/evals/policy")
    def get_agent_eval_policy() -> dict[str, object]:
        return agent_eval_policy()

    @app.get("/v1/evals/retrieval/cases")
    def get_retrieval_eval_cases() -> dict[str, object]:
        return retrieval_quality_case_export()

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

    @app.get("/v1/retrieval/status")
    def retrieval_status() -> dict[str, object]:
        return retrieval_index.status().public_dict()

    @app.get("/v1/agents/status")
    def agent_status(request: Request, user_id: str = "local-user") -> dict[str, object]:
        actor_user_id, tenant_id, _ = _actor_context(request, user_id)
        return agent_registry.status(
            actor_user_id,
            scope_id=actor_user_id if tenant_id is not None else None,
        )

    @app.post("/v1/agents/providers")
    def add_agent_provider(
        request: Request,
        payload: AgentProviderRequest,
    ) -> dict[str, object]:
        principal = _hosted_principal(request)
        try:
            provider = agent_registry.configure_provider(
                **payload.model_dump(),
                scope_id=principal.principal_id if principal is not None else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return provider.public_dict()

    @app.post("/v1/agents/defaults")
    def set_agent_default(
        request: Request,
        payload: AgentDefaultsRequest,
    ) -> dict[str, object]:
        actor_user_id, tenant_id, _ = _actor_context(request, payload.user_id)
        scope_id = actor_user_id if tenant_id is not None else None
        try:
            agent_registry.set_default(
                actor_user_id,
                payload.capability,
                payload.provider_id,
                scope_id=scope_id,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return agent_registry.status(actor_user_id, scope_id=scope_id)

    @app.post("/v1/agents/test")
    def test_agent_provider(
        request: Request,
        payload: TestAgentProviderRequest,
    ) -> dict[str, object]:
        principal = _hosted_principal(request)
        try:
            return agent_registry.test_provider(
                payload.provider_id,
                scope_id=principal.principal_id if principal is not None else None,
            ).public_dict()
        except (KeyError, ValueError, AgentConfigurationRequired) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/agents/{provider_id}/invoke")
    def invoke_agent(
        request: Request,
        provider_id: str,
        payload: AgentInvokeRequest,
    ) -> dict[str, object]:
        principal = _hosted_principal(request)
        try:
            result = agent_router.invoke_provider(
                provider_id,
                scope_id=principal.principal_id if principal is not None else None,
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
        except AgentConfigurationRequired as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AgentResultInvalid as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result.public_dict()

    @app.get("/v1/models/status")
    def model_status(request: Request, user_id: str = "local-user") -> dict[str, object]:
        actor_user_id, tenant_id, _ = _actor_context(request, user_id)
        return {
            **agent_registry.status(
                actor_user_id,
                scope_id=actor_user_id if tenant_id is not None else None,
            ),
            "deprecated": True,
        }

    @app.post("/v1/models/providers")
    def add_model_provider(
        request: Request,
        payload: AgentProviderRequest,
    ) -> dict[str, object]:
        principal = _hosted_principal(request)
        try:
            provider = agent_registry.configure_provider(
                **payload.model_dump(),
                scope_id=principal.principal_id if principal is not None else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        values = provider.public_dict()
        values["deprecated"] = True
        return values

    @app.post("/v1/models/defaults")
    def set_model_default(
        request: Request,
        payload: AgentDefaultsRequest,
    ) -> dict[str, object]:
        actor_user_id, tenant_id, _ = _actor_context(request, payload.user_id)
        scope_id = actor_user_id if tenant_id is not None else None
        try:
            agent_registry.set_default(
                actor_user_id,
                _legacy_capability(payload.capability),
                payload.provider_id,
                scope_id=scope_id,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {**agent_registry.status(actor_user_id, scope_id=scope_id), "deprecated": True}

    @app.post("/v1/models/test")
    def test_model_provider(
        request: Request,
        payload: TestAgentProviderRequest,
    ) -> dict[str, object]:
        principal = _hosted_principal(request)
        try:
            values = agent_registry.test_provider(
                payload.provider_id,
                scope_id=principal.principal_id if principal is not None else None,
            ).public_dict()
            values["deprecated"] = True
            return values
        except (KeyError, ValueError, AgentConfigurationRequired) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/sessions")
    def create_session(
        request: Request,
        payload: CreateSessionRequest,
    ) -> dict[str, object]:
        actor_user_id, tenant_id, display_name = _actor_context(request, payload.user_id)
        workspace_tenant_id = tenant_id or LOCAL_TENANT_ID
        use_demo = (
            payload.use_demo_agent
            if payload.use_demo_agent is not None
            else payload.use_demo_provider
        )
        try:
            if payload.workspace_id:
                workspace_store.assert_permission(
                    actor_user_id,
                    payload.workspace_id,
                    "create_sessions",
                    tenant_id=workspace_tenant_id,
                )
                workspace_id = payload.workspace_id
            else:
                workspace_id = workspace_store.ensure_default_workspace(
                    actor_user_id,
                    display_name,
                    tenant_id=workspace_tenant_id,
                ).workspace_id
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        except WorkspaceAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if use_demo:
            agent_registry.set_demo_defaults(
                actor_user_id,
                scope_id=actor_user_id if tenant_id is not None else None,
            )
        state = store.save(
            new_session(
                actor_user_id,
                payload.track,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                trace_sink=trace_sink,
            )
        )
        return state.public_dict()

    @app.post("/v1/context-packages/validate")
    def validate_context_package(payload: LearningContextPackageRequest) -> dict[str, object]:
        try:
            package = validate_learning_context_package(payload.package)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
            "status": "valid",
            "package": package.public_dict(),
        }

    @app.post("/v1/importers/{plugin_id}/run")
    def run_importer(
        plugin_id: str,
        payload: ImporterRunRequest,
    ) -> dict[str, object]:
        try:
            result = ImporterRuntime(plugins).run(
                plugin_id,
                inputs=payload.inputs,
                confirmed_permissions=payload.confirmed_permissions,
                allow_network=payload.allow_network,
            )
        except ImporterRuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return result.public_dict(include_text=payload.include_text)

    @app.post("/v1/sessions/from-context-package")
    def create_session_from_context_package(
        request: Request,
        payload: LearningContextSessionRequest,
    ) -> dict[str, object]:
        actor_user_id, tenant_id, display_name = _actor_context(request, payload.user_id)
        workspace_tenant_id = tenant_id or LOCAL_TENANT_ID
        try:
            package = validate_learning_context_package(payload.package)
            use_demo = (
                payload.use_demo_agent
                if payload.use_demo_agent is not None
                else payload.use_demo_provider
            )
            if payload.workspace_id:
                workspace_store.assert_permission(
                    actor_user_id,
                    payload.workspace_id,
                    "create_sessions",
                    tenant_id=workspace_tenant_id,
                )
                workspace_id = payload.workspace_id
            else:
                workspace_id = workspace_store.ensure_default_workspace(
                    actor_user_id,
                    display_name,
                    tenant_id=workspace_tenant_id,
                ).workspace_id
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workspace not found") from exc
        except WorkspaceAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if use_demo:
            agent_registry.set_demo_defaults(
                actor_user_id,
                scope_id=actor_user_id if tenant_id is not None else None,
            )
        state = new_session(
            actor_user_id,
            payload.track or package.track or "ACADEMIC",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            trace_sink=trace_sink,
        )
        state = submit_enrichment(
            state,
            items=[item.enrichment_dict() for item in package.items],
            title=package.title,
            reference=package.reference,
            trace_sink=trace_sink,
        )
        state = store.save(state)
        return {
            "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
            "status": "session_created",
            "session": state.public_dict(),
            "package": package.public_dict(),
        }

    @app.get("/v1/sessions")
    def list_sessions(
        request: Request,
        user_id: str = "local-user",
        workspace_id: Optional[str] = None,
    ) -> list[dict[str, object]]:
        actor_user_id, tenant_id, _ = _actor_context(request, user_id)
        workspace_tenant_id = tenant_id or LOCAL_TENANT_ID
        sessions = store.list_sessions(tenant_id=tenant_id)
        if workspace_id:
            try:
                workspace_store.assert_permission(
                    actor_user_id,
                    workspace_id,
                    "read_sessions",
                    tenant_id=workspace_tenant_id,
                )
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="Workspace not found") from exc
            except WorkspaceAccessDenied as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            sessions = [state for state in sessions if state.workspace_id == workspace_id]
        elif tenant_id is not None:
            allowed_workspace_ids = {
                workspace.workspace_id
                for workspace in workspace_store.list_for_user(
                    actor_user_id,
                    tenant_id=workspace_tenant_id,
                )
            }
            sessions = [
                state for state in sessions if state.workspace_id in allowed_workspace_ids
            ]
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

    @app.post("/v1/sessions/{session_id}/context-package")
    def append_context_package(
        session_id: str,
        payload: LearningContextPackageRequest,
    ) -> dict[str, object]:
        try:
            package = validate_learning_context_package(payload.package)
            state = store.get(session_id)
            state = submit_enrichment(
                state,
                items=[item.enrichment_dict() for item in package.items],
                title=package.title,
                reference=package.reference,
                trace_sink=trace_sink,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = store.save(state)
        return {
            "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
            "status": "session_expanded",
            "session": state.public_dict(),
            "package": package.public_dict(),
        }

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
            "schema_version": LEARNING_ENRICHMENT_SCHEMA_VERSION,
            "contract": {
                "source_types": [
                    "web",
                    "document",
                    "video_slice",
                    "app_context",
                    "markdown_note",
                    "obsidian_note",
                ],
                "requires_locator": True,
                "requires_provenance": True,
                "requires_redaction_policy": True,
                "raw_text_returned": False,
            },
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
                    "provenance": item.metadata.get("provenance") or {},
                    "redaction_policy": item.metadata.get("redaction_policy") or "reference_only",
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

    @app.post("/v1/sessions/{session_id}/retrieval/rebuild")
    def rebuild_retrieval(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
            return retrieval_index.rebuild_session(state).public_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except RetrievalProjectionRequired as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RetrievalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/v1/sessions/{session_id}/retrieval/search")
    def search_retrieval(
        session_id: str,
        q: str,
        limit: int = 5,
    ) -> dict[str, object]:
        try:
            store.get(session_id)
            return retrieval_index.search(
                session_id=session_id,
                query=q,
                limit=limit,
            ).public_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except RetrievalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/sessions/{session_id}/retrieval/search")
    def search_retrieval_post(
        session_id: str,
        payload: RetrievalSearchRequest,
    ) -> dict[str, object]:
        try:
            store.get(session_id)
            return retrieval_index.search(
                session_id=session_id,
                query=payload.query,
                limit=payload.limit,
            ).public_dict()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except RetrievalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/v1/sessions/{session_id}/retrieval/eval")
    def eval_retrieval(
        session_id: str,
        q: str,
        limit: int = 5,
    ) -> dict[str, object]:
        try:
            store.get(session_id)
            result_set = retrieval_index.search(
                session_id=session_id,
                query=q,
                limit=limit,
            )
            return build_retrieval_quality_eval(
                RetrievalQualityInput(
                    session_id=session_id,
                    query=q,
                    retrieval_status=retrieval_index.status().public_dict(),
                    result_set=result_set,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except RetrievalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/sessions/{session_id}/retrieval/eval")
    def eval_retrieval_post(
        session_id: str,
        payload: RetrievalSearchRequest,
    ) -> dict[str, object]:
        try:
            store.get(session_id)
            result_set = retrieval_index.search(
                session_id=session_id,
                query=payload.query,
                limit=payload.limit,
            )
            return build_retrieval_quality_eval(
                RetrievalQualityInput(
                    session_id=session_id,
                    query=payload.query,
                    retrieval_status=retrieval_index.status().public_dict(),
                    result_set=result_set,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except RetrievalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/sessions/from-retrieval")
    def create_session_from_retrieval(
        request: Request,
        payload: RetrievalSessionRequest,
    ) -> dict[str, object]:
        actor_user_id, tenant_id, display_name = _actor_context(request, payload.user_id)
        workspace_tenant_id = tenant_id or LOCAL_TENANT_ID
        try:
            source_state = store.get(payload.source_session_id, tenant_id=tenant_id)
            if tenant_id is not None:
                if source_state.workspace_id is None:
                    raise KeyError(payload.source_session_id)
                workspace_store.assert_permission(
                    actor_user_id,
                    source_state.workspace_id,
                    "read_sessions",
                    tenant_id=workspace_tenant_id,
                )
            result_set = retrieval_index.search(
                session_id=payload.source_session_id,
                query=payload.query,
                limit=payload.limit,
            )
            package = validate_learning_context_package(
                result_set.context_package(
                    title=f"Retrieval: {payload.query}",
                    reference=f"retrieval://{payload.source_session_id}",
                )
            )
            use_demo = (
                payload.use_demo_agent
                if payload.use_demo_agent is not None
                else payload.use_demo_provider
            )
            if payload.workspace_id:
                workspace_store.assert_permission(
                    actor_user_id,
                    payload.workspace_id,
                    "create_sessions",
                    tenant_id=workspace_tenant_id,
                )
                workspace_id = payload.workspace_id
            else:
                workspace_id = workspace_store.ensure_default_workspace(
                    actor_user_id,
                    display_name,
                    tenant_id=workspace_tenant_id,
                ).workspace_id
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except WorkspaceAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RetrievalProjectionRequired as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RetrievalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if use_demo:
            agent_registry.set_demo_defaults(
                actor_user_id,
                scope_id=actor_user_id if tenant_id is not None else None,
            )
        state = new_session(
            actor_user_id,
            payload.track or package.track or "ACADEMIC",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            trace_sink=trace_sink,
        )
        state = submit_enrichment(
            state,
            items=[item.enrichment_dict() for item in package.items],
            title=package.title,
            reference=package.reference,
            trace_sink=trace_sink,
        )
        state = store.save(state)
        return {
            "schema_version": "retrieval-session-v1",
            "status": "session_created",
            "session": state.public_dict(),
            "retrieval": result_set.public_dict(),
            "package": package.public_dict(),
        }

    @app.post("/v1/sessions/{session_id}/retrieval/context-package")
    def append_session_from_retrieval(
        request: Request,
        session_id: str,
        payload: RetrievalSessionRequest,
    ) -> dict[str, object]:
        actor_user_id, tenant_id, _ = _actor_context(request, payload.user_id)
        try:
            state = store.get(session_id, tenant_id=tenant_id)
            source_state = store.get(payload.source_session_id, tenant_id=tenant_id)
            if tenant_id is not None:
                if source_state.workspace_id is None:
                    raise KeyError(payload.source_session_id)
                workspace_store.assert_permission(
                    actor_user_id,
                    source_state.workspace_id,
                    "read_sessions",
                    tenant_id=tenant_id,
                )
            result_set = retrieval_index.search(
                session_id=payload.source_session_id,
                query=payload.query,
                limit=payload.limit,
            )
            package = validate_learning_context_package(
                result_set.context_package(
                    title=f"Retrieval: {payload.query}",
                    reference=f"retrieval://{payload.source_session_id}",
                )
            )
            state = submit_enrichment(
                state,
                items=[item.enrichment_dict() for item in package.items],
                title=package.title,
                reference=package.reference,
                trace_sink=trace_sink,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except WorkspaceAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RetrievalProjectionRequired as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RetrievalUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state = store.save(state)
        return {
            "schema_version": "retrieval-session-v1",
            "status": "session_expanded",
            "session": state.public_dict(),
            "retrieval": result_set.public_dict(),
            "package": package.public_dict(),
        }

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
    def list_hitl(request: Request) -> list[dict[str, object]]:
        principal = _hosted_principal(request)
        if principal is None:
            return [item.__dict__ for item in store.list_hitl()]
        allowed_workspace_ids = {
            workspace.workspace_id
            for workspace in workspace_store.list_for_user(
                principal.principal_id,
                tenant_id=principal.tenant_id,
            )
        }
        return [
            item.__dict__
            for state in store.list_sessions(tenant_id=principal.tenant_id)
            if state.workspace_id in allowed_workspace_ids
            for item in state.hitl_interrupts
            if item.status == "open"
        ]

    @app.post("/v1/hitl/{task_id}/resolve")
    def resolve_hitl(
        request: Request,
        task_id: str,
        payload: ResolveHitlRequest,
    ) -> dict[str, object]:
        principal = _hosted_principal(request)
        try:
            state = store.get(
                payload.session_id,
                tenant_id=principal.tenant_id if principal is not None else None,
            )
            if principal is not None:
                if state.workspace_id is None:
                    raise KeyError(payload.session_id)
                workspace_store.assert_permission(
                    principal.principal_id,
                    state.workspace_id,
                    "write_sessions",
                    tenant_id=principal.tenant_id,
                )
            state = workflow.resolve_hitl(state, task_id, payload.payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session or HITL task not found") from exc
        except WorkspaceAccessDenied as exc:
            raise HTTPException(status_code=403, detail="Workspace permission denied") from exc
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

    @app.get("/v1/sessions/{session_id}/agent-eval/report")
    def get_agent_eval_report(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        audit = build_agent_audit(
            state,
            agent_status=agent_registry.status(state.user_id),
        )
        artifact = build_agent_eval_artifact(audit)
        quality = build_agent_quality_eval(
            state,
            agent_audit=audit,
            agent_eval_artifact=artifact,
        )
        export_status = {
            "obsidian_ready": state.stage == "completed"
            and bool(state.source and (state.scribe_log or state.insights)),
            "learning_package_ready": state.stage == "completed"
            and bool(state.source and state.quiz_items and state.grading_results),
            "second_brain_ready": state.stage == "completed"
            and bool(state.source and state.mastery and (state.insights or state.scribe_log)),
            "privacy": {
                "raw_source_text_included": False,
                "raw_enrichment_text_included": False,
                "learner_answers_included": False,
                "grading_feedback_included": False,
                "generated_insights_included": False,
                "agent_metadata_included": False,
                "secrets_included": False,
            },
        }
        return build_agent_eval_report(
            agent_audit=audit,
            agent_eval_artifact=artifact,
            quality_eval=quality,
            export_status=export_status,
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

    @app.get("/v1/sessions/{session_id}/exports/enrichment-artifact")
    def get_learning_enrichment_artifact(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
            return build_learning_enrichment_artifact(state)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/sessions/{session_id}/exports/second-brain-handoff")
    def get_second_brain_handoff(session_id: str) -> dict[str, object]:
        try:
            state = store.get(session_id)
            return build_second_brain_handoff(state)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/plugins")
    def list_plugins() -> list[dict[str, object]]:
        return [status.public_dict() for status in plugins.discover()]

    @app.get("/v1/plugins/sdk")
    def get_plugin_sdk() -> dict[str, object]:
        return plugin_sdk_contract()

    @app.get("/v1/plugins/capabilities")
    def get_plugin_capabilities() -> dict[str, object]:
        return plugin_capability_index(plugins.discover())

    @app.get("/v1/plugins/trust-policy")
    def get_plugin_trust_policy() -> dict[str, object]:
        return plugin_trust_policy()

    @app.get("/v1/plugins/registry-review")
    def get_plugin_registry_review() -> dict[str, object]:
        return plugins.registry_review().public_dict()

    @app.post("/v1/plugins/preview")
    def preview_plugin(payload: PluginPreviewRequest) -> dict[str, object]:
        status = plugins.preview_local(_plugin_source_from_intake(payload.source_path))
        return {
            **status.public_dict(),
            "install_dir": "<plugin-install-dir>",
            "quarantine_dir": "<plugin-quarantine-dir>",
            "requires_confirmation": bool(status.manifest and status.manifest.permissions),
            "default_action": "quarantine",
        }

    @app.post("/v1/plugins/validate-package")
    def validate_plugin_package_endpoint(payload: PluginValidatePackageRequest) -> dict[str, object]:
        return validate_plugin_package(_plugin_source_from_intake(payload.source_path), plugins)

    @app.post("/v1/plugins/install")
    def install_plugin(payload: PluginInstallRequest) -> dict[str, object]:
        source_path = _plugin_source_from_intake(payload.source_path)
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
        if preview.trust is not None and preview.trust.install_recommendation == "do_not_install":
            raise HTTPException(status_code=409, detail="Plugin trust policy blocks installation.")
        try:
            if payload.approve_install:
                quarantined_source = plugin_quarantine_dir / preview.manifest.plugin_id
                if not quarantined_source.exists():
                    raise ValueError("Plugin must be quarantined before approved installation.")
                status = plugins.install_local(
                    quarantined_source,
                    plugin_install_dir,
                    replace_existing=payload.replace_existing,
                )
                lifecycle_status = "installed"
                destination = plugin_install_dir
            else:
                status = plugins.quarantine_local(
                    source_path,
                    plugin_quarantine_dir,
                    replace_existing=True,
                )
                lifecycle_status = "quarantined"
                destination = plugin_quarantine_dir
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=409
                if "trust policy blocks" in str(exc) or "must be quarantined" in str(exc)
                else 400,
                detail=str(exc),
            ) from exc
        return {
            **status.public_dict(),
            "schema_version": "plugin-install-result-v1",
            "lifecycle_status": lifecycle_status,
            "installed": lifecycle_status == "installed",
            "quarantined": lifecycle_status == "quarantined",
            "install_dir": "<plugin-install-dir>",
            "quarantine_dir": "<plugin-quarantine-dir>",
            "destination_dir": (
                "<plugin-install-dir>"
                if destination == plugin_install_dir
                else "<plugin-quarantine-dir>"
            ),
            "manual_approval_required": lifecycle_status == "quarantined",
            "manual_approval_recorded": bool(payload.approve_install),
            "approval_note_recorded": bool(payload.approval_note),
            "entrypoints_executed": False,
            "requires_confirmation": False,
        }

    return app


app = create_app()
