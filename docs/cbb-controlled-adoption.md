# Controlled Adoption Evidence

Controlled adoption records what happened when an already-cleared candidate was used in
a bounded shadow, dogfood, or canary context. It does not create a new clearance.

The source package, source scope, revocation handle, exact release commit, Protocol v1
version, and conformance-pack digest are bound into every
`cbb.controlled-adoption-receipt.v1`.

## Evidence Classes

| Class | Meaning |
| --- | --- |
| `synthetic_fixture` | Deterministic repository test; not adoption evidence |
| `local_shadow` | Operator-supplied non-production shadow observation |
| `local_dogfood` | Operator-supplied internal use observation |
| `external_adopter` | Reserved for a future independently signed adoption-attestation path; fail-closed in this implementation |

Repository fixtures use only `synthetic_fixture`. The current generated report records
`real_adopter_evidence_count: 0`. Merely setting `evidence_class` to
`external_adopter` is not evidence: the current evaluator blocks it and emits
`real_adopter_evidence: false` until an independent attestation protocol exists.

## State Machine

- `observed`: a bounded pass maintained the requested scope;
- `blocked`: the request exceeded source scope or failed a binding/control;
- `incident_recorded`: adverse evidence froze or blocked further use;
- `rolled_back`: rollback evidence narrowed the resulting scope;
- `revoked`: the source clearance was revoked;
- `reopen_required`: a revoked or frozen flow requires a fresh clearance package.

No state may expand the source scope. A canary request above an internal-handoff source
is blocked even if its outcome receipt reports no adverse signal. Reopen requires a new
Trust Kernel decision, reconstruction, risk-owner evidence when applicable, and new
provenance; an old adoption pass cannot revive a revoked receipt.

## Commands

```bash
python3 scripts/generate_cbb_adoption_audit_assets.py --check
python3 scripts/verify_cbb_controlled_adoption_outcomes.py --check
python3 scripts/cbb_controlled_adoption.py \
  --package path/to/offline-provenance-package.json \
  --case path/to/operator-adoption-case.json \
  --expected-release-commit <40-character-commit> \
  --conformance-pack-sha256 <sha256>
```

The CLI reads explicit local files, performs no model or network call, and sends
nothing to a customer.

## Claim Boundary

The deterministic fixtures prove workflow behavior for pass, block, incident,
rollback, revocation, and reopen states. They do not prove external adoption, customer
outcomes, production safety, or independent audit completion.
