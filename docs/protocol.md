# Cognitive Black Box Protocol

Cognitive Black Box Protocol, or CBB Protocol, is an open receipt protocol for
scoped AI delivery trust. It defines how a specific AI-generated candidate may move
from private experimentation into a controlled handoff without treating model
confidence, AI self-review, or generic human approval as the final trust root.

The protocol governs release, not every thought. Low-impact drafting can remain
lightweight. Evidence requirements increase when a result reaches a new recipient,
new affected party, larger blast radius, irreversible effect, or higher delivery
scope.

## Protocol Constitution

These invariants form the stable Trust Kernel:

1. No receipt, no release.
2. No declared boundary, no trust claim.
3. No evidence, no promotion.
4. No risk owner for consequential delivery, no handoff.
5. AI self-review is supporting evidence, never the final trust root.
6. Human approval without qualified boundary reconstruction is insufficient.
7. Creation permission is not delivery permission.
8. A package cannot expand the scope allowed by its source receipt.
9. Protocol evolution cannot authorize its own hard-boundary change.
10. Every claim must be scoped, attributable, reproducible, and revocable.

## Core Objects

### Trust Policy

Declares the delivery scenario, allowed scope, hard denies, risk budget, required
evidence, reviewer qualification, risk owner, affected-party handling, rollback, and
receipt expiry.

### Evidence Bundle

Binds typed evidence to the candidate and policy. Evidence may include sandbox,
tests, rollback, provenance, external eval, human reconstruction, recipient scope,
and outcome history. Model-generated evidence remains untrusted until a typed
collector and verifier validate it.

### Qualified Reconstruction

Records whether a person with the required scope qualification can reconstruct the
minimum control boundary:

- what the candidate does and does not do;
- how it may fail;
- where failure must stop;
- who may be affected;
- what triggers rollback;
- which claim remains unproven.

Passive attention is weak evidence. It may route focus, but cannot by itself pass a
high-scope gate.

### Deterministic Gate Decision

The Trust Kernel evaluates policy and typed evidence without model calls. Agentic
components may discover boundaries, plan evidence collection, call tools, or draft
receipts. They cannot issue the final deterministic decision.

### Delivery Trust Receipt

A receipt binds:

- subject digest;
- policy digest;
- evidence bundle digest;
- gate decision and allowed scope;
- reviewer and risk-owner references;
- recipient and affected-party scope;
- limitations, rollback, expiry, and claim boundary;
- verifier identity, timestamp, and provenance.

An unsigned development receipt is a note, not a portable trust attestation.

### Customer Handoff Package

Packages an already allowed receipt and referenced evidence for a downstream human,
Agent, or system. It never creates trust, expands scope, or converts controlled
handoff into production approval.

### Outcome And Evolution Receipts

The protocol must learn from reality and distrust its own history. A later outcome
receipt may confirm, degrade, revoke, or require replay of a trust recipe. A policy
or recipe update is a proposal until an evolution gate verifies it through replay,
canary, rollback, and an explicit claim boundary.

## Two-Speed Architecture

### Stable Trust Kernel

- schemas and canonicalization;
- hard denies and scope ordering;
- deterministic gate evaluation;
- digest, signature, expiry, and revocation checks;
- audit trail and claim-boundary enforcement.

The kernel does not call models, read untrusted RAG as truth, or rewrite itself.

### Adaptive Evolution Layer

- scenario classification;
- evidence planning and typed function calls;
- RAG over quarantined receipt and failure memory;
- model and human capability evidence;
- trust-recipe proposals;
- anomaly, incident, and counter-evidence discovery.

This layer can become more capable over time, but its output remains proposal or
evidence until the Trust Kernel and required humans verify it.

## Reference Implementation Boundary

This repository implements a deterministic local reference harness. Current receipts
are metadata-only and keep production mutation, automatic customer sending, raw
customer payloads, model keys, hidden reasoning, and irreversible external effects
outside the default boundary.

The reference harness does not claim production readiness, legal or security
certification, regulatory approval, customer outcome guarantees, or general model
correctness. Independent human security review remains external to repository CI.

## Current Verifier Commands

```bash
python3 scripts/verify_cbb_positioning.py --check
python3 scripts/verify_cbb_protocol_contracts.py --check
python3 scripts/verify_cbb_gate.py --check
python3 scripts/verify_cbb_receipt_chain.py --check
python3 scripts/verify_cbb_self_intake.py --check
python3 scripts/verify_cbb_delivery_harness.py --check
./scripts/release_check.sh --cbb-protocol-only
```

`--cbb-protocol-only` is partial verification. It must never be described as a full
release validation.

The ordered work needed to converge the existing receipt family into Protocol v1 is
defined in [CBB Protocol v1 Development Plan](cbb-protocol-v1-development-plan.md).
