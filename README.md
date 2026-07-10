# Cognitive Black Box Protocol / 认知黑箱协议

**An open, local-first receipt protocol and reference harness for scoped AI delivery trust.**

**面向 AI 交付信任收据的开放协议与本地优先参考实现。**

Cognitive Black Box Protocol, or CBB Protocol, defines the evidence an AI-generated
deliverable must carry before it may move into a higher delivery scope. It does not
prove that AI is always correct. It proves only that a specific candidate passed a
specific policy with bounded failure evidence, qualified human reconstruction, a
deterministic propagation gate, and an explicit claim boundary.

认知黑箱协议定义了 AI 生成交付物进入更高交付层级前必须携带的证据。它不证明 AI
永远正确，只证明某个候选交付物在明确范围内通过了可控失败、合格的人类边界重构、
确定性传播门和带声明边界的收据。

> AI delivery is not trusted because it looks correct. It is trusted only within the
> scope proved by its receipts.
>
> AI 交付不是因为“看起来对”而可信，只在收据证明的范围内获得信任。

## Protocol, Harness, Adapters

This repository contains three different things. They must not be confused:

1. **CBB Protocol** defines portable contracts, evidence classes, gates, receipts,
   conformance rules, and claim boundaries.
2. **CBB Reference Harness** is this repository's deterministic, local-first
   implementation of those contracts.
3. **Adapters** connect existing workflows to the protocol. Study Anything is the Human
   Reconstruction / Learning Adapter. Cognitive Loop is an internal evidence and evolution
   workflow, not the product name.

本仓库同时包含协议、参考实现和适配器，但三者不是同一个概念：

1. **CBB Protocol** 定义可携带契约、证据类型、门控、收据、一致性规则和声明边界。
2. **CBB Reference Harness** 是本仓库的确定性、本地优先参考实现。
3. **Adapters** 把现有工作流接入协议。Study Anything 是 Human Reconstruction / Learning
   Adapter；Cognitive Loop 是内部证据与演进工作流，不再是产品名称。

The repository and Python distribution retain the historical `study-anything` name
for compatibility. That identifier does not define the current product position.

仓库名和 Python 分发名暂时保留历史标识 `study-anything` 以维持兼容，但它不再定义项目定位。

## Trust Contract

```text
Scoped Delivery Trust =
  Controlled Failure Evidence
  + Qualified Human Reconstruction
  + Deterministic Propagation Gate
  + Risk Owner and Recipient Scope
  + Claim-Bounded Delivery Receipt
  + Verifiable Provenance
```

The protocol rejects two common shortcuts:

- another AI saying the result is safe;
- a fatigued human clicking approve without reconstructing the critical boundary.

协议拒绝两种常见捷径：把 AI 审 AI 当作最终信任来源，以及让疲劳的人类在没有重构
关键边界时点击批准。

## Core Flow

```text
AI candidate
  -> Controlled Failure Environment
  -> Qualified Human Reconstruction
  -> Dual-Loop Propagation Gate
  -> Delivery Trust Receipt
  -> Customer Handoff Package
  -> Outcome Receipt and trust update
```

- **Controlled Failure Environment** exposes failure inside an observable,
  reversible scope before it can propagate.
- **Qualified Human Reconstruction** asks the human to recreate the critical control
  boundary, not reread every token.
- **Dual-Loop Gate** requires both evidence loops. Neither AI self-review nor human
  confidence may override the other side.
- **Delivery Trust Receipt** states what was checked, who owns the risk, which scope
  is allowed, and what is not claimed.
- **Customer Handoff Package** carries an allowed receipt and its referenced evidence.
  It cannot expand the approved scope.
- **Outcome Receipt** is the planned post-delivery feedback object that can reduce,
  revoke, or rebuild trust.

## Current Reference Implementation

The current `main` line includes deterministic, metadata-only implementations for:

- controlled failure contracts and sandbox receipts;
- attention reconstruction traces and summaries;
- Dual-Loop gate receipts;
- Delivery Trust Receipts and Customer Handoff Packages;
- CBB protocol contracts, deterministic gates, receipt chains, and self-intake;
- a canonical v1 Trust Kernel with hard-deny, evidence-state, scope, and static
  runtime-isolation verifiers;
- delivery-class, scenario, external feedback, and controlled handoff evidence;
- local API, Skill, platform-Agent, Docker, and static HTML artifact adapters;
- local release, security, adoption, and external-audit preparation evidence.

The reference harness can use Agentic workflows, RAG, and function calls in adapter
or evidence-discovery layers. Those layers may propose evidence and policy changes.
They may not rewrite the deterministic Trust Kernel, approve themselves, or turn
model output into the final trust root.

当前参考实现允许在适配器和证据发现层使用 Agentic workflow、RAG 和 function call。
这些层可以提出证据和策略变更，但不能改写确定性 Trust Kernel、给自己放权，或把模型
输出变成最终信任根。

## Claim Boundary

The current implementation is a local-first deterministic reference harness. It is
not:

- production deployment approval;
- legal, regulatory, security, or domain certification;
- a guarantee of customer outcomes;
- proof of general model correctness;
- proof that an independent human security audit has completed;
- permission for automatic customer sending or irreversible external effects.

The generated external security audit pack is `ready_for_independent_audit`. It is
not an audit report or certificate.

当前实现是本地优先、确定性的参考实现，不是生产批准、法律或安全认证、客户结果保证、
模型全局正确证明，也不代表独立人工安全审计已经完成。

## Verify The Protocol Core

From a prepared checkout:

```bash
.venv/bin/python scripts/verify_cbb_positioning.py --check
.venv/bin/python scripts/verify_cbb_protocol_contracts.py --check
.venv/bin/python scripts/verify_cbb_gate.py --check
.venv/bin/python scripts/verify_cbb_receipt_chain.py --check
.venv/bin/python scripts/verify_cbb_self_intake.py --check
.venv/bin/python scripts/verify_cbb_delivery_harness.py --check
./scripts/release_check.sh --cbb-protocol-only
```

`--cbb-protocol-only` is partial verification. It is not a full release check.

To run the historical Study Anything adapter without Docker:

```bash
./scripts/run_skill_mode_demo.sh
```

To launch the local API:

```bash
./scripts/launch_skill_mode.sh --foreground
```

## Self-Host And Published Images

The latest tagged binary/image line remains `v0.3.31-alpha` until a new tag is cut.
Current `main` contains later reference-harness work and must not be described as an
already published image.

Source build:

```bash
./scripts/setup.sh
docker compose --env-file .env -f infra/compose/docker-compose.yml up --build
```

Published-image path:

```bash
USE_PUBLISHED_IMAGES=true ./scripts/self_host_up.sh
python3 scripts/verify_published_image_launch.py --check
```

The release tooling verifies non-ASCII workspace paths as part of deployment
hardening. See [Self Hosting](docs/self-hosting.md) for the full boundary.

## Platform-Agent Adapters

The repository retains compatible packs for Codex, Kimi-compatible hosts,
WorkBuddy-style HTTP workspaces, Hermes Agent, and generic OpenAPI consumers.
These packs are adapters, not the protocol itself. Real model credentials, browser
access, private tools, and external applications remain owned by the user's Agent.

The developer/operator advisory review uses
`platform/prompts/cognitive-loop-review-agent.json` when an external platform Agent
is asked to produce JSON-only review evidence. That evidence is supporting material,
not an autonomous release decision.

## Documentation

- [Protocol](docs/protocol.md)
- [Trust model](docs/trust-model.md)
- [Receipt protocol](docs/receipt-protocol.md)
- [Architecture](docs/architecture.md)
- [Product positioning](docs/product-positioning.md)
- [Naming and compatibility](docs/naming-and-compatibility.md)
- [CBB Protocol v1 development plan](docs/cbb-protocol-v1-development-plan.md)
- [CBB Protocol v1 deterministic Trust Kernel](docs/cbb-protocol-v1-kernel.md)
- [CBB Protocol v1 local provenance](docs/cbb-protocol-v1-provenance.md)
- [Roadmap](docs/roadmap.md)
- [Delivery Trust Receipt](docs/delivery-trust-receipt.md)
- [Customer Handoff Package](docs/customer-handoff-package.md)
- [Study Anything adapter](docs/adapters/study-anything.md)
- [Security](docs/security.md)
- [External audit guide](security/audit/README.md)

## Development Priority

The protocol spine comes before new frontend, plugin, learning-experience, or hosted
service expansion. Work is prioritized when it strengthens at least one of these:

1. protocol portability and conformance;
2. receipt provenance and tamper evidence;
3. qualified reconstruction and scenario coverage;
4. outcome feedback, revocation, and trust degradation;
5. isolation of Agentic evidence discovery from the deterministic Trust Kernel;
6. independent external review and real controlled adoption evidence.

See [the v1 development plan](docs/cbb-protocol-v1-development-plan.md) for the
ordered implementation and acceptance gates.

## License

Apache-2.0. The protocol core and local reference harness remain open and
vendor-neutral.
