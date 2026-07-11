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
| `external_adopter` | Requires an independently signed, pre-pinned external-adopter attestation |

Repository fixtures use only `synthetic_fixture`. The current generated reports record
zero real adopter evidence. Merely setting `evidence_class` to `external_adopter` is not
evidence: the evaluator requires a verified
`cbb.external-adoption-attestation-receipt.v1` bound to the exact case, source package,
release commit, conformance digest, and independently pinned adopter identity.

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
python3 scripts/verify_cbb_external_adoption_attestation.py --check
python3 scripts/cbb_controlled_adoption.py \
  --package path/to/offline-provenance-package.json \
  --case path/to/operator-adoption-case.json \
  --expected-release-commit <40-character-commit> \
  --conformance-pack-sha256 <sha256> \
  --external-attestation-expected-scope path/to/operator-pinned-expected-scope.json \
  --external-attestation-envelope path/to/external-signed-attestation.json
```

The two attestation arguments are required only for the `external_adopter` evidence
class. The evaluator replays the signature and trust-root checks; it does not trust a
receipt JSON supplied by the caller. The CLI reads explicit local files, performs no
model or network call, and sends nothing to a customer. See
[External Adopter Attestation](cbb-external-adoption-attestation.md).

## Claim Boundary

The deterministic fixtures prove workflow behavior for pass, block, incident,
rollback, revocation, and reopen states. They do not prove external adoption, customer
outcomes, production safety, or independent audit completion.
