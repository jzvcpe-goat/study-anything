#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
env_file="${ENV_FILE:-${STUDY_ANYTHING_ENV_FILE:-.env}}"

redact_diagnostic() {
  printf "%s" "$1" | sed \
    -e 's#/Users/[^[:space:]]*#<local-path>#g' \
    -e 's#/private/tmp/[^[:space:]]*#<temp-path>#g' \
    -e 's#/tmp/[^[:space:]]*#<temp-path>#g' \
    -e 's#/private/var/folders/[^[:space:]]*#<temp-path>#g' \
    -e 's#/var/folders/[^[:space:]]*#<temp-path>#g' \
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

print_docker_missing_hint() {
  printf "Docker command was not found in PATH.\n" >&2
  printf "Failure classification: docker_cli_missing\n" >&2
  printf "If the self-host stack is running elsewhere, stop it from a shell with Docker access.\n" >&2
  printf "For local Skill Mode, stop with: ./scripts/stop_skill_mode.sh\n" >&2
  printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_compose_missing_hint() {
  compose_output="$1"
  printf "Docker Compose v2 plugin is not available from this shell.\n" >&2
  printf "Failure classification: docker_compose_missing\n" >&2
  if [ -n "$compose_output" ]; then
    printf "Docker reported: %s\n" "$(redact_diagnostic "$(printf "%s" "$compose_output" | sed -n '1p')")" >&2
  fi
  printf "Install or enable Docker Compose v2, then retry: ./scripts/stop_self_host.sh\n" >&2
  printf "If you only started Skill Mode, stop it with: ./scripts/stop_skill_mode.sh\n" >&2
  printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

print_docker_unavailable_hint() {
  docker_output="$1"
  if printf "%s" "$docker_output" | grep -qi "permission denied"; then
    docker_error_line="$(printf "%s" "$docker_output" | grep -i "permission denied\\|docker.sock" | sed -n '1p')"
    if [ -z "$docker_error_line" ]; then
      docker_error_line="$(printf "%s" "$docker_output" | sed -n '1p')"
    fi
    printf "Docker socket is not accessible from this shell.\n" >&2
    printf "Failure classification: docker_socket_permission_denied\n" >&2
    printf "Docker reported: %s\n" "$(redact_diagnostic "$docker_error_line")" >&2
    printf "Start Docker Desktop, check the active Docker context, or fix access to the Docker socket.\n" >&2
  else
    docker_error_line="$(printf "%s" "$docker_output" | sed -n '1p')"
    printf "Docker daemon is not running. Start Docker Desktop, then retry.\n" >&2
    printf "Failure classification: docker_daemon_unavailable\n" >&2
    if [ -n "$docker_error_line" ]; then
      printf "Docker reported: %s\n" "$(redact_diagnostic "$docker_error_line")" >&2
    fi
  fi
  printf "If you only started Skill Mode, stop it with: ./scripts/stop_skill_mode.sh\n" >&2
  printf "For a redacted diagnosis, run: python3 scripts/diagnose_adoption.py\n" >&2
}

if ! command -v docker >/dev/null 2>&1; then
  print_docker_missing_hint
  exit 1
fi

if ! compose_version_output="$(docker compose version 2>&1)"; then
  print_compose_missing_hint "$compose_version_output"
  exit 1
fi

if ! docker_info_output="$(docker info 2>&1)"; then
  print_docker_unavailable_hint "$docker_info_output"
  exit 1
fi

if [ -f "$env_file" ]; then
  docker compose --env-file "$env_file" -f infra/compose/docker-compose.yml --profile full --profile smoke down
else
  docker compose -f infra/compose/docker-compose.yml --profile full --profile smoke down
fi
