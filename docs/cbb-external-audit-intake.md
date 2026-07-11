# External Audit Report Intake

External audit intake is the one-way boundary between repository audit preparation and
an independently executed human security assessment.

The repository can prepare and verify the channel; it cannot manufacture the auditor
or close its own audit.

## Distinct States

| State | Meaning |
| --- | --- |
| `audit_ready` | Exact scope is pinned; no external report has been received |
| `synthetic_validated` | Signature and state-machine fixture passed; no external audit occurred |
| `rejected` | Commit, signature, identity, scope, finding, or package binding failed |
| `audit_received` | A valid real report was received, but closure conditions remain |
| `remediation_pending` | Critical/high findings or a failing decision block closure |
| `audit_closed` | Only a real externally attested report can satisfy closure controls |

No repository fixture has `audit_closed`, `report_execution_completed`, or
`external_identity_attested` set to true. GitHub issue #414 remains the public execution
checkpoint.

## Signature And Identity

The detached Ed25519 signature covers canonical report bytes with the top-level
`signature` object omitted. `report_sha256` covers those same bytes. Verification proves
key possession and report integrity.

Identity is separate. A real intake requires a trust record whose organization, lead
human reviewer, fingerprint, and external independence attestation match the report.
The actual Ed25519 public-key digest must match that fingerprint, and the fingerprint
must already exist in the locally pinned `trusted_auditor_fingerprints` set in the
expected scope. An embedded key, a self-asserted organization, or an envelope-supplied
trust record alone is not external identity.

## Scope Binding

The signed report must bind:

- exact repository and 40-character commit;
- Protocol v1 version;
- audit-pack reference and SHA-256;
- conformance-pack reference and SHA-256;
- audit-plan reference and SHA-256;
- every required audit scope area;
- finding documents, counts, remediation, and retest state.

Wrong commits, incomplete scope, invalid signatures, and repository self-certification
are rejected. Open critical/high findings enter `remediation_pending`; risk acceptance
cannot close critical/high findings.

## Commands

```bash
python3 scripts/generate_cbb_adoption_audit_assets.py --check
python3 scripts/verify_cbb_external_audit_intake.py --check
python3 scripts/cbb_external_audit_intake.py ready \
  --expected-scope path/to/expected-scope.json \
  --evaluated-at 2026-07-14T00:00:00Z
python3 scripts/cbb_external_audit_intake.py evaluate \
  --expected-scope path/to/expected-scope.json \
  --envelope path/to/external-audit-envelope.json \
  --evaluated-at 2026-07-14T00:00:00Z
```

The intake CLI does not download reports, discover identities, modify production, or
change Delivery Clearance scope.

## Claim Boundary

Synthetic fixtures prove parsing, detached-signature verification, exact binding,
rejection behavior, and state separation. They do not prove that issue #414 was
executed, an external organization was assigned, a real report was received, findings
were remediated, or production is secure.
