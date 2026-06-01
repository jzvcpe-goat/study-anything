# Architecture

Study Anything is split into four MVP layers.

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

## Observability Layer

Langfuse is included in Compose for self-hosted traces. When telemetry is explicitly enabled and project keys are configured, learning events emit Langfuse v4 observations. Trace metadata is allowlisted: source prose, answers, synthesis text, HITL prose, and nested agent metadata are omitted.

## Persistence Layer

Docker self-host uses app Postgres for session state with `SESSION_STORE=postgres`. Python-only local development can use `SESSION_STORE=json` for a file-backed store under `STUDY_ANYTHING_DATA_DIR`.

Agent provider defaults remain JSON-backed in the alpha Docker volume. This keeps the Bring Your Own Agent surface simple while the public provider contract settles.
