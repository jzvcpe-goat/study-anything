# Patch Proposal Customer Feedback Delivery Trust Case Bridge

This bridge is the Patch Proposal-specific step after the Delivery Trust Intake
Gate. It consumes a metadata-only
`patch-proposal-delivery-trust-case-candidate-v1`, validates that the candidate
still matches Product Loop and Dual Loop evidence, then runs the existing local
Delivery Trust Case Harness assembly in deterministic mode.

The output is refs only:

- Delivery Trust receipt ref;
- CustomerHandoffPackage ref;
- Delivery Trust Case ref;
- source evidence refs for Product Loop, controlled failure, attention
  reconstruction, and Dual Loop gate.

## Claim Boundary

The bridge claims that a Patch Proposal Delivery Trust case candidate can be
assembled into metadata-only Delivery Trust case and handoff refs.

It does not claim:

- raw customer payload inclusion;
- customer-visible sending;
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
- customer-visible send requests;
- source mutation;
- production mutation;
- secrets;
- model credentials.

## Artifacts

Generated fixtures live under:

```text
fixtures/patch-proposal-customer-feedback-delivery-trust-case-bridge/
```

Passing cases emit both:

- `patch-proposal-delivery-trust-case-bridge-receipt.json`
- `patch-proposal-delivery-trust-case-handoff-refs.json`

Blocked cases emit only the bridge receipt.

## Verifier

Run:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_delivery_trust_case_bridge.py --check
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
