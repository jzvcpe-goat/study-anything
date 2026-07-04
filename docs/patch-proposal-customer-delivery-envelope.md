# Patch Proposal Customer Delivery Envelope

Patch Proposal Customer Delivery Envelope sits after
`Patch Proposal Customer-Handoff Boundary Gate`.

It answers one narrow question:

> If a patch proposal has returned from an external operator and the customer
> handoff boundary is ready, what may Study Anything prepare before anything is
> visible to a customer?

The answer is intentionally conservative:

- prepare only a metadata-only customer delivery envelope;
- include only claim-boundary refs, verification command refs, metadata receipt
  refs, and blocked-path summaries;
- require a separate manual send control before any customer-facing action;
- block raw customer drafts, patch bodies, diffs, repository file bodies, PR
  comments, external publication payloads, production payloads, secrets, and
  model credentials;
- do not send, publish, deploy, comment on PRs, or call models.

It consumes:

- `fixtures/patch-proposal-customer-handoff-boundary-gate/*/patch-proposal-customer-handoff-boundary-receipt.json`
- `platform/generated/study-anything-patch-proposal-customer-handoff-boundary-gate.json`

It emits:

- `fixtures/patch-proposal-customer-delivery-envelope/*/patch-proposal-customer-delivery-envelope.json`
- `platform/generated/study-anything-patch-proposal-customer-delivery-envelope.json`
- `platform/generated/study-anything-patch-proposal-customer-delivery-envelope.md`
- `platform/generated/study-anything-patch-proposal-customer-delivery-envelope.html`

## Boundary

This layer proves only that Study Anything can prepare a metadata-only envelope
for a human or platform operator to inspect before customer delivery.

It does not include customer-visible draft text. It does not apply patches,
open or comment on PRs, publish externally, mutate production, certify truth, or
send anything to a customer.

## Command

```bash
python3 scripts/verify_patch_proposal_customer_delivery_envelope.py --check
```

Regenerate:

```bash
python3 scripts/verify_patch_proposal_customer_delivery_envelope.py --write
```

## Chinese Summary

Patch Proposal Customer Delivery Envelope 是 Customer-Handoff Boundary Gate
之后的一层。

它只允许准备 metadata-only 的客户交付 envelope，里面只能有 claim boundary、
验证命令、metadata receipt 引用和 blocked path 摘要。

它不允许生成客户正文、patch 正文、diff、仓库文件正文、PR comment、外部发布
payload、生产 payload、密钥或模型凭证。它也不发送客户消息、不发布、不部署、
不评论 PR、不调用模型。
