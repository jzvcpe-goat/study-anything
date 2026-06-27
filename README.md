# Study Anything

Study Anything is an open-source, self-host-first learning system for AI-native study workflows. The core idea is simple: reading should produce artifacts, and artifacts should deepen reading.

The alpha MVP runs a full local learning loop:

1. Add a reading source.
2. Generate source-bound quiz items.
3. Submit answers.
4. Grade the answers.
5. Update mastery.
6. Synthesize an insight.
7. Save a scribe log.
8. Detect incubation needs.
9. Discard or keep the card.

## Principles

- Apache-2.0 open-source core.
- Local-first data ownership.
- Bring Your Own Agent: no hardcoded real model default, no stored model API keys.
- Self-host before SaaS.
- Encrypted local sync packages before hosted Sync.
- Optional privacy-preserving topology projection: Postgres remains canonical, FalkorDB stays disposable.
- Optional paid services only after PMF, inspired by Obsidian-style Sync, Publish, Teams, and Catalyst offerings.
- API/Skill-as-product: external agents, CLIs, and future platform plugins are clients of the public API.

## Start Here

For a first-time user, do not start with Docker, model keys, or architecture docs.

On macOS, double-click:

```text
START_HERE.command
```

Or run this in a terminal:

```bash
./scripts/start_here.sh
```

It runs a zero-key, no-Docker disposable demo, verifies the learning loop, and stops the temporary
API before exiting. Success means you see:

```text
Done. You have proved the local learning loop once.
```

Read the ultra-short Chinese quickstart at `QUICKSTART.md`, then the fuller beginner guide at
`docs/getting-started.md`. Use `./scripts/start_here.sh --foreground` only when an Agent shell does
not preserve background processes.

Use Skill Mode directly when you want to try the learning loop without Docker:

```bash
./scripts/run_skill_mode_demo.sh
```

This creates a local Python virtual environment when needed, starts the API, verifies the CLI learning
loop, and stops the API in one command. This is the safest path for terminal-capable LLM agents whose
shell tools may not preserve background processes. For a persistent local API, run
`./scripts/launch_skill_mode.sh` and stop it with `./scripts/stop_skill_mode.sh`. If your agent or
desktop shell does not preserve background processes, use `./scripts/launch_skill_mode.sh --foreground`
and keep that terminal open while a browser or another agent uses the API.

## Adoption Smoke

For Kimi Work, Codex, WorkBuddy-style HTTP workspaces, or another platform Agent, verify the
copy-ready adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_platform_operator_drill.py --check
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_external_eval_marketplace_harness.py --check
python3 scripts/verify_agent_eval_marketplace_enforcement.py --check
python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check
python3 scripts/generate_platform_feedback_package.py --check
python3 scripts/generate_platform_field_rehearsal.py --check
python3 scripts/verify_platform_field_rehearsal.py --check
python3 scripts/generate_platform_support_triage.py --check
python3 scripts/verify_platform_support_triage.py --check
python3 scripts/generate_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py --check
python3 scripts/generate_platform_public_support_status.py --check
python3 scripts/verify_platform_public_support_status.py --check
python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check
python3 scripts/verify_learning_enrichment_bridge.py --check
python3 scripts/verify_agent_eval_baseline.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The operator drill emits `study-anything-operator-drill-v1`, proving the pack can be consumed as an
external platform tool directory. The first lesson kit emits `first-run-lesson-authoring-kit-v1`,
with copyable Kimi/Codex/WorkBuddy prompts, tool-call sequence, context-package template, local Agent
setup, and export evidence. The external eval harness emits
`external-eval-marketplace-harness-v1`, tying native eval gates, optional mature adapters, fixtures,
timeouts, and redaction checks into one platform-submission contract. The Agent eval marketplace
enforcement verifier emits `agent-eval-marketplace-enforcement-v1`, proving external judge adapters
are optional until explicitly required, required judge mode fails closed, baseline evidence is current,
and no judge/model keys are stored by Study Anything. The plugin ecosystem kit emits
`plugin-ecosystem-adoption-kit-v1`, proving bundled sample plugins, registry digests,
quarantine-first trust policy, platform-pack commands, and redacted evidence are aligned without
executing plugin entrypoints. The field adoption rehearsal emits
`platform-field-adoption-rehearsal-v1` and includes `platform-import-failure-fixture-v1` mock
fixtures for common platform import failures such as schema mismatch, missing local gateway,
unsupported auth mode, tool naming drift, timeout, localhost restrictions, package corruption, and
version drift. The Learning Enrichment bridge verifier emits
`learning-enrichment-bridge-verification-v1`, proving platform-collected web, document, app,
video-slice, Markdown, and Obsidian context can become source-bound micro-lessons, NotebookLM-style
manual bridge evidence, Obsidian handoff, and strict second-brain exports without a standalone
frontend. The support triage verifier emits `platform-support-triage-v1`, proving GitHub issue templates,
mock support tickets, support bundle fields, and maintainer playbook entries are present and redacted
for external platform failures. The onboarding readiness verifier emits
`platform-onboarding-readiness-v1` and `platform-triage-dashboard-v1`, proving first external
adopter walkthroughs, maintainer SLA labels, release-blocker fixtures, and privacy-safe triage
dashboard evidence are included before handoff. The public support status verifier emits
`public-support-status-v1` and `public-maintainer-dashboard-v1`, proving maintainers can publish
platform status, known blocker fixtures, SLA labels, commands, and fixture hashes without exposing
support bundle private fields. The adoption verifier emits `adoption-proof-v1`,
proving the Skill Mode runtime, importer/enrichment/retrieval/teaching/eval
loop, enrichment artifact, Obsidian export, and NotebookLM-style handoff without requiring the
standalone frontend or storing real model keys in Study Anything.

Maintainers and external testers can verify the project from a disposable clean clone:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
python3 scripts/verify_deployment_hardening.py --check
```

This checks Skill Mode, the OpenAI-compatible gateway dry-run, teaching layers, quiz, grading,
mastery, `agent-audit`, `agent-eval/artifact`, `agent-eval/report`, and the deployment-hardening
contract for Skill Mode, published images, source builds, Docker diagnostics, GHCR fallback, and
operator pack inclusion. See `docs/adoption.md` for Promptfoo, Kimi, Codex, WorkBuddy, diagnostics,
and published-image fallback paths.

## Docker Self-Host

Install Docker Desktop, start its daemon, then run:

```bash
python3 scripts/setup_env.py
./scripts/doctor.sh
./scripts/launch_self_host.sh
```

`doctor.sh` checks Docker, Compose, required tools, port availability, API health, Agent gateway
reachability hints, plugin directories, and recovery commands before you launch.

The default Docker profile is `core`: API and Postgres. It starts in the background so the
terminal returns. Enable observability and optional topology services later with
`STACK_PROFILE=full ./scripts/launch_self_host.sh`.

If your checkout path contains non-ASCII characters, Docker Desktop BuildKit/buildx may fail before
the app build starts. Use `USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh` or clone the repo
to an ASCII-only path such as `~/study-anything` for local source builds.

Open:

- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/v1/health
- Deployment guide: http://localhost:8000/v1/deployment/guide
- Commercial readiness: http://localhost:8000/v1/commercial/readiness
- Adoption telemetry: http://localhost:8000/v1/adoption/telemetry
- PMF readiness: http://localhost:8000/v1/pmf/readiness
- Recovery status: http://localhost:8000/v1/recovery/status
- Encrypted sync status: http://localhost:8000/v1/sync/status
- Knowledge graph status: http://localhost:8000/v1/graph/status
- Agent eval policy: http://localhost:8000/v1/evals/policy
- Agent eval artifact: `GET /v1/sessions/{session_id}/agent-eval/artifact`
- Agent eval report: `GET /v1/sessions/{session_id}/agent-eval/report`
- Langfuse: http://localhost:3000

## Published Images

Use the multi-architecture `v0.3.22-alpha` API image when you want to skip local API builds:

```bash
python3 scripts/setup_env.py
USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh
```

The launcher pulls the API image and shows layer progress so first-run downloads remain
understandable on slower connections. The release image supports `linux/amd64` and `linux/arm64`.

Maintainers can verify the public images with:

```bash
python3 scripts/verify_deployment_hardening.py --check
python3 scripts/verify_published_image_launch.py --tag v0.3.22-alpha
python3 scripts/generate_published_image_evidence.py --check
python3 scripts/verify_published_image_evidence.py --check
```

`published-image-evidence-v1` records manifest platforms, docker-images workflow evidence,
local pull-timeout fallback rules, optional remote smoke replay, and release-blocking
classifications without learning data, Agent endpoints, local paths, or model secrets.

Release handoff evidence is packaged as `adopter-evidence-archive-v1`:

```bash
python3 scripts/generate_adopter_evidence_archive.py --check
python3 scripts/verify_adopter_evidence_archive.py --check
```

If a platform Agent is driving setup, it can call `GET /v1/deployment/guide`,
`GET /v1/commercial/readiness`, `GET /v1/adoption/telemetry`, and `GET /v1/pmf/readiness` after the
API is reachable. `deployment-guide-v1` gives copyable launch commands, failure classes, and the
privacy boundary for user-owned Agents.
`commercial-readiness-v1` states that the GitHub OSS/platform-Agent launch path is ready while hosted
Sync, Publish, Teams, Catalyst, billing, SSO, and a standalone app remain future work.
`adoption-telemetry-v1` and `pmf-readiness-v1` expose local aggregate evidence only; no source text,
answers, insights, raw user ids, Agent endpoints, API keys, or browser/video/app private context are
included. `ecosystem-submission-v1` is the v0.3.4 no-frontend submission contract for
Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, and generic OpenAPI platforms.

## Bring Your Own Agent

Study Anything ships with a deterministic fake agent for tests and demos. Real reasoning is performed by an agent that the user owns and runs outside Study Anything.

Supported MVP provider shapes:

- `fake_agent`: deterministic local provider for tests and demos.
- `http_agent`: user-owned local or private HTTP gateway. This is the recommended MVP path.
- `cli_agent`: reserved adapter, disabled by default until explicitly allowlisted.
- `mcp_agent`: plugin ecosystem extension point.

The agent flow mirrors tools such as OpenClaw and Codex: the user controls the model, credentials, tools, and reasoning inside their own agent; Study Anything sends structured learning tasks and validates structured results.

For Kimi/OpenAI-compatible providers, verify the local gateway without a real key first:

```bash
python3 scripts/verify_openai_compatible_gateway.py --contract-only
python3 scripts/verify_agent_gateway_hardening.py --contract-only
python3 scripts/verify_external_agent_adapter_hardening.py --contract-only
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
python3 scripts/verify_agent_gateway_hardening.py
python3 scripts/verify_notebooklm_obsidian_bridge_hardening.py
python3 scripts/verify_plugin_quarantine.py
python3 scripts/verify_security_recovery_hardening.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

Use `--contract-only` when your current Agent runner cannot open localhost sockets; it proves the
gateway, adapter, and eval redaction contracts in-process. `--gateway-only` and the hardening
commands without `--contract-only` remain the stricter runtime checks.

Then replace dry-run mode with your own gateway, model, credentials, tools, and network policy.
Keep credentials in the gateway environment; Study Anything rejects endpoint URLs or provider
metadata that contain secret-like fields.

## Agent Eval

Study Anything now emits a redacted Agent eval artifact that can be consumed by mature open-source
eval tools instead of relying on a small homegrown judge. It also emits `agent-eval-policy-v1` and
`agent-eval-report-v1` so platform Agents can prove the Study Anything Agent workflow actually ran.
The foundation targets Promptfoo for
HTTP/CI contract gates, DeepEval for Python task-completion and quality metrics, LangChain AgentEvals
for trajectory matching, and Ragas-style retrieval/context grounding.

Against a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
.venv/bin/python scripts/verify_agent_eval_assets.py
.venv/bin/python scripts/verify_external_eval_marketplace_harness.py --check
.venv/bin/python scripts/verify_agent_eval_marketplace_enforcement.py --check
API_BASE=http://127.0.0.1:8000 .venv/bin/python scripts/run_external_agent_evals.py --tool report --create-session --required
```

When Node/npm package installation is allowed, run the Promptfoo adapter directly through the wrapper:

```bash
API_BASE=http://127.0.0.1:8000 \
  .venv/bin/python scripts/run_external_agent_evals.py --tool promptfoo --create-session --required
```

See `docs/agent-eval.md`, `docs/eval-frameworks.md`, and `evals/promptfoo/agent-eval-artifact.yaml`.

For retrieval/context quality gates:

```bash
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  .venv/bin/python scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

## Platform Agent Package

Use the constrained tool manifest when integrating Study Anything into Codex, Kimi Work,
WorkBuddy-style workspaces, or private Agent platforms:

```text
platform/study-anything-platform-tools.json
```

The manifest exposes only the learning loop tools and redacted evidence endpoints. It does not expose
model/provider setup, plugin installation, encrypted sync export, or other management APIs.

Generated import assets are checked in for platforms that prefer OpenAPI or function tools:

```text
platform/generated/study-anything-platform-openapi.json
platform/generated/study-anything-openai-tools.json
platform/generated/study-anything-tool-catalog.md
platform/ecosystem-submission.json
platform/generated/study-anything-platform-bundle.json
platform/generated/study-anything-first-lesson-authoring-kit.json
platform/generated/study-anything-plugin-ecosystem-adoption-kit.json
platform/generated/study-anything-platform-field-rehearsal.json
fixtures/platform-import-failures/*.json
```

Copy-ready starter packs are checked in for platform ecosystems:

```text
platform/packs/codex
platform/packs/kimi
platform/packs/workbuddy
```

Regenerate or verify these assets after editing the manifest, platform packs, or bundled docs:

```bash
python3 scripts/generate_platform_agent_assets.py
python3 scripts/generate_platform_agent_assets.py --check
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_platform_ecosystem_packs.py
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check
python3 scripts/generate_platform_field_rehearsal.py --check
python3 scripts/verify_platform_field_rehearsal.py --check
python3 scripts/generate_platform_bundle_manifest.py --check
```

Validate a running platform-tool integration with:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
```

`./scripts/run_skill_mode_demo.sh` runs these checks automatically after the CLI smoke.

## Skill Mode

The repo includes a standard-library CLI and a repo-local Codex skill:

```bash
./scripts/run_skill_mode_demo.sh
```

For persistent sessions, use `./scripts/launch_skill_mode.sh` and then
`python3 scripts/study_anything_cli.py demo`.

Connect a user-owned HTTP agent, import Learning Context Packages, start source-bound sessions, attach
enrichment, generate teaching layers, answer questions, inspect mastery, export Obsidian notes, and
create enrichment artifacts plus portable learning packages through the same public API. Chat-only LLM products cannot run local scripts or reach
`localhost`; use a terminal-capable agent or expose the API securely. Kimi can be the user-owned
reasoning agent through the local gateway, but a browser-only Kimi chat cannot operate the repo-local
skill by itself. For Kimi API setup, see `docs/kimi-agent-gateway.md`. For general Skill Mode usage,
see `docs/skill-mode.md`.

For Codex, Kimi, WorkBuddy, or another platform Agent, see `docs/platform-agent-integrations.md`.
Platform integrations should return `agent-audit`, `agent-eval`, `agent-eval-report`, `agent-quality-eval`,
`retrieval-quality-eval`, `learning-enrichment-artifact-v1`,
`learning-enrichment-bridge-verification-v1`, Obsidian, and `learning-package-v1` evidence after completed learning and
retrieval-backed loops. Importer integrations should first validate `learning-context-package-v1`.

## Repository Layout

```text
apps/api/                  FastAPI app and learning engine
docs/                      Architecture, roadmap, plugin SDK, commercial model
evals/                     External eval tool templates
infra/compose/             Docker Compose stack
platform/                  Platform Agent tool manifest and generated import assets
fixtures/notebooklm/       NotebookLM-style Learning Context Package fixtures
plugins/example-exporter/  Example exporter and second-brain handoff template
plugins/example-agent-provider/ Example agent provider manifest
plugins/example-web-importer/ Example web importer manifest
plugins/example-note-importer/ Example Markdown/Obsidian importer manifest
plugins/example-enrichment-importer/ Example importer plus enrichment template
scripts/                   Local smoke helpers
skills/study-anything/     Repo-local Agent skill for CLI learning flows
```

## Plugin Ecosystem

The alpha plugin surface supports SDK contracts, manifest validation, capability indexing, local
package validation, discovery, registry digest review, and permission-gated local installation for
importers, enrichment builders, agent providers, agent tools, source verifiers, quiz generators,
graders, exporters, and future client panels. See `docs/plugin-sdk.md`, `docs/plugin-registry.md`,
`docs/plugins.md`, and `plugins/example-exporter`.

Inspect the SDK and validate a local package without executing plugin code:

```bash
python3 scripts/study_anything_cli.py plugin-sdk
python3 scripts/study_anything_cli.py plugin-capabilities
python3 scripts/study_anything_cli.py plugin-validate plugins/example-exporter
```

Install an explicitly selected local plugin with the CLI without downloading or executing remote code:

```bash
python3 scripts/install_local_plugin.py plugins/example-exporter
```

Review local registry metadata before installing or updating community plugins:

```bash
curl http://localhost:8000/v1/plugins/registry-review
```

The registry review path reports digest/signature status, update candidates, blocked entries, and
manual-review actions without downloading or executing plugin code.

For external platform submissions, run:

```bash
python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check
python3 scripts/verify_plugin_ecosystem_adoption_kit.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

The report proves the adoption pack includes `plugins/registry.json`, all bundled sample plugin
manifests and sources, digest-verified registry metadata, quarantine-first install policy, and
redacted platform-pack evidence.

## Local PMF Signals

Study Anything includes local-only API metrics for PMF validation:

- completed learning loops and completion rate
- active learner hashes and repeat usage
- mastery delta and answer volume
- ready plugin count
- opt-in local interest for future Sync, Publish, Teams, Catalyst, or hosted alpha services

These metrics stay on the self-hosted machine by default. They do not expose reading prose, quiz prompts,
answers, grading feedback, insights, Agent metadata, raw user IDs, or raw contact values.

## Self-Hosting

See `docs/self-hosting.md` for launch, data, agent provider, and plugin mounting notes.

## Local Backups

Protect the local-first learning state with an explicit backup before upgrades:

```bash
python3 scripts/self_host_data.py backup
```

The backup includes the canonical app Postgres dump, Agent configuration volume, checksums, and a
private `env.snapshot`. See `docs/self-hosting.md` for restore commands and optional operational
volume backups.

For portable local-first state packages, the API can also generate an encrypted sync package with a
user-supplied passphrase:

```bash
curl -X POST http://localhost:8000/v1/sync/export \
  -H 'Content-Type: application/json' \
  -d '{"passphrase":"choose a long local passphrase"}'
```

Study Anything does not store the passphrase or upload the package. You can inspect or preview restore
impact without returning plaintext or writing local data:

```bash
curl -X POST http://localhost:8000/v1/sync/restore-preview \
  -H 'Content-Type: application/json' \
  -d '{"passphrase":"choose a long local passphrase","package":{...}}'
```

## Commercial Readiness

Study Anything is now a public self-host Alpha foundation with a machine-readable commercial
readiness contract. The current commercial path is GitHub OSS plus platform-Agent adoption; it is not
yet a paid hosted app. Run:

```bash
python3 scripts/verify_commercial_readiness.py
python3 scripts/verify_ecosystem_submission_pack.py
```

See `docs/commercial-readiness.md` for the hosted-service contracts and launch limits. See
`docs/ecosystem-submission.md` before publishing or submitting platform assets.
For external operators who start from GitHub instead of a checkout, use
`docs/release-asset-adoption.md` and run:

```bash
python3 scripts/verify_release_asset_adoption.py --tag v0.3.29-alpha --runtime metadata-only
```

## GitHub Launch

The repository includes GitHub Actions for Python tests, Docker Compose smoke, and GHCR API image publishing. See `docs/github-launch.md` before cutting the current alpha release.

Before a risky local upgrade, rehearse backup and restore without touching your real volumes:

```bash
python3 scripts/verify_backup_restore_drill.py
```

The drill runs against a disposable Docker Compose project. It verifies the API learning loop, creates
a local backup, mutates state, restores the backup, and confirms the session count rolls back while
destructive restore remains unavailable from the API.

## Status

This repository is a self-host alpha. The deterministic learning workflow, Skill Mode, agent registry, plugin manifest validation, local encrypted sync package, local PMF metrics, API surface, Postgres-backed Docker session store, optional FalkorDB topology projection, and Docker Compose stack are present. Hosted services are intentionally staged after PMF validation. A polished standalone Web UI is not part of the current launch path.
