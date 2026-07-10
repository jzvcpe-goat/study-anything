# Phase 25 Dependency And Agent Egress Audit

Audit date: 2026-07-10 PDT

Scope: disposition the remaining low Dependabot advisory and make HTTP Agent
destinations explicit, bounded, diagnosable, and release-gated.

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

- Agent target policy: **Pass for local-first and configured private deployments**.
- Low Dependabot advisory: **time-bounded tolerable risk; not fixed or dismissed as a false positive**.
- Hosted or commercial production: **Needs Changes** for identity, tenant isolation,
  network-layer egress enforcement, operations, and independent security audit.

## S0-S3 Source And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | Clean `main` at `b993ec56`; work isolated on `codex/v0.3.285-security-closure` |
| Advisory identity | Pass | `GHSA-866g-f22w-33x8`, low severity, transitive `@ai-sdk/provider-utils` v3.0.25 alias |
| Remediation availability | Unavailable upstream | Mastra's current compatibility dependency retains the same alias and the advisory has no patched v3 release |
| Claim boundary | Pass | Acceptance states tolerable risk with expiry; it does not claim a fix, false positive, or vulnerability-free repository |

## S4-S9 Security, Privacy, And Integrity

| Area | Result |
| --- | --- |
| Advisory reachability | Runtime has no direct import, affected response-handler call, model call, external response parsing, or public daemon path |
| Advisory expiry | `review_by=2026-08-10`; scheduled security and release gates fail after expiry or reachability change |
| Agent registration | Production requires a non-empty exact-origin allowlist; paths, queries, fragments, credentials, and non-loopback HTTP are rejected |
| Agent invocation | Endpoint origin is checked immediately before each request; redirects are rejected |
| Existing providers | Persisted HTTP providers outside the active policy are disabled with a generic migration warning |
| Status privacy | Returns policy mode, origin count, and redirect state; configured origins and environment values are not returned |
| Compose | Policy and allowlist variables are passed into the API container |
| Preflight | `check_env.py` emits redacted, machine-readable remediation codes before launch |

The exact-origin policy is not a complete hosted SSRF certification. A hosted
operator must additionally constrain network egress and review DNS, proxy, and
allowed-gateway compromise scenarios.

## S10-S13 Operations And Documentation

- `.env.example`, self-hosting, security, Agent contract, and unreleased notes use
  the same `operator` versus `allowlist` vocabulary.
- Local development remains copy-paste friendly. Production fails closed until an
  explicit allowlist is present.
- The policy verifier performs no model calls, external network requests, secret
  reads, or production mutation.
- Hosted identity and tenant isolation remain explicitly outside this phase.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| Focused Agent, environment, API-security, container, and advisory tests | Pass; 86 tests |
| Full API suite | Pass; 913 tests, one existing Starlette/httpx deprecation warning |
| Ruff on changed Python surfaces | Pass |
| `verify_agent_endpoint_policy.py --check` | Pass |
| `verify_dependency_risk_acceptance.py --check` | Pass; 31 days until required review on audit date |
| `verify_container_security.py --check` | Pass; Compose policy passthrough verified |
| `release_check.sh --skip-clean-clone` | Pass; exit 0, 914 tests and all integrated gates passed, partial receipt only |
| Protected GitHub checks | Pending PR |

The first local pytest command did not execute because this isolated worktree had
no `.venv`. Tests were rerun with the canonical repository's locked Python 3.11
environment and an explicit repository `PYTHONPATH`; collection and all 86 tests
then completed. The failed launcher attempt is not counted as test evidence.

The first partial release attempt reached the final Skill Mode smoke and then
started a new worktree-local dependency install. It was terminated with exit 143
under the operator's skip-stalls rule and is not counted as a pass. The same
command was rerun with the already locked Python 3.11 environment, completed with
exit 0, and emitted a receipt that keeps `clean_clone_completed=false` and
`dependency_install_completed=false`.

## S15 Decision

Merge only after the branch release gate and protected GitHub checks pass. After
merge, dismiss Dependabot alert 1 as `tolerable_risk` with the review date and PR
evidence. Do not close it as fixed or inaccurate.

This phase closes the configurable Agent target boundary and formalizes the one
remaining low advisory. It does not complete hosted identity, tenant isolation,
network-layer egress policy, penetration testing, or commercial certification.
