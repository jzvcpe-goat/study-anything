#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

export STUDY_ANYTHING_DATA_DIR="${STUDY_ANYTHING_DATA_DIR:-$ROOT/data/skill-mode-demo}"
export API_PORT="${API_PORT:-8012}"
export STUDY_ANYTHING_RETRIEVAL_BACKEND="${STUDY_ANYTHING_RETRIEVAL_BACKEND:-memory}"
api_host="${SKILL_API_HOST:-127.0.0.1}"
export STUDY_ANYTHING_API_BASE="http://$api_host:$API_PORT"
export API_BASE="$STUDY_ANYTHING_API_BASE"

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

redact_file() {
  while IFS= read -r line || [ -n "$line" ]; do
    redact_diagnostic "$line"
    printf "\n"
  done < "$1"
}

print_contract_only_recovery_hint() {
  printf "Before leaving this sandbox, you can still prove no-socket contracts:\n" >&2
  printf "  python3 scripts/verify_openai_compatible_gateway.py --contract-only\n" >&2
  printf "  python3 scripts/verify_agent_gateway_hardening.py --contract-only\n" >&2
  printf "  python3 scripts/verify_external_agent_adapter_hardening.py --contract-only\n" >&2
  printf "These checks do not replace the runtime demo; rerun the demo from a normal terminal for localhost proof.\n" >&2
}

print_step_specific_hint() {
  log_text="$1"
  if printf "%s" "$log_text" | grep -Eqi "Invalid API_PORT"; then
    printf "\nDetected invalid API_PORT configuration.\n" >&2
    printf "Use a numeric port from 1 to 65535, for example:\n" >&2
    printf "  unset API_PORT && ./scripts/run_skill_mode_demo.sh\n" >&2
    printf "  API_PORT=8013 ./scripts/run_skill_mode_demo.sh\n" >&2
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "port is already in use|address already in use|EADDRINUSE"; then
    printf "\nDetected that the selected local API port is already in use.\n" >&2
    printf "Choose a free port and retry, for example:\n" >&2
    printf "  API_PORT=8013 ./scripts/run_skill_mode_demo.sh\n" >&2
    printf "Or inspect the listener with: python3 scripts/diagnose_adoption.py\n" >&2
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "cannot listen|localhost listening sockets|operation not permitted|permission denied|Errno 1|Errno 13"; then
    printf "\nDetected that this runner cannot open localhost listening sockets.\n" >&2
    print_contract_only_recovery_hint
    printf "Run the same command from a normal terminal or host shell:\n" >&2
    printf "  ./scripts/run_skill_mode_demo.sh\n" >&2
    printf "If you are inside an AI platform sandbox, collect: python3 scripts/diagnose_adoption.py\n" >&2
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "dependency installation failed|dependency installation timed out|timed out after|ReadTimeout|TimeoutError|Connection timed out|SKILL_PIP_INSTALL_TIMEOUT_SECONDS|No matching distribution|Failed to establish a new connection|nodename nor servname|temporary failure in name resolution|pip subprocess"; then
    printf "\nDetected Python dependency installation failure.\n" >&2
    printf "Retry from a terminal with PyPI/network access, or configure a package index:\n" >&2
    printf "  PIP_INDEX_URL=https://pypi.org/simple ./scripts/run_skill_mode_demo.sh\n" >&2
    printf "If downloads are only slow, increase the bounded install wait:\n" >&2
    printf "  SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200 ./scripts/run_skill_mode_demo.sh\n" >&2
    printf "Docker fallback: USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh\n" >&2
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "Agent provider test failed|user-owned Agent exit is not ready|Bad Gateway|HTTP 502|configuration_required|upstream_unavailable"; then
    printf "\nDetected that the user-owned Agent exit is not ready.\n" >&2
    printf "Use the zero-key gateway first. It is a long-running process, so keep it open in terminal 2:\n" >&2
    printf "  AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py --port 8787\n" >&2
    printf "Then register it from terminal 1:\n" >&2
    printf "  python3 scripts/study_anything_cli.py agent-add-http --set-default\n" >&2
    return 0
  fi
}

classify_step_failure() {
  log_text="$1"
  if printf "%s" "$log_text" | grep -Eqi "Invalid API_PORT"; then
    printf "invalid_api_port"
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "port is already in use|address already in use|EADDRINUSE"; then
    printf "port_in_use"
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "cannot listen|localhost listening sockets|operation not permitted|permission denied|Errno 1|Errno 13"; then
    printf "localhost_socket_blocked"
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "dependency installation failed|dependency installation timed out|timed out after|ReadTimeout|TimeoutError|Connection timed out|SKILL_PIP_INSTALL_TIMEOUT_SECONDS|No matching distribution|Failed to establish a new connection|nodename nor servname|temporary failure in name resolution|pip subprocess"; then
    printf "dependency_install_failed"
    return 0
  fi
  if printf "%s" "$log_text" | grep -Eqi "Agent provider test failed|user-owned Agent exit is not ready|Bad Gateway|HTTP 502|configuration_required|upstream_unavailable"; then
    printf "agent_gateway_not_ready"
    return 0
  fi
  printf "skill_mode_demo_step_failed"
}

cleanup() {
  sh ./scripts/stop_skill_mode.sh >/dev/null 2>&1 || true
}

run_step() {
  label="$1"
  shift
  printf "%s ...\n" "$label"
  step_log="${TMPDIR:-/tmp}/study-anything-skill-demo-step.$$.log"
  if "$@" >"$step_log" 2>&1; then
    redact_file "$step_log"
    rm -f "$step_log"
    return 0
  else
    status=$?
  fi
  redacted_log_tail=""
  if [ -s "$step_log" ]; then
    redacted_log_tail="$(redact_file "$step_log")"
    printf "%s" "$redacted_log_tail" >&2
  fi
  rm -f "$step_log"
  printf "\nStudy Anything Skill Mode demo step failed: %s\n" "$label" >&2
  printf "Command: %s\n" "$(redact_diagnostic "$*")" >&2
  printf "API base: %s\n" "$STUDY_ANYTHING_API_BASE" >&2
  printf "Failure classification: %s\n" "$(classify_step_failure "$redacted_log_tail")" >&2
  print_step_specific_hint "$redacted_log_tail"
  printf "Try these recovery paths:\n" >&2
  printf "  1. Collect a redacted report: python3 scripts/diagnose_adoption.py\n" >&2
  printf "  2. Start the API only: ./scripts/launch_skill_mode.sh\n" >&2
  printf "  3. Retry with a different port: API_PORT=8013 ./scripts/run_skill_mode_demo.sh\n" >&2
  printf "  4. If localhost sockets are blocked, run from a normal terminal or host shell.\n" >&2
  printf "  5. In a socket-blocked sandbox, run the three --contract-only verifiers first.\n" >&2
  exit "$status"
}

trap cleanup EXIT HUP INT TERM

printf "Starting disposable Study Anything Skill Mode at %s ...\n" "$STUDY_ANYTHING_API_BASE"
run_step "Starting Skill Mode API" sh ./scripts/launch_skill_mode.sh

venv_dir="${STUDY_ANYTHING_VENV:-$ROOT/.venv}"
if [ -x "$venv_dir/bin/python3" ]; then
  python_bin="$venv_dir/bin/python3"
elif [ -x "$venv_dir/bin/python" ]; then
  python_bin="$venv_dir/bin/python"
else
  python_bin="${PYTHON_BIN:-python3}"
fi

run_step "Running deterministic Skill Mode CLI flow" \
  "$python_bin" scripts/verify_skill_cli_flow.py

run_step "Verifying Agent eval artifact flow" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_agent_eval_flow.py

run_step "Verifying Agent eval maturity report" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/run_external_agent_evals.py \
  --tool report \
  --create-session \
  --required

run_step "Verifying Agent quality eval runner" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/run_external_agent_evals.py \
  --tool deepeval \
  --create-session \
  --allow-native-quality-fallback

run_step "Verifying OpenAI-compatible gateway dry-run flow" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_openai_compatible_gateway.py

run_step "Verifying platform-agent tool manifest" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_platform_agent_tools.py

run_step "Verifying enriched platform lesson flow" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_platform_lesson_flow.py

run_step "Verifying importer-based platform lesson flow" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_importer_lesson_flow.py

run_step "Verifying importer runtime and retrieval flow" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_importer_runtime_retrieval_flow.py

run_step "Verifying platform ecosystem eval flow" \
  env API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_platform_ecosystem_eval_flow.py

printf "ok    Skill Mode demo completed. API was cleaned up.\n"
