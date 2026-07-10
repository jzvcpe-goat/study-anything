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
- Production or non-loopback exposure requires
  `STUDY_ANYTHING_API_AUTH_MODE=token` and a strong
  `STUDY_ANYTHING_API_TOKEN`. The CLI reads that token from its environment or
  the private `.env` file and sends it in the `Authorization` header, never in a
  URL.
- Token mode is an operator boundary for a private self-host. It is not hosted
  account authentication, tenant isolation, SSO, or a Teams security claim.

Verify this boundary with:

```bash
python3 scripts/verify_local_api_security.py --check
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

## Release Gate

Run the security recovery gate before publishing an alpha:

```bash
python3 scripts/verify_security_recovery_hardening.py
python3 scripts/verify_local_api_security.py --check
python3 scripts/verify_container_security.py --check
```

The container and GitHub Actions baseline is documented in `docs/security-baseline.md`. The API and
mock Agent use a fixed non-root runtime identity, read-only root filesystems, dropped capabilities,
and `no-new-privileges`. GitHub Actions are full-SHA pinned, with CodeQL and dependency review in a
separate security workflow.

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
