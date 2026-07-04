#!/usr/bin/env python3
"""Verify that release stack intake candidates were safely promoted into the manifest."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from verify_release_stack_intake_candidate import (
    SOURCE_SCHEMA_VERSION,
    normalize_checks,
    normalize_merge_commit,
    reject_private_text,
    reject_raw_payloads,
)
from verify_release_stack_readiness import (
    MANIFEST,
    REQUIRED_CHECKS,
    ROOT,
    VERSION,
    ReleaseStackReadinessError,
    current_group,
    load_json,
    verify_manifest,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-release-stack-candidate-promotion.json"
PR_SOURCES = {
    346: ROOT / "fixtures" / "release-stack" / "pr-346-intake-candidate.json",
}
REPORT_SCHEMA_VERSION = "release-stack-candidate-promotion-v1"
PROMOTED_GROUP_ID = "release-stack-promotion-v0.3.222"
PREVIOUS_CURRENT_GROUP_ID = "release-stack-promotion-v0.3.220"
GENERATED_AT = "2026-01-01T00:00:00Z"
SAFE_OPERATOR_COMMANDS = {
    "python3 scripts/verify_release_stack_readiness.py",
    "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
    "python3 scripts/verify_release_stack_intake_candidate.py --check",
    "python3 scripts/verify_release_stack_candidate_promotion.py --check",
    "python3 scripts/verify_release_stack_live_status.py",
    "python3 scripts/verify_release_stack_lineage.py",
    "python3 scripts/verify_release_stack_merge_runbook.py --report-only",
    "./scripts/release_check.sh",
}
POST_MERGE_EVIDENCE_REFS = [
    "platform/generated/study-anything-release-stack-intake-candidate.json",
    "platform/generated/study-anything-release-stack-manifest-fixtures.json",
    "platform/generated/study-anything-release-stack-candidate-promotion.json",
    "platform/generated/study-anything-platform-bundle.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "docs/external-feedback-receipt.md",
    "platform/schemas/delivery-trust/external-feedback-receipt-v1.schema.json",
    "platform/generated/study-anything-external-feedback-receipt.json",
    "platform/generated/study-anything-external-feedback-receipt.md",
    "platform/generated/study-anything-external-feedback-receipt.html",
    "scripts/external_feedback_receipt.py",
    "scripts/verify_external_feedback_receipt.py",
    "docs/external-feedback-backlog-bridge.md",
    "platform/schemas/delivery-trust/external-feedback-backlog-bridge-v1.schema.json",
    "platform/schemas/delivery-trust/product-loop-backlog-item-v1.schema.json",
    "platform/generated/study-anything-external-feedback-backlog-bridge.json",
    "platform/generated/study-anything-external-feedback-backlog-bridge.md",
    "platform/generated/study-anything-external-feedback-backlog-bridge.html",
    "scripts/external_feedback_backlog_bridge.py",
    "scripts/verify_external_feedback_backlog_bridge.py",
    "docs/product-owner-prioritization-gate.md",
    "platform/schemas/delivery-trust/product-owner-prioritization-receipt-v1.schema.json",
    "platform/schemas/delivery-trust/product-spec-eval-candidate-v1.schema.json",
    "platform/generated/study-anything-product-owner-prioritization-gate.json",
    "platform/generated/study-anything-product-owner-prioritization-gate.md",
    "platform/generated/study-anything-product-owner-prioritization-gate.html",
    "fixtures/product-owner-prioritization-gate/pass/product-owner-prioritization-receipt.json",
    "fixtures/product-owner-prioritization-gate/pass/product-spec-eval-candidate.json",
    "scripts/product_owner_prioritization_gate.py",
    "scripts/verify_product_owner_prioritization_gate.py",
    "docs/product-spec-eval-authoring-gate.md",
    "platform/schemas/delivery-trust/product-spec-eval-authoring-receipt-v1.schema.json",
    "platform/schemas/delivery-trust/product-spec-eval-brief-v1.schema.json",
    "platform/generated/study-anything-product-spec-eval-authoring-gate.json",
    "platform/generated/study-anything-product-spec-eval-authoring-gate.md",
    "platform/generated/study-anything-product-spec-eval-authoring-gate.html",
    "fixtures/product-spec-eval-authoring-gate/pass/product-spec-eval-authoring-receipt.json",
    "fixtures/product-spec-eval-authoring-gate/pass/product-spec-eval-brief.json",
    "scripts/product_spec_eval_authoring_gate.py",
    "scripts/verify_product_spec_eval_authoring_gate.py",
    "docs/product-loop-brief-intake.md",
    "platform/schemas/cbb/product-loop-brief-intake-receipt-v1.schema.json",
    "platform/generated/study-anything-product-loop-brief-intake.json",
    "platform/generated/study-anything-product-loop-brief-intake.md",
    "platform/generated/study-anything-product-loop-brief-intake.html",
    "fixtures/product-loop-brief-intake/pass/product-loop-brief-intake-receipt.json",
    "fixtures/product-loop-brief-intake/pass/product-loop-scenario.json",
    "fixtures/product-loop-brief-intake/pass/product-loop-run.json",
    "scripts/product_loop_brief_intake.py",
    "scripts/verify_product_loop_brief_intake.py",
    "platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json",
    "platform/generated/study-anything-operating-model-loops.json",
    "platform/generated/study-anything-cbb-receipt-chain.json",
    "platform/generated/study-anything-cbb-self-intake.json",
    "platform/generated/study-anything-cbb-delivery-scenario-harness.json",
    "platform/generated/study-anything-delivery-trust-case-harness.json",
    "platform/generated/study-anything-delivery-trust-case-pack.json",
    "platform/generated/study-anything-delivery-trust-case-pack-consumer-walkthrough.json",
    "platform/generated/study-anything-delivery-class-registry.json",
    "platform/generated/study-anything-delivery-class-registry.html",
    "docs/delivery-class-registry.md",
    "scripts/verify_delivery_class_registry.py",
    "platform/generated/study-anything-trust-scenario-catalog.json",
    "platform/generated/study-anything-trust-scenario-catalog.html",
    "docs/trust-scenario-catalog.md",
    "scripts/verify_trust_scenario_catalog.py",
    "platform/generated/study-anything-trust-scenario-decision-gate.json",
    "platform/generated/study-anything-trust-scenario-decision-gate.html",
    "docs/trust-scenario-decision-gate.md",
    "scripts/trust_scenario_decision_gate.py",
    "scripts/verify_trust_scenario_decision_gate.py",
    "docs/code-review-delivery-class.md",
    "docs/client-report-delivery-class.md",
    "docs/support-response-delivery-class.md",
    "platform/generated/study-anything-code-review-delivery-class.json",
    "platform/generated/study-anything-code-review-delivery-class.html",
    "platform/generated/study-anything-client-report-delivery-class.json",
    "platform/generated/study-anything-client-report-delivery-class.html",
    "platform/generated/study-anything-support-response-delivery-class.json",
    "platform/generated/study-anything-support-response-delivery-class.html",
    "platform/schemas/delivery-trust/code-review-handoff-case-v1.schema.json",
    "platform/schemas/delivery-trust/client-report-handoff-case-v1.schema.json",
    "platform/schemas/delivery-trust/support-response-handoff-case-v1.schema.json",
    "scripts/code_review_delivery_class_handoff.py",
    "scripts/verify_code_review_delivery_class_handoff.py",
    "scripts/client_report_delivery_class_handoff.py",
    "scripts/verify_client_report_delivery_class_handoff.py",
    "scripts/support_response_delivery_class_handoff.py",
    "scripts/verify_support_response_delivery_class_handoff.py",
    "docs/trust-evidence-handoff-pack.md",
    "platform/generated/study-anything-trust-evidence-handoff-pack.json",
    "platform/generated/study-anything-trust-evidence-handoff-pack.md",
    "platform/generated/study-anything-trust-evidence-handoff-pack.sha256",
    "platform/generated/study-anything-trust-evidence-handoff-pack.zip",
    "platform/generated/study-anything-trust-evidence-handoff-pack-consumer-walkthrough.json",
    "docs/trust-evidence-acceptance-drill.md",
    "platform/generated/study-anything-trust-evidence-acceptance-drill.json",
    "platform/generated/study-anything-trust-evidence-acceptance-drill.md",
    "docs/controlled-handoff-runbook.md",
    "platform/generated/study-anything-controlled-handoff-runbook.json",
    "platform/generated/study-anything-controlled-handoff-runbook.md",
    "docs/customer-delivery-trust-envelope.md",
    "platform/generated/study-anything-customer-delivery-trust-envelope.json",
    "platform/generated/study-anything-customer-delivery-trust-envelope.md",
    "docs/customer-delivery-rehearsal.md",
    "platform/generated/study-anything-customer-delivery-rehearsal.json",
    "platform/generated/study-anything-customer-delivery-rehearsal.md",
    "docs/end-to-end-trust-chain-harness.md",
    "platform/schemas/cbb/end-to-end-trust-chain-harness-v1.schema.json",
    "platform/generated/study-anything-end-to-end-trust-chain-harness.json",
    "platform/generated/study-anything-end-to-end-trust-chain-harness.md",
    "platform/generated/study-anything-end-to-end-trust-chain-harness.html",
    "fixtures/end-to-end-trust-chain-harness/pass/end-to-end-trust-chain-report.json",
    "scripts/end_to_end_trust_chain_harness.py",
    "scripts/verify_end_to_end_trust_chain_harness.py",
    "docs/real-adopter-scenario-import.md",
    "platform/schemas/cbb/real-adopter-scenario-import-v1.schema.json",
    "platform/generated/study-anything-real-adopter-scenario-import.json",
    "platform/generated/study-anything-real-adopter-scenario-import.md",
    "platform/generated/study-anything-real-adopter-scenario-import.html",
    "fixtures/real-adopter-scenario-import/pass/real-adopter-issue-summary.json",
    "fixtures/real-adopter-scenario-import/pass/external-feedback-receipt.json",
    "fixtures/real-adopter-scenario-import/pass/external-feedback-backlog-bridge.json",
    "fixtures/real-adopter-scenario-import/pass/product-loop-backlog-item.json",
    "fixtures/real-adopter-scenario-import/pass/product-owner-prioritization-receipt.json",
    "fixtures/real-adopter-scenario-import/pass/product-spec-eval-candidate.json",
    "fixtures/real-adopter-scenario-import/pass/product-spec-eval-authoring-receipt.json",
    "fixtures/real-adopter-scenario-import/pass/product-spec-eval-brief.json",
    "fixtures/real-adopter-scenario-import/pass/product-loop-brief-intake-receipt.json",
    "fixtures/real-adopter-scenario-import/pass/product-loop-scenario.json",
    "fixtures/real-adopter-scenario-import/pass/product-loop-run.json",
    "fixtures/real-adopter-scenario-import/pass/real-adopter-scenario-import-report.json",
    "scripts/real_adopter_scenario_import.py",
    "scripts/verify_real_adopter_scenario_import.py",
    "docs/spec-eval-scenario-execution-rehearsal.md",
    "platform/schemas/cbb/spec-eval-scenario-execution-rehearsal-v1.schema.json",
    "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.json",
    "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.md",
    "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.html",
    "fixtures/spec-eval-scenario-execution-rehearsal/pass/spec-eval-execution-rehearsal-receipt.json",
    "scripts/spec_eval_scenario_execution_rehearsal.py",
    "scripts/verify_spec_eval_scenario_execution_rehearsal.py",
    "docs/sandboxed-patch-proposal-rehearsal.md",
    "platform/schemas/cbb/sandboxed-patch-proposal-rehearsal-v1.schema.json",
    "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.json",
    "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.md",
    "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.html",
    "fixtures/sandboxed-patch-proposal-rehearsal/pass/sandboxed-patch-proposal-envelope.json",
    "scripts/sandboxed_patch_proposal_rehearsal.py",
    "scripts/verify_sandboxed_patch_proposal_rehearsal.py",
    "docs/code-review-operator-handoff-rehearsal.md",
    "platform/generated/study-anything-code-review-operator-handoff-rehearsal.json",
    "platform/generated/study-anything-code-review-operator-handoff-rehearsal.md",
    "docs/client-report-operator-handoff-rehearsal.md",
    "platform/generated/study-anything-client-report-operator-handoff-rehearsal.json",
    "platform/generated/study-anything-client-report-operator-handoff-rehearsal.md",
    "docs/support-response-operator-handoff-rehearsal.md",
    "platform/generated/study-anything-support-response-operator-handoff-rehearsal.json",
    "platform/generated/study-anything-support-response-operator-handoff-rehearsal.md",
    "docs/operator-handoff-rehearsal-contract.md",
    "platform/schemas/delivery-trust/operator-handoff-rehearsal-contract-v1.schema.json",
    "platform/generated/study-anything-operator-handoff-rehearsal-contract.json",
    "platform/generated/study-anything-operator-handoff-rehearsal-contract.md",
    "scripts/verify_operator_handoff_rehearsal_contract.py",
    "scripts/generate_trust_evidence_handoff_pack.py",
    "scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py",
    "scripts/verify_trust_evidence_acceptance_drill.py",
    "scripts/verify_controlled_handoff_runbook.py",
    "scripts/verify_customer_delivery_trust_envelope.py",
    "scripts/verify_customer_delivery_rehearsal.py",
    "scripts/verify_code_review_operator_handoff_rehearsal.py",
    "scripts/verify_client_report_operator_handoff_rehearsal.py",
    "scripts/verify_support_response_operator_handoff_rehearsal.py",
    "platform/generated/study-anything-client-report-delivery-class.json",
    "platform/generated/study-anything-client-report-delivery-class.html",
]
PR_EVIDENCE_REFS = {
    346: [
        "platform/generated/study-anything-release-stack-intake-candidate.json",
        "platform/generated/study-anything-release-stack-manifest-fixtures.json",
        "platform/generated/study-anything-release-stack-candidate-promotion.json",
        "platform/generated/study-anything-platform-bundle.json",
        "platform/generated/study-anything-platform-adoption-pack.json",
        "docs/external-feedback-receipt.md",
        "platform/schemas/delivery-trust/external-feedback-receipt-v1.schema.json",
        "platform/generated/study-anything-external-feedback-receipt.json",
        "platform/generated/study-anything-external-feedback-receipt.md",
        "platform/generated/study-anything-external-feedback-receipt.html",
        "scripts/external_feedback_receipt.py",
        "scripts/verify_external_feedback_receipt.py",
        "docs/external-feedback-backlog-bridge.md",
        "platform/schemas/delivery-trust/external-feedback-backlog-bridge-v1.schema.json",
        "platform/schemas/delivery-trust/product-loop-backlog-item-v1.schema.json",
        "platform/generated/study-anything-external-feedback-backlog-bridge.json",
        "platform/generated/study-anything-external-feedback-backlog-bridge.md",
        "platform/generated/study-anything-external-feedback-backlog-bridge.html",
        "scripts/external_feedback_backlog_bridge.py",
        "scripts/verify_external_feedback_backlog_bridge.py",
        "docs/product-owner-prioritization-gate.md",
        "platform/schemas/delivery-trust/product-owner-prioritization-receipt-v1.schema.json",
        "platform/schemas/delivery-trust/product-spec-eval-candidate-v1.schema.json",
        "platform/generated/study-anything-product-owner-prioritization-gate.json",
        "platform/generated/study-anything-product-owner-prioritization-gate.md",
        "platform/generated/study-anything-product-owner-prioritization-gate.html",
        "fixtures/product-owner-prioritization-gate/pass/product-owner-prioritization-receipt.json",
        "fixtures/product-owner-prioritization-gate/pass/product-spec-eval-candidate.json",
        "scripts/product_owner_prioritization_gate.py",
        "scripts/verify_product_owner_prioritization_gate.py",
        "docs/product-spec-eval-authoring-gate.md",
        "platform/schemas/delivery-trust/product-spec-eval-authoring-receipt-v1.schema.json",
        "platform/schemas/delivery-trust/product-spec-eval-brief-v1.schema.json",
        "platform/generated/study-anything-product-spec-eval-authoring-gate.json",
        "platform/generated/study-anything-product-spec-eval-authoring-gate.md",
        "platform/generated/study-anything-product-spec-eval-authoring-gate.html",
        "fixtures/product-spec-eval-authoring-gate/pass/product-spec-eval-authoring-receipt.json",
        "fixtures/product-spec-eval-authoring-gate/pass/product-spec-eval-brief.json",
        "scripts/product_spec_eval_authoring_gate.py",
        "scripts/verify_product_spec_eval_authoring_gate.py",
        "docs/product-loop-brief-intake.md",
        "platform/schemas/cbb/product-loop-brief-intake-receipt-v1.schema.json",
        "platform/generated/study-anything-product-loop-brief-intake.json",
        "platform/generated/study-anything-product-loop-brief-intake.md",
        "platform/generated/study-anything-product-loop-brief-intake.html",
        "fixtures/product-loop-brief-intake/pass/product-loop-brief-intake-receipt.json",
        "fixtures/product-loop-brief-intake/pass/product-loop-scenario.json",
        "fixtures/product-loop-brief-intake/pass/product-loop-run.json",
        "scripts/product_loop_brief_intake.py",
        "scripts/verify_product_loop_brief_intake.py",
        "platform/generated/study-anything-release-asset-adoption.json",
        "platform/generated/study-anything-product-loop-harness.json",
        "platform/generated/study-anything-delivery-trust-case-harness.json",
        "platform/generated/study-anything-delivery-trust-case-pack.json",
        "platform/generated/study-anything-delivery-trust-case-pack-consumer-walkthrough.json",
        "platform/generated/study-anything-delivery-class-registry.json",
        "platform/generated/study-anything-delivery-class-registry.html",
        "docs/delivery-class-registry.md",
        "scripts/verify_delivery_class_registry.py",
        "platform/generated/study-anything-trust-scenario-catalog.json",
        "platform/generated/study-anything-trust-scenario-catalog.html",
        "docs/trust-scenario-catalog.md",
        "scripts/verify_trust_scenario_catalog.py",
        "platform/generated/study-anything-trust-scenario-decision-gate.json",
        "platform/generated/study-anything-trust-scenario-decision-gate.html",
        "docs/trust-scenario-decision-gate.md",
        "scripts/trust_scenario_decision_gate.py",
        "scripts/verify_trust_scenario_decision_gate.py",
        "docs/code-review-delivery-class.md",
        "docs/client-report-delivery-class.md",
        "docs/support-response-delivery-class.md",
        "platform/generated/study-anything-code-review-delivery-class.json",
        "platform/generated/study-anything-code-review-delivery-class.html",
        "platform/generated/study-anything-client-report-delivery-class.json",
        "platform/generated/study-anything-client-report-delivery-class.html",
        "platform/generated/study-anything-support-response-delivery-class.json",
        "platform/generated/study-anything-support-response-delivery-class.html",
        "platform/schemas/delivery-trust/code-review-handoff-case-v1.schema.json",
        "platform/schemas/delivery-trust/client-report-handoff-case-v1.schema.json",
        "platform/schemas/delivery-trust/support-response-handoff-case-v1.schema.json",
        "scripts/code_review_delivery_class_handoff.py",
        "scripts/verify_code_review_delivery_class_handoff.py",
        "scripts/client_report_delivery_class_handoff.py",
        "scripts/verify_client_report_delivery_class_handoff.py",
        "scripts/support_response_delivery_class_handoff.py",
        "scripts/verify_support_response_delivery_class_handoff.py",
        "docs/trust-evidence-handoff-pack.md",
        "platform/generated/study-anything-trust-evidence-handoff-pack.json",
        "platform/generated/study-anything-trust-evidence-handoff-pack.md",
        "platform/generated/study-anything-trust-evidence-handoff-pack.sha256",
        "platform/generated/study-anything-trust-evidence-handoff-pack.zip",
        "platform/generated/study-anything-trust-evidence-handoff-pack-consumer-walkthrough.json",
        "docs/trust-evidence-acceptance-drill.md",
        "platform/generated/study-anything-trust-evidence-acceptance-drill.json",
        "platform/generated/study-anything-trust-evidence-acceptance-drill.md",
        "docs/controlled-handoff-runbook.md",
        "platform/generated/study-anything-controlled-handoff-runbook.json",
        "platform/generated/study-anything-controlled-handoff-runbook.md",
        "docs/customer-delivery-trust-envelope.md",
        "platform/generated/study-anything-customer-delivery-trust-envelope.json",
        "platform/generated/study-anything-customer-delivery-trust-envelope.md",
    "docs/customer-delivery-rehearsal.md",
    "platform/generated/study-anything-customer-delivery-rehearsal.json",
    "platform/generated/study-anything-customer-delivery-rehearsal.md",
    "docs/end-to-end-trust-chain-harness.md",
    "platform/schemas/cbb/end-to-end-trust-chain-harness-v1.schema.json",
    "platform/generated/study-anything-end-to-end-trust-chain-harness.json",
    "platform/generated/study-anything-end-to-end-trust-chain-harness.md",
    "platform/generated/study-anything-end-to-end-trust-chain-harness.html",
    "fixtures/end-to-end-trust-chain-harness/pass/end-to-end-trust-chain-report.json",
    "scripts/end_to_end_trust_chain_harness.py",
    "scripts/verify_end_to_end_trust_chain_harness.py",
        "docs/real-adopter-scenario-import.md",
        "platform/schemas/cbb/real-adopter-scenario-import-v1.schema.json",
        "platform/generated/study-anything-real-adopter-scenario-import.json",
        "platform/generated/study-anything-real-adopter-scenario-import.md",
        "platform/generated/study-anything-real-adopter-scenario-import.html",
        "fixtures/real-adopter-scenario-import/pass/real-adopter-issue-summary.json",
        "fixtures/real-adopter-scenario-import/pass/external-feedback-receipt.json",
        "fixtures/real-adopter-scenario-import/pass/external-feedback-backlog-bridge.json",
        "fixtures/real-adopter-scenario-import/pass/product-loop-backlog-item.json",
        "fixtures/real-adopter-scenario-import/pass/product-owner-prioritization-receipt.json",
        "fixtures/real-adopter-scenario-import/pass/product-spec-eval-candidate.json",
        "fixtures/real-adopter-scenario-import/pass/product-spec-eval-authoring-receipt.json",
        "fixtures/real-adopter-scenario-import/pass/product-spec-eval-brief.json",
        "fixtures/real-adopter-scenario-import/pass/product-loop-brief-intake-receipt.json",
        "fixtures/real-adopter-scenario-import/pass/product-loop-scenario.json",
        "fixtures/real-adopter-scenario-import/pass/product-loop-run.json",
        "fixtures/real-adopter-scenario-import/pass/real-adopter-scenario-import-report.json",
        "scripts/real_adopter_scenario_import.py",
        "scripts/verify_real_adopter_scenario_import.py",
        "docs/spec-eval-scenario-execution-rehearsal.md",
        "platform/schemas/cbb/spec-eval-scenario-execution-rehearsal-v1.schema.json",
        "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.json",
        "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.md",
        "platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.html",
        "fixtures/spec-eval-scenario-execution-rehearsal/pass/spec-eval-execution-rehearsal-receipt.json",
        "scripts/spec_eval_scenario_execution_rehearsal.py",
        "scripts/verify_spec_eval_scenario_execution_rehearsal.py",
        "docs/sandboxed-patch-proposal-rehearsal.md",
        "platform/schemas/cbb/sandboxed-patch-proposal-rehearsal-v1.schema.json",
        "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.json",
        "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.md",
        "platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.html",
        "fixtures/sandboxed-patch-proposal-rehearsal/pass/sandboxed-patch-proposal-envelope.json",
        "scripts/sandboxed_patch_proposal_rehearsal.py",
        "scripts/verify_sandboxed_patch_proposal_rehearsal.py",
        "docs/code-review-operator-handoff-rehearsal.md",
        "platform/generated/study-anything-code-review-operator-handoff-rehearsal.json",
        "platform/generated/study-anything-code-review-operator-handoff-rehearsal.md",
        "docs/client-report-operator-handoff-rehearsal.md",
        "platform/generated/study-anything-client-report-operator-handoff-rehearsal.json",
        "platform/generated/study-anything-client-report-operator-handoff-rehearsal.md",
        "docs/support-response-operator-handoff-rehearsal.md",
        "platform/generated/study-anything-support-response-operator-handoff-rehearsal.json",
        "platform/generated/study-anything-support-response-operator-handoff-rehearsal.md",
        "docs/operator-handoff-rehearsal-contract.md",
        "platform/schemas/delivery-trust/operator-handoff-rehearsal-contract-v1.schema.json",
        "platform/generated/study-anything-operator-handoff-rehearsal-contract.json",
        "platform/generated/study-anything-operator-handoff-rehearsal-contract.md",
        "scripts/verify_operator_handoff_rehearsal_contract.py",
        "scripts/generate_trust_evidence_handoff_pack.py",
        "scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py",
        "scripts/verify_trust_evidence_acceptance_drill.py",
        "scripts/verify_controlled_handoff_runbook.py",
        "scripts/verify_customer_delivery_trust_envelope.py",
        "scripts/verify_customer_delivery_rehearsal.py",
        "scripts/verify_code_review_operator_handoff_rehearsal.py",
        "scripts/verify_client_report_operator_handoff_rehearsal.py",
        "scripts/verify_support_response_operator_handoff_rehearsal.py",
        "platform/generated/study-anything-client-report-delivery-class.json",
        "platform/generated/study-anything-client-report-delivery-class.html",
        "platform/schemas/delivery-trust/client-report-handoff-case-v1.schema.json",
    ],
}
PRIVACY_ASSERTIONS = {
    "metadata_only": True,
    "github_tokens_included": False,
    "job_logs_included": False,
    "check_annotations_included": False,
    "live_check_payloads_included": False,
    "source_mutation_performed": False,
    "raw_source_text_included": False,
    "learner_answers_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}
PRIVATE_NEEDLES = (
    "gho_",
    "ghp_",
    "github_pat_",
    "sk-proj-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "raw log:",
    "job log:",
    "artifact:",
    "annotation:",
    "raw source text:",
    "learner answer:",
    "agent endpoint:",
)


class ReleaseStackPromotionError(RuntimeError):
    """Readable release stack promotion failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def redact(text: str) -> str:
    redacted = text
    for needle in PRIVATE_NEEDLES:
        redacted = re.sub(re.escape(needle), "<redacted>", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._-]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"github_pat_[A-Za-z0-9_]+", "<redacted>", redacted)
    redacted = re.sub(r"gh[op]_[A-Za-z0-9_]+", "<redacted>", redacted)
    redacted = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "<redacted>", redacted)
    return redacted


def reject_private_payload(payload: Any, label: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True) if not isinstance(payload, str) else payload
    lowered = serialized.lower()
    hits = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if hits:
        raise ReleaseStackPromotionError(f"{label} contains private or unsafe text: {hits}")


def relative_ref_exists(ref: str) -> bool:
    path = Path(ref)
    return not path.is_absolute() and ".." not in path.parts and (ROOT / path).exists()


def validate_refs(refs: list[str], label: str) -> None:
    if not refs:
        raise ReleaseStackPromotionError(f"{label} must include evidence refs.")
    missing = [ref for ref in refs if not relative_ref_exists(ref)]
    if missing:
        raise ReleaseStackPromotionError(f"{label} has missing or unsafe evidence refs: {missing}")


def validate_commands(commands: Any) -> list[str]:
    if not isinstance(commands, list) or not commands:
        raise ReleaseStackPromotionError("promotion operator_commands must be a non-empty list.")
    normalized = [str(command) for command in commands]
    unsafe = [command for command in normalized if command not in SAFE_OPERATOR_COMMANDS]
    if unsafe:
        raise ReleaseStackPromotionError(f"promotion operator_commands contains unsafe commands: {unsafe}")
    return normalized


def load_source_row(
    source: Mapping[str, Any],
    *,
    expected_pr: int,
    order: int,
    evidence_refs: list[str],
    require_promotion_commands: bool,
) -> dict[str, Any]:
    if source.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ReleaseStackPromotionError(f"PR #{expected_pr} source schema_version drifted.")
    reject_private_text(source, f"PR #{expected_pr} promotion source")
    reject_raw_payloads(source)
    reject_private_payload(source, f"PR #{expected_pr} promotion source")
    if source.get("pr_number") != expected_pr:
        raise ReleaseStackPromotionError(f"PR #{expected_pr} promotion source must describe PR #{expected_pr}.")
    if source.get("base_branch") != "main" or source.get("state") != "MERGED":
        raise ReleaseStackPromotionError(f"PR #{expected_pr} promotion source must be merged into main.")
    if require_promotion_commands:
        commands = validate_commands(source.get("operator_commands"))
        for command in (
            "python3 scripts/verify_release_stack_intake_candidate.py --check",
            "python3 scripts/verify_release_stack_candidate_promotion.py --check",
        ):
            if command not in commands:
                raise ReleaseStackPromotionError(f"PR #{expected_pr} promotion source missing operator command: {command}")
    checks = normalize_checks(source)
    row = {
        "order": order,
        "pr": expected_pr,
        "branch": str(source.get("head_branch")),
        "base": "main",
        "status_expected_before_merge": "checks_pass",
        "final_state": "MERGED",
        "merge_commit": normalize_merge_commit(source),
        "required_checks": checks,
        "evidence_refs": list(evidence_refs),
    }
    validate_refs(row["evidence_refs"], f"PR #{expected_pr} evidence_refs")
    return row


def expected_group(pr_sources: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "group_id": PROMOTED_GROUP_ID,
        "role": "current",
        "status": "completed",
        "target_branch": "main",
        "summary": "Completed self-intake for the Sandboxed Patch Proposal Rehearsal evidence chain.",
        "required_checks": sorted(REQUIRED_CHECKS),
        "operator_commands": [
            "python3 scripts/verify_release_stack_readiness.py",
            "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
            "python3 scripts/verify_release_stack_intake_candidate.py --check",
            "python3 scripts/verify_release_stack_candidate_promotion.py --check",
            "python3 scripts/verify_release_stack_live_status.py",
            "python3 scripts/verify_release_stack_lineage.py",
            "python3 scripts/verify_release_stack_merge_runbook.py --report-only",
            "./scripts/release_check.sh",
        ],
        "post_merge_evidence_refs": list(POST_MERGE_EVIDENCE_REFS),
        "stack": [
            load_source_row(
                pr_sources[346],
                expected_pr=346,
                order=1,
                evidence_refs=PR_EVIDENCE_REFS[346],
                require_promotion_commands=True,
            ),
        ],
        "privacy_assertions": dict(PRIVACY_ASSERTIONS),
    }


def find_group(manifest: Mapping[str, Any], group_id: str) -> dict[str, Any]:
    groups = manifest.get("stack_groups")
    if not isinstance(groups, list):
        raise ReleaseStackPromotionError("manifest stack_groups must be a list.")
    matches = [group for group in groups if isinstance(group, dict) and group.get("group_id") == group_id]
    if len(matches) != 1:
        raise ReleaseStackPromotionError(f"manifest group {group_id!r} must exist exactly once.")
    return matches[0]


def all_manifest_prs(manifest: Mapping[str, Any]) -> list[int]:
    prs: list[int] = []
    for group in manifest.get("stack_groups", []):
        if not isinstance(group, Mapping):
            continue
        for row in group.get("stack", []):
            if isinstance(row, Mapping) and isinstance(row.get("pr"), int):
                prs.append(row["pr"])
    return prs


def assert_no_duplicate_prs(manifest: Mapping[str, Any]) -> None:
    prs = all_manifest_prs(manifest)
    duplicates = sorted({pr for pr in prs if prs.count(pr) > 1})
    if duplicates:
        raise ReleaseStackPromotionError(f"manifest contains duplicate promoted PRs: {duplicates}")


def verify_promoted_manifest(
    manifest: dict[str, Any],
    pr_sources: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    reject_private_payload(manifest, "release stack manifest")
    try:
        readiness = verify_manifest(manifest)
    except ReleaseStackReadinessError as exc:
        raise ReleaseStackPromotionError(str(exc)) from exc
    if manifest.get("current_group") != PROMOTED_GROUP_ID:
        raise ReleaseStackPromotionError(f"manifest current_group must be {PROMOTED_GROUP_ID}.")
    previous = find_group(manifest, PREVIOUS_CURRENT_GROUP_ID)
    if previous.get("role") != "archived" or previous.get("status") != "archived":
        raise ReleaseStackPromotionError("previous current group must be archived after promotion.")
    previous_prs = [row.get("pr") for row in previous.get("stack", []) if isinstance(row, Mapping)]
    if previous_prs != [344]:
        raise ReleaseStackPromotionError("previous current group must retain PR #344 audit rows.")

    expected = expected_group(pr_sources)
    actual = find_group(manifest, PROMOTED_GROUP_ID)
    if actual != expected:
        raise ReleaseStackPromotionError("promoted current group does not match the expected #346 candidate group.")
    if manifest.get("stack") != expected["stack"]:
        raise ReleaseStackPromotionError("top-level stack must mirror promoted current group stack.")
    validate_commands(actual.get("operator_commands"))
    validate_refs(actual.get("post_merge_evidence_refs", []), "promoted post_merge_evidence_refs")
    assert_no_duplicate_prs(manifest)
    return readiness


def run_negative_case(
    case_id: str,
    mutator: Any,
    manifest: dict[str, Any],
    pr_sources: Mapping[int, Mapping[str, Any]],
) -> dict[str, str]:
    payload = copy.deepcopy(manifest)
    mutator(payload)
    try:
        verify_promoted_manifest(payload, pr_sources)
    except ReleaseStackPromotionError as exc:
        return {"case_id": case_id, "status": "rejected", "error": redact(str(exc))}
    raise ReleaseStackPromotionError(f"Negative promotion fixture was not rejected: {case_id}")


def sync_top_level_stack(manifest: dict[str, Any]) -> None:
    group = find_group(manifest, PROMOTED_GROUP_ID)
    manifest["stack"] = copy.deepcopy(group["stack"])


def negative_fixtures(
    manifest: dict[str, Any],
    pr_sources: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, str]]:
    def duplicate_pr(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        duplicate = copy.deepcopy(group["stack"][0])
        duplicate["order"] = len(group["stack"]) + 1
        group["stack"].append(duplicate)
        sync_top_level_stack(payload)

    def missing_merge_commit(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        group["stack"][0]["merge_commit"] = "not-a-sha"
        sync_top_level_stack(payload)

    def failed_required_check(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        group["stack"][0]["required_checks"]["api-tests"] = "failed"
        sync_top_level_stack(payload)

    def missing_required_check(payload: dict[str, Any]) -> None:
        group = find_group(payload, PROMOTED_GROUP_ID)
        group["stack"][0]["required_checks"].pop("compose-smoke", None)
        sync_top_level_stack(payload)

    def unsafe_command(payload: dict[str, Any]) -> None:
        find_group(payload, PROMOTED_GROUP_ID)["operator_commands"].append(
            "gh api repos/jzvcpe-goat/study-anything/actions/jobs/1/logs"
        )

    def secret_payload(payload: dict[str, Any]) -> None:
        find_group(payload, PROMOTED_GROUP_ID)["summary"] = "github_pat_unsafe raw log: do not store"

    def manifest_regression(payload: dict[str, Any]) -> None:
        payload["current_group"] = PREVIOUS_CURRENT_GROUP_ID

    cases = [
        ("already_represented_pr", duplicate_pr),
        ("missing_merge_commit", missing_merge_commit),
        ("failed_required_check", failed_required_check),
        ("missing_required_check", missing_required_check),
        ("unsafe_command", unsafe_command),
        ("secret_log_artifact_payload", secret_payload),
        ("manifest_regression", manifest_regression),
    ]
    return [run_negative_case(case_id, mutator, manifest, pr_sources) for case_id, mutator in cases]


def build_report(manifest: dict[str, Any], pr_sources: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    readiness = verify_promoted_manifest(manifest, pr_sources)
    current = current_group(manifest)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "generated_at": GENERATED_AT,
        "source_reports": [
            "fixtures/release-stack/pr-346-intake-candidate.json",
            "platform/release-stack.json",
        ],
        "promotion": {
            "previous_current_group": PREVIOUS_CURRENT_GROUP_ID,
            "previous_current_group_archived": True,
            "current_group": PROMOTED_GROUP_ID,
            "promoted_prs": [row["pr"] for row in current["stack"]],
            "top_level_stack_mirrors_current": True,
        },
        "readiness": {
            "schema_version": readiness["schema_version"],
            "status": readiness["status"],
            "current_group": readiness["current_group"],
            "archived_group_count": readiness["archived_group_count"],
            "stack_prs": readiness["stack_prs"],
        },
        "negative_fixtures": negative_fixtures(manifest, pr_sources),
        "privacy": {
            "metadata_only": True,
            "github_tokens_stored": False,
            "job_logs_stored": False,
            "check_annotations_stored": False,
            "artifacts_stored": False,
            "live_check_payloads_stored": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "source_mutation_performed": False,
        },
    }
    reject_private_payload(report, "release stack promotion report")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--pr-346-source", type=Path, default=PR_SOURCES[346])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_json(args.manifest)
    pr_sources = {
        346: load_json(args.pr_346_source),
    }
    report = build_report(manifest, pr_sources)
    text = dump_json(report)
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
        return
    if args.check:
        if not REPORT.exists():
            raise ReleaseStackPromotionError(f"promotion report missing: {REPORT.relative_to(ROOT)}")
        if REPORT.read_text(encoding="utf-8") != text:
            raise ReleaseStackPromotionError(
                "Release stack candidate promotion report is stale. Run: "
                "python3 scripts/verify_release_stack_candidate_promotion.py --write"
            )
        print("ok    release stack candidate promotion report is up to date")
        return
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_candidate_promotion failed: {redact(str(exc))}", file=sys.stderr)
        sys.exit(1)
