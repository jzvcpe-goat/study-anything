# Code Review Operator Handoff Rehearsal

This rehearsal is the first concrete operator handoff layer after Customer
Delivery Rehearsal. It is for the `code_review_handoff` delivery class only.

It answers one narrow question:

Can a platform Agent or external operator prepare a code-review handoff decision
from metadata-only evidence, without posting PR comments, sending a customer
message, mutating production, or reading raw diff/review text?

## Inputs

- `platform/generated/study-anything-code-review-delivery-class.json`
- `platform/generated/study-anything-customer-delivery-rehearsal.json`

Both inputs must already pass their own verifiers.

## Outputs

- `platform/generated/study-anything-code-review-operator-handoff-rehearsal.json`
- `platform/generated/study-anything-code-review-operator-handoff-rehearsal.md`

The output contains one ready case and blocked cases for:

- blocked Code Review delivery class evidence;
- blocked Customer Delivery Rehearsal evidence;
- missing operator understanding that this is not send approval;
- automatic PR commenting attempts;
- automatic customer sending attempts;
- raw diff or raw review text requests.

## Boundary

This layer may prepare a human-facing operator decision. It does not approve
customer sending, post PR comments, merge or deploy code, certify security,
discover all vulnerabilities, certify truth, guarantee outcomes, or replace
customer-specific legal/compliance review.

It is metadata-only. It must not include raw source text, raw diffs, raw review
text, raw customer payloads, screenshots, attention streams, secrets, model
credentials, or user-owned Agent credentials.

## Commands

```bash
python3 scripts/verify_code_review_operator_handoff_rehearsal.py --check
```

Refresh deterministic outputs:

```bash
python3 scripts/verify_code_review_operator_handoff_rehearsal.py --write
```

## 中文说明

这一层不是“AI 自动把审查结果发出去”，也不是“AI 已经证明代码安全”。它只是把
`code_review_handoff` 这个交付类别和 Customer Delivery Rehearsal 连接起来，让外部
operator 或平台 Agent 可以在只看 metadata 的情况下判断：是否已经可以进入人工外发
决策。

它必须继续阻断自动 PR 评论、自动客户发送、生产变更、原始 diff/review text 暴露和
过度承诺。真正的外部发送动作仍然发生在系统之外，由人完成。
