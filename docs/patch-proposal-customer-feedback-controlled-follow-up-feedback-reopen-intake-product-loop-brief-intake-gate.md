# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Product Loop Brief Intake Gate

This gate consumes metadata-only `patch-proposal-product-loop-brief-candidate-v1`
artifacts from the reopen-intake Spec/Eval Authoring Gate and turns them into
Product Loop scenario/run candidates only after active developer/product-loop
boundary reconstruction.

It emits:

- `patch-proposal-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-receipt-v1`
- `product-loop-scenario-v1`
- `product-loop-run-v1`

The scenario and run use the generic Product Loop Harness contracts. This keeps
the reopen-intake customer-feedback chain compatible with the same three-loop
product-development gate as other delivery classes.

## Claim Boundary

The gate claims that a Patch Proposal controlled follow-up feedback reopen-intake
brief candidate may become a Product Loop scenario/run candidate only after the
source Spec/Eval Authoring receipt is already queued and the developer has
actively reconstructed the Product Loop boundary.

It does not claim:

- Delivery Trust Harness completion;
- customer-visible follow-up or customer contact;
- Product Loop backlog mutation;
- source mutation;
- production mutation;
- external publication;
- automatic execution;
- automatic backlog creation or priority assignment;
- finished customer deliverable quality;
- model-call evaluation.

## Blocked Paths

The gate blocks:

- missing or blocked source Spec/Eval Authoring receipts;
- missing brief-candidate references;
- missing reopen-intake gate, bridge, closure, outcome, action, actor, intake,
  backlog, or Product Owner references;
- missing product-loop reconstruction;
- missing claim or privacy boundaries;
- raw brief, spec, eval, follow-up, customer, or backlog material;
- customer identity;
- automatic backlog creation or priority assignment;
- AI-review-only evidence;
- direct Delivery Trust Harness skips or invocation;
- automatic execution;
- customer contact;
- Product Loop backlog mutation;
- external publication payloads;
- source mutation;
- production mutation;
- model calls;
- secrets;
- model credentials.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-product-loop-brief-intake-gate/
```

The passing case is:

- `pass`

Blocked cases intentionally do not include `product-loop-scenario.json` or
`product-loop-run.json`.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_product_loop_brief_intake_gate.py --check
```

The verifier checks deterministic fixtures, schema identity, CLI roundtrip,
custom brief-candidate input, metadata-only privacy boundaries, Product Loop
scenario/run validation, source-chain references, and negative injections for
raw brief body, unsafe policy changes, Delivery Trust invocation, automatic
execution, customer contact, external publication, source mutation, production
mutation, model calls, and unsafe blocked receipts with run artifacts.

## Runtime Boundary

This gate is local-first and metadata-only. It does not start a daemon, call a
model, invoke the Delivery Trust Harness, contact customers, mutate source,
mutate production, mutate the Product Loop backlog, or store raw
customer/spec/eval/brief material.
