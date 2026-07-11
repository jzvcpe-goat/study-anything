# External Adopter Attestation

External adopter attestation is the optional Protocol v1 extension that lets a real
adopter prove a bounded canary observation without turning repository fixtures or a
self-declared identity into evidence.

The intake does not create Delivery Clearance. It only determines whether a signed,
identity-bound observation may enter the existing Controlled Adoption evaluator. The
resulting adoption receipt can maintain or reduce the source scope, never expand it.

## Contracts

- `cbb.external-adoption-attestation-envelope.v1` carries the signed observation,
  adopter trust record, detached Ed25519 signature, and metadata-only boundary.
- `cbb.external-adoption-attestation-receipt.v1` records signature, identity, case,
  release, source-package, conformance, and trust-root verification.

These are optional extension contracts. They do not change the eight canonical
Protocol v1 object classes.

## Independent Trust Root

The submitted envelope is untrusted. Before intake, an operator must provide an
`ExternalAdoptionExpectedScopeV1` outside that envelope. It pins:

- the exact repository release commit;
- Protocol v1 and conformance-pack digest;
- source package digest, Delivery Clearance receipt, revocation handle, and scope;
- the exact Controlled Adoption case id and canonical digest;
- trusted adopter organization and human-observer references;
- the adopter's Ed25519 public-key fingerprint and independence-attestation reference;
- repository actor references that cannot self-attest as the external adopter.

Possession of a signing key is not external identity. The organization, observer,
fingerprint, and independence reference must match a pre-pinned trusted identity.
The public deterministic fixture key is also denied by the intake kernel when presented
as an external trust root, even if a caller places it in an expected scope.

## State Machine

- `attestation_ready`: scope is pinned, but no signed external attestation exists;
- `rejected`: a signature, identity, binding, privacy, or trust-root check failed;
- `synthetic_validated`: fixture shape and verifier behavior passed, with zero real
  adopter evidence;
- `external_attestation_verified`: a separately trusted external identity signed the
  exact observation and case.

Only `external_attestation_verified` may set
`real_adopter_evidence_accepted: true`. Even then, the intake receipt grants no delivery
or production authority. Controlled Adoption rechecks the receipt against the actual
case before recording `real_adopter_evidence: true`.

## Commands

```bash
python3 scripts/generate_cbb_adoption_audit_assets.py --check
python3 scripts/verify_cbb_external_adoption_attestation.py --check

python3 scripts/cbb_external_adoption_attestation.py ready \
  --expected-scope path/to/operator-pinned-expected-scope.json \
  --evaluated-at 2026-07-15T03:00:00Z

python3 scripts/cbb_external_adoption_attestation.py evaluate \
  --expected-scope path/to/operator-pinned-expected-scope.json \
  --envelope path/to/external-signed-attestation.json \
  --evaluated-at 2026-07-15T03:00:00Z \
  --out path/to/external-adoption-attestation-receipt.json

python3 scripts/cbb_controlled_adoption.py \
  --package path/to/offline-provenance-package.json \
  --case path/to/exact-controlled-adoption-case.json \
  --expected-release-commit <40-character-commit> \
  --conformance-pack-sha256 <sha256> \
  --external-attestation-expected-scope path/to/operator-pinned-expected-scope.json \
  --external-attestation-envelope path/to/external-signed-attestation.json
```

Controlled Adoption replays the envelope instead of trusting the intake receipt's
boolean fields. Its resulting receipt id binds the attestation receipt ref and digest,
so distinct signed evidence cannot share one Controlled Adoption identity. All commands
are offline and deterministic. They make no model call, network request, production
mutation, or automatic customer send.

## Claim Boundary

Repository fixtures and the hermetic integration test prove contract behavior only.
They do not identify an external adopter, receive external evidence, prove customer
outcomes, authorize delivery, certify production, or complete an independent audit.
A real-evidence count remains zero until an external actor supplies a signed envelope
whose identity was independently pinned before submission.
