# Delivery Class Registry

The Delivery Class Registry is the public index of delivery types that have been
mapped into the Dual Loop / Delivery Trust protocol.

It is intentionally small. The registry does not create a new frontend, does
not send work to customers, does not certify legal or financial correctness, and
does not prove that every AI output is true. It proves a narrower thing: each
listed delivery class has metadata-only evidence, pass and blocked fixtures,
claim boundaries, negative checks, and release-gate coverage.

## Current Delivery Classes

- Code Review Handoff: a controlled handoff for AI-assisted code review output.
- Client Report Handoff: a controlled handoff for AI-assisted report or memo
  output.
- Support Response Handoff: a controlled handoff for AI-assisted support reply
  drafts before any requester-visible send.

Each delivery class must include:

- a deterministic verifier;
- a JSON report and static HTML report;
- a schema file;
- deterministic pass and blocked fixtures;
- negative checks for unsafe shortcuts;
- release-check integration;
- a metadata-only privacy boundary.

## Why This Exists

Single examples are easy to overclaim. A registry makes the product direction
more honest: a new delivery type is not accepted because the prose sounds good,
but because it fits the same contract as the existing classes.

The long-term product shape is a trust protocol for AI delivery. The registry is
the table of delivery classes that the protocol currently understands.

## Commands

Refresh generated reports:

```bash
python3 scripts/verify_delivery_class_registry.py --write
```

Verify the registry:

```bash
python3 scripts/verify_delivery_class_registry.py --check
```

The verifier rejects missing reports, missing fixtures, missing negative checks,
missing release-gate wiring, raw private payloads, model calls, production
mutation, and external publication.
