# Customer Delivery Trust Envelope

Customer Delivery Trust Envelope is the boundary after the Controlled Handoff
Runbook.

It answers one narrow question:

> If an operator or platform Agent may prepare a controlled handoff packet, what
> may be assembled before anything becomes customer-visible?

The answer is intentionally conservative:

- create a metadata-only customer-delivery envelope;
- include only delivery class IDs, claim boundaries, verification commands, and
  metadata receipt references;
- keep blocked paths blocked;
- require human scope confirmation before any customer send;
- stop before automatic customer sending, production mutation, external
  publication, truth certification, or outcome guarantees.

It consumes:

- `platform/generated/study-anything-controlled-handoff-runbook.json`

It emits:

- `platform/generated/study-anything-customer-delivery-trust-envelope.json`
- `platform/generated/study-anything-customer-delivery-trust-envelope.md`

The next boundary is `docs/customer-delivery-rehearsal.md`, which may rehearse a
ready/block decision from the envelope but still must not send anything to a
customer.

## Boundary

The envelope is metadata-only. It does not call models, start a daemon, mutate
production, send customer messages, publish externally, certify truth, include
raw source text, include raw diffs, include report bodies, include customer
payloads, include screenshots, read attention streams, or store user-owned Agent
credentials.

It proves only that an external operator or platform Agent can prepare a
customer-delivery envelope while preserving all claim limits and stopping before
customer-visible effects.

## Command

```bash
python3 scripts/verify_customer_delivery_trust_envelope.py --check
```

Regenerate:

```bash
python3 scripts/verify_customer_delivery_trust_envelope.py --write
```

## Chinese Summary

Customer Delivery Trust Envelope 是 Controlled Handoff Runbook 之后的一层。
它不允许平台 Agent 自动把结果发给客户，也不允许生产变更或真实性认证。

它只允许准备一个 metadata-only 的客户交付封套：里面可以有交付类别、claim
boundary、验证命令、metadata receipt 引用和 blocked path 摘要；不能有原文、
diff、报告正文、客户 payload、截图、注意力流、密钥或用户 Agent 凭证。

这一步的意义是把“可以准备 handoff”推进到“可以准备客户可审阅前的封套”，但最后
是否发送仍必须由人类确认范围并在系统外执行。
