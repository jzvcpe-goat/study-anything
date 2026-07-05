# Patch Proposal Customer Feedback Delivery Trust Case Bridge

Metadata-only proof that Patch Proposal Delivery Trust case candidates can run the local deterministic Delivery Trust Case Harness and emit only handoff refs.

- status: `pass`
- ready ref sets: `3`
- blocked transitions: `13`
- raw customer payloads: `blocked`
- customer-visible sends: `blocked`
- source and production mutation: `blocked`

## Claim Boundary

A Patch Proposal Delivery Trust case candidate can be assembled into metadata-only Delivery Trust case and handoff refs only when the candidate, Product Loop run, controlled-failure evidence, attention reconstruction, and Dual Loop gate all match.

Not claimed:
- raw customer payload included
- customer-visible send performed
- source mutation allowed
- production mutation allowed
- external publication performed
- model call performed
- real customer delivery
- production deployment approval

## Cases

- `pass-customer-signal`: `delivery_trust_case_refs_ready` / `emit_delivery_trust_case_handoff_refs` / refs: `True` / reasons: none
- `pass-operator-signal`: `delivery_trust_case_refs_ready` / `emit_delivery_trust_case_handoff_refs` / refs: `True` / reasons: none
- `pass-host-platform-agent-signal`: `delivery_trust_case_refs_ready` / `emit_delivery_trust_case_handoff_refs` / refs: `True` / reasons: none
- `blocked-missing-candidate`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: candidate_missing
- `blocked-invalid-candidate`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: candidate_invalid
- `blocked-missing-product-loop-run`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: product_loop_run_missing
- `blocked-product-loop-hash-mismatch`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: product_loop_run_hash_mismatch, product_loop_run_id_mismatch
- `blocked-missing-dual-loop-evidence`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: sandbox_receipt_missing
- `blocked-dual-loop-evidence-mismatch`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: dual_loop_evidence_ref_mismatch
- `blocked-dual-loop-gate-blocked`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: dual_loop_evidence_ref_mismatch, dual_loop_gate_blocked, sandbox_risk_outside_budget
- `blocked-ai-review-only`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: product_loop_run_invalid
- `blocked-customer-visible-send`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: customer_visible_send_rejected
- `blocked-source-mutation`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: source_mutation_rejected
- `blocked-production-mutation`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: production_mutation_rejected
- `blocked-secret`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: secret_rejected
- `blocked-model-credential`: `blocked` / `block_patch_proposal_delivery_trust_case_bridge` / refs: `False` / reasons: model_credential_rejected
