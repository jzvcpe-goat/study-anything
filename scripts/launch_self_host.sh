#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 scripts/setup_env.py
  else
    cp .env.example .env
    printf "Created .env from .env.example. Replace placeholder secrets before production use.\n"
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  python3 scripts/check_env.py
fi

profile="${STACK_PROFILE:-full}"
case "$profile" in
  core)
    docker compose -f infra/compose/docker-compose.yml up --build
    ;;
  smoke)
    docker compose -f infra/compose/docker-compose.yml --profile smoke up --build
    ;;
  full)
    docker compose -f infra/compose/docker-compose.yml --profile full up --build
    ;;
  *)
    printf "Unsupported STACK_PROFILE=%s. Use core, smoke, or full.\n" "$profile" >&2
    exit 1
    ;;
esac
