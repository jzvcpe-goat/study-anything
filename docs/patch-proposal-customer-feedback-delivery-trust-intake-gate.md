# Patch Proposal Customer Feedback Delivery Trust Intake Gate

This gate is the Patch Proposal-specific bridge from Product Loop evidence into
the Delivery Trust Case Harness queue.

It consumes a Patch Proposal `product-loop-run-v1` artifact and requires
controlled-failure, attention-reconstruction, and Dual Loop gate evidence before
emitting a metadata-only `patch-proposal-delivery-trust-case-candidate-v1`.

## Claim Boundary

The gate claims that the candidate is ready to be handed to the Delivery Trust
Case Harness. It does not claim that the Delivery Trust Case Harness has run.

It does not claim:

- customer handoff package creation;
- customer-visible follow-up;
- source mutation;
- production mutation;
- automatic execution;
- model-call evaluation;
- real customer delivery.

## Blocked Paths

The gate blocks:

- missing or invalid Product Loop runs;
- missing sandbox receipts;
- missing attention reconstruction;
- blocked Dual Loop gates;
- AI-review-only Product Loop evidence;
- customer-visible follow-up;
- source mutation;
- production mutation;
- secrets;
- model credentials.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-delivery-trust-intake-gate/
```

Passing cases emit both:

- `patch-proposal-delivery-trust-intake-receipt.json`
- `patch-proposal-delivery-trust-case-candidate.json`

Blocked cases emit only the receipt.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_delivery_trust_intake_gate.py --check
```

The verifier checks deterministic fixtures, schema identity, CLI roundtrip,
custom Product Loop run input, metadata-only privacy boundaries, Dual Loop
evidence requirements, and negative injections for raw delivery case bodies,
customer handoff package creation, Delivery Trust harness invocation, customer
follow-up, production mutation, and unsafe blocked receipts with candidates.

## Runtime Boundary

This gate does not start a daemon, call a model, invoke the Delivery Trust Case
Harness, create a customer handoff package, send a customer message, mutate
source, mutate production, or store raw customer/spec/eval/sandbox/attention
material.
