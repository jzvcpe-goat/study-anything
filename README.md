# Delivery Clearance

## AI Delivery Clearance Protocol / AI 交付放行协议

**未经放行，不得交付。**

**Delivery Clearance does not prove that AI is always correct. It proves why this
delivery may move forward, to whom, for what purpose, within what limits, and under
whose responsibility.**

**AI 交付放行协议不证明 AI 永远正确；它证明这次交付为什么可以继续向前、可以交给谁、
可以用于什么、受到哪些限制，以及由谁承担责任。**

Delivery Clearance is an open, local-first protocol and reference harness for the
last decision before an AI-generated deliverable crosses a real-world responsibility
boundary. It requires controlled-failure evidence, qualified human reconstruction,
a deterministic clearance gate, explicit responsibility, and a claim-bounded receipt.

Delivery Clearance 是 AI 交付跨越现实责任边界前的最后一道开放协议与本地优先参考实现。
它要求可控失败证据、合格的人类边界重构、确定性放行门、明确的责任归属和受声明边界约束
的收据。

The protocol governs every responsibility transfer, not every model thought. Humans
do not reread the entire output by default. They handle only unresolved boundary
deltas, novel context, residual risk, and scope changes that deterministic evidence
cannot close.

## Protocol, Reference Harness, Adapters

This repository contains three different things. They must not be confused:

1. **AI Delivery Clearance Protocol** defines portable contracts, evidence classes,
   clearance gates, receipts,
   conformance rules, and claim boundaries.
2. **Delivery Clearance Reference Harness** is this repository's deterministic,
   local-first implementation. Existing `cbb.*` schemas and CBB module names remain
   compatibility identifiers.
3. **Adapters** connect existing workflows to the protocol. Study Anything is the Human
   Reconstruction / Learning Adapter. Cognitive Loop is an internal evidence and evolution
   workflow, not the product name.

本仓库同时包含协议、参考实现和适配器，但三者不是同一个概念：

1. **AI 交付放行协议**定义可携带契约、证据类型、放行门、收据、一致性规则和声明边界。
2. **Delivery Clearance Reference Harness** 是本仓库的确定性、本地优先参考实现；
   `cbb.*` schema 和 CBB 模块名仅作为兼容标识继续存在。
3. **Adapters** 把现有工作流接入协议。Study Anything 是 Human Reconstruction / Learning
   Adapter；Cognitive Loop 是内部证据与演进工作流，不再是产品名称。

The repository and Python distribution retain the historical `study-anything` name,
and Protocol v1 retains the `cbb.*` namespace, for compatibility. Neither identifier
defines the public product position.

仓库名和 Python 分发名暂时保留历史标识 `study-anything` 以维持兼容，但它不再定义项目定位。

## Trust Contract

```text
Delivery Clearance =
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
  -> Dual-Loop Clearance Gate
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
- **Outcome Receipt** records bounded post-delivery evidence and can maintain, narrow,
  freeze, or revoke trust without ever increasing the source clearance scope.

## Current Reference Implementation

The current `main` line includes deterministic, metadata-only implementations for:

- controlled failure contracts and sandbox receipts;
- attention reconstruction traces and summaries;
- Dual-Loop gate receipts;
- Delivery Trust Receipts and Customer Handoff Packages;
- Protocol v1 `cbb.*` compatibility contracts, deterministic gates, receipt chains,
  and self-intake;
- a canonical v1 Trust Kernel with hard-deny, evidence-state, scope, and static
  runtime-isolation verifiers;
- local Ed25519 provenance, tamper, expiry, replay, and revocation verification;
- scenario-scoped recipients, risk owners, affected parties, safeguards, Minimum
  Reconstructable Units, and challengeable human/model capability profiles;
- deterministic vibe-coding fixtures from personal-local use through blocked
  production and regulated/irreversible candidates;
- signed-source and locally signed post-delivery outcome receipts, bounded sampling,
  deterministic degradation replay, affected-party challenges, rollback failure,
  historical source binding, local revocation, and non-increasing trust updates;
- typed Agentic evidence tools, quarantined metadata memory, proposal/approver
  separation, and signed deterministic evolution-gate receipts that stop at a local
  candidate and never auto-apply;
- a deterministic Protocol v1 conformance pack and isolated second consumer that
  independently replay canonical bytes, gates, signatures, outcomes, evolution,
  version negotiation, extensions, and v0 migration without importing `study_anything`;
- bounded shadow/dogfood/canary adoption receipts plus an externally signed audit-report
  intake state machine that keeps synthetic fixtures, real adoption, remediation, and
  audit closure as separate evidence classes;
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
.venv/bin/python scripts/verify_cbb_v1_scenarios.py --check
.venv/bin/python scripts/verify_cbb_v1_qualification.py --check
.venv/bin/python scripts/generate_cbb_v1_conformance_pack.py --check
.venv/bin/python scripts/verify_cbb_v1_external_consumer.py --check
.venv/bin/python scripts/verify_cbb_controlled_adoption_outcomes.py --check
.venv/bin/python scripts/verify_cbb_external_audit_intake.py --check
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
- [Protocol v1 development plan](docs/cbb-protocol-v1-development-plan.md)
- [Protocol v1 deterministic Trust Kernel](docs/cbb-protocol-v1-kernel.md)
- [Protocol v1 local provenance](docs/cbb-protocol-v1-provenance.md)
- [Protocol v1 scenarios and qualification](docs/cbb-protocol-v1-scenarios-and-qualification.md)
- [Protocol v1 outcomes and trust degradation](docs/cbb-protocol-v1-outcomes.md)
- [Protocol v1 Agentic evidence and evolution gate](docs/cbb-protocol-v1-agentic-evolution.md)
- [Protocol v1 conformance](docs/cbb-protocol-v1-conformance.md)
- [Protocol governance](docs/protocol-governance.md)
- [Extensions and versioning](docs/extensions-and-versioning.md)
- [Compatibility and trademark](docs/compatibility-and-trademark.md)
- [Controlled adoption evidence](docs/cbb-controlled-adoption.md)
- [External audit report intake](docs/cbb-external-audit-intake.md)
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
