# Delivery Trust Receipt / 交付信任收据

`delivery-trust-receipt-v1` is the first customer-handoff contract in Cognitive
Black Box. It turns Dual-Loop evidence into a single metadata-only receipt that
says whether an AI-generated candidate may be handed to a customer inside the
current controlled scope.

`delivery-trust-receipt-v1` 是认知黑箱里的第一份客户交付前收据。它把 Dual Loop
证据合并成一个只含 metadata 的结果：这个 AI 生成候选物是否可以在当前受控范围内
交给客户。

## Inputs

The receipt consumes structured artifacts only:

```text
failure-contract-v1
sandbox-receipt-v1
attention-reconstruction-summary-v1
dual-loop-gate-receipt-v1
```

It does not consume source bodies, customer payloads, screenshots, keystrokes,
mouse coordinates, attention streams, model prompts, model keys, cookies, bearer
tokens, signed URLs, or platform Agent credentials.

## Output

The output is:

```text
delivery-trust-receipt-v1
```

A passing receipt has:

- `status: allowed`
- `decision: allow_controlled_customer_handoff`
- `customer_delivery_scope.allowed_handoff: true`
- `trust_basis.ai_eval_receipts_role: supporting_only_not_sufficient`
- `trust_basis.human_review_role: active_reconstruction_not_full_manual_re_review`

A blocked receipt has:

- `status: blocked`
- `decision: block_customer_handoff`
- concrete `reasons`, such as `human_reconstruction_missing`,
  `sandbox_risk_outside_budget`, or `dual_loop_gate_blocked`

## Why It Exists

The receipt prevents two bad shortcuts:

1. **Excessive manual re-review as the only control**

   The human does not need to reread everything. They must reconstruct the
   important failure boundaries.

2. **AI-reviewing-AI as the only control**

   Eval receipts can support the case, but they cannot replace the sandbox,
   human reconstruction, and propagation gate.

## CLI

```bash
python3 scripts/delivery_trust_receipt.py build \
  --failure-contract fixtures/delivery-trust/pass/failure-contract.json \
  --sandbox-receipt fixtures/delivery-trust/pass/sandbox-receipt.json \
  --attention-summary fixtures/delivery-trust/pass/attention-reconstruction-summary.json \
  --dual-loop-gate fixtures/delivery-trust/pass/dual-loop-gate-receipt.json \
  --output .cognitive-loop/artifacts/delivery-trust/delivery-trust-receipt.json \
  --html-output .cognitive-loop/artifacts/delivery-trust/delivery-trust-receipt.html
```

## Verifier

```bash
python3 scripts/verify_delivery_trust_receipt.py --check
```

The verifier proves:

- a valid Dual Loop pass allows controlled customer handoff;
- missing human reconstruction blocks handoff;
- risk outside sandbox budget blocks handoff;
- AI-review-only trust basis is rejected;
- eval-as-sufficient trust basis is rejected;
- missing claim boundary is rejected;
- generated JSON/HTML reports stay metadata-only.

Generated evidence:

```text
platform/generated/study-anything-delivery-trust-receipt.json
platform/generated/study-anything-delivery-trust-receipt.html
fixtures/delivery-trust/
```

## Claim Boundary

An allowed receipt does **not** mean production deployment approval. It means the
candidate passed the current local deterministic trust harness for controlled
customer handoff. Real production still requires domain acceptance tests,
operator-owned deployment approval, customer-specific rollback planning, and any
required legal or security review.
