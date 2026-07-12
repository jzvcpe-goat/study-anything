# Personal Local Clearance MVP

`delivery-clearance` lets one operator audit an AI-assisted local Git project before
continuing the development process. It is deliberately narrower than customer handoff,
production approval, or independent audit.

The MVP answers one question:

> Is this exact Git-visible project state cleared for my own personal local use, under
> boundaries I reconstructed and responsibility I explicitly accepted for this run?

**未经放行，不得交付。** For this MVP, "delivery" means continuing to use or promote the
candidate inside the operator's own local workflow. The maximum scope is always
`personal_local`.

## Install

From a clone of this repository:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/delivery-clearance --help
```

The compatibility wrapper remains available:

```bash
.venv/bin/python scripts/personal_clearance.py --help
```

## Use It On A Local Project

Initialize a contract in the target Git repository:

```bash
delivery-clearance init --project /path/to/my-project
```

This creates:

```text
.delivery-clearance/
  .gitignore
  personal-clearance.json
```

The generated config contains blocking `TODO:` values. Replace them with:

- the exact purpose of the candidate;
- explicit non-goals;
- the critical failure path;
- the observable rollback trigger;
- the rollback strategy;
- known evidence limitations;
- one or more project-specific, read-only checks represented as argument arrays.

Example check entry:

```json
{
  "check_id": "unit-tests",
  "argv": ["python3", "-m", "pytest", "-q"],
  "timeout_seconds": 300,
  "required": true
}
```

Build a receipt only after reviewing the config:

```bash
delivery-clearance audit \
  --project /path/to/my-project \
  --execute-checks \
  --accept-responsibility
```

The two flags are intentionally separate:

- `--execute-checks` authorizes the configured argument arrays for this run;
- `--accept-responsibility` records a run-specific self-attestation to the reconstructed
  boundaries. A value stored in the config cannot silently substitute for this action.

Before continuing the development flow, verify the receipt again:

```bash
delivery-clearance verify --project /path/to/my-project
```

Use the `verify` command as a manual pre-commit, pre-merge, or pre-handoff gate. The MVP
does not install Git hooks automatically.

## Decision Rules

An `allow` result requires all of the following:

1. the target is a local Git repository;
2. every boundary placeholder has been replaced;
3. all configured required checks were explicitly run and passed;
4. the checks did not alter the Git-visible project state;
5. the operator accepted responsibility for this exact run;
6. the canonical Protocol v1 Trust Kernel replay allows only `personal_local`;
7. the receipt is unexpired and still matches the current Git state.

The command exits with:

| Code | Meaning |
|---:|---|
| `0` | cleared or successfully verified for `personal_local` |
| `1` | invalid config, missing/tampered/stale receipt, or verification error |
| `2` | more evidence or active reconstruction is required |
| `3` | a failed check or hard deny blocked clearance |

Any tracked, staged, unstaged, or non-ignored untracked content change invalidates the
receipt. The snapshot binds the HEAD commit, branch-name hash, staged and unstaged diff
hashes, non-ignored untracked content manifest, submodule-state hash, and config digest.
It never emits raw source, raw diffs, untracked paths, raw check commands, or raw check
output.

## Artifacts

The audit writes ignored local artifacts under:

```text
.delivery-clearance/artifacts/
  project-snapshot.json
  check-results.json
  human-reconstruction.json
  trust-policy.json
  evidence-bundle.json
  qualified-reconstruction.json
  gate-decision.json
  personal-clearance-receipt.json
  personal-clearance-report.html
```

The config is intended to be reviewable and may be committed. The generated artifact
directory is ignored by the nested `.gitignore` unless the operator deliberately changes
that policy.

## Security And Claim Boundary

Configured checks run with the current user's permissions, inherit the current process
environment, and are invoked with `shell=False`. The MVP does not provide an OS sandbox,
network egress control, or protection from external side effects caused by a configured
child command. Git-visible state is compared before and after checks; ignored-file,
network, service, database, or other external mutations are not independently detected.

`verify` validates the existing check receipt; it does not rerun checks. Re-audit after
the receipt expires, after any Git state change, or whenever a check definition or boundary
changes.

The public CLI always uses the local system clock. Test-only deterministic timestamps are
available only to the Python verification helpers and cannot be supplied as command-line
arguments.

A passing personal receipt proves only:

- a deterministic local gate replay matched the stored artifacts;
- the exact current Git-visible state matches the audited state;
- the operator self-attested the stated boundaries for this run;
- configured checks reported success within the stated evidence limitations.

It does not prove AI correctness, independent review, external delivery authority,
production approval, professional qualification, or legal/security/compliance
certification. External or customer-facing claims still require a separate qualified
reviewer, risk owner, provenance, and target-scope receipt.

An installed plugin is not clearance evidence by itself. A real local plugin study found
that manifest parsing can pass while the plugin runtime, native browser surface, dependency
loader, or full regression suite remains unavailable. It also confirmed that project-external
side effects and mutable external inputs are not observed by the Git snapshot. See
[Phase 42 Real Installed-Plugin Boundary Study](quality-audits/phase-42-real-plugin-boundary-study.md)
for the executed cases, timings, and the explicit list of capabilities this MVP cannot clear.

For plugin-assisted work, run [Plugin Evidence Adapter v0.1](plugin-evidence-adapter.md) as a
required configured check. The adapter does not run the plugin and cannot expand scope; it
turns bounded runtime, input, effect, native-verification, and domain evidence into a zero-exit
precondition for the final personal audit.

## Verify The MVP Itself

```bash
.venv/bin/python scripts/verify_personal_clearance_mvp.py --check
.venv/bin/python -m unittest discover -s apps/api/tests -p 'test_personal_clearance.py'
```

The verifier covers CLI exposure, default blocking, explicit personal release, missing
responsibility, unexecuted checks, check failure, check mutation, stale state, expiry,
tamper, scope expansion, secret-like config, and local-path privacy.
