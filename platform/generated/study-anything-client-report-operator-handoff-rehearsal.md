# Client Report Operator Handoff Rehearsal

- Schema: `client-report-operator-handoff-rehearsal-v1`
- Status: `pass`
- Mode: `operator_handoff_decision_only`
- Delivery class: `client_report_handoff`
- Ready cases: `1`
- Blocked cases: `7`

## Rehearsal Matrix

- `ready-client-report-operator-decision`: `ready_for_operator_handoff_decision` (ready)
- `block-client-report-class-blocked`: `block_operator_handoff` (blocked)
- `block-customer-rehearsal-blocked`: `block_operator_handoff` (blocked)
- `block-missing-recipient-scope-confirmation`: `block_operator_handoff` (blocked)
- `block-missing-not-send-approval-understanding`: `block_operator_handoff` (blocked)
- `block-automatic-customer-send`: `block_operator_handoff` (blocked)
- `block-external-publication`: `block_operator_handoff` (blocked)
- `block-raw-report-requested`: `block_operator_handoff` (blocked)

## Claim Boundary

A platform Agent or external operator can prepare a Client Report handoff decision from metadata-only evidence when both the delivery class and customer-delivery rehearsal pass.

This rehearsal does not approve customer sending, publish externally, mutate
production, certify legal or financial advice, certify complete factual
correctness, guarantee outcomes, or replace customer-specific legal/compliance
review.
