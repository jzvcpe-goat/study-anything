#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

data_dir="${STUDY_ANYTHING_DATA_DIR:-$ROOT/data/skill-mode}"
api_host="${SKILL_API_HOST:-127.0.0.1}"
env_file="${STUDY_ANYTHING_ENV_FILE:-$ROOT/.env}"

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
pid_file="$data_dir/api.pid"
log_file="$data_dir/api.log"
pip_install_log="$data_dir/pip-install.log"
venv_create_log="$data_dir/venv-create.log"
venv_dir="${STUDY_ANYTHING_VENV:-$ROOT/.venv}"
venv_python="$venv_dir/bin/python3"
foreground="${SKILL_API_FOREGROUND:-false}"
health_attempts="${SKILL_API_HEALTH_ATTEMPTS:-30}"
pip_install_timeout_seconds="${PIP_INSTALL_TIMEOUT_SECONDS:-${SKILL_PIP_INSTALL_TIMEOUT_SECONDS:-900}}"
pip_default_timeout="${PIP_DEFAULT_TIMEOUT:-60}"
pip_retries="${PIP_RETRIES:-3}"
skill_install_target="${SKILL_PIP_INSTALL_TARGET:-}"
skill_workflow_engine="${SKILL_WORKFLOW_ENGINE:-deterministic}"
locked_skill_requirements="$ROOT/requirements/locked-skill.txt"

validate_skill_api_port() {
  case "$api_port" in
    ""|*[!0-9]*)
      printf "Invalid API_PORT=%s for Skill Mode.\n" "$api_port" >&2
      printf "API_PORT must be a number from 1 to 65535.\n" >&2
      printf "Try one of these recovery paths:\n" >&2
      printf "  1. Use the default port: unset API_PORT && ./scripts/launch_skill_mode.sh\n" >&2
      printf "  2. Choose a known free port: API_PORT=8012 ./scripts/launch_skill_mode.sh\n" >&2
      printf "  3. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
      exit 1
      ;;
  esac
  if [ "$api_port" -lt 1 ] 2>/dev/null || [ "$api_port" -gt 65535 ] 2>/dev/null; then
    printf "Invalid API_PORT=%s for Skill Mode.\n" "$api_port" >&2
    printf "API_PORT must be between 1 and 65535.\n" >&2
    printf "Try one of these recovery paths:\n" >&2
    printf "  1. Use the default port: unset API_PORT && ./scripts/launch_skill_mode.sh\n" >&2
    printf "  2. Choose a known free port: API_PORT=8012 ./scripts/launch_skill_mode.sh\n" >&2
    printf "  3. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
    exit 1
  fi
}

validate_positive_integer_setting() {
  setting_name="$1"
  setting_value="$2"
  example="$3"
  case "$setting_value" in
    ""|*[!0-9]*)
      printf "Invalid %s=%s.\n" "$setting_name" "$setting_value" >&2
      printf "Use a positive number of seconds, for example:\n" >&2
      printf "  %s ./scripts/launch_skill_mode.sh\n" "$example" >&2
      exit 1
      ;;
  esac
  if [ "$setting_value" -lt 1 ] 2>/dev/null; then
    printf "Invalid %s=%s.\n" "$setting_name" "$setting_value" >&2
    printf "Use a positive number of seconds, for example:\n" >&2
    printf "  %s ./scripts/launch_skill_mode.sh\n" "$example" >&2
    exit 1
  fi
}

validate_pip_install_timeout() {
  validate_positive_integer_setting PIP_INSTALL_TIMEOUT_SECONDS "$pip_install_timeout_seconds" "PIP_INSTALL_TIMEOUT_SECONDS=900"
  validate_positive_integer_setting PIP_DEFAULT_TIMEOUT "$pip_default_timeout" "PIP_DEFAULT_TIMEOUT=60"
  validate_positive_integer_setting PIP_RETRIES "$pip_retries" "PIP_RETRIES=3"
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

print_recent_logs() {
  tail -n 80 "$log_file" 2>/dev/null || true
}

print_skill_mode_ready_next_steps() {
  printf "Study Anything Skill API is ready at %s\n" "$api_base"
  printf "Next steps:\n"
  printf "  1. Check API health: python3 scripts/study_anything_cli.py --api-base %s health\n" "$api_base"
  printf "  2. Run the local demo lesson: python3 scripts/study_anything_cli.py --api-base %s demo\n" "$api_base"
  printf "  3. Optional zero-key Agent gateway: AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --host 127.0.0.1 --port 8787\n"
  printf "  4. Register that gateway: python3 scripts/study_anything_cli.py --api-base %s agent-add-http --set-default\n" "$api_base"
  printf "  5. If anything fails, collect a redacted report: python3 scripts/diagnose_adoption.py\n"
  printf "Stop with: ./scripts/stop_skill_mode.sh\n"
  printf "Agent shell note: if background processes do not persist, use ./scripts/run_skill_mode_demo.sh.\n"
}

is_study_anything_health_payload() {
  payload="$1"
  printf "%s" "$payload" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ok"' &&
  printf "%s" "$payload" | grep -Eq '"version"[[:space:]]*:'
}

print_wrong_health_service_hint() {
  payload="$1"
  printf "A service answered %s/v1/health, but it does not look like Study Anything.\n" "$api_base" >&2
  if [ -n "$payload" ]; then
    printf "Health response excerpt: %s\n" "$(redact_diagnostic "$payload" | cut -c 1-300)" >&2
  fi
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. If another app owns this port, retry with a free port: API_PORT=8012 ./scripts/launch_skill_mode.sh\n" >&2
  printf "  2. Inspect the listener: lsof -nP -iTCP:%s -sTCP:LISTEN\n" "$api_port" >&2
  printf "  3. If this is stale Study Anything state, stop it: ./scripts/stop_skill_mode.sh\n" >&2
  printf "  4. Collect a redacted report: python3 scripts/diagnose_adoption.py\n" >&2
}

print_contract_only_recovery_hint() {
  printf "Before leaving this socket-blocked runner, you can still prove no-socket contracts:\n" >&2
  printf "  python3 scripts/verify_openai_compatible_gateway.py --contract-only\n" >&2
  printf "  python3 scripts/verify_agent_gateway_hardening.py --contract-only\n" >&2
  printf "  python3 scripts/verify_external_agent_adapter_hardening.py --contract-only\n" >&2
  printf "These checks are sandbox evidence only; rerun ./scripts/launch_skill_mode.sh from a normal terminal for localhost runtime proof.\n" >&2
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

print_bind_permission_hint() {
  log_tail="$1"
  if printf "%s" "$log_tail" | grep -Eqi "operation not permitted|permission denied|Errno 13" &&
     printf "%s" "$log_tail" | grep -Eqi "bind|address|$api_host"; then
    printf "\nLocal Skill Mode API could not bind to %s:%s from this runner.\n" "$api_host" "$api_port" >&2
    printf "This usually means the current agent sandbox blocks listening sockets.\n" >&2
    printf "Try one of these recovery paths:\n" >&2
    printf "  1. Run no-socket contract checks in this sandbox first:\n" >&2
    printf "     python3 scripts/verify_openai_compatible_gateway.py --contract-only\n" >&2
    printf "     python3 scripts/verify_agent_gateway_hardening.py --contract-only\n" >&2
    printf "     python3 scripts/verify_external_agent_adapter_hardening.py --contract-only\n" >&2
    printf "  2. Run this command from a normal terminal or host shell: ./scripts/launch_skill_mode.sh\n" >&2
    printf "  3. If another process owns the port, set API_PORT to a free port and retry.\n" >&2
    printf "  4. Run python3 scripts/diagnose_adoption.py for a redacted support report.\n" >&2
  fi
}

print_early_exit_hint() {
  log_tail="$1"
  printf "\nSkill Mode API process exited before it became healthy.\n" >&2
  if [ -z "$log_tail" ]; then
    printf "No startup log was written before the process exited.\n" >&2
    printf "Local Skill Mode API could not bind to %s:%s, or Python exited before uvicorn wrote logs.\n" "$api_host" "$api_port" >&2
  fi
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. If this runner blocks localhost sockets, run no-socket contract checks here first:\n" >&2
  printf "     python3 scripts/verify_openai_compatible_gateway.py --contract-only\n" >&2
  printf "     python3 scripts/verify_agent_gateway_hardening.py --contract-only\n" >&2
  printf "     python3 scripts/verify_external_agent_adapter_hardening.py --contract-only\n" >&2
  printf "  2. Run from a normal terminal or host shell: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  3. See foreground errors directly: ./scripts/launch_skill_mode.sh --foreground\n" >&2
  printf "  4. If another app owns the port, retry with a free port: API_PORT=8012 ./scripts/launch_skill_mode.sh\n" >&2
  printf "  5. Collect a redacted report: python3 scripts/diagnose_adoption.py\n" >&2
}

print_port_in_use_hint() {
  printf "Skill Mode API port is already in use: %s:%s\n" "$api_host" "$api_port" >&2
  if command -v lsof >/dev/null 2>&1; then
    owner="$(lsof -nP -iTCP:"$api_port" -sTCP:LISTEN 2>/dev/null | sed -n '2p' || true)"
    if [ -n "$owner" ]; then
      printf "Detected listener: %s\n" "$(redact_diagnostic "$owner")" >&2
    fi
  fi
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. If this is an old Study Anything process, stop it: ./scripts/stop_skill_mode.sh\n" >&2
  printf "  2. If another app owns the port, retry with a free port: API_PORT=8012 ./scripts/launch_skill_mode.sh\n" >&2
  printf "  3. Inspect port ownership manually: lsof -nP -iTCP:%s -sTCP:LISTEN\n" "$api_port" >&2
  printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_unhealthy_existing_process_hint() {
  old_pid="$1"
  printf "Skill Mode process %s exists but is not healthy at %s.\n" "$old_pid" "$api_base" >&2
  printf "Log file: %s\n" "$(display_path "$log_file")" >&2
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. Inspect recent logs: tail -n 80 %s\n" "$(display_path "$log_file")" >&2
  printf "  2. Restart the local API: ./scripts/stop_skill_mode.sh && ./scripts/launch_skill_mode.sh\n" >&2
  printf "  3. If another service owns this port, retry with a free port: API_PORT=8012 ./scripts/launch_skill_mode.sh\n" >&2
  printf "  4. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_invalid_pid_file_hint() {
  old_pid="$1"
  printf "Removed invalid stale Skill Mode PID file: %s\n" "$(display_path "$pid_file")" >&2
  if [ -n "$old_pid" ]; then
    printf "Invalid PID value was: %s\n" "$(redact_diagnostic "$old_pid")" >&2
  else
    printf "Invalid PID value was empty.\n" >&2
  fi
  printf "Continuing with a fresh Skill Mode startup.\n" >&2
}

print_dependency_install_excerpt() {
  if [ ! -f "$pip_install_log" ]; then
    return 0
  fi
  excerpt="$(
    grep -Ei \
      "installing study anything api dependencies|installing build dependencies|pip subprocess to install build dependencies|dependency installation timed out|timed out after|readtimeout|timeouterror|connection timed out|failed to establish a new connection|nodename nor servname provided|temporary failure in name resolution|could not find a version that satisfies|no matching distribution found|/simple/setuptools/|/simple/pip/" \
      "$pip_install_log" 2>/dev/null | \
      grep -Eiv "Retrying" | \
      tail -n 12 || true
  )"
  if [ -z "$excerpt" ]; then
    excerpt="$(tail -n 40 "$pip_install_log" 2>/dev/null || true)"
  fi
  if [ -n "$excerpt" ]; then
    printf "\nRelevant pip output:\n%s\n" "$(redact_diagnostic "$excerpt")" >&2
  fi
}

run_pip_install() {
  "$venv_python" - "$pip_install_log" "$pip_install_timeout_seconds" "$venv_python" "$@" <<'PY'
import shlex
import subprocess
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
try:
    timeout = int(sys.argv[2])
except ValueError:
    timeout = 900
command = [sys.argv[3], *sys.argv[4:]]
with log_path.open("ab") as log:
    rendered = " ".join(shlex.quote(part) for part in command)
    log.write(
        f"\n[study-anything] running dependency install with process timeout {timeout}s: {rendered}\n".encode()
    )
    log.flush()
    try:
        completed = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log.write(f"\n[study-anything] dependency installation timed out after {timeout}s.\n".encode())
        log.write(
            b"[study-anything] retry from a networked terminal, set PIP_INDEX_URL, "
            b"or increase SKILL_PIP_INSTALL_TIMEOUT_SECONDS.\n"
        )
        raise SystemExit(124)
raise SystemExit(completed.returncode)
PY
}

print_venv_creation_excerpt() {
  if [ ! -f "$venv_create_log" ]; then
    return 0
  fi
  excerpt="$(
    grep -Ei \
      "ensurepip|No module named venv|python3[.-].*venv|venv|permission denied|operation not permitted|externally managed|Errno 13|Errno 1" \
      "$venv_create_log" 2>/dev/null | \
      tail -n 16 || true
  )"
  if [ -z "$excerpt" ]; then
    excerpt="$(tail -n 40 "$venv_create_log" 2>/dev/null || true)"
  fi
  if [ -n "$excerpt" ]; then
    printf "\nRelevant venv output:\n%s\n" "$(redact_diagnostic "$excerpt")" >&2
  fi
}

print_venv_creation_failure_hint() {
  python_candidate="$1"
  resolved_python="$(command -v "$python_candidate" 2>/dev/null || printf "%s" "$python_candidate")"
  printf "\nStudy Anything virtual environment creation failed.\n" >&2
  printf "Python interpreter: %s\n" "$(display_path "$resolved_python")" >&2
  printf "Target venv: %s\n" "$(display_path "$venv_dir")" >&2
  print_venv_creation_excerpt
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. Install Python's venv/ensurepip support, then retry: ./scripts/launch_skill_mode.sh\n" >&2
  printf "     Debian/Ubuntu example: sudo apt install python3.11-venv\n" >&2
  printf "  2. Use a known-good interpreter: PYTHON_BIN=/path/to/python3.11 ./scripts/launch_skill_mode.sh\n" >&2
  printf "  3. Use an existing writable venv: STUDY_ANYTHING_VENV=/path/to/.venv ./scripts/launch_skill_mode.sh\n" >&2
  printf "  4. Remove a partially created venv and retry: rm -rf %s && ./scripts/launch_skill_mode.sh\n" "$(display_path "$venv_dir")" >&2
  printf "  5. Use Docker published images instead: USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n" >&2
  printf "  6. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
  printf "Full venv log: %s\n" "$(display_path "$venv_create_log")" >&2
}

print_python_recovery_paths() {
  printf "Try one of these recovery paths:\n" >&2
  printf "  1. Install Python 3.11 or 3.12 and retry: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  2. Use a specific interpreter: PYTHON_BIN=/path/to/python3.11 ./scripts/launch_skill_mode.sh\n" >&2
  printf "  3. Use an existing venv: STUDY_ANYTHING_VENV=/path/to/.venv ./scripts/launch_skill_mode.sh\n" >&2
  printf "  4. Use Docker published images instead: USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n" >&2
  printf "  5. For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_python_missing_hint() {
  printf "Python 3.11 or 3.12 is required for Skill Mode, but no usable interpreter was found.\n" >&2
  if [ -n "${PYTHON_BIN:-}" ]; then
    printf "Configured PYTHON_BIN was not found or not executable: %s\n" "$(display_path "$PYTHON_BIN")" >&2
  else
    printf "Checked python3.12, python3.11, and python3 on PATH.\n" >&2
  fi
  print_python_recovery_paths
}

print_python_version_hint() {
  python_candidate="$1"
  version_text="$("$python_candidate" -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || printf "unknown")"
  resolved_python="$(command -v "$python_candidate" 2>/dev/null || printf "%s" "$python_candidate")"
  printf "Python 3.11 or 3.12 is required for Skill Mode; found %s at %s.\n" "$version_text" "$(display_path "$resolved_python")" >&2
  print_python_recovery_paths
}

check_bind_preflight() {
  if [ "${SKILL_API_SKIP_BIND_PREFLIGHT:-false}" = "true" ]; then
    return 0
  fi
  mkdir -p "$data_dir"
  bind_error_file="$data_dir/bind-preflight.err"
  if "$venv_python" - "$api_host" "$api_port" 2>"$bind_error_file" <<'PY'
import errno
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
except OSError as exc:
    if exc.errno == errno.EADDRINUSE:
        print(f"port_in_use: {host}:{port} is already in use ({exc})", file=sys.stderr)
        raise SystemExit(2)
    if exc.errno in {errno.EPERM, errno.EACCES}:
        print(f"permission_denied: cannot bind {host}:{port} ({exc})", file=sys.stderr)
        raise SystemExit(3)
    print(f"bind_failed: cannot bind {host}:{port} ({exc})", file=sys.stderr)
    raise SystemExit(4)
PY
  then
    rm -f "$bind_error_file"
    return 0
  else
    bind_status=$?
  fi
  bind_error="$(cat "$bind_error_file" 2>/dev/null || true)"
  rm -f "$bind_error_file"
  case "$bind_status" in
    2)
      print_port_in_use_hint
      ;;
    3)
      printf "Local Skill Mode API cannot listen on %s:%s from this runner.\n" "$api_host" "$api_port" >&2
      printf "This usually means the current agent sandbox blocks localhost listening sockets.\n" >&2
      print_contract_only_recovery_hint
      printf "Run from a normal terminal or host shell, then retry: ./scripts/launch_skill_mode.sh\n" >&2
      printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
      ;;
    *)
      printf "Skill Mode API bind preflight failed for %s:%s.\n" "$api_host" "$api_port" >&2
      printf "%s\n" "$(redact_diagnostic "$bind_error")" >&2
      printf "Try API_PORT=8012 ./scripts/launch_skill_mode.sh, or run python3 scripts/diagnose_adoption.py.\n" >&2
      ;;
  esac
  return "$bind_status"
}

print_usage() {
  cat <<'EOF'
Usage: ./scripts/launch_skill_mode.sh [--foreground]

Starts the local Study Anything Skill Mode API.

Options:
  --foreground   Run the API in the current terminal instead of the background.
  --help         Show this help.

Common configuration:
  API_PORT=8012 ./scripts/launch_skill_mode.sh
  SKILL_API_HOST=127.0.0.1 ./scripts/launch_skill_mode.sh
  STUDY_ANYTHING_VENV=.venv ./scripts/launch_skill_mode.sh

After it starts:
  python3 scripts/study_anything_cli.py health
  python3 scripts/study_anything_cli.py demo
EOF
}

if [ "$#" -gt 1 ]; then
  printf "launch_skill_mode.sh accepts at most one option.\n" >&2
  print_usage >&2
  exit 1
fi
case "${1:-}" in
  "")
    ;;
  "--foreground")
    foreground="true"
    ;;
  "--help"|"-h")
    print_usage
    exit 0
    ;;
  *)
    printf "Unknown launch_skill_mode.sh option: %s\n" "$(redact_diagnostic "$1")" >&2
    printf "Use API_PORT=8012 ./scripts/launch_skill_mode.sh to choose a port; --port is not a supported option.\n" >&2
    print_usage >&2
    exit 1
    ;;
esac

validate_skill_api_port
validate_pip_install_timeout

if [ -x "$venv_python" ]; then
  python_bin="$venv_python"
elif [ -n "${PYTHON_BIN:-}" ]; then
  python_bin="$PYTHON_BIN"
else
  python_bin=""
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      python_bin="$candidate"
      break
    fi
  done
fi

existing_health_payload="$(curl -fsS "$api_base/v1/health" 2>/dev/null || true)"
if [ -n "$existing_health_payload" ]; then
  if is_study_anything_health_payload "$existing_health_payload"; then
    printf "Study Anything Skill API is already running.\n"
    print_skill_mode_ready_next_steps
    exit 0
  fi
  print_wrong_health_service_hint "$existing_health_payload"
  exit 1
fi

if [ -z "$python_bin" ] || ! command -v "$python_bin" >/dev/null 2>&1; then
  print_python_missing_hint
  exit 1
fi

if ! "$python_bin" - <<'PY'
import sys

raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 13) else 1)
PY
then
  print_python_version_hint "$python_bin"
  exit 1
fi

if [ ! -x "$venv_python" ]; then
  printf "Creating Skill Mode virtual environment at %s ...\n" "$(display_path "$venv_dir")"
  mkdir -p "$data_dir"
  : >"$venv_create_log"
  if ! "$python_bin" -m venv "$venv_dir" >"$venv_create_log" 2>&1; then
    print_venv_creation_failure_hint "$python_bin"
    exit 1
  fi
fi

if ! "$venv_python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  printf "Installing Study Anything API dependencies ...\n"
  mkdir -p "$data_dir/pip-cache"
  : >"$pip_install_log"
  export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$data_dir/pip-cache}"
  export PIP_DISABLE_PIP_VERSION_CHECK="${PIP_DISABLE_PIP_VERSION_CHECK:-1}"
  export PIP_DEFAULT_TIMEOUT="$pip_default_timeout"
  export PIP_RETRIES="$pip_retries"
  export PIP_NO_INPUT="${PIP_NO_INPUT:-1}"
  install_failed="false"
  if [ -f "$locked_skill_requirements" ]; then
    if ! run_pip_install -m pip install \
      --timeout "$pip_default_timeout" \
      --retries "$pip_retries" \
      --require-hashes \
      -r "$locked_skill_requirements"; then
      install_failed="true"
    elif [ -n "$skill_install_target" ]; then
      run_pip_install -m pip install \
        --timeout "$pip_default_timeout" \
        --retries "$pip_retries" \
        --no-deps \
        --no-build-isolation \
        -e "$skill_install_target" || install_failed="true"
    fi
  elif [ -z "$skill_install_target" ]; then
    if run_pip_install -m pip install \
      --timeout "$pip_default_timeout" \
      --retries "$pip_retries" \
      "fastapi>=0.115.0" \
      "uvicorn>=0.30.0" \
      "pydantic>=2.8.0" \
      "httpx>=0.27.0"; then
      :
    else
      install_failed="true"
    fi
  else
    if "$venv_python" -c "import setuptools" >/dev/null 2>&1; then
      if run_pip_install -m pip install --timeout "$pip_default_timeout" --retries "$pip_retries" --no-build-isolation -e "$skill_install_target"; then
        :
      else
        pip_install_status=$?
        if [ "$pip_install_status" -eq 124 ]; then
          install_failed="true"
        else
          printf "\nNo-build-isolation install failed; retrying with standard build isolation ...\n" >&2
          run_pip_install -m pip install --timeout "$pip_default_timeout" --retries "$pip_retries" -e "$skill_install_target" || install_failed="true"
        fi
      fi
    else
      if run_pip_install -m pip install --timeout "$pip_default_timeout" --retries "$pip_retries" -e "$skill_install_target"; then
        :
      else
        pip_install_status=$?
        if [ "$pip_install_status" -eq 124 ]; then
          install_failed="true"
        else
          printf "\nInitial dependency install failed; retrying without build isolation ...\n" >&2
          run_pip_install -m pip install --timeout "$pip_default_timeout" --retries "$pip_retries" --no-build-isolation -e "$skill_install_target" || install_failed="true"
        fi
      fi
    fi
  fi
  if [ "${install_failed:-false}" = "true" ]; then
    printf "\nStudy Anything dependency installation failed.\n" >&2
    printf "Common causes: no PyPI/network access, a corporate proxy, or a locked-down agent runner.\n" >&2
    print_dependency_install_excerpt
    printf "Try one of these recovery paths:\n" >&2
    printf "  1. Re-run from a normal terminal with network access: ./scripts/launch_skill_mode.sh\n" >&2
    printf "  2. Configure a reachable package index, for example: PIP_INDEX_URL=https://pypi.org/simple ./scripts/launch_skill_mode.sh\n" >&2
    printf "  3. Use Docker published images instead of local Python install: USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n" >&2
    printf "  4. Preinstall the locked Skill Mode runtime: %s -m pip install --require-hashes -r requirements/locked-skill.txt\n" "$(display_path "$venv_python")" >&2
    printf "  5. If downloads are just slow, increase the bounded install wait: SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200 ./scripts/launch_skill_mode.sh\n" >&2
    printf "  6. If you are inside an AI platform sandbox, run python3 scripts/diagnose_adoption.py and share the redacted output.\n" >&2
    printf "Full pip log: %s\n" "$(display_path "$pip_install_log")" >&2
    exit 1
  fi
fi

mkdir -p "$data_dir"
if [ -f "$pid_file" ]; then
  old_pid="$(cat "$pid_file" 2>/dev/null || true)"
  if ! is_positive_pid "$old_pid"; then
    print_invalid_pid_file_hint "$old_pid"
    rm -f "$pid_file"
  elif kill -0 "$old_pid" >/dev/null 2>&1; then
    print_unhealthy_existing_process_hint "$old_pid"
    exit 1
  else
    rm -f "$pid_file"
  fi
fi

check_bind_preflight || exit $?

if [ "$foreground" = "true" ]; then
  printf "Starting Study Anything Skill API in foreground at %s ...\n" "$api_base"
  printf "Keep this terminal open. Stop with Ctrl-C.\n"
  SESSION_STORE=json \
  WORKFLOW_ENGINE="$skill_workflow_engine" \
  LANGGRAPH_CHECKPOINTER=memory \
  FALKORDB_ENABLED=false \
  PYTHONPATH="$ROOT/apps/api${PYTHONPATH:+:$PYTHONPATH}" \
  STUDY_ANYTHING_DATA_DIR="$data_dir" \
  exec "$venv_python" -m uvicorn study_anything.api.main:app \
    --host "$api_host" \
    --port "$api_port"
fi

printf "Starting Study Anything Skill API at %s ...\n" "$api_base"
SESSION_STORE=json \
WORKFLOW_ENGINE="$skill_workflow_engine" \
LANGGRAPH_CHECKPOINTER=memory \
FALKORDB_ENABLED=false \
PYTHONPATH="$ROOT/apps/api${PYTHONPATH:+:$PYTHONPATH}" \
STUDY_ANYTHING_DATA_DIR="$data_dir" \
nohup "$venv_python" -m uvicorn study_anything.api.main:app \
  --host "$api_host" \
  --port "$api_port" \
  >"$log_file" 2>&1 &
pid=$!
printf "%s\n" "$pid" >"$pid_file"

attempt=0
last_health_payload=""
until last_health_payload="$(curl -fsS "$api_base/v1/health" 2>/dev/null)" &&
  is_study_anything_health_payload "$last_health_payload"; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$health_attempts" ]; then
    printf "Skill Mode API did not become healthy. Recent logs:\n" >&2
    log_tail="$(print_recent_logs)"
    redacted_log_tail="$(redact_diagnostic "$log_tail")"
    printf "%s\n" "$redacted_log_tail" >&2
    if [ -z "$redacted_log_tail" ] || ! kill -0 "$pid" >/dev/null 2>&1; then
      print_early_exit_hint "$redacted_log_tail"
    fi
    if [ -n "$last_health_payload" ]; then
      print_wrong_health_service_hint "$last_health_payload"
    fi
    print_bind_permission_hint "$redacted_log_tail"
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$pid_file"
    exit 1
  fi
  sleep 1
done

print_skill_mode_ready_next_steps
