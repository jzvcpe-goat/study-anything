# Patch Proposal External Work Order Pack

Patch Proposal External Work Order Pack sits above the Patch Proposal
Acceptance Drill.

It answers one narrow delivery-trust question:

> If the acceptance drill allows continuation, can Study Anything / Cognitive
> Black Box emit a bounded work-order package for a host platform operator
> without including raw patch bodies or performing the work itself?

The pack consumes `patch-proposal-acceptance-drill-receipt-v1` and emits
`patch-proposal-external-work-order-receipt-v1`.

A ready receipt means only:

- the acceptance receipt was allowed;
- the work-order purpose is present;
- the operator reconstructed that execution belongs outside this system;
- the pack contains metadata refs and hashes only;
- a host platform operator may continue under separate local controls.

It does not mean the patch was read, reviewed, applied, committed, opened as a
PR, commented on, sent to a customer, published externally, deployed, or
certified as true or secure.

## Generated Evidence

- `platform/generated/study-anything-patch-proposal-external-work-order-pack.json`
- `platform/generated/study-anything-patch-proposal-external-work-order-pack.md`
- `platform/generated/study-anything-patch-proposal-external-work-order-pack.html`
- `fixtures/patch-proposal-external-work-order-pack/*/patch-proposal-external-work-order-receipt.json`

## Verifier

```bash
python3 scripts/verify_patch_proposal_external_work_order_pack.py --check
```

Regenerate deterministic fixtures and reports:

```bash
python3 scripts/verify_patch_proposal_external_work_order_pack.py --write
```

## Privacy Boundary

The pack must not include raw patch bodies, raw diffs, raw source text, raw
customer payloads, screenshots, attention streams, real secrets, Agent endpoint
secrets, model keys, user-owned Agent credentials, or local absolute paths. It
stores source refs, hashes, booleans, bounded work-order metadata, and explicit
claim limits.

## Failure Cases

The verifier proves the work-order pack blocks:

- blocked upstream acceptance receipt;
- missing work-order purpose or reconstruction;
- raw patch or raw diff requests;
- apply patch requests;
- open PR requests;
- PR comment requests;
- customer-visible action requests;
- external publication requests;
- production mutation requests.

## Product Meaning

This layer is the first portable "handoff to host operator" proof in the
patch-proposal chain. It still refuses to execute the work. The host platform
operator, terminal Agent, WorkBuddy-style workspace, or human developer must run
separate controls outside Study Anything / Cognitive Black Box before touching
code, PRs, customers, public channels, or production.
