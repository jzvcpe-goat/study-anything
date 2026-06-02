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

profile="${STACK_PROFILE:-core}"
compose() {
  docker compose --env-file .env -f infra/compose/docker-compose.yml "$@"
}

if ! docker info >/dev/null 2>&1; then
  printf "Docker daemon is not running. Start Docker Desktop, then retry.\n" >&2
  exit 1
fi

case "$profile" in
  core)
    compose up -d --build
    ;;
  smoke)
    compose --profile smoke up -d --build
    ;;
  full)
    compose --profile full up -d --build
    ;;
  *)
    printf "Unsupported STACK_PROFILE=%s. Use core, smoke, or full.\n" "$profile" >&2
    exit 1
    ;;
esac

api_url="http://127.0.0.1:${API_PORT:-8000}/v1/health"
printf "Waiting for Study Anything API at %s ...\n" "$api_url"
attempt=0
until curl -fsS "$api_url" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    printf "API did not become healthy. Inspect logs with:\n" >&2
    printf "  docker compose --env-file .env -f infra/compose/docker-compose.yml logs --tail=200\n" >&2
    exit 1
  fi
  sleep 2
done

printf "Study Anything is ready.\n"
printf "Web UI:    http://127.0.0.1:%s\n" "${WEB_PORT:-5173}"
printf "API docs:  http://127.0.0.1:%s/docs\n" "${API_PORT:-8000}"
printf "Stop with: ./scripts/stop_self_host.sh\n"
