# Commercial Readiness

Study Anything is currently a public self-host Alpha foundation. A realistic commercial-readiness estimate is about 43%.

## What Is Ready

- Open-source foundation, Apache-2.0 license, contribution docs, security docs, branch policy, and GitHub release flow.
- Docker full stack with API, Web, app Postgres, mock HTTP agent, and optional Langfuse/FalkorDB boundaries.
- Bring Your Own Agent architecture with fake demo agent and HTTP agent contract.
- Source-bound learning loop: ingestion, quiz generation, grading, mastery, synthesis, scribe log, HITL, discard.
- Plugin manifest validation and example plugin surfaces.
- Explicit local plugin installer with manifest validation and overwrite protection.
- Compiled LangGraph adapter with in-memory and Postgres checkpointing modes.
- Optional privacy-preserving Langfuse v4 learning-event observations.
- Optional privacy-preserving FalkorDB topology projection with idempotent per-session rebuild.
- CI for API tests, Web build, and Compose smoke.
- GHCR image publishing path.

## What Blocks Commercial Launch

- Accounts, identity, workspace ownership, roles, and permission boundaries.
- End-to-end encrypted sync/backup for paid convenience services.
- Hosted deployment architecture, tenant isolation, billing, plan limits, and support workflows.
- Team spaces, admin controls, export/audit guarantees, and enterprise data retention settings.
- Plugin marketplace trust model: signing, review, permission prompts, install/update UX.
- Production observability: SLOs, incident response, trace retention, privacy-preserving telemetry.
- Security hardening: threat model, dependency policy, secret scanning, container hardening, external audit.
- Product analytics for PMF: weekly active learners, repeat sessions, mastery delta, plugin installs, hosted waitlist.
- Polished onboarding and documentation for non-developer users.

## Suggested Branch Tracks

- `codex/ui-natural-language-workspace`: natural-language-first UI and bilingual onboarding.
- `feature/accounts-workspaces`: local identity, workspace model, roles, and permissions.
- `feature/encrypted-sync-design`: Sync protocol, key ownership, and hosted convenience boundary.
- `feature/plugin-trust`: plugin permissions, signing, review metadata, and install UX.
- `feature/pmf-metrics`: privacy-preserving local metrics and optional hosted waitlist.
- `ops/production-hardening`: container, CI, release, and security baseline.

## Next Commercial Milestone

Reach 50-55% readiness by making the self-host Alpha friendly for real learners:

- Guided first-run onboarding for non-developer learners.
- Plugin installation UX with permission confirmation.
- Privacy-preserving PMF metrics and an opt-in hosted waitlist.
- Docker soak testing, trace retention guidance, and a documented backup path.
