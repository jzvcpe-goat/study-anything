# Sandboxed Patch Proposal Rehearsal

Metadata-only proof that an allowed Spec/Eval execution rehearsal can create only a sandbox-local patch proposal envelope before any repository mutation.

- status: `pass`
- schema: `sandboxed-patch-proposal-rehearsal-v1`
- cases: `8`

## Claim Boundary

A patch proposal can be prepared as sandbox-local metadata refs only when Spec/Eval, Controlled Failure, and Human Reconstruction gates pass.

Not claimed:
- patch content generated
- repository changed
- customer handoff approved
- external publication approved
- production change approved

## Cases

- `pass`: `allowed` / `prepare_sandbox_local_patch_proposal` / reasons: none
- `blocked-missing-spec-eval-allowance`: `blocked` / `block_patch_proposal` / reasons: spec_eval_execution_not_allowed, sandbox_start_not_authorized, human_reconstruction_missing, dual_loop_gate_not_allowed
- `blocked-missing-rollback-plan`: `blocked` / `block_patch_proposal` / reasons: rollback_plan_missing
- `blocked-missing-test-plan`: `blocked` / `block_patch_proposal` / reasons: test_plan_missing
- `blocked-repository-mutation`: `blocked` / `block_patch_proposal` / reasons: repository_mutation_rejected
- `blocked-customer-visible-action`: `blocked` / `block_patch_proposal` / reasons: customer_visible_action_rejected
- `blocked-external-publication`: `blocked` / `block_patch_proposal` / reasons: external_publication_rejected
- `blocked-production-mutation`: `blocked` / `block_patch_proposal` / reasons: production_mutation_rejected
