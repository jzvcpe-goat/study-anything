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

## v0.2.13-alpha

- Agent Eval release gates for redacted artifact adapters and external Promptfoo execution wrapper.
- Copy-ready platform packs for Codex, Kimi-compatible agents, and WorkBuddy-style workspaces.
- Platform ecosystem pack verifier tied to privacy and Agent audit/eval acceptance evidence.
- Deterministic platform bundle manifest with sha256 hashes for platform packs, generated import
  assets, key docs, and the repo-local Skill entrypoint.
- CI and release-check drift detection for the platform bundle manifest.

## v0.2.14-alpha

- Layered teaching orchestration so platform Agents can request source-bound overview, glossary,
  examples, and Obsidian-style notes from separate user-owned Agent capabilities.
- `POST /v1/sessions/{session_id}/teaching-layers` for optional pre-quiz teaching output.
- Platform tool manifest, generated import assets, and verifier coverage for
  `study_anything_teaching_layers`.
- Demo and mock HTTP Agents support `teach.overview`, `teach.glossary`, `teach.examples`, and
  `note.scribe`.

## v0.2.15-alpha

- OpenAI-compatible Agent gateway dry-run mode for Kimi/OpenAI-compatible provider setup without
  storing model keys in Study Anything.
- End-to-end verifier for gateway contract, provider registration, teaching layers, quiz, grading,
  mastery, redacted `agent-audit`, and redacted `agent-eval/artifact`.
- Platform packs and bundle manifest include Kimi/Codex/WorkBuddy acceptance commands for clean-clone
  platform Agent setup.
- CLI `agent-add-http --set-default` now registers teaching, quiz, grading, synthesis, scribe, source
  verification, and embedding capabilities by default.

## v0.2.16-alpha

- Clean-clone adoption verifier for external users: `.env` generation, Skill Mode, gateway dry-run,
  teaching layers, quiz, grading, mastery, redacted `agent-audit`, and redacted `agent-eval/artifact`.
- Promptfoo can be invoked from the adoption verifier as the first mature external eval runner while
  docs separate invocation proof from quality evaluation.
- Platform packs for Codex, Kimi-compatible agents, and WorkBuddy-style HTTP workspaces now carry
  clean-clone adoption and diagnostics commands as machine-readable acceptance evidence.
- Adoption diagnostics distinguish localhost API reachability, Docker daemon state, GHCR image
  visibility, Agent endpoint health, and missing provider capability defaults.
- Published-image smoke can produce an explicit slow-GHCR diagnostic fallback when local image pulls
  are the bottleneck but release workflow and manifest evidence are healthy.

## v0.2.17-alpha

- Platform Agent tools now accept Learning Enrichment inputs from browser pages, documents, app
  context, and video slices without exposing raw text in redacted evidence.
- Redacted `agent-quality-eval-v1` reports prove minimum teaching quality across invocation proof,
  overview, glossary, quiz generation, grading, synthesis, and source binding.
- DeepEval adapter path added for mature external quality evaluation, with deterministic fallback for
  local-first environments that have not installed DeepEval.
- Obsidian-compatible Markdown export turns a completed learning loop into source references,
  teaching layers, quiz review, mastery, insights, and enrichment references.
- Kimi, Codex, and WorkBuddy packs now include enrichment, quality eval, Obsidian export, and
  DeepEval smoke evidence.

## v0.2.18-alpha

- Portable `learning-package-v1` export gives platform agents, NotebookLM-style bridges, Obsidian
  pipelines, and local archives a stable handoff artifact.
- CLI and Skill Mode now expose enrichment, teaching layers, quality eval, Obsidian export, learning
  package export, and one-command lesson completion.
- `scripts/verify_platform_lesson_flow.py` proves an enriched lesson can complete through the public
  API and return audit, eval, quality, Obsidian, and learning-package evidence.
- Kimi, Codex, and WorkBuddy packs now require `learning-package-v1` and the enriched platform lesson
  verifier as release evidence.

## v0.2.19-alpha

- `learning-context-package-v1` defines the import boundary for platform-collected web, document,
  video-slice, app-context, Markdown, and Obsidian material.
- Public API and CLI can validate a Learning Context Package, create a session from it, or expand an
  existing session with it.
- Bundled web and note importer plugin examples pass manifest and registry trust review.
- NotebookLM-style support now has a concrete fixture and verifier while remaining independent of an
  official NotebookLM API.
- Obsidian export preserves backlinks from imported context, stabilizes frontmatter, and uses
  vault-safe filenames.
- Kimi, Codex, and WorkBuddy packs now require the importer lesson release gate.

## v0.2.20-alpha

- Reviewed local importer plugins can run through `POST /v1/importers/{plugin_id}/run` after exact
  permission confirmation.
- Importer execution defaults to no network access; `network:http` requires `allow_network=true`.
- Optional retrieval projection adds `GET /v1/retrieval/status`, rebuild/search APIs, and
  retrieval-to-session flows.
- LanceDB is the optional durable retrieval adapter; `STUDY_ANYTHING_RETRIEVAL_BACKEND=memory` is only
  for local smoke and platform Agent development.
- `scripts/verify_importer_runtime_retrieval_flow.py` proves importer runtime -> retrieval -> lesson
  -> quality eval -> Obsidian/learning-package export.

## v0.2.21-alpha

- Platform tool packs expose redacted retrieval/context quality eval gates alongside Agent audit,
  Agent eval, teaching quality, Obsidian export, and learning-package export.
- `GET|POST /v1/sessions/{session_id}/retrieval/eval` returns
  `retrieval-quality-eval-v1` for source binding, snippet minimality, query relevance, context package
  validity, and privacy invariants.
- `scripts/run_external_agent_evals.py --tool retrieval` adds a Ragas-compatible native retrieval
  quality adapter while keeping Promptfoo and DeepEval paths available.
- `scripts/verify_platform_ecosystem_eval_flow.py` proves platform Agent context collection ->
  importer runtime -> enrichment -> retrieval -> retrieval eval -> teaching layers -> learning loop ->
  external eval adapters -> Obsidian and learning-package export.
- Kimi, Codex, and WorkBuddy packs now include one-command ecosystem eval acceptance commands.

## v0.2.24-alpha

- Add a committed deterministic Agent eval baseline and a regression comparison report so release
  checks can detect adapter, trajectory, quality-score, retrieval-score, and privacy regressions.
- Include `study-anything-agent-eval-regression-report-v1` in the local-first release gate without
  requiring judge-model keys or external package installs.
- Keep Promptfoo, DeepEval, LangChain AgentEvals, and Ragas as mature ecosystem targets while making
  fast native gates the default CI path.
- Extend `adoption-proof-v1` and the platform adoption pack with eval baseline evidence.
- Keep real model, platform, and judge-model credentials in the user's Agent/eval environment, not in
  Study Anything.

## v0.3 Next

- Add platform-specific submission docs and hosted examples for Kimi/Codex/WorkBuddy-style wrappers.
- Add live NotebookLM-style adapters only when stable API or reliable platform-agent operation paths
  exist.
- Expand Agent quality eval suites for LangChain AgentEvals, Ragas, retrieval quality, and
  judge-model scoring.
- Hosted-account design for Sync/Teams on top of the local workspace and encrypted package boundaries.
- E2E Playwright tests.
- External Agent embeddings for retrieval and retrieval quality evals.

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
