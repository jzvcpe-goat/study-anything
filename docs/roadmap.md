# Roadmap

## v0.1.0-alpha

- Self-host Docker Compose stack.
- Deterministic demo agent.
- Source-bound learning loop.
- Agent registry and provider health checks.
- Plugin manifest contract and example plugin.
- Durable JSON alpha store for sessions and agent defaults.
- Web operator panel for agent setup, system status, and plugin discovery.
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
- Sequential API/Web image pulls with clear cold-download messaging.
- Explicit tag, registry mirror, and offline-cache overrides.
- Shell behavior tests for source builds and published-image launches.

## v0.2.2-alpha

- Visible Docker layer progress during published-image pulls.
- Patch release for slow-network first-run clarity.

## v0.2.3-alpha

- Guided first-run Web onboarding for the demo loop, learner-owned source material, and Bring Your Own Agent setup.
- Agent status copy distinguishes the deterministic demo agent from a learner-configured real Agent.
- Web learning sessions default to the learner's Agent when one is configured.
- Permission-gated Web plugin installation for explicitly selected local plugin directories.
- Self-host doctor checks Docker, Compose config, profile ports, health endpoints, Agent gateway hints, and recovery commands.
- Mobile learning layout keeps the source, composer, and progress areas readable instead of squeezing columns.
- Local-only PMF launch panel and API metrics for completion, repeat usage, mastery delta, plugin readiness, and future-service interest.
- Foreground Skill Mode launch for agent and desktop environments that do not preserve background processes.

## v0.3 Next

- Importer plugin SDK.
- E2E Playwright tests.
- LanceDB reading embedding index and retrieval API.

## PMF Track

- Community-scale PMF readouts from explicitly shared local aggregate exports.
- Cohort-level mastery delta and repeat-use analysis.
- Plugin activation telemetry, opt-in only.
- Hosted waitlist consent and export policy for Sync and Publish.

## Post-PMF Commercial Services

- Study Sync: encrypted backup and cross-device sync.
- Study Publish: publish selected maps, trails, decks, or reports.
- Study Teams: private shared workspaces and audit/export controls.
- Catalyst: supporter tier with early builds and roadmap voting.
