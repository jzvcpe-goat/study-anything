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

blocked_report_root="data/release-blocked-reports"
blocked_report_dir="${STUDY_ANYTHING_RELEASE_BLOCKED_REPORT_DIR:-$blocked_report_root/$$}"

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

redact_file() {
  while IFS= read -r line || [ -n "$line" ]; do
    redact_diagnostic "$line"
    printf "\n"
  done < "$1"
}

display_path() {
  value="$1"
  case "$value" in
    "$ROOT"/*)
      printf "%s" "${value#"$ROOT"/}"
      ;;
    /*)
      redact_diagnostic "$value"
      ;;
    *)
      redact_diagnostic "$value"
      ;;
  esac
}

display_python_bin() {
  display_path "$python_bin"
}

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  printf "error Python 3.11+ is required. Create a project virtualenv with:\n" >&2
  printf "  python3.11 -m venv .venv\n" >&2
  printf "  .venv/bin/python -m pip install -e .\n" >&2
  exit 1
fi

if ! "$python_bin" -c 'import fastapi' >/dev/null 2>&1; then
  printf "error API dependencies are missing for %s. Install them with:\n" "$(display_python_bin)" >&2
  printf "  %s -m pip install -e .\n" "$(display_python_bin)" >&2
  exit 1
fi

printf "Using Python runtime: %s\n" "$(display_python_bin)"

run_redacted() {
  redacted_log="${TMPDIR:-/tmp}/study-anything-release-redacted.$$.log"
  if "$@" >"$redacted_log" 2>&1; then
    redact_file "$redacted_log"
    rm -f "$redacted_log"
    return 0
  else
    status=$?
    redact_file "$redacted_log" >&2
    rm -f "$redacted_log"
    return "$status"
  fi
}

write_blocked_report() {
  name="$1"
  shift
  report_path="$blocked_report_dir/${name}.json"
  err_path="$blocked_report_dir/${name}.stderr"
  if "$@" >"$report_path" 2>"$err_path"; then
    rm -f "$err_path"
    printf "wrote blocked report: %s\n" "$(display_path "$report_path")" >&2
  else
    printf "warn  could not write blocked report: %s\n" "$(display_path "$report_path")" >&2
    if [ -s "$err_path" ]; then
      redact_file "$err_path" | sed 's/^/  /' >&2
    fi
  fi
}

write_contract_only_report() {
  name="$1"
  shift
  report_path="$blocked_report_dir/${name}.json"
  err_path="$blocked_report_dir/${name}.stderr"
  if "$@" >"$report_path" 2>"$err_path"; then
    rm -f "$err_path"
    printf "wrote contract-only report: %s\n" "$(display_path "$report_path")" >&2
  else
    status=$?
    redacted_err_path="$blocked_report_dir/${name}.stderr.redacted"
    redact_file "$err_path" >"$redacted_err_path"
    "$python_bin" - "$report_path" "$name" "$status" "$redacted_err_path" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import sys

report_path = Path(sys.argv[1])
contract_name = sys.argv[2]
exit_code = int(sys.argv[3])
diagnostic = Path(sys.argv[4]).read_text(encoding="utf-8", errors="replace")[:4000]
report_path.write_text(
    json.dumps(
        {
            "schema_version": "release-contract-only-report-v1",
            "status": "failed",
            "contract": contract_name,
            "exit_code": exit_code,
            "diagnostic": diagnostic,
            "runtime_gate_replaced": False,
            "privacy": {
                "redacted": True,
                "absolute_paths_returned": False,
                "raw_secrets_returned": False,
            },
        },
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
    rm -f "$err_path" "$redacted_err_path"
    printf "warn  contract-only report failed: %s\n" "$(display_path "$report_path")" >&2
  fi
}

write_blocked_report_readme() {
  readme_path="$blocked_report_dir/README.txt"
  cat >"$readme_path" <<EOF
Study Anything localhost-blocked release reports

release_check.sh generated this directory because the current runner could not
open localhost listening sockets. This often happens inside AI platform
sandboxes, while a normal terminal on the same machine can still run the gate.

Files in this directory are machine-readable, redacted environment-blocked
reports. They do not prove the runtime behavior; they classify the current
runner limitation and preserve the strict release gate failure.

When possible, release_check.sh also writes *.contract-only.json reports. Those
reports prove no-socket gateway/adapter contracts inside the current sandbox,
but they still do not replace the normal localhost runtime gates.

When release_check.sh later completes successfully with the default report
location, it clears stale localhost-blocked report directories automatically.

Next steps:
1. Rerun ./scripts/release_check.sh from a normal terminal or host shell.
2. If you need to prove no-socket contracts inside this sandbox first, run:
   $(display_python_bin) scripts/verify_openai_compatible_gateway.py --contract-only
   $(display_python_bin) scripts/verify_agent_gateway_hardening.py --contract-only
   $(display_python_bin) scripts/verify_external_agent_adapter_hardening.py --contract-only
3. If you still need a blocked report, rerun:
   STUDY_ANYTHING_RELEASE_BLOCKED_REPORT_DIR=$(display_path "$blocked_report_dir") ./scripts/release_check.sh
4. For environment diagnostics, run:
   $(display_python_bin) scripts/diagnose_adoption.py
5. After inspecting these local reports, clear only this report directory with:
   $(display_python_bin) scripts/diagnose_adoption.py --release-report-dir $(display_path "$blocked_report_dir") --clear-release-blocked-reports
EOF
  printf "wrote blocked report guide: %s\n" "$(display_path "$readme_path")" >&2
}

collect_localhost_block_reports() {
  mkdir -p "$blocked_report_dir"
  printf "Collecting localhost-blocked reports in: %s\n" "$(display_path "$blocked_report_dir")" >&2
  write_blocked_report \
    "external-adoption.localhost-blocked" \
    "$python_bin" scripts/verify_external_adoption.py \
      --pack platform/generated/study-anything-platform-adoption-pack.zip \
      --current-worktree \
      --allow-localhost-block-report
  write_blocked_report \
    "agent-gateway-hardening.localhost-blocked" \
    "$python_bin" scripts/verify_agent_gateway_hardening.py \
      --allow-localhost-block-report
  write_blocked_report \
    "external-agent-adapter-hardening.localhost-blocked" \
    "$python_bin" scripts/verify_external_agent_adapter_hardening.py \
      --allow-localhost-block-report
  write_contract_only_report \
    "openai-compatible-gateway.contract-only" \
    "$python_bin" scripts/verify_openai_compatible_gateway.py \
      --contract-only
  write_contract_only_report \
    "agent-gateway-hardening.contract-only" \
    "$python_bin" scripts/verify_agent_gateway_hardening.py \
      --contract-only
  write_contract_only_report \
    "external-agent-adapter-hardening.contract-only" \
    "$python_bin" scripts/verify_external_agent_adapter_hardening.py \
      --contract-only
  write_blocked_report_readme
}

cleanup_successful_blocked_reports() {
  if [ -n "${STUDY_ANYTHING_RELEASE_BLOCKED_REPORT_DIR:-}" ]; then
    printf "info  keeping explicitly configured blocked report directory: %s\n" "$(display_path "$blocked_report_dir")"
    return
  fi
  if [ -d "$blocked_report_root" ]; then
    rm -rf "$blocked_report_root"
    printf "ok    cleared stale localhost-blocked reports after successful release check: %s\n" "$(display_path "$blocked_report_root")"
  fi
}

print_localhost_gate_hint() {
  label="$1"
  printf "\n%s appears blocked by the local runtime environment.\n" "$label" >&2
  printf "This release gate remains strict and will exit non-zero here.\n" >&2
  printf "release_check.sh attempted to collect machine-readable blocked reports in:\n" >&2
  printf "  %s\n" "$(display_path "$blocked_report_dir")" >&2
  printf "The default report directory is under ignored data/ so local users can find it without polluting Git.\n" >&2
  printf "It also attempted to write *.contract-only.json no-socket reports there; these do not replace runtime gates.\n" >&2
  printf "If you are running inside an AI platform sandbox that blocks localhost sockets, collect a machine-readable blocked report with:\n" >&2
  printf "  %s scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --current-worktree --allow-localhost-block-report\n" "$(display_python_bin)" >&2
  printf "  %s scripts/verify_agent_gateway_hardening.py --allow-localhost-block-report\n" "$(display_python_bin)" >&2
  printf "  %s scripts/verify_external_agent_adapter_hardening.py --allow-localhost-block-report\n" "$(display_python_bin)" >&2
  printf "To prove no-socket gateway/adapter contracts before leaving the sandbox, run:\n" >&2
  printf "  %s scripts/verify_openai_compatible_gateway.py --contract-only\n" "$(display_python_bin)" >&2
  printf "  %s scripts/verify_agent_gateway_hardening.py --contract-only\n" "$(display_python_bin)" >&2
  printf "  %s scripts/verify_external_agent_adapter_hardening.py --contract-only\n" "$(display_python_bin)" >&2
  printf "Then rerun release_check.sh from a normal terminal or host shell that permits localhost listening sockets.\n" >&2
  printf "For redacted environment diagnostics, run:\n" >&2
  printf "  %s scripts/diagnose_adoption.py\n" "$(display_python_bin)" >&2
  printf "After inspecting this local report directory, clear the stale warning with:\n" >&2
  printf "  %s scripts/diagnose_adoption.py --release-report-dir %s --clear-release-blocked-reports\n" "$(display_python_bin)" "$(display_path "$blocked_report_dir")" >&2
}

run_localhost_sensitive_gate() {
  label="$1"
  shift
  gate_log="${TMPDIR:-/tmp}/study-anything-release-${label}.$$.log"
  if "$@" >"$gate_log" 2>&1; then
    redact_file "$gate_log"
    rm -f "$gate_log"
    return 0
  else
    status=$?
  fi
  redact_file "$gate_log" >&2
  if grep -qi "localhost\\|127\\.0\\.0\\.1\\|operation not permitted\\|permission denied\\|listening sockets\\|cannot allocate a local port" "$gate_log"; then
    collect_localhost_block_reports
    print_localhost_gate_hint "$label"
  fi
  rm -f "$gate_log"
  return "$status"
}

tmp_env="${TMPDIR:-/tmp}/study-anything-release.env"
run_redacted "$python_bin" scripts/setup_env.py --force --output "$tmp_env"
run_redacted "$python_bin" scripts/check_env.py --env "$tmp_env" --strict
if [ -f .env ]; then
  run_redacted "$python_bin" scripts/check_env.py
fi
"$python_bin" -m compileall -q apps/api/study_anything scripts plugins
run_localhost_sensitive_gate openai_compatible_gateway "$python_bin" scripts/verify_openai_compatible_gateway.py --gateway-only || exit $?
run_localhost_sensitive_gate agent_gateway_hardening "$python_bin" scripts/verify_agent_gateway_hardening.py || exit $?
run_localhost_sensitive_gate external_agent_adapter_hardening "$python_bin" scripts/verify_external_agent_adapter_hardening.py || exit $?
"$python_bin" scripts/verify_notebooklm_obsidian_bridge_hardening.py
"$python_bin" scripts/verify_learning_enrichment_bridge.py --check
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
"$python_bin" scripts/generate_platform_support_bundle_replay.py --check
"$python_bin" scripts/verify_platform_support_bundle_replay.py --check
"$python_bin" scripts/replay_support_bundle.py \
  --bundle fixtures/platform-support-bundles/local-ghcr-pull-timeout.json \
  --expect-classification local_ghcr_pull_timeout
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

cleanup_successful_blocked_reports
printf "ok    release check completed\n"
