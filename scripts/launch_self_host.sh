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
use_published_images="${USE_PUBLISHED_IMAGES:-false}"
image_tag="${STUDY_ANYTHING_IMAGE_TAG:-v0.2.2-alpha}"

is_true() {
  case "$1" in
    1|true|TRUE|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if is_true "$use_published_images"; then
  export STUDY_ANYTHING_API_IMAGE="${STUDY_ANYTHING_API_IMAGE:-ghcr.io/jzvcpe-goat/study-anything/api:${image_tag}}"
  export STUDY_ANYTHING_WEB_IMAGE="${STUDY_ANYTHING_WEB_IMAGE:-ghcr.io/jzvcpe-goat/study-anything/web:${image_tag}}"
fi

compose() {
  if is_true "$use_published_images"; then
    docker compose \
      --env-file .env \
      -f infra/compose/docker-compose.yml \
      -f infra/compose/docker-compose.images.yml \
      "$@"
  else
    docker compose --env-file .env -f infra/compose/docker-compose.yml "$@"
  fi
}

start_stack() {
  if is_true "$use_published_images"; then
    compose "$@" up -d
  else
    compose "$@" up -d --build
  fi
}

if ! docker info >/dev/null 2>&1; then
  printf "Docker daemon is not running. Start Docker Desktop, then retry.\n" >&2
  exit 1
fi

if is_true "$use_published_images"; then
  printf "Using published Study Anything images tagged %s.\n" "$image_tag"
  if is_true "${PULL_PUBLISHED_IMAGES:-true}"; then
    printf "Pulling API image first. A cold download can take a few minutes.\n"
    docker pull "$STUDY_ANYTHING_API_IMAGE"
    printf "Pulling Web image second.\n"
    docker pull "$STUDY_ANYTHING_WEB_IMAGE"
  else
    printf "Skipping published image pulls because PULL_PUBLISHED_IMAGES=%s.\n" "${PULL_PUBLISHED_IMAGES:-false}"
  fi
else
  printf "Building Study Anything API and Web images from this source checkout.\n"
fi

case "$profile" in
  core)
    start_stack
    ;;
  smoke)
    start_stack --profile smoke
    ;;
  full)
    start_stack --profile full
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
    if is_true "$use_published_images"; then
      printf "  docker compose --env-file .env -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.images.yml logs --tail=200\n" >&2
    else
      printf "  docker compose --env-file .env -f infra/compose/docker-compose.yml logs --tail=200\n" >&2
    fi
    exit 1
  fi
  sleep 2
done

printf "Study Anything is ready.\n"
printf "Web UI:    http://127.0.0.1:%s\n" "${WEB_PORT:-5173}"
printf "API docs:  http://127.0.0.1:%s/docs\n" "${API_PORT:-8000}"
printf "Stop with: ./scripts/stop_self_host.sh\n"
