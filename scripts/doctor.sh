#!/usr/bin/env sh
set -eu

printf "Study Anything self-host doctor\n"
printf "================================\n"

check_cmd() {
  name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf "ok    %s: %s\n" "$name" "$(command -v "$name")"
  else
    printf "miss  %s\n" "$name"
  fi
}

check_cmd docker
check_cmd python3
check_cmd node
check_cmd npm

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    printf "ok    docker compose: %s\n" "$(docker compose version)"
  else
    printf "miss  docker compose plugin\n"
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  if [ -f .env ]; then
    python3 scripts/check_env.py
  else
    printf "warn  .env missing; run python3 scripts/setup_env.py before launch.\n"
  fi
  python3 -m unittest discover apps/api/tests
fi

printf "\nDefault launch ports: 3000, 5173, 8000, 5432, 5433, 6379, 6378, 8123, 9000, 9090\n"
printf "If a port is occupied, override the matching *_PORT value in .env before launch.\n"
printf "STACK_PROFILE=core starts API/Web/Postgres only; STACK_PROFILE=smoke adds the mock HTTP agent; STACK_PROFILE=full adds Langfuse, Redis, ClickHouse, MinIO, and FalkorDB.\n"
