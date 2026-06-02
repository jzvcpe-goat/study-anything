#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
data_dir="${STUDY_ANYTHING_DATA_DIR:-$ROOT/data/skill-mode}"
pid_file="$data_dir/api.pid"

if [ ! -f "$pid_file" ]; then
  printf "Study Anything Skill API is not running.\n"
  exit 0
fi

pid="$(cat "$pid_file")"
if kill -0 "$pid" >/dev/null 2>&1; then
  kill "$pid"
  printf "Stopped Study Anything Skill API process %s.\n" "$pid"
else
  printf "Removed stale Skill Mode PID file for process %s.\n" "$pid"
fi
rm -f "$pid_file"
