# Patch Proposal Customer Feedback Backlog Bridge

This layer turns accepted Patch Proposal Customer Feedback Intake receipts into
metadata-only Product Loop backlog signals.

It exists to close the loop from external/customer feedback back into product
development without turning Study Anything into a customer messaging system, a
priority engine, a source mutator, or a production operator.

## What It Emits

- `patch-proposal-customer-feedback-backlog-bridge-v1`
- `product-loop-backlog-signal-v1`

The backlog signal contains only metadata refs and hashes:

- source feedback-intake receipt id/ref/hash;
- source customer-delivery outcome ref/hash;
- bounded feedback signal type;
- destination `product_loop_backlog`;
- next boundary `product_owner_prioritization`;
- explicit blocked destinations.

## What It Blocks

- raw customer replies;
- private customer data;
- PR comment bodies;
- automatic priority assignment;
- automatic follow-up sending;
- source mutation;
- production mutation;
- external publication;
- secrets and user-owned model credentials;
- model calls in this layer.

## Required Local Gate

```bash
python3 scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py --check
```

Use `--write` only when intentionally refreshing deterministic fixtures and
generated reports:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_backlog_bridge.py --write
```

## Claim Boundary

This layer proves only that accepted customer/operator/host-platform feedback
signals can become backlog metadata. It does not prove customer satisfaction,
does not prioritize work, does not assign an owner, does not create a spec/eval,
and does not authorize execution.

The next boundary is Product Owner Prioritization.
