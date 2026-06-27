#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
env_file="${STUDY_ANYTHING_ENV_FILE:-$ROOT/.env}"

env_file_value() {
  key="$1"
  [ -f "$env_file" ] || return 1
  while IFS= read -r raw_line || [ -n "$raw_line" ]; do
    line="$raw_line"
    case "$line" in
      ""|\#*) continue ;;
    esac
    case "$line" in
      export\ *) line="${line#export }" ;;
    esac
    name="${line%%=*}"
    [ "$name" = "$key" ] || continue
    value="${line#*=}"
    value="$(printf "%s" "$value" | sed 's/[[:space:]]#.*$//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    case "$value" in
      \"*\") value="${value#\"}"; value="${value%%\"*}" ;;
      \'*\') value="${value#\'}"; value="${value%%\'*}" ;;
    esac
    printf "%s" "$value"
    return 0
  done < "$env_file"
  return 1
}

api_port="$(env_file_value API_PORT 2>/dev/null || printf "8000")"
API_BASE="${API_BASE:-${STUDY_ANYTHING_API_BASE:-http://127.0.0.1:$api_port}}"

redact_diagnostic() {
  printf "%s" "$1" | sed \
    -e 's#/Users/[^[:space:]]*#<local-path>#g' \
    -e 's#/private/tmp/[^[:space:]]*#<temp-path>#g' \
    -e 's#/tmp/[^[:space:]]*#<temp-path>#g' \
    -e 's#/private/var/folders/[^[:space:]]*#<temp-path>#g' \
    -e 's#/var/folders/[^[:space:]]*#<temp-path>#g' \
    -e 's#sk-\(proj-\)\{0,1\}[A-Za-z0-9_-]\{12,\}#sk-<redacted>#g' \
    -e 's#\([Aa]uthorization[[:space:]]*[:=][[:space:]]*\)[Bb]earer[[:space:]][A-Za-z0-9._~+/=-]\{8,\}#\1Bearer <redacted>#g'
}

classify_smoke_failure() {
  status="$1"
  diagnostic="$2"
  case "$diagnostic" in
    *"Operation not permitted"*|*"operation not permitted"*|*"Permission denied"*|*"permission denied"*)
      printf "localhost_socket_blocked"
      return 0
      ;;
    *"Failed to connect"*|*"Connection refused"*|*"connection refused"*|*"Could not connect"*|*"could not connect"*)
      printf "api_unreachable"
      return 0
      ;;
    *"Operation timed out"*|*"operation timed out"*|*"timed out"*|*"Timeout"*)
      printf "api_timeout"
      return 0
      ;;
    *"Could not resolve host"*|*"Name or service not known"*|*"nodename nor servname"*)
      printf "api_host_unresolved"
      return 0
      ;;
    *"The requested URL returned error"*)
      printf "api_endpoint_http_error"
      return 0
      ;;
  esac
  case "$status" in
    6)
      printf "api_host_unresolved"
      ;;
    7)
      printf "api_unreachable"
      ;;
    22)
      printf "api_endpoint_http_error"
      ;;
    28)
      printf "api_timeout"
      ;;
    *)
      printf "api_smoke_failed"
      ;;
  esac
}

if ! command -v curl >/dev/null 2>&1; then
  printf "Study Anything API smoke failed: curl is not installed or not on PATH.\n" >&2
  printf "Failure classification: missing_curl\n" >&2
  printf "Recovery:\n" >&2
  printf "  1. Install curl or run the Python verifier: python3 scripts/diagnose_adoption.py\n" >&2
  printf "  2. Start local Skill Mode first: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  3. If the API uses another port, set API_BASE=http://127.0.0.1:<port>.\n" >&2
  exit 1
fi

curl_log="${TMPDIR:-/tmp}/study-anything-api-smoke.$$.log"
cleanup() {
  rm -f "$curl_log"
}
trap cleanup EXIT HUP INT TERM

check_endpoint() {
  label="$1"
  path="$2"
  url="$API_BASE$path"
  if curl -fsS "$url" 2>"$curl_log"; then
    printf "\n"
    return 0
  else
    status=$?
  fi
  diagnostic=""
  if [ -s "$curl_log" ]; then
    diagnostic="$(redact_diagnostic "$(cat "$curl_log")")"
  fi
  printf "Study Anything API smoke failed: %s endpoint is not reachable.\n" "$label" >&2
  printf "Endpoint: %s\n" "$url" >&2
  printf "Exit code: %s\n" "$status" >&2
  printf "Failure classification: %s\n" "$(classify_smoke_failure "$status" "$diagnostic")" >&2
  if [ -n "$diagnostic" ]; then
    printf "curl diagnostic:\n%s\n" "$diagnostic" >&2
  fi
  printf "Recovery:\n" >&2
  printf "  1. Start the local API: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  2. If you launched on a custom port, retry with: API_BASE=http://127.0.0.1:<port> sh scripts/verify_api_smoke.sh\n" >&2
  printf "  3. Collect a redacted report: python3 scripts/diagnose_adoption.py\n" >&2
  printf "  4. If localhost sockets are blocked in this runner, rerun from a normal terminal or host shell.\n" >&2
  exit "$status"
}

check_endpoint "health" "/v1/health"
check_endpoint "system status" "/v1/system/status"
check_endpoint "plugins" "/v1/plugins"
