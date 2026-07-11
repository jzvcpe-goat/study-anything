# CBB Protocol v1 Canonical Contracts

This document defines the first canonical contract layer of Cognitive Black Box
Protocol v1. It converges the shipped Dual Loop and Delivery Trust receipt
families without deleting or renaming their public v0 interfaces.

## Delivered Surface

| Schema | Responsibility |
| --- | --- |
| `cbb.trust-policy.v1` | Subject, scenario, maximum scope, hard denies, risk budget, required evidence and roles |
| `cbb.evidence-bundle.v1` | Typed and attributable evidence bound to a subject and policy |
| `cbb.qualified-reconstruction.v1` | Active, scope-qualified human reconstruction with freshness and MRU evidence |
| `cbb.gate-decision.v1` | Canonical allow, block, or needs-evidence result |
| `cbb.delivery-trust-receipt.v1` | Claim-bounded receipt that carries the canonical decision and provenance |
| `cbb.receipt-provenance.v1` | Deterministic digest bindings and explicit unsigned-development status |
| `cbb.delivery-outcome-receipt.v1` | Signed-source post-delivery evidence and non-increasing trust update |

All models reject unknown fields. The committed Draft 2020-12 JSON Schemas are
generated from the strict Python models and checked for exact freshness.

## Canonical JSON

`cbb-json-c14n-v1` currently defines deterministic local bytes as UTF-8 JSON
with recursive key ordering, no insignificant whitespace, no NaN/Infinity, and
JSON-compatible model values. Equal objects with different input key order must
produce identical bytes and SHA-256 digests.

This is a local canonicalization contract for Protocol v1 fixtures. It is not a
portable signature standard. Signed cross-implementation provenance belongs to
the next provenance phase.

## Compatibility Map

```text
failure-contract-v1
  -> cbb.trust-policy.v1

failure-contract-v1 + sandbox-receipt-v1
  -> cbb.evidence-bundle.v1

attention-reconstruction-summary-v1
  -> cbb.qualified-reconstruction.v1

dual-loop-gate-receipt-v1
  -> cbb.evidence-bundle.v1

cbb.trust-policy.v1 + cbb.evidence-bundle.v1
  + cbb.qualified-reconstruction.v1
  -> cbb.gate-decision.v1

delivery-trust-receipt-v1 + cbb.gate-decision.v1
  -> cbb.delivery-trust-receipt.v1
```

The compatibility invariant is:

```text
target_scope <= source_scope
```

An equal mapping is valid. A narrower mapping is valid when evidence is stale,
missing, ambiguous, or blocked. A wider mapping is always rejected. The stale
fixture deliberately converts a v0 controlled-handoff allow into a v1
`needs_evidence` decision with blocked scope.

## Fixture Matrix

| Fixture | Expected Result |
| --- | --- |
| `pass` | Controlled customer handoff preserved |
| `missing-evidence` | No reconstruction; needs evidence; blocked scope |
| `hard-deny` | Production mutation hard deny blocks every scope |
| `stale` | Source allow narrows to needs evidence |
| `secret-like` | Forbidden field rejected before model validation |
| `malformed` | Missing and unknown fields rejected |
| `naive-timestamp` | Timestamp without a UTC offset rejected |
| `invalid-state` | Ambiguous cross-field state rejected |
| `scope-expansion` | Sandbox-only to limited-beta mapping rejected |

## Runtime Isolation

The canonical contract path imports no model SDK, Agent framework, RAG runtime,
browser automation, HTTP client, socket, subprocess, or customer-delivery
runtime. It performs no model calls, network calls, production mutation, or
automatic customer send.

The `compat_v0` module may read validated v0 metadata objects. It cannot change
their files, rewrite their output, or grant more authority than the source
receipt.

## Verification

```bash
python3 scripts/generate_cbb_v1_contract_assets.py --check
python3 scripts/verify_cbb_v1_contracts.py --check
python3 scripts/verify_cbb_v0_compatibility.py --check
python3 scripts/verify_cbb_v1_kernel.py --check
python3 scripts/verify_cbb_runtime_isolation.py --check
./scripts/release_check.sh --cbb-protocol-only
```

The first two verifier reports are generated at:

```text
platform/generated/study-anything-cbb-v1-contracts.json
platform/generated/study-anything-cbb-v0-compatibility.json
```

## Claim Boundary

This contract phase proves strict local contracts, deterministic JSON, metadata
privacy, and non-expanding v0 compatibility. The separate deterministic Trust
Kernel phase now evaluates these objects. Neither phase implements cryptographic
signing, revocation, production delivery, customer outcomes, safe Agentic
self-evolution, or independent audit completion.
