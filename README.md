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
- Optional paid services only after PMF, inspired by Obsidian-style Sync, Publish, Teams, and Catalyst offerings.
- API-as-product: the Web UI is a client of the public API.

## Quickstart

The codebase is structured so core tests run without Docker or a real agent.

```bash
python3 -m unittest discover apps/api/tests
python3 scripts/smoke_core.py
```

For the full alpha stack, install Docker and run:

```bash
python3 scripts/setup_env.py
./scripts/doctor.sh
./scripts/launch_self_host.sh
```

Then open:

- Web UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/v1/health
- Langfuse: http://localhost:3000

## Bring Your Own Agent

Study Anything ships with a deterministic fake agent for tests and demos. Real reasoning is performed by an agent that the user owns and runs outside Study Anything.

Supported MVP provider shapes:

- `fake_agent`: deterministic local provider for tests and demos.
- `http_agent`: user-owned local or private HTTP gateway. This is the recommended MVP path.
- `cli_agent`: reserved adapter, disabled by default until explicitly allowlisted.
- `mcp_agent`: plugin ecosystem extension point.

The agent flow mirrors tools such as OpenClaw and Codex: the user controls the model, credentials, tools, and reasoning inside their own agent; Study Anything sends structured learning tasks and validates structured results.

## Repository Layout

```text
apps/api/                  FastAPI app and learning engine
apps/web/                  React/Vite alpha UI
docs/                      Architecture, roadmap, plugin API, commercial model
infra/compose/             Docker Compose stack
plugins/example-exporter/  Example exporter manifest
plugins/example-agent-provider/ Example agent provider manifest
scripts/                   Local smoke helpers
```

## Plugin Ecosystem

The alpha plugin surface supports manifest validation and discovery for importers, agent providers, agent tools, source verifiers, quiz generators, graders, exporters, and UI panels. See `docs/plugins.md` and `plugins/example-exporter`.

## Self-Hosting

See `docs/self-hosting.md` for launch, data, agent provider, and plugin mounting notes.

## Commercial Readiness

Study Anything is a public self-host Alpha foundation, roughly 35% of the way to a complete commercial product. See `docs/commercial-readiness.md` for the gap analysis and suggested branch tracks.

## GitHub Launch

The repository includes GitHub Actions for Python tests, Web build/audit, Docker Compose smoke, and GHCR image publishing. See `docs/github-launch.md` before cutting the first public alpha release.

## Status

This repository is an alpha scaffold. The deterministic learning workflow, agent registry, plugin manifest validation, API surface, Web UI shell, Postgres-backed Docker session store, and Docker Compose stack are present. Hosted services are intentionally staged after PMF validation.
