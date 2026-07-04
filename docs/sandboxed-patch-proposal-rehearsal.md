# Sandboxed Patch Proposal Rehearsal

This layer consumes an allowed Spec/Eval Scenario Execution Rehearsal receipt and
creates a metadata-only patch proposal envelope. The envelope can describe
sandbox-local refs, rollback boundaries, and test refs, but it cannot include raw
patch bodies, raw diffs, customer payloads, repository secrets, external
publication, production mutation, or any irreversible effect.

## Boundary

- Input: `spec-eval-execution-rehearsal-receipt.json` from an allowed Spec/Eval
  scenario.
- Output: `sandboxed-patch-proposal-envelope-v1`.
- Bridge: structured JSON artifacts only.
- Authority: prepare sandbox-local metadata refs only.
- Not allowed: applying a patch, mutating the repository, sending customer-visible
  output, publishing externally, or changing production.

## Acceptance

Run:

```bash
python3 scripts/verify_sandboxed_patch_proposal_rehearsal.py --check
```

The verifier proves:

- an allowed Spec/Eval rehearsal can create a sandbox-local proposal envelope;
- missing Spec/Eval allowance blocks;
- missing rollback or test plan blocks;
- repository mutation, customer-visible action, external publication, and
  production mutation block;
- raw patch or diff bodies are rejected as negative fixtures;
- all artifacts remain metadata-only.

## Claim Boundary

This layer does not generate patch content, apply changes, approve customer
handoff, publish externally, or approve production changes. It only proves that
an implementation proposal can become a bounded, reversible, inspectable
sandbox-local envelope before any real mutation.
