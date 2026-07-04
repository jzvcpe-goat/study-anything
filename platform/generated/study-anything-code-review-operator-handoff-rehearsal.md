# Code Review Operator Handoff Rehearsal

- Schema: `code-review-operator-handoff-rehearsal-v1`
- Status: `pass`
- Mode: `operator_handoff_decision_only`
- Delivery class: `code_review_handoff`
- Ready cases: `1`
- Blocked cases: `6`

## Rehearsal Matrix

- `ready-code-review-operator-decision`: `ready_for_operator_handoff_decision` (ready)
- `block-code-review-class-blocked`: `block_operator_handoff` (blocked)
- `block-customer-rehearsal-blocked`: `block_operator_handoff` (blocked)
- `block-missing-not-send-approval-understanding`: `block_operator_handoff` (blocked)
- `block-automatic-pr-comment`: `block_operator_handoff` (blocked)
- `block-automatic-customer-send`: `block_operator_handoff` (blocked)
- `block-raw-diff-requested`: `block_operator_handoff` (blocked)

## Claim Boundary

A platform Agent or external operator can prepare a Code Review handoff decision from metadata-only evidence when both the delivery class and customer-delivery rehearsal pass.

This rehearsal does not approve customer sending, post PR comments, merge or
deploy code, certify security, discover all vulnerabilities, certify truth,
guarantee outcomes, or replace customer-specific legal/compliance review.
