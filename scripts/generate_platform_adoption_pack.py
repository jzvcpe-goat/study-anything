#!/usr/bin/env python3
"""Generate the distributable platform adoption pack archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
MANIFEST_PATH = OUTPUT_DIR / "study-anything-platform-adoption-pack.json"
ARCHIVE_PATH = OUTPUT_DIR / "study-anything-platform-adoption-pack.zip"
ARCHIVE_ROOT = "study-anything-platform-adoption-pack"

CBB_PROTOCOL_CASES = [
    "safe-controlled-handoff",
    "missing-claim-boundary",
    "reviewer-not-qualified",
    "recipient-risk-unknown",
    "ai-review-only-rejected",
]
CBB_PROTOCOL_ARTIFACTS = [
    "claim-boundary.json",
    "trust-root.json",
    "reviewer-reconstruction-receipt.json",
    "risk-owner-scope.json",
    "delivery-decision-receipt.json",
]
CBB_SELF_INTAKE_POSITIVE_ARTIFACTS = [
    "claim-boundary.json",
    "trust-root.json",
    "reviewer-reconstruction-receipt.json",
    "risk-owner-scope.json",
    "delivery-decision-receipt.json",
    "receipt-chain.json",
    "self-intake-receipt.json",
    "delivery-evidence-pack.json",
]
CBB_SELF_INTAKE_NEGATIVE_CASES = {
    "receipt-hash-mismatch": ["receipt-chain.json", "expected-error.json"],
    "receipt-chain-stale-source-commit": ["receipt-chain.json", "expected-error.json"],
    "missing-reviewer-reconstruction": ["self-intake-receipt.json", "expected-error.json"],
    "stale-source-commit": ["self-intake-receipt.json", "expected-error.json"],
    "scope-expansion": ["self-intake-receipt.json", "expected-error.json"],
    "ci-evidence-missing": ["self-intake-receipt.json", "expected-error.json"],
    "ai-review-only-evidence-rejected": ["self-intake-receipt.json", "expected-error.json"],
}
CBB_DELIVERY_HARNESS_CASES = [
    "pass",
    "blocked-missing-developer-reconstruction",
    "blocked-risk-over-budget",
    "blocked-external-scope-expansion",
    "blocked-stale-receipt-chain",
    "blocked-ai-review-only",
]
CBB_DELIVERY_HARNESS_ARTIFACTS = [
    "delivery-scenario.json",
    "external-feedback-intake.json",
    "receipt-chain.json",
    "self-intake-receipt.json",
    "tri-loop-run.json",
]
PRODUCT_LOOP_HARNESS_CASES = [
    "pass",
    "blocked-missing-product-spec-evals",
    "blocked-missing-developer-vision",
    "blocked-external-scope-expansion",
    "blocked-ai-review-only",
    "blocked-loop-dominance",
]
PRODUCT_LOOP_HARNESS_ARTIFACTS = [
    "product-loop-scenario.json",
    "product-loop-run.json",
]
EXTERNAL_FEEDBACK_RECEIPT_CASES = [
    "pass",
    "blocked-raw-feedback",
    "blocked-identity",
    "blocked-production-mutation",
    "blocked-ai-review-only",
]
EXTERNAL_FEEDBACK_BACKLOG_BRIDGE_CASES = [
    "pass",
    "blocked-raw-feedback",
    "blocked-identity",
    "blocked-production-mutation",
    "blocked-ai-review-only",
]
PRODUCT_OWNER_PRIORITIZATION_GATE_CASES = [
    "pass",
    "blocked-missing-owner-reconstruction",
    "blocked-automatic-priority",
    "blocked-skip-to-delivery-harness",
    "blocked-automatic-execution",
    "blocked-production-mutation",
    "blocked-customer-visible-action",
    "blocked-blocked-backlog-source",
]
PRODUCT_SPEC_EVAL_AUTHORING_GATE_CASES = [
    "pass",
    "blocked-missing-authoring-reconstruction",
    "blocked-raw-spec-body",
    "blocked-automatic-execution",
    "blocked-skip-to-delivery-harness",
    "blocked-production-mutation",
    "blocked-customer-visible-action",
    "blocked-invalid-candidate-source",
]
PRODUCT_LOOP_BRIEF_INTAKE_CASES = [
    "pass",
    "blocked-missing-brief",
    "blocked-invalid-brief",
    "blocked-missing-developer-vision",
    "blocked-external-scope-expansion",
    "blocked-ai-review-only",
    "blocked-production-mutation",
    "blocked-skip-to-delivery-harness",
]
PRODUCT_LOOP_BRIEF_INTAKE_ARTIFACTS = {
    "pass": [
        "product-loop-brief-intake-receipt.json",
        "product-loop-scenario.json",
        "product-loop-run.json",
    ],
    "blocked-missing-brief": ["product-loop-brief-intake-receipt.json"],
    "blocked-invalid-brief": ["product-loop-brief-intake-receipt.json"],
    "blocked-missing-developer-vision": ["product-loop-brief-intake-receipt.json"],
    "blocked-external-scope-expansion": ["product-loop-brief-intake-receipt.json"],
    "blocked-ai-review-only": ["product-loop-brief-intake-receipt.json"],
    "blocked-production-mutation": ["product-loop-brief-intake-receipt.json"],
    "blocked-skip-to-delivery-harness": ["product-loop-brief-intake-receipt.json"],
}
SPEC_EVAL_SCENARIO_EXECUTION_REHEARSAL_CASES = [
    "pass",
    "blocked-missing-sandbox",
    "blocked-missing-human-reconstruction",
    "blocked-ai-review-only",
    "blocked-customer-visible-action",
    "blocked-production-mutation",
]
SPEC_EVAL_SCENARIO_EXECUTION_REHEARSAL_ARTIFACTS = {
    "pass": [
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "spec-eval-acceptance-receipt.json",
        "spec-eval-execution-rehearsal-receipt.json",
    ],
    "blocked-missing-sandbox": [
        "failure-contract.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "spec-eval-acceptance-receipt.json",
        "spec-eval-execution-rehearsal-receipt.json",
    ],
    "blocked-missing-human-reconstruction": [
        "failure-contract.json",
        "sandbox-receipt.json",
        "dual-loop-gate-receipt.json",
        "spec-eval-acceptance-receipt.json",
        "spec-eval-execution-rehearsal-receipt.json",
    ],
    "blocked-ai-review-only": [
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "spec-eval-acceptance-receipt.json",
        "spec-eval-execution-rehearsal-receipt.json",
    ],
    "blocked-customer-visible-action": [
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "spec-eval-acceptance-receipt.json",
        "spec-eval-execution-rehearsal-receipt.json",
    ],
    "blocked-production-mutation": [
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "spec-eval-acceptance-receipt.json",
        "spec-eval-execution-rehearsal-receipt.json",
    ],
}
SANDBOXED_PATCH_PROPOSAL_REHEARSAL_CASES = [
    "pass",
    "blocked-missing-spec-eval-allowance",
    "blocked-missing-rollback-plan",
    "blocked-missing-test-plan",
    "blocked-repository-mutation",
    "blocked-customer-visible-action",
    "blocked-external-publication",
    "blocked-production-mutation",
]
SANDBOXED_PATCH_PROPOSAL_REHEARSAL_ARTIFACTS = {
    case_id: ["sandboxed-patch-proposal-envelope.json"]
    for case_id in SANDBOXED_PATCH_PROPOSAL_REHEARSAL_CASES
}
PATCH_PROPOSAL_OPERATOR_HANDOFF_BRIDGE_CASES = [
    "pass",
    "blocked-sandboxed-proposal-blocked",
    "blocked-missing-operator-confirmation",
    "blocked-raw-patch-request",
    "blocked-repository-mutation",
    "blocked-customer-visible-action",
    "blocked-external-publication",
    "blocked-production-mutation",
]
PATCH_PROPOSAL_OPERATOR_HANDOFF_BRIDGE_ARTIFACTS = {
    case_id: ["patch-proposal-operator-handoff-bridge-receipt.json"]
    for case_id in PATCH_PROPOSAL_OPERATOR_HANDOFF_BRIDGE_CASES
}
PATCH_PROPOSAL_ACCEPTANCE_DRILL_CASES = [
    "pass",
    "blocked-bridge-blocked",
    "blocked-missing-operator-decision",
    "blocked-raw-patch-evidence-request",
    "blocked-apply-patch-request",
    "blocked-open-pr-request",
    "blocked-customer-visible-action",
    "blocked-external-publication",
    "blocked-production-mutation",
]
PATCH_PROPOSAL_ACCEPTANCE_DRILL_ARTIFACTS = {
    case_id: ["patch-proposal-acceptance-drill-receipt.json"]
    for case_id in PATCH_PROPOSAL_ACCEPTANCE_DRILL_CASES
}
PATCH_PROPOSAL_EXTERNAL_WORK_ORDER_PACK_CASES = [
    "pass",
    "blocked-acceptance-blocked",
    "blocked-missing-work-order-purpose",
    "blocked-raw-patch-request",
    "blocked-apply-patch-request",
    "blocked-open-pr-request",
    "blocked-pr-comment-request",
    "blocked-customer-visible-action",
    "blocked-external-publication",
    "blocked-production-mutation",
]
PATCH_PROPOSAL_EXTERNAL_WORK_ORDER_PACK_ARTIFACTS = {
    case_id: ["patch-proposal-external-work-order-receipt.json"]
    for case_id in PATCH_PROPOSAL_EXTERNAL_WORK_ORDER_PACK_CASES
}
PATCH_PROPOSAL_EXTERNAL_OPERATOR_COMPLETION_CASES = [
    "pass",
    "blocked-work-order-blocked",
    "blocked-missing-completion-purpose",
    "blocked-missing-reconstruction",
    "blocked-raw-patch-return",
    "blocked-raw-diff-return",
    "blocked-repository-file-body-return",
    "blocked-pr-comment-return",
    "blocked-customer-visible-payload",
    "blocked-external-publication-payload",
    "blocked-production-payload",
    "blocked-secret-return",
    "blocked-model-credential-return",
]
PATCH_PROPOSAL_EXTERNAL_OPERATOR_COMPLETION_ARTIFACTS = {
    case_id: ["patch-proposal-external-operator-completion-receipt.json"]
    for case_id in PATCH_PROPOSAL_EXTERNAL_OPERATOR_COMPLETION_CASES
}
PATCH_PROPOSAL_CUSTOMER_HANDOFF_BOUNDARY_GATE_CASES = [
    "pass",
    "blocked-completion-blocked",
    "blocked-missing-delivery-class-scenario",
    "blocked-missing-human-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-missing-sandbox-receipt",
    "blocked-raw-customer-draft",
    "blocked-raw-patch-return",
    "blocked-production-payload",
    "blocked-auto-send",
    "blocked-external-publication",
    "blocked-secret-return",
    "blocked-model-credential-return",
]
PATCH_PROPOSAL_CUSTOMER_HANDOFF_BOUNDARY_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-customer-handoff-boundary-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_HANDOFF_BOUNDARY_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_DELIVERY_ENVELOPE_CASES = [
    "pass",
    "blocked-boundary-blocked",
    "blocked-missing-manual-send-control",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-customer-draft",
    "blocked-raw-patch-body",
    "blocked-raw-diff-body",
    "blocked-pr-comment-body",
    "blocked-production-payload",
    "blocked-auto-send",
    "blocked-external-publication",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_DELIVERY_ENVELOPE_ARTIFACTS = {
    case_id: ["patch-proposal-customer-delivery-envelope.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_DELIVERY_ENVELOPE_CASES
}
PATCH_PROPOSAL_CUSTOMER_DELIVERY_REHEARSAL_CASES = [
    "pass",
    "blocked-envelope-blocked",
    "blocked-missing-recipient-scope",
    "blocked-missing-delivery-class-scope",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-missing-manual-send-boundary",
    "blocked-raw-customer-draft",
    "blocked-raw-patch-body",
    "blocked-raw-diff-body",
    "blocked-pr-comment-action",
    "blocked-auto-send",
    "blocked-external-publication",
    "blocked-production-mutation",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_DELIVERY_REHEARSAL_ARTIFACTS = {
    case_id: ["patch-proposal-customer-delivery-rehearsal-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_DELIVERY_REHEARSAL_CASES
}
PATCH_PROPOSAL_CUSTOMER_DELIVERY_OUTCOME_CASES = [
    "pass-human-operator",
    "pass-host-platform-agent",
    "blocked-rehearsal-blocked",
    "blocked-missing-external-actor",
    "blocked-missing-action-reference",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-customer-visible-body",
    "blocked-pr-comment-body",
    "blocked-external-publication-payload",
    "blocked-production-payload",
    "blocked-automatic-send",
    "blocked-source-mutation",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_DELIVERY_OUTCOME_ARTIFACTS = {
    case_id: ["patch-proposal-customer-delivery-outcome-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_DELIVERY_OUTCOME_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_INTAKE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-outcome-blocked",
    "blocked-missing-response-signal",
    "blocked-missing-signal-reference",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-customer-reply",
    "blocked-private-customer-data",
    "blocked-pr-comment-body",
    "blocked-external-publication-payload",
    "blocked-production-payload",
    "blocked-automatic-follow-up",
    "blocked-source-mutation",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_INTAKE_ARTIFACTS = {
    case_id: ["patch-proposal-customer-feedback-intake-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_INTAKE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_BACKLOG_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-intake-blocked",
    "blocked-missing-product-loop-target",
    "blocked-automatic-priority-assignment",
    "blocked-automatic-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-raw-customer-reply",
    "blocked-private-customer-data",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_BACKLOG_ARTIFACTS = {
    case_id: [
        "patch-proposal-customer-feedback-backlog-bridge.json",
        *(
            ["product-loop-backlog-signal.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_BACKLOG_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_OWNER_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-owner-reconstruction",
    "blocked-automatic-priority-assignment",
    "blocked-skip-to-delivery-harness",
    "blocked-automatic-execution",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-blocked-backlog-source",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_OWNER_ARTIFACTS = {
    case_id: [
        "patch-proposal-customer-feedback-product-owner-receipt.json",
        *(
            ["patch-proposal-product-spec-eval-candidate.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_OWNER_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_SPEC_EVAL_AUTHORING_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-authoring-reconstruction",
    "blocked-raw-spec-body",
    "blocked-raw-eval-body",
    "blocked-automatic-execution",
    "blocked-skip-to-delivery-trust",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-invalid-product-owner-candidate",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_SPEC_EVAL_AUTHORING_ARTIFACTS = {
    case_id: [
        "patch-proposal-customer-feedback-spec-eval-authoring-receipt.json",
        *(
            ["patch-proposal-product-loop-brief-candidate.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_SPEC_EVAL_AUTHORING_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-brief-candidate",
    "blocked-invalid-brief-candidate",
    "blocked-missing-product-loop-reconstruction",
    "blocked-ai-review-only",
    "blocked-skip-to-delivery-trust",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_ARTIFACTS = {
    case_id: [
        "patch-proposal-product-loop-brief-intake-receipt.json",
        *(
            ["product-loop-scenario.json", "product-loop-run.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_INTAKE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-product-loop-run",
    "blocked-invalid-product-loop-run",
    "blocked-missing-sandbox-receipt",
    "blocked-missing-attention-reconstruction",
    "blocked-dual-loop-gate-blocked",
    "blocked-ai-review-only",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_INTAKE_ARTIFACTS = {
    case_id: [
        "patch-proposal-delivery-trust-intake-receipt.json",
        *(
            ["patch-proposal-delivery-trust-case-candidate.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_INTAKE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-candidate",
    "blocked-invalid-candidate",
    "blocked-missing-product-loop-run",
    "blocked-product-loop-hash-mismatch",
    "blocked-missing-dual-loop-evidence",
    "blocked-dual-loop-evidence-mismatch",
    "blocked-dual-loop-gate-blocked",
    "blocked-ai-review-only",
    "blocked-customer-visible-send",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_ARTIFACTS = {
    case_id: [
        "patch-proposal-delivery-trust-case-bridge-receipt.json",
        *(
            ["patch-proposal-delivery-trust-case-handoff-refs.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_BOUNDARY_GATE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-bridge-receipt",
    "blocked-invalid-bridge-receipt",
    "blocked-missing-handoff-refs",
    "blocked-handoff-refs-mismatch",
    "blocked-missing-reconstruction",
    "blocked-passive-reconstruction",
    "blocked-unsupported-reconstruction-source",
    "blocked-missing-product-loop-ref",
    "blocked-missing-dual-loop-ref",
    "blocked-missing-delivery-trust-case-ref",
    "blocked-raw-follow-up-body",
    "blocked-automatic-customer-send",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_BOUNDARY_GATE_ARTIFACTS = {
    case_id: [
        "patch-proposal-controlled-follow-up-boundary-receipt.json",
        *(
            ["patch-proposal-follow-up-boundary-reconstruction.json"]
            if case_id != "blocked-missing-reconstruction"
            else []
        ),
        *(
            ["patch-proposal-controlled-follow-up-envelope-refs.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_BOUNDARY_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_REHEARSAL_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-envelope-refs",
    "blocked-invalid-envelope-refs",
    "blocked-passive-rehearsal",
    "blocked-unsupported-rehearsal-source",
    "blocked-missing-active-reconstruction-ref",
    "blocked-missing-product-loop-ref",
    "blocked-missing-dual-loop-ref",
    "blocked-missing-delivery-trust-ref",
    "blocked-raw-follow-up-preview",
    "blocked-customer-visible-draft",
    "blocked-automatic-customer-send",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_REHEARSAL_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-rehearsal-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_REHEARSAL_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_OUTCOME_CASES = [
    "pass-human-operator",
    "pass-host-platform-agent",
    "blocked-rehearsal-blocked",
    "blocked-missing-external-actor",
    "blocked-missing-action-reference",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-body",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-send-payload",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_OUTCOME_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-outcome-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_OUTCOME_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_INTAKE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-outcome-blocked",
    "blocked-missing-response-signal",
    "blocked-missing-signal-reference",
    "blocked-missing-product-loop-target",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-private-customer-data",
    "blocked-pr-comment-body",
    "blocked-external-publication-payload",
    "blocked-automatic-follow-up",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_INTAKE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-intake-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_INTAKE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BACKLOG_BRIDGE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-intake-blocked",
    "blocked-missing-product-loop-target",
    "blocked-automatic-priority-assignment",
    "blocked-automatic-follow-up",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-private-customer-data",
    "blocked-pr-comment-body",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BACKLOG_BRIDGE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-backlog-bridge.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BACKLOG_BRIDGE_CASES
}
for _case_id in (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
):
    PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BACKLOG_BRIDGE_ARTIFACTS[
        _case_id
    ].append("product-loop-backlog-signal.json")
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_OWNER_GATE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-owner-reconstruction",
    "blocked-automatic-priority-assignment",
    "blocked-skip-to-delivery-harness",
    "blocked-automatic-execution",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-blocked-backlog-source",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_OWNER_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-product-owner-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_OWNER_GATE_CASES
}
for _case_id in (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
):
    PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_OWNER_GATE_ARTIFACTS[
        _case_id
    ].append("patch-proposal-product-spec-eval-candidate.json")
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_SPEC_EVAL_AUTHORING_GATE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-authoring-reconstruction",
    "blocked-raw-spec-body",
    "blocked-raw-eval-body",
    "blocked-automatic-execution",
    "blocked-skip-to-delivery-trust",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-invalid-product-owner-candidate",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_SPEC_EVAL_AUTHORING_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_SPEC_EVAL_AUTHORING_GATE_CASES
}
for _case_id in (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
):
    PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_SPEC_EVAL_AUTHORING_GATE_ARTIFACTS[
        _case_id
    ].append("patch-proposal-product-loop-brief-candidate.json")
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_GATE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-brief-candidate",
    "blocked-invalid-brief-candidate",
    "blocked-missing-product-loop-reconstruction",
    "blocked-ai-review-only",
    "blocked-skip-to-delivery-trust",
    "blocked-automatic-execution",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-product-loop-brief-intake-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_GATE_CASES
}
for _case_id in (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
):
    PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_GATE_ARTIFACTS[
        _case_id
    ].extend(["product-loop-scenario.json", "product-loop-run.json"])
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_INTAKE_GATE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-product-loop-run",
    "blocked-invalid-product-loop-run",
    "blocked-missing-sandbox-receipt",
    "blocked-missing-attention-reconstruction",
    "blocked-dual-loop-gate-blocked",
    "blocked-ai-review-only",
    "blocked-direct-delivery-trust-harness",
    "blocked-customer-handoff-package",
    "blocked-automatic-execution",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_INTAKE_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_INTAKE_GATE_CASES
}
for _case_id in (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
):
    PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_INTAKE_GATE_ARTIFACTS[
        _case_id
    ].append("patch-proposal-delivery-trust-case-candidate.json")
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-candidate",
    "blocked-invalid-candidate",
    "blocked-missing-product-loop-run",
    "blocked-product-loop-hash-mismatch",
    "blocked-missing-dual-loop-evidence",
    "blocked-dual-loop-evidence-mismatch",
    "blocked-dual-loop-gate-blocked",
    "blocked-ai-review-only",
    "blocked-automatic-customer-send",
    "blocked-customer-visible-send",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-delivery-trust-case-bridge-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_CASES
}
for _case_id in (
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
):
    PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_ARTIFACTS[
        _case_id
    ].append("patch-proposal-controlled-follow-up-feedback-delivery-trust-case-handoff-refs.json")
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BOUNDARY_GATE_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-bridge-receipt",
    "blocked-invalid-bridge-receipt",
    "blocked-missing-handoff-refs",
    "blocked-handoff-refs-mismatch",
    "blocked-missing-reconstruction",
    "blocked-passive-reconstruction",
    "blocked-unsupported-reconstruction-source",
    "blocked-missing-product-loop-ref",
    "blocked-missing-dual-loop-ref",
    "blocked-missing-delivery-trust-case-ref",
    "blocked-raw-follow-up-body",
    "blocked-automatic-customer-send",
    "blocked-customer-visible-follow-up",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BOUNDARY_GATE_ARTIFACTS = {
    case_id: [
        "patch-proposal-controlled-follow-up-feedback-boundary-receipt.json",
        *(
            ["patch-proposal-follow-up-feedback-boundary-reconstruction.json"]
            if case_id != "blocked-missing-reconstruction"
            else []
        ),
        *(
            ["patch-proposal-controlled-follow-up-feedback-envelope-refs.json"]
            if case_id in {"pass-customer-signal", "pass-operator-signal", "pass-host-platform-agent-signal"}
            else []
        ),
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BOUNDARY_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REHEARSAL_CASES = [
    "pass-customer-signal",
    "pass-operator-signal",
    "pass-host-platform-agent-signal",
    "blocked-missing-envelope-refs",
    "blocked-invalid-envelope-refs",
    "blocked-passive-rehearsal",
    "blocked-unsupported-rehearsal-source",
    "blocked-missing-active-reconstruction-ref",
    "blocked-missing-product-loop-ref",
    "blocked-missing-dual-loop-ref",
    "blocked-missing-delivery-trust-ref",
    "blocked-raw-follow-up-preview",
    "blocked-customer-visible-draft",
    "blocked-automatic-customer-send",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REHEARSAL_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-rehearsal-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REHEARSAL_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_OUTCOME_CASES = [
    "pass-human-operator",
    "pass-host-platform-agent",
    "blocked-rehearsal-blocked",
    "blocked-missing-external-actor",
    "blocked-missing-action-reference",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-body",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-send-payload",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_OUTCOME_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-outcome-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_OUTCOME_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_LOOP_CLOSURE_CASES = [
    "pass-archive-cycle",
    "pass-reopen-as-intake",
    "pass-external-owner-review",
    "blocked-missing-outcome-receipt",
    "blocked-outcome-blocked",
    "blocked-missing-external-actor-ref",
    "blocked-missing-action-ref",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-body",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-send-payload",
    "blocked-automatic-recontact",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_LOOP_CLOSURE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-loop-closure-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_LOOP_CLOSURE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BRIDGE_CASES = [
    "pass",
    "blocked-missing-closure-receipt",
    "blocked-closure-blocked",
    "blocked-archive-action",
    "blocked-external-owner-action",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-body",
    "blocked-raw-customer-reply",
    "blocked-customer-identity",
    "blocked-send-payload",
    "blocked-automatic-recontact",
    "blocked-automatic-intake-creation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BRIDGE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-reopen-intake-bridge-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BRIDGE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_INTAKE_GATE_CASES = [
    "pass",
    "blocked-missing-bridge-receipt",
    "blocked-bridge-blocked",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-customer-identity",
    "blocked-send-payload",
    "blocked-automatic-contact",
    "blocked-automatic-intake-creation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_INTAKE_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_INTAKE_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BACKLOG_BRIDGE_CASES = [
    "pass",
    "blocked-missing-gate-receipt",
    "blocked-gate-blocked",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-product-loop-target",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-customer-identity",
    "blocked-automatic-customer-contact",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-prioritization",
    "blocked-automatic-execution",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BACKLOG_BRIDGE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BACKLOG_BRIDGE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BACKLOG_BRIDGE_ARTIFACTS[
    "pass"
] = [
    "patch-proposal-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json",
    "product-loop-backlog-signal.json",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_OWNER_GATE_CASES = [
    "pass",
    "blocked-missing-backlog-bridge-receipt",
    "blocked-bridge-blocked",
    "blocked-missing-gate-ref",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-backlog-signal-ref",
    "blocked-missing-owner-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-raw-backlog-data",
    "blocked-customer-identity",
    "blocked-automatic-customer-contact",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-priority-assignment",
    "blocked-skip-to-delivery-harness",
    "blocked-automatic-execution",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_OWNER_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_OWNER_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_OWNER_GATE_ARTIFACTS[
    "pass"
] = [
    "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt.json",
    "patch-proposal-product-spec-eval-candidate.json",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_SPEC_EVAL_AUTHORING_GATE_CASES = [
    "pass",
    "blocked-missing-product-owner-receipt",
    "blocked-product-owner-blocked",
    "blocked-missing-spec-eval-candidate-ref",
    "blocked-missing-gate-ref",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-backlog-signal-ref",
    "blocked-missing-product-owner-ref",
    "blocked-missing-authoring-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-spec-body",
    "blocked-raw-eval-body",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-raw-backlog-data",
    "blocked-customer-identity",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-priority-assignment",
    "blocked-automatic-execution",
    "blocked-skip-to-delivery-trust",
    "blocked-customer-contact",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_SPEC_EVAL_AUTHORING_GATE_ARTIFACTS = {
    case_id: ["patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json"]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_SPEC_EVAL_AUTHORING_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_SPEC_EVAL_AUTHORING_GATE_ARTIFACTS[
    "pass"
] = [
    "patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt.json",
    "patch-proposal-product-loop-brief-candidate.json",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_LOOP_BRIEF_INTAKE_GATE_CASES = [
    "pass",
    "blocked-missing-authoring-receipt",
    "blocked-authoring-blocked",
    "blocked-missing-brief-candidate-ref",
    "blocked-missing-gate-ref",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-backlog-signal-ref",
    "blocked-missing-product-owner-ref",
    "blocked-missing-product-loop-reconstruction",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-raw-brief-body",
    "blocked-raw-spec-body",
    "blocked-raw-eval-body",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-raw-backlog-data",
    "blocked-customer-identity",
    "blocked-automatic-backlog-creation",
    "blocked-automatic-priority-assignment",
    "blocked-ai-review-only",
    "blocked-skip-to-delivery-trust",
    "blocked-delivery-trust-invocation",
    "blocked-automatic-execution",
    "blocked-customer-contact",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_LOOP_BRIEF_INTAKE_GATE_ARTIFACTS = {
    case_id: [
        "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json"
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_LOOP_BRIEF_INTAKE_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_LOOP_BRIEF_INTAKE_GATE_ARTIFACTS[
    "pass"
] = [
    "patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt.json",
    "product-loop-scenario.json",
    "product-loop-run.json",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_DELIVERY_TRUST_INTAKE_GATE_CASES = [
    "pass",
    "blocked-missing-product-loop-intake-receipt",
    "blocked-product-loop-intake-blocked",
    "blocked-missing-product-loop-run",
    "blocked-product-loop-run-blocked",
    "blocked-missing-product-loop-scenario",
    "blocked-missing-authoring-receipt-ref",
    "blocked-missing-spec-eval-candidate-ref",
    "blocked-missing-brief-candidate-ref",
    "blocked-missing-gate-ref",
    "blocked-missing-bridge-ref",
    "blocked-missing-closure-ref",
    "blocked-missing-outcome-ref",
    "blocked-missing-action-ref",
    "blocked-missing-actor-ref",
    "blocked-missing-intake-candidate-ref",
    "blocked-missing-intake-item-ref",
    "blocked-missing-backlog-signal-ref",
    "blocked-missing-product-owner-ref",
    "blocked-missing-failure-contract",
    "blocked-missing-sandbox-receipt",
    "blocked-missing-attention-summary",
    "blocked-missing-dual-loop-gate",
    "blocked-dual-loop-blocked",
    "blocked-sandbox-risk",
    "blocked-attention-missing",
    "blocked-missing-claim-boundary",
    "blocked-missing-privacy-boundary",
    "blocked-missing-attention-reconstruction",
    "blocked-ai-review-only",
    "blocked-raw-brief-body",
    "blocked-raw-spec-body",
    "blocked-raw-eval-body",
    "blocked-raw-follow-up-data",
    "blocked-raw-customer-data",
    "blocked-raw-backlog-data",
    "blocked-customer-identity",
    "blocked-delivery-trust-harness-invocation",
    "blocked-customer-handoff-package",
    "blocked-automatic-execution",
    "blocked-customer-contact",
    "blocked-product-loop-backlog-mutation",
    "blocked-source-mutation",
    "blocked-production-mutation",
    "blocked-external-publication-payload",
    "blocked-model-call",
    "blocked-secret",
    "blocked-model-credential",
]
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_DELIVERY_TRUST_INTAKE_GATE_ARTIFACTS = {
    case_id: [
        "patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt.json"
    ]
    for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_DELIVERY_TRUST_INTAKE_GATE_CASES
}
PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_DELIVERY_TRUST_INTAKE_GATE_ARTIFACTS[
    "pass"
] = [
    "patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt.json",
    "patch-proposal-delivery-trust-case-candidate.json",
]
DELIVERY_TRUST_CASE_HARNESS_CASES = {
    "pass": [
        "product-loop-scenario.json",
        "product-loop-run.json",
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "delivery-trust-receipt.json",
        "customer-handoff-package.json",
        "delivery-trust-case.json",
    ],
    "blocked-product-loop": [
        "product-loop-scenario.json",
        "product-loop-run.json",
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "delivery-trust-receipt.json",
        "customer-handoff-package.json",
        "delivery-trust-case.json",
    ],
    "blocked-dual-loop": [
        "product-loop-scenario.json",
        "product-loop-run.json",
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "delivery-trust-receipt.json",
        "delivery-trust-case.json",
    ],
    "blocked-customer-handoff": [
        "product-loop-scenario.json",
        "product-loop-run.json",
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "delivery-trust-receipt.json",
        "customer-handoff-package.json",
        "delivery-trust-case.json",
    ],
    "blocked-ai-review-only": [
        "product-loop-scenario.json",
        "product-loop-run.json",
        "failure-contract.json",
        "sandbox-receipt.json",
        "attention-reconstruction-trace.json",
        "attention-reconstruction-summary.json",
        "dual-loop-gate-receipt.json",
        "delivery-trust-receipt.json",
        "customer-handoff-package.json",
        "delivery-trust-case.json",
    ],
}


PACK_FILES: list[tuple[str, str, str]] = [
    ("README.md", "root_doc", "Repository overview and local-first launch entrypoint."),
    ("QUICKSTART.md", "root_doc", "Beginner-friendly quickstart guide."),
    ("START_HERE.command", "launcher", "Double-click macOS beginner launcher."),
    ("docs/getting-started.md", "operator_doc", "Step-by-step first-run guide."),
    ("docs/skill-mode.md", "operator_doc", "Skill Mode startup and CLI guide."),
    ("docs/adoption.md", "operator_doc", "Clean-clone and published-image adoption guide."),
    ("docs/github-launch.md", "operator_doc", "GitHub launch, tag, release, and published-image verification guide."),
    ("docs/platform-agent-integrations.md", "operator_doc", "General external platform Agent integration guide."),
    ("docs/cognitive-loop-adoption-cookbook.md", "operator_doc", "Scenario cookbook for Kimi, Codex, WorkBuddy, and private platform Agent Cognitive Loop operations."),
    ("docs/platform-agent-release-replay.md", "operator_doc", "Release-asset platform Agent replay simulator guide."),
    ("docs/platform-plugin-downloads.md", "operator_doc", "GitHub Release download guide for Codex, Kimi, WorkBuddy, and Hermes plugin packs."),
    ("docs/learning-enrichment.md", "operator_doc", "Learning Enrichment Layer context contract and micro-lesson export guide."),
    ("docs/okf-alignment.md", "operator_doc", "OKF-style Cognitive Black Box knowledge-bundle alignment guide."),
    ("docs/second-brain-handoff.md", "operator_doc", "Strict Obsidian, NotebookLM-style, and local archive handoff guide."),
    ("docs/obsidian-export.md", "operator_doc", "Obsidian export privacy and second-brain note guide."),
    ("docs/notebooklm-bridge.md", "operator_doc", "NotebookLM-style manual bridge contract."),
    ("docs/plugin-sdk.md", "operator_doc", "Plugin SDK hook, capability, and validation contract."),
    ("docs/plugin-registry.md", "operator_doc", "Plugin registry digest and local trust policy."),
    ("docs/plugins.md", "operator_doc", "Plugin examples, manifest, quarantine, and sample install guide."),
    ("docs/kimi-agent-gateway.md", "operator_doc", "Kimi-compatible HTTP Agent gateway guide."),
    ("docs/use-with-kimi.md", "operator_doc", "Kimi usage modes for copy-only, HTTP tools, and local Agent gateway."),
    ("docs/use-with-workbuddy.md", "operator_doc", "CodeBuddy/WorkBuddy inline learning workflow, fallback runtime, and first learning flow guide."),
    ("docs/use-with-hermes.md", "operator_doc", "Hermes Agent Skill setup, local runtime, and first learning flow guide."),
    ("docs/workbuddy-field-report.md", "operator_doc", "Real CodeBuddy CLI field validation report and remaining first-lesson acceptance boundary."),
    ("docs/operator-drill.md", "operator_doc", "External platform operator drill and transcript guide."),
    ("docs/self-hosting.md", "operator_doc", "Docker/Skill Mode self-hosting guide."),
    ("docs/self-host-reliability.md", "operator_doc", "Bounded self-host soak, recovery, and trace-retention guide."),
    ("docs/scheduled-reliability.md", "operator_doc", "Scheduled source-build and published-image restart/recovery contract."),
    ("docs/generated-evidence-topology.md", "operator_doc", "Release-distribution evidence refresh and fixed-point convergence guide."),
    ("docs/security.md", "operator_doc", "Local-first security model and recovery hardening guide."),
    ("docs/security-baseline.md", "operator_doc", "GitHub Actions and non-root container security baseline."),
    ("docs/commercial-readiness.md", "operator_doc", "Commercial readiness contract, hosted-service boundaries, and local-first launch limits."),
    ("docs/adoption-telemetry.md", "operator_doc", "Local aggregate adoption telemetry and PMF readiness privacy contract."),
    ("docs/ecosystem-submission.md", "operator_doc", "Ecosystem submission metadata, verification, and no-frontend launch guide."),
    ("docs/support-desk.md", "operator_doc", "GitHub-first support desk, support bundle, and maintainer triage playbook."),
    ("docs/adopter-onboarding.md", "operator_doc", "First external adopter walkthrough and failure fallback guide."),
    ("docs/maintainer-rotation.md", "operator_doc", "Maintainer SLA labels, release blocker handling, and rotation checklist."),
    ("docs/public-support-status.md", "operator_doc", "Public support status and maintainer dashboard publishing guide."),
    ("docs/adopter-evidence-archive.md", "operator_doc", "External adopter evidence archive and maintainer handoff guide."),
    ("docs/published-image-evidence.md", "operator_doc", "Published-image evidence and pull-timeout fallback classification guide."),
    ("docs/release-asset-adoption.md", "operator_doc", "GitHub Release asset adoption replay guide."),
    ("docs/release-asset-bootstrap.md", "operator_doc", "GitHub Release asset bootstrap entrypoint for external platform Agents."),
    ("docs/release-cleanroom-bootstrap.md", "operator_doc", "Release-only cleanroom bootloader guide for repo-free external adoption."),
    ("docs/release-checklist.md", "operator_doc", "Release gate checklist for platform adoption evidence."),
    ("docs/roadmap.md", "operator_doc", "Roadmap and release track for platform adoption goals."),
    ("docs/product-positioning.md", "operator_doc", "Canonical Delivery Clearance positioning and claim boundary."),
    ("docs/architecture.md", "operator_doc", "Protocol-first reference harness architecture and isolation boundary."),
    ("docs/naming-and-compatibility.md", "operator_doc", "Canonical naming, historical identifiers, and migration rules."),
    ("docs/cbb-protocol-v1-development-plan.md", "operator_doc", "CBB Protocol v1 implementation sequence and acceptance matrix."),
    ("docs/operating-model.md", "operator_doc", "Cognitive Black Box three-loop operating model and PR evidence rules."),
    ("docs/release-stack-policy.md", "operator_doc", "Release-stack recursion guard and batch archive policy."),
    ("docs/product-runway.md", "operator_doc", "Next product runway for Dual Loop trust protocol development."),
    ("docs/cognitive-loop-contracts.md", "operator_doc", "Cognitive Loop local contract bootstrap and privacy boundary guide."),
    ("docs/dual-loop-mvp.md", "operator_doc", "Dual-Loop MVP controlled-failure and attention-reconstruction boundary guide."),
    ("docs/dual-loop-scenario-harness.md", "operator_doc", "Dual Loop Trust Scenario Harness guide for customer delivery readiness."),
    ("docs/dual-loop-trust-scenario-pack.md", "operator_doc", "Portable Dual Loop trust scenario pack guide."),
    ("docs/product-loop-harness.md", "operator_doc", "Product Loop Harness guide for three-loop product development gating."),
    ("docs/product-loop-brief-intake.md", "operator_doc", "Product Loop Brief Intake Gate guide for consuming Product Spec/Eval briefs."),
    ("docs/end-to-end-trust-chain-harness.md", "operator_doc", "End-to-End Trust Chain Harness guide for external feedback to controlled customer handoff rehearsal."),
    ("docs/real-adopter-scenario-import.md", "operator_doc", "Real-Adopter Scenario Import guide for metadata-only field feedback to Product Loop evidence."),
    ("docs/spec-eval-scenario-execution-rehearsal.md", "operator_doc", "Spec/Eval Scenario Execution Rehearsal guide for controlled sandbox implementation rehearsal authorization."),
    ("docs/sandboxed-patch-proposal-rehearsal.md", "operator_doc", "Sandboxed Patch Proposal Rehearsal guide for metadata-only patch proposal envelopes."),
    ("docs/patch-proposal-operator-handoff-bridge.md", "operator_doc", "Patch Proposal Operator Handoff Bridge guide for metadata-only operator handoff refs."),
    ("docs/patch-proposal-acceptance-drill.md", "operator_doc", "Patch Proposal Acceptance Drill guide for metadata-only external operator continuation decisions."),
    ("docs/patch-proposal-external-work-order-pack.md", "operator_doc", "Patch Proposal External Work Order Pack guide for metadata-only host operator work-order packages."),
    ("docs/patch-proposal-external-operator-completion.md", "operator_doc", "Patch Proposal External Operator Completion guide for metadata-only completion receipts."),
    ("docs/patch-proposal-customer-handoff-boundary-gate.md", "operator_doc", "Patch Proposal Customer-Handoff Boundary Gate guide for metadata-only customer handoff preparation boundaries."),
    ("docs/patch-proposal-customer-delivery-envelope.md", "operator_doc", "Patch Proposal Customer Delivery Envelope guide for metadata-only customer delivery preparation envelopes."),
    ("docs/patch-proposal-customer-delivery-rehearsal.md", "operator_doc", "Patch Proposal Customer Delivery Rehearsal guide for metadata-only manual handoff readiness decisions."),
    ("docs/patch-proposal-customer-delivery-outcome.md", "operator_doc", "Patch Proposal Customer Delivery Outcome Receipt guide for metadata-only external handoff outcome records."),
    ("docs/patch-proposal-customer-feedback-intake.md", "operator_doc", "Patch Proposal Customer Feedback Intake Receipt guide for metadata-only response signal records."),
    ("docs/patch-proposal-customer-feedback-backlog-bridge.md", "operator_doc", "Patch Proposal Customer Feedback Backlog Bridge guide for metadata-only Product Loop backlog signals."),
    ("docs/patch-proposal-customer-feedback-product-owner-gate.md", "operator_doc", "Patch Proposal Customer Feedback Product Owner Gate guide for metadata-only spec/eval candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-spec-eval-authoring-gate.md", "operator_doc", "Patch Proposal Customer Feedback Spec/Eval Authoring Gate guide for metadata-only Product Loop brief candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-product-loop-brief-intake-gate.md", "operator_doc", "Patch Proposal Customer Feedback Product Loop Brief Intake Gate guide for metadata-only Product Loop scenario/run candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-delivery-trust-intake-gate.md", "operator_doc", "Patch Proposal Customer Feedback Delivery Trust Intake Gate guide for metadata-only Delivery Trust case candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-delivery-trust-case-bridge.md", "operator_doc", "Patch Proposal Customer Feedback Delivery Trust Case Bridge guide for metadata-only Delivery Trust case/handoff refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-boundary-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate guide for metadata-only follow-up envelope refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-rehearsal.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Rehearsal guide for metadata-only local rehearsal receipts."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-outcome.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt guide for metadata-only external follow-up outcome records."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake guide for metadata-only response signal records."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge guide for metadata-only Product Loop backlog signal refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-owner-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate guide for metadata-only spec/eval candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate guide for metadata-only Product Loop brief candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate guide for metadata-only Product Loop scenario/run candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate guide for metadata-only Delivery Trust case candidate boundaries."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge guide for metadata-only Delivery Trust case and handoff refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate guide for metadata-only follow-up envelope refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal guide for metadata-only local rehearsal receipts."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome guide for metadata-only external action outcome receipts."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure guide for metadata-only feedback-cycle closure decisions."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge guide for metadata-only reopen-intake candidate refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate guide for metadata-only Product Loop intake item refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge guide for metadata-only Product Loop backlog signal refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate guide for metadata-only spec/eval candidate receipts."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate guide for metadata-only Product Loop brief candidate refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate guide for metadata-only Product Loop scenario/run candidate refs."),
    ("docs/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate.md", "operator_doc", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate guide for metadata-only Delivery Trust case candidate refs."),
    ("docs/delivery-trust-case-harness.md", "operator_doc", "Delivery Trust Case Harness guide for end-to-end controlled customer-handoff decisions."),
    ("docs/delivery-trust-case-pack.md", "operator_doc", "Delivery Trust Case pack guide for ZIP-only external consumer verification."),
    ("docs/code-review-delivery-class.md", "operator_doc", "Code Review Delivery Class metadata-only handoff guide."),
    ("docs/client-report-delivery-class.md", "operator_doc", "Client Report Delivery Class metadata-only handoff guide."),
    ("docs/support-response-delivery-class.md", "operator_doc", "Support Response Delivery Class metadata-only handoff guide."),
    ("docs/external-feedback-receipt.md", "operator_doc", "External Feedback Receipt metadata-only product-loop feedback guide."),
    ("docs/external-feedback-backlog-bridge.md", "operator_doc", "External Feedback Backlog Bridge product-loop backlog guide."),
    ("docs/product-owner-prioritization-gate.md", "operator_doc", "Product Owner Prioritization Gate spec/eval candidate queue guide."),
    ("docs/product-spec-eval-authoring-gate.md", "operator_doc", "Product Spec/Eval Authoring Gate metadata-only brief guide."),
    ("docs/delivery-class-registry.md", "operator_doc", "Delivery Class Registry guide for protocol-supported handoff classes."),
    ("docs/trust-scenario-catalog.md", "operator_doc", "Trust Scenario Catalog guide for supported and blocked AI delivery scenarios."),
    ("docs/trust-scenario-decision-gate.md", "operator_doc", "Trust Scenario Decision Gate guide for deterministic local scenario handoff receipts."),
    ("docs/trust-model.md", "operator_doc", "Cognitive Black Box AI delivery trust model."),
    ("docs/delivery-trust-receipt.md", "operator_doc", "Delivery Trust Receipt contract and verifier guide."),
    ("docs/customer-handoff-package.md", "operator_doc", "CustomerHandoffPackage portable evidence package guide."),
    ("docs/protocol.md", "operator_doc", "Cognitive Black Box protocol core and AI delivery trust boundary guide."),
    ("docs/cbb-protocol-v1-contracts.md", "operator_doc", "Canonical Protocol v1 schemas, serialization, fixtures, and compatibility guide."),
    ("docs/cbb-protocol-v1-kernel.md", "operator_doc", "Canonical deterministic Trust Kernel and runtime-isolation guide."),
    ("docs/cbb-protocol-v1-provenance.md", "operator_doc", "Canonical local signing, offline verification, and claim-boundary guide."),
    ("docs/cbb-protocol-v1-scenarios-and-qualification.md", "operator_doc", "Scenario, affected-party, MRU, and scoped capability policy guide."),
    ("docs/receipt-protocol.md", "operator_doc", "Cognitive Black Box metadata-only receipt protocol guide."),
    ("docs/adapters/study-anything.md", "operator_doc", "Study Anything adapter boundary for the Cognitive Black Box protocol."),
    (".cognitive-loop/loops.yaml", "cognitive_loop_contract", "Machine-readable three-loop operating model contract."),
    (".cognitive-loop/release-stack-policy.yaml", "cognitive_loop_contract", "Machine-readable release-stack recursion guard contract."),
    (".cognitive-loop/watchers.yaml", "cognitive_loop_contract", "Optional Cognitive Loop manual watcher ingest contract."),
    ("platform/mastra/README.md", "mastra_adapter", "Copy-ready Mastra adapter operator guide."),
    ("platform/mastra/manifest.json", "mastra_adapter", "Machine-readable Mastra adapter contract-pack manifest."),
    ("platform/mastra/cognitive-loop-mastra-adapter.ts", "mastra_adapter", "TypeScript Mastra workflow scaffold for Cognitive Loop HITL mapping."),
    ("docs/cognitive-loop-code-review.md", "operator_doc", "Cognitive Loop advisory code review guide."),
    ("docs/github-review-agent-workflow.md", "operator_doc", "Manual GitHub Actions workflow template guide for external Review Agent evidence."),
    ("docs/agent-eval.md", "operator_doc", "Agent and retrieval eval guide."),
    ("docs/eval-frameworks.md", "operator_doc", "External eval framework selection, adapter boundary, and marketplace harness guide."),
    ("docs/real-agent-eval-bridge.md", "operator_doc", "User-owned real-agent eval receipt bridge and learning-quality harness guide."),
    ("docs/api.md", "operator_doc", "HTTP API reference for platform workspaces."),
    ("docs/release-notes/v0.3.31-alpha.md", "release_doc", "Release notes for this adoption pack."),
    ("evals/README.md", "eval", "External eval overview and native/optional adapter guide."),
    ("evals/review-agent/README.md", "eval", "Offline Cognitive Loop Review Agent eval fixture guide."),
    ("evals/review-agent/cases/approved-docs.json", "eval_fixture", "Review Agent approved decision synthetic diff case."),
    ("evals/review-agent/cases/needs-review-test-gap.json", "eval_fixture", "Review Agent needs-review synthetic diff case."),
    ("evals/review-agent/cases/needs-fix-command-injection.json", "eval_fixture", "Review Agent needs-fix critical security synthetic diff case."),
    ("evals/review-agent/golden/approved-docs.json", "eval_fixture", "Review Agent approved golden report."),
    ("evals/review-agent/golden/needs-review-test-gap.json", "eval_fixture", "Review Agent needs-review golden report."),
    ("evals/review-agent/golden/needs-fix-command-injection.json", "eval_fixture", "Review Agent needs-fix golden report."),
    ("evals/review-agent/bad/privacy-leak.json", "eval_fixture", "Review Agent negative privacy-leak report fixture."),
    ("platform/study-anything-platform-tools.json", "tool_manifest", "Source platform tool contract."),
    ("platform/ecosystem-submission.json", "submission_manifest", "Machine-readable ecosystem submission metadata."),
    ("platform/prompts/cognitive-loop-review-agent.json", "prompt_contract", "External Cognitive Loop Review Agent JSON-only prompt contract."),
    ("platform/schemas/cognitive-loop-review-agent-report.schema.json", "schema", "External Cognitive Loop Review Agent final report JSON Schema."),
    ("platform/schemas/cognitive-loop-pr-ci-receipt.schema.json", "schema", "Cognitive Loop PR CI receipt JSON Schema for offline platform-Agent validation."),
    ("platform/schemas/cognitive-loop-pr-ci-source.schema.json", "schema", "Cognitive Loop PR CI source JSON Schema for offline platform-Agent validation."),
    ("platform/schemas/dual-loop/failure-contract-v1.schema.json", "schema", "Dual-Loop failure contract JSON Schema."),
    ("platform/schemas/dual-loop/sandbox-receipt-v1.schema.json", "schema", "Dual-Loop sandbox receipt JSON Schema."),
    ("platform/schemas/dual-loop/attention-reconstruction-trace-v1.schema.json", "schema", "Dual-Loop attention reconstruction trace JSON Schema."),
    ("platform/schemas/dual-loop/attention-reconstruction-summary-v1.schema.json", "schema", "Dual-Loop attention reconstruction summary JSON Schema."),
    ("platform/schemas/dual-loop/dual-loop-gate-receipt-v1.schema.json", "schema", "Dual-Loop propagation gate receipt JSON Schema."),
    ("platform/schemas/delivery-trust/delivery-trust-receipt-v1.schema.json", "schema", "Delivery Trust Receipt JSON Schema."),
    ("platform/schemas/customer-handoff/customer-handoff-package-v1.schema.json", "schema", "CustomerHandoffPackage JSON Schema."),
    ("platform/schemas/cbb/cbb.trust-policy.v1.schema.json", "schema", "Canonical CBB Protocol v1 trust policy JSON Schema."),
    ("platform/schemas/cbb/cbb.evidence-bundle.v1.schema.json", "schema", "Canonical CBB Protocol v1 evidence bundle JSON Schema."),
    ("platform/schemas/cbb/cbb.qualified-reconstruction.v1.schema.json", "schema", "Canonical CBB Protocol v1 qualified reconstruction JSON Schema."),
    ("platform/schemas/cbb/cbb.gate-decision.v1.schema.json", "schema", "Canonical CBB Protocol v1 gate decision JSON Schema."),
    ("platform/schemas/cbb/cbb.delivery-trust-receipt.v1.schema.json", "schema", "Canonical CBB Protocol v1 delivery trust receipt JSON Schema."),
    ("platform/schemas/cbb/cbb.receipt-provenance.v1.schema.json", "schema", "Canonical CBB Protocol v1 receipt provenance JSON Schema."),
    ("platform/schemas/cbb/claim-boundary-v1.schema.json", "schema", "Cognitive Black Box Claim Boundary JSON Schema."),
    ("platform/schemas/cbb/trust-root-v1.schema.json", "schema", "Cognitive Black Box Trust Root JSON Schema."),
    ("platform/schemas/cbb/reviewer-reconstruction-receipt-v1.schema.json", "schema", "Cognitive Black Box Reviewer Reconstruction Receipt JSON Schema."),
    ("platform/schemas/cbb/risk-owner-scope-v1.schema.json", "schema", "Cognitive Black Box Risk Owner Scope JSON Schema."),
    ("platform/schemas/cbb/delivery-decision-receipt-v1.schema.json", "schema", "Cognitive Black Box Delivery Decision Receipt JSON Schema."),
    ("platform/schemas/cbb/cbb-receipt-chain-v1.schema.json", "schema", "Cognitive Black Box tamper-evident receipt chain JSON Schema."),
    ("platform/schemas/cbb/cbb-self-intake-receipt-v1.schema.json", "schema", "Cognitive Black Box self-intake receipt JSON Schema."),
    ("platform/schemas/cbb/cbb-delivery-evidence-pack-v1.schema.json", "schema", "Cognitive Black Box delivery evidence pack JSON Schema."),
    ("platform/schemas/cbb/cbb-delivery-scenario-v1.schema.json", "schema", "Cognitive Black Box delivery scenario JSON Schema."),
    ("platform/schemas/cbb/cbb-external-feedback-intake-v1.schema.json", "schema", "Cognitive Black Box external feedback intake JSON Schema."),
    ("platform/schemas/cbb/cbb-tri-loop-run-v1.schema.json", "schema", "Cognitive Black Box tri-loop run JSON Schema."),
    ("platform/schemas/cbb/product-loop-scenario-v1.schema.json", "schema", "Product Loop Harness scenario JSON Schema."),
    ("platform/schemas/cbb/product-loop-run-v1.schema.json", "schema", "Product Loop Harness run JSON Schema."),
    ("platform/schemas/cbb/product-loop-brief-intake-receipt-v1.schema.json", "schema", "Product Loop Brief Intake Gate receipt JSON Schema."),
    ("platform/schemas/cbb/end-to-end-trust-chain-harness-v1.schema.json", "schema", "End-to-End Trust Chain Harness JSON Schema."),
    ("platform/schemas/cbb/real-adopter-scenario-import-v1.schema.json", "schema", "Real-Adopter Scenario Import JSON Schema."),
    ("platform/schemas/cbb/spec-eval-scenario-execution-rehearsal-v1.schema.json", "schema", "Spec/Eval Scenario Execution Rehearsal JSON Schema."),
    ("platform/schemas/cbb/sandboxed-patch-proposal-rehearsal-v1.schema.json", "schema", "Sandboxed Patch Proposal Rehearsal JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-operator-handoff-bridge-v1.schema.json", "schema", "Patch Proposal Operator Handoff Bridge JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-acceptance-drill-v1.schema.json", "schema", "Patch Proposal Acceptance Drill JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-external-work-order-pack-v1.schema.json", "schema", "Patch Proposal External Work Order Pack JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-external-operator-completion-v1.schema.json", "schema", "Patch Proposal External Operator Completion JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-handoff-boundary-gate-v1.schema.json", "schema", "Patch Proposal Customer-Handoff Boundary Gate JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-delivery-envelope-v1.schema.json", "schema", "Patch Proposal Customer Delivery Envelope JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-delivery-rehearsal-v1.schema.json", "schema", "Patch Proposal Customer Delivery Rehearsal JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-delivery-outcome-v1.schema.json", "schema", "Patch Proposal Customer Delivery Outcome Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-intake-v1.schema.json", "schema", "Patch Proposal Customer Feedback Intake Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-backlog-bridge-v1.schema.json", "schema", "Patch Proposal Customer Feedback Backlog Bridge JSON Schema."),
    ("platform/schemas/cbb/product-loop-backlog-signal-v1.schema.json", "schema", "Product Loop backlog signal JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-product-owner-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Product Owner Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-product-owner-receipt-v1.schema.json", "schema", "Patch Proposal Customer Feedback Product Owner Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-product-spec-eval-candidate-v1.schema.json", "schema", "Patch Proposal Product Spec/Eval Candidate JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-spec-eval-authoring-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Spec/Eval Authoring Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-spec-eval-authoring-receipt-v1.schema.json", "schema", "Patch Proposal Customer Feedback Spec/Eval Authoring Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-product-loop-brief-candidate-v1.schema.json", "schema", "Patch Proposal Product Loop Brief Candidate JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-product-loop-brief-intake-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Product Loop Brief Intake Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-product-loop-brief-intake-receipt-v1.schema.json", "schema", "Patch Proposal Customer Feedback Product Loop Brief Intake Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-delivery-trust-intake-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Delivery Trust Intake Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-delivery-trust-intake-receipt-v1.schema.json", "schema", "Patch Proposal Customer Feedback Delivery Trust Intake Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-delivery-trust-case-candidate-v1.schema.json", "schema", "Patch Proposal Delivery Trust Case Candidate JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-delivery-trust-case-bridge-v1.schema.json", "schema", "Patch Proposal Customer Feedback Delivery Trust Case Bridge report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-delivery-trust-case-bridge-receipt-v1.schema.json", "schema", "Patch Proposal Delivery Trust Case Bridge Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-boundary-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-boundary-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Boundary Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-rehearsal-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Rehearsal report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-rehearsal-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Rehearsal Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-outcome-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-outcome-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Outcome Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-intake-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-intake-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Intake Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-owner-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-product-owner-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Product Owner Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-spec-eval-authoring-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Spec/Eval Authoring Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-product-loop-brief-intake-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Product Loop Brief Intake Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-delivery-trust-intake-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Delivery Trust Intake Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-delivery-trust-case-bridge-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Delivery Trust Case Bridge Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-boundary-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Boundary Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-rehearsal-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Rehearsal Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-outcome-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Outcome Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-loop-closure-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Loop Closure Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-reopen-intake-bridge-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Reopen Intake Bridge Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-reopen-intake-gate-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Reopen Intake Gate Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Reopen Intake Product Owner Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Receipt JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate-v1.schema.json", "schema", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate report JSON Schema."),
    ("platform/schemas/cbb/patch-proposal-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-receipt-v1.schema.json", "schema", "Patch Proposal Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Receipt JSON Schema."),
    ("platform/schemas/delivery-trust/delivery-trust-case-v1.schema.json", "schema", "Delivery Trust Case JSON Schema."),
    ("platform/schemas/delivery-trust/code-review-handoff-case-v1.schema.json", "schema", "Code Review Delivery Class handoff JSON Schema."),
    ("platform/schemas/delivery-trust/client-report-handoff-case-v1.schema.json", "schema", "Client Report Delivery Class handoff JSON Schema."),
    ("platform/schemas/delivery-trust/support-response-handoff-case-v1.schema.json", "schema", "Support Response Delivery Class handoff JSON Schema."),
    ("platform/schemas/delivery-trust/external-feedback-receipt-v1.schema.json", "schema", "External Feedback Receipt JSON Schema."),
    ("platform/schemas/delivery-trust/external-feedback-backlog-bridge-v1.schema.json", "schema", "External Feedback Backlog Bridge JSON Schema."),
    ("platform/schemas/delivery-trust/product-loop-backlog-item-v1.schema.json", "schema", "Product Loop backlog item JSON Schema."),
    ("platform/schemas/delivery-trust/product-owner-prioritization-receipt-v1.schema.json", "schema", "Product Owner Prioritization Gate receipt JSON Schema."),
    ("platform/schemas/delivery-trust/product-spec-eval-candidate-v1.schema.json", "schema", "Product spec/eval candidate JSON Schema."),
    ("platform/schemas/delivery-trust/product-spec-eval-authoring-receipt-v1.schema.json", "schema", "Product Spec/Eval Authoring Gate receipt JSON Schema."),
    ("platform/schemas/delivery-trust/product-spec-eval-brief-v1.schema.json", "schema", "Product Spec/Eval brief JSON Schema."),
    ("platform/schemas/workbuddy-learning-input-v1.schema.json", "schema", "WorkBuddy inline learning input JSON Schema."),
    ("platform/schemas/workbuddy-learning-output-v1.schema.json", "schema", "WorkBuddy inline learning output JSON Schema."),
    ("fixtures/workbuddy-learning-flow/deepseek-pm-interview/input.json", "fixture", "WorkBuddy inline DeepSeek PM interview fixture input."),
    ("fixtures/workbuddy-learning-flow/deepseek-pm-interview/expected-boundary.json", "fixture", "WorkBuddy inline privacy and quality boundary fixture."),
    ("fixtures/real-agent-eval-bridge/pass.json", "fixture", "Passing user-owned real-agent eval receipt bridge fixture."),
    ("fixtures/real-agent-eval-bridge/missing-model-call.json", "fixture", "Negative real-agent eval bridge fixture for missing model-call evidence."),
    ("fixtures/real-agent-eval-bridge/adapter-failed.json", "fixture", "Negative real-agent eval bridge fixture for failed adapter metrics."),
    ("fixtures/workbuddy-real-agent-learning-quality/pass.json", "fixture", "Passing WorkBuddy/Kimi/Codex real-agent learning-quality fixture."),
    ("fixtures/workbuddy-real-agent-learning-quality/deterministic-only.json", "fixture", "Negative learning-quality fixture for deterministic-only evidence."),
    ("fixtures/workbuddy-real-agent-learning-quality/mechanical-restatement.json", "fixture", "Negative learning-quality fixture for mechanical restatement."),
    ("fixtures/workbuddy-real-agent-learning-quality/missing-citations.json", "fixture", "Negative learning-quality fixture for missing citation grounding."),
    ("fixtures/workbuddy-real-agent-learning-quality/high-cost-low-quality.json", "fixture", "Negative learning-quality fixture for high-cost low-quality output."),
    ("scripts/workbuddy_learning_flow.py", "cli", "WorkBuddy inline learning flow CLI."),
    ("scripts/verify_workbuddy_inline_learning_flow.py", "verification", "Verify WorkBuddy inline flow runtime, privacy, source-bound, and quality boundaries."),
    ("scripts/cognitive_loop_review_agent_handoff.py", "cli", "Prepare ephemeral external Review Agent handoff requests and validate returned JSON reports."),
    ("scripts/cognitive_loop_review_agent_receipt.py", "cli", "Build and validate metadata-only external Review Agent CI receipts."),
    ("scripts/cognitive_loop_review_agent_pr_comment.py", "cli", "Build and validate metadata-only external Review Agent PR comment packs."),
    ("scripts/cognitive_loop_review_agent_acceptance_bundle.py", "cli", "Build and validate metadata-only external Review Agent acceptance bundles."),
    ("platform/workflows/cognitive-loop-review-agent-manual.yml", "workflow_template", "Manual GitHub Actions template for metadata-only external Review Agent evidence."),
    ("scripts/cognitive_loop_review_agent_policy_gate.py", "cli", "Evaluate metadata-only Review Agent evidence against advisory, soft, or strict policy gates."),
    ("scripts/verify_cognitive_loop_review_agent_policy_gate.py", "verification", "Verify metadata-only Review Agent policy gate behavior and privacy boundaries."),
    ("scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py", "verification", "Verify external adopters can install the Review Agent workflow from the adoption pack and reproduce policy gate behavior."),
    ("scripts/verify_cognitive_loop_review_agent_adoption_drill.py", "verification", "Verify the full zip-only Review Agent adoption drill from acceptance bundle through policy gate and workflow install."),
    ("platform/generated/study-anything-platform-openapi.json", "tool_import", "OpenAPI 3.1 import asset."),
    ("platform/generated/study-anything-openai-tools.json", "tool_import", "OpenAI-compatible function tools."),
    ("platform/generated/study-anything-tool-catalog.md", "tool_catalog", "Human-readable platform tool catalog."),
    ("platform/generated/study-anything-platform-bundle.json", "bundle_manifest", "Source file manifest for platform assets."),
    ("platform/generated/study-anything-okf-alignment.json", "submission_report", "OKF-style Cognitive Black Box knowledge-bundle verification report."),
    ("platform/generated/study-anything-cognitive-loop-contracts.json", "submission_report", "Cognitive Loop contract bootstrap verification report."),
    ("platform/generated/study-anything-operating-model-loops.json", "submission_report", "Cognitive Black Box three-loop operating model verification report."),
    ("platform/generated/study-anything-release-stack-policy.json", "submission_report", "Release-stack recursion guard and product runway verification report."),
    ("platform/generated/study-anything-dual-loop-contracts.json", "submission_report", "Dual-Loop contract schema and privacy verification report."),
    ("platform/generated/study-anything-failure-sandbox-lite.json", "submission_report", "Dual-Loop Failure Sandbox Lite CLI verification report."),
    ("platform/generated/study-anything-attention-reconstruction-lite.json", "submission_report", "Dual-Loop Attention Reconstruction Lite CLI verification report."),
    ("platform/generated/study-anything-dual-loop-gate.json", "submission_report", "Dual-Loop propagation gate pass/fail fixture verification report."),
    ("platform/generated/study-anything-delivery-trust-receipt.json", "submission_report", "Delivery Trust Receipt verification report for controlled customer handoff."),
    ("platform/generated/study-anything-delivery-trust-receipt.html", "submission_report", "Delivery Trust Receipt verification HTML report."),
    ("platform/generated/study-anything-customer-handoff-package.json", "submission_report", "Customer Handoff Package verification report and package metadata."),
    ("platform/generated/study-anything-customer-handoff-package.html", "submission_report", "Customer Handoff Package verification HTML report."),
    ("platform/generated/study-anything-customer-handoff-package.zip", "submission_report", "Portable metadata-only Customer Handoff Package archive."),
    ("platform/generated/study-anything-dual-loop-scenario-harness.json", "submission_report", "Dual Loop Trust Scenario Harness verification report for customer delivery readiness."),
    ("platform/generated/study-anything-dual-loop-trust-scenario-pack.json", "submission_report", "Portable Dual Loop trust scenario pack sidecar manifest."),
    ("platform/generated/study-anything-dual-loop-trust-scenario-pack.md", "submission_report", "Portable Dual Loop trust scenario pack operator summary."),
    ("platform/generated/study-anything-dual-loop-trust-scenario-pack.zip", "submission_report", "Portable metadata-only Dual Loop trust scenario pack archive."),
    ("platform/generated/study-anything-dual-loop-trust-scenario-pack.sha256", "submission_report", "Portable Dual Loop trust scenario pack archive checksum."),
    ("platform/generated/study-anything-external-security-audit-pack.json", "security_audit_pack", "Machine-readable external security audit preparation manifest."),
    ("platform/generated/study-anything-external-security-audit-pack.md", "security_audit_pack", "Human-readable external security audit preparation summary."),
    ("platform/generated/study-anything-external-security-audit-pack.zip", "security_audit_pack", "Portable metadata-only external security audit preparation archive."),
    ("platform/generated/study-anything-external-security-audit-pack.sha256", "security_audit_pack", "External security audit preparation archive checksum."),
    ("platform/generated/study-anything-dual-loop-trust-pack-consumer-walkthrough.json", "submission_report", "ZIP-only external consumer walkthrough report for the Dual Loop trust scenario pack."),
    ("platform/generated/study-anything-cbb-v1-contracts.json", "submission_report", "Canonical CBB Protocol v1 schema, fixture, canonicalization, and isolation report."),
    ("platform/generated/study-anything-cbb-v0-compatibility.json", "submission_report", "Deterministic non-expanding CBB v0-to-v1 compatibility report."),
    ("platform/generated/study-anything-cbb-v1-kernel.json", "submission_report", "Deterministic CBB Protocol v1 Trust Kernel verification report."),
    ("platform/generated/study-anything-cbb-runtime-isolation.json", "submission_report", "Static canonical Trust Kernel runtime-isolation report."),
    ("platform/generated/study-anything-cbb-v1-provenance.json", "submission_report", "Local Ed25519 provenance and offline verification report."),
    ("platform/generated/study-anything-cbb-v1-tamper-cases.json", "submission_report", "Canonical object and signature tamper rejection report."),
    ("platform/generated/study-anything-cbb-v1-scenarios.json", "submission_report", "Deterministic CBB Protocol v1 scenario decision report."),
    ("platform/generated/study-anything-cbb-v1-qualification.json", "submission_report", "Scoped MRU and human/model qualification verification report."),
    ("platform/generated/study-anything-cbb-protocol-contracts.json", "submission_report", "Cognitive Black Box protocol contract and privacy verification report."),
    ("platform/generated/study-anything-cbb-gate.json", "submission_report", "Cognitive Black Box deterministic delivery gate verification report."),
    ("platform/generated/study-anything-cbb-receipt-chain.json", "submission_report", "Cognitive Black Box tamper-evident receipt-chain verification report for PR 285."),
    ("platform/generated/study-anything-cbb-self-intake.json", "submission_report", "Cognitive Black Box self-intake verification report for PR 285."),
    ("platform/generated/study-anything-cbb-delivery-scenario-harness.json", "submission_report", "Cognitive Black Box tri-loop delivery scenario harness verification report."),
    ("platform/generated/study-anything-product-loop-harness.json", "submission_report", "Product Loop Harness verification report for three-loop product development gating."),
    ("platform/generated/study-anything-product-loop-brief-intake.json", "submission_report", "Product Loop Brief Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-product-loop-brief-intake.md", "submission_report", "Product Loop Brief Intake Gate operator summary."),
    ("platform/generated/study-anything-product-loop-brief-intake.html", "submission_report", "Product Loop Brief Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-end-to-end-trust-chain-harness.json", "submission_report", "End-to-End Trust Chain Harness metadata-only verification report."),
    ("platform/generated/study-anything-end-to-end-trust-chain-harness.md", "submission_report", "End-to-End Trust Chain Harness operator summary."),
    ("platform/generated/study-anything-end-to-end-trust-chain-harness.html", "submission_report", "End-to-End Trust Chain Harness static HTML verification report."),
    ("platform/generated/study-anything-real-adopter-scenario-import.json", "submission_report", "Real-Adopter Scenario Import metadata-only verification report."),
    ("platform/generated/study-anything-real-adopter-scenario-import.md", "submission_report", "Real-Adopter Scenario Import operator summary."),
    ("platform/generated/study-anything-real-adopter-scenario-import.html", "submission_report", "Real-Adopter Scenario Import static HTML verification report."),
    ("platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.json", "submission_report", "Spec/Eval Scenario Execution Rehearsal metadata-only verification report."),
    ("platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.md", "submission_report", "Spec/Eval Scenario Execution Rehearsal operator summary."),
    ("platform/generated/study-anything-spec-eval-scenario-execution-rehearsal.html", "submission_report", "Spec/Eval Scenario Execution Rehearsal static HTML verification report."),
    ("platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.json", "submission_report", "Sandboxed Patch Proposal Rehearsal metadata-only verification report."),
    ("platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.md", "submission_report", "Sandboxed Patch Proposal Rehearsal operator summary."),
    ("platform/generated/study-anything-sandboxed-patch-proposal-rehearsal.html", "submission_report", "Sandboxed Patch Proposal Rehearsal static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-operator-handoff-bridge.json", "submission_report", "Patch Proposal Operator Handoff Bridge metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-operator-handoff-bridge.md", "submission_report", "Patch Proposal Operator Handoff Bridge operator summary."),
    ("platform/generated/study-anything-patch-proposal-operator-handoff-bridge.html", "submission_report", "Patch Proposal Operator Handoff Bridge static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-acceptance-drill.json", "submission_report", "Patch Proposal Acceptance Drill metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-acceptance-drill.md", "submission_report", "Patch Proposal Acceptance Drill operator summary."),
    ("platform/generated/study-anything-patch-proposal-acceptance-drill.html", "submission_report", "Patch Proposal Acceptance Drill static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-external-work-order-pack.json", "submission_report", "Patch Proposal External Work Order Pack metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-external-work-order-pack.md", "submission_report", "Patch Proposal External Work Order Pack operator summary."),
    ("platform/generated/study-anything-patch-proposal-external-work-order-pack.html", "submission_report", "Patch Proposal External Work Order Pack static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-external-operator-completion.json", "submission_report", "Patch Proposal External Operator Completion metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-external-operator-completion.md", "submission_report", "Patch Proposal External Operator Completion operator summary."),
    ("platform/generated/study-anything-patch-proposal-external-operator-completion.html", "submission_report", "Patch Proposal External Operator Completion static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.json", "submission_report", "Patch Proposal Customer-Handoff Boundary Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.md", "submission_report", "Patch Proposal Customer-Handoff Boundary Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.html", "submission_report", "Patch Proposal Customer-Handoff Boundary Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-envelope.json", "submission_report", "Patch Proposal Customer Delivery Envelope metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-envelope.md", "submission_report", "Patch Proposal Customer Delivery Envelope operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-envelope.html", "submission_report", "Patch Proposal Customer Delivery Envelope static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.json", "submission_report", "Patch Proposal Customer Delivery Rehearsal metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.md", "submission_report", "Patch Proposal Customer Delivery Rehearsal operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.html", "submission_report", "Patch Proposal Customer Delivery Rehearsal static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-outcome.json", "submission_report", "Patch Proposal Customer Delivery Outcome Receipt metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-outcome.md", "submission_report", "Patch Proposal Customer Delivery Outcome Receipt operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-delivery-outcome.html", "submission_report", "Patch Proposal Customer Delivery Outcome Receipt static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-intake.json", "submission_report", "Patch Proposal Customer Feedback Intake Receipt metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-intake.md", "submission_report", "Patch Proposal Customer Feedback Intake Receipt operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-intake.html", "submission_report", "Patch Proposal Customer Feedback Intake Receipt static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-backlog-bridge.json", "submission_report", "Patch Proposal Customer Feedback Backlog Bridge metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-backlog-bridge.md", "submission_report", "Patch Proposal Customer Feedback Backlog Bridge operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-backlog-bridge.html", "submission_report", "Patch Proposal Customer Feedback Backlog Bridge static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-product-owner-gate.json", "submission_report", "Patch Proposal Customer Feedback Product Owner Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-product-owner-gate.md", "submission_report", "Patch Proposal Customer Feedback Product Owner Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-product-owner-gate.html", "submission_report", "Patch Proposal Customer Feedback Product Owner Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-spec-eval-authoring-gate.json", "submission_report", "Patch Proposal Customer Feedback Spec/Eval Authoring Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-spec-eval-authoring-gate.md", "submission_report", "Patch Proposal Customer Feedback Spec/Eval Authoring Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-spec-eval-authoring-gate.html", "submission_report", "Patch Proposal Customer Feedback Spec/Eval Authoring Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-product-loop-brief-intake-gate.json", "submission_report", "Patch Proposal Customer Feedback Product Loop Brief Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-product-loop-brief-intake-gate.md", "submission_report", "Patch Proposal Customer Feedback Product Loop Brief Intake Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-product-loop-brief-intake-gate.html", "submission_report", "Patch Proposal Customer Feedback Product Loop Brief Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-delivery-trust-intake-gate.json", "submission_report", "Patch Proposal Customer Feedback Delivery Trust Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-delivery-trust-intake-gate.md", "submission_report", "Patch Proposal Customer Feedback Delivery Trust Intake Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-delivery-trust-intake-gate.html", "submission_report", "Patch Proposal Customer Feedback Delivery Trust Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-delivery-trust-case-bridge.json", "submission_report", "Patch Proposal Customer Feedback Delivery Trust Case Bridge metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-delivery-trust-case-bridge.md", "submission_report", "Patch Proposal Customer Feedback Delivery Trust Case Bridge operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-delivery-trust-case-bridge.html", "submission_report", "Patch Proposal Customer Feedback Delivery Trust Case Bridge static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-boundary-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-boundary-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-boundary-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Rehearsal metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Rehearsal operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Rehearsal static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-outcome.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-outcome.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-outcome.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-intake.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-product-owner-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-product-owner-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-product-owner-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate.json", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate metadata-only verification report."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate.md", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate operator summary."),
    ("platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate.html", "submission_report", "Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate static HTML verification report."),
    ("platform/generated/study-anything-delivery-trust-case-harness.json", "submission_report", "Delivery Trust Case Harness end-to-end controlled customer-handoff verification report."),
    ("platform/generated/study-anything-delivery-trust-case-harness.html", "submission_report", "Delivery Trust Case Harness static HTML verification report."),
    ("platform/generated/study-anything-delivery-trust-case-pack.json", "submission_report", "Portable Delivery Trust Case pack sidecar manifest."),
    ("platform/generated/study-anything-delivery-trust-case-pack.md", "submission_report", "Portable Delivery Trust Case pack operator summary."),
    ("platform/generated/study-anything-delivery-trust-case-pack.zip", "submission_report", "Portable metadata-only Delivery Trust Case pack archive."),
    ("platform/generated/study-anything-delivery-trust-case-pack.sha256", "submission_report", "Portable Delivery Trust Case pack archive checksum."),
    ("platform/generated/study-anything-delivery-trust-case-pack-consumer-walkthrough.json", "submission_report", "ZIP-only external consumer walkthrough report for the Delivery Trust Case pack."),
    ("platform/generated/study-anything-code-review-delivery-class.json", "submission_report", "Code Review Delivery Class metadata-only handoff verification report."),
    ("platform/generated/study-anything-code-review-delivery-class.html", "submission_report", "Code Review Delivery Class static HTML verification report."),
    ("platform/generated/study-anything-client-report-delivery-class.json", "submission_report", "Client Report Delivery Class metadata-only handoff verification report."),
    ("platform/generated/study-anything-client-report-delivery-class.html", "submission_report", "Client Report Delivery Class static HTML verification report."),
    ("platform/generated/study-anything-support-response-delivery-class.json", "submission_report", "Support Response Delivery Class metadata-only handoff verification report."),
    ("platform/generated/study-anything-support-response-delivery-class.html", "submission_report", "Support Response Delivery Class static HTML verification report."),
    ("platform/generated/study-anything-external-feedback-receipt.json", "submission_report", "External Feedback Receipt metadata-only verification report."),
    ("platform/generated/study-anything-external-feedback-receipt.md", "submission_report", "External Feedback Receipt operator summary."),
    ("platform/generated/study-anything-external-feedback-receipt.html", "submission_report", "External Feedback Receipt static HTML verification report."),
    ("platform/generated/study-anything-external-feedback-backlog-bridge.json", "submission_report", "External Feedback Backlog Bridge metadata-only verification report."),
    ("platform/generated/study-anything-external-feedback-backlog-bridge.md", "submission_report", "External Feedback Backlog Bridge operator summary."),
    ("platform/generated/study-anything-external-feedback-backlog-bridge.html", "submission_report", "External Feedback Backlog Bridge static HTML verification report."),
    ("platform/generated/study-anything-product-owner-prioritization-gate.json", "submission_report", "Product Owner Prioritization Gate metadata-only verification report."),
    ("platform/generated/study-anything-product-owner-prioritization-gate.md", "submission_report", "Product Owner Prioritization Gate operator summary."),
    ("platform/generated/study-anything-product-owner-prioritization-gate.html", "submission_report", "Product Owner Prioritization Gate static HTML verification report."),
    ("platform/generated/study-anything-product-spec-eval-authoring-gate.json", "submission_report", "Product Spec/Eval Authoring Gate metadata-only verification report."),
    ("platform/generated/study-anything-product-spec-eval-authoring-gate.md", "submission_report", "Product Spec/Eval Authoring Gate operator summary."),
    ("platform/generated/study-anything-product-spec-eval-authoring-gate.html", "submission_report", "Product Spec/Eval Authoring Gate static HTML verification report."),
    ("platform/generated/study-anything-delivery-class-registry.json", "submission_report", "Delivery Class Registry metadata-only verification report."),
    ("platform/generated/study-anything-delivery-class-registry.html", "submission_report", "Delivery Class Registry static HTML verification report."),
    ("platform/generated/study-anything-trust-scenario-catalog.json", "submission_report", "Trust Scenario Catalog metadata-only verification report."),
    ("platform/generated/study-anything-trust-scenario-catalog.html", "submission_report", "Trust Scenario Catalog static HTML verification report."),
    ("platform/generated/study-anything-trust-scenario-decision-gate.json", "submission_report", "Trust Scenario Decision Gate metadata-only verification report."),
    ("platform/generated/study-anything-trust-scenario-decision-gate.html", "submission_report", "Trust Scenario Decision Gate static HTML verification report."),
    ("platform/generated/study-anything-workbuddy-inline-learning-flow.json", "submission_report", "WorkBuddy inline learning flow verification report."),
    ("platform/generated/study-anything-cognitive-loop-cli-artifact.json", "submission_report", "Cognitive Loop CLI init, verify, and static HTML artifact verification report."),
    ("platform/generated/study-anything-cognitive-loop-run-once-evidence.json", "submission_report", "Cognitive Loop run-once LoopRun and DecisionCard evidence verification report."),
    ("platform/generated/study-anything-cognitive-loop-project-snapshot.json", "submission_report", "Cognitive Loop redacted project snapshot verification report."),
    ("platform/generated/study-anything-cognitive-loop-human-gate.json", "submission_report", "Cognitive Loop Human Mastery Gate approval and rejection verification report."),
    ("platform/generated/study-anything-cognitive-loop-evidence-bundle.json", "submission_report", "Cognitive Loop metadata-only evidence bundle verification report."),
    ("platform/generated/study-anything-cognitive-loop-event-index.json", "submission_report", "Cognitive Loop metadata-only local event index verification report."),
    ("platform/generated/study-anything-cognitive-loop-event-store.json", "submission_report", "Cognitive Loop local SQLite Event Store verification report."),
    ("platform/generated/study-anything-cognitive-loop-watcher-ingest.json", "submission_report", "Cognitive Loop manual watcher ingest verification report."),
    ("platform/generated/study-anything-cognitive-loop-watcher-runner.json", "submission_report", "Cognitive Loop bounded watcher runner-lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-adapter.json", "submission_report", "Cognitive Loop Mastra adapter contract-pack verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-runtime-dry-run.json", "submission_report", "Cognitive Loop Mastra runtime dry-run verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-runtime-service.json", "submission_report", "Cognitive Loop repository-started Mastra runtime service verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-runtime-durable.json", "submission_report", "Cognitive Loop durable Mastra runtime suspend/resume verification report."),
    ("platform/generated/study-anything-cognitive-loop-langfuse-observability.json", "submission_report", "Cognitive Loop Langfuse observability DTO mapping verification report."),
    ("platform/generated/study-anything-cognitive-loop-study-anything-adapter.json", "submission_report", "Cognitive Loop Study Anything Learning Adapter verification report."),
    ("platform/generated/study-anything-cognitive-loop-study-adapter-cli.json", "submission_report", "Cognitive Loop Study Anything Adapter CLI Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-artifact-doctor.json", "submission_report", "Cognitive Loop metadata-only artifact doctor verification report."),
    ("platform/generated/study-anything-cognitive-loop-repair-plan.json", "submission_report", "Cognitive Loop manual-only repair plan verification report."),
    ("platform/generated/study-anything-cognitive-loop-artifact-index.json", "submission_report", "Cognitive Loop static local artifact index verification report."),
    ("platform/generated/study-anything-cognitive-loop-artifact-console.json", "submission_report", "Cognitive Loop static HTML Artifact Console Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-personal-plugin-mode.json", "submission_report", "Cognitive Loop Personal Plugin Mode Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-evolution-report.json", "submission_report", "Cognitive Loop Evolution Report Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-apply-plan.json", "submission_report", "Cognitive Loop Governed Apply Plan Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-improvement-comparison.json", "submission_report", "Cognitive Loop Measured Improvement Comparator Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-patch-proposal.json", "submission_report", "Cognitive Loop Patch Proposal Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-evolution-receipt.json", "submission_report", "Cognitive Loop Mastra Evolution Receipt Link Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-mastra-evolution-replay.json", "submission_report", "Cognitive Loop Mastra Evolution Workflow Replay Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-patch-apply-sandbox.json", "submission_report", "Cognitive Loop Governed Patch Apply Sandbox Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-evolution-pack-export.json", "submission_report", "Cognitive Loop Professional Evolution Pack Export Lite verification report."),
    ("platform/generated/study-anything-cognitive-loop-evolution-pack-consumer.json", "submission_report", "Cognitive Loop Professional Evolution Pack zip-only consumer verification report."),
    ("platform/generated/study-anything-cognitive-loop-pr-ci-receipt.json", "submission_report", "Cognitive Loop PR CI metadata-only receipt verification report with optional GitHub CLI metadata adapter."),
    ("platform/generated/study-anything-cognitive-loop-maintainer-acceptance-ledger.json", "submission_report", "Cognitive Loop maintainer go/no-go acceptance ledger verification report."),
    ("platform/generated/study-anything-cognitive-loop-review.json", "submission_report", "Cognitive Loop advisory code review verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-prompt.json", "submission_report", "External Cognitive Loop Review Agent prompt verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-report.json", "submission_report", "External Cognitive Loop Review Agent report handoff verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-handoff-cli.json", "submission_report", "External Cognitive Loop Review Agent prepare/validate CLI verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-eval-harness.json", "submission_report", "Offline Cognitive Loop Review Agent eval harness verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-ci-receipt.json", "submission_report", "External Cognitive Loop Review Agent CI receipt verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-pr-comment-pack.json", "submission_report", "External Cognitive Loop Review Agent PR comment pack verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-acceptance-bundle.json", "submission_report", "External Cognitive Loop Review Agent acceptance bundle verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json", "submission_report", "External Cognitive Loop Review Agent GitHub workflow template verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-policy-gate.json", "submission_report", "External Cognitive Loop Review Agent policy gate verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json", "submission_report", "External Cognitive Loop Review Agent workflow install smoke verification report."),
    ("platform/generated/study-anything-cognitive-loop-review-agent-adoption-drill.json", "submission_report", "External Cognitive Loop Review Agent zip-only adoption drill verification report."),
    ("platform/generated/study-anything-cognitive-loop-adoption-cookbook.json", "submission_report", "Cognitive Loop platform-agent adoption cookbook verification report."),
    ("platform/generated/study-anything-cognitive-loop-adoption-recipes.json", "submission_report", "Machine-readable Cognitive Loop platform-agent adoption recipes."),
    ("platform/generated/study-anything-cognitive-loop-recipe-replay.json", "submission_report", "Cognitive Loop platform-agent recipe replay verification report."),
    ("platform/generated/study-anything-cognitive-loop-skill-entrypoint.json", "submission_report", "Cognitive Loop Skill and platform-pack recipe entrypoint verification report."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli.json", "submission_report", "Cognitive Loop read-only recipe CLI verification report."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json", "submission_report", "Deterministic read-only Cognitive Loop recipe CLI output receipts."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json", "submission_report", "Deterministic read-only Cognitive Loop recipe CLI failure receipts."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json", "submission_report", "Offline JSON Schemas for Cognitive Loop recipe CLI reports and PR CI receipt/source metadata reports."),
    ("platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json", "submission_report", "Negative fixtures proving Cognitive Loop recipe CLI schemas reject drift, unsafe flags, malformed types, and private text probes."),
    ("platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json", "submission_report", "Zip-only consumer proof for Cognitive Loop recipe CLI schema evidence in the adoption pack."),
    ("platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json", "submission_report", "Tampered adoption-pack failure proof for Cognitive Loop recipe CLI schema evidence."),
    ("platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json", "submission_report", "Extracted adoption-pack smoke proof for bundled Cognitive Loop schema consumer checks."),
    ("platform/generated/study-anything-platform-handoff-checklist.json", "submission_report", "External platform handoff checklist for import, verification, runtime, and support escalation."),
    ("platform/generated/study-anything-launch-acceptance-ledger.json", "submission_report", "Public launch acceptance ledger for GitHub OSS and platform-Agent adoption."),
    ("platform/generated/study-anything-github-launch-operator-guide.json", "submission_report", "GitHub launch operator guide proof for release sequence, assets, and local-first boundaries."),
    ("platform/generated/study-anything-release-stack-manifest-fixtures.json", "submission_report", "Negative fixtures proving release stack archive manifest boundary checks."),
    ("platform/generated/study-anything-release-stack-intake-candidate.json", "submission_report", "Metadata-only release stack intake candidate report for the next PR group."),
    ("platform/generated/study-anything-release-stack-candidate-promotion.json", "submission_report", "Metadata-only release stack candidate promotion report for the current PR group."),
    ("platform/generated/study-anything-operator-drill-transcript.json", "submission_report", "External platform operator drill transcript."),
    ("platform/generated/study-anything-platform-submission-dry-run.json", "submission_report", "External platform submission dry-run readiness report."),
    ("platform/generated/study-anything-platform-manual-submission-rehearsal.json", "submission_report", "Manual platform-submission rehearsal and redacted handoff report."),
    ("platform/generated/study-anything-first-lesson-authoring-kit.json", "submission_report", "Copyable first-run lesson authoring kit for platform Agents."),
    ("platform/generated/study-anything-external-eval-harness.json", "submission_report", "Marketplace-quality external Agent eval harness for platform submissions."),
    ("platform/generated/study-anything-real-agent-eval-bridge.json", "submission_report", "User-owned real-agent eval receipt bridge verification report."),
    ("platform/generated/study-anything-real-agent-eval-bridge.html", "submission_report", "User-owned real-agent eval receipt bridge HTML report."),
    ("platform/generated/study-anything-workbuddy-real-agent-learning-quality.json", "submission_report", "WorkBuddy/Kimi/Codex real-agent learning-quality verification report."),
    ("platform/generated/study-anything-workbuddy-real-agent-learning-quality.html", "submission_report", "WorkBuddy/Kimi/Codex real-agent learning-quality HTML report."),
    ("platform/generated/study-anything-agent-eval-marketplace-enforcement.json", "submission_report", "Agent eval marketplace enforcement report for optional and required external judge gates."),
    ("platform/generated/study-anything-platform-adoption-feedback-diagnostics.json", "submission_report", "Platform import diagnostics and redacted feedback boundary report."),
    ("platform/generated/study-anything-platform-feedback-package.json", "feedback_package", "Local-only redacted feedback package manifest."),
    ("platform/generated/study-anything-platform-feedback-package.zip", "feedback_package", "Local-only redacted feedback package archive."),
    ("platform/generated/study-anything-platform-field-rehearsal.json", "submission_report", "Redacted field-adoption rehearsal transcript and import quirks report."),
    ("platform/generated/study-anything-platform-support-triage.json", "submission_report", "GitHub-first support triage report for external platform adoption failures."),
    ("platform/generated/study-anything-platform-support-bundle-replay.json", "submission_report", "Maintainer replay evidence for redacted platform support bundles."),
    ("platform/generated/study-anything-platform-onboarding-readiness.json", "submission_report", "First-adopter onboarding readiness and maintainer SLA report."),
    ("platform/generated/study-anything-platform-triage-dashboard.json", "submission_report", "Generated platform triage dashboard JSON."),
    ("platform/generated/study-anything-platform-triage-dashboard.md", "submission_report", "Generated platform triage dashboard Markdown."),
    ("platform/generated/study-anything-public-support-status.json", "submission_report", "Public support status report."),
    ("platform/generated/study-anything-public-maintainer-dashboard.json", "submission_report", "Public maintainer dashboard JSON."),
    ("platform/generated/study-anything-public-maintainer-dashboard.md", "submission_report", "Public maintainer dashboard Markdown."),
    ("platform/generated/study-anything-published-image-evidence.json", "submission_report", "Published-image evidence JSON."),
    ("platform/generated/study-anything-published-image-evidence.md", "submission_report", "Published-image evidence Markdown."),
    ("platform/generated/study-anything-published-image-evidence.zip", "submission_report", "Published-image evidence package."),
    ("platform/generated/study-anything-published-image-evidence.sha256", "submission_report", "Published-image evidence checksum."),
    ("platform/generated/study-anything-release-asset-adoption.json", "submission_report", "GitHub Release asset adoption replay evidence JSON."),
    ("platform/generated/study-anything-release-asset-adoption.md", "submission_report", "GitHub Release asset adoption replay evidence Markdown."),
    ("platform/generated/study-anything-release-asset-adoption.zip", "submission_report", "GitHub Release asset adoption replay evidence package."),
    ("platform/generated/study-anything-release-asset-adoption.sha256", "submission_report", "GitHub Release asset adoption replay evidence checksum."),
    ("platform/generated/study-anything-release-asset-bootstrap.json", "submission_report", "GitHub Release asset bootstrap evidence JSON."),
    ("platform/generated/study-anything-release-asset-bootstrap.md", "submission_report", "GitHub Release asset bootstrap evidence Markdown."),
    ("platform/generated/study-anything-release-asset-bootstrap.zip", "submission_report", "GitHub Release asset bootstrap evidence package."),
    ("platform/generated/study-anything-release-asset-bootstrap.sha256", "submission_report", "GitHub Release asset bootstrap evidence checksum."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.json", "submission_report", "Release-only cleanroom bootstrap evidence JSON."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.md", "submission_report", "Release-only cleanroom bootstrap evidence Markdown."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.zip", "submission_report", "Release-only cleanroom bootstrap evidence package."),
    ("platform/generated/study-anything-release-cleanroom-bootstrap.sha256", "submission_report", "Release-only cleanroom bootstrap evidence checksum."),
    ("platform/generated/study-anything-platform-agent-replay.json", "submission_report", "Platform Agent release replay evidence JSON."),
    ("platform/generated/study-anything-platform-agent-replay.md", "submission_report", "Platform Agent release replay evidence Markdown."),
    ("platform/generated/study-anything-platform-agent-replay.zip", "submission_report", "Platform Agent release replay evidence package."),
    ("platform/generated/study-anything-platform-agent-replay.sha256", "submission_report", "Platform Agent release replay evidence checksum."),
    ("platform/generated/study-anything-adopter-evidence-archive.json", "submission_report", "External adopter evidence archive JSON."),
    ("platform/generated/study-anything-adopter-evidence-archive.md", "submission_report", "External adopter evidence archive Markdown."),
    ("platform/generated/study-anything-adopter-evidence-archive.zip", "submission_report", "External adopter evidence archive package."),
    ("platform/generated/study-anything-adopter-evidence-archive.sha256", "submission_report", "External adopter evidence archive checksum."),
    ("fixtures/platform-import-failures/schema_mismatch.json", "fixture", "Mock platform import failure fixture for schema mismatch."),
    ("fixtures/platform-import-failures/missing_local_gateway.json", "fixture", "Mock platform import failure fixture for missing local gateway."),
    ("fixtures/platform-import-failures/unsupported_auth_mode.json", "fixture", "Mock platform import failure fixture for unsupported auth mode."),
    ("fixtures/platform-import-failures/tool_naming_drift.json", "fixture", "Mock platform import failure fixture for tool naming drift."),
    ("fixtures/platform-import-failures/timeout.json", "fixture", "Mock platform import failure fixture for timeout diagnostics."),
    ("fixtures/platform-import-failures/cors_localhost.json", "fixture", "Mock platform import failure fixture for browser localhost restrictions."),
    ("fixtures/platform-import-failures/package_corruption.json", "fixture", "Mock platform import failure fixture for corrupted adoption packages."),
    ("fixtures/platform-import-failures/version_drift.json", "fixture", "Mock platform import failure fixture for version drift."),
    (".github/ISSUE_TEMPLATE/platform_import_failure.md", "support_template", "GitHub issue template for platform import failures."),
    (".github/ISSUE_TEMPLATE/local_gateway_failure.md", "support_template", "GitHub issue template for local Agent gateway failures."),
    (".github/ISSUE_TEMPLATE/published_image_pull_failure.md", "support_template", "GitHub issue template for published-image pull failures."),
    (".github/ISSUE_TEMPLATE/agent_eval_evidence_failure.md", "support_template", "GitHub issue template for Agent eval evidence failures."),
    (".github/ISSUE_TEMPLATE/docs_confusion.md", "support_template", "GitHub issue template for docs confusion reports."),
    ("fixtures/platform-support-tickets/platform_import_failure.json", "support_fixture", "Mock support ticket fixture for platform import failure triage."),
    ("fixtures/platform-support-tickets/local_gateway_failure.json", "support_fixture", "Mock support ticket fixture for local Agent gateway triage."),
    ("fixtures/platform-support-tickets/published_image_pull_failure.json", "support_fixture", "Mock support ticket fixture for published-image pull triage."),
    ("fixtures/platform-support-tickets/agent_eval_evidence_failure.json", "support_fixture", "Mock support ticket fixture for Agent eval evidence triage."),
    ("fixtures/platform-support-tickets/docs_confusion.json", "support_fixture", "Mock support ticket fixture for docs confusion triage."),
    ("fixtures/platform-support-bundles/local-ghcr-pull-timeout.json", "support_fixture", "Mock redacted support bundle for a local GHCR pull timeout replay."),
    ("fixtures/platform-support-bundles/cleanroom-runtime-launch-failed.json", "support_fixture", "Mock redacted support bundle for cleanroom runtime launch replay."),
    ("fixtures/platform-support-bundles/privacy-contract-violation.json", "support_fixture", "Mock redacted support bundle proving privacy violation replay blocks."),
    ("fixtures/platform-release-blockers/tool_import_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for platform tool import failures."),
    ("fixtures/platform-release-blockers/local_gateway_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for local Agent gateway failures."),
    ("fixtures/platform-release-blockers/published_image_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for published-image launch failures."),
    ("fixtures/platform-release-blockers/agent_eval_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for Agent eval evidence failures."),
    ("fixtures/platform-release-blockers/support_bundle_privacy_blocker.json", "release_blocker_fixture", "Mock release blocker fixture for unsafe support bundle privacy reports."),
    ("fixtures/release-stack/pr-183-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 183."),
    ("fixtures/release-stack/pr-184-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 184."),
    ("fixtures/release-stack/pr-185-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 185."),
    ("fixtures/release-stack/pr-186-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 186."),
    ("fixtures/release-stack/pr-187-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 187."),
    ("fixtures/release-stack/pr-188-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 188."),
    ("fixtures/release-stack/pr-189-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 189."),
    ("fixtures/release-stack/pr-190-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 190."),
    ("fixtures/release-stack/pr-191-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 191."),
    ("fixtures/release-stack/pr-192-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 192."),
    ("fixtures/release-stack/pr-193-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 193."),
    ("fixtures/release-stack/pr-194-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 194."),
    ("fixtures/release-stack/pr-195-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 195."),
    ("fixtures/release-stack/pr-196-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 196."),
    ("fixtures/release-stack/pr-197-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 197."),
    ("fixtures/release-stack/pr-198-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 198."),
    ("fixtures/release-stack/pr-199-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 199."),
    ("fixtures/release-stack/pr-200-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 200."),
    ("fixtures/release-stack/pr-201-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 201."),
    ("fixtures/release-stack/pr-202-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 202."),
    ("fixtures/release-stack/pr-203-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 203."),
    ("fixtures/release-stack/pr-204-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 204."),
    ("fixtures/release-stack/pr-205-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 205."),
    ("fixtures/release-stack/pr-206-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 206."),
    ("fixtures/release-stack/pr-207-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 207."),
    ("fixtures/release-stack/pr-208-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 208."),
    ("fixtures/release-stack/pr-209-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 209."),
    ("fixtures/release-stack/pr-210-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 210."),
    ("fixtures/release-stack/pr-211-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 211."),
    ("fixtures/release-stack/pr-212-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 212."),
    ("fixtures/release-stack/pr-213-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 213."),
    ("fixtures/release-stack/pr-214-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 214."),
    ("fixtures/release-stack/pr-215-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 215."),
    ("fixtures/release-stack/pr-216-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 216."),
    ("fixtures/release-stack/pr-217-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 217."),
    ("fixtures/release-stack/pr-218-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 218."),
    ("fixtures/release-stack/pr-219-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 219."),
    ("fixtures/release-stack/pr-220-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 220."),
    ("fixtures/release-stack/pr-221-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 221."),
    ("fixtures/release-stack/pr-222-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 222."),
    ("fixtures/release-stack/pr-223-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 223."),
    ("fixtures/release-stack/pr-224-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 224."),
    ("fixtures/release-stack/pr-225-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 225."),
    ("fixtures/release-stack/pr-226-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 226."),
    ("fixtures/release-stack/pr-227-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 227."),
    ("fixtures/release-stack/pr-228-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 228."),
    ("fixtures/release-stack/pr-229-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 229."),
    ("fixtures/release-stack/pr-230-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 230."),
    ("fixtures/release-stack/pr-231-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 231."),
    ("fixtures/release-stack/pr-232-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 232."),
    ("fixtures/release-stack/pr-233-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 233."),
    ("fixtures/release-stack/pr-234-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 234."),
    ("fixtures/release-stack/pr-235-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 235."),
    ("fixtures/release-stack/pr-236-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 236."),
    ("fixtures/release-stack/pr-237-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 237."),
    ("fixtures/release-stack/pr-238-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 238."),
    ("fixtures/release-stack/pr-240-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 240."),
    ("fixtures/release-stack/pr-241-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 241."),
    ("fixtures/release-stack/pr-243-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 243."),
    ("fixtures/release-stack/pr-244-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 244."),
    ("fixtures/release-stack/pr-246-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 246."),
    ("fixtures/release-stack/pr-247-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 247."),
    ("fixtures/release-stack/pr-249-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 249."),
    ("fixtures/release-stack/pr-250-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 250."),
    ("fixtures/release-stack/pr-252-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 252."),
    ("fixtures/release-stack/pr-253-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 253."),
    ("fixtures/release-stack/pr-255-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 255."),
    ("fixtures/release-stack/pr-256-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 256."),
    ("fixtures/release-stack/pr-258-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 258."),
    ("fixtures/release-stack/pr-259-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 259."),
    ("fixtures/release-stack/pr-277-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 277."),
    ("fixtures/release-stack/pr-278-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 278."),
    ("fixtures/release-stack/pr-280-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 280."),
    ("fixtures/release-stack/pr-281-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 281."),
    ("fixtures/release-stack/pr-286-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 286."),
    ("fixtures/release-stack/pr-287-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 287."),
    ("fixtures/release-stack/pr-288-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 288."),
    ("fixtures/release-stack/pr-336-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 336."),
    ("fixtures/release-stack/pr-338-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 338."),
    ("fixtures/release-stack/pr-358-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 358."),
    ("fixtures/release-stack/pr-360-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 360."),
    ("fixtures/release-stack/pr-362-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 362."),
    ("fixtures/release-stack/pr-364-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 364."),
    ("fixtures/release-stack/pr-366-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 366."),
    ("fixtures/release-stack/pr-396-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 396."),
    ("fixtures/release-stack/pr-398-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 398."),
    ("fixtures/release-stack/pr-401-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 401."),
    ("fixtures/release-stack/pr-405-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 405."),
    ("fixtures/release-stack/pr-407-intake-candidate.json", "fixture", "Redacted release stack intake candidate fixture for PR 407."),
    ("scripts/verify_release_stack_intake_candidate.py", "verification", "Verify metadata-only release stack intake candidates from PR summary metadata."),
    ("scripts/verify_release_stack_candidate_promotion.py", "verification", "Verify metadata-only release stack candidate promotion into the manifest."),
    ("fixtures/platform-status-links/intake.json", "status_linkage_fixture", "Public status linkage fixture for intake issues."),
    ("fixtures/platform-status-links/needs-repro.json", "status_linkage_fixture", "Public status linkage fixture for needs-repro issues."),
    ("fixtures/platform-status-links/confirmed.json", "status_linkage_fixture", "Public status linkage fixture for confirmed issues."),
    ("fixtures/platform-status-links/blocked-by-platform.json", "status_linkage_fixture", "Public status linkage fixture for blocked-by-platform issues."),
    ("fixtures/platform-status-links/docs-fix.json", "status_linkage_fixture", "Public status linkage fixture for docs-fix issues."),
    ("fixtures/platform-status-links/release-blocker.json", "status_linkage_fixture", "Public status linkage fixture for release-blocker issues."),
    ("fixtures/platform-status-links/resolved.json", "status_linkage_fixture", "Public status linkage fixture for resolved issues."),
    ("fixtures/review-agent/approved.json", "review_agent_fixture", "Accepted external Review Agent approved report fixture."),
    ("fixtures/review-agent/needs-review.json", "review_agent_fixture", "Accepted external Review Agent needs-review report fixture."),
    ("fixtures/review-agent/needs-fix.json", "review_agent_fixture", "Accepted external Review Agent needs-fix report fixture."),
    ("fixtures/review-agent/invalid-low-confidence-final.json", "review_agent_fixture", "Rejected external Review Agent low-confidence final finding fixture."),
    ("fixtures/review-agent-receipts/raw-diff-leak.json", "review_agent_receipt_fixture", "Rejected external Review Agent CI receipt raw-diff leak fixture."),
    ("fixtures/review-agent-pr-comments/raw-diff-leak.json", "review_agent_pr_comment_fixture", "Rejected external Review Agent PR comment raw-diff leak fixture."),
    ("fixtures/review-agent-acceptance-bundles/raw-diff-leak/manifest.json", "review_agent_acceptance_bundle_fixture", "Rejected external Review Agent acceptance bundle raw-diff leak fixture."),
    ("fixtures/review-agent-github-workflows/unsafe-auto-pr.yml", "review_agent_github_workflow_fixture", "Rejected unsafe Review Agent GitHub workflow fixture."),
    ("fixtures/adopter-evidence-archive/successful-release.json", "adopter_evidence_fixture", "Public evidence fixture for a successful release handoff."),
    ("fixtures/adopter-evidence-archive/local-ghcr-pull-timeout.json", "adopter_evidence_fixture", "Public evidence fixture for local GHCR pull timeout fallback."),
    ("fixtures/adopter-evidence-archive/needs-repro-issue.json", "adopter_evidence_fixture", "Public evidence fixture for needs-repro support state."),
    ("fixtures/adopter-evidence-archive/release-blocker.json", "adopter_evidence_fixture", "Public evidence fixture for release-blocker support state."),
    ("fixtures/adopter-evidence-archive/platform-blocked.json", "adopter_evidence_fixture", "Public evidence fixture for platform-blocked support state."),
    ("fixtures/adopter-evidence-archive/resolved-support-case.json", "adopter_evidence_fixture", "Public evidence fixture for resolved support state."),
    ("fixtures/published-image-evidence/manifest-pass-local-pull-timeout.json", "published_image_evidence_fixture", "Published-image evidence fixture for local pull timeout fallback."),
    ("fixtures/published-image-evidence/cached-image-missing.json", "published_image_evidence_fixture", "Published-image evidence fixture for cached-only local image misses."),
    ("fixtures/published-image-evidence/compose-up-timeout.json", "published_image_evidence_fixture", "Published-image evidence fixture for bounded Compose startup timeouts."),
    ("fixtures/published-image-evidence/manifest-only-runtime-unverified.json", "published_image_evidence_fixture", "Published-image evidence fixture for manifest-only runtime-unverified handoff."),
    ("fixtures/published-image-evidence/manifest-missing-platform.json", "published_image_evidence_fixture", "Published-image evidence fixture for a missing manifest platform."),
    ("fixtures/published-image-evidence/docker-images-failed.json", "published_image_evidence_fixture", "Published-image evidence fixture for failed docker-images publishing."),
    ("fixtures/published-image-evidence/ghcr-unavailable.json", "published_image_evidence_fixture", "Published-image evidence fixture for GHCR or network unavailability."),
    ("fixtures/published-image-evidence/remote-smoke-pass.json", "published_image_evidence_fixture", "Published-image evidence fixture for a passing remote smoke replay."),
    ("fixtures/published-image-evidence/remote-smoke-failed.json", "published_image_evidence_fixture", "Published-image evidence fixture for runtime smoke failure."),
    ("fixtures/release-asset-adoption/asset-only-pass.json", "release_asset_adoption_fixture", "Release asset adoption fixture for a passing asset-only replay."),
    ("fixtures/release-asset-adoption/asset-missing.json", "release_asset_adoption_fixture", "Release asset adoption fixture for a missing release asset."),
    ("fixtures/release-asset-adoption/digest-mismatch.json", "release_asset_adoption_fixture", "Release asset adoption fixture for digest mismatch."),
    ("fixtures/release-asset-adoption/pack-corrupted.json", "release_asset_adoption_fixture", "Release asset adoption fixture for a corrupted adoption pack."),
    ("fixtures/release-asset-adoption/published-evidence-missing.json", "release_asset_adoption_fixture", "Release asset adoption fixture for missing published-image evidence."),
    ("fixtures/release-asset-adoption/network-unavailable.json", "release_asset_adoption_fixture", "Release asset adoption fixture for GitHub release network unavailability."),
    ("fixtures/cognitive-loop-study-adapter/project-event.json", "cognitive_loop_fixture", "ProjectEvent fixture for the Study Anything adapter CLI."),
    ("fixtures/cognitive-loop-study-adapter/decision-card.json", "cognitive_loop_fixture", "DecisionCard fixture for the Study Anything adapter CLI."),
    ("fixtures/dual-loop/pass/failure-contract.json", "dual_loop_fixture", "Passing Dual-Loop failure contract fixture."),
    ("fixtures/dual-loop/pass/sandbox-receipt.json", "dual_loop_fixture", "Passing Dual-Loop sandbox receipt fixture."),
    ("fixtures/dual-loop/pass/attention-reconstruction-trace.json", "dual_loop_fixture", "Passing Dual-Loop attention reconstruction trace fixture."),
    ("fixtures/dual-loop/pass/attention-reconstruction-summary.json", "dual_loop_fixture", "Passing Dual-Loop attention reconstruction summary fixture."),
    ("fixtures/dual-loop/pass/dual-loop-gate-receipt.json", "dual_loop_fixture", "Passing Dual-Loop propagation gate receipt fixture."),
    ("fixtures/dual-loop/blocked-missing-attention/failure-contract.json", "dual_loop_fixture", "Blocked Dual-Loop fixture with sandbox pass and missing attention reconstruction."),
    ("fixtures/dual-loop/blocked-missing-attention/sandbox-receipt.json", "dual_loop_fixture", "Blocked Dual-Loop sandbox receipt fixture with missing attention reconstruction."),
    ("fixtures/dual-loop/blocked-missing-attention/dual-loop-gate-receipt.json", "dual_loop_fixture", "Blocked Dual-Loop gate receipt fixture for missing attention reconstruction."),
    ("fixtures/dual-loop/blocked-risk-budget/failure-contract.json", "dual_loop_fixture", "Blocked Dual-Loop failure contract fixture for risk-budget overflow."),
    ("fixtures/dual-loop/blocked-risk-budget/sandbox-receipt.json", "dual_loop_fixture", "Blocked Dual-Loop sandbox receipt fixture for risk-budget overflow."),
    ("fixtures/dual-loop/blocked-risk-budget/attention-reconstruction-summary.json", "dual_loop_fixture", "Blocked Dual-Loop attention summary fixture with passing human reconstruction."),
    ("fixtures/dual-loop/blocked-risk-budget/dual-loop-gate-receipt.json", "dual_loop_fixture", "Blocked Dual-Loop gate receipt fixture for risk-budget overflow."),
    ("fixtures/dual-loop-scenarios/pass/scenario-result.json", "dual_loop_fixture", "Passing Dual Loop trust scenario result for customer delivery readiness."),
    ("fixtures/dual-loop-scenarios/pass/customer-handoff-package.json", "dual_loop_fixture", "Passing Dual Loop scenario CustomerHandoffPackage fixture."),
    ("fixtures/dual-loop-scenarios/attention-missing/scenario-result.json", "dual_loop_fixture", "Blocked Dual Loop scenario result for missing human reconstruction."),
    ("fixtures/dual-loop-scenarios/attention-missing/delivery-trust-receipt.json", "dual_loop_fixture", "Blocked scenario Delivery Trust Receipt for missing human reconstruction."),
    ("fixtures/dual-loop-scenarios/risk-over-budget/scenario-result.json", "dual_loop_fixture", "Blocked Dual Loop scenario result for sandbox risk outside budget."),
    ("fixtures/dual-loop-scenarios/risk-over-budget/delivery-trust-receipt.json", "dual_loop_fixture", "Blocked scenario Delivery Trust Receipt for sandbox risk outside budget."),
    ("fixtures/dual-loop-scenarios/both-fail/scenario-result.json", "dual_loop_fixture", "Blocked Dual Loop scenario result when sandbox and reconstruction both fail."),
    ("fixtures/dual-loop-scenarios/both-fail/delivery-trust-receipt.json", "dual_loop_fixture", "Blocked scenario Delivery Trust Receipt when sandbox and reconstruction both fail."),
    ("fixtures/delivery-trust/pass/delivery-trust-receipt.json", "delivery_trust_fixture", "Passing Delivery Trust Receipt fixture for controlled customer handoff."),
    ("fixtures/delivery-trust/blocked-missing-attention/delivery-trust-receipt.json", "delivery_trust_fixture", "Blocked Delivery Trust Receipt fixture for missing human reconstruction."),
    ("fixtures/delivery-trust/blocked-risk-budget/delivery-trust-receipt.json", "delivery_trust_fixture", "Blocked Delivery Trust Receipt fixture for sandbox risk outside budget."),
    ("fixtures/customer-handoff/pass/customer-handoff-package.json", "customer_handoff_fixture", "Passing CustomerHandoffPackage fixture for controlled customer handoff."),
    ("fixtures/customer-handoff/block-missing-delivery-trust/expected-error.json", "customer_handoff_fixture", "CustomerHandoffPackage negative fixture for missing DeliveryTrustReceipt."),
    ("fixtures/customer-handoff/block-scope-expansion/expected-error.json", "customer_handoff_fixture", "CustomerHandoffPackage negative fixture for scope expansion."),
    ("fixtures/customer-handoff/block-missing-claim-boundary/expected-error.json", "customer_handoff_fixture", "CustomerHandoffPackage negative fixture for missing claim boundary."),
    ("fixtures/codeql-negative/check-env-placeholder.txt", "security_negative_fixture", "Static placeholder environment fixture for redaction verification."),
    ("fixtures/codeql-negative/review-auth-guard.txt", "security_negative_fixture", "Static source fixture for review redaction verification."),
    ("fixtures/codeql-negative/artifact-console-evolution-secret.json", "security_negative_fixture", "Static secret-like Evolution report fixture for console rejection verification."),
    ("fixtures/codeql-negative/evolution-pack-patch-secret.json", "security_negative_fixture", "Static secret-like patch fixture for Evolution pack rejection verification."),
    ("fixtures/codeql-negative/patch-apply-proposal-secret.json", "security_negative_fixture", "Static secret-like patch fixture for apply sandbox rejection verification."),
    *[
        (
            f"fixtures/cbb-protocol/{case_id}/{artifact}",
            "cbb_fixture",
            f"Cognitive Black Box protocol {case_id} {artifact} fixture.",
        )
        for case_id in CBB_PROTOCOL_CASES
        for artifact in CBB_PROTOCOL_ARTIFACTS
    ],
    *[
        (
            f"fixtures/cbb-self-intake/pr-285/{artifact}",
            "cbb_self_intake_fixture",
            f"Cognitive Black Box PR 285 self-intake {artifact} fixture.",
        )
        for artifact in CBB_SELF_INTAKE_POSITIVE_ARTIFACTS
    ],
    *[
        (
            f"fixtures/cbb-self-intake/negative/{case_id}/{artifact}",
            "cbb_self_intake_fixture",
            f"Cognitive Black Box self-intake negative {case_id} {artifact} fixture.",
        )
        for case_id, artifacts in CBB_SELF_INTAKE_NEGATIVE_CASES.items()
        for artifact in artifacts
    ],
    *[
        (
            f"fixtures/cbb-delivery-harness/{case_id}/{artifact}",
            "cbb_delivery_harness_fixture",
            f"Cognitive Black Box delivery harness {case_id} {artifact} fixture.",
        )
        for case_id in CBB_DELIVERY_HARNESS_CASES
        for artifact in CBB_DELIVERY_HARNESS_ARTIFACTS
    ],
    *[
        (
            f"fixtures/product-loop-harness/{case_id}/{artifact}",
            "product_loop_harness_fixture",
            f"Product Loop Harness {case_id} {artifact} fixture.",
        )
        for case_id in PRODUCT_LOOP_HARNESS_CASES
        for artifact in PRODUCT_LOOP_HARNESS_ARTIFACTS
    ],
    *[
        (
            f"fixtures/delivery-trust-case/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Delivery Trust Case Harness {case_id} {artifact} fixture.",
        )
        for case_id, artifacts in DELIVERY_TRUST_CASE_HARNESS_CASES.items()
        for artifact in artifacts
    ],
    *[
        (
            f"fixtures/code-review-delivery-class/{case_id}/code-review-handoff-case.json",
            "delivery_trust_case_harness_fixture",
            f"Code Review Delivery Class {case_id} handoff fixture.",
        )
        for case_id in (
            "pass",
            "blocked-missing-reconstruction",
            "blocked-unsafe-diff-scope",
            "blocked-ai-review-only",
        )
    ],
    *[
        (
            f"fixtures/client-report-delivery-class/{case_id}/client-report-handoff-case.json",
            "delivery_trust_case_harness_fixture",
            f"Client Report Delivery Class {case_id} handoff fixture.",
        )
        for case_id in (
            "pass",
            "blocked-missing-reconstruction",
            "blocked-risk-over-budget",
            "blocked-unbounded-recipient",
            "blocked-ai-summary-only",
        )
    ],
    *[
        (
            f"fixtures/support-response-delivery-class/{case_id}/support-response-handoff-case.json",
            "delivery_trust_case_harness_fixture",
            f"Support Response Delivery Class {case_id} handoff fixture.",
        )
        for case_id in (
            "pass",
            "blocked-missing-reconstruction",
            "blocked-risk-over-budget",
            "blocked-unbounded-recipient",
            "blocked-policy-gap",
            "blocked-ai-summary-only",
        )
    ],
    *[
        (
            f"fixtures/external-feedback-receipt/{case_id}/external-feedback-receipt.json",
            "delivery_trust_case_harness_fixture",
            f"External Feedback Receipt {case_id} fixture.",
        )
        for case_id in EXTERNAL_FEEDBACK_RECEIPT_CASES
    ],
    *[
        (
            f"fixtures/external-feedback-backlog-bridge/{case_id}/external-feedback-backlog-bridge.json",
            "delivery_trust_case_harness_fixture",
            f"External Feedback Backlog Bridge {case_id} fixture.",
        )
        for case_id in EXTERNAL_FEEDBACK_BACKLOG_BRIDGE_CASES
    ],
    ("fixtures/external-feedback-backlog-bridge/pass/product-loop-backlog-item.json", "delivery_trust_case_harness_fixture", "External Feedback Backlog Bridge pass Product Loop backlog item fixture."),
    *[
        (
            f"fixtures/product-owner-prioritization-gate/{case_id}/product-owner-prioritization-receipt.json",
            "delivery_trust_case_harness_fixture",
            f"Product Owner Prioritization Gate {case_id} fixture.",
        )
        for case_id in PRODUCT_OWNER_PRIORITIZATION_GATE_CASES
    ],
    ("fixtures/product-owner-prioritization-gate/pass/product-spec-eval-candidate.json", "delivery_trust_case_harness_fixture", "Product Owner Prioritization Gate pass spec/eval candidate fixture."),
    *[
        (
            f"fixtures/product-spec-eval-authoring-gate/{case_id}/product-spec-eval-authoring-receipt.json",
            "delivery_trust_case_harness_fixture",
            f"Product Spec/Eval Authoring Gate {case_id} fixture.",
        )
        for case_id in PRODUCT_SPEC_EVAL_AUTHORING_GATE_CASES
    ],
    ("fixtures/product-spec-eval-authoring-gate/pass/product-spec-eval-brief.json", "delivery_trust_case_harness_fixture", "Product Spec/Eval Authoring Gate pass brief fixture."),
    *[
        (
            f"fixtures/product-loop-brief-intake/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Product Loop Brief Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PRODUCT_LOOP_BRIEF_INTAKE_CASES
        for artifact in PRODUCT_LOOP_BRIEF_INTAKE_ARTIFACTS[case_id]
    ],
    ("fixtures/end-to-end-trust-chain-harness/pass/end-to-end-trust-chain-report.json", "delivery_trust_case_harness_fixture", "End-to-End Trust Chain Harness pass report fixture."),
    ("fixtures/real-adopter-scenario-import/pass/real-adopter-issue-summary.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass issue summary fixture."),
    ("fixtures/real-adopter-scenario-import/pass/external-feedback-receipt.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass External Feedback Receipt fixture."),
    ("fixtures/real-adopter-scenario-import/pass/external-feedback-backlog-bridge.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass External Feedback Backlog Bridge fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-loop-backlog-item.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Loop backlog item fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-owner-prioritization-receipt.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Owner receipt fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-spec-eval-candidate.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Spec/Eval candidate fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-spec-eval-authoring-receipt.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Spec/Eval authoring receipt fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-spec-eval-brief.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Spec/Eval brief fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-loop-brief-intake-receipt.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Loop Brief Intake receipt fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-loop-scenario.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Loop scenario fixture."),
    ("fixtures/real-adopter-scenario-import/pass/product-loop-run.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass Product Loop run fixture."),
    ("fixtures/real-adopter-scenario-import/pass/real-adopter-scenario-import-report.json", "delivery_trust_case_harness_fixture", "Real-Adopter Scenario Import pass report fixture."),
    *[
        (
            f"fixtures/spec-eval-scenario-execution-rehearsal/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Spec/Eval Scenario Execution Rehearsal {case_id} {artifact} fixture.",
        )
        for case_id in SPEC_EVAL_SCENARIO_EXECUTION_REHEARSAL_CASES
        for artifact in SPEC_EVAL_SCENARIO_EXECUTION_REHEARSAL_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/sandboxed-patch-proposal-rehearsal/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Sandboxed Patch Proposal Rehearsal {case_id} {artifact} fixture.",
        )
        for case_id in SANDBOXED_PATCH_PROPOSAL_REHEARSAL_CASES
        for artifact in SANDBOXED_PATCH_PROPOSAL_REHEARSAL_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-operator-handoff-bridge/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Operator Handoff Bridge {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_OPERATOR_HANDOFF_BRIDGE_CASES
        for artifact in PATCH_PROPOSAL_OPERATOR_HANDOFF_BRIDGE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-acceptance-drill/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Acceptance Drill {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_ACCEPTANCE_DRILL_CASES
        for artifact in PATCH_PROPOSAL_ACCEPTANCE_DRILL_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-external-work-order-pack/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal External Work Order Pack {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_EXTERNAL_WORK_ORDER_PACK_CASES
        for artifact in PATCH_PROPOSAL_EXTERNAL_WORK_ORDER_PACK_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-external-operator-completion/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal External Operator Completion {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_EXTERNAL_OPERATOR_COMPLETION_CASES
        for artifact in PATCH_PROPOSAL_EXTERNAL_OPERATOR_COMPLETION_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-handoff-boundary-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer-Handoff Boundary Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_HANDOFF_BOUNDARY_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_HANDOFF_BOUNDARY_GATE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-delivery-envelope/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Delivery Envelope {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_DELIVERY_ENVELOPE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_DELIVERY_ENVELOPE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-delivery-rehearsal/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Delivery Rehearsal {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_DELIVERY_REHEARSAL_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_DELIVERY_REHEARSAL_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-delivery-outcome/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Delivery Outcome Receipt {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_DELIVERY_OUTCOME_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_DELIVERY_OUTCOME_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-intake/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Intake Receipt {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_INTAKE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_INTAKE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-backlog-bridge/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Backlog Bridge {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_BACKLOG_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_BACKLOG_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-product-owner-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Product Owner Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_OWNER_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_OWNER_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-spec-eval-authoring-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Spec/Eval Authoring Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_SPEC_EVAL_AUTHORING_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_SPEC_EVAL_AUTHORING_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-product-loop-brief-intake-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Product Loop Brief Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-delivery-trust-intake-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Delivery Trust Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_INTAKE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_INTAKE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-delivery-trust-case-bridge/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Delivery Trust Case Bridge {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-boundary-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_BOUNDARY_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_BOUNDARY_GATE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-rehearsal/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Rehearsal {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_REHEARSAL_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_REHEARSAL_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-outcome/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_OUTCOME_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_OUTCOME_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-intake/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_INTAKE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_INTAKE_ARTIFACTS[case_id]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BACKLOG_BRIDGE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BACKLOG_BRIDGE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-owner-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_OWNER_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_OWNER_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_SPEC_EVAL_AUTHORING_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_SPEC_EVAL_AUTHORING_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-product-loop-brief-intake-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_PRODUCT_LOOP_BRIEF_INTAKE_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-intake-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_INTAKE_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_INTAKE_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_DELIVERY_TRUST_CASE_BRIDGE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-boundary-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BOUNDARY_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_BOUNDARY_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-rehearsal/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REHEARSAL_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REHEARSAL_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-outcome/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_OUTCOME_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_OUTCOME_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_LOOP_CLOSURE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_LOOP_CLOSURE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BRIDGE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BRIDGE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-intake-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_INTAKE_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_INTAKE_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BACKLOG_BRIDGE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_BACKLOG_BRIDGE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-owner-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_OWNER_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_OWNER_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_SPEC_EVAL_AUTHORING_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_SPEC_EVAL_AUTHORING_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_LOOP_BRIEF_INTAKE_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_PRODUCT_LOOP_BRIEF_INTAKE_GATE_ARTIFACTS[
            case_id
        ]
    ],
    *[
        (
            f"fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-delivery-trust-intake-gate/{case_id}/{artifact}",
            "delivery_trust_case_harness_fixture",
            f"Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate {case_id} {artifact} fixture.",
        )
        for case_id in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_DELIVERY_TRUST_INTAKE_GATE_CASES
        for artifact in PATCH_PROPOSAL_CUSTOMER_FEEDBACK_CONTROLLED_FOLLOW_UP_FEEDBACK_REOPEN_INTAKE_DELIVERY_TRUST_INTAKE_GATE_ARTIFACTS[
            case_id
        ]
    ],
    ("platform/okf/examples/demo-session.json", "okf_example", "Demo learning session input for OKF-style knowledge-bundle export."),
    ("platform/okf/examples/demo-okf-bundle/manifest.json", "okf_example", "Demo OKF-style knowledge-bundle manifest."),
    ("platform/okf/examples/demo-okf-bundle/overview.md", "okf_example", "Demo OKF-style session overview note."),
    ("platform/okf/examples/demo-okf-bundle/sources.md", "okf_example", "Demo OKF-style source-reference note."),
    ("platform/okf/examples/demo-okf-bundle/mastery.md", "okf_example", "Demo OKF-style mastery note."),
    ("platform/okf/examples/demo-okf-bundle/decisions.md", "okf_example", "Demo OKF-style handoff decision note."),
    ("platform/okf/examples/demo-okf-bundle/concepts/overview.md", "okf_example", "Demo OKF-style concept overview note."),
    ("platform/okf/examples/demo-okf-bundle/concepts/glossary.md", "okf_example", "Demo OKF-style glossary note."),
    ("platform/okf/examples/demo-okf-bundle/questions/review.md", "okf_example", "Demo OKF-style question review note with answers omitted."),
    ("platform/generated/study-anything-plugin-ecosystem-adoption-kit.json", "submission_report", "Copy-ready plugin ecosystem adoption kit for platform submissions."),
    ("platform/generated/study-anything-deployment-hardening.json", "submission_report", "Deployment hardening and clean-clone operator path report."),
    ("platform/generated/study-anything-learning-enrichment-bridge.json", "submission_report", "Learning Enrichment operator bridge report for platform Agents, NotebookLM, Obsidian, and second-brain handoff."),
    ("platform/packs/README.md", "platform_pack", "Platform pack index."),
    ("platform/packs/kimi/README.md", "platform_pack", "Kimi Work and Kimi-compatible setup."),
    ("platform/packs/kimi/pack.json", "platform_pack", "Machine-readable Kimi pack."),
    ("platform/packs/codex/README.md", "platform_pack", "Codex setup and command flow."),
    ("platform/packs/codex/pack.json", "platform_pack", "Machine-readable Codex pack."),
    ("platform/packs/workbuddy/README.md", "platform_pack", "WorkBuddy-style HTTP workspace setup."),
    ("platform/packs/workbuddy/pack.json", "platform_pack", "Machine-readable WorkBuddy pack."),
    ("platform/packs/hermes/README.md", "platform_pack", "Hermes Agent Skill setup."),
    ("platform/packs/hermes/pack.json", "platform_pack", "Machine-readable Hermes Agent pack."),
    (".codebuddy-plugin/marketplace.json", "workbuddy_marketplace", "CodeBuddy/WorkBuddy marketplace listing for the Study Anything plugin."),
    ("plugins/study-anything/.codebuddy-plugin/plugin.json", "workbuddy_marketplace", "Installable CodeBuddy/WorkBuddy plugin manifest."),
    ("plugins/study-anything/README.md", "workbuddy_marketplace", "Installable CodeBuddy/WorkBuddy plugin README."),
    ("plugins/study-anything/skills/study-anything/SKILL.md", "workbuddy_marketplace", "CodeBuddy/WorkBuddy Study Anything skill entrypoint."),
    ("plugins/study-anything/commands/start.md", "workbuddy_marketplace", "CodeBuddy/WorkBuddy start command."),
    ("plugins/study-anything/commands/learn.md", "workbuddy_marketplace", "CodeBuddy/WorkBuddy learn command."),
    ("plugins/study-anything/commands/diagnose.md", "workbuddy_marketplace", "CodeBuddy/WorkBuddy diagnose command."),
    ("plugins/study-anything/commands/export.md", "workbuddy_marketplace", "CodeBuddy/WorkBuddy export command."),
    ("platform/generated/study-anything-codex-plugin-pack.json", "plugin_pack", "Codex downloadable plugin pack sidecar manifest."),
    ("platform/generated/study-anything-codex-plugin-pack.zip", "plugin_pack", "Codex downloadable plugin pack archive."),
    ("platform/generated/study-anything-codex-plugin-pack.sha256", "plugin_pack", "Codex downloadable plugin pack checksum."),
    ("platform/generated/study-anything-kimi-plugin-pack.json", "plugin_pack", "Kimi downloadable plugin pack sidecar manifest."),
    ("platform/generated/study-anything-kimi-plugin-pack.zip", "plugin_pack", "Kimi downloadable plugin pack archive."),
    ("platform/generated/study-anything-kimi-plugin-pack.sha256", "plugin_pack", "Kimi downloadable plugin pack checksum."),
    ("platform/generated/study-anything-workbuddy-plugin-pack.json", "plugin_pack", "WorkBuddy downloadable plugin pack sidecar manifest."),
    ("platform/generated/study-anything-workbuddy-plugin-pack.zip", "plugin_pack", "WorkBuddy downloadable plugin pack archive."),
    ("platform/generated/study-anything-workbuddy-plugin-pack.sha256", "plugin_pack", "WorkBuddy downloadable plugin pack checksum."),
    ("platform/generated/study-anything-hermes-plugin-pack.json", "plugin_pack", "Hermes downloadable plugin pack sidecar manifest."),
    ("platform/generated/study-anything-hermes-plugin-pack.zip", "plugin_pack", "Hermes downloadable plugin pack archive."),
    ("platform/generated/study-anything-hermes-plugin-pack.sha256", "plugin_pack", "Hermes downloadable plugin pack checksum."),
    ("platform/generated/study-anything-platform-plugin-downloads.json", "plugin_pack", "Public GitHub Release download index for platform plugin packs."),
    ("platform/generated/study-anything-platform-plugin-downloads.md", "plugin_pack", "Human-readable GitHub Release download index for platform plugin packs."),
    ("platform/generated/study-anything-workbuddy-codebuddy-marketplace.json", "workbuddy_marketplace", "Generated CodeBuddy/WorkBuddy marketplace verification report."),
    ("platform/generated/study-anything-workbuddy-codebuddy-marketplace.md", "workbuddy_marketplace", "Human-readable CodeBuddy/WorkBuddy marketplace verification report."),
    ("skills/study-anything/SKILL.md", "skill", "Codex Skill entrypoint."),
    ("skills/study-anything/agents/openai.yaml", "skill", "OpenAI-compatible Skill agent metadata."),
    ("scripts/openai_compatible_agent_gateway.py", "gateway", "User-owned local HTTP Agent gateway."),
    ("scripts/mock_http_agent.py", "gateway", "Deterministic mock HTTP Agent for smoke tests."),
    ("scripts/setup_env.py", "runtime", "Generate local .env files with development-safe local secrets."),
    ("scripts/check_env.py", "runtime", "Validate required local environment variables before launch."),
    ("scripts/doctor.sh", "diagnostics", "Self-host doctor for Docker, ports, env, and Compose config."),
    ("scripts/self_host_soak.py", "diagnostics", "Metadata-only bounded self-host health soak receipt generator."),
    ("scripts/verify_self_host_soak.py", "verification", "Deterministic self-host soak and privacy-boundary verifier."),
    ("scripts/self_host_reliability_matrix.py", "diagnostics", "Isolated source-build and published-image restart/recovery matrix runner."),
    ("scripts/verify_self_host_reliability_matrix.py", "verification", "Deterministic scheduled reliability receipt and workflow verifier."),
    ("scripts/reliability_evidence_index.py", "diagnostics", "Offline metadata-only longitudinal reliability index builder."),
    ("scripts/verify_reliability_evidence_index.py", "verification", "Deterministic reliability index, privacy, and workflow wiring verifier."),
    ("scripts/verify_strict_reliability_acceptance.py", "verification", "Verify one real strict dual-path run and its bounded index replay."),
    ("fixtures/reliability/run-29060766261/source-build-receipt.json", "fixture", "Metadata-only strict source-build reliability receipt."),
    ("fixtures/reliability/run-29060766261/published-image-receipt.json", "fixture", "Metadata-only strict published-image reliability receipt."),
    ("fixtures/reliability/run-29060766261/reliability-index.json", "fixture", "Metadata-only strict dual-path reliability index."),
    ("fixtures/reliability/run-29060766261/remote-evidence.json", "fixture", "Redacted GitHub run and artifact metadata for strict reliability acceptance."),
    ("platform/generated/study-anything-strict-reliability-acceptance.json", "verification_report", "Generated strict reliability acceptance report."),
    ("scripts/verify_container_security.py", "verification", "Deterministic GitHub Actions and container security baseline verifier."),
    ("scripts/verify_github_security_posture.py", "verification", "Deterministic and read-only live GitHub repository security posture verifier."),
    (".github/workflows/reliability-soak.yml", "workflow", "Scheduled real-time source-build and published-image reliability matrix."),
    ("scripts/generated_evidence_topology.py", "verification", "Release-distribution evidence dependency and feedback-edge orchestrator."),
    ("scripts/verify_generated_evidence_topology.py", "verification", "Deterministic topology, convergence, and privacy-boundary verifier."),
    ("scripts/launch_self_host.sh", "runtime", "Docker Compose self-host launcher."),
    ("scripts/stop_self_host.sh", "runtime", "Docker Compose self-host stop helper."),
    ("scripts/verify_published_image_launch.py", "verification", "Disposable GHCR published-image launch verifier."),
    ("scripts/start_here.sh", "runtime", "Beginner-friendly one-command local launcher."),
    ("scripts/launch_skill_mode.sh", "runtime", "Local Skill Mode API launcher."),
    ("scripts/stop_skill_mode.sh", "runtime", "Local Skill Mode API stop helper."),
    ("scripts/run_skill_mode_demo.sh", "verification", "One-command Skill Mode demo and eval gate."),
    ("scripts/study_anything_cli.py", "cli", "CLI for learning loop and evidence commands."),
    ("scripts/install_local_plugin.py", "cli", "CLI for explicit local plugin quarantine and approved install."),
    ("scripts/localhost_diagnostics.py", "diagnostics", "Shared localhost diagnostics and redaction helpers."),
    ("scripts/verify_external_adoption.py", "verification", "Adoption-proof-v1 verifier for external operators."),
    ("scripts/verify_clean_clone_adoption.py", "verification", "Disposable clean-clone Skill Mode and gateway adoption verifier."),
    ("scripts/verify_adoption_telemetry.py", "verification", "Aggregate adoption telemetry and PMF readiness verifier."),
    ("scripts/verify_agent_gateway_hardening.py", "verification", "User-owned Agent gateway hardening and privacy verifier."),
    ("scripts/verify_external_agent_adapter_hardening.py", "verification", "External Agent eval adapter hardening and bad-output diagnostics verifier."),
    ("scripts/verify_notebooklm_obsidian_bridge_hardening.py", "verification", "NotebookLM, Obsidian, and Learning Enrichment bridge privacy verifier."),
    ("scripts/verify_plugin_quarantine.py", "verification", "Plugin trust quarantine and explicit approval verifier."),
    ("scripts/verify_security_recovery_hardening.py", "verification", "Security recovery, backup manifest, and sync restore privacy verifier."),
    ("scripts/verify_platform_submission_dry_run.py", "verification", "External platform submission dry-run verifier."),
    ("scripts/verify_platform_manual_submission_rehearsal.py", "verification", "Manual platform-submission rehearsal verifier."),
    ("scripts/verify_first_lesson_authoring_kit.py", "verification", "Copyable first-run lesson authoring kit verifier."),
    ("scripts/verify_external_eval_marketplace_harness.py", "verification", "Marketplace-quality external Agent eval harness verifier."),
    ("scripts/real_agent_eval_bridge.py", "cli", "Build user-owned real-agent eval bridge and learning-quality reports."),
    ("scripts/verify_real_agent_eval_bridge.py", "verification", "Verify user-owned real-agent eval receipt bridge reports."),
    ("scripts/verify_workbuddy_real_agent_learning_quality.py", "verification", "Verify WorkBuddy/Kimi/Codex real-agent learning-quality reports."),
    ("scripts/verify_agent_eval_marketplace_enforcement.py", "verification", "Agent eval marketplace enforcement verifier."),
    ("scripts/verify_platform_adoption_feedback_diagnostics.py", "verification", "Platform import diagnostics and feedback boundary verifier."),
    ("scripts/generate_platform_feedback_package.py", "diagnostics", "Generate a local-only redacted platform feedback package."),
    ("scripts/generate_platform_field_rehearsal.py", "diagnostics", "Generate redacted field-adoption rehearsal transcripts and failed-import fixtures."),
    ("scripts/verify_platform_field_rehearsal.py", "verification", "Verify field-adoption rehearsals, import quirks, failed-import fixtures, and pack inclusion."),
    ("scripts/generate_platform_support_triage.py", "diagnostics", "Generate GitHub-first issue templates, support ticket fixtures, and support triage report."),
    ("scripts/verify_platform_support_triage.py", "verification", "Verify support triage redaction, actionability, pack inclusion, and docs."),
    ("scripts/generate_platform_support_bundle_replay.py", "diagnostics", "Generate maintainer replay evidence for redacted platform support bundles."),
    ("scripts/verify_platform_support_bundle_replay.py", "verification", "Verify support bundle replay evidence, fixtures, and adoption pack inclusion."),
    ("scripts/replay_support_bundle.py", "verification", "Replay a redacted platform support bundle into a maintainer-facing issue summary."),
    ("scripts/generate_platform_onboarding_readiness.py", "diagnostics", "Generate first-adopter onboarding, triage dashboard, and release-blocker fixtures."),
    ("scripts/verify_platform_onboarding_readiness.py", "verification", "Verify onboarding readiness, SLA labels, dashboard, release blockers, packs, submission, and docs."),
    ("scripts/generate_platform_public_support_status.py", "diagnostics", "Generate public support status, maintainer dashboard, and status-linkage fixtures."),
    ("scripts/verify_platform_public_support_status.py", "verification", "Verify public support status, dashboard, status-linkage fixtures, packs, submission, and docs."),
    ("scripts/generate_published_image_evidence.py", "diagnostics", "Generate published-image evidence, checksum, and release fallback fixtures."),
    ("scripts/verify_published_image_evidence.py", "verification", "Verify published-image evidence, fixtures, platform packs, submission, adoption pack, and docs."),
    ("scripts/generate_release_asset_adoption.py", "diagnostics", "Generate GitHub Release asset adoption replay evidence and fixtures."),
    ("scripts/verify_release_asset_adoption.py", "verification", "Verify GitHub Release asset download, digest, pack, evidence, and runtime replay."),
    ("scripts/bootstrap_from_release.py", "verification", "Bootstrap external platform adoption from public GitHub Release assets."),
    ("scripts/generate_release_asset_bootstrap.py", "diagnostics", "Generate GitHub Release asset bootstrap evidence."),
    ("platform/bootstrap/study_anything_release_bootstrap.py", "verification", "Standalone release-only cleanroom bootstrapper."),
    ("scripts/generate_release_cleanroom_bootstrap.py", "diagnostics", "Generate release-only cleanroom bootstrap evidence."),
    ("scripts/replay_platform_agent_from_release.py", "verification", "Replay platform Agent tool calls from public GitHub Release assets."),
    ("scripts/generate_platform_agent_replay.py", "diagnostics", "Generate platform Agent release replay evidence."),
    ("scripts/generate_adopter_evidence_archive.py", "diagnostics", "Generate external adopter evidence archive, checksum, and maintainer handoff fixtures."),
    ("scripts/verify_adopter_evidence_archive.py", "verification", "Verify adopter evidence archive, fixtures, platform packs, submission, adoption pack, and docs."),
    ("scripts/verify_plugin_ecosystem_adoption_kit.py", "verification", "Plugin ecosystem sample, registry, and trust-policy adoption verifier."),
    ("scripts/verify_deployment_hardening.py", "verification", "Deployment hardening and published-image operator path verifier."),
    ("scripts/verify_learning_enrichment_bridge.py", "verification", "Learning Enrichment operator bridge verifier."),
    ("scripts/export_okf_bundle.py", "cli", "Export a Study Anything session into an OKF-style Cognitive Black Box Markdown bundle."),
    ("scripts/verify_okf_bundle.py", "verification", "Verify OKF-style Cognitive Black Box bundle frontmatter, consumers, and privacy boundaries."),
    ("scripts/verify_ecosystem_submission_pack.py", "verification", "Ecosystem submission pack verifier for external platform review."),
    ("scripts/verify_cognitive_loop_contracts.py", "verification", "Cognitive Loop contract bootstrap verifier."),
    ("scripts/verify_operating_model_loops.py", "verification", "Verify Cognitive Black Box operating-model loop contract and release-stack boundaries."),
    ("scripts/verify_release_stack_policy.py", "verification", "Verify release-stack recursion guard and product runway reset."),
    ("scripts/verify_dual_loop_contracts.py", "verification", "Dual-Loop schema, artifact, and metadata-only boundary verifier."),
    ("scripts/failure_sandbox_lite.py", "cli", "Dual-Loop deterministic Failure Sandbox Lite artifact generator."),
    ("scripts/verify_failure_sandbox_lite.py", "verification", "Dual-Loop Failure Sandbox Lite CLI verifier."),
    ("scripts/attention_reconstruction_lite.py", "cli", "Dual-Loop deterministic Attention Reconstruction Lite artifact generator."),
    ("scripts/verify_attention_reconstruction_lite.py", "verification", "Dual-Loop Attention Reconstruction Lite CLI verifier."),
    ("scripts/dual_loop_gate.py", "cli", "Dual-Loop propagation gate evaluator for structured sandbox and attention artifacts."),
    ("scripts/verify_dual_loop_gate.py", "verification", "Dual-Loop propagation gate pass/fail fixture verifier."),
    ("scripts/delivery_trust_receipt.py", "cli", "Build metadata-only Delivery Trust Receipt artifacts from Dual-Loop evidence."),
    ("scripts/verify_delivery_trust_receipt.py", "verification", "Verify Delivery Trust Receipt pass/fail fixtures and trust-boundary rejection cases."),
    ("scripts/customer_handoff_package.py", "cli", "Build and validate metadata-only CustomerHandoffPackage JSON, HTML, and ZIP artifacts."),
    ("scripts/verify_customer_handoff_package.py", "verification", "Verify CustomerHandoffPackage pass/fail fixtures, ZIP integrity, and scope boundaries."),
    ("scripts/run_dual_loop_scenario_harness.py", "cli", "Run deterministic Dual Loop customer-delivery trust scenario harness."),
    ("scripts/verify_dual_loop_scenario_harness.py", "verification", "Verify Dual Loop trust scenario fixtures, runner output, and handoff gating."),
    ("scripts/generate_dual_loop_trust_scenario_pack.py", "cli", "Generate portable Dual Loop trust scenario pack assets."),
    ("scripts/verify_dual_loop_trust_scenario_pack.py", "verification", "Verify portable Dual Loop trust scenario pack assets."),
    ("scripts/verify_dual_loop_trust_pack_consumer_walkthrough.py", "verification", "Verify external ZIP-only consumption of the Dual Loop trust scenario pack."),
    ("scripts/cbb_protocol_cli.py", "cli", "Cognitive Black Box deterministic protocol demo artifact generator."),
    ("scripts/cbb_gate.py", "cli", "Cognitive Black Box delivery decision gate evaluator."),
    ("fixtures/cbb-v1-contracts/pass.json", "fixture", "Canonical CBB Protocol v1 passing compatibility fixture."),
    ("fixtures/cbb-v1-contracts/missing-evidence.json", "fixture", "Canonical CBB Protocol v1 missing-evidence fixture."),
    ("fixtures/cbb-v1-contracts/hard-deny.json", "fixture", "Canonical CBB Protocol v1 hard-deny fixture."),
    ("fixtures/cbb-v1-contracts/stale.json", "fixture", "Canonical CBB Protocol v1 stale reconstruction fixture."),
    ("fixtures/cbb-v1-contracts/secret-like.json", "fixture", "Canonical CBB Protocol v1 secret-like rejection fixture."),
    ("fixtures/cbb-v1-contracts/malformed.json", "fixture", "Canonical CBB Protocol v1 malformed payload fixture."),
    ("fixtures/cbb-v1-contracts/naive-timestamp.json", "fixture", "Canonical CBB Protocol v1 timezone rejection fixture."),
    ("fixtures/cbb-v1-contracts/invalid-state.json", "fixture", "Canonical CBB Protocol v1 cross-field state rejection fixture."),
    ("fixtures/cbb-v1-contracts/scope-expansion.json", "fixture", "Canonical CBB Protocol v1 scope-expansion rejection fixture."),
    ("fixtures/cbb-v1-kernel/pass.json", "fixture", "Canonical Trust Kernel passing fixture."),
    ("fixtures/cbb-v1-kernel/missing-evidence.json", "fixture", "Canonical missing-evidence decision fixture."),
    ("fixtures/cbb-v1-kernel/failed-evidence.json", "fixture", "Canonical failed-evidence blocking fixture."),
    ("fixtures/cbb-v1-kernel/stale-reconstruction.json", "fixture", "Canonical stale reconstruction fixture."),
    ("fixtures/cbb-v1-kernel/hard-deny.json", "fixture", "Canonical hard-deny fixture."),
    ("fixtures/cbb-v1-kernel/reference-mismatch.json", "fixture", "Canonical reference-integrity fixture."),
    ("fixtures/cbb-v1-kernel/claim-boundary-narrowing.json", "fixture", "Canonical claim-boundary narrowing fixture."),
    ("fixtures/cbb-v1-provenance/pass-signed.json", "fixture", "Canonical locally signed provenance fixture."),
    ("fixtures/cbb-v1-provenance/unsigned-development.json", "fixture", "Unsigned development provenance rejection fixture."),
    ("fixtures/cbb-v1-provenance/expired.json", "fixture", "Expired provenance rejection fixture."),
    ("fixtures/cbb-v1-provenance/revoked.json", "fixture", "Local revocation rejection fixture."),
    ("fixtures/cbb-v1-provenance/replay.json", "fixture", "Replay nonce consumption fixture."),
    ("fixtures/cbb-v1-provenance/tampered-policy.json", "fixture", "Policy tamper rejection fixture."),
    ("fixtures/cbb-v1-provenance/tampered-evidence.json", "fixture", "Evidence tamper rejection fixture."),
    ("fixtures/cbb-v1-provenance/tampered-reconstruction.json", "fixture", "Reconstruction tamper rejection fixture."),
    ("fixtures/cbb-v1-provenance/tampered-decision.json", "fixture", "Decision tamper rejection fixture."),
    ("fixtures/cbb-v1-provenance/tampered-receipt.json", "fixture", "Delivery receipt envelope tamper rejection fixture."),
    ("fixtures/cbb-v1-provenance/tampered-signature.json", "fixture", "Signature tamper rejection fixture."),
    ("fixtures/cbb-v1-provenance/wrong-public-key.json", "fixture", "Wrong public key rejection fixture."),
    ("fixtures/cbb-v1-scenarios/personal-local-prototype.json", "fixture", "Personal-local scenario allow fixture."),
    ("fixtures/cbb-v1-scenarios/public-fake-data-demo.json", "fixture", "Public fake-data demo allow fixture."),
    ("fixtures/cbb-v1-scenarios/limited-beta.json", "fixture", "Limited-beta candidate fixture."),
    ("fixtures/cbb-v1-scenarios/paid-customer-candidate.json", "fixture", "Controlled paid-customer candidate fixture."),
    ("fixtures/cbb-v1-scenarios/production-candidate-blocked.json", "fixture", "Production candidate missing-evidence fixture."),
    ("fixtures/cbb-v1-scenarios/regulated-or-irreversible-blocked.json", "fixture", "Regulated or irreversible hard-deny fixture."),
    ("scripts/generate_cbb_v1_contract_assets.py", "generator", "Generate canonical CBB Protocol v1 schemas and deterministic fixtures."),
    ("scripts/generate_cbb_v1_provenance_assets.py", "generator", "Generate deterministic public-only CBB Protocol v1 provenance fixtures."),
    ("scripts/verify_cbb_v1_contracts.py", "verification", "Verify canonical CBB Protocol v1 contracts and deterministic serialization."),
    ("scripts/verify_cbb_v0_compatibility.py", "verification", "Verify v0 mappings preserve or narrow delivery scope."),
    ("scripts/verify_cbb_v1_kernel.py", "verification", "Verify canonical deterministic CBB Protocol v1 Trust Kernel decisions."),
    ("scripts/verify_cbb_runtime_isolation.py", "verification", "Verify the canonical Trust Kernel has no Agentic runtime authority."),
    ("scripts/cbb_provenance.py", "cli", "Generate local keys, sign canonical receipt sets, and verify packages offline."),
    ("scripts/verify_cbb_v1_provenance.py", "verification", "Verify local signing, expiry, revocation, replay, and scope boundaries."),
    ("scripts/verify_cbb_v1_tamper_cases.py", "verification", "Verify canonical object, signature, and public-key tamper rejection."),
    ("scripts/generate_cbb_v1_scenario_assets.py", "generator", "Generate deterministic CBB Protocol v1 scenario fixtures."),
    ("scripts/verify_cbb_v1_scenarios.py", "verification", "Verify scenario scope, actor, safeguard, and hard-deny decisions."),
    ("scripts/verify_cbb_v1_qualification.py", "verification", "Verify MRU and scoped human/model capability boundaries."),
    ("scripts/verify_cbb_protocol_contracts.py", "verification", "Cognitive Black Box protocol contract and metadata-only privacy verifier."),
    ("scripts/verify_cbb_positioning.py", "verification", "Verify protocol-first positioning, compatibility boundaries, and obsolete-brand removal."),
    ("scripts/verify_cbb_gate.py", "verification", "Cognitive Black Box delivery gate pass/fail fixture verifier."),
    ("scripts/cbb_receipt_chain.py", "cli", "Cognitive Black Box tamper-evident receipt-chain builder."),
    ("scripts/cbb_self_intake.py", "cli", "Cognitive Black Box PR self-intake receipt and evidence-pack builder."),
    ("scripts/verify_cbb_receipt_chain.py", "verification", "Verify Cognitive Black Box receipt-chain contracts, fixtures, and tamper rejection."),
    ("scripts/verify_cbb_self_intake.py", "verification", "Verify Cognitive Black Box PR self-intake receipts, evidence packs, and negative cases."),
    ("scripts/cbb_delivery_harness.py", "cli", "Cognitive Black Box tri-loop delivery scenario harness CLI."),
    ("scripts/verify_cbb_delivery_harness.py", "verification", "Verify Cognitive Black Box delivery scenario tri-loop fixtures and privacy boundaries."),
    ("scripts/product_loop_harness.py", "cli", "Product Loop Harness CLI for deterministic three-loop product development artifacts."),
    ("scripts/verify_product_loop_harness.py", "verification", "Verify Product Loop Harness fixtures, schemas, CLI output, and privacy boundaries."),
    ("scripts/delivery_trust_case_harness.py", "cli", "Delivery Trust Case Harness CLI for end-to-end controlled customer-handoff artifacts."),
    ("scripts/verify_delivery_trust_case_harness.py", "verification", "Verify Delivery Trust Case Harness fixtures, schemas, CLI output, and privacy boundaries."),
    ("scripts/generate_delivery_trust_case_pack.py", "cli", "Generate portable Delivery Trust Case pack assets."),
    ("scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py", "verification", "Verify external ZIP-only consumption of the Delivery Trust Case pack."),
    ("scripts/code_review_delivery_class_handoff.py", "cli", "Build deterministic metadata-only Code Review Delivery Class handoff artifacts."),
    ("scripts/verify_code_review_delivery_class_handoff.py", "verification", "Verify Code Review Delivery Class handoff fixtures, reports, negative checks, and privacy boundaries."),
    ("scripts/client_report_delivery_class_handoff.py", "cli", "Build deterministic metadata-only Client Report Delivery Class handoff artifacts."),
    ("scripts/verify_client_report_delivery_class_handoff.py", "verification", "Verify Client Report Delivery Class handoff fixtures, reports, negative checks, and privacy boundaries."),
    ("scripts/support_response_delivery_class_handoff.py", "cli", "Build deterministic metadata-only Support Response Delivery Class handoff artifacts."),
    ("scripts/verify_support_response_delivery_class_handoff.py", "verification", "Verify Support Response Delivery Class handoff fixtures, reports, negative checks, and privacy boundaries."),
    ("scripts/verify_delivery_class_registry.py", "verification", "Verify Delivery Class Registry assets, release gates, and privacy boundaries."),
    ("scripts/verify_trust_scenario_catalog.py", "verification", "Verify Trust Scenario Catalog assets, delivery-class alignment, release gates, and privacy boundaries."),
    ("scripts/trust_scenario_decision_gate.py", "cli", "Evaluate metadata-only Trust Scenario Catalog handoff decisions."),
    ("scripts/verify_trust_scenario_decision_gate.py", "verification", "Verify Trust Scenario Decision Gate fixtures, reports, CLI behavior, and privacy boundaries."),
    ("docs/trust-evidence-handoff-pack.md", "operator_doc", "Trust Evidence Handoff Pack guide for external operators and customer reviewers."),
    ("platform/generated/study-anything-trust-evidence-handoff-pack.json", "generated_asset", "Trust Evidence Handoff Pack manifest."),
    ("platform/generated/study-anything-trust-evidence-handoff-pack.md", "generated_asset", "Trust Evidence Handoff Pack markdown report."),
    ("platform/generated/study-anything-trust-evidence-handoff-pack.sha256", "generated_asset", "Trust Evidence Handoff Pack checksum."),
    ("platform/generated/study-anything-trust-evidence-handoff-pack.zip", "generated_asset", "Portable metadata-only Trust Evidence Handoff Pack archive."),
    ("platform/generated/study-anything-trust-evidence-handoff-pack-consumer-walkthrough.json", "generated_asset", "ZIP-only consumer walkthrough for the Trust Evidence Handoff Pack."),
    ("scripts/generate_trust_evidence_handoff_pack.py", "generator", "Generate portable Trust Evidence Handoff Pack assets."),
    ("scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py", "verification", "Verify external ZIP-only consumption of the Trust Evidence Handoff Pack."),
    ("docs/trust-evidence-acceptance-drill.md", "operator_doc", "Trust Evidence Acceptance Drill guide for external operator allow/block rehearsal."),
    ("platform/generated/study-anything-trust-evidence-acceptance-drill.json", "generated_asset", "Trust Evidence Acceptance Drill report."),
    ("platform/generated/study-anything-trust-evidence-acceptance-drill.md", "generated_asset", "Trust Evidence Acceptance Drill markdown report."),
    ("scripts/verify_trust_evidence_acceptance_drill.py", "verification", "Verify external operator allow/block decisions from the Trust Evidence ZIP."),
    ("docs/controlled-handoff-runbook.md", "operator_doc", "Controlled Handoff Runbook guide for external operator handoff preparation."),
    ("platform/generated/study-anything-controlled-handoff-runbook.json", "generated_asset", "Controlled Handoff Runbook report."),
    ("platform/generated/study-anything-controlled-handoff-runbook.md", "generated_asset", "Controlled Handoff Runbook markdown report."),
    ("scripts/verify_controlled_handoff_runbook.py", "verification", "Verify controlled handoff preparation steps derived from Trust Evidence decisions."),
    ("docs/customer-delivery-trust-envelope.md", "operator_doc", "Customer Delivery Trust Envelope guide for pre-customer-send boundary checks."),
    ("platform/generated/study-anything-customer-delivery-trust-envelope.json", "generated_asset", "Customer Delivery Trust Envelope report."),
    ("platform/generated/study-anything-customer-delivery-trust-envelope.md", "generated_asset", "Customer Delivery Trust Envelope markdown report."),
    ("scripts/verify_customer_delivery_trust_envelope.py", "verification", "Verify customer-delivery envelope boundaries derived from controlled handoff evidence."),
    ("docs/customer-delivery-rehearsal.md", "operator_doc", "Customer Delivery Rehearsal guide for ready/block pre-send decisions."),
    ("platform/generated/study-anything-customer-delivery-rehearsal.json", "generated_asset", "Customer Delivery Rehearsal report."),
    ("platform/generated/study-anything-customer-delivery-rehearsal.md", "generated_asset", "Customer Delivery Rehearsal markdown report."),
    ("scripts/verify_customer_delivery_rehearsal.py", "verification", "Verify customer-delivery ready/block rehearsal boundaries from the trust envelope."),
    ("docs/code-review-operator-handoff-rehearsal.md", "operator_doc", "Code Review Operator Handoff Rehearsal guide for metadata-only operator decisions."),
    ("platform/generated/study-anything-code-review-operator-handoff-rehearsal.json", "generated_asset", "Code Review Operator Handoff Rehearsal report."),
    ("platform/generated/study-anything-code-review-operator-handoff-rehearsal.md", "generated_asset", "Code Review Operator Handoff Rehearsal markdown report."),
    ("scripts/verify_code_review_operator_handoff_rehearsal.py", "verification", "Verify Code Review operator handoff decisions from delivery-class and customer rehearsal evidence."),
    ("docs/client-report-operator-handoff-rehearsal.md", "operator_doc", "Client Report Operator Handoff Rehearsal guide for metadata-only operator decisions."),
    ("platform/generated/study-anything-client-report-operator-handoff-rehearsal.json", "generated_asset", "Client Report Operator Handoff Rehearsal report."),
    ("platform/generated/study-anything-client-report-operator-handoff-rehearsal.md", "generated_asset", "Client Report Operator Handoff Rehearsal markdown report."),
    ("scripts/verify_client_report_operator_handoff_rehearsal.py", "verification", "Verify Client Report operator handoff decisions from delivery-class and customer rehearsal evidence."),
    ("docs/support-response-operator-handoff-rehearsal.md", "operator_doc", "Support Response Operator Handoff Rehearsal guide for metadata-only operator decisions."),
    ("platform/generated/study-anything-support-response-operator-handoff-rehearsal.json", "generated_asset", "Support Response Operator Handoff Rehearsal report."),
    ("platform/generated/study-anything-support-response-operator-handoff-rehearsal.md", "generated_asset", "Support Response Operator Handoff Rehearsal markdown report."),
    ("scripts/verify_support_response_operator_handoff_rehearsal.py", "verification", "Verify Support Response operator handoff decisions from delivery-class and customer rehearsal evidence."),
    ("scripts/external_feedback_receipt.py", "verification", "Build deterministic External Feedback Receipt fixtures."),
    ("scripts/verify_external_feedback_receipt.py", "verification", "Verify External Feedback Receipt product-loop feedback boundaries."),
    ("scripts/external_feedback_backlog_bridge.py", "verification", "Build Product Loop backlog bridge fixtures from External Feedback receipts."),
    ("scripts/verify_external_feedback_backlog_bridge.py", "verification", "Verify External Feedback Backlog Bridge product-loop boundaries."),
    ("scripts/product_owner_prioritization_gate.py", "verification", "Build Product Owner Prioritization Gate fixtures from Product Loop backlog items."),
    ("scripts/verify_product_owner_prioritization_gate.py", "verification", "Verify Product Owner Prioritization Gate spec/eval candidate boundaries."),
    ("scripts/product_spec_eval_authoring_gate.py", "verification", "Build Product Spec/Eval Authoring Gate fixtures from spec/eval candidates."),
    ("scripts/verify_product_spec_eval_authoring_gate.py", "verification", "Verify Product Spec/Eval Authoring Gate metadata-only brief boundaries."),
    ("scripts/product_loop_brief_intake.py", "verification", "Build Product Loop Brief Intake fixtures from Product Spec/Eval briefs."),
    ("scripts/verify_product_loop_brief_intake.py", "verification", "Verify Product Loop Brief Intake metadata-only bridge boundaries."),
    ("scripts/end_to_end_trust_chain_harness.py", "verification", "Build metadata-only end-to-end Cognitive Black Box trust-chain reports."),
    ("scripts/verify_end_to_end_trust_chain_harness.py", "verification", "Verify end-to-end trust-chain fixtures, CLI output, and privacy boundaries."),
    ("scripts/real_adopter_scenario_import.py", "verification", "Import bounded real-adopter issue summaries into Product Loop evidence."),
    ("scripts/verify_real_adopter_scenario_import.py", "verification", "Verify real-adopter scenario import fixtures, chain continuity, and privacy boundaries."),
    ("scripts/spec_eval_scenario_execution_rehearsal.py", "verification", "Build metadata-only Spec/Eval Scenario Execution Rehearsal artifacts."),
    ("scripts/verify_spec_eval_scenario_execution_rehearsal.py", "verification", "Verify Spec/Eval Scenario Execution Rehearsal fixtures, CLI output, and privacy boundaries."),
    ("scripts/sandboxed_patch_proposal_rehearsal.py", "verification", "Build metadata-only Sandboxed Patch Proposal Rehearsal artifacts."),
    ("scripts/verify_sandboxed_patch_proposal_rehearsal.py", "verification", "Verify Sandboxed Patch Proposal Rehearsal fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_operator_handoff_bridge.py", "verification", "Build metadata-only Patch Proposal Operator Handoff Bridge artifacts."),
    ("scripts/verify_patch_proposal_operator_handoff_bridge.py", "verification", "Verify Patch Proposal Operator Handoff Bridge fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_acceptance_drill.py", "verification", "Build metadata-only Patch Proposal Acceptance Drill artifacts."),
    ("scripts/verify_patch_proposal_acceptance_drill.py", "verification", "Verify Patch Proposal Acceptance Drill fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_external_work_order_pack.py", "verification", "Build metadata-only Patch Proposal External Work Order Pack artifacts."),
    ("scripts/verify_patch_proposal_external_work_order_pack.py", "verification", "Verify Patch Proposal External Work Order Pack fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_external_operator_completion.py", "verification", "Build metadata-only Patch Proposal External Operator Completion artifacts."),
    ("scripts/verify_patch_proposal_external_operator_completion.py", "verification", "Verify Patch Proposal External Operator Completion fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_handoff_boundary_gate.py", "verification", "Build metadata-only Patch Proposal Customer-Handoff Boundary Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_handoff_boundary_gate.py", "verification", "Verify Patch Proposal Customer-Handoff Boundary Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_delivery_envelope.py", "verification", "Build metadata-only Patch Proposal Customer Delivery Envelope artifacts."),
    ("scripts/verify_patch_proposal_customer_delivery_envelope.py", "verification", "Verify Patch Proposal Customer Delivery Envelope fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_delivery_rehearsal.py", "verification", "Build metadata-only Patch Proposal Customer Delivery Rehearsal artifacts."),
    ("scripts/verify_patch_proposal_customer_delivery_rehearsal.py", "verification", "Verify Patch Proposal Customer Delivery Rehearsal fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_delivery_outcome_receipt.py", "verification", "Build metadata-only Patch Proposal Customer Delivery Outcome Receipt artifacts."),
    ("scripts/verify_patch_proposal_customer_delivery_outcome_receipt.py", "verification", "Verify Patch Proposal Customer Delivery Outcome Receipt fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_intake_receipt.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Intake Receipt artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_intake_receipt.py", "verification", "Verify Patch Proposal Customer Feedback Intake Receipt fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_backlog_bridge.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Backlog Bridge artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py", "verification", "Verify Patch Proposal Customer Feedback Backlog Bridge fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_product_owner_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Product Owner Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_product_owner_gate.py", "verification", "Verify Patch Proposal Customer Feedback Product Owner Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_spec_eval_authoring_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Spec/Eval Authoring Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_spec_eval_authoring_gate.py", "verification", "Verify Patch Proposal Customer Feedback Spec/Eval Authoring Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_product_loop_brief_intake_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Product Loop Brief Intake Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_product_loop_brief_intake_gate.py", "verification", "Verify Patch Proposal Customer Feedback Product Loop Brief Intake Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_delivery_trust_intake_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Delivery Trust Intake Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_delivery_trust_intake_gate.py", "verification", "Verify Patch Proposal Customer Feedback Delivery Trust Intake Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_delivery_trust_case_bridge.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Delivery Trust Case Bridge artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_delivery_trust_case_bridge.py", "verification", "Verify Patch Proposal Customer Feedback Delivery Trust Case Bridge fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_boundary_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_boundary_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_rehearsal.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Rehearsal artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_rehearsal.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Rehearsal fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_outcome_receipt.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_outcome_receipt.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Outcome Receipt fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_intake.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Intake fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_backlog_bridge.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_backlog_bridge.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_product_owner_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_product_owner_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_product_loop_brief_intake_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_product_loop_brief_intake_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Loop Brief Intake Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_delivery_trust_intake_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_delivery_trust_intake_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Intake Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_delivery_trust_case_bridge.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_delivery_trust_case_bridge.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_boundary_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Boundary Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_rehearsal.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Rehearsal fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_outcome.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Outcome fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_loop_closure.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_loop_closure.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_bridge.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_bridge.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_intake_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_owner_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Owner Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_spec_eval_authoring_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_spec_eval_authoring_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate fixtures, CLI output, and privacy boundaries."),
    ("scripts/patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py", "verification", "Build metadata-only Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate artifacts."),
    ("scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_delivery_trust_intake_gate.py", "verification", "Verify Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Delivery Trust Intake Gate fixtures, CLI output, and privacy boundaries."),
    ("docs/operator-handoff-rehearsal-contract.md", "operator_doc", "Shared Operator Handoff Rehearsal Contract for supported delivery classes."),
    ("platform/schemas/delivery-trust/operator-handoff-rehearsal-contract-v1.schema.json", "schema", "Operator Handoff Rehearsal Contract JSON schema."),
    ("platform/generated/study-anything-operator-handoff-rehearsal-contract.json", "generated_asset", "Operator Handoff Rehearsal Contract report."),
    ("platform/generated/study-anything-operator-handoff-rehearsal-contract.md", "generated_asset", "Operator Handoff Rehearsal Contract markdown report."),
    ("scripts/verify_operator_handoff_rehearsal_contract.py", "verification", "Verify the shared operator handoff rehearsal contract across delivery classes."),
    ("scripts/cognitive_loop_cli.py", "cli", "Local Cognitive Loop contract init, verify, and static HTML artifact CLI."),
    ("scripts/verify_cognitive_loop_cli.py", "verification", "Cognitive Loop CLI and static HTML artifact verifier."),
    ("scripts/verify_cognitive_loop_run_once.py", "verification", "Cognitive Loop run-once evidence verifier."),
    ("scripts/verify_cognitive_loop_snapshot.py", "verification", "Cognitive Loop project snapshot verifier."),
    ("scripts/verify_cognitive_loop_human_gate.py", "verification", "Cognitive Loop Human Mastery Gate verifier."),
    ("scripts/verify_cognitive_loop_evidence_bundle.py", "verification", "Cognitive Loop metadata-only evidence bundle verifier."),
    ("scripts/verify_cognitive_loop_event_index.py", "verification", "Cognitive Loop metadata-only local event index verifier."),
    ("scripts/cognitive_loop_event_store.py", "cli", "Local SQLite Event Store for validated Cognitive Loop event metadata."),
    ("scripts/verify_cognitive_loop_event_store.py", "verification", "Verify the local SQLite Event Store, idempotent rebuild, HTML export, and privacy rejection path."),
    ("scripts/cognitive_loop_watcher_ingest.py", "cli", "Manual watcher-event ingest for Cognitive Loop metadata artifacts."),
    ("scripts/verify_cognitive_loop_watcher_ingest.py", "verification", "Verify manual watcher ingest, Event Index classification, Event Store projection, and privacy boundaries."),
    ("scripts/cognitive_loop_watcher_runner.py", "cli", "Bounded watcher runner-lite for metadata-only local project signals."),
    ("scripts/verify_cognitive_loop_watcher_runner.py", "verification", "Verify watcher runner-lite debounce, Event Store idempotency, Study Adapter gate, and privacy boundaries."),
    ("scripts/cognitive_loop_artifact_console.py", "cli", "Build a static metadata-only Cognitive Loop HTML Artifact Console Lite."),
    ("scripts/verify_cognitive_loop_artifact_console.py", "verification", "Verify Artifact Console Lite aggregation, links, degradation, mobile shell, and privacy boundaries."),
    ("scripts/cognitive_loop_personal_mode.py", "cli", "Build read-only Personal Plugin Mode Lite learning artifacts."),
    ("scripts/verify_cognitive_loop_personal_plugin_mode.py", "verification", "Verify Personal Plugin Mode Lite file, README, webpage, diff-summary, report, and privacy boundaries."),
    ("scripts/cognitive_loop_evolution.py", "cli", "Build read-only Cognitive Loop Evolution Report Lite artifacts."),
    ("scripts/verify_cognitive_loop_evolution_report.py", "verification", "Verify Evolution Report Lite clustering, gating, degradation, and privacy boundaries."),
    ("scripts/cognitive_loop_apply_plan.py", "cli", "Build governed low-risk Cognitive Loop Apply Plan Lite artifacts."),
    ("scripts/verify_cognitive_loop_apply_plan.py", "verification", "Verify Apply Plan Lite dry-run, explicit receipt apply, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_improvement_comparator.py", "cli", "Build read-only Cognitive Loop Improvement Comparator Lite artifacts."),
    ("scripts/verify_cognitive_loop_improvement_comparator.py", "verification", "Verify Improvement Comparator Lite status classification, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_patch_proposal.py", "cli", "Build read-only Cognitive Loop Patch Proposal Lite artifacts."),
    ("scripts/verify_cognitive_loop_patch_proposal.py", "verification", "Verify Patch Proposal Lite categories, manual-only degradation, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_mastra_evolution_receipt.py", "cli", "Build read-only Cognitive Loop Mastra Evolution Receipt Link Lite artifacts."),
    ("scripts/verify_cognitive_loop_mastra_evolution_receipt.py", "verification", "Verify Mastra Evolution Receipt Link Lite readiness, blocking, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_mastra_evolution_replay.py", "cli", "Build read-only Cognitive Loop Mastra Evolution Workflow Replay Lite artifacts."),
    ("scripts/verify_cognitive_loop_mastra_evolution_replay.py", "verification", "Verify Mastra Evolution Workflow Replay Lite replay readiness, blocking, guardrails, and privacy boundaries."),
    ("scripts/cognitive_loop_patch_apply_sandbox.py", "cli", "Build metadata-only Cognitive Loop governed patch-apply sandbox receipts."),
    ("scripts/verify_cognitive_loop_patch_apply_sandbox.py", "verification", "Verify Patch Apply Sandbox Lite readiness, rollback proof, read-only boundaries, and privacy rejection paths."),
    ("scripts/cognitive_loop_evolution_pack_export.py", "cli", "Export a metadata-only Cognitive Loop professional evolution evidence pack."),
    ("scripts/verify_cognitive_loop_evolution_pack_export.py", "verification", "Verify Evolution Pack Export Lite zip integrity, manifest hashes, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_evolution_pack_consumer.py", "verification", "Verify Evolution Pack zip-only consumer import, tamper rejection, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_pr_ci_receipt.py", "verification", "Verify PR CI receipt decisions, required checks, optional GitHub CLI metadata adapter, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py", "verification", "Verify maintainer go/no-go acceptance ledger evidence, CI fixture, and privacy boundaries."),
    ("scripts/verify_cognitive_loop_mastra_adapter.py", "verification", "Verify the Cognitive Loop Mastra adapter contract pack and privacy boundary."),
    ("scripts/verify_cognitive_loop_mastra_runtime_dry_run.py", "verification", "Verify the Cognitive Loop Mastra runtime dry-run harness and privacy boundary."),
    ("platform/mastra-runtime/README.md", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime MVP operator notes."),
    ("platform/mastra-runtime/package.json", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime package manifest."),
    ("platform/mastra-runtime/package-lock.json", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime dependency lockfile."),
    ("platform/mastra-runtime/tsconfig.json", "mastra_runtime", "Repository-started Cognitive Loop Mastra runtime TypeScript configuration."),
    ("platform/mastra-runtime/src/runtime.ts", "mastra_runtime", "Repository-started Mastra instance registration for the Cognitive Loop workflow."),
    ("platform/mastra-runtime/src/run-once.ts", "mastra_runtime", "Deterministic Mastra workflow run covering suspend, resume, bail, and no-gate paths."),
    ("platform/mastra-runtime/src/durable-run.ts", "mastra_runtime", "Deterministic durable Mastra workflow run covering cross-process resume and bail paths."),
    ("platform/mastra-runtime/src/observability.ts", "mastra_runtime", "Redacted Langfuse DTO mapping for Cognitive Loop Mastra receipts."),
    ("platform/mastra-runtime/src/observability-run.ts", "mastra_runtime", "Deterministic local Langfuse observability receipt runner."),
    ("platform/mastra-runtime/src/workflows/cognitive-loop-mastra-adapter.ts", "mastra_runtime", "Runtime-local copy of the Cognitive Loop Mastra workflow adapter kept identical to the public pack."),
    ("apps/api/study_anything/core/cognitive_loop_learning_adapter.py", "api_core", "Study Anything Learning Adapter bridge for Cognitive Loop mastery records."),
    ("apps/api/study_anything/core/dual_loop.py", "api_core", "Dual-Loop metadata-only artifact builders, validators, and propagation gate logic."),
    ("apps/api/study_anything/core/cbb_protocol.py", "api_core", "Cognitive Black Box metadata-only protocol contracts, validators, and deterministic trust kernel."),
    ("apps/api/study_anything/core/cbb_receipt_chain.py", "api_core", "Cognitive Black Box receipt-chain, self-intake, and delivery evidence pack validators."),
    ("apps/api/study_anything/core/cbb_delivery_harness.py", "api_core", "Cognitive Black Box delivery scenario tri-loop harness validators."),
    ("apps/api/study_anything/core/product_loop_harness.py", "api_core", "Product Loop Harness validators for three-loop product development evidence."),
    ("apps/api/study_anything/core/delivery_trust_case.py", "api_core", "Delivery Trust Case Harness validators for end-to-end customer handoff evidence."),
    ("scripts/cognitive_loop_study_adapter_cli.py", "cli", "CLI Lite bridge from Cognitive Loop ProjectEvent/DecisionCard files to Study Anything learning evidence."),
    ("scripts/verify_cognitive_loop_mastra_runtime_service.py", "verification", "Verify the repository-started Cognitive Loop Mastra runtime service and privacy boundary."),
    ("scripts/verify_cognitive_loop_mastra_runtime_durable.py", "verification", "Verify the durable Cognitive Loop Mastra runtime suspend/resume privacy boundary."),
    ("scripts/verify_cognitive_loop_langfuse_observability.py", "verification", "Verify redacted Langfuse observability DTO mapping for Cognitive Loop Mastra receipts."),
    ("scripts/verify_cognitive_loop_study_anything_adapter.py", "verification", "Verify Cognitive Loop Study Anything Learning Adapter mastery projection."),
    ("scripts/verify_cognitive_loop_study_adapter_cli.py", "verification", "Verify the Study Anything adapter CLI Lite evidence and HTML output."),
    ("scripts/verify_cognitive_loop_artifact_doctor.py", "verification", "Cognitive Loop metadata-only artifact doctor verifier."),
    ("scripts/verify_cognitive_loop_repair_plan.py", "verification", "Cognitive Loop manual-only repair plan verifier."),
    ("scripts/verify_cognitive_loop_artifact_index.py", "verification", "Cognitive Loop static local artifact index verifier."),
    ("scripts/cognitive_loop_review.py", "cli", "Cognitive Loop advisory code review CLI."),
    ("scripts/verify_cognitive_loop_review.py", "verification", "Cognitive Loop advisory code review verifier."),
    ("scripts/verify_cognitive_loop_review_agent_prompt.py", "verification", "External Cognitive Loop Review Agent prompt verifier."),
    ("scripts/verify_cognitive_loop_review_agent_report.py", "verification", "External Cognitive Loop Review Agent report handoff verifier."),
    ("scripts/verify_cognitive_loop_review_agent_handoff_cli.py", "verification", "External Cognitive Loop Review Agent handoff CLI verifier."),
    ("scripts/verify_cognitive_loop_review_agent_eval_harness.py", "verification", "Offline Cognitive Loop Review Agent eval harness verifier."),
    ("scripts/verify_cognitive_loop_review_agent_ci_receipt.py", "verification", "External Cognitive Loop Review Agent CI receipt verifier."),
    ("scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py", "verification", "External Cognitive Loop Review Agent PR comment pack verifier."),
    ("scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py", "verification", "External Cognitive Loop Review Agent acceptance bundle verifier."),
    ("scripts/verify_cognitive_loop_review_agent_github_workflow.py", "verification", "External Cognitive Loop Review Agent GitHub workflow template verifier."),
    ("scripts/verify_cognitive_loop_adoption_cookbook.py", "verification", "Cognitive Loop platform-agent adoption cookbook verifier."),
    ("scripts/generate_cognitive_loop_adoption_recipes.py", "verification", "Generate machine-readable Cognitive Loop platform-agent adoption recipes."),
    ("scripts/verify_cognitive_loop_recipe_replay.py", "verification", "Verify Cognitive Loop adoption recipes are replay-ready for platform Agents."),
    ("scripts/verify_cognitive_loop_skill_entrypoint.py", "verification", "Verify Cognitive Loop recipe entrypoints are visible from the Skill and platform packs."),
    ("scripts/cognitive_loop_recipe_cli.py", "cli", "Read-only Cognitive Loop recipe query CLI for platform Agents."),
    ("scripts/verify_cognitive_loop_recipe_cli.py", "verification", "Verify the read-only Cognitive Loop recipe CLI for platform Agents."),
    ("scripts/verify_cognitive_loop_recipe_cli_receipts.py", "verification", "Generate and verify deterministic Cognitive Loop recipe CLI receipts."),
    ("scripts/verify_cognitive_loop_recipe_cli_failures.py", "verification", "Generate and verify deterministic Cognitive Loop recipe CLI failure receipts."),
    ("scripts/verify_cognitive_loop_recipe_cli_schemas.py", "verification", "Generate and verify offline JSON Schemas for Cognitive Loop recipe CLI reports."),
    ("scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py", "verification", "Verify negative fixtures for Cognitive Loop recipe CLI JSON Schemas."),
    ("scripts/verify_cognitive_loop_schema_pack_consumer.py", "verification", "Verify Cognitive Loop schema evidence can be consumed from the adoption pack only."),
    ("scripts/verify_cognitive_loop_schema_pack_consumer_failures.py", "verification", "Verify Cognitive Loop schema pack consumer failure cases are safe and deterministic."),
    ("scripts/verify_cognitive_loop_pack_extract_smoke.py", "verification", "Verify the extracted adoption pack can run its included schema consumer checks."),
    ("scripts/verify_platform_handoff_checklist.py", "verification", "Generate and verify the external platform handoff checklist."),
    ("scripts/verify_launch_acceptance_ledger.py", "verification", "Generate and verify the public launch acceptance ledger."),
    ("scripts/verify_github_launch_operator_guide.py", "verification", "Generate and verify the GitHub launch operator guide proof."),
    ("scripts/verify_platform_operator_drill.py", "verification", "External platform pack consumption verifier."),
    ("scripts/verify_platform_agent_tools.py", "verification", "Platform tool manifest runtime verifier."),
    ("scripts/generate_platform_plugin_packs.py", "verification", "Generate downloadable Codex, Kimi, WorkBuddy, and Hermes platform plugin packs."),
    ("scripts/verify_platform_plugin_packs.py", "verification", "Verify platform plugin pack archives, manifests, hashes, and privacy boundaries."),
    ("scripts/generate_platform_plugin_downloads.py", "verification", "Generate the GitHub Release download index for platform plugin packs."),
    ("scripts/verify_platform_plugin_downloads.py", "verification", "Verify the GitHub Release download index for platform plugin packs."),
    ("scripts/generate_workbuddy_plugin_marketplace.py", "verification", "Generate installable CodeBuddy/WorkBuddy marketplace plugin files."),
    ("scripts/verify_workbuddy_plugin_marketplace.py", "verification", "Verify CodeBuddy/WorkBuddy marketplace plugin files and privacy boundaries."),
    ("scripts/verify_platform_ecosystem_eval_flow.py", "verification", "Full platform ecosystem learning/eval/export verifier."),
    ("scripts/verify_importer_lesson_flow.py", "verification", "NotebookLM-style importer lesson verifier."),
    ("scripts/verify_importer_runtime_retrieval_flow.py", "verification", "Importer runtime plus retrieval verifier."),
    ("scripts/verify_platform_lesson_flow.py", "verification", "Enriched platform lesson verifier."),
    ("scripts/verify_agent_eval_flow.py", "verification", "Agent eval artifact verifier."),
    ("scripts/verify_agent_eval_assets.py", "verification", "Agent eval asset and adapter contract verifier."),
    ("scripts/verify_agent_eval_baseline.py", "verification", "Agent eval baseline and regression gate verifier."),
    ("scripts/run_external_agent_evals.py", "verification", "Promptfoo/DeepEval/retrieval eval runner."),
    ("scripts/verify_openai_compatible_gateway.py", "verification", "OpenAI-compatible gateway dry-run verifier."),
    ("infra/compose/docker-compose.yml", "runtime", "Docker Compose source-build stack definition."),
    ("infra/compose/docker-compose.images.yml", "runtime", "Docker Compose published-image override."),
    ("scripts/diagnose_adoption.py", "diagnostics", "Adoption diagnostics and remediation hints."),
    ("evals/promptfoo/agent-eval-artifact.yaml", "eval", "Promptfoo eval config."),
    ("evals/deepeval/study_anything_quality_eval.py", "eval", "DeepEval-compatible native quality adapter."),
    ("evals/baselines/study-anything-agent-eval-baseline.json", "eval", "Deterministic Agent eval regression baseline."),
    ("evals/fixtures/fake-agent-learning-loop.json", "eval_fixture", "Fake deterministic Agent eval fixture."),
    ("evals/fixtures/mock-http-agent-learning-loop.json", "eval_fixture", "Mock HTTP/user-owned Agent eval fixture."),
    (".cognitive-loop/config.yaml", "cognitive_loop_contract", "Local-first Cognitive Loop project configuration contract."),
    (".cognitive-loop/permissions.yaml", "cognitive_loop_contract", "Cognitive Loop permission and human approval contract."),
    (".cognitive-loop/evals.yaml", "cognitive_loop_contract", "Cognitive Loop required eval command contract."),
    (".cognitive-loop/risk.yaml", "cognitive_loop_contract", "Cognitive Loop risk and human mastery gate contract."),
    ("fixtures/notebooklm/README.md", "fixture", "NotebookLM fixture notes."),
    ("fixtures/notebooklm/notebooklm-style-context-package.json", "fixture", "NotebookLM-style context package fixture."),
    ("plugins/registry.json", "plugin_registry", "Bundled sample plugin registry with source digests."),
    ("plugins/example-note-importer/plugin.json", "sample_plugin", "Markdown and Obsidian importer manifest."),
    ("plugins/example-note-importer/plugin.py", "sample_plugin", "Markdown and Obsidian importer template source."),
    ("plugins/example-web-importer/plugin.json", "sample_plugin", "Web excerpt importer manifest."),
    ("plugins/example-web-importer/plugin.py", "sample_plugin", "Web excerpt importer template source."),
    ("plugins/example-enrichment-importer/plugin.json", "sample_plugin", "Learning enrichment importer manifest."),
    ("plugins/example-enrichment-importer/plugin.py", "sample_plugin", "Learning enrichment importer template source."),
    ("plugins/example-exporter/plugin.json", "sample_plugin", "Obsidian and second-brain exporter manifest."),
    ("plugins/example-exporter/plugin.py", "sample_plugin", "Obsidian and second-brain exporter template source."),
    ("plugins/example-agent-provider/plugin.json", "sample_plugin", "User-owned Agent provider manifest template."),
    ("plugins/example-agent-provider/plugin.py", "sample_plugin", "User-owned Agent provider template source."),
]

REQUIRED_PLATFORM_TOOLS = [
    "study_anything_deployment_guide",
    "study_anything_commercial_readiness",
    "study_anything_adoption_telemetry",
    "study_anything_pmf_readiness",
    "study_anything_health",
    "study_anything_eval_policy",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_append_context_package",
    "study_anything_plugin_sdk",
    "study_anything_plugin_capabilities",
    "study_anything_validate_plugin_package",
    "study_anything_run_importer",
    "study_anything_add_enrichment",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_retrieval_search",
    "study_anything_retrieval_quality_eval",
    "study_anything_teaching_layers",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_agent_quality_eval",
    "study_anything_agent_eval_report",
    "study_anything_obsidian_export",
    "study_anything_enrichment_artifact_export",
    "study_anything_learning_package_export",
    "study_anything_second_brain_handoff_export",
]


class AdoptionPackError(RuntimeError):
    """Readable adoption-pack generation failure."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdoptionPackError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc


def assert_safe_path(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.exists():
        raise AdoptionPackError(f"Adoption pack file is missing: {relative_path}")
    if path.is_dir():
        raise AdoptionPackError(f"Adoption pack file must not be a directory: {relative_path}")
    if any(part in {".git", ".env", ".venv", "data", "__pycache__"} for part in path.parts):
        raise AdoptionPackError(f"Unsafe adoption pack path: {relative_path}")
    return path


def file_record(relative_path: str, kind: str, purpose: str) -> dict[str, object]:
    path = assert_safe_path(relative_path)
    return {
        "path": relative_path,
        "archive_path": f"{ARCHIVE_ROOT}/{relative_path}",
        "kind": kind,
        "purpose": purpose,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_source_contract() -> None:
    tools = read_json(ROOT / "platform" / "study-anything-platform-tools.json")
    if tools.get("schema_version") != "study-anything-platform-tools-v1":
        raise AdoptionPackError("Platform tool manifest schema drifted.")
    names = {tool.get("name") for tool in tools.get("tools", [])}
    missing = [name for name in REQUIRED_PLATFORM_TOOLS if name not in names]
    if missing:
        raise AdoptionPackError(f"Platform tool manifest is missing adoption tools: {missing}")


def pack_readme() -> str:
    return """# Delivery Clearance Platform Adoption Pack

This archive is the copy-ready integration bundle for Kimi Work, Codex,
WorkBuddy-style HTTP tool workspaces, and other platform Agents. It carries the
historical Study Anything adapter and `cbb.*` compatibility interfaces; it is not
the AI Delivery Clearance Protocol itself.

Delivery Clearance does not prove that AI is always correct. It proves why this
delivery may move forward, to whom, for what purpose, within what limits, and under
whose responsibility. No clearance, no delivery.

Use it when the platform Agent owns browsing, files, video slicing, outside
tools, real model credentials, and conversation. The Study Anything adapter owns
source-bound human-reconstruction and learning state, audit/eval evidence,
retrieval quality, OKF-style Markdown bundles, and Obsidian/NotebookLM handoff.

## Quick Start

1. Start Study Anything locally with Skill Mode or the published Docker image.
2. Import `platform/generated/study-anything-platform-openapi.json` or
   `platform/generated/study-anything-openai-tools.json` into your platform.
3. Follow the operator guide for your platform under `platform/packs/`.
4. Run:

```bash
python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree
```

The verifier emits `adoption-proof-v1` JSON. Treat that JSON as the minimum
acceptance evidence before claiming an external platform integration works.
The generated `adopter-evidence-archive-v1` package is the public maintainer
handoff bundle for release proof, checksums, and local GHCR pull-timeout
fallback evidence.

## Privacy

Do not put real model API keys in the Study Anything adapter. Keep real model credentials
inside the user's own Agent or platform runtime. The adoption evidence is
designed to be redacted and must not include raw source text, long answers,
agent endpoints with secrets, or platform-private browsing/video context.
"""


def manifest_payload() -> dict[str, object]:
    validate_source_contract()
    file_paths = [path for path, _kind, _purpose in PACK_FILES]
    if len(file_paths) != len(set(file_paths)):
        raise AdoptionPackError("Adoption pack file list contains duplicates.")
    return {
        "schema_version": "study-anything-platform-adoption-pack-v1",
        "name": "study-anything-platform-adoption-pack",
        "version": "v0.3.31-alpha",
        "archive_name": ARCHIVE_PATH.name,
        "archive_root": ARCHIVE_ROOT,
        "description": (
            "Copy-ready CBB reference-harness adapter pack for Kimi Work, Codex, "
            "WorkBuddy-style HTTP workspaces, Hermes Agent, NotebookLM/Obsidian "
            "handoff, and external Agent eval proof."
        ),
        "supported_platforms": [
            "kimi-work",
            "codex",
            "workbuddy-style-http",
            "hermes-agent",
            "generic-http-tools",
        ],
        "runtime_modes": ["skill-mode", "published-image"],
        "no_frontend_required": True,
        "real_model_keys_stored_by_study_anything": False,
        "required_tool_names": REQUIRED_PLATFORM_TOOLS,
        "acceptance": {
            "proof_schema": "adoption-proof-v1",
            "command": (
                "python3 scripts/verify_external_adoption.py --pack "
                "platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree"
            ),
            "target_minutes": 15,
            "must_verify": [
                "archive sha256 manifest",
                "OpenAPI/OpenAI tool import assets",
                "Kimi/Codex/WorkBuddy operator packs",
                "study-anything-platform-plugin-pack-v1",
                "Skill Mode or published-image runtime",
                "external platform Agent learning flow",
                "external platform pack consumption drill",
                "retrieval-quality-eval-v1",
                "agent-eval-policy-v1",
                "agent-eval-report-v1",
                "agent-quality-eval-v1",
                "study-anything-agent-eval-regression-report-v1",
                "obsidian-markdown-export-v1",
                "learning-package-v1",
                "second-brain-handoff-v1",
                "plugin-sdk-v1",
                "plugin-capability-index-v1",
                "plugin-package-validation-v1",
                "plugin-quarantine-verification-v1",
                "deployment-guide-v1",
                "commercial-readiness-v1",
                "adoption-telemetry-v1",
                "pmf-readiness-v1",
                "adoption-telemetry-verification-v1",
                "agent-gateway-hardening-verification-v1",
                "notebooklm-obsidian-bridge-hardening-v1",
                "learning-enrichment-bridge-verification-v1",
                "cognitive-black-box-okf-alignment-verification-v1",
                "cognitive-black-box-okf-bundle-v1",
                "security-recovery-hardening-verification-v1",
                "platform-submission-dry-run-v1",
                "platform-manual-submission-rehearsal-v1",
                "first-run-lesson-authoring-kit-v1",
                "external-eval-marketplace-harness-v1",
                "agent-eval-marketplace-enforcement-v1",
                "delivery-trust-receipt-v1",
                "delivery-trust-receipt-verification-v1",
                "customer-handoff-package-v1",
                "customer-handoff-package-verification-v1",
                "claim-boundary-v1",
                "trust-root-v1",
                "reviewer-reconstruction-receipt-v1",
                "risk-owner-scope-v1",
                "delivery-decision-receipt-v1",
                "cbb-protocol-contracts-verification-v1",
                "cbb-gate-verification-v1",
                "cbb-receipt-chain-v1",
                "cbb-self-intake-receipt-v1",
                "cbb-delivery-evidence-pack-v1",
                "cbb-receipt-chain-verification-v1",
                "cbb-self-intake-verification-v1",
                "cbb-delivery-scenario-v1",
                "cbb-external-feedback-intake-v1",
                "cbb-tri-loop-run-v1",
                "cbb-delivery-scenario-harness-verification-v1",
                "cognitive-loop-review-agent-eval-harness-v1",
                "cognitive-loop-review-agent-ci-receipt-v1",
                "cognitive-loop-review-agent-pr-comment-pack-v1",
                "cognitive-loop-review-agent-acceptance-bundle-v1",
                "platform-adoption-feedback-diagnostics-v1",
                "platform-feedback-package-v1",
                "platform-field-adoption-rehearsal-v1",
                "platform-import-failure-fixture-v1",
                "platform-support-triage-v1",
                "platform-support-ticket-fixture-v1",
                "platform-support-issue-template-v1",
                "platform-onboarding-readiness-v1",
                "first-external-adopter-walkthrough-v1",
                "maintainer-sla-labels-v1",
                "maintainer-rotation-checklist-v1",
                "platform-triage-dashboard-v1",
                "platform-release-blocker-fixture-v1",
                "public-support-status-v1",
                "public-maintainer-dashboard-v1",
                "public-status-linkage-fixture-v1",
                "published-image-evidence-v1",
                "published-image-evidence-fixture-v1",
                "release-asset-adoption-v1",
                "release-asset-adoption-fixture-v1",
                "release-asset-adoption-proof-v1",
                "release-asset-bootstrap-v1",
                "release-asset-bootstrap-transcript-v1",
                "platform-agent-release-replay-v1",
                "adopter-evidence-archive-v1",
                "adopter-evidence-fixture-v1",
                "plugin-ecosystem-adoption-kit-v1",
                "deployment-hardening-verification-v1",
                "ecosystem-submission-v1",
                "ecosystem-submission-verification-v1",
                "cognitive-loop-pr-ci-receipt-v1",
                "cognitive-loop-maintainer-acceptance-ledger-v1",
            ],
        },
        "privacy_contract": {
            "must_not_store": [
                "real model API keys",
                "platform private browser traces",
                "raw long source text in eval evidence",
                "raw answer text in eval evidence",
                "agent endpoint secrets",
            ],
            "user_owned_exports_may_include": [
                "learner answers",
                "review history",
                "Obsidian markdown selected by the learner",
            ],
        },
        "files": [file_record(*item) for item in PACK_FILES],
    }


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def archive_bytes(manifest: dict[str, object]) -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in [
            (f"{ARCHIVE_ROOT}/ADOPTION_PACK_README.md", pack_readme().encode("utf-8")),
            (f"{ARCHIVE_ROOT}/manifest.json", dump_json(manifest).encode("utf-8")),
        ]:
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
        for record in sorted(manifest["files"], key=lambda item: str(item["path"])):  # type: ignore[index]
            relative_path = str(record["path"])
            source = ROOT / relative_path
            info = zipfile.ZipInfo(str(record["archive_path"]))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    return buffer.getvalue()


def build_outputs() -> tuple[str, bytes]:
    archive_manifest = manifest_payload()
    archive = archive_bytes(archive_manifest)
    enriched = dict(archive_manifest)
    enriched["archive_sha256"] = sha256_bytes(archive)
    enriched["archive_bytes"] = len(archive)
    return dump_json(enriched), archive


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_text, archive = build_outputs()
    MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    print(f"wrote {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")


def check_outputs() -> None:
    expected_manifest, expected_archive = build_outputs()
    missing = [
        str(path.relative_to(ROOT))
        for path in [MANIFEST_PATH, ARCHIVE_PATH]
        if not path.exists()
    ]
    stale = []
    if MANIFEST_PATH.exists() and MANIFEST_PATH.read_text(encoding="utf-8") != expected_manifest:
        stale.append(str(MANIFEST_PATH.relative_to(ROOT)))
    if ARCHIVE_PATH.exists() and ARCHIVE_PATH.read_bytes() != expected_archive:
        stale.append(str(ARCHIVE_PATH.relative_to(ROOT)))
    if missing or stale:
        raise AdoptionPackError(
            "Platform adoption pack is stale. Run "
            "`python3 scripts/generate_platform_adoption_pack.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated platform adoption pack is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_platform_adoption_pack failed: {exc}", file=sys.stderr)
        sys.exit(1)
