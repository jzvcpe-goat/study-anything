# Trust Model / 信任模型

## Core Claim

CBB Protocol does not prove that an AI is trustworthy in general. It proves that a
specific candidate may move only as far as a specific policy and receipt allow.

CBB 协议不证明某个 AI 在全局上值得信任。它只证明一个具体候选物可以走到某份策略和
收据允许的范围。

Trust is scoped, stateful, time-bound, evidence-backed, and reversible. A model,
human, project, recipient, or delivery context changing can invalidate an earlier
decision.

信任有范围、有状态、有期限、有证据，并且必须可撤销。模型、人、项目、接收者或交付
场景发生变化，都可能使旧决策失效。

## Controlled Release, Not Permanent Restraint

The protocol is a mechanism for knowing when to let go. It earns that freedom by
exposing failure early, bounding propagation, reconstructing control boundaries, and
leaving an auditable receipt.

协议的目标不是永久束缚 AI，而是知道何时可以放手。这个自由来自早期暴露失败、限制
传播、重构控制边界，并留下可审计收据。

```text
We know what the candidate can do.
We know how it has failed.
We know where failure must stop.
We know who owns the residual risk.
We know what remains unproven.
Therefore we can release it only inside that boundary.
```

## Equal-Weight Dual Loop

### Loop A: Controlled Failure

The AI candidate is exercised inside an observable and reversible environment. The
evidence must show:

- allowed and forbidden failure modes;
- blast-radius budget;
- escaped effects, if any;
- rollback availability and replayability;
- evidence provenance;
- whether the candidate stayed inside the declared scope.

### Loop B: Qualified Human Reconstruction

The human is not asked to repeat the whole task. The reviewer reconstructs the
minimum control boundary appropriate to the scenario:

- intent and non-goals;
- critical failure path;
- affected parties and recipient scope;
- rollback trigger;
- evidence weakness and known limitation;
- acceptable residual risk.

Passive attention routes the reviewer to likely gaps. Active reconstruction provides
the stronger evidence. Qualification is local to a project, boundary type, and time
window. It is not a permanent label attached to a person.

### Propagation Gate

Both loops must pass. Controlled failure without human reconstruction blocks.
Human confidence without bounded failure evidence also blocks. Neither loop may
compensate for the other.

## Trust Actors

The protocol keeps these roles separate:

| Actor | Responsibility |
|---|---|
| Producer | Creates the candidate and supporting evidence |
| Evidence collector | Calls typed tools and records provenance |
| Qualified reviewer | Reconstructs the required human boundary |
| Risk owner | Accepts residual organizational or operational risk |
| Recipient | Receives or operates the candidate |
| Affected party | May experience the result or harm without being the recipient |
| Deterministic verifier | Checks policy, evidence, digests, scope, and receipt |

One actor may fill multiple low-risk roles, but the receipt must not hide that fact.
For higher-scope delivery, policy may require separation of duties.

## What Counts As Evidence

Evidence must be typed, attributable, bounded, and linked to the candidate. Examples:

- sandbox execution and negative fixtures;
- deterministic tests and scanner output;
- rollback replay;
- qualified reconstruction checkpoints;
- recipient, affected-party, and risk-owner declarations;
- signed external eval receipts as supporting evidence;
- post-delivery outcomes and incidents;
- policy, verifier, and artifact digests.

Natural-language confidence, model reputation, or a generic approval button is not
sufficient evidence.

## Self-Distrust

The protocol must distrust itself. Its main structural threats are:

1. **Forged or selective receipts**: mitigated by digests, signatures, verifier
   identity, timestamps, and tamper-evident chains.
2. **Compromised Agentic runtime**: mitigated by least privilege, typed function
   calls, untrusted-input isolation, and a model-free Trust Kernel.
3. **RAG or memory poisoning**: mitigated by provenance, quarantine, expiry,
   counter-evidence, and incident-triggered rollback.
4. **Goodhart pressure**: mitigated by negative fixtures, random audit, hidden
   adversarial cases, post-delivery sampling, and receipt revocation.
5. **Self-authorization**: mitigated by proposal/decision separation and CBB-on-CBB
   evolution receipts.
6. **Affected-party omission**: mitigated by separate recipient, risk-owner,
   affected-party, disclosure, appeal, and redress fields.

Opaque systems may propose trust evidence. They cannot be the final source of trust.

黑箱系统可以提出信任证据，但不能成为最终信任来源。

## Trust Growth And Degradation

Repeated success can reduce friction only inside the same bounded scenario. A mature
Trust Recipe may reuse known fixtures, rollback patterns, and reconstruction evidence.
New risk, new recipient, new model behavior, new affected party, or changed impact
returns the case to a higher level of reconstruction.

Trust must also move downward. Incidents, failed rollback, stale evidence, model
regression, compromised memory, or claim-boundary violation can:

- lower the autonomy ceiling;
- expire or revoke receipts;
- freeze a Trust Recipe;
- require replay or independent review;
- narrow the allowed delivery scope.

## Neural-System Design Analogy

This is a design analogy, not a neuroscience claim:

| Layer | CBB role |
|---|---|
| Spinal reflex | Fast local guardrails and hard stops |
| Brainstem | Stable Trust Kernel and survival boundaries |
| Cerebellum | Practiced Trust Recipes and failure memory |
| Cerebrum | Novel context, value judgment, and human reconstruction |

The engineering rule is useful: hard local danger should be fast and deterministic;
repeated safe patterns may become lower-friction recipes; novel or consequential
contexts move upward to human judgment.

## Current Claim Boundary

The current repository proves a local, deterministic, metadata-only reference
harness. It does not prove:

- production deployment approval;
- customer outcome guarantees;
- legal, security, or domain certification;
- general model correctness;
- independent human security audit completion;
- safe autonomous self-evolution;
- hosted multi-tenant operational readiness.

## Current Verification

```bash
python3 scripts/verify_cbb_positioning.py --check
python3 scripts/verify_dual_loop_contracts.py --check
python3 scripts/verify_failure_sandbox_lite.py --check
python3 scripts/verify_attention_reconstruction_lite.py --check
python3 scripts/verify_dual_loop_gate.py --check
python3 scripts/verify_delivery_trust_receipt.py --check
python3 scripts/verify_customer_handoff_package.py --check
python3 scripts/verify_cbb_protocol_contracts.py --check
python3 scripts/verify_cbb_gate.py --check
python3 scripts/verify_cbb_receipt_chain.py --check
```

Passing these commands proves only their documented deterministic scope.
