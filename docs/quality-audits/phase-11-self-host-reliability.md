# Phase 11 Project Quality Audit

Audit date: 2026-07-09

Scope: Self-host reliability and recovery proof on
`codex/v0.3.271-self-host-reliability-recovery-proof`.

Authority: `通用质检方案.md` (Contract-First Product Audit Framework), reviewed in S0-S15 order.

## Executive Conclusion

- Phase 11 delivery: **Pass**.
- Whole-product commercial production launch: **Needs Changes**.
- Claim boundary: this phase proves a deterministic metadata-only reliability harness, one short real
  Docker health window, and a real isolated backup/restore rollback. It does not prove a multi-hour
  production SLO, disaster recovery across arbitrary hosts, hosted tenancy, billing, or community PMF.

## S0-S3 Direction And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Materials complete | Pass | Implementation, tests, verifier, operator guide, CI, release gate, Docker receipt |
| Source of truth | Pass | Postgres remains canonical; soak receipts contain operational metadata only |
| Delivery boundary | Pass | Local self-host operator, API/Skill/platform-Agent distribution, no standalone UI claim |
| Product contract | Pass for phase | Bounded health evidence and reversible recovery guidance match the implementation |

The implemented loop is: launch local runtime -> sample health -> emit a private metadata-only receipt
-> diagnose without mutation -> back up -> restart or explicitly restore -> verify again. The receipt is
evidence about one window, not a promise about correctness or production availability.

## S4-S8 Implementation, User Loop, Data, And Agent Surface

- The CLI validates schemes, hosts, thresholds, sample counts, timeouts, and explicit network-token
  consent before probing.
- Redirects are rejected so bearer authorization cannot be forwarded to another origin.
- Health bodies, endpoint URLs, tokens, Docker logs, source text, answers, Agent metadata, and local
  paths are excluded from receipts. Receipt files use mode `0600`.
- The launcher identifies Postgres credential drift and stops with a non-destructive recovery order. It
  does not delete volumes or regenerate credentials automatically.
- The beginner path and failure path are documented in five ordered steps.
- The canonical application data stays in Postgres. Reliability receipts are derived evidence and can
  be recreated.
- There is no new model call, browser automation, production mutation, or remote restore action.
- UI and information-architecture review are not applicable to this phase because the accepted product
  surface is CLI/API/Skill/platform-Agent. This is not approval of a future standalone application UI.

## S9 Security And Privacy

Result: **Pass for the implemented local-first boundary**.

Verified controls:

- loopback defaults and explicit confirmation before sending a local token to a network host;
- redirect rejection for authenticated health probes;
- metadata-only receipts and local-user-only output permissions;
- no destructive automatic volume recovery;
- focused secret, absolute-path, and destructive-command scans;
- deterministic privacy assertions in unit and verifier coverage.

Residual boundary: no independent penetration test or exhaustive external security audit was performed.

## S10 Commercial And Production Readiness

Result: **Needs Changes for a hosted commercial launch**.

| Severity | Gap | Why it matters | Acceptance evidence |
| --- | --- | --- | --- |
| P0 | No hosted identity or tenant isolation | A paid multi-user service cannot safely separate customers | Threat model, tenant tests, authorization matrix, isolation test receipts |
| P0 | No billing, entitlement, or support operations | There is no paid-service commercial loop | Sandbox payment flow, idempotent webhooks, entitlement tests, refund/support runbook |
| P0 | Hosted Sync/Teams are planned, not shipped | Current distribution is OSS self-host Alpha | Explicit hosted product contract and end-to-end acceptance matrix |
| P1 | No multi-hour source-build and published-image soak | A short health window is not an SLO | Scheduled bounded soak receipts for both image paths plus interruption/restart cases |
| P1 | No production SLO, alert, incident, or enforced retention policy | Operators lack a production operations contract | SLO/error-budget definitions, alerts, incident drill, retention/deletion evidence |
| P1 | No independent security assessment | Internal checks cannot establish external assurance | Independent report with tracked remediation |
| P1 | No community-scale PMF evidence | Product demand and repeat value remain unproven | Cohort-based opt-in adoption and repeat-use report |

These P0 findings do not block the local-first OSS phase because hosted commercial service is outside
the current delivery contract. They do block any claim that the whole product is commercially live.

## S11-S13 UI, Copy, And Legacy

- UI/design system: not applicable to the current no-standalone-frontend delivery boundary.
- Copy: pass. Docs repeatedly distinguish a bounded window from production reliability and avoid
  promising automatic recovery.
- Legacy: the repository, package, and API retain `study-anything` compatibility names while Cognitive
  Black Box is the product center. This is an intentional adapt/deprecate boundary, not a completed
  rename.

## S14 Automated Gates

| Gate | Result |
| --- | --- |
| Eight focused unit tests | Pass |
| `python3 scripts/verify_self_host_soak.py --check` | Pass |
| Ruff and Python compile checks | Pass |
| Real Docker API learning flow | Pass |
| Real bounded Docker soak, 10/10 healthy | Pass |
| Isolated backup/mutate/restore, session count 1 -> 2 -> 1 | Pass |
| Platform bundle and adoption pack checks | Pass |
| External adoption verification, 2,172 files | Pass |
| Full `./scripts/release_check.sh`, including clean clone and dependencies | Pass |
| Full unit suite, 838 tests | Pass |

The final release receipt records `status=completed`, `exit_code=0`,
`full_release_check_completed=true`, `clean_clone_completed=true`,
`dependency_install_completed=true`, and `known_issue=none` for this run.

## S15 Findings And Build Order

### Preserve

- Dual Loop and Delivery Trust evidence chain.
- Local-first Bring Your Own Agent privacy boundary.
- Deterministic metadata-only receipts and executable verifiers.
- Backup/restore isolation and non-destructive failure handling.
- Platform Agent packs and release evidence generation.

### P2 Engineering Debt

- Generated evidence has a dependency order but no single topological refresh command. During this
  phase, stale derived assets had to be refreshed in several rounds.
- Strict mypy covers selected security-critical targets, not the entire Python package.
- Credential recovery after `.env` loss still requires a trusted matching `.env` or `env.snapshot`;
  diagnosis is automatic but recovery is intentionally manual.

### Recommended Order

1. Add a generated-evidence topology orchestrator with one refresh/check command and dependency
   receipts.
2. Add scheduled source-build and published-image soak/restart evidence without claiming an SLO.
3. Define hosted identity, tenancy, entitlement, incident, retention, and support contracts before
   implementing paid services.
4. Obtain independent security review and real adopter evidence before a commercial production claim.

## Final Decision

Phase 11 satisfies its declared acceptance contract and may merge after GitHub CI passes. The project
remains a verified local-first OSS Alpha, not a commercially complete hosted product.
