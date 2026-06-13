# Security Model

Study Anything is a local-first learning layer for platform Agents. The security
model is intentionally narrow: Study Anything orchestrates learning state,
contracts, validation, audit events, and local exports; user-owned Agents keep
real model credentials, tools, browser access, and external data access outside
the Study Anything database.

## Trust Boundaries

- Study Anything stores learning sessions, source references, mastery state,
  aggregate PMF metrics, plugin metadata, and local configuration needed to run
  the API.
- Study Anything must not store real model API keys, bearer tokens, cookies,
  signed URLs, or platform Agent credentials.
- HTTP Agent provider records may include a local or private endpoint, declared
  capabilities, and non-secret metadata only.
- Plugin preview and quarantine must validate manifests without importing or
  executing plugin entrypoints.
- Optional graph and retrieval projections are derived from Postgres. They must
  not become the source of truth.

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
```

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

## Reporting

Do not file public issues for vulnerabilities, leaked secrets, or
privacy-impacting bugs. Use the private advisory channel or contact the
maintainers listed in `SECURITY.md`.
