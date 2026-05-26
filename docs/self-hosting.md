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

`./scripts/launch_self_host.sh` uses `STACK_PROFILE=full` by default. Available profiles:

- `core`: API, Web UI, and app Postgres.
- `smoke`: core stack plus the mock HTTP agent.
- `full`: core stack plus Langfuse, Redis, ClickHouse, MinIO, and FalkorDB.

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

If you already have services on the default ports, override `API_PORT`, `WEB_PORT`, `APP_POSTGRES_PORT`, `MOCK_AGENT_PORT`, `LANGFUSE_PORT`, `REDIS_PORT`, `FALKORDB_PORT`, `CLICKHOUSE_HTTP_PORT`, `CLICKHOUSE_NATIVE_PORT`, `MINIO_PORT`, `MINIO_CONSOLE_PORT`, or `LANGFUSE_POSTGRES_PORT` in `.env`.

## Using Published Images

After the GitHub repository publishes GHCR images, you can skip local API/Web builds:

```bash
STUDY_ANYTHING_API_IMAGE=ghcr.io/<owner>/<repo>/api:v0.1.0-alpha \
STUDY_ANYTHING_WEB_IMAGE=ghcr.io/<owner>/<repo>/web:v0.1.0-alpha \
docker compose \
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

For Python-only development without Docker, set `SESSION_STORE=json` and `STUDY_ANYTHING_DATA_DIR=data/api`.

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
docker compose -f infra/compose/docker-compose.yml --profile smoke up -d mock-http-agent
API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://mock-http-agent:8787 ./scripts/verify_mock_http_agent_flow.py
```

## Plugins

Bundled plugins live in `/app/plugins` inside the API container. Community plugins can be mounted into that path or added to `STUDY_ANYTHING_PLUGIN_DIRS`.

## Stop

```bash
./scripts/stop_self_host.sh
```

Use `docker volume ls` and `docker volume rm` only when you intentionally want to delete local data.
