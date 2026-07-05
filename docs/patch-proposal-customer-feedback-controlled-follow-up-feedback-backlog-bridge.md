# Patch Proposal Customer Feedback Controlled Follow-up Feedback Backlog Bridge

This layer turns accepted Patch Proposal Customer Feedback Controlled Follow-up
Feedback Intake receipts into metadata-only Product Loop backlog signal refs.

It exists to close the controlled follow-up loop back into product development
without turning Study Anything into a customer inbox, priority engine, Product
Loop backlog writer, source mutator, production operator, PR commenter, or model
caller.

## What It Emits

- `patch-proposal-customer-feedback-controlled-follow-up-feedback-backlog-bridge-v1`
- `product-loop-backlog-signal-v1`

The backlog signal contains only metadata refs and hashes:

- source controlled follow-up feedback-intake receipt id/ref/hash;
- source controlled follow-up outcome ref/hash;
- bounded feedback signal type;
- destination `product_loop_backlog`;
- next boundary `product_owner_prioritization`;
- explicit blocked destinations and provenance chain refs.

## What It Blocks

- raw customer replies;
- customer identity or private customer data;
- PR comment bodies;
- automatic priority assignment;
- Product Loop backlog mutation;
- automatic follow-up sending;
- source mutation;
- production mutation;
- external publication;
- secrets and user-owned model credentials;
- model calls in this layer.

## Required Local Gate

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_backlog_bridge.py --check
```

Use `--write` only when intentionally refreshing deterministic fixtures and
generated reports:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_backlog_bridge.py --write
```

## Claim Boundary

This layer proves only that accepted controlled follow-up feedback signals can
become Product Loop backlog metadata refs. It does not prove customer
satisfaction, prioritize work, assign an owner, create a spec/eval, mutate a
live backlog, or authorize execution.

The next boundary is Product Owner Prioritization.
