#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

export STUDY_ANYTHING_DATA_DIR="${STUDY_ANYTHING_DATA_DIR:-$ROOT/data/skill-mode-demo}"
export API_PORT="${API_PORT:-8012}"
export STUDY_ANYTHING_RETRIEVAL_BACKEND="${STUDY_ANYTHING_RETRIEVAL_BACKEND:-memory}"
api_host="${SKILL_API_HOST:-127.0.0.1}"
export STUDY_ANYTHING_API_BASE="http://$api_host:$API_PORT"
export API_BASE="$STUDY_ANYTHING_API_BASE"

cleanup() {
  ./scripts/stop_skill_mode.sh >/dev/null 2>&1 || true
}

trap cleanup EXIT HUP INT TERM

printf "Starting disposable Study Anything Skill Mode at %s ...\n" "$STUDY_ANYTHING_API_BASE"
./scripts/launch_skill_mode.sh

venv_dir="${STUDY_ANYTHING_VENV:-$ROOT/.venv}"
if [ -x "$venv_dir/bin/python3" ]; then
  python_bin="$venv_dir/bin/python3"
elif [ -x "$venv_dir/bin/python" ]; then
  python_bin="$venv_dir/bin/python"
else
  python_bin="${PYTHON_BIN:-python3}"
fi

printf "Running deterministic Skill Mode CLI flow ...\n"
"$python_bin" scripts/verify_skill_cli_flow.py

printf "Verifying Agent eval artifact flow ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_agent_eval_flow.py

printf "Verifying Agent quality eval runner ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/run_external_agent_evals.py \
  --tool deepeval \
  --create-session \
  --allow-native-quality-fallback

printf "Verifying OpenAI-compatible gateway dry-run flow ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_openai_compatible_gateway.py

printf "Verifying platform-agent tool manifest ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_platform_agent_tools.py

printf "Verifying enriched platform lesson flow ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_platform_lesson_flow.py

printf "Verifying importer-based platform lesson flow ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_importer_lesson_flow.py

printf "Verifying importer runtime and retrieval flow ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_importer_runtime_retrieval_flow.py

printf "Verifying platform ecosystem eval flow ...\n"
API_BASE="$STUDY_ANYTHING_API_BASE" "$python_bin" scripts/verify_platform_ecosystem_eval_flow.py

printf "ok    Skill Mode demo completed. API was cleaned up.\n"
