#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

dual_loop_only="${DUAL_LOOP_ONLY:-0}"
cbb_protocol_only="${CBB_PROTOCOL_ONLY:-0}"
skip_clean_clone="${SKIP_CLEAN_CLONE:-0}"
receipt_path=".cognitive-loop/artifacts/release/release-check-receipt.json"
receipt_written="false"
full_release_check_completed="false"
clean_clone_completed="false"
dependency_install_completed="false"
dual_loop_verifiers_integrated="true"
dual_loop_verifiers_passed_individually="false"
llm_depth_verifiers_integrated="true"
llm_depth_verifiers_passed_individually="false"
real_agent_eval_verifiers_integrated="true"
real_agent_eval_verifiers_passed_individually="false"
delivery_trust_verifiers_integrated="true"
delivery_trust_verifiers_passed_individually="false"
customer_handoff_verifiers_integrated="true"
customer_handoff_verifiers_passed_individually="false"
cbb_protocol_verifiers_integrated="true"
cbb_protocol_verifiers_passed_individually="false"
known_issue="none"
claim_boundary="Full release validation has not completed yet."
PIP_INSTALL_TIMEOUT_SECONDS="${PIP_INSTALL_TIMEOUT_SECONDS:-900}"
PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-60}"
PIP_RETRIES="${PIP_RETRIES:-3}"

usage() {
  cat <<'EOF'
Usage: ./scripts/release_check.sh [--dual-loop-only] [--cbb-protocol-only] [--skip-clean-clone]

Modes:
  --dual-loop-only   Run only the Dual-Loop verifier gates. This is NOT full release validation.
  --cbb-protocol-only Run only the CBB protocol verifier gates. This is NOT full release validation.
  --skip-clean-clone Run all local gates except clean-clone adoption. This is NOT full release validation.

Environment:
  DUAL_LOOP_ONLY=1
  CBB_PROTOCOL_ONLY=1
  SKIP_CLEAN_CLONE=1
  PIP_INSTALL_TIMEOUT_SECONDS=900
  PIP_DEFAULT_TIMEOUT=60
  PIP_RETRIES=3
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dual-loop-only)
      dual_loop_only="1"
      ;;
    --cbb-protocol-only)
      cbb_protocol_only="1"
      ;;
    --skip-clean-clone)
      skip_clean_clone="1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf "error unknown release_check option: %s\n" "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

is_enabled() {
  case "$1" in
    1|true|TRUE|yes|YES|on|ON)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

dual_loop_only_enabled="false"
cbb_protocol_only_enabled="false"
skip_clean_clone_enabled="false"
if is_enabled "$dual_loop_only"; then
  dual_loop_only_enabled="true"
  skip_clean_clone_enabled="true"
  known_issue="dual-loop-only partial validation mode requested"
  claim_boundary="Partial verification only: do not claim full release_check.sh passed."
fi
if is_enabled "$cbb_protocol_only"; then
  cbb_protocol_only_enabled="true"
  skip_clean_clone_enabled="true"
  known_issue="cbb-protocol-only partial validation mode requested"
  claim_boundary="Partial verification only: do not claim full release_check.sh passed."
fi
if is_enabled "$skip_clean_clone"; then
  skip_clean_clone_enabled="true"
  if [ "$dual_loop_only_enabled" != "true" ] && [ "$cbb_protocol_only_enabled" != "true" ]; then
    known_issue="clean-clone adoption phase skipped by operator request"
    claim_boundary="Partial verification only: clean-clone adoption was skipped, so do not claim full release_check.sh passed."
  fi
fi

phase() {
  printf "\n== Phase: %s ==\n" "$1"
}

validate_positive_int() {
  name="$1"
  value="$2"
  case "$value" in
    ""|*[!0-9]*)
      printf "error %s must be a positive integer, got: %s\n" "$name" "$value" >&2
      exit 2
      ;;
  esac
  if [ "$value" -lt 1 ] 2>/dev/null; then
    printf "error %s must be a positive integer, got: %s\n" "$name" "$value" >&2
    exit 2
  fi
}

json_bool() {
  if [ "$1" = "true" ]; then
    printf "True"
  else
    printf "False"
  fi
}

write_release_receipt() {
  rc="$1"
  if [ "$receipt_written" = "true" ]; then
    return 0
  fi
  if [ "$rc" -ne 0 ] && [ "$known_issue" = "none" ]; then
    known_issue="release_check.sh failed or was interrupted before every phase completed"
    claim_boundary="Failed or partial verification only: do not claim full release_check.sh passed."
  fi
  mkdir -p "$(dirname "$receipt_path")"
  receipt_python="${python_bin:-python3}"
  "$receipt_python" - "$receipt_path" <<PY
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "schema_version": "release-check-receipt-v1",
    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "status": "completed" if int("$rc") == 0 else "failed",
    "exit_code": int("$rc"),
    "full_release_check_completed": $(json_bool "$full_release_check_completed"),
    "clean_clone_completed": $(json_bool "$clean_clone_completed"),
    "dependency_install_completed": $(json_bool "$dependency_install_completed"),
    "dual_loop_verifiers_integrated": $(json_bool "$dual_loop_verifiers_integrated"),
    "dual_loop_verifiers_passed_individually": $(json_bool "$dual_loop_verifiers_passed_individually"),
    "llm_depth_verifiers_integrated": $(json_bool "$llm_depth_verifiers_integrated"),
    "llm_depth_verifiers_passed_individually": $(json_bool "$llm_depth_verifiers_passed_individually"),
    "real_agent_eval_verifiers_integrated": $(json_bool "$real_agent_eval_verifiers_integrated"),
    "real_agent_eval_verifiers_passed_individually": $(json_bool "$real_agent_eval_verifiers_passed_individually"),
    "delivery_trust_verifiers_integrated": $(json_bool "$delivery_trust_verifiers_integrated"),
    "delivery_trust_verifiers_passed_individually": $(json_bool "$delivery_trust_verifiers_passed_individually"),
    "customer_handoff_verifiers_integrated": $(json_bool "$customer_handoff_verifiers_integrated"),
    "customer_handoff_verifiers_passed_individually": $(json_bool "$customer_handoff_verifiers_passed_individually"),
    "cbb_protocol_verifiers_integrated": $(json_bool "$cbb_protocol_verifiers_integrated"),
    "cbb_protocol_verifiers_passed_individually": $(json_bool "$cbb_protocol_verifiers_passed_individually"),
    "partial_modes": {
        "dual_loop_only": $(json_bool "$dual_loop_only_enabled"),
        "cbb_protocol_only": $(json_bool "$cbb_protocol_only_enabled"),
        "skip_clean_clone": $(json_bool "$skip_clean_clone_enabled"),
    },
    "dependency_install_bounds": {
        "pip_install_timeout_seconds": int("$PIP_INSTALL_TIMEOUT_SECONDS"),
        "pip_default_timeout": int("$PIP_DEFAULT_TIMEOUT"),
        "pip_retries": int("$PIP_RETRIES"),
    },
    "known_issue": "$known_issue",
    "claim_boundary": "$claim_boundary",
    "privacy": {
        "metadata_only": True,
        "raw_logs_included": False,
        "local_absolute_paths_included": False,
        "real_secrets_included": False,
        "model_calls_performed": False,
        "production_mutation_performed": False,
    },
}
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  receipt_written="true"
}

on_exit() {
  rc="$?"
  if [ "$receipt_written" != "true" ]; then
    phase "release receipt summary"
    write_release_receipt "$rc"
    printf "release receipt: %s\n" "$receipt_path"
    if [ "$rc" -ne 0 ]; then
      printf "release check did not complete; see receipt claim_boundary.\n" >&2
    fi
  fi
  exit "$rc"
}
trap on_exit EXIT

run_dual_loop_verifier_gates() {
  phase "Dual-Loop verifier gates"
  "$python_bin" scripts/verify_dual_loop_contracts.py --check
  "$python_bin" scripts/verify_failure_sandbox_lite.py --check
  "$python_bin" scripts/verify_attention_reconstruction_lite.py --check
  "$python_bin" scripts/verify_dual_loop_gate.py --check
  "$python_bin" scripts/verify_delivery_trust_receipt.py --check
  "$python_bin" scripts/verify_customer_handoff_package.py --check
  "$python_bin" scripts/verify_delivery_trust_case_harness.py --check
  "$python_bin" scripts/generate_delivery_trust_case_pack.py --check
  "$python_bin" scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py --check
  "$python_bin" scripts/verify_code_review_delivery_class_handoff.py --check
  "$python_bin" scripts/verify_client_report_delivery_class_handoff.py --check
  "$python_bin" scripts/verify_support_response_delivery_class_handoff.py --check
  "$python_bin" scripts/verify_delivery_class_registry.py --check
  "$python_bin" scripts/verify_trust_scenario_catalog.py --check
  "$python_bin" scripts/verify_trust_scenario_decision_gate.py --check
  "$python_bin" scripts/generate_trust_evidence_handoff_pack.py --check
  "$python_bin" scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py --check
  "$python_bin" scripts/verify_trust_evidence_acceptance_drill.py --check
  "$python_bin" scripts/verify_controlled_handoff_runbook.py --check
  "$python_bin" scripts/verify_customer_delivery_trust_envelope.py --check
  "$python_bin" scripts/verify_customer_delivery_rehearsal.py --check
  "$python_bin" scripts/verify_code_review_operator_handoff_rehearsal.py --check
  "$python_bin" scripts/verify_client_report_operator_handoff_rehearsal.py --check
  "$python_bin" scripts/verify_support_response_operator_handoff_rehearsal.py --check
  "$python_bin" scripts/verify_operator_handoff_rehearsal_contract.py --check
  "$python_bin" scripts/verify_external_feedback_receipt.py --check
  "$python_bin" scripts/verify_external_feedback_backlog_bridge.py --check
  "$python_bin" scripts/verify_product_owner_prioritization_gate.py --check
  "$python_bin" scripts/verify_product_spec_eval_authoring_gate.py --check
  "$python_bin" scripts/verify_product_loop_brief_intake.py --check
  "$python_bin" scripts/verify_end_to_end_trust_chain_harness.py --check
  "$python_bin" scripts/verify_real_adopter_scenario_import.py --check
  "$python_bin" scripts/verify_spec_eval_scenario_execution_rehearsal.py --check
  "$python_bin" scripts/verify_sandboxed_patch_proposal_rehearsal.py --check
  "$python_bin" scripts/verify_patch_proposal_operator_handoff_bridge.py --check
  "$python_bin" scripts/verify_patch_proposal_acceptance_drill.py --check
  "$python_bin" scripts/verify_patch_proposal_external_work_order_pack.py --check
  "$python_bin" scripts/verify_patch_proposal_external_operator_completion.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_delivery_envelope.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_delivery_rehearsal.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_delivery_outcome_receipt.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_feedback_intake_receipt.py --check
  "$python_bin" scripts/verify_dual_loop_scenario_harness.py --check
  "$python_bin" scripts/generate_dual_loop_trust_scenario_pack.py --check
  "$python_bin" scripts/verify_dual_loop_trust_scenario_pack.py --check
  "$python_bin" scripts/verify_dual_loop_trust_pack_consumer_walkthrough.py --check
  dual_loop_verifiers_passed_individually="true"
  delivery_trust_verifiers_passed_individually="true"
  customer_handoff_verifiers_passed_individually="true"
}

run_cbb_protocol_verifier_gates() {
  phase "CBB protocol verifier gates"
  "$python_bin" scripts/verify_cbb_protocol_contracts.py --check
  "$python_bin" scripts/verify_cbb_gate.py --check
  "$python_bin" scripts/verify_cbb_receipt_chain.py --check
  "$python_bin" scripts/verify_cbb_self_intake.py --check
  "$python_bin" scripts/verify_cbb_delivery_harness.py --check
  "$python_bin" scripts/verify_product_loop_harness.py --check
  "$python_bin" scripts/verify_delivery_trust_case_harness.py --check
  "$python_bin" scripts/generate_delivery_trust_case_pack.py --check
  "$python_bin" scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py --check
  "$python_bin" scripts/verify_code_review_delivery_class_handoff.py --check
  "$python_bin" scripts/verify_client_report_delivery_class_handoff.py --check
  "$python_bin" scripts/verify_support_response_delivery_class_handoff.py --check
  "$python_bin" scripts/verify_delivery_class_registry.py --check
  "$python_bin" scripts/verify_trust_scenario_catalog.py --check
  "$python_bin" scripts/verify_trust_scenario_decision_gate.py --check
  "$python_bin" scripts/generate_trust_evidence_handoff_pack.py --check
  "$python_bin" scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py --check
  "$python_bin" scripts/verify_trust_evidence_acceptance_drill.py --check
  "$python_bin" scripts/verify_controlled_handoff_runbook.py --check
  "$python_bin" scripts/verify_customer_delivery_trust_envelope.py --check
  "$python_bin" scripts/verify_customer_delivery_rehearsal.py --check
  "$python_bin" scripts/verify_code_review_operator_handoff_rehearsal.py --check
  "$python_bin" scripts/verify_client_report_operator_handoff_rehearsal.py --check
  "$python_bin" scripts/verify_support_response_operator_handoff_rehearsal.py --check
  "$python_bin" scripts/verify_operator_handoff_rehearsal_contract.py --check
  "$python_bin" scripts/verify_external_feedback_receipt.py --check
  "$python_bin" scripts/verify_external_feedback_backlog_bridge.py --check
  "$python_bin" scripts/verify_product_owner_prioritization_gate.py --check
  "$python_bin" scripts/verify_product_spec_eval_authoring_gate.py --check
  "$python_bin" scripts/verify_product_loop_brief_intake.py --check
  "$python_bin" scripts/verify_end_to_end_trust_chain_harness.py --check
  "$python_bin" scripts/verify_real_adopter_scenario_import.py --check
  "$python_bin" scripts/verify_spec_eval_scenario_execution_rehearsal.py --check
  "$python_bin" scripts/verify_sandboxed_patch_proposal_rehearsal.py --check
  "$python_bin" scripts/verify_patch_proposal_operator_handoff_bridge.py --check
  "$python_bin" scripts/verify_patch_proposal_acceptance_drill.py --check
  "$python_bin" scripts/verify_patch_proposal_external_work_order_pack.py --check
  "$python_bin" scripts/verify_patch_proposal_external_operator_completion.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_delivery_envelope.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_delivery_rehearsal.py --check
  "$python_bin" scripts/verify_patch_proposal_customer_delivery_outcome_receipt.py --check
  cbb_protocol_verifiers_passed_individually="true"
}

run_llm_depth_verifier_gates() {
  phase "LLM Depth verifier gates"
  "$python_bin" scripts/verify_llm_depth_risk_engine.py --check
  llm_depth_verifiers_passed_individually="true"
}

run_real_agent_eval_verifier_gates() {
  phase "Real-Agent eval bridge verifier gates"
  "$python_bin" scripts/verify_real_agent_eval_bridge.py --check
  "$python_bin" scripts/verify_workbuddy_real_agent_learning_quality.py --check
  real_agent_eval_verifiers_passed_individually="true"
}

printf "Study Anything release check\n"
printf "============================\n"
if [ "$dual_loop_only_enabled" = "true" ]; then
  printf "mode  dual-loop-only partial verification; this is NOT full release validation.\n"
elif [ "$cbb_protocol_only_enabled" = "true" ]; then
  printf "mode  cbb-protocol-only partial verification; this is NOT full release validation.\n"
elif [ "$skip_clean_clone_enabled" = "true" ]; then
  printf "mode  skip-clean-clone partial verification; this is NOT full release validation.\n"
else
  printf "mode  full release validation\n"
fi

validate_positive_int PIP_INSTALL_TIMEOUT_SECONDS "$PIP_INSTALL_TIMEOUT_SECONDS"
validate_positive_int PIP_DEFAULT_TIMEOUT "$PIP_DEFAULT_TIMEOUT"
validate_positive_int PIP_RETRIES "$PIP_RETRIES"

python_bin="${STUDY_ANYTHING_PYTHON:-}"
if [ -z "$python_bin" ]; then
  if [ -x .venv/bin/python ]; then
    python_bin=".venv/bin/python"
  else
    python_bin="python3"
  fi
fi

phase "repository sanity"
printf "Using Python runtime: %s\n" "$python_bin"
if [ "$dual_loop_only_enabled" = "true" ]; then
  printf "partial  skipping FastAPI/full dependency sanity; running Dual-Loop and CBB protocol gates only.\n"
  run_dual_loop_verifier_gates
  run_cbb_protocol_verifier_gates
  phase "release receipt summary"
  write_release_receipt 0
  printf "release receipt: %s\n" "$receipt_path"
  printf "ok    Dual-Loop-only partial verification completed; full release validation was not run.\n"
  trap - EXIT
  exit 0
fi

if [ "$cbb_protocol_only_enabled" = "true" ]; then
  printf "partial  skipping FastAPI/full dependency sanity; running CBB protocol gates only.\n"
  run_cbb_protocol_verifier_gates
  phase "release receipt summary"
  write_release_receipt 0
  printf "release receipt: %s\n" "$receipt_path"
  printf "ok    CBB-protocol-only partial verification completed; full release validation was not run.\n"
  trap - EXIT
  exit 0
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  printf "error Python 3.11+ is required. Create a project virtualenv with:\n" >&2
  printf "  python3.11 -m venv .venv\n" >&2
  printf "  .venv/bin/python -m pip install -e '.[dev,full]'\n" >&2
  exit 1
fi

if ! "$python_bin" -c 'import fastapi' >/dev/null 2>&1; then
  printf "error API dependencies are missing for %s. Install them with:\n" "$python_bin" >&2
  printf "  %s -m pip install -e '.[dev,full]'\n" "$python_bin" >&2
  exit 1
fi

tmp_env="${TMPDIR:-/tmp}/study-anything-release.env"
"$python_bin" scripts/setup_env.py --force --output "$tmp_env"
"$python_bin" scripts/check_env.py --env "$tmp_env" --strict
if [ -f .env ]; then
  "$python_bin" scripts/check_env.py
fi
"$python_bin" -m compileall -q apps/api/study_anything scripts plugins

phase "clean-clone setup"
if [ "$skip_clean_clone_enabled" = "true" ]; then
  printf "skip  clean-clone setup skipped; this is NOT full release validation.\n"
else
  printf "ok    clean-clone setup will run in a disposable worktree.\n"
fi

phase "dependency install"
if [ "$skip_clean_clone_enabled" = "true" ]; then
  printf "skip  dependency install skipped with clean-clone; this is NOT full release validation.\n"
else
  printf "pip   bounded install timeout=%ss default-timeout=%ss retries=%s\n" \
    "$PIP_INSTALL_TIMEOUT_SECONDS" "$PIP_DEFAULT_TIMEOUT" "$PIP_RETRIES"
  PIP_INSTALL_TIMEOUT_SECONDS="$PIP_INSTALL_TIMEOUT_SECONDS" \
    SKILL_PIP_INSTALL_TIMEOUT_SECONDS="${SKILL_PIP_INSTALL_TIMEOUT_SECONDS:-$PIP_INSTALL_TIMEOUT_SECONDS}" \
    PIP_DEFAULT_TIMEOUT="$PIP_DEFAULT_TIMEOUT" \
    PIP_RETRIES="$PIP_RETRIES" \
    "$python_bin" scripts/verify_clean_clone_adoption.py \
    --repo . \
    --copy-worktree \
    --timeout-seconds "${STUDY_ANYTHING_CLEAN_CLONE_TIMEOUT_SECONDS:-1800}"
  clean_clone_completed="true"
  dependency_install_completed="true"
fi

phase "existing release gates"
"$python_bin" scripts/verify_cognitive_loop_contracts.py --check
"$python_bin" scripts/verify_operating_model_loops.py --check
"$python_bin" scripts/verify_release_stack_policy.py --check
"$python_bin" scripts/verify_cognitive_loop_cli.py --check
"$python_bin" scripts/verify_cognitive_loop_run_once.py --check
"$python_bin" scripts/verify_cognitive_loop_snapshot.py --check
"$python_bin" scripts/verify_cognitive_loop_human_gate.py --check
"$python_bin" scripts/verify_cognitive_loop_evidence_bundle.py --check
"$python_bin" scripts/verify_cognitive_loop_event_index.py --check
"$python_bin" scripts/verify_cognitive_loop_event_store.py --check
"$python_bin" scripts/verify_cognitive_loop_watcher_ingest.py --check
"$python_bin" scripts/verify_cognitive_loop_watcher_runner.py --check
"$python_bin" scripts/verify_cognitive_loop_mastra_adapter.py --check
"$python_bin" scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check
"$python_bin" scripts/verify_cognitive_loop_mastra_runtime_service.py --check
"$python_bin" scripts/verify_cognitive_loop_mastra_runtime_durable.py --check
"$python_bin" scripts/verify_cognitive_loop_langfuse_observability.py --check
"$python_bin" scripts/verify_cognitive_loop_study_anything_adapter.py --check
"$python_bin" scripts/verify_cognitive_loop_study_adapter_cli.py --check
"$python_bin" scripts/verify_cognitive_loop_artifact_doctor.py --check
"$python_bin" scripts/verify_cognitive_loop_repair_plan.py --check
"$python_bin" scripts/verify_cognitive_loop_artifact_index.py --check
"$python_bin" scripts/verify_cognitive_loop_artifact_console.py --check
"$python_bin" scripts/verify_cognitive_loop_personal_plugin_mode.py --check
"$python_bin" scripts/verify_cognitive_loop_evolution_report.py --check
"$python_bin" scripts/verify_cognitive_loop_apply_plan.py --check
"$python_bin" scripts/verify_cognitive_loop_improvement_comparator.py --check
"$python_bin" scripts/verify_cognitive_loop_patch_proposal.py --check
"$python_bin" scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check
"$python_bin" scripts/verify_cognitive_loop_mastra_evolution_replay.py --check
"$python_bin" scripts/verify_cognitive_loop_patch_apply_sandbox.py --check
"$python_bin" scripts/verify_cognitive_loop_evolution_pack_export.py --check
"$python_bin" scripts/verify_cognitive_loop_evolution_pack_consumer.py --check
"$python_bin" scripts/verify_cognitive_loop_pr_ci_receipt.py --check
"$python_bin" scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check
"$python_bin" scripts/verify_cognitive_loop_review.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_prompt.py --check
"$python_bin" scripts/verify_llm_depth_risk_engine.py --check
"$python_bin" scripts/verify_real_agent_eval_bridge.py --check
"$python_bin" scripts/verify_workbuddy_real_agent_learning_quality.py --check
"$python_bin" scripts/verify_delivery_trust_receipt.py --check
"$python_bin" scripts/verify_customer_handoff_package.py --check
"$python_bin" scripts/verify_product_loop_harness.py --check
"$python_bin" scripts/verify_delivery_trust_case_harness.py --check
"$python_bin" scripts/generate_delivery_trust_case_pack.py --check
"$python_bin" scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py --check
"$python_bin" scripts/verify_code_review_delivery_class_handoff.py --check
"$python_bin" scripts/verify_client_report_delivery_class_handoff.py --check
"$python_bin" scripts/verify_support_response_delivery_class_handoff.py --check
"$python_bin" scripts/verify_delivery_class_registry.py --check
"$python_bin" scripts/verify_trust_scenario_catalog.py --check
"$python_bin" scripts/verify_trust_scenario_decision_gate.py --check
"$python_bin" scripts/generate_trust_evidence_handoff_pack.py --check
"$python_bin" scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py --check
"$python_bin" scripts/verify_trust_evidence_acceptance_drill.py --check
"$python_bin" scripts/verify_controlled_handoff_runbook.py --check
"$python_bin" scripts/verify_customer_delivery_trust_envelope.py --check
"$python_bin" scripts/verify_customer_delivery_rehearsal.py --check
"$python_bin" scripts/verify_code_review_operator_handoff_rehearsal.py --check
"$python_bin" scripts/verify_client_report_operator_handoff_rehearsal.py --check
"$python_bin" scripts/verify_support_response_operator_handoff_rehearsal.py --check
"$python_bin" scripts/verify_operator_handoff_rehearsal_contract.py --check
"$python_bin" scripts/verify_external_feedback_receipt.py --check
"$python_bin" scripts/verify_external_feedback_backlog_bridge.py --check
"$python_bin" scripts/verify_product_owner_prioritization_gate.py --check
"$python_bin" scripts/verify_product_spec_eval_authoring_gate.py --check
"$python_bin" scripts/verify_product_loop_brief_intake.py --check
"$python_bin" scripts/verify_end_to_end_trust_chain_harness.py --check
"$python_bin" scripts/verify_real_adopter_scenario_import.py --check
"$python_bin" scripts/verify_spec_eval_scenario_execution_rehearsal.py --check
"$python_bin" scripts/verify_sandboxed_patch_proposal_rehearsal.py --check
"$python_bin" scripts/verify_patch_proposal_operator_handoff_bridge.py --check
"$python_bin" scripts/verify_patch_proposal_acceptance_drill.py --check
"$python_bin" scripts/verify_patch_proposal_external_work_order_pack.py --check
"$python_bin" scripts/verify_patch_proposal_external_operator_completion.py --check
"$python_bin" scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --check
"$python_bin" scripts/verify_patch_proposal_customer_delivery_envelope.py --check
"$python_bin" scripts/verify_patch_proposal_customer_delivery_rehearsal.py --check
"$python_bin" scripts/verify_patch_proposal_customer_delivery_outcome_receipt.py --check
"$python_bin" scripts/verify_patch_proposal_customer_feedback_intake_receipt.py --check
"$python_bin" scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py --check
"$python_bin" scripts/generate_dual_loop_trust_scenario_pack.py --check
"$python_bin" scripts/verify_dual_loop_trust_scenario_pack.py --check
"$python_bin" scripts/verify_dual_loop_trust_pack_consumer_walkthrough.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_report.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_handoff_cli.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_eval_harness.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_policy_gate.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
"$python_bin" scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check
"$python_bin" scripts/verify_cognitive_loop_adoption_cookbook.py --check
"$python_bin" scripts/generate_cognitive_loop_adoption_recipes.py --check
"$python_bin" scripts/verify_cognitive_loop_recipe_replay.py --check
"$python_bin" scripts/verify_cognitive_loop_skill_entrypoint.py --check
"$python_bin" scripts/verify_cognitive_loop_recipe_cli.py --check
"$python_bin" scripts/verify_cognitive_loop_recipe_cli_receipts.py --check
"$python_bin" scripts/verify_cognitive_loop_recipe_cli_failures.py --check
"$python_bin" scripts/verify_cognitive_loop_recipe_cli_schemas.py --check
"$python_bin" scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py --check
"$python_bin" scripts/verify_openai_compatible_gateway.py --gateway-only
"$python_bin" scripts/verify_agent_gateway_hardening.py
"$python_bin" scripts/verify_external_agent_adapter_hardening.py
"$python_bin" scripts/verify_notebooklm_obsidian_bridge_hardening.py
"$python_bin" scripts/verify_learning_enrichment_bridge.py --check
"$python_bin" scripts/verify_okf_bundle.py --check
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
"$python_bin" scripts/verify_platform_handoff_checklist.py --check
"$python_bin" scripts/verify_launch_acceptance_ledger.py --check
"$python_bin" scripts/verify_github_launch_operator_guide.py --check
"$python_bin" scripts/verify_release_stack_readiness.py
"$python_bin" scripts/verify_release_stack_manifest_fixtures.py --check
"$python_bin" scripts/verify_release_stack_intake_candidate.py --check
"$python_bin" scripts/verify_release_stack_candidate_promotion.py --check
"$python_bin" scripts/generate_platform_plugin_packs.py --check
"$python_bin" scripts/verify_platform_plugin_packs.py --check
"$python_bin" scripts/generate_platform_plugin_downloads.py --check
"$python_bin" scripts/verify_platform_plugin_downloads.py --check
"$python_bin" scripts/generate_workbuddy_plugin_marketplace.py --check
"$python_bin" scripts/verify_workbuddy_plugin_marketplace.py --check
"$python_bin" scripts/generate_platform_bundle_manifest.py --check
"$python_bin" scripts/verify_platform_operator_drill.py --check
"$python_bin" scripts/generate_platform_adoption_pack.py --check
"$python_bin" scripts/verify_cognitive_loop_schema_pack_consumer.py --check
"$python_bin" scripts/verify_cognitive_loop_schema_pack_consumer_failures.py --check
"$python_bin" scripts/verify_cognitive_loop_pack_extract_smoke.py --check
"$python_bin" scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --current-worktree \
  --python "$python_bin"
"$python_bin" scripts/verify_agent_eval_assets.py
"$python_bin" scripts/verify_agent_eval_baseline.py --check

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

run_dual_loop_verifier_gates
run_cbb_protocol_verifier_gates
run_llm_depth_verifier_gates
run_real_agent_eval_verifier_gates

if [ "$skip_clean_clone_enabled" = "true" ]; then
  full_release_check_completed="false"
else
  full_release_check_completed="true"
  known_issue="none"
  claim_boundary="Full release_check.sh completed in this run; all phases reached release receipt summary."
fi

phase "release receipt summary"
write_release_receipt 0
printf "release receipt: %s\n" "$receipt_path"
printf "ok    release check completed\n"
trap - EXIT
