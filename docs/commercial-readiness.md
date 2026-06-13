# Commercial Readiness

Study Anything is currently a public self-host Alpha foundation with a machine-readable commercial
readiness contract. The current launch path is GitHub OSS plus platform-Agent adoption, not a paid
standalone app.

Use:

```bash
python3 scripts/verify_commercial_readiness.py
python3 scripts/verify_agent_gateway_hardening.py
python3 scripts/verify_external_agent_adapter_hardening.py
python3 scripts/verify_notebooklm_obsidian_bridge_hardening.py
python3 scripts/verify_plugin_quarantine.py
python3 scripts/verify_security_recovery_hardening.py
python3 scripts/verify_platform_submission_dry_run.py --check
```

or call:

```bash
curl http://127.0.0.1:8000/v1/commercial/readiness
```

The response is `commercial-readiness-v1`. It is metadata-only and states:

- `github_oss_launch=ready`
- `platform_agent_distribution=ready`
- `self_host_alpha=ready`
- `standalone_app=not_in_launch_path`
- `hosted_paid_services=not_ready`

This means Study Anything can be distributed as an OSS local-first learning layer for Kimi, Codex,
WorkBuddy-style tools, and user-owned Agent gateways. It does not mean hosted subscriptions, billing,
SSO, remote accounts, or a standalone frontend are ready.
The Agent gateway hardening verifier is part of the launch proof for this distribution path: it
checks that real credentials remain outside Study Anything, unsafe provider config is rejected, and
bad Agent output produces redacted diagnostics.
The NotebookLM/Obsidian bridge verifier is the matching proof for the learning-context path: it
checks bounded imports, duplicate/idempotency behavior, hidden instruction rejection, strict
second-brain archive redaction, and `learning-package-v1` Agent metadata boundaries.
The plugin quarantine verifier is the matching proof for the extension path: it checks unknown
plugins quarantine by default, explicit approval is required for installation, digest mismatches are
blocked before any copy is written, and plugin entrypoints are not executed during preview or
quarantine.
The security recovery verifier is the matching proof for the operator safety path: it checks backup
manifest tamper detection, path traversal rejection, invalid digest rejection, wrong passphrase
redaction, restore-preview privacy, and recovery status path redaction.
The platform submission dry-run verifier is the matching proof for ecosystem distribution: it checks
Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, and generic OpenAPI packages before manual
submission without turning Study Anything into a paid standalone app.
The external Agent adapter hardening verifier is the matching proof for user-owned model execution:
it separates fake and external Agent evidence, diagnoses bad external Agent outputs, and redacts
secret-looking metadata values before eval evidence is shared.

For adoption and PMF review, call:

```bash
curl http://127.0.0.1:8000/v1/adoption/telemetry
curl http://127.0.0.1:8000/v1/pmf/readiness
```

Those responses are `adoption-telemetry-v1` and `pmf-readiness-v1`. They contain aggregate local
evidence only: adoption proof status, runtime modes, tool import success, Agent eval pass/fail,
repeat session counts, plugin validation counts, and explicit opt-in feedback counts. They do not
include source text, answers, insights, raw user ids, Agent endpoints, API keys, or browser/video/app
private context.

## Local Core Invariants

The commercial contract treats these as release-blocking local-first invariants:

- No account required for local learning.
- No real model credentials stored by Study Anything.
- User-owned local data, encrypted sync packages, Obsidian export, NotebookLM-style handoff, and
  archive export remain available without hosted services.
- Future hosted services never block Skill Mode, API use, fake demo Agent, user-owned HTTP Agent, or
  local exports.
- Platform-agent distribution remains the main adoption path before PMF.

## Hosted-Service Contracts

These services are designed as future convenience products and remain `contract_only` in the current
alpha:

- `Neural Sync`: encrypted backup and multi-device learning-state sync. The local foundation is
  `sync-package-v1`; remote encrypted storage, conflict resolution, account recovery, support, and
  security review are still required before sale.
- `Neural Publish`: selected learning maps, reading trails, decks, or reports. The local foundation is
  `learning-package-v1` and `second-brain-handoff-v1`; publish consent, sharing controls, abuse
  handling, and artifact versioning are still required.
- `Neural Teams`: shared courses, private workspaces, admin controls, audit/export. The local
  foundation is workspace metadata; tenant isolation, retention controls, billing, support, and
  enterprise security posture are still required.
- `Catalyst`: one-time supporter tier for early builds and roadmap voting. It must not lock the core
  workflow or community plugins behind payment.

Paid services should sell convenience, reliability, collaboration, hosting, and trust operations.
They must not sell lock-in to the core learning workflow, hosted custody of real model keys, access
to user-owned local data, or a closed plugin channel as a requirement.

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
- Local aggregate adoption telemetry and PMF readiness contracts for platform-Agent operators and
  maintainers, with no automatic upload and no private learning content.
- API smoke that verifies learning flow, recovery status, encrypted sync export/inspect, plugin registry trust, local PMF metrics, and Agent audit boundaries.
- Redacted Agent Eval artifact foundation that bridges invocation audit evidence into mature external eval tools such as Promptfoo, DeepEval, LangChain AgentEvals, and Ragas.
- NotebookLM/Obsidian bridge hardening verifier for bounded context packages, source-type coverage,
  hidden instruction rejection, idempotent duplicate handling, and strict second-brain handoff
  privacy.
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
- PMF validation at community scale: real weekly active learners, repeat sessions, mastery delta by
  cohort, plugin activation, explicit feedback, and hosted waitlist conversion.
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
- Public PMF sharing workflow: documented collection norms, maintainer review process, cohort readout
  templates, and opt-in adoption telemetry review.
- Mature Agent quality eval suites wired into CI or documented operator workflows.
