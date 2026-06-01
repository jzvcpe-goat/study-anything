#!/usr/bin/env sh
set -eu

if [ -f .env ]; then
  docker compose --env-file .env -f infra/compose/docker-compose.yml --profile full --profile smoke down
else
  docker compose -f infra/compose/docker-compose.yml --profile full --profile smoke down
fi
