# Controlled Handoff Runbook

Controlled Handoff Runbook is the operator layer after the Trust Evidence
Acceptance Drill.

It answers the next practical question:

> If the Trust Evidence ZIP says a delivery class may enter controlled handoff,
> what may Codex, Kimi, WorkBuddy, Hermes, or a human operator do next without
> accidentally turning evidence into production approval?

The answer is intentionally narrow:

- prepare a metadata-only handoff packet;
- attach the claim boundary;
- keep blocked paths blocked;
- require final human scope confirmation;
- stop before customer sending, production mutation, external publication, or
  truth certification.

It consumes:

- `platform/generated/study-anything-trust-evidence-acceptance-drill.json`

It emits:

- `platform/generated/study-anything-controlled-handoff-runbook.json`
- `platform/generated/study-anything-controlled-handoff-runbook.md`

## Boundary

The runbook is metadata-only. It does not call models, start a daemon, mutate
production, send customer messages, publish externally, certify truth, include
raw source text, include raw diffs, include report bodies, include customer
payloads, include screenshots, read attention streams, or store user-owned
Agent credentials.

It proves only that an external operator or platform Agent can transform
accepted evidence into controlled handoff preparation steps while preserving all
blocked paths and claim limits.

## Command

```bash
python3 scripts/verify_controlled_handoff_runbook.py --check
```

Regenerate:

```bash
python3 scripts/verify_controlled_handoff_runbook.py --write
```

## 中文说明

Controlled Handoff Runbook 是 Acceptance Drill 之后的一层：它不再只回答
“能不能 allow/block”，而是回答“如果允许 controlled handoff，平台 Agent 或人类
操作者下一步到底能做什么”。

它允许的动作很窄：

- 准备 metadata-only handoff packet；
- 附上 claim boundary；
- 保持 blocked case 继续阻断；
- 要求最终的人类 scope 确认；
- 停在客户发送、生产变更、外部发布、真理认证之前。

这一步的意义是把“证据能被外部验收”推进到“外部平台 Agent 能按证据准备交付”，
同时仍然不把本地确定性证据包装成生产批准或客户结果保证。
