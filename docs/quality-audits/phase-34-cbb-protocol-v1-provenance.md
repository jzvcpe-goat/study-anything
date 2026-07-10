# Phase 34 CBB Protocol V1 Provenance Audit

Audit date: 2026-07-10 PDT

Project: local Ed25519 provenance, expiry, revocation references, replay controls,
and offline verification for CBB Protocol v1

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.294-cbb-v1-provenance`

Audit base: `8b3f04a7b84321c170a26cbbfa61b416d40c26e8`

Preview: none; this phase changes protocol contracts, local cryptographic tooling,
metadata-only packages, release gates, fixtures, and verifier receipts.

Auditor: Codex

Authority: `/Users/james/Downloads/通用质检方案.md`, reviewed in S0-S15
order.

## Executive Conclusion

Decision: **Pass locally; full release and protected CI pending**.

Protocol v1 now binds canonical policy, evidence, qualified reconstruction,
deterministic decision, and the Delivery Trust Receipt envelope into one local
Ed25519 provenance object. Offline verification re-runs the deterministic Trust
Kernel and checks content digests, signer public-key possession, expiry, supplied
revocation state, optional replay consumption, safe metadata, and monotonic scope.

Four P1 defects were found and removed during Contract-First review:

1. The first signing design did not bind Delivery Trust Receipt fields outside the
   embedded provenance object. A new non-circular receipt-envelope digest now
   invalidates receipt ID, reference, limitation, status, scope, reason, privacy,
   or issued-time tampering.
2. An unsigned development package initially inherited the gate's customer-handoff
   scope at its top-level claim boundary. Unsigned packages now always claim
   `blocked` scope and fail portable verification.
3. A signer could narrow a gate scope while the package and verification result
   still displayed the wider gate scope. The signer ceiling now propagates to both
   package claim and verification output, and the package cannot re-expand it.
4. Secret-like strings in structurally valid external metadata could raise a raw
   canonicalization exception. Safe-metadata scanning now runs first and returns a
   stable `safe_metadata=false` result without echoing the rejected value.

Three P2 boundaries remain explicit rather than overclaimed: the bundled replay
ledger is not concurrency-safe across processes, time validation has no external
trusted time authority, and raw local private-key files are owner-only but not
encrypted or hardware-backed.

One additional P2 CLI issue was removed: local input and key failures previously
fell through to Python tracebacks. The CLI now returns bounded error codes, keeps the
optional dependency install hint, and does not echo key paths or rejected input.

## S0-S3 Source, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | Isolated worktree based on `8b3f04a7` |
| Product contract | Pass | Signature protects deterministic trust evidence; it does not replace the gate |
| Delivery boundary | Pass | Local self-asserted identity and metadata-only offline package only |
| No-touch boundary | Pass | `/Users/james/Documents/学习系统` was not modified |
| External checkpoint | Pending | Issue #414 remains an external human audit checkpoint; audit completion is false |

Included:

- Ed25519 local key generation, signing, and verification;
- canonical subject, policy, evidence, reconstruction, decision, receipt-envelope,
  and package-binding digests;
- local self-asserted signer metadata and public-key fingerprint;
- expiry, supplied-registry revocation, and optional nonce consumption;
- 12 state fixtures and seven explicit tamper cases;
- CLI, tests, release receipt fields, platform/adoption packs, and external audit
  preparation scope.

Excluded:

- third-party identity proof, PKI, transparency log, timestamp authority, HSM, or
  encrypted key management;
- distributed/concurrent replay prevention or globally current revocation state;
- archive byte identity, production release approval, customer outcome proof, or
  automatic customer sending;
- Agentic policy mutation or independent security-audit completion.

## S4-S8 Loop, Data, And Protocol Surface

The implemented loop is:

1. validate strict canonical CBB objects;
2. recompute subject, policy, evidence, reconstruction, decision, and receipt
   envelope digests;
3. sign the canonical provenance object with its signature field omitted;
4. package public metadata only and embed the same provenance in the receipt;
5. scan external package metadata for forbidden or secret-like content;
6. re-run the deterministic Trust Kernel offline;
7. verify digest bindings, signature, public-key fingerprint, time, supplied
   revocation state, and signer/gate/package scope monotonicity;
8. optionally consume the nonce only after every other check passes.

The package binding excludes the archive and signature to avoid circular hashing.
The receipt-envelope digest excludes only the embedded provenance object. Package
validation requires receipt and decision references, status, scope, and reasons to
match before cryptographic verification.

## S9 Security And Privacy

| Boundary | Result |
| --- | --- |
| Signature algorithm | Ed25519 through optional `cryptography` dependency |
| Private key export | Absent from packages, reports, platform packs, and audit pack |
| Key file permissions | Owner-only `0600`; group/world access rejected |
| Signer identity | Explicitly `local_self_asserted` |
| Scope escalation | Rejected above gate; signer narrowing preserved |
| Secret-like metadata | Stable fail without value or exception-text echo |
| Object tampering | Policy, evidence, reconstruction, decision, and receipt fail |
| Signature/key tampering | Invalid signature and wrong public key fail |
| Expiry/revocation/replay | Fail closed under supplied local state |

The fixture signing key is deterministically derived from a public test seed and is
not production key material. Generated assets contain only its public key and
signature. A valid local signature does not certify the signer identity or audit
status.

## S10-S13 Production, UI, Copy, And Legacy

- No UI, payment, hosted identity, production mutation, customer send, or customer
  payload is introduced.
- The existing six v1 schema IDs and all v0 CLI/output contracts remain supported.
- `cbb.receipt-provenance.v1` expands in place because provenance was explicitly the
  unsigned-development placeholder for this phase.
- Public wording distinguishes cryptographic validity from delivery allow: a valid
  signed blocked decision can verify while still authorizing `blocked` scope.
- Revocation, replay, time, and key-storage limitations are documented as local
  alpha boundaries rather than production guarantees.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| Provenance verifier | Pass; 12 cases |
| Tamper verifier | Pass; seven cases |
| Focused provenance tests | Pass; 11 tests |
| Canonical contract verifier | Pass with receipt-envelope binding |
| Ruff | Pass on changed Python surfaces |
| Strict mypy | Pass on four changed CBB modules; repository baseline exception excluded |
| Platform/adoption pack convergence | Pass; topology converged in two refresh passes, then 21/21 no-mutation check |
| External audit preparation pack | Pass; 71 files, 73 ZIP entries, audit remains incomplete |
| Full API suite | Pass; 960 tests, existing Starlette/httpx deprecation warning only |
| Partial release check | Pass; CBB-only, dependency-light Dual-Loop-only, and skip-clean-clone receipts remained honest |
| Protected GitHub checks | Pending PR |
| Independent human audit | Not started |

## S15 Decision

Merge only after generated evidence converges, the full API suite passes, partial
release receipts remain honest, and protected checks pass. After merge, regenerate
and repin issue #414 to the exact main commit and audit-pack digest while keeping
`audit completed: no`.

This audit authorizes the next local Protocol v1 milestone only. It is not a
third-party signer certificate, production release, global revocation service,
customer outcome proof, independent security audit, or permission for Agentic code
to modify the Trust Kernel.
