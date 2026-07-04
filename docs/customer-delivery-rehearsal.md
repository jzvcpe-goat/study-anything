# Customer Delivery Rehearsal

Customer Delivery Rehearsal is the operator exercise after the Customer Delivery
Trust Envelope.

It answers one narrow question:

> Can an external operator or platform Agent inspect the envelope, confirm the
> human scope boundary, and produce a ready/block decision before anything is
> sent to a customer?

The answer stays deliberately conservative:

- one ready path exists only when every active scope confirmation is present;
- missing human scope confirmation blocks;
- hidden claim boundary blocks;
- raw payload or secret attachment blocks;
- automatic customer-send attempts block;
- already blocked envelope items remain blocked.

It consumes:

- `platform/generated/study-anything-customer-delivery-trust-envelope.json`

It emits:

- `platform/generated/study-anything-customer-delivery-rehearsal.json`
- `platform/generated/study-anything-customer-delivery-rehearsal.md`

## Boundary

The rehearsal is metadata-only. It does not call models, start a daemon, mutate
production, send customer messages, publish externally, certify truth, include
raw source text, include raw diffs, include report bodies, include customer
payloads, include screenshots, read attention streams, or store user-owned Agent
credentials.

It proves only that a platform Agent or operator can rehearse the decision path
before customer-visible action. Actual customer sending remains outside this
system and requires a human.

## Command

```bash
python3 scripts/verify_customer_delivery_rehearsal.py --check
```

Regenerate:

```bash
python3 scripts/verify_customer_delivery_rehearsal.py --write
```

## Chinese Summary

Customer Delivery Rehearsal 是 Customer Delivery Trust Envelope 之后的一层。
它不发送客户消息，不批准生产，不做真实性认证。它只做一件事：让外部 operator
或平台 Agent 在 metadata-only 的封套上演练 ready/block 决策。

只有当收件人范围、客户上下文、claim boundary、无 raw payload/secret、以及
“真正发送必须由人类在系统外执行”都被确认时，才进入
`ready_for_manual_send_review`。任何自动发送、raw payload、claim boundary 缺失、
人类范围确认缺失，都会被 block。
