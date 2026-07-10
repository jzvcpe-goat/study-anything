# Phase 23 Project Quality Audit

Audit date: 2026-07-09 PDT

Scope: repository security scan, confirmed-finding remediation, generated evidence convergence,
and post-development Contract-First Product Audit.

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

- Phase 23 branch: **Pass for PR after the partial release receipt and protected CI pass**.
- Local-first OSS alpha: **Pass with documented limitations**.
- Hosted or commercial production launch: **Needs Changes**.
- Repository security claim: **partial validated scan, not exhaustive and not an external audit**.

The pinned scan target produced 15 validated findings: 3 high, 11 medium, and 1 low. Fourteen
have concrete remediations on this branch. The remaining P1 is a cross-platform, hash-bound Python
dependency lock for Docker and clean-clone installation.

## S0-S3 Source, Truth, And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical repository | Pass | Latest clean `main` base `ffdbff73`; remediation isolated on `codex/v0.3.283-qc-security-remediation` |
| Product contract | Pass | Local-first Cognitive Black Box / Dual Loop trust harness; Study Anything is the learning adapter |
| Model-key boundary | Pass | Bring Your Own Agent remains authoritative; no real model key enters Study Anything |
| Security scan boundary | Needs Changes | 554 ranked rows and 65-row deep-review worklist; 15 full-file worker receipts plus parent review; remaining workers were blocked by platform filters |
| Release claim boundary | Pass | Clean `main` completed the full release check; this branch completed `--skip-clean-clone`, while its clean-clone install remains unproven locally |

## S4-S9 Functionality, Data, Protocol, Security, And Privacy

| Area | Result | Change |
| --- | --- | --- |
| Plugin lifecycle | Pass | Filesystem-safe ids, resolved-root confinement, destination/source symlink rejection, destructive regression tests |
| HTTP Agent | Pass | Secret-like URL components rejected, invalid ports rejected, response body limited to 1 MiB |
| Sync package | Pass | Imported PBKDF2 work factor has a supported upper bound before key derivation |
| Cognitive Loop Event Store | Pass | Conflicting event ids fail closed and roll back; identical rebuild remains idempotent |
| PR CI receipt | Pass | Offline schema fixes check identity/order and binds `ready` to two passing checks with no reasons |
| Release cleanroom | Pass | Download and ZIP work bounded; self-hash no longer overclaims trusted asset verification |
| Docker core/full | Pass for local alpha | Python base image digest pinned; Langfuse and MinIO host ports loopback-only; MinIO password has no fallback default |
| Python dependency supply chain | Needs Changes | Known vulnerable `langsmith` range excluded, but full dependency installation is not yet hash locked |
| Privacy | Pass | New receipts and generated packs remain metadata-only; no source, answers, endpoint secrets, or model keys added |

The user-owned HTTP Agent endpoint remains operator-selected in the current single-operator model.
Before hosted or multi-user operation, destination and redirect policy must become an explicit
allowlist; current local flexibility is not a hosted SSRF boundary.

## S10-S13 Production, UI, Copy, And Legacy

- Production: hosted identity, tenant authorization, billing/entitlement, incident response,
  operational SLOs, deletion/retention policy, and external penetration testing are not complete.
- Reliability: one strict two-hour source-build/published-image dual pass exists; this is not a
  longitudinal SLO. Two additional independent strict passes are still required for trend claims.
- UI: not applicable to this phase. The supported launch surfaces remain platform Agent packs,
  CLI/Skill Mode, HTTP tools, and static metadata artifacts.
- Copy: docs now distinguish trusted digest verification from self-hashing and local alpha from
  hosted production.
- Legacy: Study Anything naming and `/v1` APIs remain adapter compatibility surfaces, not the
  Cognitive Black Box product core.
- Release: the latest public GitHub release remains `v0.3.31-alpha`; main contains later work that
  is not yet represented by a new tagged release.

## S14 Automated Gates

| Gate | Result |
| --- | --- |
| Focused security and contract tests | Pass; 54 security tests and 61 final release/adoption/container regressions |
| Full API suite | Pass; 893 tests, one existing Starlette/httpx deprecation warning |
| Container security and full-profile Compose config | Pass |
| Generated evidence topology | Pass; final check confirmed 19/19 nodes in one pass |
| Ecosystem submission pack | Pass |
| External adoption replay | Pass with the pre-provisioned full environment in 17.761 seconds; isolated dependency install was stopped after 2 minutes 24 seconds without progress |
| Branch `release_check.sh --skip-clean-clone` | Pass; receipt status `completed`, exit code 0, all integrated trust gates passed |
| Full branch `release_check.sh` | Not completed; an earlier run installed dependencies then found the now-fixed event-id conflict, while the final retry was stopped during the clean-clone pip install |
| GitHub protected checks | Pending PR |

## S15 Findings And Decision

Phase 23 may merge only after protected GitHub checks independently validate installation and the
changed surfaces. The branch receipt is intentionally partial: it proves the existing release gates,
Dual Loop gates, and adoption replay while explicitly not claiming clean-clone completion. The
security fixes are regression-tested and distribution evidence is converged. The formal scan is useful
but partial because platform filters prevented the remaining full-file workers from closing all 65
deep-review rows.

The product is not commercially production-ready. The next independent goal is Python dependency
lock/hashes plus repeatable SBOM/advisory verification, followed by hosted identity/tenancy and an
external security review before any paid hosted service claim.

Do not call this vulnerability-free, exhaustive, hosted-production-ready, or a commercial launch.
