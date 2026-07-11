# Independent Security Audit Report

## Engagement

- Repository: `jzvcpe-goat/study-anything`
- Scope commit: `<40-character commit SHA>`
- Auditor organization: `<external organization>`
- Lead human reviewer: `<name or stable reviewer id>`
- Review period: `<start>` to `<end>`
- Independence attested: `true`

## Scope And Method

List audited areas, excluded areas, environments, source-review methods,
negative tests, tools, and any constraints that reduced assurance.

## Executive Decision

Decision: `pass | conditional_pass | fail`

This decision applies only to the pinned commit and listed deployment target. It
is not a legal, compliance, model-correctness, or universal security certificate.

## Findings

| Finding ID | Severity | Status | Affected surface | Retest |
| --- | --- | --- | --- | --- |
| `<id>` | `<severity>` | `<status>` | `<surface>` | `<result>` |

Each finding must validate against
`external-security-audit-finding-v1.schema.json`. Keep private reproduction
details in the agreed secure channel.

## Residual Risk

Record every accepted residual risk, owner, expiry, compensating control, and
deployment limitation.

## Evidence

List the exact Protocol v1 version, audit-pack SHA-256, conformance-pack SHA-256,
audit-plan SHA-256, source commit, protected CI run links, SBOM hash, verification
commands, and finding or retest artifact hashes. The machine-readable report must use
the `evidence_bindings` object; changing any bound artifact requires a new signed report.

## Signature

Record the signature method, report SHA-256, detached signature reference, and signing
identity. `report_sha256` is the canonical SHA-256 of the machine-readable report with
the top-level `signature` object omitted. The detached signature covers those same
canonical bytes. The machine-readable report must validate against
`external-security-audit-report-v1.schema.json`. The receiving expected scope must pin
the independently verified Ed25519 public-key fingerprint before intake; a fingerprint
declared only inside the submitted envelope is not an identity trust root.
