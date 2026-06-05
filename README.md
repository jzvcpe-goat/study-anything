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
- API-as-product: the Web UI is a client of the public API.

## Fastest Local Demo

Use Skill Mode when you want to try the learning loop without Docker:

```bash
./scripts/run_skill_mode_demo.sh
```

This creates a local Python virtual environment when needed, starts the API, verifies the CLI learning
loop, and stops the API in one command. This is the safest path for terminal-capable LLM agents whose
shell tools may not preserve background processes. For a persistent local API, run
`./scripts/launch_skill_mode.sh` and stop it with `./scripts/stop_skill_mode.sh`. If your agent or
desktop shell does not preserve background processes, use `./scripts/launch_skill_mode.sh --foreground`
and keep that terminal open while a browser or another agent uses the API.

## Docker Self-Host

Install Docker Desktop, start its daemon, then run:

```bash
python3 scripts/setup_env.py
./scripts/doctor.sh
./scripts/launch_self_host.sh
```

`doctor.sh` checks Docker, Compose, required tools, port availability, API/Web health, Agent gateway
reachability hints, plugin directories, and recovery commands before you launch.

The default Docker profile is `core`: API, Web UI, and Postgres. It starts in the background so the
terminal returns. Enable observability and optional topology services later with
`STACK_PROFILE=full ./scripts/launch_self_host.sh`.

If your checkout path contains non-ASCII characters, Docker Desktop BuildKit/buildx may fail before
the app build starts. Use `USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh` or clone the repo
to an ASCII-only path such as `~/study-anything` for local source builds.

Open:

- Web UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/v1/health
- Encrypted sync status: http://localhost:8000/v1/sync/status
- Knowledge graph status: http://localhost:8000/v1/graph/status
- Langfuse: http://localhost:3000

## Published Images

Use the multi-architecture `v0.2.4-alpha` images when you want to skip local API and Web builds:

```bash
python3 scripts/setup_env.py
USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh
```

The launcher pulls API and Web sequentially and shows layer progress so first-run downloads remain
understandable on slower connections. The release images support `linux/amd64` and `linux/arm64`.

## Bring Your Own Agent

Study Anything ships with a deterministic fake agent for tests and demos. Real reasoning is performed by an agent that the user owns and runs outside Study Anything.

Supported MVP provider shapes:

- `fake_agent`: deterministic local provider for tests and demos.
- `http_agent`: user-owned local or private HTTP gateway. This is the recommended MVP path.
- `cli_agent`: reserved adapter, disabled by default until explicitly allowlisted.
- `mcp_agent`: plugin ecosystem extension point.

The agent flow mirrors tools such as OpenClaw and Codex: the user controls the model, credentials, tools, and reasoning inside their own agent; Study Anything sends structured learning tasks and validates structured results.

## Skill Mode

You can use the learning loop before the Web UI is visually complete. The repo includes a standard-library CLI and a repo-local Codex skill:

```bash
./scripts/run_skill_mode_demo.sh
```

For persistent sessions, use `./scripts/launch_skill_mode.sh` and then
`python3 scripts/study_anything_cli.py demo`.

Connect a user-owned HTTP agent, start source-bound sessions, answer questions, inspect mastery, and resolve HITL tasks through the same public API. Chat-only LLM products cannot run local scripts or reach `localhost`; use a terminal-capable agent or expose the API securely. Kimi can be the user-owned reasoning agent through the local gateway, but a browser-only Kimi chat cannot operate the repo-local skill by itself. For Kimi API setup, see `docs/kimi-agent-gateway.md`. For general Skill Mode usage, see `docs/skill-mode.md`.

## Repository Layout

```text
apps/api/                  FastAPI app and learning engine
apps/web/                  React/Vite alpha UI
docs/                      Architecture, roadmap, plugin API, commercial model
infra/compose/             Docker Compose stack
plugins/example-exporter/  Example exporter manifest
plugins/example-agent-provider/ Example agent provider manifest
scripts/                   Local smoke helpers
skills/study-anything/     Repo-local Agent skill for CLI learning flows
```

## Plugin Ecosystem

The alpha plugin surface supports manifest validation, discovery, and permission-gated local installation for importers, agent providers, agent tools, source verifiers, quiz generators, graders, exporters, and UI panels. See `docs/plugins.md` and `plugins/example-exporter`.

Install an explicitly selected local plugin from the Web Agent page, or use the CLI without downloading or executing code:

```bash
python3 scripts/install_local_plugin.py plugins/example-exporter
```

## Local PMF Signals

Study Anything includes a local-only launch panel and API metrics for PMF validation:

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

Study Anything does not store the passphrase or upload the package.

## Commercial Readiness

Study Anything is a public self-host Alpha foundation, roughly 65% of the way to a complete commercial product. See `docs/commercial-readiness.md` for the gap analysis and suggested branch tracks.

## GitHub Launch

The repository includes GitHub Actions for Python tests, Web build/audit, Docker Compose smoke, and GHCR image publishing. See `docs/github-launch.md` before cutting the current alpha release.

## Status

This repository is a self-host alpha. The deterministic learning workflow, guided Web onboarding, agent registry, plugin manifest validation, local encrypted sync package, local PMF metrics, API surface, Postgres-backed Docker session store, optional FalkorDB topology projection, and Docker Compose stack are present. Hosted services are intentionally staged after PMF validation.
