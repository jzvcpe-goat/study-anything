# Architecture

Study Anything is split into five MVP layers.

## API Layer

FastAPI exposes stable REST and event endpoints. The Web UI is intentionally thin and consumes these APIs.

## Workflow Layer

The alpha workflow models the nine Study Anything nodes:

1. `initialize_session`
2. `architect_node`
3. `gap_filler`
4. `quiz_generator`
5. `quiz_grader`
6. `mastery_evaluator`
7. `synthesist_node`
8. `scribe_node`
9. `incubation_detector`

The current implementation runs the existing deterministic business nodes through a compiled LangGraph `StateGraph`. Local Python development uses an in-memory checkpointer by default. Docker self-host uses the app Postgres service when `LANGGRAPH_CHECKPOINTER=postgres`.

Set `WORKFLOW_ENGINE=deterministic` to fall back to the original sequential executor while debugging.

## Agent Layer

`AgentRegistry` stores configured user-owned agents and capability defaults. `AgentRouter` sends structured `AgentTask` payloads to a provider and validates every `AgentResult` before workflow state changes.

Study Anything does not store real model API keys, choose production models, or run the user's tools. The recommended MVP path is a local/private HTTP agent gateway. Deprecated `ModelRegistry` imports and `/v1/models/*` endpoints remain as aliases for one alpha release.

## Local Identity And Workspace Layer

`LocalWorkspaceStore` keeps hashed local identities, default workspace ownership, membership roles, and
role capability names in the self-host data directory. It is a local ownership boundary for sessions and
future Sync/Teams services, not a hosted account system. Raw user IDs are not persisted in the workspace
store.

New sessions carry `workspace_id` in canonical session state. Existing sessions without a workspace ID
continue to load, and the API creates a default local workspace when a caller has not selected one.

## Observability Layer

Langfuse is included in Compose for self-hosted traces. When telemetry is explicitly enabled and project keys are configured, learning events emit Langfuse v4 observations. Trace metadata is allowlisted: source prose, answers, synthesis text, HITL prose, and nested agent metadata are omitted.

## Persistence Layer

Docker self-host uses app Postgres for session state with `SESSION_STORE=postgres`. Python-only local development can use `SESSION_STORE=json` for a file-backed store under `STUDY_ANYTHING_DATA_DIR`.

Agent provider defaults and local workspace state remain JSON-backed in the alpha Docker volume. This
keeps the Bring Your Own Agent and local ownership surfaces simple while the public provider and hosted
service contracts settle.

## Optional Topology Projection

FalkorDB is a disposable learning-topology projection, never the canonical store. Postgres remains the
source of truth. After mastery evaluation, the workflow may project learner, session, source-reference,
and mastery edges through an explicit allowlist.

Graph failures produce a sanitized warning event and do not block learning. The graph does not receive
reading prose, titles, quizzes, answers, feedback, insights, scribe logs, agent metadata, or secrets.
Operators can inspect graph health and rebuild a single session from canonical state through the fixed
topology API.
