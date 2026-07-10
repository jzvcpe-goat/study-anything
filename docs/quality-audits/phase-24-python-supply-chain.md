# Phase 24 Python Supply-Chain Audit

Audit date: 2026-07-09 PDT

Scope: close the Phase 23 P1 for unbounded Python dependency resolution in Docker, CI, Skill Mode,
and repository policy jobs.

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

- Implementation: **Pass for protected CI**.
- Local deterministic verification: **Pass**.
- Local isolated install: **Incomplete because package downloads were too slow; no hash failure was
  observed**.
- Hosted or commercial production: **Needs Changes for unrelated identity, tenancy, operations, and
  external-audit requirements**.

## S0-S3 Source And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | Clean `main` at `0c4d3504`; work isolated on `codex/v0.3.284-python-supply-chain-lock` |
| Resolution truth source | Pass | `uv.lock` is the universal lock for Python `>=3.11,<3.13` |
| Pip compatibility | Pass | Skill, full, dev/full, and policy projections use exact versions and SHA-256 hashes |
| Claim boundary | Pass | Receipt separates inventory/lock evidence from online vulnerability or index-trust claims |

Python 3.13 and newer are not claimed. The tested project matrix is Python 3.11 and 3.12.

## S4-S9 Security, Privacy, And Integrity

| Area | Result |
| --- | --- |
| Docker source build | Hash-bound full requirements; local package uses `--no-deps --no-build-isolation` |
| API CI | Hash-bound dev/full requirements and offline lock/SBOM verification |
| Skill Mode | Hash-bound lightweight requirements; legacy fallback remains only when a distribution omits the lock projection |
| Policy workflow | Hash-bound policy requirements |
| SBOM | Deterministic CycloneDX 1.5; invocation timestamp and random serial removed |
| Privacy | Metadata-only package names, versions, hashes, relationships, and counts; no source, answers, secrets, or local paths |
| Advisory boundary | GitHub dependency review remains the online PR gate; local receipt does not assert an advisory query occurred |

## S10-S13 Operations And Documentation

- `docs/python-supply-chain.md` defines maintainers' refresh/check flow.
- Security, self-hosting, Skill Mode, getting started, release checklist, and unreleased notes use the
  same Python support and hash-install contract.
- The GitHub supply-chain workflow intentionally uploads a generated candidate before checking for
  uncommitted drift. This allowed the Linux-generated lock to be reviewed and reproduced offline on
  macOS without trusting the local stalled resolver.
- Platform bundles and adoption packs include the lock, projections, SBOM, receipt, docs, and updated
  workflow surfaces.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| Focused Python/container/launcher/release/clean-clone tests | Pass; 78 tests |
| Ruff and shell syntax | Pass |
| Offline lock, requirements, SBOM, and receipt reproduction | Pass; 92 lock packages, 91 SBOM components |
| Container security policy and full Compose config | Pass |
| Generated release-distribution topology | Pass; 20/20 nodes after adding the previously omitted platform-agent replay generator |
| Local empty Skill environment install | Stopped after 2 minutes 30 seconds while downloads were still progressing at about 15 KB/s |
| Local `release_check.sh --skip-clean-clone` | Pass; 901 tests and all integrated trust gates, with an honest partial receipt |
| GitHub locked API install, Docker smoke, lock/SBOM, CodeQL, dependency review | Pass on the implementation head; final audit-only head must replay before merge |

## S15 Decision

Merge only after GitHub verifies the checked-in lock is unchanged, installs the hash-bound dev/full
environment, runs the API suite, builds the real Docker smoke stack, and passes the security checks.
Do not describe the SBOM as proof that dependencies are vulnerability-free. The existing low-severity
default-branch advisory and future dependency updates remain separate maintenance work.

During the local partial release run, the release replay test initially forced a new repository venv
and became an accidental network-install test. The replay launcher now respects an explicitly supplied
pre-provisioned venv, while clean installation remains owned by the separate supply-chain and GitHub
CI gates. This also exposed and fixed a harness gap: the generated-evidence topology previously did
not include platform-agent replay and could report 19/19 while that artifact was stale.
