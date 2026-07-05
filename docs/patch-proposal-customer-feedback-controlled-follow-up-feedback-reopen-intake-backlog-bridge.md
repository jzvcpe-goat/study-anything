# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Backlog Bridge

This layer turns allowed Patch Proposal Customer Feedback Controlled Follow-up
Feedback Reopen Intake Gate receipts into metadata-only Product Loop backlog
signal refs.

It exists to close the controlled follow-up loop back into product development
without turning Study Anything into a customer inbox, priority engine, Product
Loop backlog writer, source mutator, production operator, PR commenter, or model
caller.

## What It Emits

- `patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-backlog-bridge-v1`
- `product-loop-backlog-signal-v1`

The backlog signal contains only metadata refs and hashes:

- source reopen-intake gate id/ref/hash;
- source reopen-intake bridge ref/hash;
- closure, outcome, action, external actor, intake-candidate, and Product Loop
  intake-item ref hashes;
- bounded reopen-intake signal type;
- destination `product_loop_backlog`;
- next boundary `product_owner_prioritization`;
- explicit blocked destinations and provenance chain refs.

## What It Blocks

- raw follow-up data or raw customer data;
- customer identity;
- automatic customer contact;
- automatic backlog item creation;
- automatic priority assignment;
- automatic execution;
- Product Loop backlog mutation;
- automatic follow-up sending;
- source mutation;
- production mutation;
- external publication;
- secrets and user-owned model credentials;
- model calls in this layer.

## Required Local Gate

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py --check
```

Use `--write` only when intentionally refreshing deterministic fixtures and
generated reports:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_backlog_bridge.py --write
```

## Claim Boundary

This layer proves only that allowed controlled follow-up feedback reopen-intake
gates can become Product Loop backlog metadata refs. It does not prove customer
satisfaction, create a live backlog item, prioritize work, assign an owner,
create a spec/eval, mutate a live backlog, or authorize execution.

The next boundary is Product Owner Prioritization.
