# Trust Scenario Catalog

The Trust Scenario Catalog turns the Dual Loop / Delivery Trust protocol into a
small, machine-checkable scenario table.

It answers a practical product question:

> For this kind of AI output, what is the highest safe handoff we can claim
> today, and what evidence must exist before that handoff is allowed?

The catalog is metadata-only. It does not include raw source text, report text,
customer payloads, screenshots, attention streams, secrets, model keys, or
user-owned Agent credentials. It does not call models, mutate production, send
messages, publish externally, or certify that an output is true.

## Why This Exists

Delivery classes prove that one type of handoff can be checked. A catalog proves
how the product thinks across several scenarios.

This matters because the core product goal is not "AI reviews AI" and not
"humans approve every step." The goal is controlled trust:

- AI failure stays inside a reversible sandbox.
- Humans actively reconstruct the key boundaries.
- The gate only allows handoff when both loops pass.
- Unsupported shortcuts are blocked before they become customer-visible claims.

## Current Scenario Types

Supported controlled handoffs:

- Controlled Code Review Handoff: advisory handoff to a maintainer or developer.
- Controlled Client Report Handoff: bounded handoff package for customer-visible
  report or memo work.

Blocked unsafe claims:

- Direct production mutation: blocked until converted into a reversible sandbox
  and controlled handoff.
- Certified truth claim: blocked because v0.1 receipts do not certify legal,
  financial, or general factual truth.

## Required Evidence

A supported scenario must have evidence from both sides of the Dual Loop:

- `failure-contract-v1`
- `sandbox-receipt-v1`
- `attention-reconstruction-trace-v1`
- `attention-reconstruction-summary-v1`
- `dual-loop-gate-receipt-v1`
- a delivery-specific case receipt

Customer-visible scenarios also need `customer-handoff-package-v1`.

The catalog treats passive attention as weak evidence. Supported scenarios must
include active reconstruction checkpoints for the failure boundary, risk budget,
and recipient scope.

## What The Catalog Blocks

The catalog rejects:

- automatic customer sending;
- automatic PR commenting or merge approval;
- production mutation;
- external publication;
- legal, financial, security, or truth certification claims;
- AI-review-only evidence;
- eval receipts used as sufficient proof;
- one loop dominating the other.

## Commands

Refresh generated reports:

```bash
python3 scripts/verify_trust_scenario_catalog.py --write
```

Verify the catalog:

```bash
python3 scripts/verify_trust_scenario_catalog.py --check
```

The verifier checks the catalog against the Delivery Class Registry, release
gate wiring, privacy boundaries, required Dual Loop artifacts, active
reconstruction checkpoints, and blocked unsafe claims.
