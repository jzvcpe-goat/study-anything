# Architecture / 架构

## Architectural Identity

Cognitive Black Box is protocol-first. The protocol defines portable trust contracts;
this repository supplies one deterministic local reference harness; adapters connect
existing learning, coding, review, and Agent workflows.

认知黑箱以协议为第一层。协议定义可携带的信任契约；本仓库提供一个确定性、本地优先
参考实现；适配器负责连接学习、编码、审查和 Agent 工作流。

```text
CBB Protocol
  -> CBB Reference Harness
      -> Adapters and evidence collectors
          -> Study Anything
          -> Cognitive Loop workflows
          -> Platform Agents
          -> CI, scanners, evals, and external reviewers
```

The protocol is the stable public contract. The harness and adapters may evolve or be
replaced without changing what a valid receipt means.

## System Layers

```text
┌──────────────────────────────────────────────────────────────┐
│ Protocol and Conformance                                    │
│ schemas, canonicalization, compatibility, conformance tests │
├──────────────────────────────────────────────────────────────┤
│ Deterministic Trust Kernel                                  │
│ hard denies, scope ordering, gate, expiry, revocation       │
├──────────────────────────────┬───────────────────────────────┤
│ Controlled Failure Loop      │ Human Reconstruction Loop     │
│ sandbox, tests, rollback     │ attention, MRU, qualification │
├──────────────────────────────┴───────────────────────────────┤
│ Receipt and Provenance Layer                                │
│ evidence bundle, digests, signatures, receipt chain         │
├──────────────────────────────────────────────────────────────┤
│ Delivery and Outcome Layer                                  │
│ handoff package, outcome receipt, degradation, revocation   │
├──────────────────────────────────────────────────────────────┤
│ Adaptive Evolution Layer                                    │
│ RAG, typed tools, Agentic planning, recipe proposals        │
├──────────────────────────────────────────────────────────────┤
│ Adapters                                                    │
│ Study Anything, Cognitive Loop, platform Agents, CI/evals   │
└──────────────────────────────────────────────────────────────┘
```

## Trust Kernel

The Trust Kernel is deliberately small and model-free. It owns:

- canonical protocol schemas and validation;
- hard denies and delivery-scope ordering;
- deterministic gate decisions;
- policy, subject, evidence, and receipt digests;
- signature, expiry, revocation, and chain verification;
- claim-boundary enforcement;
- separation between proposal and authorization.

The kernel must not call models, execute arbitrary Agent tools, treat RAG memory as
truth, or accept model-generated policy as self-applying.

## Equal-Weight Evidence Loops

### Controlled Failure Environment

This loop exercises a candidate inside an observable and reversible scope. Existing
reference objects include `failure-contract-v1` and `sandbox-receipt-v1`.

### Qualified Human Reconstruction

This loop proves that a reviewer can reconstruct the minimum critical boundary for
the delivery scenario. Existing compatibility objects are named
`attention-reconstruction-trace-v1` and `attention-reconstruction-summary-v1`.
Protocol v1 will normalize them under a qualified-reconstruction contract while
preserving v0 compatibility.

### Dual-Loop Gate

`dual-loop-gate-receipt-v1` is the existing equal-weight gate. A passing loop cannot
compensate for a failed or missing opposite loop.

## Receipt Layer

Current receipt flow:

```text
failure contract + sandbox receipt
  + attention/reconstruction summary
  -> dual-loop-gate-receipt-v1
  -> delivery-trust-receipt-v1
  -> customer-handoff-package-v1
```

The current CBB protocol-core flow additionally produces claim-boundary, trust-root,
reviewer-reconstruction, risk-owner-scope, delivery-decision, receipt-chain, and
self-intake receipts.

Protocol v1 will converge these parallel receipt families into a minimal canonical
set with explicit compatibility mappings. It will not delete working v0 artifacts
before a migration verifier and replacement path exist.

## Adaptive Evolution Layer

The adaptive layer may use:

- scenario classification;
- typed function calls for tests, scanners, CI, diff metadata, and rollback;
- RAG over quarantined failure and receipt memory;
- human and model capability evidence;
- Agentic workflows for evidence planning and policy proposals;
- bounded replay and canary evaluation.

It may propose a Trust Recipe or policy change. It cannot apply a hard-boundary
change or issue its own final approval. CBB changes to CBB require an evolution
receipt, deterministic conformance checks, rollback, and an independent acceptance
path appropriate to the affected scope.

## Physical Isolation

The controlled-failure runtime and human-reconstruction runtime are physically and
logically separated:

- sandbox execution cannot write human reconstruction receipts;
- the reconstruction surface has no production mutation authority;
- fine-grained attention streams are not exposed as a real-time persuasion signal;
- only typed, redacted, digest-bound artifacts cross the bridge;
- the gate reads both sides but neither side may edit the other;
- external Agent output remains untrusted until validated.

This prevents the AI from optimizing presentation against live human attention and
prevents the human interface from becoming an execution backdoor.

## Actors And Ownership

The architecture separates producer, evidence collector, qualified reviewer, risk
owner, recipient, affected party, verifier, and signer. Low-risk local use may combine
roles. Higher delivery scopes may require separation of duties and independent
evidence.

Risk-owner acceptance does not replace affected-party disclosure, appeal, or redress
where the scenario requires them.

## Current Reference Implementation Map

| Concern | Current implementation |
|---|---|
| Protocol models | `apps/api/study_anything/core/cbb_protocol.py` |
| Protocol CLI | `scripts/cbb_protocol_cli.py` |
| Deterministic gate | `scripts/cbb_gate.py` and CBB verifiers |
| Dual Loop | `apps/api/study_anything/core/dual_loop.py` |
| Delivery receipt | `apps/api/study_anything/core/delivery_trust.py` |
| Customer package | `apps/api/study_anything/core/customer_handoff.py` |
| Receipt chain | `apps/api/study_anything/core/cbb_receipt_chain.py` |
| Human adapter | `apps/api/study_anything/core/cognitive_loop_learning_adapter.py` |
| Runtime adapter | `platform/mastra-runtime/` |
| API compatibility | `apps/api/study_anything/api/main.py` |
| Release gates | `scripts/release_check.sh` |

The Python package remains `study_anything` for compatibility. Namespace migration is
not a prerequisite for Protocol v1 and must not be attempted without import shims,
artifact migration, deprecation evidence, and a no-old-import gate.

## Current Versus Planned

### Implemented

- deterministic metadata-only Dual Loop and CBB receipt contracts;
- local gate and negative fixtures;
- Delivery Trust Receipt and Customer Handoff Package;
- receipt-chain and repository self-intake evidence;
- local API, Skill, platform-Agent, Docker, and static HTML adapters;
- local security, release, adoption, and external-audit preparation evidence.

### Planned For Protocol v1

- canonical Trust Policy, Evidence Bundle, Qualified Reconstruction, Gate Decision,
  Delivery Trust Receipt, Outcome Receipt, and Evolution Receipt schemas;
- signed local provenance and tamper verification;
- scenario, recipient, affected-party, reviewer, and risk-owner policies;
- expiry, revocation, trust degradation, and incident feedback;
- isolated Agentic evidence discovery and quarantined trust memory;
- vendor-neutral conformance fixtures and governance.

### Explicitly Not Claimed

- production deployment or automatic customer delivery;
- independent audit completion;
- legal, security, regulatory, or domain certification;
- customer outcome guarantees;
- autonomous policy self-modification;
- hosted multi-tenant operational readiness.

## Adapter Boundary

Study Anything remains the Human Reconstruction / Learning Adapter. Cognitive Loop
remains an internal evidence and evolution workflow. Mastra, Langfuse, Promptfoo,
Ragas, DeepEval, and platform Agents are optional implementations or evidence sources.
None is the protocol's source of truth.

## Next Architecture Work

The ordered implementation and acceptance matrix are maintained in
[CBB Protocol v1 Development Plan](cbb-protocol-v1-development-plan.md). The project
does not prioritize a new frontend, plugin family, learning experience, or hosted
service until the protocol-core convergence, provenance, outcome, and runtime
isolation gates are in place.

The provenance layer is now local and explicit: Ed25519 signatures bind canonical
policy, evidence, qualified reconstruction, and deterministic decision objects.
It remains separate from the Trust Kernel and proves local key possession rather
than external signer identity. Outcome degradation and Agentic runtime isolation
remain later milestones.
