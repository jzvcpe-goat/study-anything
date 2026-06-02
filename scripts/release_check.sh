#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

printf "Study Anything release check\n"
printf "============================\n"

python_bin="${STUDY_ANYTHING_PYTHON:-}"
if [ -z "$python_bin" ]; then
  if [ -x .venv/bin/python ]; then
    python_bin=".venv/bin/python"
  else
    python_bin="python3"
  fi
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  printf "error Python 3.11+ is required. Create a project virtualenv with:\n" >&2
  printf "  python3.11 -m venv .venv\n" >&2
  printf "  .venv/bin/python -m pip install -e .\n" >&2
  exit 1
fi

if ! "$python_bin" -c 'import fastapi' >/dev/null 2>&1; then
  printf "error API dependencies are missing for %s. Install them with:\n" "$python_bin" >&2
  printf "  %s -m pip install -e .\n" "$python_bin" >&2
  exit 1
fi

printf "Using Python runtime: %s\n" "$python_bin"

tmp_env="${TMPDIR:-/tmp}/study-anything-release.env"
"$python_bin" scripts/setup_env.py --force --output "$tmp_env"
"$python_bin" scripts/check_env.py --env "$tmp_env" --strict
if [ -f .env ]; then
  "$python_bin" scripts/check_env.py
fi
"$python_bin" -m compileall -q apps/api/study_anything scripts plugins
"$python_bin" -m unittest discover apps/api/tests
"$python_bin" scripts/smoke_core.py

if command -v npm >/dev/null 2>&1; then
  (cd apps/web && npm ci && npm run build && npm audit --audit-level=moderate)
else
  printf "warn  npm missing; skipped Web build and audit.\n"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose --env-file "$tmp_env" -f infra/compose/docker-compose.yml --profile full config >/dev/null
else
  printf "warn  docker compose missing; skipped Compose config validation.\n"
fi

printf "hint  after launching Docker Compose, run: WEB_BASE=http://127.0.0.1:5173 python3 scripts/verify_full_stack_web.py\n"

printf "ok    release check completed\n"
