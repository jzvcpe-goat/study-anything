#!/usr/bin/env sh
set -eu

if [ -n "${PATH:-}" ]; then
  PATH="$PATH:/usr/bin:/bin:/usr/sbin:/sbin"
else
  PATH="/usr/bin:/bin:/usr/sbin:/sbin"
fi
export PATH

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
env_file="${ENV_FILE:-${STUDY_ANYTHING_ENV_FILE:-.env}}"

if [ ! -f "$env_file" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 scripts/setup_env.py --output "$env_file"
  else
    cp .env.example "$env_file"
    printf "Created env file from .env.example. Replace placeholder secrets before production use.\n"
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  python3 scripts/check_env.py --env "$env_file"
fi

profile="${STACK_PROFILE:-core}"
use_published_images="${USE_PUBLISHED_IMAGES:-false}"
image_tag="${STUDY_ANYTHING_IMAGE_TAG:-v0.3.29-alpha}"
docker_source_path="${STUDY_ANYTHING_DOCKER_SOURCE_PATH:-$ROOT}"
health_attempts="${SELF_HOST_API_HEALTH_ATTEMPTS:-60}"
health_interval_seconds="${SELF_HOST_API_HEALTH_INTERVAL_SECONDS:-2}"

env_or_file_value() {
  key="$1"
  default="$2"
  eval "override=\${$key-}"
  if [ -n "$override" ]; then
    printf "%s\n" "$override"
    return
  fi
  if [ -f "$env_file" ]; then
    value="$(
      awk -F= -v target="$key" '
        /^[[:space:]]*($|#)/ { next }
        {
          key=$1
          sub(/^[[:space:]]*export[[:space:]]+/, "", key)
          sub(/^[[:space:]]+/, "", key)
          sub(/[[:space:]]+$/, "", key)
          if (key == target) {
            value=substr($0, index($0, "=") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            if (value ~ /^"/) {
              sub(/^"/, "", value)
              sub(/".*$/, "", value)
            } else if (value ~ /^'\''/) {
              sub(/^'\''/, "", value)
              sub(/'\''.*/, "", value)
            } else {
              sub(/[[:space:]]+#.*/, "", value)
              gsub(/[[:space:]]+$/, "", value)
            }
            print value
            exit
          }
        }
      ' "$env_file"
    )"
    if [ -n "$value" ]; then
      printf "%s\n" "$value"
      return
    fi
  fi
  printf "%s\n" "$default"
}

validate_self_host_api_port() {
  api_port_value="$(env_or_file_value API_PORT 8000)"
  case "$api_port_value" in
    ""|*[!0-9]*)
      printf "Invalid API_PORT=%s for self-host launch.\n" "$api_port_value" >&2
      printf "API_PORT must be a number from 1 to 65535.\n" >&2
      printf "Try one of these recovery paths:\n" >&2
      printf "  1. Use the default port: unset API_PORT && ./scripts/launch_self_host.sh\n" >&2
      printf "  2. Choose a known free port: API_PORT=8012 ./scripts/launch_self_host.sh\n" >&2
      printf "  3. Check current port owners: ./scripts/doctor.sh\n" >&2
      printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
      exit 1
      ;;
  esac
  if [ "$api_port_value" -lt 1 ] 2>/dev/null || [ "$api_port_value" -gt 65535 ] 2>/dev/null; then
    printf "Invalid API_PORT=%s for self-host launch.\n" "$api_port_value" >&2
    printf "API_PORT must be between 1 and 65535.\n" >&2
    printf "Try one of these recovery paths:\n" >&2
    printf "  1. Use the default port: unset API_PORT && ./scripts/launch_self_host.sh\n" >&2
    printf "  2. Choose a known free port: API_PORT=8012 ./scripts/launch_self_host.sh\n" >&2
    printf "  3. Check current port owners: ./scripts/doctor.sh\n" >&2
    printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
    exit 1
  fi
}

validate_self_host_port_value() {
  key="$1"
  value="$2"
  label="$3"
  default="$4"
  case "$value" in
    ""|*[!0-9]*)
      printf "Invalid %s=%s for %s.\n" "$key" "$value" "$label" >&2
      printf "%s must be a number from 1 to 65535.\n" "$key" >&2
      printf "Try one of these recovery paths:\n" >&2
      printf "  1. Use the default port: unset %s && ./scripts/launch_self_host.sh\n" "$key" >&2
      printf "  2. Choose a known free port: %s=%s ./scripts/launch_self_host.sh\n" "$key" "$default" >&2
      printf "  3. Check current port owners: ./scripts/doctor.sh\n" >&2
      printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
      exit 1
      ;;
  esac
  if [ "$value" -lt 1 ] 2>/dev/null || [ "$value" -gt 65535 ] 2>/dev/null; then
    printf "Invalid %s=%s for %s.\n" "$key" "$value" "$label" >&2
    printf "%s must be between 1 and 65535.\n" "$key" >&2
    printf "Try one of these recovery paths:\n" >&2
    printf "  1. Use the default port: unset %s && ./scripts/launch_self_host.sh\n" "$key" >&2
    printf "  2. Choose a known free port: %s=%s ./scripts/launch_self_host.sh\n" "$key" "$default" >&2
    printf "  3. Check current port owners: ./scripts/doctor.sh\n" >&2
    printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
    exit 1
  fi
}

validate_self_host_profile_ports() {
  validate_self_host_port_value APP_POSTGRES_PORT "$(env_or_file_value APP_POSTGRES_PORT 5433)" "App Postgres" 5433
  case "$profile" in
    smoke)
      validate_self_host_port_value MOCK_AGENT_PORT "$(env_or_file_value MOCK_AGENT_PORT 8787)" "Mock HTTP Agent" 8787
      validate_self_host_port_value FALKORDB_HOST_PORT "$(env_or_file_value FALKORDB_HOST_PORT 6378)" "FalkorDB" 6378
      ;;
    full)
      validate_self_host_port_value MOCK_AGENT_PORT "$(env_or_file_value MOCK_AGENT_PORT 8787)" "Mock HTTP Agent" 8787
      validate_self_host_port_value FALKORDB_HOST_PORT "$(env_or_file_value FALKORDB_HOST_PORT 6378)" "FalkorDB" 6378
      validate_self_host_port_value LANGFUSE_PORT "$(env_or_file_value LANGFUSE_PORT 3000)" "Langfuse web" 3000
      validate_self_host_port_value LANGFUSE_POSTGRES_PORT "$(env_or_file_value LANGFUSE_POSTGRES_PORT 5432)" "Langfuse Postgres" 5432
      validate_self_host_port_value REDIS_PORT "$(env_or_file_value REDIS_PORT 6379)" "Redis" 6379
      validate_self_host_port_value CLICKHOUSE_HTTP_PORT "$(env_or_file_value CLICKHOUSE_HTTP_PORT 8123)" "ClickHouse HTTP" 8123
      validate_self_host_port_value CLICKHOUSE_NATIVE_PORT "$(env_or_file_value CLICKHOUSE_NATIVE_PORT 9000)" "ClickHouse native" 9000
      validate_self_host_port_value MINIO_PORT "$(env_or_file_value MINIO_PORT 9090)" "MinIO API" 9090
      validate_self_host_port_value MINIO_CONSOLE_PORT "$(env_or_file_value MINIO_CONSOLE_PORT 9091)" "MinIO console" 9091
      ;;
    core)
      ;;
    *)
      print_unsupported_profile_hint
      exit 1
      ;;
  esac
}

active_self_host_port_records() {
  printf "API_PORT=%s\n" "$(env_or_file_value API_PORT 8000)"
  printf "APP_POSTGRES_PORT=%s\n" "$(env_or_file_value APP_POSTGRES_PORT 5433)"
  case "$profile" in
    smoke)
      printf "MOCK_AGENT_PORT=%s\n" "$(env_or_file_value MOCK_AGENT_PORT 8787)"
      printf "FALKORDB_HOST_PORT=%s\n" "$(env_or_file_value FALKORDB_HOST_PORT 6378)"
      ;;
    full)
      printf "MOCK_AGENT_PORT=%s\n" "$(env_or_file_value MOCK_AGENT_PORT 8787)"
      printf "FALKORDB_HOST_PORT=%s\n" "$(env_or_file_value FALKORDB_HOST_PORT 6378)"
      printf "LANGFUSE_PORT=%s\n" "$(env_or_file_value LANGFUSE_PORT 3000)"
      printf "LANGFUSE_POSTGRES_PORT=%s\n" "$(env_or_file_value LANGFUSE_POSTGRES_PORT 5432)"
      printf "REDIS_PORT=%s\n" "$(env_or_file_value REDIS_PORT 6379)"
      printf "CLICKHOUSE_HTTP_PORT=%s\n" "$(env_or_file_value CLICKHOUSE_HTTP_PORT 8123)"
      printf "CLICKHOUSE_NATIVE_PORT=%s\n" "$(env_or_file_value CLICKHOUSE_NATIVE_PORT 9000)"
      printf "MINIO_PORT=%s\n" "$(env_or_file_value MINIO_PORT 9090)"
      printf "MINIO_CONSOLE_PORT=%s\n" "$(env_or_file_value MINIO_CONSOLE_PORT 9091)"
      ;;
  esac
}

validate_self_host_unique_active_ports() {
  duplicate_line="$(
    active_self_host_port_records | awk -F= '
      {
        ports[$2] = ports[$2] ? ports[$2] ", " $1 : $1
        count[$2] += 1
      }
      END {
        for (port in count) {
          if (count[port] > 1) {
            print port "|" ports[port]
            exit
          }
        }
      }
    '
  )"
  if [ -n "$duplicate_line" ]; then
    duplicate_port="${duplicate_line%%|*}"
    duplicate_keys="${duplicate_line#*|}"
    printf "Duplicate host port %s for active self-host profile %s: %s.\n" "$duplicate_port" "$profile" "$duplicate_keys" >&2
    printf "Docker Compose cannot bind multiple active services to the same host port.\n" >&2
    printf "Try one of these recovery paths:\n" >&2
    printf "  1. Edit %s so each active host port is unique: %s\n" "$(redact_diagnostic "$env_file")" "$duplicate_keys" >&2
    printf "  2. Use the smallest first-run stack: STACK_PROFILE=core ./scripts/launch_self_host.sh\n" >&2
    printf "  3. Check current port owners and config: ./scripts/doctor.sh\n" >&2
    printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
    exit 1
  fi
}

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

redact_diagnostic() {
  printf "%s" "$1" | sed \
    -e 's#/Users/[^[:space:]]*#<local-path>#g' \
    -e 's#/private/tmp/[^[:space:]]*#<temp-path>#g' \
    -e 's#/tmp/[^[:space:]]*#<temp-path>#g' \
    -e 's#/private/var/folders/[^[:space:]]*#<temp-path>#g' \
    -e 's#/var/folders/[^[:space:]]*#<temp-path>#g' \
    -e 's#https://[^/@[:space:]]*:[^/@[:space:]]*@#https://<redacted>@#g' \
    -e 's#http://[^/@[:space:]]*:[^/@[:space:]]*@#http://<redacted>@#g' \
    -e 's#sk-\(proj-\)\{0,1\}[A-Za-z0-9_-]\{12,\}#sk-<redacted>#g' \
    -e 's#\([Aa]uthorization[[:space:]]*[:=][[:space:]]*\)[Bb]earer[[:space:]][A-Za-z0-9._~+/=-]\{8,\}#\1Bearer <redacted>#g' \
    -e 's#\([A-Za-z_]*KEY[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*TOKEN[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*SECRET[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*key[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*token[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*secret[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g'
}

print_docker_missing_hint() {
  printf "Docker command was not found in PATH.\n" >&2
  printf "Install Docker Desktop or Docker Engine, then retry: ./scripts/launch_self_host.sh\n" >&2
  printf "First-run fallback without Docker: ./scripts/launch_skill_mode.sh\n" >&2
  printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_compose_missing_hint() {
  compose_output="$1"
  printf "Docker Compose v2 plugin is not available from this shell.\n" >&2
  if [ -n "$compose_output" ]; then
    first_line="$(printf "%s" "$compose_output" | sed -n '1p')"
    printf "Docker reported: %s\n" "$(redact_diagnostic "$first_line")" >&2
  fi
  printf "Install or enable Docker Compose v2, then retry: ./scripts/launch_self_host.sh\n" >&2
  printf "Check with: docker compose version\n" >&2
  printf "First-run fallback without Docker Compose: ./scripts/launch_skill_mode.sh\n" >&2
  printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_docker_pull_failure_hint() {
  image="$1"
  pull_output="$2"
  printf "Published Study Anything image pull failed: %s\n" "$image" >&2
  pull_error_line="$(
    printf "%s" "$pull_output" | \
      grep -Ei "denied|unauthorized|not found|manifest|timeout|timed out|no such host|network|connection|TLS|rate|toomanyrequests|failed|error" | \
      sed -n '1p' || true
  )"
  if [ -z "$pull_error_line" ]; then
    pull_error_line="$(printf "%s" "$pull_output" | sed -n '1p')"
  fi
  if [ -n "$pull_error_line" ]; then
    printf "Docker reported: %s\n" "$(redact_diagnostic "$pull_error_line")" >&2
  fi
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. Check registry/manifest reachability: docker manifest inspect %s\n" "$image" >&2
  printf "  2. Retry after Docker Desktop/network/proxy/GHCR access is healthy: USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n" >&2
  printf "  3. If the image is already cached locally, skip the pull: USE_PUBLISHED_IMAGES=true PULL_PUBLISHED_IMAGES=false ./scripts/launch_self_host.sh\n" >&2
  printf "  4. Use local Skill Mode while registry pulls are blocked: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  5. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

compose_command_hint() {
  if is_true "$use_published_images"; then
    printf "docker compose --env-file %s -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.images.yml" "$(redact_diagnostic "$env_file")"
  else
    printf "docker compose --env-file %s -f infra/compose/docker-compose.yml" "$(redact_diagnostic "$env_file")"
  fi
}

first_relevant_line() {
  printf "%s" "$1" | \
    grep -Ei "bind|port is already allocated|address already in use|permission denied|no space left|pull access denied|manifest|network|timeout|timed out|unhealthy|exited|failed|error" | \
    sed -n '1p' || true
}

print_compose_up_failure_hint() {
  profile_name="$1"
  compose_output="$2"
  compose_hint="$(compose_command_hint)"
  error_line="$(first_relevant_line "$compose_output")"
  if [ -z "$error_line" ]; then
    error_line="$(printf "%s" "$compose_output" | sed -n '1p')"
  fi
  printf "Docker Compose failed to start the Study Anything stack.\n" >&2
  printf "Stack profile: %s\n" "$profile_name" >&2
  if [ -n "$error_line" ]; then
    printf "Docker reported: %s\n" "$(redact_diagnostic "$error_line")" >&2
  fi
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. Inspect container state: %s ps\n" "$compose_hint" >&2
  printf "  2. Inspect recent logs: %s logs --tail=200 api app-postgres\n" "$compose_hint" >&2
  printf "  3. Check ports, Docker, env, and Agent hints: ./scripts/doctor.sh\n" >&2
  printf "  4. If a local port is busy, retry with another API port: API_PORT=8012 ./scripts/launch_self_host.sh\n" >&2
  printf "  5. If Docker is the blocker, use Skill Mode: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  6. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_api_health_timeout_hint() {
  api_url="$1"
  compose_hint="$(compose_command_hint)"
  printf "API did not become healthy at %s after %s attempts.\n" "$api_url" "$health_attempts" >&2
  printf "This usually means the API container exited, Postgres is still unhealthy, or the host port is blocked/busy.\n" >&2
  printf "Inspect with:\n" >&2
  printf "  %s ps\n" "$compose_hint" >&2
  printf "  %s logs --tail=200 api app-postgres\n" "$compose_hint" >&2
  printf "Then try one of these recovery paths:\n" >&2
  printf "  1. Check Docker/ports/env: ./scripts/doctor.sh\n" >&2
  printf "  2. Retry on another API port: API_PORT=8012 ./scripts/launch_self_host.sh\n" >&2
  printf "  3. Use Skill Mode while Docker is blocked: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_unsupported_profile_hint() {
  printf "Unsupported STACK_PROFILE=%s.\n" "$profile" >&2
  printf "Use one of: core, smoke, full.\n" >&2
  printf "Profiles:\n" >&2
  printf "  core  - API and Postgres only; fastest first-run path.\n" >&2
  printf "  smoke - adds mock HTTP Agent and FalkorDB for local smoke tests.\n" >&2
  printf "  full  - adds Langfuse, Redis, ClickHouse, MinIO, and FalkorDB.\n" >&2
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. Use the default profile: unset STACK_PROFILE && ./scripts/launch_self_host.sh\n" >&2
  printf "  2. Run smoke services: STACK_PROFILE=smoke ./scripts/launch_self_host.sh\n" >&2
  printf "  3. Run the full optional stack: STACK_PROFILE=full ./scripts/launch_self_host.sh\n" >&2
  printf "  4. Use Skill Mode while deciding: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  5. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

path_has_non_ascii() {
  printf "%s" "$1" | LC_ALL=C grep -q '[^ -~]'
}

profile="$(env_or_file_value STACK_PROFILE "$profile")"
use_published_images="$(env_or_file_value USE_PUBLISHED_IMAGES "$use_published_images")"
image_tag="$(env_or_file_value STUDY_ANYTHING_IMAGE_TAG "$image_tag")"
docker_source_path="$(env_or_file_value STUDY_ANYTHING_DOCKER_SOURCE_PATH "$docker_source_path")"

validate_self_host_api_port
validate_self_host_profile_ports
validate_self_host_unique_active_ports
self_host_api_port="$(env_or_file_value API_PORT 8000)"

if ! is_true "$use_published_images" && path_has_non_ascii "$docker_source_path"; then
  if ! is_true "${ALLOW_NON_ASCII_DOCKER_BUILD:-false}"; then
    printf "Docker source builds can fail when the checkout path contains non-ASCII characters.\n" >&2
    printf "Current path: %s\n" "$(redact_diagnostic "$docker_source_path")" >&2
    printf "Docker Desktop BuildKit/buildx may report: x-docker-expose-session-sharedkey contains value with non-printable ASCII characters.\n" >&2
    printf "\nUse one of these recovery paths:\n" >&2
    printf "  USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n" >&2
    printf "  git clone <repo-url> ~/study-anything && cd ~/study-anything && ./scripts/launch_self_host.sh\n" >&2
    printf "\nTo bypass this guard anyway:\n" >&2
    printf "  ALLOW_NON_ASCII_DOCKER_BUILD=true ./scripts/launch_self_host.sh\n" >&2
    exit 1
  fi
fi

if is_true "$use_published_images"; then
  export STUDY_ANYTHING_API_IMAGE="${STUDY_ANYTHING_API_IMAGE:-ghcr.io/jzvcpe-goat/study-anything/api:${image_tag}}"
fi

if ! command -v docker >/dev/null 2>&1; then
  print_docker_missing_hint
  exit 1
fi

if ! compose_version_output="$(docker compose version 2>&1)"; then
  print_compose_missing_hint "$compose_version_output"
  exit 1
fi

compose() {
  if is_true "$use_published_images"; then
    docker compose \
      --env-file "$env_file" \
      -f infra/compose/docker-compose.yml \
      -f infra/compose/docker-compose.images.yml \
      "$@"
  else
    docker compose --env-file "$env_file" -f infra/compose/docker-compose.yml "$@"
  fi
}

start_stack() {
  if is_true "$use_published_images"; then
    compose "$@" up -d
  else
    compose "$@" up -d --build
  fi
}

if ! docker_info_output="$(docker info 2>&1)"; then
  if printf "%s" "$docker_info_output" | grep -qi "permission denied"; then
    docker_error_line="$(printf "%s" "$docker_info_output" | grep -i "permission denied\\|docker.sock" | sed -n '1p')"
    if [ -z "$docker_error_line" ]; then
      docker_error_line="$(printf "%s" "$docker_info_output" | sed -n '1p')"
    fi
    printf "Docker socket is not accessible from this shell.\n" >&2
    printf "Docker reported: %s\n" "$(redact_diagnostic "$docker_error_line")" >&2
    printf "Start Docker Desktop, check the active Docker context, or fix access to the Docker socket.\n" >&2
    printf "First-run fallback without Docker: ./scripts/launch_skill_mode.sh\n" >&2
    printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
  else
    docker_error_line="$(printf "%s" "$docker_info_output" | sed -n '1p')"
    printf "Docker daemon is not running. Start Docker Desktop, then retry.\n" >&2
    if [ -n "$docker_error_line" ]; then
      printf "Docker reported: %s\n" "$(redact_diagnostic "$docker_error_line")" >&2
    fi
    printf "First-run fallback without Docker: ./scripts/launch_skill_mode.sh\n" >&2
    printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
  fi
  exit 1
fi

if is_true "$use_published_images"; then
  printf "Using published Study Anything images tagged %s.\n" "$image_tag"
  if is_true "${PULL_PUBLISHED_IMAGES:-true}"; then
    printf "Pulling API image. A cold download can take a few minutes.\n"
    if ! docker_pull_output="$(docker pull "$STUDY_ANYTHING_API_IMAGE" 2>&1)"; then
      print_docker_pull_failure_hint "$STUDY_ANYTHING_API_IMAGE" "$docker_pull_output"
      exit 1
    fi
    if [ -n "$docker_pull_output" ]; then
      printf "%s\n" "$docker_pull_output"
    fi
  else
    printf "Skipping published image pulls because PULL_PUBLISHED_IMAGES=%s.\n" "${PULL_PUBLISHED_IMAGES:-false}"
  fi
else
  printf "Building Study Anything API image from this source checkout.\n"
fi

case "$profile" in
  core)
    stack_profile_args=""
    ;;
  smoke)
    stack_profile_args="--profile smoke"
    ;;
  full)
    stack_profile_args="--profile full"
    ;;
  *)
    print_unsupported_profile_hint
    exit 1
    ;;
esac

if ! stack_output="$(start_stack $stack_profile_args 2>&1)"; then
  print_compose_up_failure_hint "$profile" "$stack_output"
  exit 1
fi
if [ -n "$stack_output" ]; then
  printf "%s\n" "$stack_output"
fi

api_url="http://127.0.0.1:${self_host_api_port}/v1/health"
printf "Waiting for Study Anything API at %s ...\n" "$api_url"
attempt=0
until curl -fsS "$api_url" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$health_attempts" ]; then
    print_api_health_timeout_hint "$api_url"
    exit 1
  fi
  sleep "$health_interval_seconds"
done

printf "Study Anything is ready.\n"
printf "API docs:  http://127.0.0.1:%s/docs\n" "$self_host_api_port"
printf "API health:http://127.0.0.1:%s/v1/health\n" "$self_host_api_port"
printf "Next steps:\n"
printf "  1. Check API health: python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:%s health\n" "$self_host_api_port"
printf "  2. Run the local demo lesson: python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:%s demo\n" "$self_host_api_port"
printf "  3. Optional zero-key Agent gateway: AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --host 127.0.0.1 --port 8787\n"
printf "  4. Register that gateway: python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:%s agent-add-http --set-default\n" "$self_host_api_port"
printf "  5. If anything fails, collect a redacted report: python3 scripts/diagnose_adoption.py\n"
printf "Stop with: ./scripts/stop_self_host.sh\n"
