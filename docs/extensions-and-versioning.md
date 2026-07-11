# Extensions And Version Negotiation

The eight `cbb.*.v1` objects are the bounded canonical Protocol v1 surface. Extensions
may add metadata or domain evidence but may not silently alter Trust Kernel authority.

## Extension Rules

An extension record must declare:

- a globally distinguishable `extension_id`;
- owner and specification reference;
- version and compatibility range;
- whether it is informational or evidence-bearing;
- explicit `claims_authority: false` unless promoted through protocol governance;
- unknown-extension handling;
- privacy and claim boundaries.

Protocol v1 recognizes informational extensions only. They can be preserved, displayed,
or ignored. They cannot:

- change `approved_scope` or a claim-boundary ceiling;
- add, remove, or override a hard deny;
- satisfy required evidence or qualified reconstruction by themselves;
- alter signature, canonicalization, expiry, replay, or revocation behavior;
- authorize tool calls, policy mutation, production mutation, or customer sending.

An unknown informational extension is preserved or ignored. An unknown extension that
claims any authority fails closed.

## Version Negotiation

A consumer compares the requested `major.minor.patch` with its supported version:

1. exact supported version: accept;
2. supported major with an unknown newer minor or patch: reject until declared compatible;
3. different major: reject;
4. v0 identifier with an explicit migration map: compatibility-only, never canonical;
5. malformed or absent version: reject.

Negotiation cannot promote a lower-scope or compatibility-only receipt. Consumers must
record the selected protocol version and conformance-pack digest in their output.

## Current Registry

The v1 conformance pack contains the machine-readable registry. The initial registered
entry is a non-authoritative fixture metadata extension used to exercise interoperability.
Registration is not endorsement.

## Claim Boundary

Extension support proves parsing and bounded handling only. It does not delegate protocol
authority, certify a vendor, or permit scope expansion.
