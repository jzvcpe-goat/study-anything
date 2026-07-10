# Rules Of Engagement

## Independence

- The lead reviewer must be outside the implementation team for the scoped
  commit and attest that independence in the signed report.
- AI tools may assist analysis, but AI-only review is not sufficient evidence.
- Repository maintainers may answer questions and remediate findings; they may
  not sign the independent decision on behalf of the auditor.

## Allowed Targets

- A pinned local clone or disposable test environment.
- An explicitly authorized isolated staging deployment with synthetic data.
- Public repository and release artifacts named by the audit plan.

Production systems, real customer accounts, and third-party Agent or identity
provider infrastructure are excluded unless separately authorized in writing.

## Allowed Methods

- Source and configuration review.
- Dependency and SBOM review.
- API authorization and negative-path tests with synthetic identities.
- Container, filesystem, archive, plugin, and egress-boundary testing.
- Bounded fuzzing and concurrency tests that do not create denial of service.
- Receipt, checksum, and generated-evidence integrity validation.

## Prohibited Methods

- Destructive tests, persistence, social engineering, or credential harvesting.
- Denial of service, unbounded load, or scanning unrelated networks.
- Real secrets, cookies, bearer tokens, signed URLs, or customer payloads.
- Publishing exploit details before remediation and disclosure approval.
- Production mutation or customer-visible actions.

## Finding Handling

Critical and high findings must be reported through the private contact channel
within one business day. Public tracking uses a redacted finding ID, severity,
affected surface, status, and remediation commit only. Private exploit material
must not enter repository issues, CI logs, or generated packs.

## Completion

The engagement is complete only when the auditor provides a signed report bound
to an exact commit, the report validates against the repository schema, all
critical and high findings are closed and retested, and residual risks have a
named owner and expiry. Pack generation alone cannot satisfy this condition.
