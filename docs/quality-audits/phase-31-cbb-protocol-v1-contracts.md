# Phase 31 CBB Protocol V1 Canonical Contracts Audit

Audit date: 2026-07-10 PDT

Project: Cognitive Black Box Protocol v1 canonical contract layer and v0
compatibility boundary

Repo: `jzvcpe-goat/study-anything`

Worktree: `study-anything-cbb-v1-contracts`

Branch: `codex/v0.3.291-cbb-v1-contracts`

Audit base: `1dfe0dd6170dda0f8b9dfa129dcbf9aa6a11c39b`

Preview: none; this phase changes Python protocol models, generated JSON
schemas and fixtures, deterministic verifiers, release receipts, and platform
distribution metadata rather than a UI surface.

Auditor: Codex

Authority: `/Users/james/Downloads/通用质检方案.md`, reviewed in S0-S15
order.

## Executive Conclusion

Decision: **Pass locally; protected CI pending**.

The phase implements the first bounded Protocol v1 milestone: six strict
canonical contracts, deterministic JSON bytes, explicit negative fixtures,
and adapters that preserve or narrow authority when projecting shipped v0
Dual Loop evidence into v1. It does not implement the deterministic policy
evaluator, portable signing, production release authority, outcome-based trust
degradation, Agentic evidence collection, or an external human audit.

Maximum current risks:

1. Contract validity is not gate authority. PR 2 must add the deterministic
   Trust Kernel before policy plus evidence can independently reproduce a
   decision.
2. `cbb.receipt-provenance.v1` is deliberately `unsigned_development`.
   Digest binding is not portable identity, attestation, or non-repudiation.
3. The repository remains self-audited. Independent external security review
   is still pending in issue #414 and cannot be replaced by CI success.

Current implementation: a local-first, deterministic, metadata-only contract
and compatibility layer for the CBB reference harness.

Claimed target: an open CBB protocol whose implementations can evaluate
scoped delivery trust, emit portable receipts, observe outcomes, degrade
trust, and evolve without black-box self-authorization.

Core mismatch: intentionally temporal. This PR defines the v1 data language;
it does not claim that the full v1 decision runtime exists.

Next required step: implement PR 2, the deterministic Trust Kernel and runtime
isolation gate, against these contracts without changing v0 compatibility
outputs.

Explicitly do not add in this phase: model calls, RAG, production mutation,
automatic customer sending, hosted control planes, real customer payloads,
portable signatures, or rule self-modification.

## S0 Materials Collected

- canonical product and protocol documents;
- shipped v0 failure, attention, Dual Loop, Delivery Trust, and handoff
  contracts;
- current release and platform-pack generators;
- Phase 30 positioning audit and Protocol v1 development plan;
- six generated v1 schemas and seven positive/negative fixture cases;
- focused and repository-wide automated verification;
- the named Contract-First audit framework.

## S1 Source Of Truth Audit

| Area | Current Truth | Evidence | Risk |
| --- | --- | --- | --- |
| Canonical repository | `/Users/james/Documents/study-anything-cognitive-loop-positioning-pivot` | Clean `main` supplied this phase's base | Low |
| Isolated implementation | `/Users/james/Documents/study-anything-cbb-v1-contracts` | Dedicated worktree and branch | Low |
| Base main | `1dfe0dd6170dda0f8b9dfa129dcbf9aa6a11c39b` | `git rev-parse HEAD` before edits | Low |
| No-touch workspace | `/Users/james/Documents/学习系统` | No commands or edits were directed there | Pass |
| Runtime | Full project Python 3.11 environment selected explicitly | Verifier and test commands record the selected interpreter | Low |
| Preview | None | No user-facing UI changed | Not applicable |
| Historical v0 assets | Compatibility sources, not the v1 normative model | `compat_v0.py` maps rather than deletes them | Medium if mislabelled; controlled by adapters |

Verdict: **Pass**. The implementation and review surfaces are not mixed with
the historical no-touch workspace or an unverified mirror.

## S2 Delivery Boundary Audit

| Category | Items | Evidence | Risk |
| --- | --- | --- | --- |
| Included | Six canonical models and schemas; canonical JSON; nine fixtures; v0 adapters; two verifiers; release and distribution integration | Source, schemas, reports, tests, release receipt | Low |
| Excluded | Trust Kernel evaluator, protocol CLI, signatures, revocation, outcome loop, Agentic runtime, customer delivery automation | Protocol docs and claim boundaries | None if wording stays explicit |
| Claimed but unproven | None | Unreleased notes call the layer local and unsigned | Pass |
| External checkpoint | Independent security audit | Issue #414 remains external and incomplete | Required before external audit claim |

The CBB-only release receipt is partial proof: it must keep full release,
clean-clone, and dependency-install fields false. `--dual-loop-only` may run
without project dependencies; in that mode the receipt explicitly records the
v1 contract verifiers as integrated but not passed.

Verdict: **Pass**.

## S3 Product Contract Audit

### Product identity

CBB is an open, local-first protocol and reference harness for scoped AI
delivery trust. Study Anything remains a Human Reconstruction / Learning
Adapter.

### Primary users

- protocol implementers and verifier authors;
- AI delivery operators and risk owners;
- adapter and Agent-platform maintainers;
- humans reconstructing delivery boundaries.

### Contract for this phase

1. Express policy, evidence, qualified reconstruction, decision, receipt, and
   provenance through one canonical v1 vocabulary.
2. Reject unknown fields, malformed states, unsafe metadata, and authority
   expansion.
3. Produce byte-stable JSON and generated Draft 2020-12 schemas.
4. Preserve shipped v0 entrypoints and evidence while making narrowing
   explicit.
5. Integrate conformance evidence into release and adopter packages without
   claiming production trust.

Actual implementation matches this bounded contract. No learning-product or
plugin-marketplace expansion is introduced.

Verdict: **Pass**.

## S4-S6 Implementation, User Loop, And Information Architecture

The primary loop is a developer/operator protocol loop rather than a web UI:

1. select a v0 delivery evidence chain or construct canonical v1 payloads;
2. validate every payload against strict models;
3. canonicalize and hash metadata deterministically;
4. project v0 evidence without increasing authority;
5. inspect pass, missing, stale, hard-deny, malformed, unsafe, and
   scope-expansion results;
6. run release gates and distribute the schemas, fixtures, and reports;
7. hand the canonical objects to the future deterministic kernel.

Information architecture is explicit:

| Layer | Ownership |
| --- | --- |
| `cbb/protocol/models.py` | Normative data invariants and scope ordering |
| `canonical.py` | Canonical bytes, safe metadata, schema generation |
| `compat_v0.py` | Non-expanding mapping from shipped v0 evidence |
| `fixtures.py` | Deterministic conformance examples and negatives |
| `verify_cbb_v1_contracts.py` | v1 model, byte, schema, and isolation conformance |
| `verify_cbb_v0_compatibility.py` | compatibility equality/narrowing conformance |
| `release_check.sh` | release invocation and honest receipt state |

No page, navigation, or design-system assertion is made. UI review is not an
appropriate blocker for this phase.

## S7 Data Architecture Audit

| Canonical object | Authority represented | Key invariant |
| --- | --- | --- |
| `cbb.trust-policy.v1` | Maximum allowed scope and required evidence | Required hard denies cannot be omitted |
| `cbb.evidence-bundle.v1` | Referenced evidence and its supported scope | Claim and evidence scope cannot exceed bundle support |
| `cbb.qualified-reconstruction.v1` | Scoped, expiring human reconstruction | Passive attention cannot qualify delivery; stale evidence blocks |
| `cbb.gate-decision.v1` | Deterministic decision result shape | Non-allow decisions remain blocked; claim cannot expand decision |
| `cbb.delivery-trust-receipt.v1` | Human/machine-readable delivery claim | Status, reasons, scope, and provenance must agree |
| `cbb.receipt-provenance.v1` | Local digest bindings and verifier identity | Unsigned provenance must disclaim portable attestation |

Canonicalization is UTF-8 JSON with recursively sorted object keys, no
formatting whitespace, and no NaN values. A payload with different input key
order produces identical bytes and SHA-256. The implementation does not claim
compatibility with JCS or another external canonicalization standard.

The data loop is additive. v0 artifacts remain authoritative for existing
consumers; v1 wrappers retain their refs and cannot grant a higher scope than
the source receipt. A stale reconstruction narrows a source allow to
`needs_evidence` with blocked scope.

Verdict: **Pass for PR 1; deterministic evaluation remains PR 2**.

## S8 Protocol And Agent Action Surface Audit

| Surface | Allowed | Forbidden |
| --- | --- | --- |
| Canonical models | Validate metadata and state relationships | Execute tools, mutate policy, or approve delivery |
| Compatibility adapter | Preserve or narrow source authority | Expand delivery scope or invent stronger evidence |
| Verifier | Read repository artifacts and emit bounded reports | Network, model, browser, process, or production authority |
| Future Agentic runtime | Propose evidence plans and boundary candidates | Override kernel, edit hard denies, or self-approve |
| External eval | Supporting evidence | Final trust source |

An AST isolation check rejects runtime-authority imports from the canonical
protocol package. This is a structural guard, not a proof against all supply
chain or interpreter compromise.

Verdict: **Pass**.

## S9 Security, Privacy, And Permissions Audit

- Strict models forbid unknown fields.
- Recursive metadata validation rejects raw source/report/customer payload
  fields, attention streams, prompts, credentials, tokens, signed URLs,
  screenshots, keystrokes, mouse coordinates, and local absolute paths.
- Privacy contracts require metadata-only operation, no model call, no
  production mutation, and no automatic customer send.
- Required hard denies include AI-review-only trust, irreversible external
  effects, and production mutation.
- No Agent or model identity is a final trust root.
- Unsigned provenance is bounded to local development and blocked authority.
- The canonical layer has no network, subprocess, browser, model, or external
  storage import.

Residual risks:

- P2: digest binding is not signature verification; scheduled for PR 3.
- P2: outcome revocation and trust degradation are absent; scheduled for PR 5.
- External: independent human security review remains pending.

Verdict: **Pass for the declared local deterministic scope**.

## S10 Commercialization And Production Audit

No payment, entitlement, production deployment, customer send, legal
certification, compliance certification, or hosted service is added.

`controlled_customer_handoff` is a bounded protocol scope, not production
approval. `production_candidate` is only an ordered vocabulary value; current
policy and privacy invariants do not authorize production mutation.

Verdict: **Not production ready and not claimed as such**.

## S11-S12 UI And Product Language Audit

There is no UI change. Schema titles and docs use current protocol-first names.
Historical v0 identifiers appear only where necessary for compatibility. The
current language does not present Study Anything as the top-level product or
call local unsigned receipts portable trust.

Verdict: **Pass**.

## S13 Legacy Leakage And Migration Audit

| Legacy surface | Category | Action | Rollback |
| --- | --- | --- | --- |
| `failure-contract-v1` and `sandbox-receipt-v1` | Adapt | Map to policy/evidence | Remove v1 wrapper without touching v0 producers |
| attention reconstruction summary | Adapt | Map to expiring qualified reconstruction | Keep original summary unchanged |
| Dual Loop and Delivery Trust receipts | Adapt | Map to decision and canonical receipt | Existing consumers continue reading v0 |
| Existing script names and platform packs | Preserve | Add v1 assets, do not rename entrypoints | Revert additive manifest entries |
| Historical docs and audits | Preserve | Treat as evidence history | Never rewrite history for current branding |
| Direct v0 deletion | Reject | Requires downstream migration proof and compatibility release | Not attempted |

Fixtures prove equal or narrower authority. An explicit scope-expansion case is
rejected. No destructive migration is present.

Verdict: **Pass**.

## S14 Automated Gate Matrix

| Gate | Result |
| --- | --- |
| Asset generation and freshness | Pass; 6 schemas and 9 fixtures |
| Canonical v1 verifier | Pass; stable bytes, schema, state, safety, and isolation checks |
| v0 compatibility verifier | Pass; 2 equal, 1 narrowed, 0 expanded; explicit expansion rejected |
| Focused contract and release-script tests | Pass; 8 tests |
| Full API suite | Pass; 945 tests, one existing Starlette/httpx deprecation warning |
| Ruff | Pass on full repository |
| Strict mypy on changed protocol paths | New protocol code clean; one pre-existing `study_anything.__init__` `no-any-return` remains outside this phase |
| Generated evidence topology | Pass; 21/21 nodes converged in two refresh passes and one final check pass |
| CBB protocol-only release | Pass; partial receipt, v1 contract gates true, full release false |
| Skip-clean-clone release | Pass with exit 0; receipt keeps full release, clean clone, and dependency install false |
| Protected GitHub checks | Pending PR |
| Independent external security audit | Pending issue #414 |

No failed or skipped gate is represented as completed.

## Acceptance Matrix

| Area | Minimum passing condition | Status |
| --- | --- | --- |
| Contract strictness | Unknown fields and impossible state combinations fail | Pass |
| Canonical bytes | Key order does not change bytes or SHA-256 | Pass |
| Unsafe metadata | Raw, secret-like, attention, prompt, token, and path material rejected | Pass |
| Runtime isolation | Canonical package has no runtime-authority imports | Pass |
| v0 preservation | Existing artifacts remain untouched and mappable | Pass |
| Scope monotonicity | Target scope never exceeds source receipt | Pass |
| Staleness | Expired reconstruction cannot authorize delivery | Pass |
| Release honesty | Partial modes keep full-release claims false | Pass |
| Full repository regression | All API tests and generated topology pass on final tree | Pass |
| External trust claim | Independent auditor returns a commit-bound signed report | Not completed |

## S15 Decision And Next Goal

Merge this phase only after the final API suite, generated topology,
skip-clean-clone release stack, and protected GitHub checks pass. Do not wait
for the external audit to continue internal protocol development, but do not
describe the repository as independently audited.

Next goal, PR 2: implement the deterministic CBB Trust Kernel.

Required PR 2 contract:

1. evaluate `TrustPolicyV1 + EvidenceBundleV1 + QualifiedReconstructionV1`
   into `GateDecisionV1` without model or network calls;
2. enforce hard denies, required evidence, role requirements, scope ordering,
   risk budget, staleness, and claim-boundary monotonicity;
3. route current CBB gate behavior through the canonical kernel while keeping
   v0 wrapper outputs stable;
4. add pass, missing-evidence, stale, hard-deny, risk-budget, role, and
   attempted-scope-expansion fixtures;
5. add `verify_cbb_v1_kernel.py --check` and a dedicated runtime isolation
   verifier;
6. keep signing, outcome degradation, Agentic workflow, and production
   authority out of PR 2.
