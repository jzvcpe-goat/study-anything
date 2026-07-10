# Project Quality Audit: Phase 19 Security Baseline

Date: 2026-07-09 PDT
Project: Cognitive Black Box / Study Anything
Repo: `jzvcpe-goat/study-anything`
Branch: `codex/v0.3.279-security-baseline`
Base commit: `93f0b8652628bc4569c3ffc18a094160a63ac638`
Preview: not applicable; this phase changes repository and container controls
Auditor: Codex, using `通用质检方案.md`

## 1. Executive Conclusion

Decision: **Pass for Phase 19 merge; whole product Needs Changes**

The Phase 19 implementation is internally consistent and passes a full clean-clone release check,
all six required checks pass on final head `bb9d49bd`, and live repository settings pass 13/13
read-only checks. The whole product is still an OSS/local-first alpha, not a hosted commercial
service.

Largest remaining risks:

1. The strict two-hour source-build/published-image reliability run is still in progress and cannot be claimed.
2. A threat-led repository scan, image/SBOM review, and independent audit remain outstanding.
3. The optional full profile still needs separate third-party image and service-hardening review.

Next required actions:

1. Merge the final green Phase 19 head without weakening branch protection.
2. Validate both strict-reliability artifacts after the two-hour run finishes.
3. Run and triage an independent threat-led security scan as a separate acceptance track.

Do not:

1. Call this a hosted-production or vulnerability-free release.
2. Treat deterministic posture checks as proof of live GitHub settings.
3. Treat one strict reliability run as a production SLO or longitudinal trend.

## 2. Delivery Boundary

| Category | Items | Evidence | Risk |
|---|---|---|---|
| Included | Non-root API image, read-only application containers, dropped capabilities, hardened tmpfs | Dockerfile, Compose, runtime inspect smoke | Low after remote CI |
| Included | Full-SHA Action references, CodeQL, dependency review, container policy | Final head passed all six required checks | Low |
| Included | Read-only live GitHub posture verifier | Live 13/13 checks pass | Low |
| Excluded | Hosted identity, tenant isolation, billing, payments, SSO | Commercial readiness contract | P0 for hosted commercialization, outside this phase |
| Excluded | Independent penetration test and external audit | Security claim boundary | P1 before hosted production |
| Claimed but unproven | Strict two-hour dual-path reliability run | GitHub run `29060766261` is in progress | P1 before reliability acceptance |

Verdict: **Pass for the Phase 19 merge; Needs Changes for whole-product production readiness**.

## 3. Source of Truth

| Area | Current truth | Risk |
|---|---|---|
| Active repo | `/Users/james/Documents/study-anything-cognitive-loop-positioning-pivot` | None |
| Active branch | `codex/v0.3.279-security-baseline` | Unmerged |
| Base commit | `93f0b8652628bc4569c3ffc18a094160a63ac638` | Working changes not yet remote |
| Release receipt | `.cognitive-loop/artifacts/release/release-check-receipt.json` | Local-only metadata receipt |
| Deprecated workspace | `/Users/james/Documents/学习系统` | Must not be used as release truth |

## 4. Product Contract

The public product contract is a local-first Cognitive Black Box / Dual Loop Trust Harness that
controls AI failure, requires active human reconstruction, and emits metadata-only evidence. Study
Anything remains the learning adapter and platform-distribution compatibility surface.

This phase does not change that contract. It reduces runtime privilege and CI supply-chain drift
without introducing model keys, hosted accounts, production mutation, or a standalone frontend.

## 5. What Works / Preserve

| Area | Evidence | Why preserve |
|---|---|---|
| Claim boundaries | Security docs distinguish baseline, live settings, and independent audit | Prevents local proof from becoming a production claim |
| Runtime isolation | UID/GID `10001:10001`, read-only root, `cap_drop: ALL`, `no-new-privileges` | Reduces container blast radius |
| Workflow reproducibility | 29 Action references across 6 repository/distribution workflows use full SHAs | Prevents mutable tag drift |
| Negative testing | Root user, writable root, missing tmpfs flags, force pushes, missing Dependabot, and unpinned Actions are rejected | Makes controls regression-resistant |
| Dependency remediation | `js-yaml` is forced to patched `3.15.0`; npm audit has no moderate/high/critical findings | Removes the fixable Dependabot alert |
| Release integration | Full clean-clone release check completed with 874 tests | Covers current working tree, not a partial mode |
| Evidence topology | 19/19 release-distribution nodes converged | Keeps generated packs synchronized |

## 6. Major Gaps

| Severity | Area | Current | Required | Impact |
|---|---|---|---|---|
| P1 | Reliability acceptance | Strict run still in progress | Both paths complete and metadata receipts validate | No strict-run claim yet |
| P1 | Independent security | No threat-led full scan or external audit | Scan, triage, remediation, independent review | No vulnerability-free or hosted-production claim |
| P2 | Third-party full profile | API and mock are hardened; Postgres/FalkorDB/Langfuse dependencies are not covered by this policy | Separate image/SBOM and service-hardening review | Optional full profile has broader risk |
| P2 | Unpatched transitive AI SDK alert | Mastra pins affected `@ai-sdk/provider-utils` v3 and upstream has no patched v3 release | Track upstream; current runtime performs no external model calls | Low-severity residual risk |
| P2 | Dependency warning | Starlette TestClient emits an `httpx` deprecation warning | Planned compatibility upgrade with regression tests | Future test-environment break risk |
| P2 | Release UX | Clean-clone install has long silent intervals inside a bounded timeout | Periodic progress heartbeat without leaking pip output | Operators may mistake progress for a hang |

## 7. Data Architecture Audit

No product schema changes are introduced. `/data/study-anything` remains the application data
volume and Postgres remains the workflow source of truth. The container identity owns only the
application data and home directories. Backup, restore, tamper detection, and session recovery
gates remain green; this phase does not claim hosted multi-tenant deletion or retention guarantees.

## 8. Protocol / Integration Audit

The Agent boundary remains Bring Your Own Agent. No model credential enters the image, Compose,
workflow, generated packs, or security receipts. The GitHub live verifier invokes only read-only
`gh api` calls and emits booleans plus required check names, not raw API payloads or tokens.

## 9. Security / Privacy Audit

| Resource | Current permission | Required permission | Risk |
|---|---|---|---|
| API container | Fixed non-root user; writable data volume only | Preserve and verify at runtime | Low |
| Mock Agent container | Fixed non-root user; read-only root | Preserve | Low |
| GitHub workflows | Read-only by default; CodeQL gets scoped `security-events: write` | Preserve least privilege | Low after CI |
| Model credentials | Owned by external/user Agent; not stored | Preserve | Low |
| Generated evidence | Metadata-only, no logs or raw API payloads | Preserve | Low |
| Hosted user data | Not implemented | Identity, ACL/RLS, retention and deletion before hosted service | P0 for future hosted scope |

## 10. Payment / Production Audit

Payments and entitlements are intentionally absent and must not be implied. Production monitoring,
incident response, hosted backup, tenant recovery, and paid-service billing remain future work. The
current passing claim is limited to the GitHub OSS/local-first platform alpha.

## 11. UI / Design System Audit

Not applicable to this phase. The current product path explicitly does not ship a standalone Web
UI; platform Agents, CLI, Skill Mode, and static metadata artifacts remain the supported surfaces.

## 12. Legacy Leakage Audit

The Study Anything name and API namespace remain compatibility surfaces, not accidental product
reversion. The distributed Review Agent workflow was upgraded from mutable version tags to pinned
SHAs. The intentionally unsafe workflow fixture remains unpinned as a negative test and is not a
shippable workflow.

## 13. Gate Matrix

| Rule | Script / job | Blocks merge? | Evidence |
|---|---|---:|---|
| Container source policy | `verify_container_security.py --check` | Yes | Local pass, CI wired |
| Runtime container policy | `verify_container_security.py --runtime-container-id ...` | Yes for this phase | Real disposable container pass |
| GitHub posture contract | `verify_github_security_posture.py --check` | Yes | 4 focused posture tests and deterministic gate pass |
| Live GitHub posture | `verify_github_security_posture.py --live ...` | Yes before phase completion | Pass, 13/13 settings |
| Code scanning | `codeql (python)` and `CodeQL` | Yes | Final head passed both checks |
| Dependency changes | `dependency review` | Yes | Final head passed after enabling Dependency Graph |
| Existing API/Compose gates | `api-tests`, `compose-smoke` | Yes | Final head and local full release passed |
| Distribution consistency | `generated_evidence_topology.py --check` | Yes | 19/19 converged |
| Full release | `./scripts/release_check.sh` | Yes | Completed, 874 tests, clean clone included |

## 14. Migration And Rollback

The image change requires no data migration. A rollback uses the previous API image/commit; the
named data and Postgres volumes remain unchanged. If a third-party plugin unexpectedly writes to
the image filesystem, Compose now fails closed instead of silently persisting that write. Such a
plugin must be corrected to use `/data/study-anything`, not granted a writable root filesystem.

## 15. Acceptance Matrix

| Area | Minimum passing condition | Current |
|---|---|---|
| Container | Non-root and least-privilege source plus runtime checks pass | Pass |
| Workflow supply chain | All shipped Action references use full SHAs | Pass |
| Local release | Full clean-clone release receipt completed | Pass |
| Remote CI | Old and new required jobs pass on the final PR head | Pass, 6/6 on `bb9d49bd` |
| Repository settings | Read-only live posture report passes | Pass, 13/13 checks |
| Reliability | Strict two-hour dual-path artifacts validate | In progress |
| Hosted production | Identity, tenancy, SLO, incidents, payment, external audit | Out of scope / not ready |

## 16. Bottom Line

The Phase 19 security baseline, live repository settings, local full release, and final-head CI are
ready to merge. This does not make the whole product commercially production-ready. Strict
reliability, third-party full-profile hardening, and independent security remain separate acceptance
tracks with no passing claim yet.
