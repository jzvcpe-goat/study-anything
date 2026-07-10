# Security Model

Cognitive Black Box is a local-first trust harness for AI-generated
deliverables. Its security model is intentionally narrow: the repository
orchestrates metadata-only contracts, validation, audit events, local exports,
Dual-Loop gates, delivery trust receipts, and customer handoff packages;
user-owned Agents keep real model credentials, tools, browser access, and
external data access outside the repository database.

## Trust Boundaries

- Study Anything stores learning sessions, source references, mastery state,
  aggregate PMF metrics, plugin metadata, and local configuration needed to run
  the API.
- Dual-Loop, Delivery Trust, and CustomerHandoffPackage artifacts store
  structured refs, hashes, risk summaries, gate results, claim boundaries,
  rollback refs, and package manifests only.
- Study Anything must not store real model API keys, bearer tokens, cookies,
  signed URLs, or platform Agent credentials.
- AI eval evidence may support a delivery decision, but it must not become the
  sole trust authority.
- Full manual re-review is not the default gate; active human reconstruction of
  failure boundaries is the required human evidence.
- HTTP Agent provider records may include a local or private endpoint, declared
  capabilities, and non-secret metadata only.
- Plugin preview and quarantine must validate manifests without importing or
  executing plugin entrypoints.
- Optional graph and retrieval projections are derived from Postgres. They must
  not become the source of truth.

## Local API Boundary

- Docker publishes the API on `127.0.0.1` by default. Skill Mode already binds
  to loopback by default.
- Browser cross-origin access is disabled by default. Set
  `STUDY_ANYTHING_CORS_ORIGINS` only to an explicit comma-separated allowlist;
  wildcard and credentialed CORS are rejected.
- `STUDY_ANYTHING_API_AUTH_MODE=local_only` is for a single local operator. The
  `user_id` and workspace member fields are local labels, not authenticated
  multi-tenant identities.
- Production or non-loopback exposure requires either `token` mode with a strong
  `STUDY_ANYTHING_API_TOKEN`, or optional `oidc_jwt` mode with a fixed issuer,
  audience, tenant claim, and static public JWKS. The CLI reads a local operator
  token from its environment or private `.env` and never puts it in a URL.
- Token mode is an operator boundary for a private self-host. It is not hosted
  account authentication, tenant isolation, SSO, or a Teams security claim.
- OIDC mode validates signed short-lived JWTs offline and binds opaque principals
  to issuer, tenant, and subject. Sessions, workspaces, and non-demo Agent
  providers are application-scoped; unscoped local-operator routes are blocked.
  See `docs/hosted-identity-tenancy.md` for the exact matrix and limitations.

Verify this boundary with:

```bash
python3 scripts/verify_local_api_security.py --check
python3 scripts/verify_hosted_identity_tenancy.py --check
```

## Agent Egress Boundary

- Local single-operator deployments default to
  `STUDY_ANYTHING_AGENT_ENDPOINT_POLICY=operator`. This preserves Bring Your Own
  Agent flexibility, but it is not a hosted SSRF boundary.
- `APP_ENV=production` requires `allowlist` mode and a non-empty
  `STUDY_ANYTHING_AGENT_ENDPOINT_ALLOWLIST` containing comma-separated exact
  origins. Paths, queries, fragments, and credentials are rejected.
- Non-loopback allowlist entries must use HTTPS. The selected endpoint is checked
  during registration and immediately before invocation.
- HTTP Agent redirects are rejected so an allowed gateway cannot redirect a
  request to a different destination. Status responses expose only policy mode
  and origin count, never the configured origins.
- Hosted operators should additionally enforce network-level egress controls.
  This policy does not certify a compromised allowed gateway or malicious DNS as
  safe.

Verify this boundary with:

```bash
python3 scripts/verify_agent_endpoint_policy.py --check
```

## Recovery And Backup

Local operators should create a backup before image upgrades, plugin installs,
or environment changes:

```bash
python3 scripts/self_host_data.py backup
```

Backup manifests are checksum verified and reject unsafe member paths including
absolute paths, backslashes, duplicate records, missing files, invalid digests,
and path traversal. The backup may include a private `env.snapshot`; keep backup
directories outside synced public folders.

Before changing real volumes, rehearse rollback in disposable Docker resources:

```bash
python3 scripts/verify_backup_restore_drill.py
```

Encrypted sync packages are portable state packages protected by a
user-supplied passphrase. Study Anything does not store that passphrase.
`/v1/sync/restore-preview` is deliberately non-destructive and must return only
counts, hashes, conflicts, warnings, and restore feasibility. It must not return
source text, learner answers, insights, Agent endpoints, secrets, or absolute
backup paths.
Imported packages reject KDF iteration counts above the supported ceiling before
key derivation, preventing a crafted package from consuming unbounded local CPU.

## Release Gate

Run the security recovery gate before publishing an alpha:

```bash
python3 scripts/verify_security_recovery_hardening.py
python3 scripts/verify_local_api_security.py --check
python3 scripts/verify_container_security.py --check
python3 scripts/verify_dependency_risk_acceptance.py --check
python3 scripts/verify_agent_endpoint_policy.py --check
python3 scripts/verify_hosted_identity_tenancy.py --check
python3 scripts/generate_external_security_audit_pack.py --check
python3 scripts/verify_external_security_audit_pack.py --check
python3 scripts/generate_python_supply_chain.py --check
```

The external audit kit lives under `security/audit/` and is distributed as
`platform/generated/study-anything-external-security-audit-pack.zip`. The pack
contains only public metadata, schemas, hashes, and evidence. It requires an
external human security reviewer and a signed report bound to an exact commit.
Generating or verifying the pack does not complete the audit.

The container and GitHub Actions baseline is documented in `docs/security-baseline.md`. The API and
mock Agent use a fixed non-root runtime identity, read-only root filesystems, dropped capabilities,
and `no-new-privileges`. GitHub Actions are full-SHA pinned, with CodeQL and dependency review in a
separate security workflow.

Python application dependencies are resolved in the universal `uv.lock` for the tested Python 3.11
and 3.12 range. Docker, CI, policy jobs, and Skill Mode consume generated requirements with exact
versions and SHA-256 hashes. The CycloneDX inventory and metadata-only receipt are documented in
`docs/python-supply-chain.md`. Hash-bound installation reduces resolver drift and package replacement
risk; it is not a vulnerability-free claim or a substitute for dependency review.

This verifier proves:

- backup tamper detection;
- path traversal rejection;
- invalid manifest record rejection;
- wrong-passphrase diagnostics without secret echoing;
- restore-preview privacy;
- destructive restore API disabled by default;
- disposable backup/restore drill coverage in the release checklist.

The full release gate also runs this verifier:

```bash
./scripts/release_check.sh
```

The release gate also requires the Dual-Loop and Delivery Trust gates:

```bash
python3 scripts/verify_dual_loop_gate.py --check
python3 scripts/verify_delivery_trust_receipt.py --check
python3 scripts/verify_customer_handoff_package.py --check
```

## Reporting

Do not file public issues for vulnerabilities, leaked secrets, or
privacy-impacting bugs. Use the private advisory channel or contact the
maintainers listed in `SECURITY.md`.
