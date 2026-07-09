# Phase 14 Contract-First Quality Audit

Date: 2026-07-09

Project: Study Anything / Cognitive Black Box

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.274-scheduled-reliability-matrix`

Audit base: `532f91024d6deda65098f344cfe6ae1308c5962a`

Preview: Not applicable; this delivery is CLI, API, Compose, and GitHub Actions infrastructure.

Auditor: Codex using `通用质检方案.md`

## 1. Executive Conclusion

Decision: **Needs Changes** for commercial production launch.

Phase 14 delivery decision: **Pass**.

The source-build and published-image reliability matrix matches the current local-first OSS contract,
passes deterministic and real Docker checks, and is integrated into CI, release validation, docs, and
generated distribution evidence. It does not make the product commercially production-ready.

Maximum risks:

1. The default two-hour GitHub schedule has not yet produced retained passing artifacts. Local runs
   were intentionally short diagnostic windows.
2. Hosted identity, tenant isolation, billing, entitlement, support operations, and production SLOs
   remain explicitly unimplemented.
3. One passing scheduled window will still be bounded evidence; repeated runs, alerting, and incident
   response are required before an availability claim.

Next required actions:

1. Merge the workflow, run a short manual GitHub dispatch for both modes, and inspect both receipts.
2. Let the default two-hour schedule complete with strict thresholds and retain both passing receipts.
3. Accumulate repeated scheduled evidence before defining any external reliability commitment.

Do not:

1. Claim a two-hour pass from the short local runs.
2. Present `full_release_check.sh` as proof of a production SLO or commercial hosted readiness.
3. Reintroduce a standalone frontend or model-key custody to solve an operational evidence gap.

## 2. Delivery Boundary

| Category | Items | Evidence | Risk |
|---|---|---|---|
| Included | Source-build and published-image Compose runner, controlled API restart, post-failure health recovery, pre-restart session recovery, scheduled workflow, metadata-only receipt | Focused verifier, real Docker runs, CI and release gates | Low |
| Excluded | Hosted service, production mutation, model calls, customer traffic, SLO, incident response, disaster-recovery certification | Receipt claim boundary and docs | None if wording remains explicit |
| Claimed but unproven | Default two-hour scheduled reliability | Workflow exists, but no default-duration GitHub artifact exists yet | P1 |
| Leaking into product | None found; workflow remains operator infrastructure | No standalone UI or public mutation surface added | Low |

Verdict: **Pass for Phase 14 implementation; Needs Changes before external reliability claims.**

## 3. Source Of Truth

| Area | Current truth | Risk |
|---|---|---|
| Active repo | Authoritative GitHub-aligned worktree for `jzvcpe-goat/study-anything` | Low |
| Active branch | `codex/v0.3.274-scheduled-reliability-matrix` | Low |
| Audit base | `532f91024d6deda65098f344cfe6ae1308c5962a` | Delivery changes are intentionally uncommitted during audit |
| Main | Base contains merged PR #397 self-intake | Low |
| Preview | None required; no standalone frontend is part of this scope | Low |
| Dirty changes | Phase 14 source, docs, tests, workflow, and generated evidence only | Must be reviewed and committed atomically |
| Deprecated mirror | The separate `学习系统` workspace was not modified | Low |

## 4. Product Contract

Claimed product: a local-first AI delivery-trust and learning control layer. The Cognitive Black Box
core controls failure, reconstruction, evidence, and promotion. Study Anything remains the learning
adapter and platform-Agent surface.

Actual implemented product: local API and CLI runtimes, Postgres-backed learning state, user-owned
Agent integration, deterministic Dual Loop/CBB harnesses, metadata-only evidence, platform packs,
and self-host deployment tooling.

Intended operator loop:

1. Run the local or private runtime.
2. Let a user-owned platform Agent perform model/tool work.
3. Persist learning/control state locally.
4. Verify evidence and risk gates.
5. Promote only after both machine and human control contracts pass.

Phase 14 extends that loop by proving that both source and published runtimes can survive one
controlled API restart without losing the learning session created before the fault.

Contract mismatch: none in the Phase 14 scope. Commercial hosted readiness remains outside the
current contract and must not be inferred from OSS Alpha readiness.

## 5. What Works And Should Be Preserved

| Area | Evidence | Why preserve |
|---|---|---|
| Equal runtime paths | `source-build` and `published-image` use the same flow, fault, and recovery thresholds | Prevents source-only confidence |
| Real failure | API container is stopped and started through isolated Compose | Avoids simulated recovery claims |
| State recovery | Mastery for the pre-restart session is read after recovery | Stronger than health-only proof |
| Provenance | Source commit/dirty state or pulled image digest is recorded | Makes receipts attributable |
| Privacy | No URL, image repository, project name, env path, logs, output, secrets, source, or answers in receipts | Matches metadata-only contract |
| Isolation | Unique Compose project, random ports, disposable volumes, cleanup on completion | Prevents propagation to operator data |
| Honest claims | Short, relaxed, and two-hour windows are distinguished | Prevents evidence inflation |
| Release enforcement | Deterministic verifier runs in CI and full release check | Prevents silent contract regression |

## 6. Major Gaps

| Severity | Area | Current | Required | Impact |
|---|---|---|---|---|
| P0 | Commercial hosted launch | Explicitly `not_ready`; no tenant identity, billing, entitlement, or production support | Separate hosted architecture and commercial acceptance program | Cannot sell a hosted service yet |
| P1 | Scheduled evidence | Workflow contract exists; only short local runs completed | Passing strict two-hour GitHub artifacts for both modes | No multi-hour reliability claim yet |
| P1 | Production operations | Optional observability and local diagnostics exist | Alerts, incident response, SLO policy, repeated restore drills | No production availability promise |
| P2 | Evidence retention | GitHub artifacts retained for 14 days | Longitudinal aggregate or signed release evidence archive | Weak trend analysis over time |
| P3 | Dependency maintenance | Full tests emit a Starlette/httpx deprecation warning | Planned dependency migration | Future compatibility risk only |

## 7. Data And Local-First Audit

| Object | Current storage | Ownership | Recovery | Gap |
|---|---|---|---|---|
| Learning session | Canonical local Postgres | Local operator | Backup/restore tooling and restart read proof | Multi-host sync is future work |
| Reliability receipt | Local private JSON or GitHub artifact | Local operator / repository maintainer | Regenerated per run | No long-term aggregate yet |
| Cognitive Loop evidence | `.cognitive-loop` metadata artifacts and local stores | Local operator | Verifiers, repair plan, bundles | Hosted custody is not implemented |
| Platform distribution | Generated ZIP/JSON/SHA256 assets | OSS release maintainer | Evidence topology refresh | Marketplace operation is external |
| Published runtime | GHCR multi-architecture image | OSS release maintainer | Immutable digest recorded in receipt | Repeated schedule evidence pending |

The real Docker checks left no Compose projects or test volumes running. Receipt files were created
with `0600` permissions. No migration or canonical data mutation was introduced by this phase.

## 8. Protocol And Agent Action Surface

The existing platform contract exposes 34 bounded OpenAPI tools and keeps real model credentials in
the user-owned Agent. High-risk Cognitive Loop decisions require structured artifacts and human gates.
The reliability matrix is an operator-only CLI/workflow, not an externally callable production
mutation API.

| Action | Surface | Risk | Confirmation | Test |
|---|---|---|---|---|
| Run isolated reliability window | CLI / GitHub workflow | Medium | Explicit command or manual dispatch | Deterministic verifier plus real Docker |
| Stop/start disposable API | Private Compose project | Medium | Part of explicit reliability run | Recovery must be observed |
| Read pre-restart mastery | Local API GET | Low | No | Session recovery gate |
| Upload receipt | GitHub artifact | Low | Workflow scope | Metadata-only verifier |

Verdict: **Pass** for the Phase 14 action surface.

## 9. Security, Privacy, And Permissions

| Resource | Current permission | Required | Risk |
|---|---|---|---|
| Local API | Loopback by default; token required for network/production mode | Preserve | Low |
| Compose project | Unique disposable project and volumes | Preserve | Low |
| GHCR image | Read-only pull in scheduled workflow | Preserve least privilege | Low |
| Reliability receipt | Metadata only, local `0600`, 14-day artifact retention | Add long-term aggregate without raw logs | P2 |
| Model credentials | Not stored or used by the matrix | Preserve | Low |
| Production data | Never mounted or mutated | Preserve | Low |

The workflow permissions are read-only for repository contents and packages. Failures remain blocking;
there is no `continue-on-error`. Failed jobs still attempt to upload the classified receipt.

## 10. Payment And Production Audit

Payment and entitlement are intentionally absent from the free OSS core. This is not a defect for the
current Alpha, but it is a P0 prerequisite for any paid hosted offering.

| Area | Current | Required for commercial hosted launch | Status |
|---|---|---|---|
| Deployment | Source build, published image, Skill Mode | Staging/production separation and controlled promotion | Partial |
| Monitoring | Health, diagnostics, optional Langfuse | Alerts, on-call policy, privacy retention enforcement | Missing |
| Backup | Local Postgres backup/restore and disposable drill | Scheduled backups and mode-specific repeated drills | Partial |
| Rollback | Container restart and explicit data restore | Version rollback plus migration rollback policy | Partial |
| Payment | Not implemented | Provider, signed idempotent webhook, orders | Missing |
| Entitlement | Not implemented | Durable grants, refunds, recovery | Missing |

Overall production verdict: **Needs Changes**.

## 11. UI, IA, And Product Copy Audit

No standalone frontend exists in the current product contract. The primary interface is natural
language through Codex, Kimi, WorkBuddy, Hermes, or another platform Agent, backed by local CLI/API
tools. Therefore atomic visual component and screenshot audits are not applicable to this phase.

Operator docs necessarily use engineering terms such as Compose, digest, threshold, and receipt.
Those terms do not leak into a consumer UI. The docs consistently distinguish short diagnostics,
scheduled evidence, and production claims.

## 12. Legacy Leakage Audit

| File or concept | Category | Action | Gate |
|---|---|---|---|
| Study Anything learning workflow | Preserve | Keep as the learning adapter | Existing learning and platform gates |
| Cognitive Loop / CBB trust contracts | Preserve | Keep as product core | Dual Loop and CBB gates |
| Standalone frontend | Delete/preserve absence | Do not reintroduce without a new product contract | `no_frontend_required` evidence |
| Direct model-key custody | Delete/preserve absence | Keep credentials in user-owned Agents | Privacy verifiers |
| Short soak as reliability claim | Deprecate as claim source | Use only for diagnostics | Receipt claim boundary |

No new legacy route, page, CSS, browser automation, or direct production write path was introduced.

## 13. Automated Gate Matrix

| Rule | Script/workflow | Blocks merge or job | Evidence |
|---|---|---|---|
| Soak aggregation and required recovery | `verify_self_host_soak.py --check` | Yes | CI and release check |
| Matrix receipt, provenance, privacy, and workflow contract | `verify_self_host_reliability_matrix.py --check` | Yes | CI and release check |
| Real source-build window | `self_host_reliability_matrix.py --mode source-build` | Scheduled job | Source receipt |
| Real published-image window | `self_host_reliability_matrix.py --mode published-image` | Scheduled job | Image receipt |
| Distribution evidence consistency | `generated_evidence_topology.py --check` | Yes | 19/19 nodes current |
| Full repository release | `release_check.sh` | Yes | Full receipt completed |

## 14. Acceptance Matrix

| Area | Minimum passing condition | Result |
|---|---|---|
| Contract | Both modes, real elapsed time, real restart, required recovery | Pass |
| Data | Pre-restart learning session remains readable | Pass |
| Provenance | Source commit/dirty bit or image digest recorded | Pass |
| Privacy | Receipt excludes endpoints, paths, logs, secrets, source, answers | Pass |
| Isolation | No production mutation; disposable project removed | Pass |
| Deterministic tests | Focused lint, verifier, and unit tests pass | Pass |
| Real Docker | Short source and published windows pass | Pass, diagnostic only |
| Full release | Clean clone, dependency install, all gates, 852 tests | Pass |
| Scheduled strict window | Two-hour receipts for both modes | Pending external GitHub run |
| Commercial launch | Identity, billing, entitlement, SLO, incident response | Not ready |

## 15. Verification Evidence

- Full `release_check.sh`: completed; clean clone and dependency installation completed; 852 tests
  passed; Dual-Loop verifiers integrated and passed; `known_issue=none`.
- Generated evidence topology: 19 nodes, 24 hard dependencies, 18 feedback dependencies, converged
  and current.
- Source-build diagnostic: 14 real samples, 3 controlled unavailable probes, recovery observed,
  pre-restart session recovered, source revision recorded, dirty development worktree disclosed.
- Published-image diagnostic: 14 real samples, 3 controlled unavailable probes, recovery observed,
  pre-restart session recovered, pulled image digest recorded, image repository excluded.
- Cleanup: no Compose projects remained after the real runs.

## 16. Bottom Line

Phase 14 is ready for PR review and merge. The repository now has an honest, reproducible scheduled
reliability mechanism, but the first strict two-hour GitHub evidence and the larger hosted commercial
operations program remain required before stronger launch claims.
