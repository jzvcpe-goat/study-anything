# Controlled Handoff Runbook

- Schema: `controlled-handoff-runbook-v1`
- Status: `pass`
- Mode: `controlled_handoff_preparation_only`
- Source ZIP SHA-256: `d6f7fedd4f8e0147dcdbf70160227ad9deb54011e6aab1e96e0ba6e77162caf2`

## Allowed Preparation Steps

- `code_review_handoff`: `prepare_controlled_handoff_packet` -> `draft_handoff_only`
- `client_report_handoff`: `prepare_controlled_handoff_packet` -> `draft_handoff_only`
- `support_response_handoff`: `prepare_controlled_handoff_packet` -> `draft_handoff_only`

## Blocked Paths

- `code_review_handoff` / `blocked-missing-reconstruction`: `keep_handoff_blocked` because `human_reconstruction_missing`
- `code_review_handoff` / `blocked-unsafe-diff-scope`: `keep_handoff_blocked` because `diff_scope_expansion, sandbox_risk_outside_budget`
- `code_review_handoff` / `blocked-ai-review-only`: `keep_handoff_blocked` because `ai_review_only_evidence_rejected, product_loop_not_passed`
- `client_report_handoff` / `blocked-missing-reconstruction`: `keep_handoff_blocked` because `human_reconstruction_missing`
- `client_report_handoff` / `blocked-risk-over-budget`: `keep_handoff_blocked` because `sandbox_risk_outside_budget`
- `client_report_handoff` / `blocked-unbounded-recipient`: `keep_handoff_blocked` because `recipient_scope_unbounded`
- `client_report_handoff` / `blocked-ai-summary-only`: `keep_handoff_blocked` because `ai_summary_only_evidence_rejected, product_loop_not_passed`
- `support_response_handoff` / `blocked-missing-reconstruction`: `keep_handoff_blocked` because `human_reconstruction_missing`
- `support_response_handoff` / `blocked-risk-over-budget`: `keep_handoff_blocked` because `sandbox_risk_outside_budget`
- `support_response_handoff` / `blocked-unbounded-recipient`: `keep_handoff_blocked` because `recipient_scope_unbounded`
- `support_response_handoff` / `blocked-policy-gap`: `keep_handoff_blocked` because `support_policy_scope_missing`
- `support_response_handoff` / `blocked-ai-summary-only`: `keep_handoff_blocked` because `ai_summary_only_evidence_rejected, product_loop_not_passed`

## Claim Boundary

A platform Agent or external operator can prepare a controlled handoff packet from accepted metadata evidence while preserving all blocked paths and claim limits.

This runbook does not approve production, send customer messages, certify truth,
guarantee customer outcomes, or replace customer-specific legal/compliance review.
