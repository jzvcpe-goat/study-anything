# Patch Proposal Customer Feedback Controlled Follow-up Feedback Delivery Trust Case Bridge

This bridge is the Patch Proposal-specific step after the controlled follow-up
feedback Delivery Trust Intake Gate. It consumes a metadata-only
`patch-proposal-delivery-trust-case-candidate-v1`, validates that the candidate
still matches the Product Loop, controlled follow-up feedback, Dual Loop, and
active reconstruction evidence, then runs the existing local Delivery Trust Case
Harness assembly in deterministic mode.

The output is refs only:

- Delivery Trust receipt ref;
- CustomerHandoffPackage ref;
- Delivery Trust Case ref;
- source evidence refs for Product Loop, controlled follow-up feedback,
  controlled failure, active attention reconstruction, and Dual Loop gate.

## Claim Boundary

The bridge claims that a controlled follow-up feedback Patch Proposal Delivery
Trust case candidate can be assembled into metadata-only Delivery Trust case and
handoff refs after Delivery Trust Case Harness evidence is present.

It does not claim:

- raw customer payload inclusion;
- automatic customer sending;
- customer-visible sending;
- customer-visible follow-up;
- source mutation;
- production mutation;
- external publication;
- model-call evaluation;
- real customer delivery;
- production deployment approval.

## Blocked Paths

The bridge blocks:

- missing or invalid Delivery Trust case candidates;
- missing Product Loop runs;
- Product Loop hash or id mismatches;
- missing or mismatched Dual Loop evidence;
- blocked Dual Loop gates;
- AI-review-only Product Loop evidence;
- automatic customer send requests;
- customer-visible send requests;
- customer-visible follow-up requests;
- source mutation;
- production mutation;
- external publication;
- model calls;
- secrets;
- model credentials.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-delivery-trust-case-bridge/
```

Passing cases emit both:

- `patch-proposal-controlled-follow-up-feedback-delivery-trust-case-bridge-receipt.json`
- `patch-proposal-controlled-follow-up-feedback-delivery-trust-case-handoff-refs.json`

Blocked cases emit only the bridge receipt.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_delivery_trust_case_bridge.py --check
```

The verifier checks deterministic fixtures, schema identity, CLI roundtrip,
custom candidate input, metadata-only privacy boundaries, candidate/Product
Loop/Dual Loop ref matching, existing Delivery Trust Case Harness assembly, and
negative injections for raw payloads, handoff package bodies, Delivery Trust
case bodies, customer sends, source mutation, production mutation, model calls,
and unsafe ready/blocked receipt transitions.

## Runtime Boundary

This bridge does not start a daemon, call a model, send a customer message,
mutate source, mutate production, or store raw customer/spec/eval/sandbox/
attention material. The only Harness output this bridge persists is a
metadata-only ref set.
