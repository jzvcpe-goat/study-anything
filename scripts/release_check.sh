#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

printf "Study Anything release check\n"
printf "============================\n"

python_bin="${STUDY_ANYTHING_PYTHON:-}"
if [ -z "$python_bin" ]; then
  if [ -x .venv/bin/python ]; then
    python_bin=".venv/bin/python"
  else
    python_bin="python3"
  fi
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  printf "error Python 3.11+ is required. Create a project virtualenv with:\n" >&2
  printf "  python3.11 -m venv .venv\n" >&2
  printf "  .venv/bin/python -m pip install -e .\n" >&2
  exit 1
fi

if ! "$python_bin" -c 'import fastapi' >/dev/null 2>&1; then
  printf "error API dependencies are missing for %s. Install them with:\n" "$python_bin" >&2
  printf "  %s -m pip install -e .\n" "$python_bin" >&2
  exit 1
fi

printf "Using Python runtime: %s\n" "$python_bin"

tmp_env="${TMPDIR:-/tmp}/study-anything-release.env"
"$python_bin" scripts/setup_env.py --force --output "$tmp_env"
"$python_bin" scripts/check_env.py --env "$tmp_env" --strict
if [ -f .env ]; then
  "$python_bin" scripts/check_env.py
fi
"$python_bin" -m compileall -q apps/api/study_anything scripts plugins
"$python_bin" scripts/verify_cognitive_loop_contracts.py --check
"$python_bin" scripts/verify_cognitive_loop_cli.py --check
"$python_bin" scripts/verify_cognitive_loop_run_once.py --check
"$python_bin" scripts/verify_openai_compatible_gateway.py --gateway-only
"$python_bin" scripts/verify_agent_gateway_hardening.py
"$python_bin" scripts/verify_external_agent_adapter_hardening.py
"$python_bin" scripts/verify_notebooklm_obsidian_bridge_hardening.py
"$python_bin" scripts/verify_learning_enrichment_bridge.py --check
"$python_bin" scripts/verify_multiteacher_agent_eval_hardening.py
"$python_bin" scripts/verify_plugin_quarantine.py
"$python_bin" scripts/verify_security_recovery_hardening.py
"$python_bin" scripts/verify_platform_submission_dry_run.py --check
"$python_bin" scripts/verify_platform_manual_submission_rehearsal.py --check
"$python_bin" scripts/verify_first_lesson_authoring_kit.py --check
"$python_bin" scripts/verify_external_eval_marketplace_harness.py --check
"$python_bin" scripts/verify_agent_eval_marketplace_enforcement.py --check
"$python_bin" scripts/verify_platform_adoption_feedback_diagnostics.py --check
"$python_bin" scripts/generate_platform_feedback_package.py --check
"$python_bin" scripts/generate_platform_field_rehearsal.py --check
"$python_bin" scripts/verify_platform_field_rehearsal.py --check
"$python_bin" scripts/generate_platform_support_triage.py --check
"$python_bin" scripts/verify_platform_support_triage.py --check
"$python_bin" scripts/generate_platform_onboarding_readiness.py --check
"$python_bin" scripts/verify_platform_onboarding_readiness.py --check
"$python_bin" scripts/generate_platform_public_support_status.py --check
"$python_bin" scripts/verify_platform_public_support_status.py --check
"$python_bin" scripts/generate_published_image_evidence.py --check
"$python_bin" scripts/verify_published_image_evidence.py --check
"$python_bin" scripts/generate_release_asset_adoption.py --check
"$python_bin" scripts/verify_release_asset_adoption.py \
  --fixture fixtures/release-asset-adoption/asset-only-pass.json \
  --asset-dir platform/generated \
  --runtime metadata-only
"$python_bin" scripts/generate_release_asset_bootstrap.py --check
"$python_bin" scripts/bootstrap_from_release.py \
  --fixture fixtures/release-asset-adoption/asset-only-pass.json \
  --asset-dir platform/generated \
  --runtime metadata-only
"$python_bin" scripts/generate_platform_agent_replay.py --check
"$python_bin" scripts/replay_platform_agent_from_release.py \
  --fixture fixtures/release-asset-adoption/asset-only-pass.json \
  --asset-dir platform/generated \
  --platform kimi \
  --runtime metadata-only
"$python_bin" scripts/generate_adopter_evidence_archive.py --check
"$python_bin" scripts/verify_adopter_evidence_archive.py --check
"$python_bin" scripts/verify_plugin_ecosystem_adoption_kit.py --check
"$python_bin" scripts/verify_deployment_hardening.py --check
"$python_bin" scripts/generate_platform_agent_assets.py --check
"$python_bin" scripts/verify_commercial_readiness.py
"$python_bin" scripts/verify_adoption_telemetry.py
"$python_bin" scripts/verify_ecosystem_submission_pack.py
"$python_bin" scripts/verify_platform_ecosystem_packs.py
"$python_bin" scripts/generate_platform_bundle_manifest.py --check
"$python_bin" scripts/verify_platform_operator_drill.py --check
"$python_bin" scripts/generate_platform_adoption_pack.py --check
"$python_bin" scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --current-worktree \
  --python "$python_bin"
"$python_bin" scripts/verify_agent_eval_assets.py
"$python_bin" scripts/verify_agent_eval_baseline.py --check
"$python_bin" scripts/verify_clean_clone_adoption.py --repo . --copy-worktree
"$python_bin" scripts/diagnose_adoption.py --ghcr-timeout-seconds 5
"$python_bin" -m unittest discover apps/api/tests
"$python_bin" scripts/smoke_core.py
STUDY_ANYTHING_DATA_DIR="${TMPDIR:-/tmp}/study-anything-release-skill-mode" \
  STUDY_ANYTHING_RETRIEVAL_BACKEND=memory \
  ./scripts/run_skill_mode_demo.sh

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose --env-file "$tmp_env" -f infra/compose/docker-compose.yml --profile full config >/dev/null
else
  printf "warn  docker compose missing; skipped Compose config validation.\n"
fi

printf "hint  after launching Docker Compose, run: API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py\n"

printf "ok    release check completed\n"
