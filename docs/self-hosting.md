# Self-Hosting

Study Anything is designed to be self-hosted first.

## Requirements

- Docker with Compose plugin.
- 4 GB RAM minimum for the app stack, more if your own agent runs local models.
- Optional: any local/private HTTP agent gateway.

## Launch

```bash
python3 scripts/setup_env.py
./scripts/doctor.sh
./scripts/launch_self_host.sh
```

`./scripts/launch_self_host.sh` uses `STACK_PROFILE=core` by default and starts containers in the
background. Available profiles:

- `core`: API, Web UI, and app Postgres.
- `smoke`: core stack plus the mock HTTP agent.
- `full`: core stack plus Langfuse, Redis, ClickHouse, MinIO, and FalkorDB.

Use the heavier full profile only when you want the optional operational services:

```bash
STACK_PROFILE=full ./scripts/launch_self_host.sh
```

If Docker Hub is unreachable from Docker Desktop but public ECR works, set these optional overrides in `.env` before building:

```bash
PYTHON_BASE_IMAGE=public.ecr.aws/docker/library/python:3.11-slim
NODE_BASE_IMAGE=public.ecr.aws/docker/library/node:22-slim
POSTGRES_IMAGE=public.ecr.aws/docker/library/postgres:17
LANGFUSE_POSTGRES_IMAGE=public.ecr.aws/docker/library/postgres:17
REDIS_IMAGE=public.ecr.aws/docker/library/redis:7
MINIO_IMAGE=quay.io/minio/minio:latest
```

The remaining service images are also configurable with `CLICKHOUSE_IMAGE`, `FALKORDB_IMAGE`, `LANGFUSE_WEB_IMAGE`, and `LANGFUSE_WORKER_IMAGE` for private registries or mirrors.

`scripts/setup_env.py` generates these mirror-friendly defaults automatically. Use `.env.example` as documentation, not as a production secret file.

If you already have services on the default ports, override `API_PORT`, `WEB_PORT`, `APP_POSTGRES_PORT`, `MOCK_AGENT_PORT`, `LANGFUSE_PORT`, `REDIS_PORT`, `FALKORDB_HOST_PORT`, `CLICKHOUSE_HTTP_PORT`, `CLICKHOUSE_NATIVE_PORT`, `MINIO_PORT`, `MINIO_CONSOLE_PORT`, or `LANGFUSE_POSTGRES_PORT` in `.env`.

## Using Published Images

After the GitHub repository publishes GHCR images, you can skip local API/Web builds:

```bash
STUDY_ANYTHING_API_IMAGE=ghcr.io/jzvcpe-goat/study-anything/api:v0.1.0-alpha \
STUDY_ANYTHING_WEB_IMAGE=ghcr.io/jzvcpe-goat/study-anything/web:v0.1.0-alpha \
docker compose \
  --env-file .env \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.images.yml \
  --profile full up -d
```

This is optional. The default local-first path still builds from source.

Open:

- Web UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/v1/health
- System status: http://localhost:8000/v1/system/status
- Langfuse: http://localhost:3000

## Data

The Docker self-host stack stores session state in app Postgres by default with `SESSION_STORE=postgres`.

Agent provider defaults are still stored in the `study_anything_data` Docker volume at `/data/study-anything/agent_registry.json` during alpha. Keep this volume in backups if you configure real HTTP agent endpoints.

The Web container serves the built UI and proxies same-origin `/v1/*` requests to the API container through `WEB_API_PROXY_TARGET`, which defaults to `http://api:8000`. This keeps the browser on `http://localhost:5173` while avoiding browser-side knowledge of the internal Compose network.

For Python-only development without Docker, set `SESSION_STORE=json` and `STUDY_ANYTHING_DATA_DIR=data/api`.
The Vite development server proxies `/v1/*` to `http://127.0.0.1:8000` by default. Set `VITE_API_PROXY_TARGET` when your local API uses another address.

The API runs the compiled LangGraph workflow by default. Docker self-host uses `LANGGRAPH_CHECKPOINTER=postgres`; local Python development defaults to the in-memory checkpointer. Set `WORKFLOW_ENGINE=deterministic` only when you need to fall back to the alpha sequential executor.

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

Use the Web UI provider panel or API endpoints to configure a provider. Real model credentials, tools, and reasoning stay inside the user's agent and are not stored by Study Anything.

Common choices:

- Local HTTP agent: `http://host.docker.internal:8787`
- OpenClaw/Codex-style gateway: expose the Study Anything agent contract over HTTP and call any internal model/tool stack you choose.
- Kimi: run `scripts/openai_compatible_agent_gateway.py` with your Moonshot API environment. See `docs/kimi-agent-gateway.md`.
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

For source checkouts, install one explicitly selected local plugin with:

```bash
python3 scripts/install_local_plugin.py /path/to/plugin
```

## Stop

```bash
./scripts/stop_self_host.sh
```

Use `docker volume ls` and `docker volume rm` only when you intentionally want to delete local data.
