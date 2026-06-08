# Roadmap

## v0.1.0-alpha

- Self-host Docker Compose stack.
- Deterministic demo agent.
- Source-bound learning loop.
- Agent registry and provider health checks.
- Plugin manifest contract and example plugin.
- Durable JSON alpha store for sessions and agent defaults.
- Skill-first CLI and repo-local Agent skill.
- OSS docs and contribution flow.

## v0.2.0-alpha

- Durable Postgres session store.
- Compiled LangGraph adapter with in-memory and Postgres checkpointing.
- Privacy-preserving Langfuse v4 node observations.
- Explicit local plugin installer with manifest validation.
- Optional FalkorDB source/mastery topology projection with session rebuild APIs.
- Local self-host backup and restore with checksum verification.
- Multi-architecture GHCR images for Linux servers and Apple Silicon Docker Desktop.

## v0.2.1-alpha

- One-command published-image core launch for first-run self-hosting.
- Sequential API image pulls with clear cold-download messaging.
- Explicit tag, registry mirror, and offline-cache overrides.
- Shell behavior tests for source builds and published-image launches.

## v0.2.2-alpha

- Visible Docker layer progress during published-image pulls.
- Patch release for slow-network first-run clarity.

## v0.2.3-alpha

- API/Skill-first onboarding for the demo loop, learner-owned source material, and Bring Your Own Agent setup.
- Agent status copy distinguishes the deterministic demo agent from a learner-configured real Agent.
- Web learning sessions default to the learner's Agent when one is configured.
- Permission-gated Web plugin installation for explicitly selected local plugin directories.
- Self-host doctor checks Docker, Compose config, profile ports, health endpoints, Agent gateway hints, and recovery commands.
- Mobile learning layout keeps the source, composer, and progress areas readable instead of squeezing columns.
- Local-only PMF launch panel and API metrics for completion, repeat usage, mastery delta, plugin readiness, and future-service interest.
- Foreground Skill Mode launch for agent and desktop environments that do not preserve background processes.

## v0.2.4-alpha

- Explicit-consent PMF export packages for community feedback and hosted waitlist review.
- API consent gate for aggregate-only PMF sharing.
- Full API smoke verification now covers PMF export consent failure and success paths.
- Docker self-host source-build diagnostics for non-ASCII checkout paths, with published-image and ASCII-path recovery guidance.
- Release docs updated for the deployability fix and PMF export package.

## v0.2.5-alpha

- Local plugin trust summaries with source digests, review metadata, signature metadata status, risk level, and install recommendation.
- `GET /v1/plugins/trust-policy` documents the self-host alpha trust boundary for plugins.
- Plugin manifest now accepts optional publisher, review, signature, homepage, and source metadata.
- Local workspace ownership foundation with hashed identities, roles, default workspace assignment, and session `workspace_id`.
- Local encrypted sync package foundation with `/v1/sync/status`, `/v1/sync/export`, and `/v1/sync/inspect`.
- Read-only encrypted sync restore preview with count-only add/overwrite/keep impact, conflict hashes, warnings, and no data mutation.
- Full API smoke verification now checks encrypted package export, inspect, and plaintext leakage boundaries.

## v0.2.6-alpha

- Read-only recovery status API for backup coverage, safeguards, restore privacy, and manual recovery commands.
- Disposable Docker backup/restore drill for self-host validation, including non-ASCII checkout recovery via an ASCII temp source copy.
- Local plugin registry digest verification, with Ed25519 registry-signature support when trusted keys are configured.
- Read-only plugin registry review reports verified digests, signature counts, update candidates, blocked entries, and manual-review actions.
- API smoke now verifies recovery status, encrypted Sync export/inspect, plugin registry trust, local PMF metrics, and Agent audit boundaries.

## v0.2.7-alpha

- API runtime version now resolves from package metadata so `/v1/health` and `/v1/system/status`
  match the release artifact.
- Published-image launch defaults point at the corrected alpha tag.
- Disposable published-image smoke verifies the public GHCR API image, runtime version, and API learning
  loop before users depend on a release.
- Standalone Web UI removed from the launch path; future UI work moves to a separate branch after API/Skill stability.

## v0.2.8-alpha

- API/Skill launch path becomes the release contract after removing the broken standalone Web UI.
- Agent invocation audit API proves whether Study Anything used fake or user-owned HTTP agents for
  required learning tasks.
- Docker, CI, release, and self-host docs target API/Postgres core services and GHCR API images only.

## v0.2.9-alpha

- Published-image verifier now normalizes Python alpha package versions such as `0.2.9a0` when checking
  a `v0.2.9-alpha` tag.

## v0.2.10-alpha

- Agent Eval foundation with a redacted `/v1/sessions/{session_id}/agent-eval/artifact` bridge.
- Promptfoo contract-gate template for completed learning sessions.
- Mature eval adapter strategy for Promptfoo, DeepEval, LangChain AgentEvals, and Ragas.

## v0.2.11-alpha

- CLI and Skill commands for Agent invocation audit and Agent eval artifacts.
- Platform-agent integration guide for Codex, Kimi, WorkBuddy-style tools, and terminal-capable Agents.
- Acceptance gate requiring completed learning loops to return Agent audit and eval evidence.

## v0.2.12-alpha

- Machine-readable platform Agent tool manifest for Kimi/Codex/WorkBuddy-style wrappers.
- Platform integration verifier that proves the manifest can complete a real local learning loop.
- Generated platform import assets: constrained OpenAPI, OpenAI-compatible function tools, and tool
  catalog.
- CI and release-check drift detection for generated platform Agent assets.

## v0.3 Next

- Importer plugin SDK.
- Expand the packaged Kimi/Codex/WorkBuddy platform-agent integrations into tested examples and
  platform-specific submission docs.
- Mature Agent quality eval suites for DeepEval, LangChain AgentEvals, and Ragas.
- Hosted-account design for Sync/Teams on top of the local workspace and encrypted package boundaries.
- E2E Playwright tests.
- LanceDB reading embedding index and retrieval API.

## PMF Track

- Community-scale PMF readouts from explicitly shared local aggregate exports.
- Cohort-level mastery delta and repeat-use analysis.
- Plugin activation telemetry, opt-in only.
- Hosted waitlist consent and export policy for Sync and Publish.

## Post-PMF Commercial Services

- Study Sync: hosted encrypted backup, cross-device sync, conflict resolution, and recovery flows.
- Study Publish: publish selected maps, trails, decks, or reports.
- Study Teams: private shared workspaces and audit/export controls.
- Catalyst: supporter tier with early builds and roadmap voting.
