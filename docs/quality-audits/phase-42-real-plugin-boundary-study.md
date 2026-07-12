# Phase 42 Real Installed-Plugin Boundary Study

Study date: 2026-07-11 PDT

Project: Delivery Clearance personal-local reference harness

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/real-plugin-boundary-study`

Audit base: `cb707a884a195fb482a70d6a1ae0c0a40d5da750`

Operator: Codex, acting as the local user

## Executive Conclusion

Decision: **The personal-local MVP is useful as a Git-state and declared-check gate,
but it cannot clear an installed plugin as a whole.**

The study exercised locally installed plugins and safe proxies for their effect classes.
It confirmed that Delivery Clearance can:

- bind a receipt to one exact Git-visible project state;
- execute explicitly authorized deterministic checks;
- block on any required non-zero result or timeout;
- preserve a narrow claim when only a subset of plugin contracts passes;
- invalidate a receipt after a Git-visible project change; and
- keep the allowed scope at `personal_local`.

It also reproduced hard boundaries that the MVP must not claim to solve. A passing receipt
does not observe external side effects, bind mutable external inputs, establish plugin
runtime readiness, validate professional semantics, prove browser or desktop state, or
sandbox a configured child process. An installed manifest is inventory evidence, not
operational or delivery evidence.

No result in this study authorizes client circulation, financial advice, database change,
deployment, production use, or any other external responsibility transfer.

## Local Plugin Inventory

The machine exposed 22 installed plugin manifests across these capability classes:

| Class | Representative installed plugins | Effect posture |
| --- | --- | --- |
| Local artifacts | Documents, PDF, Presentations, Spreadsheets, Templates | File creation and rendering |
| Local and interactive UI | Browser, Computer Use, Product Design, Figma | Browser or desktop state |
| Repository and security | GitHub, Codex Security | Local and remote repository evidence |
| Data and professional analysis | Data Analytics, Public Equity Investing, Investment Banking | Source-dependent semantic judgment |
| External services | Supabase, Vercel, Sites, Notion | Network reads and external mutation |
| Developer platforms | OpenAI Developers, Visualize | Tool, runtime, or hosted artifact behavior |

The inventory included two separately packaged GitHub plugin installations. Manifest count
therefore does not equal unique product count.

## Executed User Tests

| Case | Observed plugin behavior | Clearance result | Interpretation |
| --- | --- | --- | --- |
| Installed manifest inventory | All 22 plugin manifests parsed as JSON | `allow`, `personal_local` | Proves inventory syntax only |
| Public Equity full regression | 188 passed, 10 failed, 6 skipped in 1.86 s | `block` | Any required failure blocks the whole declared check |
| Public Equity narrow boundary | Six tests passed for connector-claim and style-as-evidence boundaries | `allow`, `personal_local` | A narrow passing claim is possible without trusting the whole plugin |
| Data Analytics full regression | 182 passed, 11 failed, 1 skipped; missing `typescript` and `playwright-core` were among the failures | `block` | Installed package was not regression-ready in this runtime |
| Documents / Spreadsheets runtime | Required dependency loader did not return after more than three minutes and was terminated | no artifact, no clearance | Plugin runtime readiness was unavailable |
| Browser report inspection | Browser runtime initialized, but both `file://` and localhost tabs failed to attach | no browser evidence | Report was not visually cleared by the plugin |
| External side-effect proxy | A configured check wrote a harmless marker outside the project and exited zero | `allow`; later `verify` passed | External mutation is not observed by the Git snapshot |
| Mutable external source | Audit passed against source version 1; source changed to version 2; old `verify` still passed | stale receipt remained valid until re-audit | `verify` does not rerun checks or bind external source state |
| Intentionally false finance memo | An unsourced, explicitly invalid claim passed `git diff --check` | `allow`, `personal_local` | Structural checks do not prove semantic or professional correctness |
| Slow plugin check | A two-second check with a one-second budget timed out | `block` in about 1.29 s | Per-check timeout fails closed |
| Same slow check, larger budget | The check completed inside a three-second budget | `allow` in about 2.31 s | Declared check time dominates audit latency |
| Ten serial checks | Ten 100 ms checks ran sequentially | `allow` in about 1.44 s | Check latency accumulates; there is no parallel scheduler |
| Non-Git directory | `init` was attempted on a plain directory | rejected | The personal MVP requires a local Git repository |

The test command output stayed outside receipt artifacts. The check receipt retained only
status, exit code, duration, byte counts, and digests.

## Scale Measurements

All scale cases used a trivial passing `git diff --check` and wrote timing output outside
the audited repository. An earlier benchmark attempt wrote its timing file into the target
repository; `verify` correctly rejected every resulting stale receipt. Those invalid runs
are excluded below.

| Project shape | Audit | Verify | Result |
| --- | ---: | ---: | --- |
| 10 untracked files | 0.29 s | 0.19 s | Pass |
| 1,000 untracked files | 0.33 s | 0.21 s | Pass |
| 10,000 untracked files | 0.63 s | 0.38 s | Pass |
| One 100 MiB untracked sparse file | 0.37 s | 0.24 s | Pass |
| Local clone of this repo, 2,847 tracked files | 0.49 s | 0.26 s | Pass |

This is an operator sample, not a general benchmark. It does not establish performance on
network filesystems, very large monorepos, nested submodules, millions of files, or slow
cryptographic and integration checks.

## Abilities The Personal MVP Can Clear

The current implementation can clear only a narrow proposition:

> This exact Git-visible state passed these exact configured checks, within their stated
> time budgets, and the operator accepted responsibility for continued personal local use.

Within that proposition it can support:

1. local source, configuration, documentation, and generated artifacts stored in Git;
2. deterministic unit, lint, type, schema, build, and narrowly scoped plugin checks;
3. metadata-only check receipts without raw command output;
4. receipt integrity, expiry, config binding, and Git-state freshness; and
5. a narrow subset claim when the operator explicitly avoids broader plugin claims.

## Abilities It Cannot Clear

The following capabilities are outside the current delivery authority even when a receipt
returns `allow` for `personal_local`:

1. **External side effects.** Database writes, deployments, messages, uploads, purchases,
   permissions, browser submissions, and desktop-app changes are outside the Git snapshot.
2. **External data freshness.** Market data, web pages, SaaS records, API responses, and
   remote repository state can change while an old local receipt still verifies.
3. **Professional semantic truth.** Financial, legal, medical, security, analytical, or
   factual quality requires domain-specific evidence and qualified reconstruction.
4. **Plugin runtime readiness.** A valid installed manifest does not prove dependencies,
   browser attachment, credentials, connectors, or the plugin's own tests are working.
5. **Visual and interactive quality.** Browser, document, spreadsheet, presentation, and
   desktop state need successful native render or interaction evidence for the exact run.
6. **Non-Git work.** The personal command has no snapshot contract for folders, documents,
   SaaS workspaces, databases, or application state that is not represented in Git.
7. **Process containment.** Checks inherit user permissions and environment; they are not
   isolated from filesystem, credential, process, or network effects.
8. **Independent responsibility transfer.** Self-attestation cannot authorize a customer,
   affected party, production operator, regulated use, or another risk owner.
9. **Long-lived external claims.** `verify` replays stored check evidence rather than
   rerunning external checks; volatile sources require re-audit or bound source snapshots.
10. **Arbitrary plugin chains at constant latency.** Checks execute sequentially. The schema
    permits up to 20 checks and up to 3,600 seconds per check, so a poorly designed contract
    can become non-interactive even though the gate itself is fast.

## Required Evidence Before Broader Plugin Clearance

Broader plugin delivery should remain blocked until a future protocol layer can bind:

- plugin id, version, package digest, runtime, and dependency readiness;
- declared capability and side-effect classes;
- sandbox or externally observed effect receipts;
- external input digests, source timestamps, and revalidation rules;
- native browser, document, spreadsheet, or desktop verification evidence;
- domain-specific evaluators and scoped qualified reviewers;
- recipient, affected-party, risk-owner, rollback, and revocation evidence; and
- a target-scope receipt that is separate from the personal self-audit.

The protocol should not try to infer these properties from command text. The external
effect proxy demonstrated that a locally passing command can still change state outside
the observed project.

## Product Decision

Keep the current MVP available for local development discipline, with this operating rule:

> Use Delivery Clearance to decide whether to continue with one exact local project state.
> Do not use it to claim that an installed plugin, external source, professional conclusion,
> or real-world action is cleared for delivery.

The correct expansion is not a generic "plugin passed" badge. Plugin Evidence Adapter v0.1
now turns package digest, runtime readiness, input provenance, effect boundary, domain checks,
and native verification into an explicit supporting receipt. It can allow only
`personal_local`; external writes remain hard-blocked, while external reads, interactive
state, and professional judgment require their respective bounded evidence. This does not
broaden the Personal Clearance claim or solve OS-level effect observation.
