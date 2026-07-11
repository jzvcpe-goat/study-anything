# Protocol Governance

Delivery Clearance is an open protocol with a reference harness. The repository is a
maintainer, not the sole source of trust.

## Change Classes

| Change | Required evidence |
| --- | --- |
| Editorial clarification | Rationale, affected docs, no semantic-change statement |
| Informational extension | Registered namespace, non-authority declaration, vectors |
| Backward-compatible schema addition | Version negotiation, positive and negative vectors |
| Canonical schema or Trust Kernel change | Migration, rollback, negative fixtures, conformance update, Evolution Receipt |
| Hard-deny, authority, signing, or revocation change | Protected change; cannot be locally auto-approved |

Every authoritative change must include:

1. an explicit problem and scope;
2. old-to-new migration behavior that never silently expands delivery scope;
3. rollback or deprecation behavior;
4. positive, negative, stale, tamper, and privacy fixtures as applicable;
5. reference and second-consumer conformance results;
6. `cbb.evolution-gate-receipt.v1` evidence;
7. a human maintainer decision separate from the proposer;
8. a security-impact and claim-boundary review.

The Evolution Receipt records only a local candidate. It never applies a protocol
change, grants delivery authority, or replaces maintainer review.

## Versioning And Deprecation

Protocol versions use `major.minor.patch`:

- major: incompatible canonical meaning or authority boundary;
- minor: backward-compatible canonical additions;
- patch: clarifications or verifier fixes that do not change valid receipt meaning.

Canonical schemas remain identified by exact `schema_version` strings. Deprecation must
publish an end date, replacement, migration map, rollback path, and negative fixture.
Compatibility aliases remain scope-narrowing and may not masquerade as canonical names.

## Decision Process

Normative changes require a public proposal, named maintainer review, conformance
evidence, security review, and a recorded disposition. Material disagreement is retained
in the proposal record rather than rewritten as consensus.

No model, Agent, vendor, signer, or maintainer may self-certify production trust. The
protocol must continue to distrust its own memory, receipts, implementations, and
governance claims.

## Security Disclosure

Security reports follow [SECURITY.md](../SECURITY.md). Public issues must not contain
unpatched exploit details, real secrets, private keys, customer payloads, or personal
data. Independent audit status remains separate from repository CI and conformance.

## Claim Boundary

Repository governance records protocol maintenance. They are not legal certification,
regulatory approval, production authorization, or proof that the protocol is immune to
capture or implementation defects.
