# Phase 18 Project Quality Audit

Audit date: 2026-07-09

Project: Study Anything / Cognitive Black Box

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.278-longitudinal-reliability-index`

Commit: `169d802e36f7bcd3ab5bf87fa0be51f676112fe9`

Pull request: #403

Authority: `通用质检方案.md` (Contract-First Product Audit Framework), reviewed in S0-S15 order.

## Executive Conclusion

- Phase 18 delivery: **Pass**.
- Whole-product commercial production launch: **Needs Changes**.
- Largest remaining reliability gap: no strict default-duration two-mode GitHub receipt exists yet.
- Claim boundary: this phase proves the offline index contract, automated GitHub artifact bridge,
  diagnostic classification, privacy rejection, and full release compatibility. It does not prove a
  strict two-hour run, a longitudinal trend, a production SLO, incident response, disaster recovery,
  commercial hosting, or customer availability.

## S0-S3 Materials, Truth, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Source of truth | Pass | PR #403 at commit `169d802e`; branch and GitHub head matched |
| Delivery included | Pass | Offline index builder, verifier, workflow summary job, tests, docs, generated packs |
| Delivery excluded | Pass | No frontend, model call, production mutation, hosted service, SLO, or strict-run claim |
| Product contract | Pass | Source-build and published-image evidence remain equal-weight release paths |
| Existing evidence preserved | Pass | Short runs remain diagnostic; prior short acceptance is not relabeled strict |

The implementation advances the local-first trust contract by making reliability claims machine
classifiable. It does not change the learning product, Agent key boundary, or customer delivery gate.

## S4-S8 Implementation, User Loop, Data, And Interfaces

The operator flow is now:

1. Run the source-build and published-image matrix under one GitHub run ID.
2. Upload one metadata-only receipt per mode.
3. Download both receipts inside a separate summary job.
4. Validate exact schemas, thresholds, source identity, image digest, and privacy flags.
5. Emit one `self-host-reliability-index-v1` artifact with canonical receipt hashes.

The builder also works offline with downloaded receipt files. It rejects unknown fields, malformed
timestamps, source/head mismatch, invalid digests, failed thresholds presented as passing, mixed
strict/diagnostic profiles, conflicting duplicate run IDs, and tampered historical summaries.

The index permits a bounded trend signal only after three strict dual passes. It always keeps
`production_slo_claimable=false`.

## S9 Security And Privacy

| Boundary | Result |
| --- | --- |
| Unknown input fields rejected | Pass |
| Raw logs and command output excluded | Pass |
| API URLs and image references excluded | Pass |
| Source text and learner answers excluded | Pass |
| Keys, tokens, secrets, and local paths excluded | Pass |
| Receipt hashes and runtime identities retained | Pass |
| Local index writer uses mode `0600` | Pass |
| Model calls or production mutation | None |

The staged secret scan matched only intentional negative-test needles. GitHub artifact extraction
does not preserve the local `0600` mode, but the artifact is metadata-only and contains no secret;
its retention is bounded to 90 days.

## S10-S13 Production, Commercial, UI, Copy, And Legacy

- A real short GitHub run, `29060254135`, passed source-build, published-image, and index jobs.
- Its index correctly reports `diagnostic_only`, `strict_dual_pass=false`,
  `longitudinal_trend_claimable=false`, and `production_slo_claimable=false`.
- The index artifact expires after 90 days; the two underlying mode receipts expire after 14 days.
- No UI or independent frontend was introduced.
- Existing release-stack history and terminal self-intake recursion policy were not changed.
- Hosted identity, multi-tenancy, billing, alerting, incident response, disaster recovery, and PMF
  remain outside this phase and are not implied by the OSS launch ledger.

## S14 Automated Gates

| Gate | Result |
| --- | --- |
| Reliability index deterministic verifier | Pass |
| Reliability matrix verifier | Pass |
| Ruff and Python compile | Pass |
| Workflow YAML parse | Pass |
| Generated evidence topology | Pass; 19/19 current |
| External adoption | Pass; 2,184 files |
| Full `./scripts/release_check.sh` | Pass |
| Clean clone and dependency install | Pass |
| Full unit suite | Pass; 864 tests |
| GitHub `api-tests` | Pass; 2m32s |
| GitHub `compose-smoke` | Pass; 1m28s |
| GitHub short source-build matrix | Pass; 1m33s |
| GitHub short published-image matrix | Pass; 1m09s |
| GitHub index summary job | Pass; 9s |

The final local release receipt records `full_release_check_completed=true`,
`clean_clone_completed=true`, `dependency_install_completed=true`, and `known_issue=none`.

## S15 Findings And Decision

### P1: Strict default-duration evidence is still missing

The real remote run is intentionally diagnostic. It proves workflow mechanics and index generation,
not the default 721-sample, 7,200-second contract. After merge and final-main image publication, run
the workflow with untouched defaults and require both modes plus the index job to pass.

### P1: Longitudinal trend is not established

One future strict pass proves one run. At least three strict dual passes are required before the
bounded trend signal becomes true. Even then, production SLO and commercial readiness remain false.

### P1: Production operations remain incomplete

Alert routing, incident ownership, recovery objectives, disaster-recovery rehearsal, production
tenant isolation, and customer availability commitments need separate evidence and must not be
inferred from isolated Compose runs.

### Decision

Phase 18 satisfies its declared contract and may merge after the final docs-only commit passes the
required GitHub checks. The immediate next goal is operational: publish the merged main image, run
the strict default two-hour matrix, inspect both receipts and the generated index, and record that
single-run evidence without claiming a trend or SLO.
