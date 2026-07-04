# Operator Handoff Rehearsal Contract

- Schema: `operator-handoff-rehearsal-contract-v1`
- Status: `pass`
- Mode: `operator_handoff_decision_only`
- Delivery classes: `2`

## Delivery Classes

- `code_review_handoff`: ready `1`, blocked `6`
- `client_report_handoff`: ready `1`, blocked `7`

## Shared Boundary

Code Review and Client Report delivery classes share a metadata-only operator handoff contract: a platform Agent can prepare a bounded ready/block decision, but cannot send, publish, comment, merge, mutate production, certify truth, or replace customer-specific review.

This contract does not approve customer sending, post PR comments, publish
externally, mutate production, certify truth, certify security/legal/financial
claims, guarantee outcomes, or replace customer-specific review.
