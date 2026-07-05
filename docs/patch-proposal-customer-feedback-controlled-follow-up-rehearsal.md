# Patch Proposal Customer Feedback Controlled Follow-up Rehearsal

Patch Proposal Customer Feedback Controlled Follow-up Rehearsal sits after
`Patch Proposal Customer Feedback Controlled Follow-up Boundary Gate`.

It answers one narrow question:

> Can an operator or host-platform Agent locally rehearse the follow-up boundary
> from metadata-only envelope refs before any customer-visible follow-up exists?

The answer remains deliberately conservative:

- consume only `patch-proposal-controlled-follow-up-envelope-refs-v1`;
- require active operator or host-platform Agent boundary reconstruction;
- require Product Loop, Dual Loop, Delivery Trust Case, and active
  reconstruction refs to remain present;
- emit only `patch-proposal-controlled-follow-up-rehearsal-receipt-v1`;
- block missing or invalid envelope refs, passive rehearsal, unsupported
  rehearsal sources, raw follow-up previews, customer-visible drafts, automatic
  sends, source mutation, production mutation, external publication, model
  calls, secrets, and model credentials;
- do not generate follow-up text, send to customers, mutate source, mutate
  production, publish externally, call models, or start daemons.

It consumes:

- `fixtures/patch-proposal-customer-feedback-controlled-follow-up-boundary-gate/*/patch-proposal-controlled-follow-up-envelope-refs.json`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-boundary-gate.json`

It emits:

- `fixtures/patch-proposal-customer-feedback-controlled-follow-up-rehearsal/*/patch-proposal-controlled-follow-up-rehearsal-receipt.json`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.json`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.md`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-rehearsal.html`

## Boundary

This layer proves only local rehearsal readiness for a metadata-only follow-up
boundary. It does not prepare customer-visible copy. It does not send, publish,
deploy, mutate source, mutate production, call models, or certify the customer
outcome.

Actual follow-up authoring and customer communication remain outside Study
Anything and require separate human or host-platform Agent action beyond this
receipt.

## Command

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_rehearsal.py --check
```

Regenerate:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_rehearsal.py --write
```

## Chinese Summary

Patch Proposal Customer Feedback Controlled Follow-up Rehearsal 是
Controlled Follow-up Boundary Gate 之后的一层。

它只允许 operator 或 host-platform Agent 基于 metadata-only 的 envelope refs 做本地
边界演练：确认 Product Loop、Dual Loop、Delivery Trust Case 和主动重构证据仍然
存在，同时不生成客户正文、不自动发送、不改源码、不改生产、不外部发布、不调用模型、
不保存密钥。

这层通过并不代表已经可以直接联系客户。它只说明“跟进边界”可以被本地复核；真正
写给客户的内容和发送动作仍必须发生在 Study Anything 之外，并由人或宿主平台 Agent
承担责任。
