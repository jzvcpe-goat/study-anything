# Trust Scenario Decision Gate

Trust Scenario Decision Gate Lite turns the static Trust Scenario Catalog into a
deterministic local decision receipt.

It answers:

> Given one catalog scenario, a metadata-only evidence list, active human
> reconstruction checkpoints, and requested shortcuts, can this handoff proceed?

The gate is local-first and metadata-only. It does not read raw source text,
report text, customer payloads, screenshots, attention streams, secrets, model
keys, or user-owned Agent credentials. It does not call models, mutate
production, publish externally, or send customer messages.

## What It Allows

The gate can allow only controlled handoff scenarios already supported by the
Trust Scenario Catalog, such as:

- controlled code-review handoff;
- controlled client-report handoff.

Allowance requires all required artifacts, active reconstruction checkpoints,
and no forbidden shortcuts.

## What It Blocks

The gate blocks:

- missing required artifacts;
- passive or incomplete human reconstruction;
- forbidden shortcuts such as merge approval or automatic customer sending;
- direct production mutation;
- legal, financial, security, or truth certification claims;
- unsupported catalog scenarios.

## Receipt

The gate emits `trust-scenario-decision-v1` receipts with:

- `scenario_id`
- `status`
- `decision`
- `reasons`
- `required_artifacts`
- `provided_artifacts`
- `missing_artifacts`
- `required_active_reconstruction_checkpoints`
- `missing_active_reconstruction_checkpoints`
- `blocked_shortcuts`
- `claim_boundary`
- `privacy`

## Commands

Evaluate a scenario:

```bash
python3 scripts/trust_scenario_decision_gate.py evaluate \
  --scenario-id controlled_code_review_handoff \
  --provided-artifact failure-contract-v1 \
  --provided-artifact sandbox-receipt-v1 \
  --provided-artifact attention-reconstruction-trace-v1 \
  --provided-artifact attention-reconstruction-summary-v1 \
  --provided-artifact dual-loop-gate-receipt-v1 \
  --provided-artifact delivery-trust-case-v1 \
  --provided-artifact code-review-handoff-case-v1 \
  --active-checkpoint failure_boundary_reconstruction \
  --active-checkpoint risk_budget_reconstruction \
  --active-checkpoint recipient_scope_reconstruction
```

Refresh deterministic fixtures and reports:

```bash
python3 scripts/verify_trust_scenario_decision_gate.py --write
```

Verify:

```bash
python3 scripts/verify_trust_scenario_decision_gate.py --check
```

This is still a gate for controlled handoff evidence, not proof of customer
adoption, factual truth, or permission to perform irreversible production work.

## 中文说明

Trust Scenario Decision Gate Lite 会把静态的 Trust Scenario Catalog 转成一个
本地、确定性、只含 metadata 的交付决策 receipt。

它回答的问题是：给定一个场景、一组证据 artifact、主动人类重建 checkpoint 和
用户请求的 shortcut，这次交付是否可以继续。

它可以允许的只有 catalog 中已经支持的受控交付场景，例如受控代码审查交接和受控
客户报告交接。允许条件是：所需 artifact 全部存在，主动重建 checkpoint 全部完成，
并且没有请求被禁止的 shortcut。

它会阻断缺少证据、被动注意力、不完整重建、自动合并、自动发客户、直接修改生产、
法律/金融/安全/真实性认证，以及任何未支持的场景。

边界也要明确：这个 gate 只证明“当前 metadata 证据足以进入受控交付”，不证明客户
已经采用，不证明事实绝对正确，也不授权不可逆的生产操作。
