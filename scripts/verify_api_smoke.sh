#!/usr/bin/env sh
set -eu

API_BASE="${API_BASE:-http://127.0.0.1:8000}"

curl -fsS "$API_BASE/v1/health"
printf "\n"
curl -fsS "$API_BASE/v1/system/status"
printf "\n"
curl -fsS "$API_BASE/v1/plugins"
printf "\n"

