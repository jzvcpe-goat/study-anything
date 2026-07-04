# Customer Delivery Rehearsal

- Schema: `customer-delivery-rehearsal-v1`
- Status: `pass`
- Mode: `operator_pre_send_rehearsal_only`
- Ready cases: `1`
- Blocked cases: `5`

## Rehearsal Matrix

- `ready-manual-scope-confirmed`: `ready_for_manual_send_review` (ready)
- `block-missing-human-scope`: `block_customer_delivery` (blocked)
- `block-hidden-claim-boundary`: `block_customer_delivery` (blocked)
- `block-raw-payload-attached`: `block_customer_delivery` (blocked)
- `block-automatic-customer-send`: `block_customer_delivery` (blocked)
- `block-source-blocked-item`: `block_customer_delivery` (blocked)

## Claim Boundary

An external operator or platform Agent can rehearse ready/block decisions from a metadata-only customer-delivery envelope before any customer-visible action.

This rehearsal does not approve customer sending, complete a customer send,
mutate production, certify truth, guarantee outcomes, or replace
customer-specific legal/compliance review.
