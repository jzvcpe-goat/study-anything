# Patch Proposal External Operator Completion

Patch Proposal External Operator Completion sits above the Patch Proposal
External Work Order Pack.

It answers one narrow delivery-trust question:

> If a host platform operator completes the work outside Study Anything /
> Cognitive Black Box, can the result re-enter this system only as metadata,
> without importing raw patch bodies, raw diffs, repository file bodies, PR
> comments, customer payloads, production payloads, secrets, or model
> credentials?

The layer consumes `patch-proposal-external-work-order-receipt-v1` and emits
`patch-proposal-external-operator-completion-receipt-v1`.

An accepted receipt means only:

- the upstream work-order receipt was ready;
- the completion purpose is present;
- the operator reconstructed that execution happened outside this system;
- the completion package contains refs, hashes, booleans, and bounded metadata;
- no raw patch, diff, repository, PR, customer, publication, production, secret,
  or model-credential payload re-entered Study Anything / Cognitive Black Box.

It does not mean the patch is correct, safe, customer-ready, publicly
publishable, production-approved, or certified.

## Generated Evidence

- `platform/generated/study-anything-patch-proposal-external-operator-completion.json`
- `platform/generated/study-anything-patch-proposal-external-operator-completion.md`
- `platform/generated/study-anything-patch-proposal-external-operator-completion.html`
- `fixtures/patch-proposal-external-operator-completion/*/patch-proposal-external-operator-completion-receipt.json`

## Verifier

```bash
python3 scripts/verify_patch_proposal_external_operator_completion.py --check
```

Regenerate deterministic fixtures and reports:

```bash
python3 scripts/verify_patch_proposal_external_operator_completion.py --write
```

## Privacy Boundary

The completion receipt must not include raw patch bodies, raw diffs, repository
file bodies, PR comment bodies, customer-visible content, external publication
payloads, production payloads, screenshots, attention streams, real secrets,
Agent endpoint secrets, model keys, user-owned Agent credentials, or local
absolute paths.

It stores source refs, hashes, booleans, bounded completion metadata, and
explicit claim limits.

## Failure Cases

The verifier proves the completion receipt blocks:

- blocked or missing upstream work-order receipts;
- missing completion purpose or reconstruction;
- raw patch or raw diff return;
- repository file body return;
- PR comment payload return;
- customer-visible payload return;
- external publication payload return;
- production payload return;
- secret return;
- model credential return.

## Product Meaning

This layer closes the first "return from host operator" boundary in the
patch-proposal chain. It still refuses customer delivery, external publication,
and production approval. Those require separate delivery-class gates outside
this receipt.
