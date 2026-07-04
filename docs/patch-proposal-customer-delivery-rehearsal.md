# Patch Proposal Customer Delivery Rehearsal

Patch Proposal Customer Delivery Rehearsal sits after
`Patch Proposal Customer Delivery Envelope`.

It answers one narrow question:

> Can a platform Agent or operator actively reconstruct the customer handoff
> boundary and produce a ready/block decision before anything is visible to a
> customer?

The answer is deliberately conservative:

- consume only a metadata-only customer delivery envelope;
- require active operator reconstruction of recipient scope, delivery class
  scope, claim boundary, privacy boundary, and the manual-send boundary;
- allow one ready path only for manual customer handoff review outside Study
  Anything;
- block blocked source envelopes, missing reconstruction, raw customer drafts,
  raw patch or diff requests, PR comment actions, automatic customer sending,
  external publication, production mutation, secrets, and model credentials;
- do not send, publish, deploy, comment on PRs, call models, or mutate source.

It consumes:

- `fixtures/patch-proposal-customer-delivery-envelope/*/patch-proposal-customer-delivery-envelope.json`
- `platform/generated/study-anything-patch-proposal-customer-delivery-envelope.json`

It emits:

- `fixtures/patch-proposal-customer-delivery-rehearsal/*/patch-proposal-customer-delivery-rehearsal-receipt.json`
- `platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.json`
- `platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.md`
- `platform/generated/study-anything-patch-proposal-customer-delivery-rehearsal.html`

## Boundary

This layer proves only that the envelope can be rehearsed as a manual
customer-handoff decision. It does not include customer-visible draft text. It
does not apply patches, open or comment on PRs, publish externally, mutate
production, certify truth, or send anything to a customer.

Actual customer sending remains outside Study Anything and requires a human or
host platform action beyond this metadata-only receipt.

## Command

```bash
python3 scripts/verify_patch_proposal_customer_delivery_rehearsal.py --check
```

Regenerate:

```bash
python3 scripts/verify_patch_proposal_customer_delivery_rehearsal.py --write
```

## Chinese Summary

Patch Proposal Customer Delivery Rehearsal 是 Customer Delivery Envelope 之后的
一层。

它只允许平台 Agent 或 operator 在 metadata-only 的 envelope 上做主动边界重构：
确认收件人范围、delivery class 范围、claim boundary、privacy boundary，以及真正
发送必须在 Study Anything 之外由人执行。

它不生成客户正文、不返回 patch/diff、不评论 PR、不自动发送、不外部发布、不改生产、
不调用模型、不保存密钥。任何缺少主动重构、raw payload、PR comment、自动发送或
生产变更请求都会被 block。
