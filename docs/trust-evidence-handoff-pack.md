# Trust Evidence Handoff Pack

Trust Evidence Handoff Pack Lite is the portable, metadata-only bundle that lets
an external operator, customer reviewer, or platform Agent inspect the current
AI delivery trust boundary without reading the whole repository.

It combines:

- Delivery Class Registry
- Code Review Delivery Class evidence
- Client Report Delivery Class evidence
- Trust Scenario Catalog
- Trust Scenario Decision Gate
- Delivery Trust Case Pack
- deterministic allow/block fixtures
- claim-boundary and privacy assertions

The pack answers:

> Which AI delivery handoffs are currently allowed, which shortcuts remain
> blocked, and what evidence must survive before anything customer-visible can
> be handed off?

## Boundary

The pack does not call models, start a daemon, mutate production, send customer
messages, publish externally, certify truth, or include raw source text, raw
report text, customer payloads, screenshots, attention streams, secrets, bearer
tokens, signed URLs, or user-owned Agent credentials.

It proves only that the current metadata evidence can be inspected from a
portable package.

## Commands

Generate:

```bash
python3 scripts/generate_trust_evidence_handoff_pack.py --write
```

Verify generated files:

```bash
python3 scripts/generate_trust_evidence_handoff_pack.py --check
```

Verify from ZIP only:

```bash
python3 scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py --check
```

Run the external operator acceptance drill:

```bash
python3 scripts/verify_trust_evidence_acceptance_drill.py --check
```

## 中文说明

Trust Evidence Handoff Pack Lite 是一个可下载、可解压、只含 metadata 的交付信任
证据包。它的目的不是让用户相信一句宣传语，而是让外部操作者、客户审阅者或平台
Agent 能够从一个包里检查：

- 当前支持哪些受控交付场景；
- code review / client report 这类具体交付类的 pass、blocked、negative check
  矩阵是否可离线检查；
- 哪些场景和 shortcut 必须被阻断；
- 需要哪些 Dual Loop、Delivery Trust、主动人类重建和交付类证据；
- 当前 claim boundary 到哪里为止。

它不读取或打包原文、报告正文、客户资料、截图、注意力流、密钥、cookie、Bearer
token、signed URL 或用户自己的 Agent 凭证，也不调用模型、不启动服务、不改生产、
不自动发客户。

这一步的产品意义是：把“AI 结果为什么可以交付、为什么不能越界”变成一个外部可验
的证据包，而不是让人重新人工复查每一步，也不是让另一个黑箱 AI 去审 AI。
