# Patch Proposal Customer Feedback Controlled Follow-up Feedback Spec/Eval Authoring Gate

This gate is a metadata-only Product Loop boundary for the Patch Proposal
controlled follow-up feedback chain.

It consumes a `patch-proposal-product-spec-eval-candidate-v1` artifact from the
Patch Proposal Customer Feedback Controlled Follow-up Feedback Product Owner
Gate and can emit only a `patch-proposal-product-loop-brief-candidate-v1`
artifact. The transition is allowed only after active authoring-boundary
reconstruction.

## Claim Boundary

The gate claims that a bounded Patch Proposal controlled follow-up feedback
spec/eval candidate can become a Product Loop brief candidate after the author
reconstructs the boundary:

- spec and eval material remains hash/reference only;
- the brief candidate remains metadata-only;
- execution remains blocked;
- Delivery Trust Harness skips remain blocked;
- customer-visible follow-up remains blocked;
- source and production mutation remain blocked.

The gate does not claim:

- finished product spec quality;
- finished eval coverage;
- automatic execution;
- customer-visible follow-up;
- source mutation;
- external publication;
- production mutation;
- Delivery Trust Harness readiness;
- model-call evaluation.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-spec-eval-authoring-gate/
```

Passing cases include:

- `pass-customer-signal`
- `pass-operator-signal`
- `pass-host-platform-agent-signal`

Blocked cases prove the boundary rejects:

- missing authoring reconstruction;
- raw spec bodies;
- raw eval bodies or eval prompts;
- automatic execution;
- Delivery Trust Harness skips;
- customer-visible follow-up;
- source mutation;
- production mutation;
- invalid Product Owner candidates;
- model calls;
- secrets;
- model credentials.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_spec_eval_authoring_gate.py --check
```

The verifier checks deterministic fixtures, schema identity, CLI roundtrip,
custom candidate input, and negative injections for raw specs, eval prompts,
acceptance criteria text, executable candidates, Delivery Trust skips, customer
follow-up effects, source mutation, production mutation, model-call effects, and
unsafe blocked receipts with brief candidates.

## Runtime Boundary

This gate does not start a daemon, call a model, mutate a repository, send a
customer message, write to production, or store raw customer material. It is a
structured artifact bridge only.
