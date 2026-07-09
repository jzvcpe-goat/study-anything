# Phase 16 Project Quality Audit

Audit date: 2026-07-09

Scope: first remote GitHub acceptance of the scheduled source-build and published-image reliability
matrix, including clean-runner fixes and bounded startup retries.

Authority: `通用质检方案.md` (Contract-First Product Audit Framework), reviewed in S0-S15 order.

## Executive Conclusion

- Phase 16 delivery: **Pass**.
- Whole-product commercial production launch: **Needs Changes**.
- Claim boundary: this phase proves a short, relaxed-threshold GitHub workflow run for both runtime
  modes. It does not prove the default two-hour schedule, a production SLO, disaster recovery,
  customer availability, security certification, commercial readiness, or PMF.

## S0-S3 Direction And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Source of truth | Pass | GitHub workflow runs and downloaded metadata-only receipts |
| Delivery boundary | Pass | Short diagnostic run is explicitly separated from default two-hour evidence |
| Product contract | Pass | Both source and published paths use the same API flow, fault, and recovery gate |
| Reversibility | Pass | Isolated Compose projects and disposable volumes are removed after each run |

## S4-S9 Implementation, Data, Protocol, Security, And Privacy

The first main-branch workflow run, `29056993173`, produced useful negative evidence:

- `source-build`: pass.
- `published-image`: blocked at `compose_start` after the API image was successfully pulled and its
  digest recorded.
- Root cause: the published path used global `--pull never`; a clean runner therefore could not pull
  the missing Postgres dependency image.

The first fix removed the global pull prohibition while retaining the explicit API pull and digest
inspection. Run `29057652810` then proved:

- `published-image`: pass, confirming the clean-runner dependency fix.
- `source-build`: one-second transient `compose_start` failure.

An unchanged rerun, `29057773169`, passed both modes. This established that the source failure was
transient rather than a deterministic source-build regression. The runner was then hardened with:

- at most three Compose start attempts;
- a ten-second delay between attempts;
- no infinite retry or weakened soak threshold;
- actual attempt count in the receipt;
- classified `*_after_retries` terminal failure.

The final fix-commit run, `29058195633`, passed both jobs:

| Mode | Duration | Samples | Controlled failures | Recoveries | Start attempts | Result |
| --- | --- | --- | --- | --- | --- | --- |
| source-build | 1m37s | 20 | 4 | 1 | 1 | Pass |
| published-image | 1m30s | 20 | 4 | 1 | 1 | Pass |

Both receipts confirm API flow completion, controlled restart completion, post-failure health
recovery, and recovery of the learning session created before restart. The source receipt records a
clean commit; the published receipt records an immutable image digest while excluding the repository
reference.

The workflow uses `actions/upload-artifact@v6`, the official Node 24 release. No Node 20 deprecation
warning remained in the final run.

## S10-S13 Production, UI, Copy, And Legacy

- Hosted production blockers remain identity/tenancy, billing/entitlement, alerts, incident response,
  repeated strict reliability evidence, independent security review, and PMF.
- No standalone UI, model-key custody, production mutation, or public action surface was added.
- The docs state that dependency images may be pulled separately from the explicitly identified API
  image and that retries are bounded.
- The first two blocked runs remain immutable negative evidence; they were not deleted or rewritten.

## S14 Automated Gates

| Gate | Result |
| --- | --- |
| Compose published dependency pull contract | Pass |
| Compose bounded retry unit test | Pass |
| Reliability matrix verifier | Pass |
| Generated evidence topology | Pass; 19/19 nodes current |
| Full `./scripts/release_check.sh` after final retry change | Pass |
| Clean clone and dependency install | Pass |
| Full unit suite | Pass; 854 tests |
| Final source-build GitHub job | Pass |
| Final published-image GitHub job | Pass |
| Final receipt privacy and recovery fields | Pass |

The final release receipt records `full_release_check_completed=true`,
`clean_clone_completed=true`, `dependency_install_completed=true`, and `known_issue=none`.

## S15 Findings And Build Order

### Preserve

- Real remote acceptance before claiming workflow usability.
- Failure receipts even when a job blocks.
- Source commit and published digest provenance.
- Pre-restart session recovery as a stronger condition than health-only recovery.
- Bounded retry with observable attempt count.
- Equal recovery gates for source and published modes.

### Residual Debt

- The default two-hour strict run has not completed. All Phase 16 runs used diagnostic thresholds.
- One passing short run is not enough to establish reliability trends.
- GitHub receipts are retained for 14 days and are not yet aggregated into long-term trend evidence.
- Production SLOs, alerting, incident response, and cross-mode restore drills remain future work.

### Next Product Goal

Allow the weekly workflow to produce strict default-duration receipts. After at least one strict pass
for both modes, add a metadata-only longitudinal reliability index that references run IDs, commit or
digest identities, thresholds, outcomes, and receipt hashes without copying logs or private payloads.

## Final Decision

Phase 16 satisfies its short remote workflow acceptance contract and is ready for PR review. The next
reliability claim must wait for strict two-hour evidence; do not relabel this diagnostic run as a
scheduled SLO result.
