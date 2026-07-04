# Patch Proposal Acceptance Drill

Patch Proposal Acceptance Drill sits above the Patch Proposal Operator Handoff
Bridge.

It answers one narrow delivery-trust question:

> Can an external operator decide whether to continue from a patch proposal
> handoff package using metadata-only evidence, without reading raw patch bodies
> or letting Study Anything / Cognitive Black Box mutate the repository?

The drill consumes a `patch-proposal-operator-handoff-bridge-receipt-v1` and
emits `patch-proposal-acceptance-drill-receipt-v1`.

A pass means only:

- the bridge receipt is ready;
- the operator decision is present;
- the operator reconstructed the no-mutation boundary;
- no raw patch or raw diff evidence was requested;
- no apply/open PR/comment/customer-send/publish/production action was requested;
- the next step is only a bounded external operator work order.

It does not mean the patch was read, reviewed, applied, committed, opened as a
PR, commented on, sent to a customer, published externally, deployed, or
certified as true or secure.

## Generated Evidence

- `platform/generated/study-anything-patch-proposal-acceptance-drill.json`
- `platform/generated/study-anything-patch-proposal-acceptance-drill.md`
- `platform/generated/study-anything-patch-proposal-acceptance-drill.html`
- `fixtures/patch-proposal-acceptance-drill/*/patch-proposal-acceptance-drill-receipt.json`

## Verifier

```bash
python3 scripts/verify_patch_proposal_acceptance_drill.py --check
```

Regenerate deterministic fixtures and reports:

```bash
python3 scripts/verify_patch_proposal_acceptance_drill.py --write
```

## Privacy Boundary

The drill must not include raw patch bodies, raw diffs, raw source text, raw
customer payloads, screenshots, attention streams, real secrets, Agent endpoint
secrets, model keys, user-owned Agent credentials, or local absolute paths. It
stores refs, hashes, booleans, bounded decisions, and explicit claim limits.

## Failure Cases

The verifier proves the acceptance drill blocks:

- blocked upstream bridge receipt;
- missing operator decision or reconstruction;
- raw patch or raw diff evidence requests;
- apply patch requests;
- open PR requests;
- customer-visible action requests;
- external publication requests;
- production mutation requests.

## Product Meaning

This layer is the first "operator can continue" proof in the patch-proposal
chain. It still refuses to perform the continuation itself. The continuation
belongs to a host platform operator, terminal Agent, WorkBuddy-style workspace,
or human developer operating under separate local controls.
