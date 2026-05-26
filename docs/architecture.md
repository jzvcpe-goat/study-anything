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

The current implementation uses a deterministic Python executor with a LangGraph-ready boundary in `core/langgraph_adapter.py`. Docker dependencies include LangGraph and the Postgres checkpointer so the production adapter can replace the local executor without changing API contracts.

## Agent Layer

`AgentRegistry` stores configured user-owned agents and capability defaults. `AgentRouter` sends structured `AgentTask` payloads to a provider and validates every `AgentResult` before workflow state changes.

Study Anything does not store real model API keys, choose production models, or run the user's tools. The recommended MVP path is a local/private HTTP agent gateway. Deprecated `ModelRegistry` imports and `/v1/models/*` endpoints remain as aliases for one alpha release.

## Observability Layer

Langfuse is included in Compose for self-hosted traces. The core event model already carries trace IDs and agent metadata.

## Persistence Layer

Docker self-host uses app Postgres for session state with `SESSION_STORE=postgres`. Python-only local development can use `SESSION_STORE=json` for a file-backed store under `STUDY_ANYTHING_DATA_DIR`.

Agent provider defaults remain JSON-backed in the alpha Docker volume. This keeps the Bring Your Own Agent surface simple while the public provider contract settles.
