# Phase 33 CBB Protocol V1 Trust Kernel Audit

Audit date: 2026-07-10 PDT

Project: deterministic CBB Protocol v1 Trust Kernel and runtime isolation

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.293-cbb-v1-kernel`

Audit base: `211abc81da6103d1f2e34a5834158a082cac23ea`

Preview: none; this phase changes protocol evaluation, compatibility adapters,
release gates, fixtures, and metadata-only verifier receipts.

Auditor: Codex

Authority: `/Users/james/Downloads/通用质检方案.md`, reviewed in S0-S15
order.

## Executive Conclusion

Decision: **Pass locally; protected CI pending**.

The canonical v1 path now has one deterministic decision authority. Trust Policy,
Evidence Bundle, and Qualified Reconstruction produce a claim-bounded Gate
Decision without model, RAG, network, filesystem, subprocess, browser, or legacy
runtime authority. Existing v0 gate output remains compatible.

The audit found and removed one P1 protocol-ordering defect during implementation:
the first compatibility map listed a v0 Delivery Trust Receipt as required evidence
for the gate decision that precedes a canonical delivery receipt. The adapter now
places the v0 Dual Loop decision in the Evidence Bundle, invokes the canonical
kernel, and treats the old delivery receipt only as a compatibility ceiling and
source reference.

The audit also found one P2 failure-state modeling defect: a failed v0 sandbox
could make a valid failure-contract item exceed the bundle ceiling and raise a
schema error. The bundle now retains its sandbox ceiling while the failed required
evidence produces the intended deterministic block decision.

The audit found one additional P1 provenance ambiguity before commit: decision IDs
were initially derived from object identifiers only. The final implementation binds
the canonical SHA-256 of policy, evidence, and reconstruction, so changed content
cannot reuse the same decision ID while retaining the same object IDs.

## S0-S3 Source, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | Clean isolated worktree at `211abc81` |
| Product contract | Pass | Kernel decides release scope; Agentic systems remain evidence/proposal layers |
| Delivery boundary | Pass | Local deterministic decision only; no signing, production, or customer outcome claim |
| No-touch boundary | Pass | `/Users/james/Documents/学习系统` was not modified |
| External checkpoint | Pending | Issue #414 remains unassigned and audit completion remains false |

Included:

- pure canonical policy evaluator and scope ordering;
- typed hard-deny observations, failed/missing/stale evidence handling, reviewer
  role checks, and reference integrity;
- seven deterministic positive and negative kernel fixtures;
- static runtime-isolation verification;
- v0 gate and Dual Loop compatibility routing;
- release receipt, platform pack, and external audit scope integration.

Excluded:

- model calls, RAG, Agentic planning, network or tool execution;
- portable signatures, revocation, outcome receipts, and self-evolution;
- production mutation, automatic customer send, or real customer payloads;
- independent security-audit completion.

## S4-S8 Loop, Data, And Protocol Surface

The implemented loop is:

1. validate canonical policy, evidence, and reconstruction contracts;
2. reject reference ambiguity and duplicate evidence types;
3. apply hard denies before positive evidence;
4. distinguish failed evidence from missing or stale evidence;
5. require scope-qualified active reconstruction and reviewer role evidence;
6. choose the minimum claim-bounded scope;
7. emit one deterministic Gate Decision.

The kernel consumes immutable Pydantic models and returns one immutable model.
It performs no I/O. Evidence type names and source refs remain metadata only.
The `hard_deny:` prefix is fail-closed: a passed signal means the deny condition
was positively observed, and unknown deny identifiers block.

V0 compatibility is one-way. Legacy receipts are translated into canonical
objects, the v1 kernel decides authority, and the adapter renders the unchanged
legacy output format. The canonical decision cannot exceed the old delivery scope.
The dependency-light `--dual-loop-only` mode retains the original v0 evaluator and
explicitly leaves both v1 contract and kernel verifier pass flags false.

## S9 Security And Privacy

| Boundary | Result |
| --- | --- |
| Model/provider SDK imports | Absent from canonical kernel |
| HTTP, socket, browser, subprocess imports | Absent from canonical kernel |
| RAG or Agent framework imports | Absent from canonical kernel |
| Legacy core dependency | Absent from canonical kernel |
| Filesystem reads or writes | Absent from canonical kernel |
| Secret-like/raw payload inclusion | Rejected by canonical contract layer |
| Hard deny precedence | Pass |
| Cross-receipt reference mismatch | Blocks |

Static isolation is not a production sandbox. The independent auditor must still
review package boundaries, dependency behavior, and adversarial inputs at the
pinned commit.

## S10-S13 Production, UI, Copy, And Legacy

- No UI, payment, hosted runtime, deployment, production authorization, or
  customer sending is introduced.
- Existing v0 CLI names, schemas, fixture directories, decisions, and reason
  strings remain supported.
- Protocol documentation now states that the canonical delivery receipt follows
  the gate rather than serving as circular gate evidence.
- All public wording keeps local deterministic proof separate from portable
  signing, production proof, external audit, and real outcome evidence.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| CBB v1 kernel verifier | Pass; seven cases |
| Runtime-isolation verifier | Pass; zero findings |
| Canonical contract and compatibility verifiers | Pass |
| Legacy CBB gate verifier | Pass; output contract preserved |
| Focused kernel tests | Pass |
| Ruff and strict mypy | Pass on changed Python surfaces |
| Generated evidence topology | Pass; 21/21 nodes converged in one refresh pass |
| Full API suite | Pass; 950 tests, one existing Starlette/httpx deprecation warning |
| Partial release check | Pass; exit 0 with full/clean-clone/dependency flags false |
| Protected GitHub checks | Pending PR |
| Independent human audit | Not started |

## S15 Decision

Merge only after generated assets converge, the full API suite passes, the
partial release receipt remains honest, and protected checks pass. After merge,
regenerate and repin issue #414 to the new exact main commit and audit-pack digest
without changing `audit completed: no`.

This audit authorizes the next local protocol milestone only. It is not a signed
security report, production approval, customer outcome proof, or permission for
an Agentic runtime to modify the Trust Kernel.
