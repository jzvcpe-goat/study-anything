# Product Owner Prioritization Gate

Metadata-only verification that Product Loop backlog items stop at Product Owner reconstruction before entering the spec/eval candidate queue.

- status: `pass`
- queued cases: `1`
- blocked cases: `7`
- candidates: `1`
- allowed next boundary: `product_spec_eval_candidate_queue`
- automatic priority assignment: `blocked`
- automatic execution: `blocked`

## Cases

- `pass`: `queued_for_spec_eval_candidate` / `create_product_spec_eval_candidate` / candidate: `True` / reasons: `none`
- `blocked-missing-owner-reconstruction`: `blocked` / `block_product_owner_prioritization` / candidate: `False` / reasons: `product_owner_reconstruction_missing`
- `blocked-automatic-priority`: `blocked` / `block_product_owner_prioritization` / candidate: `False` / reasons: `automatic_priority_assignment_rejected`
- `blocked-skip-to-delivery-harness`: `blocked` / `block_product_owner_prioritization` / candidate: `False` / reasons: `requested_next_boundary_not_spec_eval_candidate_queue`
- `blocked-automatic-execution`: `blocked` / `block_product_owner_prioritization` / candidate: `False` / reasons: `automatic_execution_rejected`
- `blocked-production-mutation`: `blocked` / `block_product_owner_prioritization` / candidate: `False` / reasons: `production_mutation_rejected`
- `blocked-customer-visible-action`: `blocked` / `block_product_owner_prioritization` / candidate: `False` / reasons: `customer_visible_action_rejected`
- `blocked-blocked-backlog-source`: `blocked` / `block_product_owner_prioritization` / candidate: `False` / reasons: `source_backlog_item_missing`

## Boundary

The gate creates only metadata-only spec/eval candidates. It does not assign priority, execute work, send customer-visible messages, publish externally, mutate production, or skip to the Delivery Trust Harness.
