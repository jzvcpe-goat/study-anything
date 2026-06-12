# API Surface

## Agents

- `GET /v1/agents/status`
- `POST /v1/agents/providers`
- `POST /v1/agents/defaults`
- `POST /v1/agents/test`
- `POST /v1/agents/{provider_id}/invoke`

Agent request/response schemas are documented in `docs/agent-contract.md`.
Platform-agent usage patterns are documented in `docs/platform-agent-integrations.md`.

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

## Local Encrypted Sync Package

- `GET /v1/sync/status`
- `POST /v1/sync/export`
- `POST /v1/sync/inspect`
- `POST /v1/sync/restore-preview`

Sync package APIs are the local-first foundation for future Study Sync. They do not upload data,
create hosted accounts, store billing state, or persist the package passphrase.

`POST /v1/sync/export` requires a user-provided `passphrase` with at least 12 characters. It returns an
AES-256-GCM encrypted package envelope and a count-only payload summary. The encrypted payload can
include sessions, local Agent registry configuration, local workspace state, local PMF interest records,
and plugin inventory metadata. The response envelope does not include raw user IDs, source text, source
titles, quiz prompts, answers, grading feedback, insights, scribe logs, Agent endpoints, Agent metadata,
or plugin source code in plaintext.

`POST /v1/sync/inspect` decrypts a package with the supplied passphrase and returns only schema,
creation time, summary counts, and privacy flags. It never returns the plaintext payload and does not
restore data. Hosted upload, cross-device conflict resolution, and account recovery remain planned
commercial-service work.

`POST /v1/sync/restore-preview` decrypts a package with the supplied passphrase and compares it with the
current local session inventory without writing data. It returns a count-only restore plan: sessions that
would be added, overwritten, or kept, the projected post-restore session count, conflict hashes, warnings,
and explicit manual-restore requirements. It never returns raw session IDs, user IDs, source text, answers,
Agent endpoints, PMF contact values, or decrypted plugin inventory.

## Sessions

- `POST /v1/sessions`
- `GET /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `POST /v1/sessions/{session_id}/reading`
- `POST /v1/sessions/{session_id}/teaching-layers`
- `POST /v1/sessions/{session_id}/run`
- `POST /v1/sessions/{session_id}/resume`

For platform Agent tools, use the constrained manifest at
`platform/study-anything-platform-tools.json` instead of exposing the full API surface. Validate that
manifest against a running API with:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
```

`POST /v1/sessions/{session_id}/teaching-layers` generates optional layered teaching output before
the quiz loop. Supported layer names are `overview`, `glossary`, `examples`, and `scribe`, which route
to `teach.overview`, `teach.glossary`, `teach.examples`, and `note.scribe` Agent capabilities. This
endpoint returns private learning content and should be redacted by platform wrappers before logging.

## Learning

- `POST /v1/sessions/{session_id}/answers`
- `POST /v1/sessions/{session_id}/discard`
- `GET /v1/sessions/{session_id}/mastery`
- `GET /v1/sessions/{session_id}/agent-audit`
- `GET /v1/sessions/{session_id}/agent-eval/artifact`
- `GET /v1/sessions/{session_id}/agent-eval` deprecated alias for one alpha release

`agent-audit` proves redacted Agent invocation coverage. `agent-eval/artifact` converts that audit into
a redacted record for external tools such as Promptfoo, DeepEval, LangChain AgentEvals, and Ragas. It
does not run judge models and does not return source text, answers, feedback, Agent endpoints, or raw
Agent metadata.

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
- `GET /v1/recovery/status`
- `GET /v1/plugins`
- `GET /v1/plugins/trust-policy`
- `GET /v1/plugins/registry-review`
- `POST /v1/plugins/preview`
- `POST /v1/plugins/install`

Plugin install is local-first. Preview validates a user-selected local directory and returns the manifest,
permission details, trust summary, and target install directory without copying or executing plugin code.
Install requires the caller to echo the exact manifest permission list as `confirmed_permissions`;
otherwise the API returns `409`.

`GET /v1/plugins/trust-policy` returns the local-first alpha trust policy: local directories only, no
remote code downloads, no entrypoint execution during install, no raw secrets stored by Study Anything,
supported review statuses, registry digest/signature statuses, Ed25519 registry-signature payload,
and install recommendation values.

`GET /v1/plugins/registry-review` summarizes local registry metadata against discovered local plugins.
It returns verified counts, signature verification counts, update candidates, blocked entries, manual
review requirements, registry file names, and per-plugin action labels. It reads metadata only and never
downloads plugin source, installs updates, executes entrypoints, or contacts a marketplace.

`GET /v1/recovery/status` returns read-only self-host backup and restore readiness. It exposes the
documented local commands, backup coverage, privacy warnings, and safety checks such as SHA-256
manifests and explicit destructive-restore confirmation. It does not run backup or restore operations,
does not expose absolute local paths, and keeps destructive restore out of the Web/API surface.

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
