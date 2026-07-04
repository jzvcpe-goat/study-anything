# Patch Proposal Customer Feedback Product Owner Gate

This gate is a metadata-only Product Loop boundary for the Patch Proposal
customer-feedback chain.

It consumes a `product-loop-backlog-signal-v1` artifact from the Patch Proposal
Customer Feedback Backlog Bridge and can emit only a
`patch-proposal-product-spec-eval-candidate-v1` artifact. The transition is
allowed only after active Product Owner boundary reconstruction.

## Claim Boundary

The gate claims that a bounded customer/operator/platform feedback signal can
enter the spec/eval candidate queue after a Product Owner reconstructs the
boundary:

- feedback remains hash/reference only;
- the candidate remains metadata-only;
- priority remains unassigned;
- execution remains blocked;
- customer-visible follow-up remains blocked;
- source and production mutation remain blocked.

The gate does not claim:

- automatic priority assignment;
- automatic execution;
- customer-visible follow-up;
- source mutation;
- external publication;
- production mutation;
- model-call evaluation;
- customer satisfaction certification.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-product-owner-gate/
```

Passing cases include:

- `pass-customer-signal`
- `pass-operator-signal`
- `pass-host-platform-agent-signal`

Blocked cases prove the boundary rejects:

- missing Product Owner reconstruction;
- automatic priority assignment;
- skip to delivery trust;
- automatic execution;
- customer-visible follow-up;
- source mutation;
- production mutation;
- blocked backlog source;
- secrets;
- model credentials.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_product_owner_gate.py --check
```

The verifier checks deterministic fixtures, schema identity, CLI roundtrip, and
negative injections for raw specs, raw eval bodies, priority scores, customer
follow-up effects, source mutation, production mutation, and unsafe blocked
receipts with candidates.

## Runtime Boundary

This gate does not start a daemon, call a model, mutate a repository, send a
customer message, write to production, or store raw customer material. It is a
structured artifact bridge only.
