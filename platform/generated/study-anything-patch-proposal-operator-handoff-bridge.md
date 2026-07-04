# Patch Proposal Operator Handoff Bridge

Metadata-only proof that a sandbox-local patch proposal envelope can become only an operator handoff bridge, not a repository mutation or customer-visible action.

- status: `pass`
- schema: `patch-proposal-operator-handoff-bridge-v1`
- cases: `8`

## Claim Boundary

A ready bridge only packages metadata refs so a host platform operator can decide whether to continue; it does not execute, apply, publish, or send anything.

Not claimed:
- patch content generated
- repository changed
- PR opened or commented
- customer handoff approved
- external publication approved
- production change approved
- truth or security certified

## Cases

- `pass`: `ready` / `prepare_operator_handoff_bridge` / reasons: none
- `blocked-sandboxed-proposal-blocked`: `blocked` / `block_operator_handoff_bridge` / reasons: sandboxed_patch_proposal_not_allowed, sandbox_local_scope_missing, test_plan_ref_missing
- `blocked-missing-operator-confirmation`: `blocked` / `block_operator_handoff_bridge` / reasons: operator_active_reconstruction_missing
- `blocked-raw-patch-request`: `blocked` / `block_operator_handoff_bridge` / reasons: raw_patch_or_diff_request_rejected
- `blocked-repository-mutation`: `blocked` / `block_operator_handoff_bridge` / reasons: repository_mutation_rejected
- `blocked-customer-visible-action`: `blocked` / `block_operator_handoff_bridge` / reasons: customer_visible_action_rejected
- `blocked-external-publication`: `blocked` / `block_operator_handoff_bridge` / reasons: external_publication_rejected
- `blocked-production-mutation`: `blocked` / `block_operator_handoff_bridge` / reasons: production_mutation_rejected
