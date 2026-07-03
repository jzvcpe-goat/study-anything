# Trust Model / 信任模型

## Core Claim

Cognitive Black Box is a Dual-Loop Trust Harness for AI delivery. It does not
ask users to trust an AI result because it sounds fluent, because another AI
approved it, or because a human reread every detail. It asks whether the result
has passed a controlled failure loop, an active human reconstruction loop, and a
propagation gate that keeps both loops equal weight.

认知黑箱是面向 AI 交付的 Dual-Loop Trust Harness。它不要求用户因为结果流畅、
另一个 AI 说可以、或人类重新读完所有细节而信任 AI。它只问：这个交付是否通过了
可控失败闭环、主动人类重构闭环，以及一个不让任一闭环独大的传播门。

## Why This Exists

The target problem is not generic model quality. The target problem is customer
delivery trust:

- AI can now create real deliverables quickly.
- Full human re-review does not scale and often becomes shallow fatigue.
- AI-reviewing-AI can hide failures behind another black box.
- Teams need a cheaper, repeatable proof that the delivery boundary was
  understood, tested, contained, and reversible.

目标问题不是泛泛的模型质量，而是客户交付信任：

- AI 已经可以快速生成真实交付物。
- 人类逐字逐步二次审核不可扩展，而且容易变成疲劳式走过场。
- AI 审 AI 可能只是把失败藏进另一个黑箱。
- 团队需要一种更便宜、可重复的证据，证明交付边界已被理解、测试、隔离，并且可回滚。

## The Trust Equation

```text
delivery trust =
  controlled failure evidence
+ human boundary reconstruction evidence
+ propagation gate receipt
+ explicit claim boundary
- production mutation by default
- AI-review-only promotion
- full manual re-review as the only control
```

## Loop 1: Controlled Failure Environment

AI is allowed to fail only inside an observable, reversible sandbox. The sandbox
emits:

- `failure-contract-v1`
- `sandbox-receipt-v1`

The sandbox records risk budget, allowed failure modes, forbidden propagation
paths, rollback proof, and whether any failure escaped. It must not mutate
production, expose real users, create irreversible effects, call models in the
v0.1 deterministic path, or store private payloads.

## Loop 2: Human Attention Reconstruction Environment

Human control is not step-by-step approval. The human layer records whether an
operator can reconstruct the important failure boundaries:

- what may fail;
- where failure must stop;
- what triggers rollback;
- what is and is not being claimed;
- what evidence is strong enough for the next sandbox level.

It emits:

- `attention-reconstruction-trace-v1`
- `attention-reconstruction-summary-v1`

Passive attention is weak evidence. Active reconstruction checkpoints are strong
evidence.

## Dual-Loop Propagation Gate

The gate emits:

- `dual-loop-gate-receipt-v1`

It blocks if the sandbox passes but human reconstruction is missing. It also
blocks if human reconstruction passes but sandbox risk is outside budget. Neither
loop may dominate the other.

## Delivery Trust Receipt

The delivery layer emits:

- `delivery-trust-receipt-v1`

This receipt answers the customer-facing question: can this AI-generated
candidate be handed off inside the current controlled scope?

The answer is allowed only when:

- the failure contract is valid;
- the sandbox receipt proves contained and reversible failure;
- the human reconstruction summary is present and passed;
- the Dual-Loop gate is allowed;
- AI eval receipts are treated as supporting evidence only;
- full manual re-review is not required as the primary control;
- production mutation and irreversible effects remain blocked by default;
- the claim boundary states what is and is not proven.

## Customer Handoff Package

The portable package layer emits:

- `customer-handoff-package-v1`

This package is not a new trust source. It cannot approve anything that the
Delivery Trust Receipt blocked, and it cannot expand the customer delivery
scope. It only bundles scoped metadata evidence, limitations, rollback,
human reconstruction summaries, external eval receipt refs, artifact digests,
and WorkBuddy/Hermes/Codex handoff instructions.

## Delivery Trust Case Harness

The total assembly layer emits:

- `delivery-trust-case-v1`

This layer answers whether one AI-generated candidate is ready for controlled
customer handoff. It requires Product Loop, Dual Loop, Delivery Trust Receipt,
and CustomerHandoffPackage evidence to agree. If any one layer blocks, the case
blocks. A valid package cannot compensate for a failed Product Loop, and a
passing Product Loop cannot compensate for sandbox risk outside budget.

## What This Does Not Claim

The current local-first deterministic MVP does not claim:

- production deployment approval;
- customer outcome guarantee;
- general model correctness;
- legal, security, or domain acceptance completion;
- that AI-reviewing-AI is sufficient;
- that humans no longer need judgment.

It claims only that the candidate passed a metadata-only, local, deterministic
trust harness for controlled handoff.

## Product Loop Harness

Before customer handoff, the product-development layer emits:

- `product-loop-scenario-v1`
- `product-loop-run-v1`

This layer maps the three product-development loops into machine-checkable
evidence:

- Agentic Coding Loop: coding agent to product spec/evals, roughly minutes;
- Developer Feedback Loop: developer vision to product spec/evals, roughly
  hours;
- External Feedback Loop: external feedback to developer vision, roughly days.

It blocks if product spec/evals are missing, developer vision is missing,
external feedback requests production scope, AI-review-only evidence is used as
the trust basis, or one loop dominates the others. A passing Product Loop run
may promote only to the Delivery Trust Harness, not to production.

## Verification Commands

```bash
python3 scripts/verify_dual_loop_contracts.py --check
python3 scripts/verify_failure_sandbox_lite.py --check
python3 scripts/verify_attention_reconstruction_lite.py --check
python3 scripts/verify_dual_loop_gate.py --check
python3 scripts/verify_delivery_trust_receipt.py --check
python3 scripts/verify_customer_handoff_package.py --check
python3 scripts/verify_product_loop_harness.py --check
python3 scripts/verify_delivery_trust_case_harness.py --check
```

The delivery trust command verifies pass and blocked fixtures, rejects
AI-review-only promotion, rejects eval-as-sufficient promotion, and rejects
missing claim boundaries. The customer handoff command verifies the portable
package cannot bypass delivery trust, expand scope, rely on eval receipts as
sufficient proof, omit rollback or claim boundaries, leak secret-like content,
ship digest drift, or ask platform Agents for production mutation.
