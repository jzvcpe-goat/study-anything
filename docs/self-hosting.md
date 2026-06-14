# Self-Hosting

Study Anything is designed to be self-hosted first.

## Requirements

- Docker with Compose plugin.
- 2 GB RAM minimum for the API/Postgres stack, more if your own agent runs local models.
- Optional: any local/private HTTP agent gateway.

## Launch

```bash
python3 scripts/setup_env.py
./scripts/doctor.sh
./scripts/launch_self_host.sh
```

`./scripts/launch_self_host.sh` uses `STACK_PROFILE=core` by default and starts containers in the
background. Available profiles:

- `core`: API and app Postgres.
- `smoke`: core stack plus the mock HTTP agent and FalkorDB.
- `full`: core stack plus Langfuse, Redis, ClickHouse, MinIO, and FalkorDB.

Use the heavier full profile only when you want the optional operational services:

```bash
STACK_PROFILE=full ./scripts/launch_self_host.sh
```

If Docker Hub is unreachable from Docker Desktop but public ECR works, set these optional overrides in `.env` before building:

```bash
PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.11-slim
POSTGRES_IMAGE=public.ecr.aws/docker/library/postgres:17
LANGFUSE_POSTGRES_IMAGE=public.ecr.aws/docker/library/postgres:17
REDIS_IMAGE=public.ecr.aws/docker/library/redis:7
MINIO_IMAGE=quay.io/minio/minio:latest
```

The remaining service images are also configurable with `CLICKHOUSE_IMAGE`, `FALKORDB_IMAGE`, `LANGFUSE_WEB_IMAGE`, and `LANGFUSE_WORKER_IMAGE` for private registries or mirrors.

`scripts/setup_env.py` generates these mirror-friendly defaults automatically. Use `.env.example` as documentation, not as a production secret file.

If you already have services on the default ports, override `API_PORT`, `APP_POSTGRES_PORT`, `MOCK_AGENT_PORT`, `LANGFUSE_PORT`, `REDIS_PORT`, `FALKORDB_HOST_PORT`, `CLICKHOUSE_HTTP_PORT`, `CLICKHOUSE_NATIVE_PORT`, `MINIO_PORT`, `MINIO_CONSOLE_PORT`, or `LANGFUSE_POSTGRES_PORT` in `.env`.

## Checkout Path Compatibility

Docker Desktop BuildKit/buildx can fail before the app build starts when the source checkout path
contains non-ASCII characters. The error usually looks like:

```text
header key "x-docker-expose-session-sharedkey" contains value with non-printable ASCII characters
```

If `./scripts/doctor.sh` reports this, use one of these paths:

```bash
USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh
```

or move/clone the source checkout to an ASCII-only path before local source builds:

```bash
git clone https://github.com/jzvcpe-goat/study-anything.git ~/study-anything
cd ~/study-anything
python3 scripts/setup_env.py
./scripts/launch_self_host.sh
```

Set `ALLOW_NON_ASCII_DOCKER_BUILD=true` only if you know your Docker version no longer has this
BuildKit path bug and you want to bypass the guard.

## Troubleshooting And Recovery

Run the doctor before and after launch when a self-host setup does not behave as expected:

```bash
./scripts/doctor.sh
```

It checks Docker, Compose, required local tools, Compose config validity, profile-specific port
availability, API health, Agent gateway hints, and plugin directories. Port warnings do not always
mean failure; they can also mean the stack is already running. If a launch stalls, inspect the running
services and logs:

```bash
docker compose --env-file .env -f infra/compose/docker-compose.yml ps
docker compose --env-file .env -f infra/compose/docker-compose.yml logs --tail=200 api app-postgres
```

Common recovery paths:

- Docker daemon unavailable: start Docker Desktop or Docker Engine, then rerun `./scripts/doctor.sh`.
- Image pull failure: rerun with published images, a mirror override, or `PULL_PUBLISHED_IMAGES=false`
  only when images are already cached locally.
- Port conflict: change the matching `*_PORT` value in `.env` and relaunch.
- API unhealthy: check `api` and `app-postgres` logs first.
- Agent gateway unreachable: use `STACK_PROFILE=smoke` to validate with the mock HTTP Agent, then switch
  to your own gateway endpoint. For OpenAI-compatible providers, first run
  `python3 scripts/verify_openai_compatible_gateway.py --gateway-only`, then run
  `API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py` against the
  local API before adding real credentials.
- Plugin install confusion: preview local plugin permissions before copying files; installed plugins
  live in the writable Study Anything data volume.
- Risky upgrade or restore: run `python3 scripts/self_host_data.py backup` before changing volumes,
  images, or environment values.

## Using Published Images

After the GitHub repository publishes GHCR images, you can skip local API builds:

```bash
USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh
```

This starts the core API and app Postgres services. The launcher pulls the API image before startup
and shows layer progress so a cold first download remains easy to understand. Use
`STACK_PROFILE=full USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh` only when you also want
the optional observability services.

Published images are optional. The default local-first path still builds from source.
Published API images include `linux/amd64` and `linux/arm64` manifests so the same command works on
common Linux servers and Apple Silicon Docker Desktop.

For a pinned or mirrored deployment, override the tag or exact image names:

```bash
STUDY_ANYTHING_IMAGE_TAG=v0.3.23-alpha USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh

STUDY_ANYTHING_API_IMAGE=registry.example/study-anything/api:v0.3.23-alpha \
USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh
```

Set `PULL_PUBLISHED_IMAGES=false` only when the desired images are already cached locally or managed
by an offline deployment process.

Open:

- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/v1/health
- Deployment guide: http://localhost:8000/v1/deployment/guide
- Commercial readiness: http://localhost:8000/v1/commercial/readiness
- System status: http://localhost:8000/v1/system/status
- Recovery status: http://localhost:8000/v1/recovery/status
- Local encrypted sync status: http://localhost:8000/v1/sync/status
- Local PMF metrics: http://localhost:8000/v1/metrics/pmf
- Langfuse: http://localhost:3000

## User-Owned Agent Gateway

Study Anything does not store real model API keys. Keep Kimi/OpenAI-compatible credentials in the
gateway process environment, then register only the local or private `/invoke` endpoint. For a
host-local gateway used by Docker, prefer `http://host.docker.internal:8787/invoke`.

Before using real credentials, run:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
python3 scripts/verify_agent_gateway_hardening.py
python3 scripts/verify_external_agent_adapter_hardening.py
```

Do not put bearer tokens, cookies, signed URLs, or `api_key` query parameters into
`POST /v1/agents/providers`; those configurations are rejected and should live inside the user's
gateway instead.

## Post-Launch Verification

After the API is healthy, run the public smoke flow:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py
```

This creates a demo learning session, submits source-bound reading, answers the generated quiz, verifies
mastery completion, reads local PMF metrics, and records one local-only hosted-alpha intent. PMF metrics
are aggregate-only; they do not expose raw source text, answers, insights, user IDs, contact values, or
Agent metadata. The smoke flow also exports and inspects an encrypted local sync package, then checks
that the package response does not expose the smoke learner, source text, answer text, or Agent details
in plaintext.

Maintainers can validate the public GHCR images with a disposable stack:

```bash
python3 scripts/verify_deployment_hardening.py --check
python3 scripts/verify_published_image_launch.py --tag v0.3.23-alpha
```

The first command verifies the deployment operator path and adoption pack evidence. The second pulls
the published API image, checks the runtime version, completes the API learning loop, and removes the
temporary Compose project on success.

If adoption fails before the API is usable, run the diagnostic helper:

```bash
python3 scripts/diagnose_adoption.py
```

It distinguishes localhost reachability, Docker daemon state, GHCR image visibility, HTTP Agent
health, missing `.env`, and missing provider capability defaults. The output includes
`adoption-diagnostics-v1` plus `adoption-diagnostic-plan-v1`, a copyable recovery plan for platform
Agents and human operators.

For platform-agent distribution, maintainers should also verify the adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

That proof covers Kimi/Codex/WorkBuddy-style tool imports, Skill Mode startup, importer/enrichment,
retrieval, teaching layers, eval evidence, Obsidian export, and NotebookLM-style handoff without
requiring the standalone frontend.

## Data

The Docker self-host stack stores session state in app Postgres by default with `SESSION_STORE=postgres`.

Agent provider defaults are still stored in the `study_anything_data` Docker volume at `/data/study-anything/agent_registry.json` during alpha. Keep this volume in backups if you configure real HTTP agent endpoints.

For Python-only development without Docker, set `SESSION_STORE=json` and `STUDY_ANYTHING_DATA_DIR=data/api`.

The API runs the compiled LangGraph workflow by default. Docker self-host uses `LANGGRAPH_CHECKPOINTER=postgres`; local Python development defaults to the in-memory checkpointer. Set `WORKFLOW_ENGINE=deterministic` only when you need to fall back to the alpha sequential executor.

## Encrypted Sync Package

The public API includes a local encrypted package foundation for future Study Sync:

```bash
curl http://localhost:8000/v1/sync/status

curl -X POST http://localhost:8000/v1/sync/export \
  -H 'Content-Type: application/json' \
  -d '{"passphrase":"choose a long local passphrase"}'
```

The export endpoint returns an encrypted package envelope plus count-only summary metadata. The
passphrase is never stored by Study Anything. The package is not uploaded anywhere; keep it in storage
you control. The package envelope excludes source text, answers, raw user IDs, Agent endpoints, Agent
metadata, and plugin source code in plaintext.

To inspect a package without restoring it:

```bash
curl -X POST http://localhost:8000/v1/sync/inspect \
  -H 'Content-Type: application/json' \
  -d '{"passphrase":"choose a long local passphrase","package":{...}}'
```

To preview what a package would add or overwrite before a migration or upgrade:

```bash
curl -X POST http://localhost:8000/v1/sync/restore-preview \
  -H 'Content-Type: application/json' \
  -d '{"passphrase":"choose a long local passphrase","package":{...}}'
```

`/v1/sync/inspect` returns schema, timestamp, summary counts, and privacy flags only.
`/v1/sync/restore-preview` adds count-only restore impact, conflict hashes, warnings, and manual
confirmation requirements. Neither endpoint writes data or returns decrypted session payloads. Hosted
accounts, remote storage, cross-device conflict resolution, recovery flows, and billing are not part of
the self-host alpha.

## Backup And Restore

Create a local backup before upgrades or Docker volume maintenance:

```bash
python3 scripts/self_host_data.py backup
```

The API exposes a read-only recovery status so operators can inspect the current backup
contract without triggering backup or restore operations:

```bash
curl http://localhost:8000/v1/recovery/status
```

This endpoint returns the documented backup/restore commands, coverage, privacy warnings, and
safeguards. It intentionally omits absolute host paths, never returns secrets, and does not expose a
destructive restore API.

The default backup contains:

- A compressed `pg_dump` of the canonical app Postgres database.
- The `study_anything_data` volume with Agent configuration and locally installed plugins.
- A private `env.snapshot` so a lost self-host environment can be recovered.
- A SHA-256 manifest checked before restore.

Backup directories are written under `backups/` by default, ignored by Git, and created with local
user-only permissions. They contain secrets and private learning data. Keep them encrypted at rest,
do not commit them, and do not upload them to an untrusted storage provider.

To include disposable topology data and optional Langfuse service volumes when they exist:

```bash
python3 scripts/self_host_data.py backup --include-optional
```

For the most consistent optional-service snapshot, stop the stack first with
`./scripts/stop_self_host.sh`. The backup tool starts app Postgres long enough to create its canonical
SQL dump.

Restore is intentionally explicit and destructive:

```bash
python3 scripts/self_host_data.py restore backups/study-anything-backup-YYYYmmddTHHMMSSZ --yes
./scripts/launch_self_host.sh
```

An existing `.env` is preserved by default. Use `--restore-env` only when you intentionally want to
replace it with the backed-up environment snapshot. If `.env` is missing, the snapshot is restored
automatically.

To rehearse the whole backup/restore path without touching your real self-host volumes, run the
disposable drill:

```bash
python3 scripts/verify_backup_restore_drill.py
```

The drill generates a temporary `.env` with a unique `COMPOSE_PROJECT_NAME` and random host ports,
starts a core API/Postgres stack, creates baseline learning data, backs it up, mutates the stack,
restores the backup, and asserts the session count rolled back. It removes its containers, volumes,
and temporary backup on success. Add `--keep-on-failure` when you want to inspect the disposable
Compose project after a failed run.

## Optional Learning Topology

FalkorDB is included in the `full` profile but graph projection is disabled by default. Enable the
privacy-preserving projection explicitly in `.env`:

```bash
FALKORDB_ENABLED=true
FALKORDB_HOST=falkordb
FALKORDB_PORT=6379
FALKORDB_GRAPH=study_anything
FALKORDB_QUERY_TIMEOUT_MS=1000
```

The API will continue learning sessions if FalkorDB is unavailable. Postgres remains the canonical
store. Graph records contain source references, excerpt hashes, mastery metadata, and topology IDs only.

Inspect the adapter or rebuild a session projection:

```bash
curl http://localhost:8000/v1/graph/status
curl http://localhost:8000/v1/sessions/SESSION_ID/topology
curl -X POST http://localhost:8000/v1/sessions/SESSION_ID/topology/rebuild
```

## Secrets

Do not deploy with placeholder values from `.env.example`. Generate a local file:

```bash
python3 scripts/setup_env.py
python3 scripts/check_env.py --strict
```

In `APP_ENV=production`, `scripts/check_env.py` fails on default passwords, blank secrets, and invalid Langfuse encryption keys.

## Agent Providers

Use the API endpoints or CLI to configure a provider. Real model credentials, tools, and reasoning stay inside the user's agent and are not stored by Study Anything.

Common choices:

- Local HTTP agent: `http://host.docker.internal:8787`
- OpenClaw/Codex-style gateway: expose the Study Anything agent contract over HTTP and call any internal model/tool stack you choose.
- Kimi/OpenAI-compatible: run `scripts/openai_compatible_agent_gateway.py` in dry-run mode first, then
  add your Moonshot/Kimi or other compatible API environment. See `docs/kimi-agent-gateway.md`.
- Ollama: supported through your own agent, not as a required Study Anything runtime.
- Fake demo: deterministic agent for smoke testing.

The HTTP agent must accept a JSON `AgentTask` and return a JSON `AgentResult`. See `docs/agent-contract.md`.

## HTTP Agent Smoke

For local API development:

```bash
python3 scripts/mock_http_agent.py --host 127.0.0.1 --port 8787
API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://127.0.0.1:8787 ./scripts/verify_mock_http_agent_flow.py
```

For Docker Compose, start the optional smoke profile and configure the API to reach the mock agent on the Compose network:

```bash
docker compose --env-file .env -f infra/compose/docker-compose.yml --profile smoke up -d mock-http-agent
API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://mock-http-agent:8787 ./scripts/verify_mock_http_agent_flow.py
```

## Plugins

Bundled plugins live in `/app/plugins` inside the API container. Locally installed plugins live in the writable Study Anything data volume under `/data/study-anything/plugins`. Community plugin directories can also be added to `STUDY_ANYTHING_PLUGIN_DIRS`.

Use `POST /v1/plugins/preview` to preview one explicitly selected local plugin directory, confirm each
requested permission, and copy it into the writable plugin data directory with `POST /v1/plugins/install`.
The API never downloads or executes plugin code during this install step.

Before installing or updating community plugins, check the registry review surface:

```bash
curl http://localhost:8000/v1/plugins/registry-review
```

The response is metadata-only. It reports verified digests, registry-signature counts, update
candidates, blocked entries, and manual-review actions without downloading plugin code, installing
updates, or executing entrypoints.

For source checkouts, the same local install path is available from the CLI:

```bash
python3 scripts/install_local_plugin.py /path/to/plugin
```

## Optional Retrieval

Retrieval is a rebuildable projection, not the source of truth. Session state remains in Postgres or
the local JSON store. LanceDB stores source references, excerpt hashes, locators, minimal snippets, and
vectors under the Study Anything data directory.

Default `.env.example` keeps retrieval off:

```bash
LANCEDB_ENABLED=false
LANCEDB_URI=/data/study-anything/lancedb
LANCEDB_TABLE=study_anything_retrieval
LANCEDB_VECTOR_DIMENSIONS=32
```

For a production-like self-host stack, set `LANCEDB_ENABLED=true` and restart the API. For local smoke
without installing or opening LanceDB, use the explicit in-memory backend:

```bash
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory ./scripts/launch_skill_mode.sh
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_importer_runtime_retrieval_flow.py
```

Do not treat the in-memory backend as durable. It exists only for local acceptance checks and platform
Agent integration development.

## Stop

```bash
./scripts/stop_self_host.sh
```

Use `docker volume ls` and `docker volume rm` only when you intentionally want to delete local data.

## Published Image Evidence

Before telling another operator that the published image is deployable, generate the
`published-image-evidence-v1` bundle:

```bash
python3 scripts/generate_published_image_evidence.py --check
python3 scripts/verify_published_image_evidence.py --check
```

This published-image evidence separates a local GHCR pull timeout from a missing manifest platform,
failed docker-images workflow, unavailable registry, or runtime smoke failure. It is metadata-only and
does not include learning content, Agent endpoints, local absolute paths, or model secrets.
