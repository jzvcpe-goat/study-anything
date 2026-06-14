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

## v0.2.25-alpha

- Tighten the Learning Enrichment Layer contract around source type, locator, provenance, redaction
  policy, source hashes, and secret-like value rejection.
- Add `learning-enrichment-artifact-v1`, a redacted Markdown+HTML micro-lesson export for
  Kimi/Codex/WorkBuddy conversations, NotebookLM-style bridges, and Obsidian pipelines.
- Extend the constrained platform tool manifest with `study_anything_enrichment_artifact_export`.
- Keep browser, file, app, video slicing, real model, and judge-model credentials in the user's
  platform Agent or gateway, not in Study Anything.
- Extend adoption-proof, platform packs, and release checks so enrichment artifacts become part of
  the external operator handoff.

## v0.2.26-alpha

- Add `second-brain-handoff-v1`, the strict redacted export for Obsidian, NotebookLM-style manual
  import, Kimi, Codex, WorkBuddy-style platform Agents, and local archives.
- Add `second-brain-obsidian-note-v1` with frontmatter, backlinks, note graph references, source map,
  learning map, mastery snapshot, and review queue metadata.
- Add `second-brain-archive-manifest-v1` with deterministic file hashes for Obsidian Markdown,
  redacted learning package JSON, and enrichment Markdown/HTML artifacts.
- Keep direct Obsidian and learning-package exports for user-owned workflows while steering shared
  platform logs to `study_anything_second_brain_handoff_export`.
- Extend importer, platform, ecosystem, operator, and adoption checks so second-brain handoff is part
  of external release evidence.

## v0.2.27-alpha

- Add `plugin-sdk-v1`, a machine-readable contract for importer, enrichment, exporter,
  source-verifier, Agent-tool, Agent-panel, and Agent-provider hooks.
- Add `plugin-capability-index-v1` so Kimi, Codex, WorkBuddy, and local operators can inspect
  installed plugin capabilities and trust reports without executing plugin code.
- Add `plugin-package-validation-v1` for local plugin package validation before install, with
  `entrypoints_executed=false`, `package_copied=false`, and no plugin source or Agent secrets
  returned.
- Add `plugins/example-enrichment-importer` and extend `plugins/example-exporter` as second-brain
  exporter sample plugins.
- Split plugin documentation into SDK and registry trust guides while keeping the OSS core
  local-first and marketplace-free.

## v0.2.28-alpha

- Add `deployment-guide-v1`, a redacted API contract that gives Kimi, Codex, WorkBuddy, and local
  operators copyable launch paths for Skill Mode, Docker source builds, and published GHCR images.
- Extend adoption diagnostics with `adoption-diagnostics-v1` and `adoption-diagnostic-plan-v1`, so
  first-run failures distinguish Docker missing, daemon unavailable, `.env` missing, API unreachable,
  Agent endpoint unavailable, provider defaults missing, and GHCR pull timeouts.
- Add manifest-backed fallback evidence to published-image verification when local GHCR layer pulls
  are too slow but the multi-arch image and GitHub docker workflow are healthy.
- Include self-host launch, stop, doctor, diagnostics, and published-image verification scripts in
  the platform adoption pack.
- Keep the launch target API/Skill Mode first; standalone frontend polish remains out of scope for
  this release track.

## v0.2.29-alpha

- Add `agent-eval-policy-v1`, the machine-readable Agent Eval release gate, external adapter policy,
  failure classes, fixtures, and privacy contract for platform Agents.
- Add `agent-eval-report-v1`, the per-session maturity report that combines invocation proof,
  trajectory coverage, teaching quality, retrieval grounding status, export readiness, privacy
  redaction, and external adapter readiness.
- Extend CLI, Skill Mode, Kimi/Codex/WorkBuddy packs, generated platform tools, adoption pack, and
  release checks so external operators can prove Study Anything's Agent workflow actually ran.
- Add fake deterministic and mock HTTP/user-owned Agent eval fixtures for stable adapter tests.
- Keep Promptfoo, DeepEval, LangChain AgentEvals, and Ragas optional unless an operator explicitly
  requires those external gates in their own environment.

## v0.3.0-alpha

- Add `commercial-readiness-v1`, the machine-readable OSS/local-first commercial readiness contract
  for platform Agents, release checks, and external operators.
- Expose `GET /v1/commercial/readiness` and `study_anything commercial-readiness` so Kimi, Codex,
  WorkBuddy, or a local Agent can answer what is ready for GitHub launch and what remains future
  hosted-service work.
- Keep hosted Sync, Publish, Teams, Catalyst billing, remote accounts, SSO, and standalone app
  commercialization as `contract_only` or `not_ready` while preserving the free local core.
- Add commercial readiness verification to release checks, generated platform assets, adoption pack,
  and platform tool validation.

## v0.3.1-alpha

- Add `ecosystem-submission-v1`, the machine-readable submission metadata for Kimi-compatible,
  Codex Skill, WorkBuddy-style HTTP, and generic OpenAPI platform handoff.
- Add `ecosystem-submission-verification-v1` so release checks prove no standalone frontend
  requirement, no Study Anything model-key custody, no raw learning data in submission assets, and no
  high-risk management endpoints in the imported platform tool surface.
- Include the submission manifest, verifier, docs, and release notes in the generated platform
  bundle and adoption pack.

## v0.3.2-alpha

- Add `adoption-telemetry-v1`, a local aggregate telemetry contract for clean-clone proof, runtime
  mode, platform tool import success, Agent eval pass/fail, repeat local sessions, plugin validation,
  and explicit opt-in feedback counts.
- Add `pmf-readiness-v1`, a local PMF readout that keeps hosted paid services and standalone app
  monetization out of the launch path until adoption evidence is stronger.
- Add `scripts/verify_adoption_telemetry.py` and wire adoption telemetry into platform tools,
  adoption proof, ecosystem submission, release checks, and PMF export.
- Maintain the privacy boundary: no source text, answers, insights, raw user ids, Agent endpoints,
  API keys, or browser/video/app private context in telemetry evidence.

## v0.3.3-alpha

- Add `agent-gateway-hardening-verification-v1`, a local verifier for user-owned HTTP Agent gateway
  safety, health diagnostics, malformed output handling, and privacy boundaries.
- Reject Agent provider endpoint credentials, secret-like query parameters, and secret metadata keys
  so model credentials remain inside the user's gateway or platform Agent.
- Add redacted Agent health diagnostics with stable `diagnostic_code` values for configuration
  errors, unavailable gateways, malformed JSON, invalid schema, and successful contract acceptance.
- Include the gateway hardening verifier in release checks, external adoption proof, ecosystem
  submission, platform packs, and adoption pack assets.

## v0.3.4-alpha

- Add `notebooklm-obsidian-bridge-hardening-v1`, a local verifier for NotebookLM-style fixtures,
  Obsidian handoff, Learning Enrichment artifacts, learning-package export, and strict
  second-brain archive privacy.
- Harden Learning Context Package validation against hidden/system prompt-like instructions in
  text, metadata, provenance, and nested values.
- Deduplicate exact repeated context items while rejecting reused `item_id` values with conflicting
  source content.
- Redact raw Agent metadata and endpoints from `learning-package-v1` teaching-layer exports while
  keeping provider/task/status summary fields.
- Include the bridge hardening verifier in release checks, external adoption proof, ecosystem
  submission, platform packs, and adoption pack assets.

## v0.3.5-alpha

- Add quarantine-first plugin handling for local plugin packages.
- Keep `POST /v1/plugins/install` metadata-first: confirmed permissions now quarantine by default,
  while `approve_install=true` is required for the final install copy.
- Add trust-policy lifecycle states for `previewed`, `quarantined`, `installed`, and `blocked`.
- Block `do_not_install` recommendations before both quarantine and install copies, including
  registry digest mismatches and invalid registry signatures.
- Add `plugin-quarantine-verification-v1`, covering API default quarantine, CLI default quarantine,
  explicit approved install, digest-mismatch blocking, and no entrypoint execution.
- Include the plugin quarantine verifier in release checks, external adoption proof, ecosystem
  submission, platform packs, and adoption pack assets.

## v0.3.6-alpha

- Add `security-recovery-hardening-verification-v1`, an offline verifier for backup manifest,
  recovery status, and encrypted sync restore-preview safety.
- Harden backup manifest verification against path traversal, absolute paths, invalid sha256 values,
  duplicate records, missing files, and tampered files.
- Keep backup/restore diagnostics shareable by returning relative backup member names instead of
  absolute local paths.
- Verify wrong passphrases and ciphertext tampering produce redacted sync-package diagnostics.
- Verify restore-preview stays count-only and never returns source text, answers, Agent endpoints,
  passphrases, PMF contacts, or absolute paths.
- Include the security recovery verifier in release checks, external adoption proof, ecosystem
  submission, platform packs, and adoption pack assets.

## v0.3.7-alpha

- Add `platform-submission-dry-run-v1`, a machine-readable dry-run report for Kimi-compatible,
  Codex Skill, WorkBuddy-style HTTP, and generic OpenAPI submission packages.
- Verify per-platform import assets, entrypoints, acceptance commands, warnings, and manual
  submission checklists before claiming ecosystem readiness.
- Keep the report redacted: no raw source, answers, Agent endpoint secrets, real model keys, or
  private platform context.
- Include the dry-run verifier in release checks, external adoption proof, ecosystem submission,
  platform packs, operator drill evidence, and adoption pack assets.

## v0.3.8-alpha

- Add `external-agent-adapter-hardening-v1`, a release gate for real external HTTP Agent eval
  evidence.
- Separate fake deterministic Agent evidence from user-owned external Agent evidence in the
  hardening report.
- Cover malformed JSON, invalid status, missing content, invalid score, invalid confidence,
  timeouts, missing citations, and missing declared capabilities.
- Redact secret-looking string values in Agent metadata even when the field name itself is not a
  secret-like key.
- Include the verifier in release checks, external adoption proof, ecosystem submission, platform
  packs, operator drill evidence, and adoption pack assets.

## v0.3.9-alpha

- Add `platform-manual-submission-rehearsal-v1`, a redacted handoff report for external platform
  operators.
- Verify the manual path from adoption-pack unpacking through tool import, runtime health,
  user-owned HTTP Agent setup, first lesson, export evidence, diagnostics, and failure remediation.
- Include the report in release checks, external adoption proof, ecosystem submission, platform packs,
  bundle manifest, operator drill evidence, and adoption pack assets.

## v0.3.10-alpha

- Add `first-run-lesson-authoring-kit-v1`, a redacted first-lesson kit for Kimi/Codex/WorkBuddy and
  generic OpenAPI platform Agents.
- Include bilingual copyable prompts, a tool-call sequence, Learning Context Package template,
  user-owned HTTP Agent setup, expected output schemas, export evidence, remediation, and privacy
  assertions.
- Wire the kit into release checks, external adoption proof, ecosystem submission, platform packs,
  bundle manifest, manual rehearsal, operator drill evidence, and adoption pack assets.

## v0.3.11-alpha

- Add `external-eval-marketplace-harness-v1`, a redacted marketplace-quality eval contract for
  external platform submissions.
- Separate required native gates from optional Promptfoo, DeepEval, LangChain AgentEvals, and
  Ragas-compatible adapters.
- Include fixtures, sample eval cases, timeout policy, expected evidence schema, failure remediation,
  and privacy assertions.
- Wire the harness into release checks, external adoption proof, ecosystem submission, platform packs,
  bundle manifest, manual rehearsal, operator drill evidence, and adoption pack assets.

## v0.3.12-alpha

- Add `plugin-ecosystem-adoption-kit-v1`, a copy-ready plugin ecosystem adoption kit for Kimi,
  Codex, WorkBuddy, and generic platform Agents.
- Verify bundled importer/exporter/Agent-provider sample plugins, registry digests, permissions,
  quarantine-first install policy, platform-pack commands, and privacy assertions.
- Keep plugin review metadata-first: sample plugin entrypoints are not executed during adoption
  verification and third-party plugins are not downloaded automatically.
- Wire the kit into release checks, external adoption proof, ecosystem submission, platform packs,
  bundle manifest, manual rehearsal, operator drill evidence, and adoption pack assets.

## v0.3.13-alpha

- Add `deployment-hardening-verification-v1`, a redacted deployment adoption report for external
  operators and platform Agents.
- Verify Skill Mode, published-image, and source-build paths; Docker/Compose diagnostics; non-ASCII
  checkout guidance; port conflict checks; GHCR manifest evidence; local pull-timeout fallback; and
  user-owned HTTP Agent endpoint recovery.
- Prefer published images or Skill Mode for first-run users, while keeping source builds as the
  contributor path.
- Wire the verifier into release checks, external adoption proof, ecosystem submission, platform
  packs, bundle manifest, manual rehearsal, operator drill evidence, and adoption pack assets.

## v0.3.14-alpha

- Add `learning-enrichment-bridge-verification-v1`, a redacted operator bridge report for Learning
  Enrichment, NotebookLM-style manual import/export, Obsidian, and second-brain workflows.
- Verify all supported external context source types: web, document, video slice, app context,
  Markdown note, and Obsidian note.
- Prove Markdown+HTML micro-lessons preserve source hashes, expose a safe `learning-enrichment-artifact-v1`
  structure, and do not depend on scripts or raw source dumps.
- Keep direct user-owned Obsidian and learning-package exports available while requiring strict
  second-brain handoff evidence for shared platform logs.
- Wire the verifier into release checks, external adoption proof, ecosystem submission, Kimi/Codex/
  WorkBuddy packs, bundle manifest, manual rehearsal, operator drill evidence, and adoption pack
  assets.

## v0.3.15-alpha

- Add `agent-eval-marketplace-enforcement-v1`, a redacted release and ecosystem-submission gate for
  Agent eval marketplace readiness.
- Prove native Agent eval gates remain required while Promptfoo, DeepEval, LangChain AgentEvals, and
  Ragas stay optional external judge integrations unless an operator explicitly uses required mode.
- Verify missing-runtime diagnostics, timeout controls, malformed judge output diagnostics,
  required-mode non-zero failures, baseline regression, platform-pack evidence, ecosystem submission
  evidence, and adoption-pack inclusion.
- Keep external judge keys, model keys, Agent endpoint secrets, raw source text, learner answers, and
  private browser/video context out of shared eval evidence.
- Wire the verifier into release checks, external adoption proof, ecosystem submission, Kimi/Codex/
  WorkBuddy packs, bundle manifest, manual rehearsal, operator drill evidence, submission dry-run,
  and adoption pack assets.

## v0.3.16-alpha

- Add `platform-adoption-feedback-diagnostics-v1`, a redacted release and ecosystem-submission gate
  for external platform import diagnostics.
- Add `platform-feedback-package-v1`, a local-only feedback package for Kimi, Codex, WorkBuddy, and
  generic OpenAPI operators.
- Prove pack schema, OpenAPI/OpenAI tool import assets, version drift, missing commands, unsupported
  platform capabilities, local endpoint health, Agent eval evidence, and privacy redaction are
  diagnosable before public handoff.
- Keep feedback packages free of raw source text, learner answers, Agent prompts, personal profiles,
  Agent endpoint secrets, judge keys, model keys, and private browser/video context.
- Wire diagnostics and feedback package evidence into release checks, external adoption proof,
  ecosystem submission, Kimi/Codex/WorkBuddy packs, bundle manifest, manual rehearsal, operator
  drill evidence, and adoption pack assets.

## v0.3.17-alpha

- Add `platform-field-adoption-rehearsal-v1`, a redacted field rehearsal report for Kimi, Codex,
  WorkBuddy, and generic OpenAPI platform import.
- Add `platform-import-failure-fixture-v1` mock failed-import fixtures covering schema mismatch,
  missing local gateway, unsupported auth mode, tool naming drift, timeout, browser localhost
  restrictions, package corruption, and version drift.
- Keep fixtures actionable with detection signals, likely causes, safe feedback fields, and next
  commands while excluding raw source text, learner answers, Agent prompts, real endpoints, model
  keys, and browser/video private context.
- Wire field rehearsal evidence into release checks, external adoption proof, ecosystem submission,
  Kimi/Codex/WorkBuddy packs, bundle manifest, manual rehearsal, operator drill evidence, and the
  adoption pack.

## v0.3.18-alpha

- Add `platform-support-triage-v1`, a GitHub-first support desk gate for external platform adoption
  failures.
- Add `platform-support-issue-template-v1` issue templates for platform import failures, local
  gateway failures, published-image pull failures, Agent eval evidence failures, and docs confusion.
- Add `platform-support-ticket-fixture-v1` mock tickets with version, platform, command, diagnostic
  code, fixture id, redacted logs, next commands, and linked import failure fixtures.
- Add maintainer playbook coverage for schema mismatch, missing local gateway, unsupported auth mode,
  tool naming drift, timeout, browser localhost restrictions, package corruption, and version drift.
- Keep support evidence manual, redacted, and free of raw source text, learner answers, Agent prompts,
  Agent endpoints, model keys, personal profiles, and private browser/video/app context.
- Wire support triage into release checks, external adoption proof, ecosystem submission, Kimi/Codex/
  WorkBuddy packs, bundle manifest, docs, issue templates, and the adoption pack.

## v0.3.19-alpha

- Add `platform-onboarding-readiness-v1`, a first external adopter onboarding gate for Kimi, Codex,
  WorkBuddy, and generic OpenAPI/MCP platform use.
- Add `first-external-adopter-walkthrough-v1` shortest success paths and failure fallback paths for
  each supported platform shape.
- Add `maintainer-sla-labels-v1` and `maintainer-rotation-checklist-v1` so maintainers can triage
  intake, needs-repro, confirmed, blocked-by-platform, docs-fix, release-blocker, and resolved states.
- Add `platform-triage-dashboard-v1` generated JSON/Markdown for support bundle completeness,
  diagnostic distribution, fixture coverage, privacy scan, and release blockers.
- Add `platform-release-blocker-fixture-v1` mock fixtures for tool import, local gateway, published
  image, Agent eval, and support-bundle privacy blockers.
- Wire onboarding readiness into release checks, external adoption proof, ecosystem submission,
  Kimi/Codex/WorkBuddy packs, bundle manifest, docs, release notes, and the adoption pack.

## v0.3.20-alpha

- Add `public-support-status-v1`, a publishable support-status report for external adopters and
  maintainers.
- Add `public-maintainer-dashboard-v1` JSON and Markdown generated dashboards.
- Add `public-status-linkage-fixture-v1` fixtures mapping intake, needs-repro, confirmed,
  blocked-by-platform, docs-fix, release-blocker, and resolved labels into public statuses.
- Keep public status metadata-only: schema names, release version, platform status, fixture ids,
  fixture hashes, commands, labels, and documented limitations.
- Explicitly exclude raw source text, learner answers, Agent prompts, real Agent endpoints, model
  keys, personal profiles, full support bundle payloads, and browser/video/app private context.
- Wire public support status into release checks, external adoption proof, ecosystem submission,
  platform packs, bundle manifest, docs, release notes, and the adoption pack.

## v0.3.21-alpha

- Add `adopter-evidence-archive-v1`, a single external adopter evidence archive and maintainer
  handoff package.
- Add `adopter-evidence-fixture-v1` fixtures for successful release, local GHCR pull timeout,
  needs-repro, release-blocker, platform-blocked, and resolved support states.
- Package public support status, maintainer dashboard, CI commands, Docker manifest evidence,
  platform pack checksums, adoption pack checksum, known limitations, and handoff checklist.
- Keep the archive metadata-only, excluding raw source text, learner answers, Agent prompts, Agent
  endpoints, model keys, personal profiles, support bundle private payloads, and browser/video/app
  private context.
- Wire adopter evidence archive into release checks, external adoption proof, ecosystem submission,
  platform packs, bundle manifest, docs, release notes, and the adoption pack.

## v0.3.22-alpha

- Add `published-image-evidence-v1`, a public evidence layer for GHCR published-image readiness.
- Add `published-image-evidence-fixture-v1` fixtures for manifest pass with local pull timeout,
  missing manifest platform, docker-images failure, GHCR unavailable, remote smoke pass, and remote
  smoke failure.
- Separate local Docker/GHCR pull slowness from true release blockers by recording manifest
  platforms, docker-images workflow evidence, local smoke status, optional remote replay commands, and
  release-gate classifications.
- Keep published-image evidence metadata-only, excluding raw source text, learner answers, Agent
  prompts, Agent endpoints, model keys, support bundle private payloads, and local absolute paths.
- Wire published-image evidence into release checks, external adoption proof, ecosystem submission,
  platform packs, bundle manifest, adopter evidence archive, docs, release notes, and the adoption
  pack.

## v0.3.25-alpha

- Add `release-asset-adoption-v1`, a public evidence layer for GitHub Release asset adoption replay.
- Add `release-asset-adoption-fixture-v1` fixtures for asset-only pass, missing asset, digest
  mismatch, corrupted pack, missing published-image evidence, and network-unavailable states.
- Make the GitHub Release page the external platform entrypoint by validating release zip assets,
  GitHub sha256 digests, adoption-pack manifests, embedded published-image evidence, and optional
  published-image or Skill Mode runtime replay.
- Keep release-asset evidence metadata-only, excluding raw source text, learner answers, Agent
  prompts, Agent endpoints, model keys, support bundle private payloads, and local absolute paths.
- Wire release-asset adoption proof into release checks, external adoption proof, ecosystem
  submission, platform packs, bundle manifest, docs, release notes, and the adoption pack.

## v0.3.26-alpha

- Add `platform-agent-release-replay-v1`, a public evidence layer for importing platform-agent tool
  contracts from GitHub Release assets and replaying the minimum Study Anything learning tool chain.
- Add `scripts/replay_platform_agent_from_release.py` with Kimi, Codex, WorkBuddy, and generic
  OpenAPI profiles plus metadata-only, Skill Mode, external API, and published-image runtime modes.
- Promote `study-anything-platform-agent-replay.zip` to a top-level release asset so external
  operators can verify tool import and replay evidence directly from the Release page.
- Keep replay transcripts redacted, excluding raw source text, learner answers, Agent prompts,
  Agent endpoints, model keys, support bundle private payloads, and local absolute paths.
- Wire platform-agent release replay into release checks, ecosystem submission, platform packs,
  bundle manifest, docs, release notes, and the adoption pack.

## v0.3 Next

- `v0.3.27`: Real release-asset replay against GitHub prerelease plus published-image runtime
  fallback hardening, depending on which external operator path fails first.
- Later: standalone UI rebuild only after the API/Skill/platform-agent route is stable.

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
