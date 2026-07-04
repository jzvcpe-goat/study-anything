# Client Report Operator Handoff Rehearsal

This rehearsal is the second concrete operator handoff layer after Customer
Delivery Rehearsal. It is for the `client_report_handoff` delivery class only.

It answers one narrow question:

Can a platform Agent or external operator prepare a client-report handoff
decision from metadata-only evidence, without sending a customer message,
publishing externally, mutating production, or reading raw report/customer
payload text?

## Inputs

- `platform/generated/study-anything-client-report-delivery-class.json`
- `platform/generated/study-anything-customer-delivery-rehearsal.json`

Both inputs must already pass their own verifiers.

## Outputs

- `platform/generated/study-anything-client-report-operator-handoff-rehearsal.json`
- `platform/generated/study-anything-client-report-operator-handoff-rehearsal.md`

The output contains one ready case and blocked cases for:

- blocked Client Report delivery class evidence;
- blocked Customer Delivery Rehearsal evidence;
- missing bounded recipient-scope confirmation;
- missing operator understanding that this is not send approval;
- automatic customer sending attempts;
- external publication attempts;
- raw report or raw customer payload requests.

## Boundary

This layer may prepare a human-facing operator decision. It does not approve
customer sending, publish externally, mutate production, certify legal or
financial advice, certify complete factual correctness, guarantee outcomes, or
replace customer-specific legal/compliance review.

It is metadata-only. It must not include raw source text, raw report text, raw
customer payloads, screenshots, attention streams, secrets, model credentials,
or user-owned Agent credentials.

## Commands

```bash
python3 scripts/verify_client_report_operator_handoff_rehearsal.py --check
```

Refresh deterministic outputs:

```bash
python3 scripts/verify_client_report_operator_handoff_rehearsal.py --write
```

## 中文说明

这一层不是“AI 自动把报告发给客户”，也不是“AI 证明报告完全正确”。它只是把
`client_report_handoff` 这个交付类别和 Customer Delivery Rehearsal 连接起来，让外部
operator 或平台 Agent 可以在只看 metadata 的情况下判断：是否已经可以进入人工外发
决策。

它必须继续阻断自动客户发送、外部发布、生产变更、原始报告正文、客户 payload 暴露和
法律/财务/事实正确性过度承诺。真正的外部交付动作仍然发生在系统之外，由人完成。
