# Patch Proposal Customer-Handoff Boundary Gate

Patch Proposal Customer-Handoff Boundary Gate sits above the External Operator
Completion receipt.

It answers one narrow delivery-trust question:

> Can Study Anything / Cognitive Black Box allow preparation for customer
> handoff without importing or sending customer-visible content?

The gate consumes `patch-proposal-external-operator-completion-receipt-v1` and
emits `patch-proposal-customer-handoff-boundary-receipt-v1`.

A ready receipt means only:

- the upstream external operator completion receipt was accepted;
- a delivery-class scenario is present;
- human reconstruction is present;
- claim boundary, privacy boundary, and sandbox receipt evidence are present;
- customer handoff may proceed only under a separate delivery control;
- no raw customer draft, patch, diff, repository body, PR comment, publication
  payload, production payload, secret, or model credential is included.

It does not send a customer message, publish externally, mutate production,
or certify correctness/security.

## Generated Evidence

- `platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.json`
- `platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.md`
- `platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.html`
- `fixtures/patch-proposal-customer-handoff-boundary-gate/*/patch-proposal-customer-handoff-boundary-receipt.json`

## Verifier

```bash
python3 scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --check
```

Regenerate deterministic fixtures and reports:

```bash
python3 scripts/verify_patch_proposal_customer_handoff_boundary_gate.py --write
```

## Privacy Boundary

The gate must not include raw customer drafts, raw patch bodies, raw diffs,
repository file bodies, PR comments, customer-visible payloads, external
publication payloads, production payloads, real secrets, Agent endpoint
secrets, model keys, user-owned Agent credentials, screenshots, attention
streams, or local absolute paths.

## Failure Cases

The verifier proves the gate blocks:

- blocked upstream completion;
- missing delivery-class scenario;
- missing human reconstruction;
- missing claim boundary;
- missing privacy boundary;
- missing sandbox receipt;
- raw customer drafts;
- raw patch return;
- production payload return;
- automatic customer sending;
- external publication;
- secret return;
- model credential return.

## Product Meaning

This is the first patch-proposal layer that touches the customer-delivery
boundary. It still does not perform customer delivery. It only proves that
handoff preparation must pass explicit delivery-class, human reconstruction,
claim, privacy, and sandbox gates before any customer-visible content is handled
by another control.
