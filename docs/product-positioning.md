# Delivery Clearance Product Positioning / 产品定位

## Canonical Position

**Delivery Clearance is the public product identity. AI Delivery Clearance Protocol
is an open protocol for scoped AI delivery clearance, with a local-first reference
harness in this repository.**

**Delivery Clearance 是公开产品名称；AI 交付放行协议是一套面向范围化 AI 交付放行的
开放协议，本仓库提供其本地优先参考实现。**

**未经放行，不得交付。**

**Delivery Clearance does not prove that AI is always correct. It proves why this
delivery may move forward, to whom, for what purpose, within what limits, and under
whose responsibility.**

**AI 交付放行协议不证明 AI 永远正确；它证明这次交付为什么可以继续向前、可以交给谁、
可以用于什么、受到哪些限制，以及由谁承担责任。**

It is not primarily a standalone application, a learning product, an AI reviewer,
or a generic safety score. It standardizes what evidence a specific AI-generated
candidate must carry before it may move into a higher delivery scope.

它首先不是独立 App、学习产品、AI 审核员或通用安全分数，而是一套交付证据协议：
规定某个 AI 候选交付物进入更高现实范围前，必须携带什么证据。

## Cognitive Load Contract

Delivery Clearance does not replace human judgment. It removes repeated judgment. Evidence that is
already bounded, reproducible, current, and receipt-backed stays machine-verifiable;
humans receive only the unresolved boundary delta:

```text
Human decision load =
  unresolved boundary delta
  + novel context
  + residual risk
  + requested scope change
```

If the final human surface requires exhaustive rereading, the implementation has
failed the product mission even when every technical verifier passes.

Delivery Clearance 不替代人类判断，而是消除重复判断。已被约束、可复验、仍然有效并由收据绑定的
部分留在机器证据层；人类只处理新增边界、陌生上下文、残余风险和范围变化。如果最终
仍要求人类全文重读，那么即使技术检查通过，产品使命也没有完成。

## Core Promise

An AI delivery receives clearance only when:

1. failure has been exposed inside a bounded, observable, reversible environment;
2. a qualified human has reconstructed the critical boundary;
3. a deterministic gate verifies both loops and the declared policy;
4. risk owner, recipient, affected-party, rollback, and claim boundaries are explicit;
5. the result carries a verifiable receipt that can expire, be challenged, or be revoked.

AI 交付不是因为“看起来对”而可信。它只有在以下条件成立时，才获得限定范围的信任：

1. 失败已经在可观察、可逆、有边界的环境中暴露；
2. 合格的人类已经重构关键控制边界；
3. 确定性门控同时验证两个闭环和声明的策略；
4. 风险承担者、接收者、受影响者、回滚和声明边界明确；
5. 结果携带可复验、可过期、可质疑、可撤销的收据。

## What Makes It Different

### Controlled Release, Not Permanent Restraint

Delivery Clearance rejects both false trust roots:

- **AI reviewing AI** may discover useful evidence, but cannot be the final authority.
- **Human approval alone** is insufficient when the reviewer did not reconstruct the
  delivery boundary or lacks the required scope qualification.

The protocol is a controlled-release mechanism. Its purpose is not to hold AI at
every step. Its purpose is to make it possible to let go within a boundary that is
understood, evidenced, reversible, and auditable.

Delivery Clearance 同时拒绝两个虚假信任根：AI 审 AI 只能发现辅助证据，不能成为最终权威；
人类点击批准也不够，审核者必须能重构交付边界，并具备该范围所需的资格。

它是一种受控释放机制。目标不是在每一步抓住 AI，而是让人类能够在已理解、可证明、
可回滚、可审计的边界内放心放手。

## Product Structure

| Layer | Canonical role | Not this |
|---|---|---|
| AI Delivery Clearance Protocol | Open contracts, receipts, conformance, claim boundaries | A vendor product |
| Delivery Clearance Reference Harness | Deterministic local implementation and verifier suite | Production certification |
| `cbb.*` compatibility namespace | Stable Protocol v1 schemas and implementation identifiers | Public product name |
| Dual Loop | Equal-weight controlled-failure and human-reconstruction evidence | The entire protocol |
| Cognitive Loop | Internal evidence/evolution workflow | Top-level product name |
| Study Anything Adapter | Human Reconstruction / Learning Adapter | Project center |
| Platform packs | Adapter and distribution surfaces | Trust roots |

## Primary Users

- AI builders who need to know how far a candidate may safely propagate;
- maintainers and operators who need machine-checkable delivery evidence;
- organizations defining risk ownership, affected parties, and claim boundaries;
- Agent and tool vendors implementing portable receipt and conformance support;
- human reviewers who need focused reconstruction instead of exhaustive rereading.

## Current Shipped Boundary

Current `main` provides a deterministic, metadata-only reference harness with:

- Dual-Loop contracts and negative fixtures;
- Delivery Trust Receipt and Customer Handoff Package contracts;
- Protocol receipts, deterministic gates, receipt chains, and self-intake;
- local signed provenance and tamper verification;
- scoped scenarios, recipients, risk owners, affected parties, safeguards, MRUs,
  and challengeable human/model capability profiles;
- delivery-class, scenario, external-feedback, and controlled-handoff evidence;
- local API, Skill, platform-Agent, Docker, and static artifact adapters;
- release, security, adoption, and independent-audit preparation evidence.

The historical `study-anything` package and API remain available as compatibility
surfaces. They are not renamed in place because that would break adopters and receipt
references.

## Not Shipped Or Not Proven

- general AI correctness;
- production deployment approval;
- legal, regulatory, security, or domain certification;
- independent human security audit completion;
- customer outcome guarantees;
- an autonomous self-evolving policy authority;
- hosted multi-tenant commercial operations;
- automatic customer sending or irreversible production mutation.

## Living Protocol Boundary

AI Delivery Clearance Protocol is designed to evolve with models, humans, projects, and delivery
contexts. The stable part is the deterministic Trust Kernel. The adaptable part may
use RAG, function calls, Agentic workflows, failure memory, and capability evidence
to plan checks or propose policy changes.

The adaptable layer may not:

- grant itself new delivery authority;
- weaken hard denies;
- treat model claims or memory as truth;
- alter signed receipts after the fact;
- bypass risk ownership or qualified reconstruction;
- approve a change to its own Trust Kernel.

Every protocol evolution must itself produce evidence, pass a bounded replay or
canary, preserve rollback, and emit an evolution receipt.

## Distribution Position

The core stays Apache-2.0, open, local-first, and vendor-neutral. A future commercial
offering may sell hosted operations, team workflows, evidence retention, integration,
and support. It must not make the open protocol, local verifier, or user-owned data
dependent on a paid standalone app.

## Naming Boundary

The canonical public product name is **Delivery Clearance**. The canonical protocol
name is **AI Delivery Clearance Protocol** or **AI 交付放行协议**. `CBB`, `cbb.*`,
`Study Anything`, `study-anything`, `study_anything`, and `cognitive_loop_*` remain
where compatibility requires them. They must not be used as the top-level product
identity in README first-view copy, repository metadata, protocol entry docs, or
generated artifact branding.

See [Naming and Compatibility](naming-and-compatibility.md) for the migration rules.

The old learning-product and plugin-ecosystem design has no public product authority.
It survives only where an adapter, compatibility identifier, fixture, or historical
record is required and must never re-enter the GitHub first-view narrative.
