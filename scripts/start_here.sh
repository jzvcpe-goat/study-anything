#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

mode="demo"
env_file="${STUDY_ANYTHING_ENV_FILE:-$ROOT/.env}"

usage() {
  cat <<'EOF'
Study Anything beginner launcher

最简单用法：
  macOS 双击 START_HERE.command
  或者运行 ./scripts/start_here.sh

Usage:
  ./scripts/start_here.sh                 Run the zero-key disposable demo.
  ./scripts/start_here.sh --demo          Same as default: no Docker, no API key.
  ./scripts/start_here.sh --keep-running  Start persistent Skill Mode API.
  ./scripts/start_here.sh --foreground    Keep Skill Mode API open in this terminal.
  ./scripts/start_here.sh --docker        Start Docker self-host stack.
  ./scripts/start_here.sh --check-only    Run no-socket contract checks only.
  ./scripts/start_here.sh --doctor        Run local diagnostics only.
  ./scripts/start_here.sh --help          Show this help.

Recommended first command:
  ./scripts/start_here.sh

EOF
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

choose_python() {
  venv_dir="${STUDY_ANYTHING_VENV:-$ROOT/.venv}"
  if [ -x "$venv_dir/bin/python3" ]; then
    printf "%s\n" "$venv_dir/bin/python3"
    return
  fi
  if [ -x "$venv_dir/bin/python" ]; then
    printf "%s\n" "$venv_dir/bin/python"
    return
  fi
  printf "%s\n" "${PYTHON_BIN:-python3}"
}

print_contract_only_recovery_hint() {
  printf "No-socket contract checks you can run inside a sandbox:\n" >&2
  printf "  python3 scripts/verify_openai_compatible_gateway.py --contract-only\n" >&2
  printf "  python3 scripts/verify_agent_gateway_hardening.py --contract-only\n" >&2
  printf "  python3 scripts/verify_external_agent_adapter_hardening.py --contract-only\n" >&2
  printf "These checks do not replace a real localhost runtime smoke from a normal terminal.\n" >&2
}

print_failure_hint() {
  log_text="$1"
  printf "\nBeginner launcher recovery:\n" >&2
  if printf "%s" "$log_text" | grep -Eqi "operation not permitted|permission denied|localhost listening sockets|localhost_socket_blocked|cannot listen|Errno 1|Errno 13"; then
    printf "%s\n" "- This runner appears to block localhost sockets." >&2
    print_contract_only_recovery_hint
    printf "%s\n" "- Then rerun from a normal terminal: ./scripts/start_here.sh" >&2
  elif printf "%s" "$log_text" | grep -Eqi "python 3.11|python_version|python: not found|python3: not found"; then
    printf "%s\n" "- Install Python 3.11 or 3.12, then rerun: ./scripts/start_here.sh" >&2
    printf "%s\n" "- If Python is installed elsewhere, set PYTHON_BIN=/path/to/python3.11." >&2
  elif printf "%s" "$log_text" | grep -Eqi "docker command was not found|docker daemon|docker compose"; then
    printf "%s\n" "- Docker is only needed for --docker. For first use, run the no-Docker demo: ./scripts/start_here.sh --demo" >&2
    printf "%s\n" "- If you want Docker, start Docker Desktop and run: ./scripts/start_here.sh --docker" >&2
  elif printf "%s" "$log_text" | grep -Eqi "port is already in use|address already in use|EADDRINUSE"; then
    printf "%s\n" "- A local port is already in use. Try a different demo port: API_PORT=8013 ./scripts/start_here.sh" >&2
    printf "%s\n" "- Or inspect the machine with: python3 scripts/diagnose_adoption.py" >&2
  elif printf "%s" "$log_text" | grep -Eqi "Failed to establish a new connection|temporary failure in name resolution|No matching distribution|dependency installation failed|pip subprocess"; then
    printf "%s\n" "- Python dependency installation failed. Retry from a terminal with package-index/network access." >&2
    printf "%s\n" "- If downloads are slow, run: SKILL_PIP_INSTALL_TIMEOUT_SECONDS=1200 ./scripts/start_here.sh" >&2
    printf "%s\n" "- Docker fallback after Docker Desktop is ready: ./scripts/start_here.sh --docker" >&2
  else
    printf "%s\n" "- Run a redacted diagnosis: python3 scripts/diagnose_adoption.py" >&2
    printf "%s\n" "- Read the beginner guide: docs/getting-started.md" >&2
  fi
  printf "%s\n" "- Do not paste raw source text, answers, model keys, or private Agent endpoints into public issues." >&2
}

run_step() {
  label="$1"
  shift
  printf "\n==> %s\n" "$label"
  step_log="${TMPDIR:-/tmp}/study-anything-start-here.$$.log"
  if "$@" >"$step_log" 2>&1; then
    redact_file "$step_log"
    rm -f "$step_log"
    return 0
  fi
  status=$?
  redacted_log_tail=""
  if [ -s "$step_log" ]; then
    redacted_log_tail="$(redact_file "$step_log")"
    printf "%s" "$redacted_log_tail" >&2
  fi
  rm -f "$step_log"
  printf "\nStudy Anything beginner launcher failed while: %s\n" "$label" >&2
  printf "Command: %s\n" "$(redact_diagnostic "$*")" >&2
  print_failure_hint "$redacted_log_tail"
  exit "$status"
}

ensure_env_file() {
  if [ -f "$env_file" ]; then
    printf "Using existing local env file: .env\n"
    return 0
  fi
  run_step "Creating local .env with generated development secrets" \
    python3 scripts/setup_env.py
}

print_intro() {
  printf "Study Anything 一键启动\n"
  printf "当前模式: %s\n" "$mode"
  printf "说明: QUICKSTART.md / docs/getting-started.md\n"
}

run_demo() {
  print_intro
  printf "这条路径不需要 Docker，不需要真实模型 API Key。\n"
  printf "你只需要等它跑完。\n"
  run_step "运行零配置本地学习 demo" \
    sh ./scripts/run_skill_mode_demo.sh
  printf "\nDone. You have proved the local learning loop once.\n"
  printf "\n成功。下一步只选一个：\n"
  printf "  1. 正式保持本地学习引擎运行: ./scripts/start_here.sh --keep-running\n"
  printf "  2. 给 Agent shell 使用且后台会消失: ./scripts/start_here.sh --foreground\n"
  printf "  3. 想看说明: QUICKSTART.md\n"
}

run_keep_running() {
  print_intro
  ensure_env_file
  run_step "Checking local env" \
    python3 scripts/check_env.py --env "$env_file"
  run_step "Starting persistent Skill Mode API" \
    sh ./scripts/launch_skill_mode.sh
  python_bin="$(choose_python)"
  run_step "Checking API health" \
    "$python_bin" scripts/study_anything_cli.py health
  printf "\nSkill Mode is running.\n"
  printf "Try:\n"
  printf "  python3 scripts/study_anything_cli.py demo\n"
  printf "  python3 scripts/study_anything_cli.py lesson --title \"检索练习\" --reference local://demo --text \"检索练习能提升长期记忆。\" --answer \"主动回忆能巩固记忆。\"\n"
  printf "If your Agent shell cleans up background processes after commands finish, use:\n"
  printf "  ./scripts/start_here.sh --foreground\n"
  printf "Stop it with:\n"
  printf "  ./scripts/stop_skill_mode.sh\n"
}

run_foreground() {
  print_intro
  ensure_env_file
  run_step "Checking local env" \
    python3 scripts/check_env.py --env "$env_file"
  printf "\nStarting Skill Mode in the foreground.\n"
  printf "Keep this terminal open while Kimi/Codex/WorkBuddy or another terminal calls the API.\n"
  printf "Stop with Ctrl-C.\n\n"
  SKILL_API_FOREGROUND=true exec sh ./scripts/launch_skill_mode.sh
}

run_docker() {
  print_intro
  ensure_env_file
  run_step "Checking local env" \
    python3 scripts/check_env.py --env "$env_file"
  run_step "Running Docker/self-host doctor" \
    sh ./scripts/doctor.sh
  run_step "Launching Docker self-host stack" \
    sh ./scripts/launch_self_host.sh
  printf "\nDocker self-host launch command completed.\n"
  printf "Open API docs: http://localhost:8000/docs\n"
  printf "Stop it with: ./scripts/stop_self_host.sh\n"
}

run_check_only() {
  print_intro
  python_bin="$(choose_python)"
  run_step "Checking OpenAI-compatible gateway contract without sockets" \
    "$python_bin" scripts/verify_openai_compatible_gateway.py --contract-only
  run_step "Checking Agent gateway hardening contract without sockets" \
    "$python_bin" scripts/verify_agent_gateway_hardening.py --contract-only
  run_step "Checking external Agent adapter contract without sockets" \
    "$python_bin" scripts/verify_external_agent_adapter_hardening.py --contract-only
  printf "\nNo-socket contract checks passed. Runtime launch still needs a normal terminal.\n"
}

if [ "$#" -gt 1 ]; then
  usage >&2
  exit 1
fi
if [ "$#" -eq 1 ]; then
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --demo)
      mode="demo"
      ;;
    --keep-running)
      mode="keep-running"
      ;;
    --foreground)
      mode="foreground"
      ;;
    --docker)
      mode="docker"
      ;;
    --check-only)
      mode="check-only"
      ;;
    --doctor)
      mode="doctor"
      ;;
    *)
      printf "Unknown start_here.sh option: %s\n\n" "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
fi

case "$mode" in
  demo)
    run_demo
    ;;
  keep-running)
    run_keep_running
    ;;
  foreground)
    run_foreground
    ;;
  docker)
    run_docker
    ;;
  check-only)
    run_check_only
    ;;
  doctor)
    run_step "Running local diagnostics" sh ./scripts/doctor.sh
    ;;
esac
