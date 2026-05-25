# API Surface

## Agents

- `GET /v1/agents/status`
- `POST /v1/agents/providers`
- `POST /v1/agents/defaults`
- `POST /v1/agents/test`
- `POST /v1/agents/{provider_id}/invoke`

Agent request/response schemas are documented in `docs/agent-contract.md`.

## Deprecated Model Aliases

These remain for one alpha release and return agent-backed status:

- `GET /v1/models/status`
- `POST /v1/models/providers`
- `POST /v1/models/defaults`
- `POST /v1/models/test`

## Sessions

- `POST /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `POST /v1/sessions/{session_id}/reading`
- `POST /v1/sessions/{session_id}/run`
- `POST /v1/sessions/{session_id}/resume`

## Learning

- `POST /v1/sessions/{session_id}/answers`
- `POST /v1/sessions/{session_id}/discard`
- `GET /v1/sessions/{session_id}/mastery`

## HITL and Events

- `GET /v1/hitl`
- `POST /v1/hitl/{task_id}/resolve`
- `GET /v1/sessions/{session_id}/events`

## System and Plugins

- `GET /v1/system/status`
- `GET /v1/system/integrations`
- `GET /v1/plugins`
