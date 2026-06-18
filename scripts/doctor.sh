#!/usr/bin/env sh
set -eu

printf "Study Anything self-host doctor\n"
printf "================================\n"

problems=0
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
env_file="${ENV_FILE:-.env}"
profile="${STACK_PROFILE:-core}"
use_published_images="${USE_PUBLISHED_IMAGES:-false}"
image_tag="${STUDY_ANYTHING_IMAGE_TAG:-v0.3.31-alpha}"
docker_source_path="${STUDY_ANYTHING_DOCKER_SOURCE_PATH:-$ROOT}"

is_true() {
  case "$1" in
    1|true|TRUE|yes|YES)
      return 0
    ;;
    *)
      return 1
      ;;
  esac
}

path_has_non_ascii() {
  printf "%s" "$1" | LC_ALL=C grep -q '[^ -~]'
}

check_cmd() {
  name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf "ok    %s: %s\n" "$name" "$(command -v "$name")"
  else
    printf "miss  %s\n" "$name"
    problems=$((problems + 1))
  fi
}

check_optional_cmd() {
  name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf "ok    %s: %s\n" "$name" "$(command -v "$name")"
  else
    printf "warn  %s missing; optional for Docker self-host.\n" "$name"
  fi
}

check_cmd docker
check_cmd curl
check_optional_cmd python3
check_optional_cmd lsof

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    printf "ok    docker compose: %s\n" "$(docker compose version)"
  else
    printf "miss  docker compose plugin\n"
    problems=$((problems + 1))
  fi
  if docker info >/dev/null 2>&1; then
    printf "ok    docker daemon is running\n"
  else
    printf "miss  docker daemon is not running; start Docker Desktop before launch.\n"
    problems=$((problems + 1))
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  if [ -f "$env_file" ]; then
    python3 scripts/check_env.py --env "$env_file"
  else
    printf "warn  %s missing; run python3 scripts/setup_env.py before launch.\n" "$env_file"
  fi
fi

env_value() {
  key="$1"
  default="$2"
  eval "override=\${$key-}"
  if [ -n "$override" ]; then
    printf "%s\n" "$override"
    return
  fi
  if [ -f "$env_file" ] && command -v python3 >/dev/null 2>&1; then
    python3 - "$env_file" "$key" "$default" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
target = sys.argv[2]
default = sys.argv[3]
value = default
for line in path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        continue
    key, raw = line.split("=", 1)
    if key.strip() == target:
        value = raw.strip().strip("'\"")
print(value)
PY
  else
    printf "%s\n" "$default"
  fi
}

check_port() {
  label="$1"
  key="$2"
  default="$3"
  port="$(env_value "$key" "$default")"
  case "$port" in
    ""|*[!0-9]*)
      printf "warn  %s=%s is not a numeric port for %s.\n" "$key" "$port" "$label"
      return
      ;;
  esac
  if command -v lsof >/dev/null 2>&1; then
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      owner="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sed -n '2p')"
      printf "warn  port %s for %s (%s) is already listening: %s\n" "$port" "$label" "$key" "$owner"
    else
      printf "ok    port %s for %s (%s) is available\n" "$port" "$label" "$key"
    fi
  else
    printf "warn  lsof missing; cannot check port %s for %s.\n" "$port" "$label"
  fi
}

check_http_health() {
  label="$1"
  url="$2"
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS "$url" >/dev/null 2>&1; then
      printf "ok    %s responds at %s\n" "$label" "$url"
    else
      printf "info  %s is not responding yet at %s. This is normal before launch.\n" "$label" "$url"
    fi
  fi
}

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && [ -f "$env_file" ]; then
  if is_true "$use_published_images"; then
    export STUDY_ANYTHING_API_IMAGE="${STUDY_ANYTHING_API_IMAGE:-ghcr.io/jzvcpe-goat/study-anything/api:${image_tag}}"
    if docker compose --env-file "$env_file" -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.images.yml config >/dev/null; then
      printf "ok    Docker Compose published-image config is valid for STACK_PROFILE=%s\n" "$profile"
    else
      printf "miss  Docker Compose published-image config is invalid.\n"
      problems=$((problems + 1))
    fi
  else
    if path_has_non_ascii "$docker_source_path" && ! is_true "${ALLOW_NON_ASCII_DOCKER_BUILD:-false}"; then
      printf "miss  Docker source build path contains non-ASCII characters: %s\n" "$docker_source_path"
      printf "      Use USE_PUBLISHED_IMAGES=true, clone to an ASCII-only path, or set ALLOW_NON_ASCII_DOCKER_BUILD=true to bypass.\n"
      problems=$((problems + 1))
    fi
    if docker compose --env-file "$env_file" -f infra/compose/docker-compose.yml config >/dev/null; then
      printf "ok    Docker Compose source-build config is valid for STACK_PROFILE=%s\n" "$profile"
    else
      printf "miss  Docker Compose source-build config is invalid.\n"
      problems=$((problems + 1))
    fi
  fi
fi

printf "\nPort checks for STACK_PROFILE=%s\n" "$profile"
check_port "API" API_PORT 8000
check_port "App Postgres" APP_POSTGRES_PORT 5433
case "$profile" in
  smoke)
    check_port "Mock HTTP Agent" MOCK_AGENT_PORT 8787
    check_port "FalkorDB" FALKORDB_HOST_PORT 6378
    ;;
  full)
    check_port "Mock HTTP Agent" MOCK_AGENT_PORT 8787
    check_port "Langfuse" LANGFUSE_PORT 3000
    check_port "Langfuse Postgres" LANGFUSE_POSTGRES_PORT 5432
    check_port "Redis" REDIS_PORT 6379
    check_port "FalkorDB" FALKORDB_HOST_PORT 6378
    check_port "ClickHouse HTTP" CLICKHOUSE_HTTP_PORT 8123
    check_port "ClickHouse Native" CLICKHOUSE_NATIVE_PORT 9000
    check_port "MinIO" MINIO_PORT 9090
    check_port "MinIO Console" MINIO_CONSOLE_PORT 9091
    ;;
  core)
    ;;
  *)
    printf "warn  Unsupported STACK_PROFILE=%s. launch_self_host.sh accepts core, smoke, or full.\n" "$profile"
    ;;
esac

api_port="$(env_value API_PORT 8000)"
check_http_health "API health" "http://127.0.0.1:${api_port}/v1/health"

agent_url="$(env_value AGENT_HTTP_GATEWAY_URL http://host.docker.internal:8787)"
case "$agent_url" in
  http://127.0.0.1:*|http://localhost:*)
    check_http_health "HTTP Agent gateway" "$agent_url/health"
    ;;
  "")
    printf "info  AGENT_HTTP_GATEWAY_URL is blank. Use the demo Agent or configure your own gateway through /v1/agents/*.\n"
    ;;
  *)
    printf "info  Agent gateway is configured as %s. If Docker cannot reach it, try http://host.docker.internal:8787 or the smoke profile.\n" "$agent_url"
    ;;
esac

if [ -d plugins ]; then
  printf "ok    bundled plugin directory exists: plugins\n"
else
  printf "miss  bundled plugin directory is missing.\n"
  problems=$((problems + 1))
fi

plugin_dir="$(env_value STUDY_ANYTHING_PLUGIN_INSTALL_DIR data/plugins)"
plugin_parent="$(dirname "$plugin_dir")"
if [ -d "$plugin_dir" ]; then
  printf "ok    local plugin install directory exists: %s\n" "$plugin_dir"
elif [ -d "$plugin_parent" ]; then
  printf "info  local plugin install directory will be created on first install: %s\n" "$plugin_dir"
else
  printf "warn  local plugin install parent is missing: %s\n" "$plugin_parent"
fi

printf "\nRecovery commands\n"
printf "  Launch core stack:        ./scripts/launch_self_host.sh\n"
printf "  Launch with GHCR images:  USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n"
printf "  Skip pulls if cached:     USE_PUBLISHED_IMAGES=true PULL_PUBLISHED_IMAGES=false ./scripts/launch_self_host.sh\n"
printf "  Smoke Agent path:         STACK_PROFILE=smoke ./scripts/launch_self_host.sh\n"
printf "  API logs:                 docker compose --env-file %s -f infra/compose/docker-compose.yml logs --tail=200 api app-postgres\n" "$env_file"
printf "  Full stack status:        docker compose --env-file %s -f infra/compose/docker-compose.yml ps\n" "$env_file"
printf "  Backup before changes:    python3 scripts/self_host_data.py backup\n"
printf "  Stop stack:               ./scripts/stop_self_host.sh\n"

printf "\nProfile guide\n"
printf "  STACK_PROFILE=core starts API/Postgres only.\n"
printf "  STACK_PROFILE=smoke adds the mock HTTP agent and FalkorDB for smoke tests.\n"
printf "  STACK_PROFILE=full adds Langfuse, Redis, ClickHouse, MinIO, and FalkorDB.\n"

if [ "$problems" -gt 0 ]; then
  printf "\nDoctor found %s blocking issue(s).\n" "$problems" >&2
  exit 1
fi
