#!/usr/bin/env sh
set -eu

printf "Study Anything self-host doctor\n"
printf "================================\n"

problems=0
recommended_next_step=""
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
env_file="${ENV_FILE:-${STUDY_ANYTHING_ENV_FILE:-.env}}"
profile="${STACK_PROFILE:-core}"
use_published_images="${USE_PUBLISHED_IMAGES:-false}"
image_tag="${STUDY_ANYTHING_IMAGE_TAG:-v0.3.29-alpha}"
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

set_recommended_next_step() {
  if [ -z "$recommended_next_step" ]; then
    recommended_next_step="$1"
  fi
}

path_has_non_ascii() {
  printf "%s" "$1" | LC_ALL=C grep -q '[^ -~]'
}

redact_diagnostic() {
  printf "%s" "$1" | sed \
    -e 's#/Users/[^[:space:],"'"'"'<>}]*#<local-path>#g' \
    -e 's#/private/tmp/[^[:space:],"'"'"'<>}]*#<temp-path>#g' \
    -e 's#/tmp/[^[:space:],"'"'"'<>}]*#<temp-path>#g' \
    -e 's#/private/var/folders/[^[:space:],"'"'"'<>}]*#<temp-path>#g' \
    -e 's#/var/folders/[^[:space:],"'"'"'<>}]*#<temp-path>#g' \
    -e 's#https://[^/@[:space:]]*:[^/@[:space:]]*@#https://<redacted>@#g' \
    -e 's#http://[^/@[:space:]]*:[^/@[:space:]]*@#http://<redacted>@#g' \
    -e 's#sk-\(proj-\)\{0,1\}[A-Za-z0-9_-]\{12,\}#sk-<redacted>#g' \
    -e 's#\([Aa]uthorization[[:space:]]*[:=][[:space:]]*\)[Bb]earer[[:space:]][A-Za-z0-9._~+/=-]\{8,\}#\1Bearer <redacted>#g' \
    -e 's#"\([Tt][Oo][Kk][Ee][Nn]\)"[[:space:]]*:[[:space:]]*"[^"]*"#"\1":"<redacted>"#g' \
    -e 's#"\([Ss][Ee][Cc][Rr][Ee][Tt]\)"[[:space:]]*:[[:space:]]*"[^"]*"#"\1":"<redacted>"#g' \
    -e 's#"\([Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd]\)"[[:space:]]*:[[:space:]]*"[^"]*"#"\1":"<redacted>"#g' \
    -e 's#"\([Aa][Pp][Ii]_[Kk][Ee][Yy]\)"[[:space:]]*:[[:space:]]*"[^"]*"#"\1":"<redacted>"#g' \
    -e 's#\([?&][Aa][Pp][Ii][_-]\{0,1\}[Kk][Ee][Yy]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Xx]-[Aa][Pp][Ii]-[Kk][Ee][Yy]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Aa][Cc][Cc][Ee][Ss][Ss][_-]\{0,1\}[Tt][Oo][Kk][Ee][Nn]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Aa][Uu][Tt][Hh][Oo][Rr][Ii][Zz][Aa][Tt][Ii][Oo][Nn]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Aa][Uu][Tt][Hh]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Bb][Ee][Aa][Rr][Ee][Rr]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Tt][Oo][Kk][Ee][Nn]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Cc][Ll][Ii][Ee][Nn][Tt][_-]\{0,1\}[Ss][Ee][Cc][Rr][Ee][Tt]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Ss][Ee][Cc][Rr][Ee][Tt]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([?&][Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd]=\)[^&[:space:],"'"'"'<>}]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*KEY[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*TOKEN[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*SECRET[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*key[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*token[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g' \
    -e 's#\([A-Za-z_]*secret[A-Za-z_]*=\)[^[:space:]]*#\1<redacted>#g'
}

is_study_anything_health_payload() {
  payload="$1"
  printf "%s" "$payload" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' &&
  printf "%s" "$payload" | grep -Eq '"version"[[:space:]]*:'
}

is_agent_gateway_health_payload_ready() {
  payload="$1"
  printf "%s" "$payload" | grep -Eiq '"status"[[:space:]]*:[[:space:]]*"(ok|healthy)"'
}

agent_endpoint_has_secret_material() {
  value="$1"
  lower_value="$(printf "%s" "$value" | tr '[:upper:]' '[:lower:]')"
  case "$lower_value" in
    *://*@*|*"?api_key="*|*"&api_key="*|*"#api_key="*|*"?apikey="*|*"&apikey="*|*"#apikey="*|*"?api-key="*|*"&api-key="*|*"#api-key="*|*"?x-api-key="*|*"&x-api-key="*|*"#x-api-key="*|*"?access_token="*|*"&access_token="*|*"#access_token="*|*"?accesstoken="*|*"&accesstoken="*|*"#accesstoken="*|*"?token="*|*"&token="*|*"#token="*|*"?authorization="*|*"&authorization="*|*"#authorization="*|*"?auth="*|*"&auth="*|*"#auth="*|*"?bearer="*|*"&bearer="*|*"#bearer="*|*"?client_secret="*|*"&client_secret="*|*"#client_secret="*|*"?clientsecret="*|*"&clientsecret="*|*"#clientsecret="*|*"?secret="*|*"&secret="*|*"#secret="*|*"?password="*|*"&password="*|*"#password="*|*"sk-"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

normalize_agent_gateway_url() {
  value="$1"
  case "$value" in
    127.*|localhost:*|0.0.0.0:*|\[::1\]:*)
      printf "http://%s" "$value"
      ;;
    *)
      printf "%s" "$value"
      ;;
  esac
}

agent_gateway_health_url() {
  value="${1%/}"
  case "$value" in
    */invoke)
      value="${value%/invoke}"
      ;;
  esac
  case "$value" in
    http://0.0.0.0:*)
      value="http://127.0.0.1:${value#http://0.0.0.0:}"
      ;;
  esac
  printf "%s/health" "$value"
}

check_cmd() {
  name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf "ok    %s: %s\n" "$name" "$(redact_diagnostic "$(command -v "$name")")"
  else
    printf "miss  %s\n" "$name"
    case "$name" in
      docker)
        set_recommended_next_step "Install/start Docker Desktop, or run ./scripts/launch_skill_mode.sh for the no-Docker local smoke."
        ;;
      curl)
        set_recommended_next_step "Install curl, or run python3 scripts/diagnose_adoption.py for a Python-based diagnostic report."
        ;;
      *)
        set_recommended_next_step "Install the missing command '$name', then rerun ./scripts/doctor.sh."
        ;;
    esac
    problems=$((problems + 1))
  fi
}

check_optional_cmd() {
  name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf "ok    %s: %s\n" "$name" "$(redact_diagnostic "$(command -v "$name")")"
  else
    printf "warn  %s missing; optional for Docker self-host.\n" "$name"
  fi
}

check_python_runtime() {
  python_runtime="${STUDY_ANYTHING_PYTHON:-}"
  if [ -z "$python_runtime" ]; then
    if [ -x .venv/bin/python ]; then
      python_runtime=".venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
      python_runtime="python3"
    else
      printf "warn  Python 3.11+ was not found. Skill Mode and local verifiers need Python 3.11 or newer.\n"
      printf "      Install Python 3.11+, or use Docker published images: USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n"
      return
    fi
  fi
  if python_version_output="$("$python_runtime" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"); raise SystemExit(0 if sys.version_info >= (3, 11) else 2)' 2>/dev/null)"; then
    printf "ok    Python runtime for local tools: %s (%s)\n" "$(redact_diagnostic "$python_runtime")" "$python_version_output"
  else
    python_status=$?
    if [ "$python_status" -eq 2 ]; then
      printf "warn  Python runtime is older than 3.11: %s (%s).\n" "$(redact_diagnostic "$python_runtime")" "$python_version_output"
      printf "      Skill Mode and local verifiers need Python 3.11 or newer.\n"
      printf "      Try: PYTHON_BIN=/path/to/python3.11 ./scripts/launch_skill_mode.sh\n"
      printf "      Or use Docker published images: USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n"
    else
      printf "warn  Could not inspect Python runtime: %s.\n" "$(redact_diagnostic "$python_runtime")"
      printf "      If Skill Mode fails, retry with PYTHON_BIN=/path/to/python3.11 ./scripts/launch_skill_mode.sh\n"
    fi
  fi
}

latest_release_blocked_report_dir() {
  report_root="data/release-blocked-reports"
  if [ ! -d "$report_root" ]; then
    return 0
  fi
  ls -td "$report_root"/*/ 2>/dev/null | sed -n '1p' | sed 's#/$##'
}

release_report_python() {
  if [ -x .venv/bin/python ]; then
    printf "%s" ".venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    printf "%s" "python3"
  fi
}

release_contract_report_summary() {
  report_dir="$1"
  python_runtime="$(release_report_python)"
  if [ -z "$python_runtime" ]; then
    return 0
  fi
  "$python_runtime" - "$report_dir" <<'PY' 2>/dev/null || true
from __future__ import annotations

import json
from pathlib import Path
import sys

report_dir = Path(sys.argv[1])
paths = sorted(report_dir.glob("*.contract-only.json"))
if not paths:
    raise SystemExit(0)
print(f"Contract-only no-socket reports: {len(paths)} found.")
for path in paths:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print(f"- {path.name}: unreadable")
        continue
    contract = payload.get("contract") or path.name.removesuffix(".contract-only.json")
    status = payload.get("status") or "unknown"
    replaces_runtime = bool(payload.get("runtime_gate_replaced", False))
    print(f"- {contract}: {status} (replaces runtime gate: {str(replaces_runtime).lower()})")
print("These reports prove sandbox-safe contracts only; rerun ./scripts/release_check.sh from a normal terminal for release verification.")
PY
}

check_cmd docker
check_cmd curl
check_optional_cmd python3
check_optional_cmd lsof
check_python_runtime

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    printf "ok    docker compose: %s\n" "$(docker compose version)"
  else
    printf "miss  docker compose plugin\n"
    set_recommended_next_step "Install Docker Compose v2, or run ./scripts/launch_skill_mode.sh for the no-Docker local smoke."
    problems=$((problems + 1))
  fi
  if docker_info_output="$(docker info 2>&1)"; then
    printf "ok    docker daemon is running\n"
  else
    if printf "%s" "$docker_info_output" | grep -qi "permission denied"; then
      docker_error_line="$(printf "%s" "$docker_info_output" | grep -i "permission denied\\|docker.sock" | sed -n '1p')"
      if [ -z "$docker_error_line" ]; then
        docker_error_line="$(printf "%s" "$docker_info_output" | sed -n '1p')"
      fi
      printf "miss  docker socket is not accessible from this shell.\n"
      printf "      Docker reported: %s\n" "$(redact_diagnostic "$docker_error_line")"
      printf "      Start Docker Desktop, check the active Docker context, or fix access to the Docker socket.\n"
      printf "      First-run fallback without Docker: ./scripts/launch_skill_mode.sh\n"
      set_recommended_next_step "Start Docker Desktop/check the active Docker context, or run ./scripts/launch_skill_mode.sh."
    else
      docker_error_line="$(printf "%s" "$docker_info_output" | sed -n '1p')"
      printf "miss  docker daemon is not running; start Docker Desktop before launch.\n"
      if [ -n "$docker_error_line" ]; then
        printf "      Docker reported: %s\n" "$(redact_diagnostic "$docker_error_line")"
      fi
      set_recommended_next_step "Start Docker Desktop, then rerun ./scripts/doctor.sh; no-Docker fallback: ./scripts/launch_skill_mode.sh."
    fi
    problems=$((problems + 1))
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  if [ -f "$env_file" ]; then
    if env_check_output="$(python3 scripts/check_env.py --env "$env_file" 2>&1)"; then
      printf "%s\n" "$env_check_output"
    else
      printf "miss  %s failed environment validation.\n" "$(redact_diagnostic "$env_file")"
      printf "%s\n" "$(redact_diagnostic "$env_check_output")" | sed 's/^/      /'
      printf "      Recovery: python3 scripts/check_env.py --env %s --strict\n" "$(redact_diagnostic "$env_file")"
      printf "      Regenerate local secrets: python3 scripts/setup_env.py --force --output %s\n" "$(redact_diagnostic "$env_file")"
      set_recommended_next_step "Fix the env file first: python3 scripts/check_env.py --env $(redact_diagnostic "$env_file") --strict"
      problems=$((problems + 1))
    fi
  else
    printf "warn  %s missing; run python3 scripts/setup_env.py before launch.\n" "$(redact_diagnostic "$env_file")"
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
try:
    lines = path.read_text(encoding="utf-8").splitlines()
except (OSError, UnicodeDecodeError):
    lines = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        continue
    key, raw = line.split("=", 1)
    key = key.strip()
    if key.startswith("export "):
        key = key[len("export ") :].strip()
    if key.strip() == target:
        raw_value = raw.strip()
        if raw_value.startswith('"'):
            end = raw_value.find('"', 1)
            value = raw_value[1:end] if end != -1 else raw_value[1:]
        elif raw_value.startswith("'"):
            end = raw_value.find("'", 1)
            value = raw_value[1:end] if end != -1 else raw_value[1:]
        else:
            value = raw_value.split(" #", 1)[0].strip()
print(value)
PY
  else
    printf "%s\n" "$default"
  fi
}

profile="$(env_value STACK_PROFILE "$profile")"
use_published_images="$(env_value USE_PUBLISHED_IMAGES "$use_published_images")"
image_tag="$(env_value STUDY_ANYTHING_IMAGE_TAG "$image_tag")"
docker_source_path="$(env_value STUDY_ANYTHING_DOCKER_SOURCE_PATH "$docker_source_path")"

port_is_valid() {
  value="$1"
  case "$value" in
    ""|*[!0-9]*)
      return 1
      ;;
  esac
  [ "$value" -ge 1 ] 2>/dev/null && [ "$value" -le 65535 ] 2>/dev/null
}

check_launch_configuration() {
  api_port_value="$(env_value API_PORT 8000)"
  if ! port_is_valid "$api_port_value"; then
    printf "miss  API_PORT=%s is not a valid TCP port.\n" "$api_port_value"
    printf "      Use a number from 1 to 65535.\n"
    printf "      Recovery: unset API_PORT && ./scripts/launch_skill_mode.sh\n"
    printf "      Alternate: API_PORT=8012 ./scripts/launch_skill_mode.sh\n"
    set_recommended_next_step "unset API_PORT && ./scripts/launch_skill_mode.sh"
    problems=$((problems + 1))
  fi
  case "$profile" in
    core|smoke|full)
      ;;
    *)
      printf "miss  Unsupported STACK_PROFILE=%s.\n" "$profile"
      printf "      Use one of: core, smoke, full.\n"
      printf "      Recovery: unset STACK_PROFILE && ./scripts/launch_self_host.sh\n"
      printf "      Smoke path: STACK_PROFILE=smoke ./scripts/launch_self_host.sh\n"
      set_recommended_next_step "unset STACK_PROFILE && ./scripts/launch_self_host.sh"
      problems=$((problems + 1))
      ;;
  esac
}

check_port() {
  label="$1"
  key="$2"
  default="$3"
  port="$(env_value "$key" "$default")"
  case "$port" in
    ""|*[!0-9]*)
      if [ "$key" = "API_PORT" ]; then
        printf "info  skipping API port availability check because API_PORT=%s is invalid; fix launch configuration above first.\n" "$port"
        return
      fi
      printf "miss  %s=%s is not a numeric port for %s.\n" "$key" "$port" "$label"
      printf "      Use a number from 1 to 65535. For API, try API_PORT=8012.\n"
      set_recommended_next_step "Set $key to a numeric TCP port, then rerun ./scripts/doctor.sh."
      problems=$((problems + 1))
      return
      ;;
  esac
  if [ "$port" -lt 1 ] 2>/dev/null || [ "$port" -gt 65535 ] 2>/dev/null; then
    if [ "$key" = "API_PORT" ]; then
      printf "info  skipping API port availability check because API_PORT=%s is invalid; fix launch configuration above first.\n" "$port"
      return
    fi
    printf "miss  %s=%s is outside the valid TCP port range for %s.\n" "$key" "$port" "$label"
    printf "      Use a number from 1 to 65535. For API, try API_PORT=8012.\n"
    set_recommended_next_step "Set $key to a TCP port from 1 to 65535, then rerun ./scripts/doctor.sh."
    problems=$((problems + 1))
    return
  fi
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
    health_payload="$(curl -fsS "$url" 2>/dev/null || true)"
    if [ -n "$health_payload" ]; then
      if [ "$label" = "API health" ] && ! is_study_anything_health_payload "$health_payload"; then
        printf "miss  %s responded at %s, but it does not look like Study Anything.\n" "$label" "$url"
        printf "      Health response excerpt: %s\n" "$(redact_diagnostic "$health_payload" | cut -c 1-300)"
        printf "      Recovery: API_PORT=8012 ./scripts/launch_skill_mode.sh\n"
        printf "      Inspect listener: lsof -nP -iTCP:%s -sTCP:LISTEN\n" "$(env_value API_PORT 8000)"
        printf "      Or collect diagnostics: python3 scripts/diagnose_adoption.py\n"
        set_recommended_next_step "API_PORT=8012 ./scripts/launch_skill_mode.sh"
        problems=$((problems + 1))
      elif [ "$label" = "HTTP Agent gateway" ] && ! is_agent_gateway_health_payload_ready "$health_payload"; then
        printf "warn  %s responded at %s, but it is not healthy yet.\n" "$label" "$url"
        printf "      Health response excerpt: %s\n" "$(redact_diagnostic "$health_payload" | cut -c 1-300)"
        printf "      Zero-key recovery: AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --port 8787\n"
        printf "      Register it: python3 scripts/study_anything_cli.py agent-add-http --set-default\n"
        printf "      Or inspect endpoint diagnostics: python3 scripts/diagnose_adoption.py\n"
      else
        printf "ok    %s responds at %s\n" "$label" "$url"
      fi
    else
      printf "info  %s is not responding yet at %s. This is normal before launch.\n" "$label" "$url"
    fi
  fi
}

check_launch_configuration

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && [ -f "$env_file" ]; then
  if is_true "$use_published_images"; then
    export STUDY_ANYTHING_API_IMAGE="${STUDY_ANYTHING_API_IMAGE:-ghcr.io/jzvcpe-goat/study-anything/api:${image_tag}}"
    if docker compose --env-file "$env_file" -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.images.yml config >/dev/null; then
      printf "ok    Docker Compose published-image config is valid for STACK_PROFILE=%s\n" "$profile"
    else
      printf "miss  Docker Compose published-image config is invalid.\n"
      set_recommended_next_step "Run python3 scripts/diagnose_adoption.py, then fix Docker Compose published-image configuration before launch."
      problems=$((problems + 1))
    fi
  else
    if path_has_non_ascii "$docker_source_path" && ! is_true "${ALLOW_NON_ASCII_DOCKER_BUILD:-false}"; then
      printf "miss  Docker source build path contains non-ASCII characters: %s\n" "$(redact_diagnostic "$docker_source_path")"
      printf "      Use USE_PUBLISHED_IMAGES=true, clone to an ASCII-only path, or set ALLOW_NON_ASCII_DOCKER_BUILD=true to bypass.\n"
      set_recommended_next_step "USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh"
      problems=$((problems + 1))
    fi
    if docker compose --env-file "$env_file" -f infra/compose/docker-compose.yml config >/dev/null; then
      printf "ok    Docker Compose source-build config is valid for STACK_PROFILE=%s\n" "$profile"
    else
      printf "miss  Docker Compose source-build config is invalid.\n"
      set_recommended_next_step "Run python3 scripts/diagnose_adoption.py, then fix Docker Compose configuration before launch."
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
    printf "warn  Skipping profile-specific port checks because STACK_PROFILE=%s is unsupported.\n" "$profile"
    ;;
esac

api_port="$(env_value API_PORT 8000)"
check_http_health "API health" "http://127.0.0.1:${api_port}/v1/health"

agent_url="$(normalize_agent_gateway_url "$(env_value AGENT_HTTP_GATEWAY_URL http://host.docker.internal:8787)")"
if [ -z "$agent_url" ]; then
  printf "info  AGENT_HTTP_GATEWAY_URL is blank. Use the demo Agent or configure your own gateway through /v1/agents/*.\n"
elif agent_endpoint_has_secret_material "$agent_url"; then
  printf "miss  AGENT_HTTP_GATEWAY_URL must not contain inline credentials or secret-like query parameters.\n"
  printf "      Current value: %s\n" "$(redact_diagnostic "$agent_url")"
  printf "      Move model/API credentials into your private gateway or platform Agent environment.\n"
  printf "      Then configure only the plain endpoint, for example: AGENT_HTTP_GATEWAY_URL=http://host.docker.internal:8787\n"
  printf "      For a zero-key local smoke: AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --port 8787\n"
  set_recommended_next_step "Remove credentials from AGENT_HTTP_GATEWAY_URL, then run AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --port 8787"
  problems=$((problems + 1))
else
  case "$agent_url" in
    http://127.0.0.1:*|http://localhost:*|http://0.0.0.0:*|http://\[::1\]:*)
      check_http_health "HTTP Agent gateway" "$(agent_gateway_health_url "$agent_url")"
      ;;
    *)
      printf "info  Agent gateway is configured as %s. If Docker cannot reach it, try http://host.docker.internal:8787 or the smoke profile.\n" "$(redact_diagnostic "$agent_url")"
      ;;
  esac
fi

if [ -d plugins ]; then
  printf "ok    bundled plugin directory exists: plugins\n"
else
  printf "miss  bundled plugin directory is missing.\n"
  set_recommended_next_step "Restore the bundled plugins directory from the repo, then rerun ./scripts/doctor.sh."
  problems=$((problems + 1))
fi

plugin_dir="$(env_value STUDY_ANYTHING_PLUGIN_INSTALL_DIR data/plugins)"
plugin_parent="$(dirname "$plugin_dir")"
if [ -d "$plugin_dir" ]; then
  printf "ok    local plugin install directory exists: %s\n" "$(redact_diagnostic "$plugin_dir")"
elif [ -d "$plugin_parent" ]; then
  printf "info  local plugin install directory will be created on first install: %s\n" "$(redact_diagnostic "$plugin_dir")"
else
  printf "warn  local plugin install parent is missing: %s\n" "$(redact_diagnostic "$plugin_parent")"
fi

latest_blocked_report="$(latest_release_blocked_report_dir)"
if [ -n "$latest_blocked_report" ]; then
  printf "\nRelease gate reminder\n"
  printf "warn  previous release_check.sh left localhost-blocked reports at: %s\n" "$(redact_diagnostic "$latest_blocked_report")"
  printf "      This usually means the prior runner could not open localhost sockets; it is not release verification.\n"
  contract_summary="$(release_contract_report_summary "$latest_blocked_report")"
  if [ -n "$contract_summary" ]; then
    printf "%s\n" "$contract_summary" | while IFS= read -r line; do
      printf "      %s\n" "$(redact_diagnostic "$line")"
    done
  fi
  printf "      Rerun from a normal terminal: ./scripts/release_check.sh\n"
  printf "      Inspect diagnostics: python3 scripts/diagnose_adoption.py --release-report-dir %s\n" "$(redact_diagnostic "$latest_blocked_report")"
  printf "      Clear after inspection: python3 scripts/diagnose_adoption.py --release-report-dir %s --clear-release-blocked-reports\n" "$(redact_diagnostic "$latest_blocked_report")"
fi

printf "\nRecovery commands\n"
printf "  Launch core stack:        ./scripts/launch_self_host.sh\n"
printf "  Launch with GHCR images:  USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n"
printf "  Skip pulls if cached:     USE_PUBLISHED_IMAGES=true PULL_PUBLISHED_IMAGES=false ./scripts/launch_self_host.sh\n"
printf "  Fastest local smoke:      ./scripts/launch_skill_mode.sh && python3 scripts/study_anything_cli.py demo\n"
printf "  Zero-key Agent gateway:   AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --port 8787\n"
printf "  Smoke Agent path:         STACK_PROFILE=smoke ./scripts/launch_self_host.sh\n"
printf "  API logs:                 docker compose --env-file %s -f infra/compose/docker-compose.yml logs --tail=200 api app-postgres\n" "$(redact_diagnostic "$env_file")"
printf "  Full stack status:        docker compose --env-file %s -f infra/compose/docker-compose.yml ps\n" "$(redact_diagnostic "$env_file")"
printf "  Backup before changes:    python3 scripts/self_host_data.py backup\n"
printf "  Stop stack:               ./scripts/stop_self_host.sh\n"

printf "\nProfile guide\n"
printf "  STACK_PROFILE=core starts API/Postgres only.\n"
printf "  STACK_PROFILE=smoke adds the mock HTTP agent and FalkorDB for smoke tests.\n"
printf "  STACK_PROFILE=full adds Langfuse, Redis, ClickHouse, MinIO, and FalkorDB.\n"

if [ "$problems" -gt 0 ]; then
  printf "\nDoctor found %s blocking issue(s).\n" "$problems" >&2
  if [ -z "$recommended_next_step" ]; then
    recommended_next_step="Run ./scripts/launch_skill_mode.sh for the shortest local path, or fix the blocking issue above before Docker self-host."
  fi
  printf "Recommended next step: %s\n" "$recommended_next_step" >&2
  exit 1
fi

printf "\nDoctor found no blocking issues.\n"
printf "Recommended next step: ./scripts/launch_self_host.sh\n"
