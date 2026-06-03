# Commercial Readiness

Study Anything is currently a public self-host Alpha foundation. A realistic commercial-readiness estimate is about 55%.

## What Is Ready

- Open-source foundation, Apache-2.0 license, contribution docs, security docs, branch policy, and GitHub release flow.
- Docker full stack with API, Web, app Postgres, mock HTTP agent, and optional Langfuse/FalkorDB boundaries.
- Bring Your Own Agent architecture with fake demo agent and HTTP agent contract.
- Source-bound learning loop: ingestion, quiz generation, grading, mastery, synthesis, scribe log, HITL, discard.
- Plugin manifest validation and example plugin surfaces.
- Explicit local plugin installer and Web permission-confirmation flow with manifest validation and overwrite protection.
- Compiled LangGraph adapter with in-memory and Postgres checkpointing modes.
- Optional privacy-preserving Langfuse v4 learning-event observations.
- Optional privacy-preserving FalkorDB topology projection with idempotent per-session rebuild.
- Local-first backup and restore with checksum verification for canonical Postgres state and Agent configuration.
- CI for API tests, Web build, Compose smoke, FalkorDB projection, and backup/restore rollback.
- Multi-architecture GHCR image publishing for `linux/amd64` and `linux/arm64`.
- One-command published-image core launch with sequential pulls and visible cold-download progress.
- Guided first-run Web onboarding for the demo loop, learner-owned source material, and Bring Your Own Agent setup.
- Self-host doctor with Docker, Compose, port, health, Agent gateway, plugin-directory, and recovery-command checks.

## What Blocks Commercial Launch

- Accounts, identity, workspace ownership, roles, and permission boundaries.
- End-to-end encrypted sync/backup for paid convenience services.
- Hosted deployment architecture, tenant isolation, billing, plan limits, and support workflows.
- Team spaces, admin controls, export/audit guarantees, and enterprise data retention settings.
- Plugin marketplace trust model: signing, review metadata, remote registry policy, update UX, and payment boundaries.
- Production observability: SLOs, incident response, trace retention, privacy-preserving telemetry.
- Security hardening: threat model, dependency policy, secret scanning, container hardening, external audit.
- Product analytics for PMF: weekly active learners, repeat sessions, mastery delta, plugin installs, hosted waitlist.
- Non-developer polish beyond first-run: upgrade confidence, support docs, and guided recovery for rare edge cases.

## Suggested Branch Tracks

- `codex/guided-first-run-onboarding`: natural-language-first UI, bilingual first-run path, and Agent setup clarity.
- `feature/accounts-workspaces`: local identity, workspace model, roles, and permissions.
- `feature/encrypted-sync-design`: Sync protocol, key ownership, and hosted convenience boundary.
- `feature/plugin-trust`: plugin permissions, signing, review metadata, and install UX.
- `feature/pmf-metrics`: privacy-preserving local metrics and optional hosted waitlist.
- `ops/production-hardening`: container, CI, release, and security baseline.

## Next Commercial Milestone

Reach 55-60% readiness by making the self-host Alpha dependable for real learners:

- Privacy-preserving PMF metrics and an opt-in hosted waitlist.
- Docker soak testing and trace retention guidance.
- Backup restore drills in a disposable local stack.
- Signed plugin registry design and update-review workflow.
