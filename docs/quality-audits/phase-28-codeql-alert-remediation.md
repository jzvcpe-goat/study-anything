# Phase 28 CodeQL Alert Remediation Audit

Audit date: 2026-07-10 PDT

Scope: remediate the 15 open default-branch CodeQL alerts discovered after
Phase 27 merged, and prevent a green pull request from being confused with a
zero-alert repository ledger.

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

- Code remediation: **Pass locally; protected CI pending**.
- Default-branch alert ledger: **Needs Changes until this branch merges and a
  new main-branch CodeQL analysis closes the 15 prior alerts**.
- Independent external audit: **Still pending**. This self-remediation is not an
  audit report or security certification.

## S0-S3 Source And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | Clean `main` at `107ae2db`; isolated branch `codex/v0.3.288-codeql-alert-remediation` |
| Alert inventory | Pass | 15 open alerts pinned to `refs/heads/main`: 3 path injection, 2 exception exposure, 4 production/report sinks, and 6 synthetic negative-fixture sinks |
| Claim boundary | Pass | PR CodeQL success means no new PR alert; only a post-merge live ledger can prove zero open default-branch alerts |
| Gate integrity | Pass | No workflow query suite, severity, branch protection, or repository-wide exclusion is weakened |

## S4-S9 Data, Protocol, Security, And Privacy

- Retrieval quality output replaces exception strings with bounded error codes.
- Plugin API input is a single intake directory name. Trusted roots are
  operator configuration; filesystem candidates are enumerated from those
  roots, and symlink escapes, traversal, absolute paths, and ambiguity fail.
- Hosted OIDC middleware continues to block all plugin routes.
- Environment checks no longer print unsupported modes, bind hosts, OIDC parser
  detail, allowlist entries, invalid port values, stack profiles, or raw OS
  errors. Public environment labels are allowlisted.
- Customer handoff JSON is validated against the metadata-only contract before
  writing. Its secret-like rejection verifier remains blocking.
- Secret-like negative cases are checked-in static fixtures under
  `fixtures/codeql-negative/`. Verifiers copy those fixtures into disposable
  roots instead of constructing sensitive-looking values and writing them from
  Python. No query suppression comment, workflow exclusion, or directory-wide
  static-analysis exclusion is used.
- The five static fixtures are included in the platform bundle and adoption
  pack so the same rejection paths remain executable outside the repository.
- The GitHub posture receipt now records open Code Scanning and Dependabot
  counts and fails unless both are zero.

## S10-S13 Commercial, Operations, UI, And Legacy

- No UI, model call, production mutation, billing, or hosted account flow is
  added.
- Plugin API clients must place packages under a configured intake root and send
  the direct child name. The local shell CLI keeps its explicit operator-path
  behavior.
- The external audit plan adds the read-only live GitHub posture command. The
  audit issue must be repinned after merge because the scope commit and pack hash
  will change.
- Existing deterministic fixtures remain valid and continue proving unsafe
  inputs are rejected.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| Ruff and Python compilation | Pass on all changed Python surfaces |
| Focused environment regression | Pass; 41 tests |
| Customer handoff verifier | Pass; secret-like and scope-expansion fixtures still blocked |
| Agent gateway verifier | Pass in contract-only mode; runtime socket test not replaced |
| Artifact console verifier | Pass |
| Evolution pack verifier | Pass |
| Patch apply sandbox verifier | Pass |
| Cognitive Loop review verifier | Pass; synthetic token does not enter review output |
| GitHub posture deterministic verifier | Pass; 5 tests including non-zero alert rejection |
| Full API suite | Pass; 937 tests, with existing Starlette/httpx and importlib metadata deprecation warnings only |
| Generated evidence topology | Pass; 21 of 21 nodes converged |
| External adoption pack | Pass; 2204-file pack, 34 tools, isolated Skill Mode flow in 17.5 seconds using the prebuilt local venv |
| Full strict mypy | Not claimed; broad traversal still reports 71 pre-existing errors across dynamic and optional-integration modules |
| Partial release check | Pass with exit 0 using `--skip-clean-clone`; receipt keeps full/clean-clone/dependency-install flags false |
| Protected GitHub checks | Pending PR |
| Pre-merge live alert ledger | Expected fail; Code Scanning 15, Dependabot 0 on current `main` |
| Post-merge live alert ledger | Pending; both counts must become zero after main-branch analysis |

## Acceptance Matrix

| Area | Minimum Passing Condition | Status |
| --- | --- | --- |
| Exception privacy | No caught exception detail reaches retrieval API reports | Pass locally |
| Plugin paths | All three file-facing endpoints reject path input outside intake names | Pass locally |
| Diagnostic privacy | Environment and socket diagnostics expose bounded constants only | Pass locally |
| Negative fixtures | Unsafe test inputs remain rejected without broad static-analysis exclusions | Pass locally |
| Alert ledger | `verify_github_security_posture.py --live` reports both open counts as zero | Pending merge |
| Independent audit | External human reviewer returns a signed, commit-bound report | Not started |

## S15 Decision

Merge only after the full test suite, generated-evidence checks, partial release
receipt, and protected GitHub checks pass. After merge, require a fresh
main-branch CodeQL analysis and run the live posture verifier. If any alert stays
open, reopen remediation instead of dismissing it for schedule reasons. Repin
external audit issue #414 to the resulting merge commit and regenerated package
hash only after the ledger is zero.
