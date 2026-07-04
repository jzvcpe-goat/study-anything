# Patch Proposal Customer Feedback Product Loop Brief Intake Gate

This gate is the Patch Proposal-specific entry into the existing Product Loop
Harness.

It consumes a `patch-proposal-product-loop-brief-candidate-v1` artifact from
the Patch Proposal Customer Feedback Spec/Eval Authoring Gate. If the boundary
checks pass, it emits:

- `patch-proposal-customer-feedback-product-loop-brief-intake-receipt-v1`
- `product-loop-scenario-v1`
- `product-loop-run-v1`

The scenario and run use the generic Product Loop contracts so Patch Proposal
evidence can join the same downstream harness as other delivery classes.

## Claim Boundary

The gate claims that a Patch Proposal brief candidate may become a Product Loop
scenario/run candidate only after active developer/product-loop reconstruction.

It does not claim:

- Delivery Trust Harness completion;
- customer-visible follow-up;
- source mutation;
- production mutation;
- automatic execution;
- finished customer deliverable quality;
- model-call evaluation.

## Blocked Paths

The gate blocks:

- missing or invalid Patch Proposal brief candidates;
- missing product-loop reconstruction;
- AI-review-only evidence;
- direct Delivery Trust Harness skips or invocation;
- customer-visible follow-up;
- source mutation;
- production mutation;
- secrets;
- model credentials.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-product-loop-brief-intake-gate/
```

Passing cases include:

- `pass-customer-signal`
- `pass-operator-signal`
- `pass-host-platform-agent-signal`

Blocked cases intentionally do not include `product-loop-scenario.json` or
`product-loop-run.json`.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_product_loop_brief_intake_gate.py --check
```

The verifier checks deterministic fixtures, schema identity, CLI roundtrip,
custom brief-candidate input, metadata-only privacy boundaries, Product Loop
scenario/run validation, and negative injections for raw brief body,
AI-review-only policy, Delivery Trust invocation, customer follow-up, source
mutation, production mutation, and unsafe blocked receipts with run artifacts.

## Runtime Boundary

This gate is local-first and metadata-only. It does not start a daemon, call a
model, invoke the Delivery Trust Harness, send a customer message, mutate
source, mutate production, or store raw customer/spec/eval material.
