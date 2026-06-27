#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
data_dir="${STUDY_ANYTHING_DATA_DIR:-$ROOT/data/skill-mode}"
pid_file="$data_dir/api.pid"
env_file="${STUDY_ANYTHING_ENV_FILE:-$ROOT/.env}"
api_host="${SKILL_API_HOST:-127.0.0.1}"

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

api_port="$(env_or_file_value API_PORT 8000)"
api_base="http://$api_host:$api_port"

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

display_path() {
  value="$1"
  case "$value" in
    "$ROOT"/*)
      printf "%s" "${value#"$ROOT"/}"
      ;;
    "$ROOT")
      printf "."
      ;;
    *)
      redact_diagnostic "$value"
      ;;
  esac
}

is_positive_pid() {
  candidate="$1"
  case "$candidate" in
    ""|*[!0-9]*)
      return 1
      ;;
  esac
  [ "$candidate" -gt 0 ] 2>/dev/null
}

print_no_pid_hint() {
  printf "Study Anything Skill API is not running from its PID file.\n"
  printf "Checked PID file: %s\n" "$(display_path "$pid_file")"
  printf "Expected API base from current env: %s\n" "$(redact_diagnostic "$api_base")"
  case "$api_port" in
    ""|*[!0-9]*)
      printf "Diagnostic classification: invalid_api_port\n"
      printf "API_PORT=%s is not numeric, so port ownership could not be checked.\n" "$(redact_diagnostic "$api_port")"
      printf "Fix it with: unset API_PORT && ./scripts/launch_skill_mode.sh\n"
      return
      ;;
  esac
  if [ "$api_port" -lt 1 ] 2>/dev/null || [ "$api_port" -gt 65535 ] 2>/dev/null; then
    printf "Diagnostic classification: invalid_api_port\n"
    printf "API_PORT=%s is outside the valid TCP port range, so port ownership could not be checked.\n" "$(redact_diagnostic "$api_port")"
    printf "Fix it with: API_PORT=8012 ./scripts/launch_skill_mode.sh\n"
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    if lsof -nP -iTCP:"$api_port" -sTCP:LISTEN >/dev/null 2>&1; then
      owner="$(lsof -nP -iTCP:"$api_port" -sTCP:LISTEN 2>/dev/null | sed -n '2p')"
      printf "Diagnostic classification: port_still_listening_without_pid\n"
      printf "warn  port %s is still listening: %s\n" "$api_port" "$(redact_diagnostic "$owner")"
      printf "This usually means the API was started outside ./scripts/launch_skill_mode.sh or with a different STUDY_ANYTHING_DATA_DIR.\n"
      printf "Next steps:\n"
      printf "  1. Confirm health: curl -fsS %s/v1/health\n" "$(redact_diagnostic "$api_base")"
      printf "  2. Collect a redacted report: python3 scripts/diagnose_adoption.py\n"
      printf "  3. Stop the owning process manually only after confirming it is Study Anything.\n"
    else
      printf "Diagnostic classification: no_listener_without_pid\n"
      printf "No PID file and no listener found on %s.\n" "$(redact_diagnostic "$api_base")"
    fi
  else
    printf "Diagnostic classification: listener_check_unavailable\n"
    printf "lsof is not installed, so the port could not be checked.\n"
    printf "If the next launch reports that the port is busy, run: python3 scripts/diagnose_adoption.py\n"
  fi
}

if [ ! -f "$pid_file" ]; then
  print_no_pid_hint
  exit 0
fi

pid="$(cat "$pid_file" 2>/dev/null || true)"
if ! is_positive_pid "$pid"; then
  printf "Removed invalid Skill Mode PID file: %s\n" "$(display_path "$pid_file")"
  printf "Diagnostic classification: invalid_pid_file\n"
  if [ -n "$pid" ]; then
    printf "Invalid PID value was: %s\n" "$(redact_diagnostic "$pid")"
  else
    printf "Invalid PID value was empty.\n"
  fi
elif kill -0 "$pid" >/dev/null 2>&1; then
  kill "$pid"
  printf "Stopped Study Anything Skill API process %s.\n" "$pid"
  printf "Diagnostic classification: stopped_running_skill_mode_api\n"
  printf "Stopped API base: %s\n" "$(redact_diagnostic "$api_base")"
else
  printf "Removed stale Skill Mode PID file for process %s.\n" "$pid"
  printf "Diagnostic classification: stale_pid_file\n"
  printf "Expected API base from current env: %s\n" "$(redact_diagnostic "$api_base")"
fi
rm -f "$pid_file"
