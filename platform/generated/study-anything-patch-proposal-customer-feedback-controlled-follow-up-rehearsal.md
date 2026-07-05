# Patch Proposal Customer Feedback Controlled Follow-up Rehearsal

Metadata-only proof that controlled follow-up envelope refs can be rehearsed locally before any customer-visible action.

- status: `pass`
- schema: `patch-proposal-customer-feedback-controlled-follow-up-rehearsal-v1`
- cases: `20`

## Claim Boundary

Controlled follow-up envelope refs may be rehearsed locally by an operator or host-platform Agent as metadata-only review evidence. The rehearsal does not generate customer-visible text, send messages, mutate source or production, publish externally, call models, or replace human accountability.

Not claimed:
- raw follow-up body generated
- customer-visible draft prepared
- customer-visible send performed
- source mutation allowed
- production mutation allowed
- external publication performed
- model call performed
- customer outcome accepted
- truth or security certified

## Cases

- `pass-customer-signal`: `ready` / `ready_for_local_follow_up_rehearsal_review` / source: `operator` / reasons: none
- `pass-operator-signal`: `ready` / `ready_for_local_follow_up_rehearsal_review` / source: `operator` / reasons: none
- `pass-host-platform-agent-signal`: `ready` / `ready_for_local_follow_up_rehearsal_review` / source: `host_platform_agent` / reasons: none
- `blocked-missing-envelope-refs`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: source_envelope_refs_not_ready, active_reconstruction_ref_missing, product_loop_ref_missing, dual_loop_ref_missing, delivery_trust_ref_missing
- `blocked-invalid-envelope-refs`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: source_envelope_refs_not_ready
- `blocked-passive-rehearsal`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: active_rehearsal_missing, passive_rehearsal_rejected
- `blocked-unsupported-rehearsal-source`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `customer` / reasons: unsupported_rehearsal_source
- `blocked-missing-active-reconstruction-ref`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: source_envelope_refs_not_ready, active_reconstruction_ref_missing
- `blocked-missing-product-loop-ref`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: product_loop_ref_missing
- `blocked-missing-dual-loop-ref`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: dual_loop_ref_missing
- `blocked-missing-delivery-trust-ref`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: delivery_trust_ref_missing
- `blocked-raw-follow-up-preview`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: raw_follow_up_preview_rejected
- `blocked-customer-visible-draft`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: customer_visible_draft_rejected
- `blocked-automatic-customer-send`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: automatic_customer_send_rejected
- `blocked-source-mutation`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: source_mutation_rejected
- `blocked-production-mutation`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: production_mutation_rejected
- `blocked-external-publication`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: external_publication_rejected
- `blocked-model-call`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: model_call_rejected
- `blocked-secret`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: secret_rejected
- `blocked-model-credential`: `blocked` / `block_controlled_follow_up_rehearsal` / source: `operator` / reasons: model_credential_rejected
