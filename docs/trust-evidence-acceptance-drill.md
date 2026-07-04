# Trust Evidence Acceptance Drill

Trust Evidence Acceptance Drill is the ZIP-only operator rehearsal above the
Trust Evidence Handoff Pack.

It answers a practical adoption question:

> If an external operator, customer reviewer, or platform Agent only has the
> portable Trust Evidence ZIP, can they decide which supported delivery-class
> cases may move to controlled handoff and which must stay blocked?

The drill consumes:

- `platform/generated/study-anything-trust-evidence-handoff-pack.zip`
- embedded Code Review Delivery Class evidence
- embedded Client Report Delivery Class evidence
- embedded claim-boundary and privacy metadata

It emits:

- `platform/generated/study-anything-trust-evidence-acceptance-drill.json`
- `platform/generated/study-anything-trust-evidence-acceptance-drill.md`

## Boundary

The drill is metadata-only. It does not call models, start a daemon, mutate
production, send customer messages, publish externally, certify truth, read raw
diffs, read report bodies, read customer payloads, or store user-owned Agent
credentials.

It proves only that a reviewer can derive controlled allow/block decisions from
the packaged evidence.

## Command

```bash
python3 scripts/verify_trust_evidence_acceptance_drill.py --check
```

Regenerate:

```bash
python3 scripts/verify_trust_evidence_acceptance_drill.py --write
```

## 中文说明

Trust Evidence Acceptance Drill 是一个“外部验收演练”：假设对方不读整个仓库，
只拿到 Trust Evidence ZIP，也能判断：

- code review / client report 哪些 pass case 可以进入受控 handoff；
- 哪些 missing reconstruction、risk over budget、scope expansion、AI-review-only
  case 必须阻断；
- claim boundary 是否仍然只允许 controlled handoff，而不是生产批准、自动发客户
  或真理认证。

这一步的意义是把“证据包可检查”推进到“外部操作者能按证据包做决策”，继续避免
过度人工复审和 AI 审 AI 黑箱。
