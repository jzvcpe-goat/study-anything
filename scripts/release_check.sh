#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

printf "Study Anything release check\n"
printf "============================\n"

tmp_env="${TMPDIR:-/tmp}/study-anything-release.env"
python3 scripts/setup_env.py --force --output "$tmp_env"
python3 scripts/check_env.py --env "$tmp_env" --strict
if [ -f .env ]; then
  python3 scripts/check_env.py
fi
python3 -m compileall -q apps/api/study_anything scripts plugins
python3 -m unittest discover apps/api/tests
python3 scripts/smoke_core.py

if command -v npm >/dev/null 2>&1; then
  (cd apps/web && npm ci && npm run build && npm audit --audit-level=moderate)
else
  printf "warn  npm missing; skipped Web build and audit.\n"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose -f infra/compose/docker-compose.yml --profile full config >/dev/null
else
  printf "warn  docker compose missing; skipped Compose config validation.\n"
fi

printf "ok    release check completed\n"
