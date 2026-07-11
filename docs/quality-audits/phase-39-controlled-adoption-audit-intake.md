# Phase 39 Controlled Adoption And External Audit Intake Audit

Audit date: 2026-07-10 PDT

Project: Delivery Clearance Protocol v1 controlled adoption and signed external
audit-report intake

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.299-controlled-adoption-audit-intake`

Audit base: `1ada8ffa6318b91e38ec69bc5cd14dc294950518`

Auditor: Codex

Authority: operator-provided `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

Decision: **Needs Changes until all local, clean-clone, protected GitHub, and exact
merge-commit evidence is complete.**

The implementation adds two bounded layers above the Protocol v1 conformance pack:

1. controlled shadow, dogfood, and canary adoption receipts that cannot expand the
   source clearance or authorize customer or production delivery; and
2. signed external-audit report intake that separates cryptographic signature
   possession from independently attested auditor identity and keeps audit-ready,
   audit-received, remediation-pending, and audit-closed states distinct.

All repository fixtures are synthetic. They prove deterministic state transitions,
negative cases, integrity bindings, and privacy boundaries only. They do not prove a
real adopter exists, a customer received a delivery, an independent auditor was
assigned, a report was received, issue #414 was completed, or production is safe.

The only allowed post-merge external checkpoint is to present the exact merged audit
pack to a genuinely independent reviewer or adopter and ingest their evidence without
self-certification. No repository-controlled key, fixture, or report can close that
checkpoint.

## S0-S3 Source, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Active source | Pass | Isolated worktree on `codex/v0.3.299-controlled-adoption-audit-intake` |
| No-touch boundary | Pass | Protected historical workspace was not modified |
| Product contract | Pass | Delivery Clearance remains the final protocol before scoped responsibility transfer |
| Included delivery | Pass | Contracts, evaluator, CLIs, fixtures, schemas, verifiers, docs, release gates, audit pack, and platform distribution |
| Excluded delivery | Pass | No production mutation, customer send, model call, external identity creation, self-certification, or audit closure |
| Real adopter evidence | Pending | Verification receipt explicitly records zero real-adopter evidence |
| Independent audit | Pending | GitHub issue #414 remains open and incomplete |

The current implementation is a local-first deterministic reference path. It may say
that a synthetic adoption or audit-intake fixture passed its declared policy. It may
not say that an external organization adopted the protocol or that an independent
security audit ran or passed.

## S4-S8 Loop, Information, Data, And Action Surface

The controlled adoption loop is:

1. bind a case to the exact release commit and conformance-pack digest;
2. select shadow, dogfood, or canary mode without expanding source scope;
3. record a synthetic or externally supplied observation class;
4. replay incident, rollback, revocation, and reopen transitions deterministically;
5. emit a metadata-only receipt that grants no customer or production authority.

The external audit intake loop is:

1. publish an audit-ready envelope bound to the exact commit, audit plan, audit pack,
   and conformance pack;
2. accept a detached Ed25519 signature over canonical report bytes;
3. verify report digest and all evidence bindings;
4. separately verify externally attested auditor identity and independence;
5. reject self-certification, wrong commit, incomplete scope, and invalid signature;
6. keep open critical or high findings in remediation pending;
7. close only after a real external report, independent identity, passing decision,
   closed required findings, and successful retests.

| Surface | Authority boundary |
| --- | --- |
| Adoption fixture | Synthetic protocol behavior only; not real-adopter evidence |
| Shadow/dogfood observation | May observe local behavior; cannot increase delivery scope |
| Canary mode | Cannot authorize customer or production delivery in v1 |
| Adoption receipt | May preserve, narrow, freeze, revoke, or require reopen; never expands authority |
| Detached signature | Proves control of a private key over canonical bytes, not external identity |
| Auditor trust record | Must be independently attested and repository-independent for a real report |
| Audit intake receipt | Records state and blockers; cannot certify the repository |
| External eval | Supporting evidence only; not a substitute for Dual Loop or human audit |

## S9 Security, Privacy, And Permission

| Boundary | Result |
| --- | --- |
| Wrong release commit or pack digest | Rejected |
| Scope expansion beyond source clearance | Rejected |
| Commit supplied only by the untrusted adoption case | Rejected unless it matches the separate expected release commit |
| Production mutation or customer-send claim | Rejected |
| Synthetic fixture claiming real adoption | Rejected |
| External-adopter class without an independent attestation protocol | Blocked and recorded as no real evidence |
| Invalid detached signature or report digest | Rejected |
| Declared fingerprint not matching the actual public key | Rejected |
| Envelope-supplied external identity absent from expected trust roots | Rejected |
| Repository self-certification | Rejected |
| Missing independent identity attestation | Cannot become a real received or closed audit |
| Open critical or high finding | Closure blocked; remediation remains pending |
| Synthetic report requesting closure | Rejected |
| Secret-like metadata | Rejected |
| Raw customer payload, prompts, attention streams, or exploit details | Excluded |

The synthetic fixture key is derived in code for deterministic tests. No private key is
distributed as an artifact. Its signatures demonstrate canonical verification only and
must not be represented as an independent auditor signature.

## S10-S13 Commercial, Production, UI, Copy, And Legacy

- No paid customer flow, hosted service, production operation, or commercial clearance
  is introduced.
- No UI is added. Human-facing evidence remains short documentation and audit-pack
  summaries; machine evidence remains typed JSON and hashes.
- Public identity remains Delivery Clearance / AI Delivery Clearance Protocol, with
  `cbb.*`, `delivery-trust`, and `study-anything` retained only where required for
  technical compatibility.
- Public wording must continue to say: Delivery Clearance does not prove AI is always
  correct; it proves the scoped reasons, recipient, purpose, limits, and responsibility
  under which one delivery may move forward.
- Controlled adoption and audit intake can be removed without weakening the eight
  canonical Protocol v1 contracts or v0 compatibility mappings.

## S14 Automated Evidence

| Gate | Current result |
| --- | --- |
| Generated adoption/audit assets | Pass; 18 schemas and fixtures current |
| Controlled adoption verifier | Pass; seven synthetic state cases plus authority and privacy negatives |
| External audit intake verifier | Pass; seven synthetic intake cases plus signature, identity, scope, remediation, and closure negatives |
| Focused unit tests | Pass; 25 affected tests |
| Ruff and strict mypy | Pass; repository Ruff gate and 16 focused typed source files |
| Positioning verifier | Pass; public identity and non-claim boundaries current |
| External audit pack convergence | Pass; deterministic archive and offline verification current before final document freeze |
| Platform/adoption/topology convergence | Pass; 58-node topology, 67 hard dependencies, and 18 feedback dependencies converged |
| Full API suite | Pass; 998 tests in 69.750 seconds after trust-root hardening |
| Partial release modes | Pass; Dual-Loop-only and CBB-protocol-only receipts remain explicitly partial |
| Full clean-clone release | Pending final rerun |
| Protected GitHub checks | Pending PR |
| Real external adopter evidence | Not present |
| Independent human security audit | Pending issue #414 |

## Gate Matrix

| Rule | Gate | Merge blocking |
| --- | --- | --- |
| Adoption cannot expand source clearance | `verify_cbb_controlled_adoption_outcomes.py --check` | Yes |
| Incident, rollback, revocation, and reopen remain distinct | adoption verifier and fixtures | Yes |
| Audit signature, identity, scope, and report bindings are independent | `verify_cbb_external_audit_intake.py --check` | Yes |
| Synthetic evidence cannot close a real audit | audit-intake verifier negative cases | Yes |
| Critical/high findings prevent closure | audit-intake verifier and remediation policy | Yes |
| New evidence is present in the external audit pack | audit-pack generator and verifier | Yes |
| New evidence reaches platform and adoption distributions | generated evidence topology | Yes |
| Release receipt names the new gates honestly | `release_check.sh` and release-script tests | Yes |

## S15 Decision

Do not merge until all final local and clean-clone gates pass and protected GitHub
checks are green. After merge, regenerate and repin issue #414 to the exact merge
commit, audit-pack digest, and conformance-pack digest while preserving:

- `external_auditor_assigned: false` unless a real auditor is actually assigned;
- `external_signed_report_received: false` until a real signed report is received;
- `audit_completed: false` and `audit_closure_accepted: false` until independent
  evidence and remediation criteria genuinely close the audit.

This phase authorizes only a controlled external evidence request. It does not
authorize production delivery, customer outcome claims, external adoption claims,
self-certification, or automatic trust expansion.
