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

## Verification Commands

```bash
python3 scripts/verify_dual_loop_contracts.py --check
python3 scripts/verify_failure_sandbox_lite.py --check
python3 scripts/verify_attention_reconstruction_lite.py --check
python3 scripts/verify_dual_loop_gate.py --check
python3 scripts/verify_delivery_trust_receipt.py --check
```

The final command verifies pass and blocked fixtures, rejects AI-review-only
promotion, rejects eval-as-sufficient promotion, and rejects missing claim
boundaries.
