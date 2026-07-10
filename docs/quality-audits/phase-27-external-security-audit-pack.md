# Phase 27 External Security Audit Pack Audit

Audit date: 2026-07-10 PDT

Scope: package the public security boundary, threat model, evidence catalog,
schemas, remediation policy, and verification commands for an independent
human-led audit without allowing repository self-certification.

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

- Audit preparation package: **Pass for merge after protected CI**.
- Independent security audit execution: **Needs Changes; external human checkpoint pending**.
- Hosted paid production: **Needs Changes** until a signed commit-bound external
  report exists and all critical or high findings are remediated and retested.

The accepted status is `ready_for_independent_audit`. `audit_passed`, penetration
test completion, vulnerability-free software, and production certification are
not accepted claims.

## S0-S3 Source And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | Clean `main` at `6deae58f`; work isolated on `codex/v0.3.287-external-security-audit-pack` |
| Product contract | Pass | The repository prepares evidence; an external human reviewer owns the audit decision |
| Scope contract | Pass | Seven areas cover identity/tenancy, API/container/filesystem, Agent egress, supply chain, plugin/backup/local data, Dual Loop trust, and CI/reliability |
| Independence contract | Pass | External auditor, human reviewer, signed report, exact commit, and no AI-only or repository self-certification |
| Claim boundary | Pass | Machine-readable status remains `ready_for_independent_audit` with `audit_completed=false` |

## S4-S9 Data, Protocol, Security, And Privacy

| Area | Result |
| --- | --- |
| Threat model | Assets, actors, seven trust boundaries, twelve abuse cases, and repository-only exclusions are explicit |
| Rules of engagement | Limits testing to a pinned clone or authorized isolated staging; prohibits production mutation, destructive testing, credential harvesting, and unrelated scanning |
| Finding protocol | `external-security-audit-finding-v1` requires severity, commit, metadata evidence hashes, owner, remediation target, retest, and safe public privacy flags |
| Report protocol | `external-security-audit-report-v1` requires an external organization, lead human reviewer, independence attestation, exact commit, finding counts, decision, and detached signature metadata |
| Remediation | Critical/high SLAs block hosted launch and require external retest; medium findings require owner, treatment, and deadline |
| Archive integrity | One safe ZIP root, deterministic timestamps, per-file SHA-256, sidecar SHA-256, source/archive byte equality, and path traversal rejection |
| Privacy | Pack excludes real secrets, cookies, bearer tokens, signed URLs, user Agent credentials, raw learner/source data, production payloads, screenshots, raw logs, and private exploit details |
| Negative claim test | A mutated package with `status=audit_passed` and `audit_completed=true` is rejected |

The pack contains public documentation and metadata evidence only. Source review
and active negative testing occur in a separate pinned repository checkout. Any
sensitive reproduction material must use the private vulnerability channel.

## S10-S13 Commercial, Operations, UI, And Legacy

- Commercial readiness now exposes `security_audit_status=ready_for_independent_audit`
  and `security_audit_completed=false`; hosted paid services remain `not_ready`.
- Security CI and the release gate run both the generator freshness check and
  verifier. The generated evidence topology owns the audit pack as a dependency
  of the platform bundle and adoption pack.
- The adoption pack contains the audit `.json`, `.md`, `.zip`, and `.sha256`
  assets so an external operator can retrieve the same bounded package.
- A GitHub issue form coordinates the engagement using redacted metadata only.
  It explicitly says opening or closing an issue is not an audit pass.
- No standalone UI or payment flow is introduced in this phase.
- No prior audit receipt is migrated or presented as external evidence.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| Audit pack unit tests | Pass; 4 deterministic, archive, self-certification, and offline verification tests |
| Focused audit/readiness/container/topology tests | Pass; 31 tests |
| Full API suite | Pass; 934 tests, one existing Starlette/httpx deprecation warning |
| Ruff and Python compilation | Pass on changed Python surfaces |
| Strict mypy | Pass for commercial readiness, audit generator, audit verifier, and readiness verifier |
| `verify_external_security_audit_pack.py --check` | Pass; 7 scope areas, 27 files, 29 archive entries, one safe root, SHA-256 `a2ab7821fe008e67c17e74cd0b5899a2a50901cc62d1b6285bc6535ca72a6d8c` |
| Generated evidence topology | Pass; 21/21 nodes and 27 hard dependencies; refresh converged, final release check was stable |
| Platform adoption pack | Pass; contains all four external audit pack release assets |
| `release_check.sh --skip-clean-clone` | Pass with exit 0; explicitly partial, not full release validation |
| Protected GitHub checks | Pending PR |

The release receipt records:

```text
full_release_check_completed=false
clean_clone_completed=false
dependency_install_completed=false
exit_code=0
```

Its claim boundary is authoritative: clean-clone adoption was skipped, so the
result cannot be described as a complete `release_check.sh` pass.

## Acceptance Matrix

| Area | Minimum Passing Condition | Status |
| --- | --- | --- |
| Package integrity | Deterministic archive, sidecar digest, per-file hashes, one safe root | Pass |
| Scope | Seven security areas and executable evidence commands | Pass |
| Independence | External human reviewer, signed report, exact commit, no self-certification | Pass as contract |
| Privacy | No secret, customer, learning, local-path, raw-log, or exploit payload in pack | Pass |
| Distribution | Bundle and adoption pack contain the public audit assets | Pass |
| CI | Security workflow and release gate block stale or invalid audit packs | Pass locally; CI pending |
| Audit execution | External reviewer performs source review and negative testing | Not started |
| Findings | Critical/high findings closed and independently retested | No external findings yet |
| Signed report | Schema-valid report and detached signature returned | Not available |
| Hosted commercial launch | Identity operations, DB isolation, production controls, and external audit all complete | Not ready |

## S15 Decision

Merge Phase 27 only after protected GitHub checks pass. After merge, open a
public redacted coordination issue using the new template and attach the audit
pack SHA-256 plus the exact scope commit. The issue must stay open until an
independent reviewer returns a signed report and required retests.

This phase completes audit readiness, not the audit. The repository must not
change `audit_completed` or hosted commercial readiness based on its own CI,
CodeQL, AI review, or quality-audit document.
