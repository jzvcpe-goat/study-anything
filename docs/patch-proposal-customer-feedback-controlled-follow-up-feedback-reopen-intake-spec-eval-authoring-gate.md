# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Spec/Eval Authoring Gate

This gate is a metadata-only Product Loop boundary for the Patch Proposal
controlled follow-up feedback chain.

It consumes a `patch-proposal-controlled-follow-up-feedback-reopen-intake-product-owner-receipt-v1`
receipt and its `patch-proposal-product-spec-eval-candidate-v1` candidate from
the reopen-intake Product Owner Gate. It can emit only a
`patch-proposal-product-loop-brief-candidate-v1` artifact. The transition is
allowed only after active authoring-boundary reconstruction.

## Claim Boundary

The gate claims that a bounded Patch Proposal controlled follow-up feedback
spec/eval candidate can become a Product Loop brief candidate after the author
reconstructs the boundary:

- spec and eval material remains hash/reference only;
- the brief candidate remains metadata-only;
- execution remains blocked;
- Delivery Trust Harness skips remain blocked;
- customer contact remains blocked;
- backlog creation and priority assignment remain blocked;
- source and production mutation remain blocked.

The gate does not claim:

- finished product spec quality;
- finished eval coverage;
- automatic execution;
- customer contact;
- automatic backlog creation or priority assignment;
- source mutation;
- external publication;
- production mutation;
- Delivery Trust Harness readiness;
- model-call evaluation.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-spec-eval-authoring-gate/
```

Passing case:

- `pass`

Blocked cases prove the boundary rejects:

- missing or blocked reopen-intake Product Owner receipts;
- missing spec/eval candidate refs;
- missing gate, bridge, closure, outcome, action, actor, intake, backlog, and Product Owner refs;
- missing authoring reconstruction;
- missing claim or privacy boundaries;
- raw spec bodies;
- raw eval bodies or eval prompts;
- raw follow-up, customer, or backlog data;
- customer identity;
- automatic backlog creation or priority assignment;
- automatic execution;
- Delivery Trust Harness skips;
- customer contact;
- Product Loop backlog mutation;
- source mutation;
- production mutation;
- external publication payloads;
- model calls;
- secrets;
- model credentials.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_spec_eval_authoring_gate.py --check
```

The verifier checks deterministic fixtures, schema identity, CLI roundtrip,
custom Product Owner receipt input, and negative injections for raw specs, eval prompts,
acceptance criteria text, executable candidates, Delivery Trust skips, customer
contact effects, source mutation, production mutation, model-call effects, and
unsafe blocked receipts with brief candidates.

## Runtime Boundary

This gate does not start a daemon, call a model, mutate a repository, send a
customer message, write to production, or store raw customer material. It is a
structured artifact bridge only.
