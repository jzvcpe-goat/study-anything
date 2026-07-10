# CBB Protocol v1 Local Provenance

Protocol v1 provenance turns a deterministic gate result into a locally signed,
offline-verifiable receipt package. It uses Ed25519 over canonical
`cbb-json-c14n-v1` metadata. The signature is a content-integrity and local key
possession proof, not an external identity credential.

```text
TrustPolicy + EvidenceBundle + QualifiedReconstruction
  -> deterministic GateDecision
  -> canonical digest binding
  -> local Ed25519 signature
  -> offline provenance package
```

## Bound Objects

`cbb.receipt-provenance.v1` binds these SHA-256 values:

- subject reference;
- canonical Trust Policy;
- canonical Evidence Bundle;
- canonical Qualified Reconstruction;
- canonical Gate Decision;
- Delivery Trust Receipt fields excluding its embedded provenance object;
- a package-binding digest over those canonical object digests.

The package-binding digest deliberately excludes the archive and the provenance
signature. This avoids circular self-hashing. The offline verifier separately
checks that the Delivery Trust Receipt embeds the same provenance object and that
re-running the deterministic Trust Kernel reproduces the exact Gate Decision.

The signature input is the canonical provenance object with the `signature` field
omitted. Every other provenance field, including expiry, replay nonce, revocation
reference, signer public key, claim boundary, and digest bindings, is signed.

## Local Signer Boundary

The embedded signer uses `identity_scope=local_self_asserted`. Verification proves
that the package was signed by the private key corresponding to the embedded public
key. It does not prove that the signer is a particular person, company, auditor,
customer, or trusted authority.

Unsigned provenance remains valid only as `unsigned_development`. Its maximum scope
is `blocked`; offline portable verification rejects it. Signing cannot authorize a
scope above the deterministic Gate Decision. A signer may narrow that scope; the
offline package and verification result must preserve the narrower signer ceiling.

## Expiry, Replay, And Revocation

- `created_at` and `expires_at` bound the receipt validity window.
- `replay_nonce` can be consumed by an operator ledger when a one-time handoff is
  required. Ordinary offline re-verification does not consume it.
- `revocation.handle` and `revocation.registry_ref` identify mutable local
  revocation state. A receipt cannot permanently prove that it remains unrevoked;
  verification only evaluates the registry supplied at verification time.
- A nonce is written to the replay ledger only after every other verification check
  passes.

The bundled replay ledger is a local single-process aid, not a concurrent or
distributed one-time-use service. Time checks rely on the verifier host or explicit
operator-supplied timestamp; no trusted external time authority is claimed.

## Local CLI

Install the optional cryptography dependency before signing:

```bash
python -m pip install -e '.[crypto]'
```

Generate an owner-only raw Ed25519 key:

```bash
python3 scripts/cbb_provenance.py keygen \
  --private-key .cognitive-loop/keys/local.ed25519 \
  --acknowledge-local-identity-only
```

Sign a canonical receipt set and verify it offline:

```bash
python3 scripts/cbb_provenance.py sign \
  --input fixtures/cbb-v1-contracts/pass.json \
  --private-key .cognitive-loop/keys/local.ed25519 \
  --signer-id local-operator \
  --key-id local-key-1 \
  --output .cognitive-loop/artifacts/cbb/provenance-package.json

python3 scripts/cbb_provenance.py verify \
  --input .cognitive-loop/artifacts/cbb/provenance-package.json
```

Private keys are stored with owner-only `0600` permissions and are never written to
the package, verifier report, platform bundle, adoption pack, or external audit pack.
The raw key file is not encrypted; operators needing hardware-backed, shared, or
managed identity must provide a separate signer implementation.

## Verification

```bash
python3 scripts/generate_cbb_v1_provenance_assets.py --check
python3 scripts/verify_cbb_v1_provenance.py --check
python3 scripts/verify_cbb_v1_tamper_cases.py --check
./scripts/release_check.sh --cbb-protocol-only
```

The fixtures cover signed pass, unsigned development, expiry, local revocation,
one-time replay, policy tampering, evidence tampering, reconstruction tampering,
decision tampering, signature tampering, and wrong-public-key verification.
Delivery Trust Receipt envelope tampering is covered separately from the embedded
provenance object.

## Claim Boundary

This phase proves local Ed25519 key possession, canonical metadata integrity,
deterministic gate replay, expiry enforcement, supplied-registry revocation checks,
and optional one-time nonce consumption. It does not prove third-party signer
identity, globally current revocation state, archive byte-for-byte integrity,
production approval, customer outcomes, legal or security certification, safe
Agentic evolution, or independent audit completion.

A cryptographically valid package may still contain a `blocked` Gate Decision.
Provenance verification means the bounded decision is intact; it never changes
`blocked` into delivery authorization.
