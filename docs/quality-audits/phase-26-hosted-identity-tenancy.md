# Phase 26 Hosted Identity And Tenancy Audit

Audit date: 2026-07-10 PDT

Scope: add an optional hosted OIDC identity boundary, application-layer tenant
isolation, workspace authorization, and principal-scoped Agent providers without
changing the local-first default.

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

- Phase 26 application-layer foundation: **Pass for merge after protected CI**.
- Local-first and self-hosted modes: **Pass; existing no-account behavior is preserved**.
- Hosted paid production: **Needs Changes**. This phase is not a complete hosted
  identity service, database-enforced multitenancy proof, or security certification.

The implementation establishes a bounded identity and authorization foundation.
It does not authorize selling a multi-tenant hosted service yet.

## S0-S3 Source And Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Canonical base | Pass | `main` at `89180d1b`; work isolated on `codex/v0.3.286-hosted-identity-tenancy` |
| Product contract | Pass | Local-first remains the default; hosted identity is opt-in through `oidc_jwt` mode |
| Identity contract | Pass | Signed OIDC JWT, issuer, audience, subject, tenant claim, age, and lifetime are validated before a hosted request reaches a route |
| Tenant contract | Pass at application layer | Sessions, workspaces, HITL tasks, system views, and non-demo Agent providers are filtered by the derived tenant or principal scope |
| Claim boundary | Pass | Public docs and readiness evidence say `application_layer_foundation`, not hosted production readiness or certification |

## S4-S9 Data, Protocol, Security, And Privacy

| Area | Result |
| --- | --- |
| Trust material | Static operator-supplied JWKS only; no automatic network fetch, private JWK fields, secrets, or raw claims in public responses |
| JWT policy | Fixed `RS256`/`ES256`, required `kid`, bounded JWKS size/key count, issuer/audience/time validation, and unsupported critical-header rejection |
| Principal binding | Opaque principal and tenant identifiers bind issuer, tenant claim, and subject; body/query user identifiers cannot override hosted identity |
| Session isolation | Cross-tenant session and workspace lookups return `404`; same-tenant permission denial returns `403` |
| Workspace authorization | Owner, editor, and viewer permissions are enforced server-side; viewer mutation is denied |
| Retrieval authorization | Creating or expanding a session from retrieval requires read access to the source workspace |
| Agent isolation | Non-demo providers and defaults are scoped to the authenticated principal; endpoints and scope identifiers stay out of public status payloads |
| Storage | In-memory, JSON, and Postgres stores accept tenant filters; Postgres persists and indexes `tenant_id` |
| Compatibility | Workspace v1 data has a bounded v2 migration path; local-only and token modes remain available |
| Unsupported hosted surfaces | Routes that are not tenant-scoped are blocked in hosted mode instead of being exposed globally |
| Privacy | Verifiers use ephemeral keys and metadata-only receipts; no model calls, user credentials, raw learning bodies, or production mutation |

Application filtering is defense in depth, not a substitute for database-enforced
row policies. A production multi-tenant service still needs an independent test
against the deployed database, network, identity provider, and operations stack.

## S10-S13 Commercial, Operations, UI, And Legacy

- No payment or entitlement claim is added. Hosted Sync, Teams, and other paid
  services remain `not_ready` in commercial-readiness evidence.
- `.env.example`, Compose, self-hosting, security, architecture, API, Agent,
  positioning, and release documentation use the same hosted boundary.
- There is no standalone frontend in scope, so UI and design-system review is not
  applicable to this backend security phase.
- Deprecated model aliases remain compatibility surfaces; they route through the
  scoped Agent registry rather than bypassing identity or tenant checks.
- Production prerequisites still include managed account lifecycle and recovery,
  JWKS rotation and refresh operations, database-enforced isolation, retention and
  deletion workflows, backup/restore rehearsal, rate limiting, monitoring, and
  incident response.

## S14 Automated Evidence

| Gate | Result |
| --- | --- |
| Hosted identity, environment, container, Agent, store, workspace, and readiness focused tests | Pass; 82 tests during implementation, then 14 authorization-focused, 29 Agent/retrieval, and 19 store/tenant regression tests after review fixes |
| Full API suite | Pass; 930 tests, one existing Starlette/httpx deprecation warning |
| Ruff | Pass on the full configured Python surface |
| Strict mypy | Pass for hosted identity, workspace, API security, and hosted verifier targets |
| `verify_hosted_identity_tenancy.py --check` | Pass; identity spoofing, cross-tenant access, RBAC, Agent scope, and blocked unscoped routes covered |
| `verify_agent_endpoint_policy.py --check` | Pass; Phase 25 exact-origin egress policy remains enforced |
| `generate_python_supply_chain.py --check` | Pass; hosted dependency is lockfile, hash export, policy, and SBOM covered |
| Generated evidence topology | Pass; 20 generated-evidence checks converged after refresh |
| `release_check.sh --skip-clean-clone` | Pass with exit 0; explicitly partial, not a full release validation |
| Protected GitHub checks | Pending PR |

The release receipt records:

```text
full_release_check_completed=false
clean_clone_completed=false
dependency_install_completed=false
dual_loop_verifiers_passed_individually=true
exit_code=0
```

Its claim boundary is authoritative: clean-clone adoption was skipped, so this
evidence must not be described as a complete `release_check.sh` pass.

One targeted pytest invocation omitted the repository test-helper path and failed
during collection with no tests executed. The command was corrected with the
repository `PYTHONPATH`; the resulting 14-test run passed. The collection failure
is not counted as product evidence.

The first GitHub `container policy` run reached the hosted verifier but failed
before executing it because the minimal policy environment did not install the
optional LangGraph runtime. The verifier was corrected to select the deterministic
workflow explicitly, matching its authorization-only scope; this is a harness
dependency fix, not a weakened identity or tenancy assertion.

The next CodeQL scan identified two high-severity path-injection flows from the
session route into the JSON store. They were treated as real findings: JSON-backed
session filenames now require a canonical UUID and pass a resolved-root containment
check, with traversal, absolute-path, nested-path, and non-UUID negative tests.

## Acceptance Matrix

| Area | Minimum Passing Condition | Status |
| --- | --- | --- |
| Identity | Invalid or missing hosted JWT fails closed; body identity spoofing is ignored | Pass |
| Tenant isolation | Cross-tenant session, workspace, HITL, system, and Agent reads do not disclose another tenant | Pass at application layer |
| Authorization | Same-tenant workspace writes require server-side permission | Pass |
| Local-first compatibility | Default local mode requires no hosted identity provider | Pass |
| Supply chain | Hosted auth dependency is locked, hashed, exported, and inventoried | Pass |
| Release gate | Hosted verifier blocks security CI and the release tail | Pass locally; CI pending |
| Database isolation | Deployed database independently enforces tenant boundaries | Not implemented |
| Identity operations | Managed provisioning, recovery, revocation, JWKS rotation, and outage handling exist | Not implemented |
| Production operations | Rate limits, alerts, retention/deletion, backup/restore, and incident exercises are proven | Not proven |
| Independent security audit | External auditor executes the agreed scope and returns accepted findings | Not started |

## S15 Decision

Merge Phase 26 only after protected GitHub checks pass. Its accepted claim is:

> Study Anything has an opt-in, deterministic, application-layer hosted identity
> and tenant-isolation foundation with server-side authorization and scoped Agent
> providers.

Do not claim that hosted paid production, complete tenant isolation, penetration
testing, or security certification is complete. The next engineering phase must
package an external audit scope and evidence set while preserving an explicit
human-auditor checkpoint; the repository cannot self-award an independent audit.
