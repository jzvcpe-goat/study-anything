# Product Positioning / 项目定位

## Canonical Position

**Cognitive Black Box Protocol is an open protocol for scoped AI delivery trust,
with a local-first reference harness in this repository.**

**认知黑箱协议是一套面向 AI 交付范围化信任的开放协议，本仓库提供其本地优先参考实现。**

It is not primarily a standalone application, a learning product, an AI reviewer,
or a generic safety score. It standardizes what evidence a specific AI-generated
candidate must carry before it may move into a higher delivery scope.

它首先不是独立 App、学习产品、AI 审核员或通用安全分数，而是一套交付证据协议：
规定某个 AI 候选交付物进入更高现实范围前，必须携带什么证据。

## Core Promise

AI delivery is not trusted because it looks correct. It earns scoped trust when:

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

CBB Protocol rejects both false trust roots:

- **AI reviewing AI** may discover useful evidence, but cannot be the final authority.
- **Human approval alone** is insufficient when the reviewer did not reconstruct the
  delivery boundary or lacks the required scope qualification.

The protocol is a controlled-release mechanism. Its purpose is not to hold AI at
every step. Its purpose is to make it possible to let go within a boundary that is
understood, evidenced, reversible, and auditable.

CBB Protocol 同时拒绝两个虚假信任根：AI 审 AI 只能发现辅助证据，不能成为最终权威；
人类点击批准也不够，审核者必须能重构交付边界，并具备该范围所需的资格。

它是一种受控释放机制。目标不是在每一步抓住 AI，而是让人类能够在已理解、可证明、
可回滚、可审计的边界内放心放手。

## Product Structure

| Layer | Canonical role | Not this |
|---|---|---|
| CBB Protocol | Open contracts, receipts, conformance, claim boundaries | A vendor product |
| CBB Reference Harness | Deterministic local implementation and verifier suite | Production certification |
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
- CBB protocol receipts, deterministic gates, receipt chains, and self-intake;
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

CBB Protocol is designed to evolve with models, humans, projects, and delivery
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

The canonical public name is **Cognitive Black Box Protocol** or **CBB Protocol**.
`Study Anything`, `study-anything`, `study_anything`, and `cognitive_loop_*` remain
where compatibility requires them. They must not be used as the top-level product
identity in README first-view copy, repository metadata, protocol docs, or generated
artifact branding.

See [Naming and Compatibility](naming-and-compatibility.md) for the migration rules.
