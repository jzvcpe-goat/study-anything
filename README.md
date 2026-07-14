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

## Audit Your Own Local Project

The first usable MVP is intentionally personal and local. It lets one operator constrain
an AI-assisted development process without claiming independent audit or external delivery
authority.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/delivery-clearance init --project /path/to/my-project
# Edit /path/to/my-project/.delivery-clearance/personal-clearance.json
.venv/bin/delivery-clearance audit \
  --project /path/to/my-project \
  --execute-checks \
  --accept-responsibility
.venv/bin/delivery-clearance verify --project /path/to/my-project
```

The generated receipt is bound to the exact Git-visible state, configured check results,
active boundary reconstruction, and a short validity window. Any project-state or config
change invalidates it. The only possible allowed scope is `personal_local`.

Configured checks run with the current user's permissions and are not OS-sandboxed by this
MVP. The receipt is self-attested, not independently reviewed. See
[Personal Local Clearance MVP](docs/personal-clearance-mvp.md) for the contract, artifacts,
exit codes, privacy boundary, and suggested pre-commit/pre-handoff use.

Installed plugin metadata is not runtime, semantic, or side-effect evidence. The
[real installed-plugin boundary study](docs/quality-audits/phase-42-real-plugin-boundary-study.md)
shows which narrow checks can support personal use and which plugin capabilities remain
ineligible for delivery clearance.

[Plugin Evidence Adapter v0.1](docs/plugin-evidence-adapter.md) turns those boundaries into a
deterministic pre-check for Personal Clearance. It requires runtime, input, effect, native, and
domain evidence according to the plugin's capability class. It never grants more than
`personal_local`; external writes, credential use, and observed external mutation hard-block.

## Validation
- The Personal Clearance MVP has a reproducible 14-case verifier and 12 focused tests covering normal clearance, stale state, config drift, expiry, tamper, missing evidence, replay, failed checks, and explicit human responsibility.
- A four-state real-project replay blocks three historical incomplete delivery states and moves only the converged 59/59 evidence state to human review; it authorizes no release by itself.
- A frozen 12-case real-Agent set now binds public GitHub tasks, non-empty Agent-generated patches, and published SWE-bench-Live outcomes across 12 repositories; it is an evaluation input, not an effectiveness result.
- Its local human protocol now separates metadata-only boundary reconstruction from digest-bound full issue/patch review; no real human sessions or comparative effect result have been recorded yet.
- Passing evidence is bound only to the exact Git-visible state and `personal_local` scope.
- Current results validate prototype mechanisms, not user value, AI correctness, customer delivery, production safety, or professional certification.
- Reproduce the real sequence with `.venv/bin/python scripts/delivery_clearance_project_scenarios.py --replace`.
- See [Validation](docs/VALIDATION.md) and the [real-Agent benchmark (中文)](docs/evaluation/real-agent-delivery-benchmark.zh-CN.md) for evidence, limitations, and the paired study still required.

## Evaluate The Protocol, Not The Story

The repository includes the public, paired **Native Agent vs Delivery Clearance
Benchmark v0.1 harness** and a frozen 40-case mechanism rehearsal. The observed
pilot is still in progress. The harness compares the same candidate, model/version,
context, tools, permissions, and budget across four arms: native Agent, strengthened
native Agent, an internal Delivery Clearance checklist, and an independent
non-waivable clearance gate.

```bash
.venv/bin/python scripts/delivery_clearance_benchmark.py run \
  --suite pilot-v0.1 \
  --arms native,strengthened,internal-checklist,external-clearance \
  --out .delivery-clearance/benchmarks/pilot-v0.1
```

The bundled 40-case run is a deterministic **mechanism rehearsal**, not evidence
that Delivery Clearance is effective. Its public task identities come from
SWE-bench-Live, TUA-Bench, tau-bench, and AgentDojo, but its balanced pass/fail
variants are synthetic and explicitly record that official scorers were not run.
An observed pilot requires scored candidates, blinded adjudication, per-decision
tool traces, real human-review sessions, and six observed ablations before it may
emit `pilot_complete`.

To move beyond gold/empty/nop controls, the repository also freezes a
[12-case real-Agent delivery set](docs/evaluation/real-agent-delivery-benchmark.zh-CN.md)
from an accepted SWE-bench-Live submission. It uses real public tasks and real
Agent patches, balanced across six published functional passes and six failures.
The raw review material stays local; committed assets contain only source
identity, digests, statistics, blinded packets, and an isolated functional
oracle. Paired Agent review, local scorer replay, human adjudication, and cost
measurement are still incomplete, so no effectiveness claim is allowed.

The benchmark now embeds a preregistered incremental review-economic plan and a
real-human evidence workflow. It compares each Agent baseline with independent
clearance and separately compares boundary reconstruction with blinded full
review. Missing reviewer-time or delay valuations remain unpriced resource use;
the system does not invent a cost-effectiveness result. Use
`human-evidence-status` to see which boundary, full-review, or adjudication
receipts are still missing.

Human reviewers can complete all three observed tasks in the local browser
[Human Review Cockpit](docs/evaluation/human-review-cockpit.md):

```bash
.venv/bin/delivery-clearance-review --max-items 5
```

The Cockpit binds only to `127.0.0.1`, keeps the three roles separate, hides
labels and Agent decisions, and stores aggregate receipts instead of raw answers.

For a concrete project workflow rather than public benchmark fixtures, replay the
[four-state real-project evaluation](docs/evaluation/real-project-validation.md)
([中文](docs/evaluation/real-project-validation.zh-CN.md)), then open its two-mode
boundary-vs-full-review protocol in the same Cockpit.

The optional `capture` command runs pinned real Codex reviewer arms in ephemeral
read-only workspaces. It withholds scorer outcomes and hidden labels, records only
metadata digests and usage, and remains incomplete until independent scorer,
adjudication, and human-reconstruction evidence is supplied.

The optional `preflight` command verifies pinned public source/scorer revisions,
selected task identities, license constraints, and local runtime prerequisites.
It emits a blocked prerequisite receipt when Docker, task data, asset review, or
an observed adapter is missing; it never treats source availability as scorer
execution or effectiveness evidence.

An AgentDojo fixed-candidate scorer bridge is included for bounded smoke tests.
It records utility/security receipts and hashed trajectory-boundary evidence,
but it remains separate from the 40-case observed pilot and cannot establish an
effectiveness claim by itself.

A tau-bench bridge also runs the pinned official deterministic environment
evaluator over preregistered fixed trajectories. It records five passing controls
and five policy-violation variants without exposing task payloads. This bridge uses
`EvaluationType.ENV`; it excludes natural-language judging and is not a full
tau-bench Agent-performance result.

See [Native Agent vs Delivery Clearance Benchmark v0.1](docs/evaluation/native-agent-vs-delivery-clearance.md)
for source revisions, license boundaries, methodology, statistics, artifacts,
and prohibited claims.

## Current Reference Implementation

The current reference implementation includes deterministic, metadata-only components for:

- a one-command personal-local clearance workflow for arbitrary local Git projects,
  with state-bound receipts, explicit per-run responsibility, configured check evidence,
  mutation detection, expiry, tamper replay, and an HTML report;
- a Plugin Evidence Adapter that keeps install metadata separate from runtime evidence and
  fails closed on external writes, credential use, unbound inputs, missing native checks, and
  missing professional-domain reconstruction;
- a four-arm paired benchmark harness with public-source task identities, frozen
  label isolation, metadata-only tool traces, human review-load measurement,
  exact paired statistics, incremental review-economic evaluation, six ablations,
  and claim-bounded mechanism/observed states;
  the observed 40-case pilot is not complete until the required real human sessions
  and blinded adjudications have been recorded;
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
not an audit report or certificate. The external-adopter attestation channel is
implemented, but the repository still records zero real external adopter evidence.
That external evidence is not a blocker for the personal-local MVP; it remains mandatory
before broadening claims to independent, customer, production, or regulated use.

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
.venv/bin/python scripts/verify_cbb_external_adoption_attestation.py --check
.venv/bin/python scripts/verify_cbb_external_audit_intake.py --check
.venv/bin/python scripts/verify_personal_clearance_mvp.py --check
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
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
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
