# AI Delivery Clearance Protocol

Delivery Clearance is an open receipt protocol for scoped AI delivery clearance.
It defines how a specific AI-generated candidate may move
from private experimentation into a controlled handoff without treating model
confidence, AI self-review, or generic human approval as the final trust root.

**未经放行，不得交付。**

**Delivery Clearance does not prove that AI is always correct. It proves why this
delivery may move forward, to whom, for what purpose, within what limits, and under
whose responsibility.**

**AI 交付放行协议不证明 AI 永远正确；它证明这次交付为什么可以继续向前、可以交给谁、
可以用于什么、受到哪些限制，以及由谁承担责任。**

The existing `cbb.*` Protocol v1 schemas and CBB code namespace remain stable
compatibility identifiers for this reference implementation. They are not the public
product name.

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

## Canonical V1 Contract Layer

Protocol v1 defines six strict canonical objects,
deterministic `cbb-json-c14n-v1` bytes, and scope-narrowing adapters from the shipped
Dual Loop and Delivery Trust v0 artifacts. Existing script, schema, package, and
artifact names remain supported.

The canonical contracts feed a deterministic Trust Kernel evaluator.
The evaluator enforces hard denies, blocking evidence, reviewer reconstruction,
reference integrity, and monotonic scope ceilings without model, RAG, network, or
tool authority. Local Ed25519 provenance binds those objects with expiry, optional
replay consumption, supplied-registry revocation, and tamper checks. Scenario policy
adds scoped recipients, risk owners, affected parties, safeguards, MRUs, and
challengeable human/model capability profiles without adding another core receipt.
Outcome degradation and isolated Agentic evidence discovery remain later milestones.
See
[Protocol v1 Canonical Contracts](cbb-protocol-v1-contracts.md) and
[Protocol v1 Deterministic Trust Kernel](cbb-protocol-v1-kernel.md), and
[Protocol v1 Local Provenance](cbb-protocol-v1-provenance.md), and
[Protocol v1 Scenarios And Qualification](cbb-protocol-v1-scenarios-and-qualification.md).

## Current Verifier Commands

```bash
python3 scripts/verify_cbb_positioning.py --check
python3 scripts/verify_cbb_v1_contracts.py --check
python3 scripts/verify_cbb_v0_compatibility.py --check
python3 scripts/verify_cbb_v1_kernel.py --check
python3 scripts/verify_cbb_runtime_isolation.py --check
python3 scripts/verify_cbb_v1_provenance.py --check
python3 scripts/verify_cbb_v1_tamper_cases.py --check
python3 scripts/verify_cbb_v1_scenarios.py --check
python3 scripts/verify_cbb_v1_qualification.py --check
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
defined in [Protocol v1 Development Plan](cbb-protocol-v1-development-plan.md).
