#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

data_dir="${STUDY_ANYTHING_DATA_DIR:-$ROOT/data/skill-mode}"
api_host="${SKILL_API_HOST:-127.0.0.1}"
api_port="${API_PORT:-8000}"
api_base="http://$api_host:$api_port"
pid_file="$data_dir/api.pid"
log_file="$data_dir/api.log"
venv_dir="${STUDY_ANYTHING_VENV:-$ROOT/.venv}"
venv_python="$venv_dir/bin/python3"
foreground="${SKILL_API_FOREGROUND:-false}"

if [ "${1:-}" = "--foreground" ]; then
  foreground="true"
fi

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

if curl -fsS "$api_base/v1/health" >/dev/null 2>&1; then
  printf "Study Anything Skill API is already ready at %s\n" "$api_base"
  exit 0
fi

if [ -z "$python_bin" ] || ! command -v "$python_bin" >/dev/null 2>&1; then
  printf "Python 3.11 or newer is required for Skill Mode.\n" >&2
  exit 1
fi

"$python_bin" - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit(
        f"Python 3.11 or newer is required for Skill Mode; found {sys.version.split()[0]}."
    )
PY

if [ ! -x "$venv_python" ]; then
  printf "Creating Skill Mode virtual environment at %s ...\n" "$venv_dir"
  "$python_bin" -m venv "$venv_dir"
fi

if ! "$venv_python" -c "import fastapi, langgraph, uvicorn" >/dev/null 2>&1; then
  printf "Installing Study Anything API dependencies ...\n"
  "$venv_python" -m pip install -e .
fi

mkdir -p "$data_dir"
if [ -f "$pid_file" ]; then
  old_pid="$(cat "$pid_file")"
  if kill -0 "$old_pid" >/dev/null 2>&1; then
    printf "Skill Mode process %s exists but is not healthy. Inspect %s\n" "$old_pid" "$log_file" >&2
    exit 1
  fi
  rm -f "$pid_file"
fi

if [ "$foreground" = "true" ]; then
  printf "Starting Study Anything Skill API in foreground at %s ...\n" "$api_base"
  printf "Keep this terminal open. Stop with Ctrl-C.\n"
  SESSION_STORE=json \
  WORKFLOW_ENGINE=langgraph \
  LANGGRAPH_CHECKPOINTER=memory \
  FALKORDB_ENABLED=false \
  STUDY_ANYTHING_DATA_DIR="$data_dir" \
  exec "$venv_python" -m uvicorn study_anything.api.main:app \
    --host "$api_host" \
    --port "$api_port"
fi

printf "Starting Study Anything Skill API at %s ...\n" "$api_base"
SESSION_STORE=json \
WORKFLOW_ENGINE=langgraph \
LANGGRAPH_CHECKPOINTER=memory \
FALKORDB_ENABLED=false \
STUDY_ANYTHING_DATA_DIR="$data_dir" \
nohup "$venv_python" -m uvicorn study_anything.api.main:app \
  --host "$api_host" \
  --port "$api_port" \
  >"$log_file" 2>&1 &
pid=$!
printf "%s\n" "$pid" >"$pid_file"

attempt=0
until curl -fsS "$api_base/v1/health" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    printf "Skill Mode API did not become healthy. Recent logs:\n" >&2
    tail -n 80 "$log_file" >&2 || true
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$pid_file"
    exit 1
  fi
  sleep 1
done

printf "Study Anything Skill API is ready at %s\n" "$api_base"
printf "Try: python3 scripts/study_anything_cli.py demo\n"
printf "Stop with: ./scripts/stop_skill_mode.sh\n"
printf "Agent shell note: if background processes do not persist, use ./scripts/run_skill_mode_demo.sh.\n"
