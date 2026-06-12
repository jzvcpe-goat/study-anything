# Commercial Readiness

Study Anything is currently a public self-host Alpha foundation. A realistic commercial-readiness estimate is about 70% after removing the broken standalone Web UI from the launch path and hardening API/Skill/platform-agent distribution.

## What Is Ready

- Open-source foundation, Apache-2.0 license, contribution docs, security docs, branch policy, and GitHub release flow.
- Docker full stack with API, app Postgres, mock HTTP agent, and optional Langfuse/FalkorDB boundaries.
- Bring Your Own Agent architecture with fake demo agent and HTTP agent contract.
- Source-bound learning loop: ingestion, quiz generation, grading, mastery, synthesis, scribe log, HITL, discard.
- Plugin manifest validation and example plugin surfaces.
- Explicit local plugin installer and API permission-confirmation flow with manifest validation and overwrite protection.
- Compiled LangGraph adapter with in-memory and Postgres checkpointing modes.
- Optional privacy-preserving Langfuse v4 learning-event observations.
- Optional privacy-preserving FalkorDB topology projection with idempotent per-session rebuild.
- Local-first backup and restore with checksum verification for canonical Postgres state and Agent configuration.
- Disposable backup/restore drill script that creates an isolated Compose project, verifies rollback, and removes its test volumes on success.
- CI for API tests, Compose smoke, FalkorDB projection, and backup/restore rollback.
- Multi-architecture GHCR image publishing for `linux/amd64` and `linux/arm64`.
- One-command published-image core launch with sequential pulls and visible cold-download progress.
- Self-host doctor with Docker, Compose, port, health, Agent gateway, plugin-directory, and recovery-command checks.
- Read-only recovery status API for backup coverage, safeguards, and restore privacy warnings.
- Actionable Docker self-host diagnostics for non-ASCII checkout paths, with published-image and ASCII-path recovery guidance.
- Plugin trust summaries for local installs, including source digest, review metadata, signature metadata status, risk level, and install recommendation.
- Local plugin registry digest verification with Ed25519 registry-signature support when trusted keys are present.
- Read-only plugin registry review that surfaces verified digests, signature counts, update candidates, blocked entries, and manual-review actions without downloading code.
- Local workspace ownership foundation with hashed local identities, default workspace assignment, roles, and role capability names.
- Local encrypted sync package foundation with user-supplied passphrases, AES-256-GCM package envelopes, count-only inspect summaries, and no hosted upload.
- Read-only encrypted sync restore preview that compares a package with local sessions and returns only counts, conflict hashes, warnings, and manual confirmation requirements.
- Privacy-preserving local PMF metrics for completion rate, active learner hashes, repeat usage, mastery delta, plugin readiness, and hosted-service intent.
- Opt-in local future-service interest capture that hashes contact values and never uploads by default.
- Explicit-consent PMF export package for community PMF readouts and hosted waitlist review, with aggregate data only.
- API smoke that verifies learning flow, recovery status, encrypted sync export/inspect, plugin registry trust, local PMF metrics, and Agent audit boundaries.
- Redacted Agent Eval artifact foundation that bridges invocation audit evidence into mature external eval tools such as Promptfoo, DeepEval, LangChain AgentEvals, and Ragas.
- Platform-agent integration guide for Codex, Kimi, WorkBuddy-style tools, and terminal-capable Agents.
- Machine-readable platform Agent tool manifest plus verifier for the minimum learning loop, mastery, Agent audit, and eval artifact endpoints.
- Generated platform import assets: constrained OpenAPI, OpenAI-compatible function tools, and a checked-in tool catalog.
- Copy-ready platform packs for Codex, Kimi-compatible agents, and WorkBuddy-style HTTP tool workspaces.
- OpenAI-compatible gateway dry-run verifier so users can prove Kimi/OpenAI-compatible wiring before
  adding real model credentials.
- Disposable clean-clone adoption verifier that creates `.env`, runs Skill Mode, verifies the
  OpenAI-compatible gateway dry-run, teaching layers, quiz, grading, mastery, Agent audit, and Agent
  eval from a separate checkout.
- Adoption diagnostics for localhost reachability, Docker daemon state, GHCR visibility, Agent
  endpoint health, and provider capability defaults.
- Deterministic platform bundle manifest with sha256 hashes for platform packs, generated import
  assets, key docs, and the repo-local Skill entrypoint.
- Disposable published-image smoke that verifies the public GHCR API image, runtime version, and API
  learning flow, with an explicit slow-GHCR diagnostic fallback for local network limits.
- Published release path for the current recovery, plugin-registry, Skill/API, and Bring Your Own Agent foundations.

## What Blocks Commercial Launch

- Hosted accounts and identity provider integration beyond the local workspace boundary.
- Hosted encrypted sync service: remote storage, multi-device conflict resolution, account recovery, and support tooling.
- Hosted deployment architecture, tenant isolation, billing, plan limits, and support workflows.
- Team spaces beyond local membership metadata: admin controls, export/audit guarantees, and enterprise data retention settings.
- Plugin marketplace trust model beyond local installs: hosted signed registry distribution, maintainer review queues, automatic update UX, and payment boundaries.
- Production observability: SLOs, incident response, trace retention, privacy-preserving telemetry.
- Security hardening: threat model, dependency policy, secret scanning, container hardening, external audit.
- PMF validation at community scale: real weekly active learners, repeat sessions, mastery delta by cohort, plugin activation, and hosted waitlist conversion.
- Product delivery layer: no standalone frontend is currently shippable; the launch path depends on API/Skill/platform-agent integrations until a new UI is designed.
- Non-developer polish beyond first-run: upgrade confidence, support docs, and guided recovery for rare edge cases.

## Suggested Branch Tracks

- `codex/platform-agent-submissions`: platform-specific examples, submission docs, and real workspace import walkthroughs.
- `codex/agent-eval-quality`: DeepEval, LangChain AgentEvals, and Ragas quality suites beyond native redacted artifact gates.
- `codex/new-product-ui`: redesigned natural-language-first UI after API/Skill launch is stable.
- `feature/accounts-workspaces`: local identity, workspace model, roles, and permissions.
- `feature/hosted-sync-service`: remote storage, recovery, conflict resolution, and paid convenience boundary.
- `feature/plugin-trust`: plugin permissions, signing, review metadata, and install UX.
- `feature/pmf-validation`: community PMF readouts, hosted waitlist export policy, and cohort-level learning outcomes.
- `ops/production-hardening`: container, CI, release, and security baseline.

## Next Commercial Milestone

Reach 75% readiness by making the self-host Alpha dependable for real learners without a standalone UI:

- Docker soak testing and trace retention guidance.
- Longer Docker soak testing of the disposable backup/restore drill across source-build and published-image paths.
- Documented recovery drill walkthroughs for non-developer self-host operators.
- Hosted signed plugin registry distribution, maintainer review queue, and explicit update install workflow.
- Public PMF sharing workflow: documented collection norms, maintainer review process, and cohort readout templates.
- Mature Agent quality eval suites wired into CI or documented operator workflows.
