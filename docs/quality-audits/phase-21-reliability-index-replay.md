# Phase 21 Project Quality Audit

Audit date: 2026-07-09

Scope: bounded reliability-index replay for completed `reliability-soak` runs.

Authority: `通用质检方案.md` (Contract-First Product Audit Framework), reviewed in S0-S15 order.

## Executive Conclusion

- Phase 21 implementation: **Pass for merge**.
- Strict reliability acceptance: **Needs Changes until the replayed remote index passes**.
- Whole-product commercial production launch: **Needs Changes**.

Run `29060766261` completed both strict two-hour mode jobs successfully. Its index job did not execute
because the run retained the old workflow definition while full-SHA Action enforcement was enabled
during the two-hour window. This phase adds a bounded replay path for the original immutable mode
receipts; it does not rerun, repair, relax, or replace them.

## S0-S9 Contract, Implementation, Data, And Privacy

| Check | Result | Evidence |
| --- | --- | --- |
| Source of truth | Pass | `main` at `f5f4fd23`, branch `codex/v0.3.281-reliability-index-replay` |
| Original source-build job | Pass | 7,256 elapsed seconds, 721 samples, ratio 0.9931, recovery observed |
| Original published-image job | Pass | 7,240 elapsed seconds, 721 samples, ratio 0.9931, recovery observed |
| Original index job | Failed closed | Old mutable Action tags rejected by new repository policy |
| Offline reconstruction | Pass | Existing indexer classifies the exact two receipts as `strict_dual_pass` |
| Replay source | Pass | Positive numeric same-repository run ID only |
| Workflow binding | Pass | Source run must be completed and belong to `reliability-soak.yml` |
| Commit binding | Pass | GitHub-resolved head SHA must match the source-build receipt |
| Privacy | Pass | Index and receipts remain metadata-only; no logs, URLs, secrets, source, or answers |

The replay job obtains only the source run ID, head SHA, event, workflow path, and completion status
from GitHub. Existing receipt validation still rejects missing artifacts, mixed profiles, failed
receipts, source mismatch, insufficient elapsed time, relaxed thresholds, or private payloads.

## S10-S13 Production, UI, Copy, And Legacy

- Replay is an operator recovery path, not a second source of reliability truth.
- It cannot turn diagnostic evidence into strict evidence or infer a production SLO.
- No UI, payment, model-call, customer-visible action, or production mutation is introduced.
- The one low-severity unpatched transitive AI SDK alert and independent security scan remain
  separate product risks.

## S14 Automated Gates

| Gate | Result |
| --- | --- |
| Reliability index verifier | Pass; replay/workflow/commit bindings covered |
| Reliability index unit tests | Pass; 10 tests |
| Real source-run metadata resolution | Pass for run `29060766261` |
| Container/workflow security policy | Pass; all Actions remain full-SHA pinned |
| Generated evidence topology | Pass; 19/19 converged |
| External adoption | Pass; 2,188 files in 18.54 seconds |
| Full `./scripts/release_check.sh` | Pass |
| Clean clone and dependency install | Pass |
| Full unit suite | Pass; 874 tests |

The release receipt records `full_release_check_completed=true`, `clean_clone_completed=true`,
`dependency_install_completed=true`, and `known_issue=none` for this implementation run.

## S15 Findings And Final Decision

The implementation may merge after GitHub CI passes. After merge, dispatch the workflow with
`evidence_run_id=29060766261`, require a successful index-only run, download the 90-day index
artifact, and verify its source run ID, head SHA, receipt hashes, strict profile, and
`strict_dual_pass` decision.

Do not claim longitudinal reliability: one strict dual pass is one bounded run. Three independent
strict dual passes are still required for the limited trend signal, and no number of runs proves a
production SLO, incident response, disaster recovery, or customer availability.
