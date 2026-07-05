# Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge Receipt

Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge Receipt sits after
`Patch Proposal Customer Feedback Controlled Follow-up Feedback Loop Closure`.

It answers one narrow question:

> Can Study Anything consume a closed loop-closure receipt whose action is
> `reopen_as_customer_feedback_intake_candidate` and prepare only metadata refs
> for a future customer-feedback intake gate?

The answer remains intentionally narrow:

- consume only a closed `patch-proposal-controlled-follow-up-feedback-loop-closure-receipt-v1`;
- require the source closure action to be `reopen_as_customer_feedback_intake_candidate`;
- reject archive-cycle and external-owner-review closure actions;
- preserve Product Loop, Dual Loop, Delivery Trust Case, active reconstruction,
  outcome, actor, action, and loop-closure evidence from the existing chain;
- emit only a metadata-only bridge receipt with hashes for the source closure,
  outcome, actor, action, and prepared candidate ref;
- block raw follow-up bodies, raw customer replies, customer identity, send
  payloads, automatic re-contact, automatic intake creation, source mutation,
  production mutation, external publication payloads, model calls, secrets, and
  model credentials;
- do not create a new intake, contact customers, notify external owners, mutate
  source, mutate production, publish externally, call models, or start daemons.

It consumes:

- `fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure/*/patch-proposal-controlled-follow-up-feedback-loop-closure-receipt.json`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-loop-closure.json`

It emits:

- `fixtures/patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge/*/patch-proposal-controlled-follow-up-feedback-reopen-intake-bridge-receipt.json`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.json`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.md`
- `platform/generated/study-anything-patch-proposal-customer-feedback-controlled-follow-up-feedback-reopen-intake-bridge.html`

## Boundary

This layer proves only that a prior controlled feedback cycle can be bridged into
the next intake decision point. It does not accept, create, publish, assign, or
send the new intake.

The next layer must separately decide whether the prepared candidate can become
a new customer-feedback intake item under a Product Loop. That later gate owns
its own privacy, evidence, and delivery obligations.

## Command

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_bridge.py --check
```

Regenerate:

```bash
python3 scripts/verify_patch_proposal_customer_feedback_controlled_follow_up_feedback_reopen_intake_bridge.py --write
```

## Chinese Summary

Patch Proposal Customer Feedback Controlled Follow-up Feedback Reopen Intake Bridge Receipt 是
Controlled Follow-up Feedback Loop Closure 之后的一层。

它只接受一种上游动作：`reopen_as_customer_feedback_intake_candidate`。如果上游
closure 是 archive 或 external-owner-review，或者上游 closure 本身被 block，这一层
都会拒绝。

它的作用不是创建新的客户反馈 intake，而是把“可以重新进入 intake”的决定转成一个
metadata-only 的桥接 receipt，保留 Product Loop、Dual Loop、Delivery Trust Case、
主动重构、outcome、actor、action 和 loop-closure 的证据链。

这层通过不代表 Study Anything 已经联系客户、创建 intake、通知 owner、修改源码、
修改生产、外部发布或调用模型。它只是说明：下一层 intake gate 可以在完整边界证据下
继续判断这个候选项是否能成为新的客户反馈条目。
