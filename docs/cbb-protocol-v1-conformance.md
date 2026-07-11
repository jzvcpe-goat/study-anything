# CBB Protocol v1 Conformance

Delivery Clearance Protocol v1 conformance is an offline interoperability result, not a
certificate of AI correctness or production safety.

An implementation is **Protocol v1 fixture-conformant** only when it can independently:

1. read all eight published canonical schemas;
2. reproduce `cbb-json-c14n-v1` bytes and SHA-256 digests;
3. reproduce the deterministic Trust Kernel decisions;
4. verify local Ed25519 fixture signatures, expiry, replay, and supplied revocation;
5. reproduce Outcome Receipt trust degradation;
6. reproduce proposal-only Evolution Gate decisions;
7. reject authority-bearing unknown extensions and incompatible protocol versions;
8. preserve v0 identifiers as compatibility-only inputs without scope expansion.

The reference pack is generated with:

```bash
python3 scripts/generate_cbb_v1_conformance_pack.py --check
python3 scripts/verify_cbb_v1_external_consumer.py --check
```

## Second Implementation

`conformance/python/cbb_v1_consumer.py` is intentionally outside the
`study_anything` package. It does not import Pydantic, the Trust Kernel, the Agentic
runtime, adapters, or reference verifier code. It reads an extracted pack offline and
implements the bounded rules exercised by the public vectors.

`cryptography` is used only for Ed25519 public-key verification. The consumer performs
no model call, retrieval, network access, tool execution, policy apply, production
mutation, or customer send.

## Pack Contents

The deterministic ZIP contains:

- eight JSON Schemas and their digests;
- one canonical vector per canonical object;
- seven Trust Kernel vectors;
- twelve signed/tampered provenance vectors;
- five Outcome Receipt vectors;
- six Evolution Gate vectors;
- version-negotiation, extension-authority, privacy, and v0 migration vectors;
- the independent consumer source and public governance documents;
- a manifest covering every non-manifest file in the archive.

The manifest is integrity metadata, not a third-party signature. Signed fixture keys are
test-only and establish no external identity.

## Conformance Language

Allowed public statement:

> Implementation X is CBB Protocol v1 fixture-conformant against conformance pack digest Y.

Required qualifiers:

- name the implementation version and pack digest;
- identify any unsupported optional extension;
- state that conformance is local and fixture-bounded;
- do not claim certification, endorsement, production safety, or general AI trust.

Conformance expires as an interoperability claim when the implementation, pack digest,
canonical schema set, or major protocol version changes.

## Claim Boundary

This conformance pack proves local cross-implementation agreement against published
fixtures. It does not create a certification authority, prove a real signer identity,
provide global revocation, validate production deployment, guarantee customer outcomes,
or complete the independent human security audit.
