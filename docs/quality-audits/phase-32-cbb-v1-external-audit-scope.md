# Phase 32 CBB V1 External Audit Scope Audit

Audit date: 2026-07-10 PDT

Project: bind canonical CBB Protocol v1 evidence into the independent external
security audit preparation pack

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.292-cbb-v1-audit-scope`

Audit base: `0e76efcc95e1ffe6f256f2337b2f87a522f60d63`

Preview: none; this phase changes audit scope, package contents, deterministic
verification, and generated metadata-only artifacts.

Auditor: Codex

Authority: `/Users/james/Downloads/通用质检方案.md`, reviewed in S0-S15
order.

## Executive Conclusion

Decision: **Pass locally; protected CI pending**.

The external audit preparation pack now covers the canonical CBB Protocol v1
contract layer merged in PR #418. The update does not claim that an independent
audit ran or passed. It keeps source review bound to the exact repository commit
and adds privacy-safe schemas, fixtures, verifier receipts, and protocol docs to
the downloadable pack.

## S0-S3 Source, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | Clean `main` at `0e76efcc` in an isolated worktree |
| Delivery boundary | Pass | Audit preparation only; no signed external report or certification |
| Product contract | Pass | New top-level CBB v1 contracts are now explicit audit evidence |
| No-touch boundary | Pass | `/Users/james/Documents/学习系统` was not modified |
| External checkpoint | Pending | Issue #414 still has no assigned independent human auditor |

Included:

- two canonical CBB v1 verifier commands in the Dual Loop and Delivery Trust
  scope;
- six canonical schemas and nine public negative/positive fixtures;
- canonical contract and v0 compatibility verifier receipts;
- protocol and v1 contract documentation;
- Phase 31 as a pinned-repository evidence asset.

Excluded:

- Python source code from the metadata-only ZIP;
- the Phase 31 audit file from the ZIP because it contains local source-of-truth
  paths;
- raw payloads, secrets, logs, exploit details, production evidence, and audit
  findings;
- any claim that the audit has started, completed, or passed.

## S4-S8 Loop, Data, And Protocol Surface

The auditor loop is:

1. verify the ZIP against its published SHA-256;
2. check out the exact scope commit;
3. inspect the seven audit areas and their evidence commands;
4. run both CBB v1 contract and v0 compatibility verifiers;
5. inspect schemas, fixtures, receipts, and source at the pinned commit;
6. perform independent negative testing;
7. return schema-valid findings and a signed human-led report.

The pack manifest now requires every CBB v1 privacy-safe asset. The audit plan
requires the same assets plus Phase 31 from the repository checkout. This split
prevents local paths from entering the public ZIP while keeping the audit trail
available to the reviewer.

No Agent, model, self-review, CI job, or repository maintainer can set
`audit_completed=true`. The existing independent report schema and human
signature requirement remain authoritative.

## S9 Security And Privacy

| Boundary | Result |
| --- | --- |
| Single safe archive root | Pass |
| Offline file and archive digest verification | Pass |
| Local absolute path rejection | Pass; first build correctly blocked Phase 31 from ZIP |
| Secret-like material rejection | Pass |
| Metadata-only evidence | Pass |
| Raw source and learner data excluded | Pass |
| Production mutation and network calls | Not performed |
| Self-certified audit status | Rejected |

The generated package contains 46 declared source/evidence files and 48 ZIP
entries. Its SHA-256 is generated deterministically and must be repinned in
issue #414 only after this change merges.

## S10-S13 Production, UI, Copy, And Legacy

- No UI, payment, hosted runtime, deployment, production authorization, or
  customer send is added.
- Existing seven audit scope IDs remain stable; the CBB v1 evidence extends the
  existing `dual_loop_and_delivery_trust` scope.
- Historical Dual Loop evidence is preserved alongside canonical v1 evidence.
- The pack remains titled as an audit preparation pack, not a certificate.
- Issue #414 must retain `audit completed: no` and `external auditor unassigned`.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| External audit pack generator/check | Pass |
| External audit pack verifier | Pass; 46 files, 48 entries |
| Focused audit-pack tests | Pass; 4 tests |
| Ruff | Pass on changed Python surfaces |
| Strict mypy | Pass on generator and verifier |
| Generated evidence topology | Pass; 21/21 nodes converged in one refresh pass and one final check |
| Full API suite | Pass; 945 tests, one existing Starlette/httpx deprecation warning |
| Protected GitHub checks | Pending PR |
| Independent human audit | Not started |

## S15 Decision

Merge only after the generated evidence topology, full API suite, and protected
GitHub checks pass. After merge, update issue #414 with the new main commit,
package SHA-256, scanner ledger, and the unchanged statement that no independent
audit has completed.

This governance repair does not change the next implementation milestone: PR 2
remains the deterministic CBB Trust Kernel and runtime-isolation gate.
