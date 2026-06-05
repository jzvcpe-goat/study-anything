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

## Local Workspaces

- `GET /v1/workspaces/status`
- `GET /v1/workspaces`
- `POST /v1/workspaces`
- `POST /v1/workspaces/{workspace_id}/members`

Workspaces are local-first ownership boundaries, not hosted accounts. The API stores hashed local
identities, workspace membership, roles, and role capability names. It does not require an account,
contact method, remote identity provider, or billing plan.

Supported roles are `owner`, `admin`, `member`, and `viewer`. Workspace responses include role
permissions such as `read_sessions`, `create_sessions`, `manage_members`, `configure_agents`,
`install_plugins`, and `export_pmf`. Session creation accepts an optional `workspace_id`; when omitted,
Study Anything creates or reuses the caller's local default workspace.

## Sessions

- `POST /v1/sessions`
- `GET /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `POST /v1/sessions/{session_id}/reading`
- `POST /v1/sessions/{session_id}/run`
- `POST /v1/sessions/{session_id}/resume`

## Learning

- `POST /v1/sessions/{session_id}/answers`
- `POST /v1/sessions/{session_id}/discard`
- `GET /v1/sessions/{session_id}/mastery`

## Optional Learning Topology

- `GET /v1/graph/status`
- `GET /v1/sessions/{session_id}/topology`
- `POST /v1/sessions/{session_id}/topology/rebuild`

FalkorDB is an optional projection layer. These endpoints expose only source references, excerpt hashes,
mastery metadata, and topology identifiers. They never expose reading prose, quiz content, answers, or
generated insights.

## HITL and Events

- `GET /v1/hitl`
- `POST /v1/hitl/{task_id}/resolve`
- `GET /v1/sessions/{session_id}/events`

## System and Plugins

- `GET /v1/system/status`
- `GET /v1/system/integrations`
- `GET /v1/plugins`
- `GET /v1/plugins/trust-policy`
- `POST /v1/plugins/preview`
- `POST /v1/plugins/install`

Plugin install is local-first. Preview validates a user-selected local directory and returns the manifest,
permission details, trust summary, and target install directory without copying or executing plugin code.
Install requires the caller to echo the exact manifest permission list as `confirmed_permissions`;
otherwise the API returns `409`.

`GET /v1/plugins/trust-policy` returns the local-first alpha trust policy: local directories only, no
remote code downloads, no entrypoint execution during install, no raw secrets stored by Study Anything,
supported review statuses, and install recommendation values.

## Local PMF and Launch Signals

- `GET /v1/metrics/pmf`
- `GET /v1/pmf/summary`
- `POST /v1/pmf/interest`
- `POST /v1/pmf/export`

PMF metrics are local aggregate signals for self-host operators. They count sessions, completed learning
loops, active learner hashes, repeat usage, mastery delta, ready plugins, and optional future-service
interest. The response does not include session IDs, user IDs, user hashes, source titles, reading prose,
quiz prompts, answers, grading feedback, insights, scribe logs, Agent metadata, or raw contact values.

`POST /v1/pmf/interest` records an explicit local intent for future convenience services such as
`neural_sync`, `neural_publish`, `neural_teams`, `catalyst`, `plugin_marketplace`, or `hosted_alpha`.
Optional contact values are hashed before storage; optional comments are reduced to a boolean
`comment_provided` flag.

`POST /v1/pmf/export` creates a shareable aggregate package only when `consent_to_share=true`.
Supported destinations are `self_archive`, `github_discussion`, `email_to_maintainers`,
`hosted_waitlist`, and `research_report`. The export includes aggregate PMF metrics, service-interest
counts, the consent statement, and privacy flags. It does not include source text, quiz prompts, answers,
feedback, insights, scribe logs, Agent metadata, raw user IDs, user hashes, raw contact values, contact
hashes, or freeform comments.
