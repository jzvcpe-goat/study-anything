# 认知黑箱 / Cognitive Black Box

**Dual-Loop Trust Harness for AI delivery. / 面向 AI 交付的双闭环信任机制。**

**Cognitive Black Box** is a local-first trust harness for AI-generated deliverables. Its goal is to make AI work handoff-worthy without depending on exhaustive human re-review or opaque AI-reviewing-AI approval. It does this by combining a controlled failure environment, a human attention reconstruction environment, a Dual-Loop propagation gate, and a delivery trust receipt.

**认知黑箱** 是一个本地优先的 AI 交付信任机制。它的目标不是让人盲信 AI，也不是让人永远做疲劳式二次人工审核，更不是把 AI 审 AI 当成新的黑箱权威；它通过“可控失败环境 + 人类注意力重构环境 + 双闭环传播门 + 交付信任收据”，证明某个 AI 生成交付物在当前边界内是否可以交给客户。

The current MVP is deterministic and metadata-only. It proves the trust harness shape before any production mutation, model call, daemon, hosted service, or customer-impacting effect is allowed by default.

当前 MVP 是确定性、只含 metadata 的本地版本：它先证明信任机制本身，而不是默认允许生产改写、模型调用、常驻服务、托管服务或影响客户的外部效果。

Study Anything is now the **Learning Adapter** inside Cognitive Black Box. It remains useful, but it is no longer the product center. Its job is to help humans reconstruct and retain the boundaries needed for trustworthy AI handoff.

Study Anything 现在是认知黑箱里的 **学习适配层**。它仍然有价值，但不再是产品中心；它服务的是“人能否重构关键边界，从而支撑可信 AI 交付”。

## What It Is

- **Controlled Failure Environment**: AI may fail only inside an observable, reversible sandbox.
- **Human Attention Reconstruction Environment**: humans prove control by reconstructing key failure boundaries, not by approving every AI step.
- **Dual-Loop Propagation Gate**: promotion is blocked unless sandbox evidence and human reconstruction both pass.
- **Delivery Trust Receipt**: every customer handoff gets a claim boundary, risk result, rollback boundary, and machine-checkable receipt.
- **Study Anything Adapter**: a learning adapter that helps humans understand and remember the boundaries behind the handoff.

## 它解决什么

- **可控失败环境**：AI 只能在可观察、可逆的沙箱里失败。
- **人类注意力重构环境**：人类不是逐步点击批准，而是重构关键失败边界。
- **双闭环传播门**：沙箱证据和人类重构必须同时通过，否则不能升级交付层级。
- **交付信任收据**：每次客户交付前都有 claim boundary、风险结果、回滚边界和机器可验收收据。
- **Study Anything Adapter**：帮助人理解并记住交付背后的关键边界。

## Current Foundation

The current alpha already ships a local-first trust-harness foundation:

- Dual-Loop MVP: `failure-contract-v1`, `sandbox-receipt-v1`, `attention-reconstruction-trace-v1`, `attention-reconstruction-summary-v1`, and `dual-loop-gate-receipt-v1`.
- Delivery Trust Receipt: `delivery-trust-receipt-v1` turns Dual-Loop evidence into a controlled customer-handoff decision and rejects AI-review-only or eval-as-sufficient shortcuts.
- CustomerHandoffPackage: `customer-handoff-package-v1` packages an already-allowed Delivery Trust Receipt into portable JSON/HTML/ZIP evidence without expanding scope or becoming a new trust source.
- Dual Loop Trust Scenario Pack: a downloadable metadata-only ZIP that packages the customer-delivery scenario matrix, schemas, runner scripts, verifiers, and a ZIP-only consumer walkthrough for external operators and platform Agents.
- Product Loop Harness: `product-loop-scenario-v1` and `product-loop-run-v1` turn the Agentic Coding, Developer Feedback, and External Feedback loops into equal-weight metadata-only promotion evidence before Delivery Trust Harness handoff.
- Delivery Trust Case Harness: `delivery-trust-case-v1` assembles Product Loop, Dual Loop, Delivery Trust Receipt, and CustomerHandoffPackage evidence into one end-to-end controlled customer-handoff decision.
- Delivery Trust Case Pack: `delivery-trust-case-pack-v1` makes that decision portable for ZIP-only external consumer verification without source text, secrets, or customer payloads.
- FastAPI learning API and repo-local Skill Mode.
- Deterministic fake Agent for tests and demos.
- Bring Your Own Agent via user-owned HTTP gateway; Study Anything does not store real model keys.
- Source-bound learning loop: reading, teaching layers, quiz, grading, mastery, synthesis, scribe log, and discard/keep.
- Platform-Agent packs for Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, Hermes Agent Skill, and generic OpenAPI hosts.
- Redacted Agent audit/eval artifacts, multi-teacher attribution gates, and optional mature eval adapters.
- Learning Enrichment bridge for web, document, app, video-slice, Markdown, and Obsidian context.
- Obsidian export, NotebookLM-style manual bridge, second-brain handoff, and local archive evidence.
- Docker self-host path with Postgres, optional Langfuse, optional FalkorDB topology projection, and GHCR image evidence.
- Cognitive Loop contract bootstrap with `.cognitive-loop/config.yaml`, `permissions.yaml`, `evals.yaml`, `risk.yaml`, and `cognitive-loop-contract-bootstrap-v1` verification.
- LLM Depth Risk Engine Lite with metadata-only `PromptEvidence`, `HallucinationEvidence`, `RAGEvidence`, `ContextBudgetEvidence`, `CostQualityEvidence`, and a combined engineering-risk plus model-risk promotion gate.
- Real-Agent Eval Bridge for importing user-owned Promptfoo, Ragas, DeepEval, and LangChain AgentEvals receipts, plus WorkBuddy/Kimi/Codex learning-quality harness evidence.
- Optional Cognitive Loop manual watcher ingest with `.cognitive-loop/watchers.yaml`, metadata-only `ProjectEvent` artifacts, Event Index classification, and SQLite Event Store projection.

当前 alpha 已经具备本地优先的 trust harness 基础：

- Dual-Loop MVP：`failure-contract-v1`、`sandbox-receipt-v1`、`attention-reconstruction-trace-v1`、`attention-reconstruction-summary-v1` 和 `dual-loop-gate-receipt-v1`。
- Delivery Trust Receipt：`delivery-trust-receipt-v1` 把 Dual Loop 证据转成受控客户交付决策，并拒绝“AI 审 AI 即可放行”或“eval 结果足以放行”的捷径。
- CustomerHandoffPackage：`customer-handoff-package-v1` 把已 allowed 的 Delivery Trust Receipt 打包成可携带 JSON/HTML/ZIP 证据，不扩张 scope，也不成为新的信任来源。
- Dual Loop Trust Scenario Pack：可下载的 metadata-only ZIP，把客户交付场景矩阵、schema、runner 脚本、verifier 和只读 ZIP 消费者验收 walkthrough 打包给外部 operator 与平台 Agent 使用。
- Product Loop Harness：`product-loop-scenario-v1` 和 `product-loop-run-v1` 把 Agentic Coding、Developer Feedback、External Feedback 三个产品开发环变成同等权重的 metadata-only 升级证据，再进入 Delivery Trust Harness。
- Delivery Trust Case Harness：`delivery-trust-case-v1` 把 Product Loop、Dual Loop、Delivery Trust Receipt 和 CustomerHandoffPackage 证据总装成一次端到端的受控客户交付决策。
- Delivery Trust Case Pack：`delivery-trust-case-pack-v1` 把这份决策打包成可外部离线验证的 ZIP 证据包，不包含源码正文、密钥或客户载荷。
- FastAPI 学习 API 和仓库内 Skill Mode。
- 用于测试和 demo 的确定性 fake Agent。
- Bring Your Own Agent：真实推理由用户自己的 HTTP Agent Gateway 执行，Study Anything 不保存真实模型密钥。
- 基于来源的学习闭环：阅读、分层教学、测验、评分、掌握度、综合洞察、scribe log、保留或丢弃。
- 面向 Kimi-compatible、Codex Skill、WorkBuddy-style HTTP、Hermes Agent Skill 和通用 OpenAPI 平台的 Agent 接入包。
- 脱敏 Agent audit/eval 证据、多层教学归因验收，以及可选成熟 eval 适配。
- Learning Enrichment bridge：接收网页、文档、应用上下文、视频切片、Markdown、Obsidian 片段。
- Obsidian 导出、NotebookLM 式手动桥接、second-brain handoff、本地归档证据。
- Docker 自托管路径：Postgres、可选 Langfuse、可选 FalkorDB 拓扑投影、GHCR 镜像证据。
- Cognitive Loop contract bootstrap：`.cognitive-loop/config.yaml`、`permissions.yaml`、`evals.yaml`、`risk.yaml` 和 `cognitive-loop-contract-bootstrap-v1` 验证。
- LLM Depth Risk Engine Lite：用 metadata-only 证据覆盖 `PromptEvidence`、`HallucinationEvidence`、`RAGEvidence`、`ContextBudgetEvidence`、`CostQualityEvidence`，并通过“工程风险 + 模型风险”双通过 gate 决定能否 promote。
- Real-Agent Eval Bridge：导入用户自有 Promptfoo、Ragas、DeepEval、LangChain AgentEvals receipt，并提供 WorkBuddy/Kimi/Codex 学习质量 harness 证据。
- 可选 Cognitive Loop 手动 watcher ingest：`.cognitive-loop/watchers.yaml`、只含 metadata 的 `ProjectEvent` artifact、Event Index 分类和 SQLite Event Store 投影。

## Feasibility And Boundary

This pivot is feasible as a public positioning and architecture reset because the repo already contains a working local learning adapter, platform-Agent adoption assets, eval/audit evidence, privacy boundaries, and self-host paths. It is **not** a claim that the full Cognitive Loop runtime has shipped.

这次 pivot 适合作为公开定位和架构重置，因为仓库已经有可运行的本地学习适配层、平台 Agent 接入资产、eval/audit 证据、隐私边界和自托管路径。它 **不表示** 完整 Cognitive Loop runtime 已经交付。

Current shipped surface: Study Anything API, Skill Mode, platform-Agent packs, Docker self-host, learning/eval/export flows.

Planned surface: daemonized project watchers, production runtime gates, realtime HTML Artifact console, full personal plugins, governed source-changing auto-apply, and hosted/team services. Current bridge: a copy-ready Mastra adapter contract pack, a metadata-only runtime dry-run harness, a minimal repo-started Mastra runtime MVP under `platform/mastra-runtime/`, a local libSQL durable suspend/resume proof, a local Langfuse DTO mapping proof, a metadata-only Study Anything Adapter mastery projection proof, manual watcher ingest for metadata-only ProjectEvents, bounded watcher runner-lite, static metadata-only HTML Artifact Console Lite with Evolution Chain aggregation, Personal Plugin Mode Lite for read-only file/README/webpage/diff-summary learning artifacts, Evolution Report Lite for governed next-loop improvement proposals, Governed Apply Plan Lite for low-risk generated-artifact receipts, Measured Improvement Comparator Lite for read-only loop-to-loop evidence comparison, Patch Proposal Lite for six-category read-only patch specifications, Mastra Evolution Receipt Link Lite for metadata-only future Mastra workflow receipt DTOs, Mastra Evolution Workflow Replay Lite for read-only future workflow transcripts, Governed Patch Apply Sandbox Lite for metadata-only dry-run apply receipts that prove rollback without mutating the real worktree, Professional Evolution Pack Export Lite for redacted JSON/HTML/ZIP handoff to maintainers and platform Agents, Evolution Pack Consumer Smoke Lite for ZIP-only offline validation of that handoff, PR CI Receipt Lite for offline or explicit GitHub CLI metadata-only required-check evidence, and Maintainer Acceptance Ledger Lite for offline go/no-go review before merge or release.

当前已交付表面：Study Anything API、Skill Mode、平台 Agent 包、Docker 自托管、学习/eval/导出闭环。

计划中表面：常驻项目 watcher、生产级 runtime gate、实时 HTML Artifact console、完整个人插件、受治理的源码改写 auto-apply，以及后续 hosted/team 服务。当前桥接能力：一个可复制到外部 Mastra 项目的 Mastra adapter contract pack、只含 metadata 的 runtime dry-run harness、位于 `platform/mastra-runtime/` 的最小 repo-started Mastra runtime MVP、本地 libSQL 持久化 suspend/resume 证明、本地 Langfuse DTO 映射证明、metadata-only Study Anything Adapter 掌握度投影证明、面向 metadata-only ProjectEvent 的手动 watcher ingest、有界 watcher runner-lite、带 Evolution Chain 聚合的静态 metadata-only HTML Artifact Console Lite、用于只读文件/README/网页/diff-summary 学习 artifact 的 Personal Plugin Mode Lite、用于受治理下一轮改进建议的 Evolution Report Lite、用于低风险 generated-artifact receipt 的 Governed Apply Plan Lite、用于只读比较前后 loop evidence 的 Measured Improvement Comparator Lite、用于六类只读补丁规格的 Patch Proposal Lite、用于未来 Mastra workflow receipt DTO 的 metadata-only Mastra Evolution Receipt Link Lite、用于只读未来 workflow transcript 的 Mastra Evolution Workflow Replay Lite、用于证明 rollback 且不修改真实工作树的 metadata-only Governed Patch Apply Sandbox Lite、用于向维护者和平台 Agent 交付脱敏 JSON/HTML/ZIP 的 Professional Evolution Pack Export Lite、用于离线验证该 handoff ZIP 的 Evolution Pack Consumer Smoke Lite、用于离线或显式 GitHub CLI metadata-only required-check evidence 的 PR CI Receipt Lite，以及用于 merge/release 前离线 go/no-go 评审的 Maintainer Acceptance Ledger Lite。

## Target Architecture

```text
Cognitive Loop System
  ├── Product Entries
  │   ├── Personal Plugin Mode
  │   └── Professional HTML Artifact Mode
  ├── Cognitive Loop Core
  │   ├── ProjectEvent
  │   ├── DecisionCard
  │   ├── RiskEngine
  │   ├── HumanMasteryGate
  │   ├── EventStore
  │   ├── EvolutionReport
  │   ├── ImprovementComparison
  │   ├── PatchProposal
  │   ├── EvolutionReceiptLink
  │   ├── MastraEvolutionWorkflowReplay
  │   └── EvolutionPackManifest
  ├── Runtime Layer
  │   └── Mastra agents, workflows, tools, memory, HITL suspend/resume
  ├── Observability Layer
  │   └── Langfuse traces, prompts, evals, costs, scores
  ├── Learning Layer
  │   └── Study Anything Adapter
  ├── Project Layer
  │   ├── Watchers
  │   ├── Reverse Engine
  │   ├── Verifier
  │   └── Rollback
  └── Artifact Layer
      ├── Static HTML reports
      └── Realtime local HTML console
```

Daemonized project watchers, automated production runtime gates, the full realtime HTML Artifact console, full personal plugins, and governed source-changing auto-apply are **planned Cognitive Loop layers**, not shipped production-runtime claims. The current implementation includes public DecisionCard/Risk/Human Mastery Gate contracts, local static evidence artifacts, a local SQLite Event Store MVP for validated metadata-only event records, manual watcher ingest with `python3 scripts/cognitive_loop_watcher_ingest.py ingest --html`, bounded watcher runner-lite with `.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter`, a static metadata-only Artifact Console Lite with `python3 scripts/cognitive_loop_artifact_console.py build --html --json` that now aggregates Evolution Report, Apply Plan, Improvement Comparison, Patch Proposal, EvolutionReceiptLink, MastraEvolutionWorkflowReplay, PatchApplySandboxReceipt refs, and a Professional Evolution Pack export entry, Personal Plugin Mode Lite with `python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json`, Evolution Report Lite with `python3 scripts/cognitive_loop_evolution.py build --html --json`, Governed Apply Plan Lite with `python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json`, Measured Improvement Comparator Lite with `python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json`, Patch Proposal Lite with `python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json`, Mastra Evolution Receipt Link Lite with `python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json`, Mastra Evolution Workflow Replay Lite with `python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json`, Governed Patch Apply Sandbox Lite with `python3 scripts/cognitive_loop_patch_apply_sandbox.py sandbox --html --json`, Professional Evolution Pack Export Lite with `python3 scripts/cognitive_loop_evolution_pack_export.py export --html --json --zip`, Evolution Pack Consumer Smoke Lite with `python3 scripts/verify_cognitive_loop_evolution_pack_consumer.py --pack <cognitive-loop-professional-evolution-pack.zip>`, PR CI Receipt Lite with `python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --check` and optional `python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --from-gh-pr <PR> --write`, Maintainer Acceptance Ledger Lite with `python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check`, a Mastra adapter contract pack under `platform/mastra/`, `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` for a metadata-only suspend/resume/bail rehearsal, `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` for a minimal repo-started Mastra workflow MVP, `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` for local libSQL suspend/resume or bail across separate Node processes from watcher-generated metadata evidence, `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` for local Langfuse trace/span/generation/score DTO mapping without calling Langfuse, `python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` for routing a metadata-only ProjectEvent/DecisionCard through Study Anything into MasteryRecord evidence, and `.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html` for a platform-Agent-callable CLI Lite that writes JSON/HTML learning status, StudyCard, understanding gaps, scribe summary, MasteryRecord, and LoopRun evidence. The launch path remains API/Skill/platform-Agent first, without a standalone frontend requirement.

常驻项目监听器、自动化生产级 runtime gate、完整实时 HTML Artifact Console、完整个人插件和受治理源码改写 auto-apply 是 **下一阶段 Cognitive Loop 层**，不是当前仓库已经交付的生产级运行时能力。当前实现已经包含公开的 DecisionCard/Risk/Human Mastery Gate 契约、本地静态 evidence artifact、用于校验后 metadata-only event record 的本地 SQLite Event Store MVP、通过 `python3 scripts/cognitive_loop_watcher_ingest.py ingest --html` 执行的手动 watcher ingest、通过 `.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter` 执行的有界 watcher runner-lite、通过 `python3 scripts/cognitive_loop_artifact_console.py build --html --json` 生成的静态 metadata-only Artifact Console Lite、通过 `python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json` 执行的 Personal Plugin Mode Lite、通过 `python3 scripts/cognitive_loop_evolution.py build --html --json` 执行的 Evolution Report Lite、通过 `python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json` 执行的 Governed Apply Plan Lite、通过 `python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json` 执行的 Measured Improvement Comparator Lite、通过 `python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json` 执行的 Patch Proposal Lite、通过 `python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json` 执行的 Mastra Evolution Receipt Link Lite、位于 `platform/mastra/` 的 Mastra adapter contract pack、通过 `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` 验证的只含 metadata 的 suspend/resume/bail 演练、通过 `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` 验证的最小 repo-started Mastra workflow MVP、通过 `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` 验证的本地 libSQL 跨 Node 进程 suspend/resume 或 bail 证明、通过 `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` 验证的不调用 Langfuse 的本地 trace/span/generation/score DTO 映射、通过 `python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` 验证的 ProjectEvent/DecisionCard 到 Study Anything 再到 MasteryRecord 的 metadata-only 学习桥接，以及通过 `.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html` 执行的平台 Agent 可调用 CLI Lite，用来写出 JSON/HTML 学习状态、StudyCard、理解缺口、scribe 摘要、MasteryRecord 和 LoopRun evidence；上线路径仍然是 API/Skill/平台 Agent 优先，不要求独立前端。

## Public Conceptual Contracts

These names are documented now so future implementation work has a stable public vocabulary. They are conceptual contracts, not current HTTP endpoints:
The first local validator for these contracts is now available in `scripts/verify_cognitive_loop_contracts.py`. A companion local CLI can initialize the contracts, render a static HTML DecisionCard artifact with `python3 scripts/cognitive_loop_cli.py report --html`, produce one bounded local `LoopRun` / `DecisionCard` evidence cycle with `python3 scripts/cognitive_loop_cli.py run-once --html`, capture a redacted path-level project snapshot with `python3 scripts/cognitive_loop_cli.py snapshot --html`, record a local Human Mastery Gate approval or rejection with `python3 scripts/cognitive_loop_cli.py gate --approve --html`, create a metadata-only evidence bundle with `python3 scripts/cognitive_loop_cli.py bundle --html`, build a metadata-only local event timeline with `python3 scripts/cognitive_loop_cli.py index --html`, rebuild a local SQLite Event Store with `python3 scripts/cognitive_loop_event_store.py rebuild`, manually ingest watcher observations with `python3 scripts/cognitive_loop_watcher_ingest.py ingest --html`, batch/debounce explicit watcher signals with `.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter`, build a static metadata-only Artifact Console Lite with `python3 scripts/cognitive_loop_artifact_console.py build --html --json`, create read-only Personal Plugin Mode Lite learning artifacts with `python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json`, create governed Evolution Report Lite proposals with `python3 scripts/cognitive_loop_evolution.py build --html --json`, create governed low-risk Apply Plan Lite receipts with `python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json`, compare loop-to-loop improvement evidence with `python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json`, create read-only PatchProposal specs with `python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json`, create read-only EvolutionReceiptLink specs with `python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json`, check local artifact consistency with `python3 scripts/cognitive_loop_cli.py doctor --html`, create a manual-only repair plan with `python3 scripts/cognitive_loop_cli.py repair-plan --html`, open a static local artifact index with `python3 scripts/cognitive_loop_cli.py artifact-index --html`, run the Study Anything learning gate with `.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html`, and generate developer/operator advisory code-review evidence with `python3 scripts/cognitive_loop_review.py --base main --head HEAD --html`. `platform/mastra/cognitive-loop-mastra-adapter.ts` is a copy-ready Mastra workflow scaffold that maps Cognitive Loop evidence validation and Human Mastery Gate state to Mastra workflow step, suspend/resume, and bail semantics; verify it with `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check`, rehearse the runtime boundary with `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check`, start the minimal repo-local runtime with `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check`, prove local durable suspend/resume with `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check`, then verify local Langfuse DTO mapping with `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check`. The external Review Agent prompt contract for real line-level CI review lives at `platform/prompts/cognitive-loop-review-agent.json`, and its machine-checkable report schema lives at `platform/schemas/cognitive-loop-review-agent-report.schema.json`; this is delivery-assurance tooling for maintainers and platform Agents, not a Study Anything end-user learning feature. Watcher daemons, governed source-changing auto-apply, and the full realtime HTML console are still planned layers.

- `ProjectEvent`: normalized file, git, CI, runtime, human, or Agent event.
- `DecisionCard`: evidence-bound decision record with impact, risk, verification, human gate, and rollback plan.
- `LoopRun`: one bounded workflow execution cycle with status, trace refs, verification results, and artifacts.
- `MasteryRecord`: human understanding state for a topic, file, subsystem, or risky change.
- `EvolutionReport`: governed proposal for improving prompts, policies, evals, docs, tasks, retrieval, or learning paths.
- `ImprovementComparison`: read-only comparison of metadata-only loop artifacts showing whether the latest loop improved, regressed, stayed unchanged, lacks enough evidence, or needs review.
- `PatchProposal`: read-only patch specification across prompt, policy, eval, task, doc, and retrieval categories; it never contains raw unified diffs or executes apply.
- `EvolutionReceiptLink`: metadata-only linkage record that turns Evolution Report, Apply Plan, Improvement Comparison, and Patch Proposal evidence into a future Mastra workflow receipt DTO without starting Mastra, calling models, executing apply, or modifying source files.
- `MastraEvolutionWorkflowReplay`: metadata-only replay transcript that maps an EvolutionReceiptLink into future Mastra workflow steps, manual review gates, blocked states, and observability handoff without starting production Mastra or applying changes.
- `PatchApplySandboxReceipt`: metadata-only dry-run receipt that consumes PatchProposal, Apply Plan, EvolutionReceiptLink, and MastraEvolutionWorkflowReplay refs, proves rollback with a temporary sandbox preview, and confirms the real worktree was not mutated.
- `EvolutionPackManifest`: metadata-only professional handoff manifest that packages Artifact Console, EvolutionReport, ApplyPlan, ImprovementComparison, PatchProposal, EvolutionReceiptLink, MastraEvolutionWorkflowReplay, and PatchApplySandboxReceipt refs into redacted JSON/HTML/ZIP evidence for maintainers and platform Agents.
- `ReviewRun` / `ReviewFinding` / `ReviewDecision` / `ReviewMetrics`: advisory code-review evidence from path-level git or PR summary metadata, documented in `docs/cognitive-loop-code-review.md`; external CI/platform Agents can use `platform/prompts/cognitive-loop-review-agent.json` plus `platform/schemas/cognitive-loop-review-agent-report.schema.json` when the operator wants JSON-only line-level diff review.
- `CodeReviewHandoffCase`: metadata-only delivery-class evidence, documented in `docs/code-review-delivery-class.md`, that allows controlled code-review handoff only when Product Loop, Dual Loop, human reconstruction, source grounding, and CustomerHandoff boundaries pass; it does not allow automatic PR comments, customer sending, merges, deployments, or security-certification claims.
- `ClientReportHandoffCase`: metadata-only delivery-class evidence, documented in `docs/client-report-delivery-class.md`, that allows controlled client-report handoff only when Product Loop, Dual Loop, active human reconstruction, source grounding, bounded recipient scope, and CustomerHandoff boundaries pass; it does not send customer messages, publish externally, certify legal/financial advice, or include raw report/customer payload.
- `DeliveryClassRegistry`: metadata-only registry, documented in `docs/delivery-class-registry.md`, proving which delivery classes currently implement the same Dual Loop / Delivery Trust contract.
- `TrustScenarioCatalog`: metadata-only scenario catalog, documented in `docs/trust-scenario-catalog.md`, proving which AI delivery scenarios are currently supported, which shortcuts are blocked, and what Dual Loop evidence is required.
- `TrustScenarioDecision`: metadata-only gate receipt, documented in `docs/trust-scenario-decision-gate.md`, that turns a catalog scenario plus evidence/checkpoint metadata into an allow/block handoff decision.

这些名称先作为公开概念契约，方便后续实现保持稳定词汇。它们现在不是 HTTP endpoint：
第一版本地 validator 已经在 `scripts/verify_cognitive_loop_contracts.py` 中可用。配套本地 CLI 可以初始化契约，通过 `python3 scripts/cognitive_loop_cli.py report --html` 渲染静态 HTML DecisionCard artifact，通过 `python3 scripts/cognitive_loop_cli.py run-once --html` 生成一次有边界的本地 `LoopRun` / `DecisionCard` evidence cycle，通过 `python3 scripts/cognitive_loop_cli.py snapshot --html` 捕获脱敏的路径级项目 snapshot，通过 `python3 scripts/cognitive_loop_cli.py gate --approve --html` 记录本地 Human Mastery Gate 的批准或拒绝，通过 `python3 scripts/cognitive_loop_cli.py bundle --html` 创建只含 metadata 的 evidence bundle，通过 `python3 scripts/cognitive_loop_cli.py index --html` 构建只含 metadata 的本地事件 timeline，通过 `python3 scripts/cognitive_loop_event_store.py rebuild` 重建本地 SQLite Event Store，通过 `python3 scripts/cognitive_loop_watcher_ingest.py ingest --html` 手动摄入 watcher observation，通过 `.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter` 批处理/去重显式 watcher 信号，通过 `python3 scripts/cognitive_loop_artifact_console.py build --html --json` 生成静态 metadata-only Artifact Console Lite，通过 `python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json` 生成只读 Personal Plugin Mode Lite 学习 artifact，通过 `python3 scripts/cognitive_loop_evolution.py build --html --json` 生成受治理的 Evolution Report Lite 改进建议，通过 `python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json` 生成 Governed Apply Plan Lite，通过 `python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json` 比较 loop 改进证据，通过 `python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json` 生成只读 PatchProposal 规格，通过 `python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json` 生成只读 EvolutionReceiptLink 规格，通过 `python3 scripts/cognitive_loop_cli.py doctor --html` 检查本地 artifact consistency，通过 `python3 scripts/cognitive_loop_cli.py repair-plan --html` 创建仅手动执行的 repair plan，通过 `python3 scripts/cognitive_loop_cli.py artifact-index --html` 打开一个静态本地 artifact 入口页，并通过 `python3 scripts/cognitive_loop_review.py --base main --head HEAD --html` 生成面向 developer/operator 的咨询式代码审查证据；`platform/mastra/cognitive-loop-mastra-adapter.ts` 是可复制到 Mastra 项目的 workflow scaffold，会把 Cognitive Loop evidence validation 与 Human Mastery Gate 状态映射到 Mastra workflow step、suspend/resume 和 bail 语义，可用 `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check` 验证，通过 `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` 演练 runtime 边界，通过 `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` 启动最小本仓库 runtime，通过 `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` 验证本地持久化 suspend/resume，再通过 `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` 验证本地 Langfuse DTO 映射；真实行级 CI 审查的外部 Review Agent prompt contract 位于 `platform/prompts/cognitive-loop-review-agent.json`，机器可验收报告 schema 位于 `platform/schemas/cognitive-loop-review-agent-report.schema.json`，它服务维护者和平台 Agent，不是 Study Anything 面向终端用户的学习功能。常驻 watcher daemon、受治理 auto-apply 和完整实时 HTML console 仍然是计划中的层。

- `ProjectEvent`：标准化的文件、Git、CI、运行时、人类或 Agent 事件。
- `DecisionCard`：绑定证据的决策记录，包含影响、风险、验证、人类门禁和回滚计划。
- `LoopRun`：一次有边界的 workflow 执行循环，包含状态、trace 引用、验证结果和产物。
- `MasteryRecord`：人类对 topic、文件、子系统或高风险变更的理解状态。
- `EvolutionReport`：对 prompt、policy、eval、文档、任务、检索或学习路径的受治理改进提案。
- `ImprovementComparison`：只读比较 metadata-only loop artifacts，用来判断最新 loop 是改进、退化、无变化、证据不足，还是需要人工复核。
- `ReviewRun` / `ReviewFinding` / `ReviewDecision` / `ReviewMetrics`：来自路径级 git 或 PR 摘要元数据的咨询式代码审查证据，详见 `docs/cognitive-loop-code-review.md`；如果操作者需要 JSON-only 的真实 diff 行级审查，外部 CI/平台 Agent 应使用 `platform/prompts/cognitive-loop-review-agent.json` 和 `platform/schemas/cognitive-loop-review-agent-report.schema.json`。
- `CodeReviewHandoffCase`：只含 metadata 的交付类证据，详见 `docs/code-review-delivery-class.md`；只有 Product Loop、Dual Loop、人类重建、source grounding 和 CustomerHandoff 边界全部通过，才允许受控代码审查交接；它不允许自动 PR 评论、自动发客户、合并、部署或安全认证声明。
- `ClientReportHandoffCase`：只含 metadata 的交付类证据，详见 `docs/client-report-delivery-class.md`；只有 Product Loop、Dual Loop、主动人类重建、source grounding、受限接收方范围和 CustomerHandoff 边界全部通过，才允许受控客户报告交接；它不自动发客户、不外部发布、不认证法律/金融建议，也不包含报告原文或客户原始资料。
- `DeliveryClassRegistry`：只含 metadata 的交付类注册表，详见 `docs/delivery-class-registry.md`；用于证明哪些交付类型已经实现同一套 Dual Loop / Delivery Trust 契约。
- `TrustScenarioCatalog`：只含 metadata 的信任场景目录，详见 `docs/trust-scenario-catalog.md`；用于证明哪些 AI 交付场景当前可受控支持、哪些捷径必须阻断，以及需要哪些 Dual Loop 证据。
- `TrustScenarioDecision`：只含 metadata 的决策门 receipt，详见 `docs/trust-scenario-decision-gate.md`；把 catalog 场景、证据列表和主动重建 checkpoint 转成允许/阻断交付的本地决策。

Future project contract files:

```text
.cognitive-loop/config.yaml
.cognitive-loop/permissions.yaml
.cognitive-loop/evals.yaml
.cognitive-loop/risk.yaml
.cognitive-loop/watchers.yaml
```

Future CLI names, not implemented in this pivot:

```bash
cognitive-loop init
cognitive-loop import-repo .
cognitive-loop explain-diff --html
cognitive-loop report --html
cognitive-loop watch --html
```

## Fastest Local Demo

Use Skill Mode when you want to try the current Study Anything learning loop without Docker:

```bash
./scripts/run_skill_mode_demo.sh
```

For a persistent local API:

```bash
./scripts/launch_skill_mode.sh
```

If your shell does not preserve background processes:

```bash
./scripts/launch_skill_mode.sh --foreground
```

## Platform-Agent Adoption

Downloadable plugin packs are generated under `platform/generated/`:

- `study-anything-codex-plugin-pack.zip` for Codex Skills and terminal-capable Agents.
- `study-anything-kimi-plugin-pack.zip` for Kimi-compatible OpenAI tool imports.
- `study-anything-workbuddy-plugin-pack.zip` for WorkBuddy-style OpenAPI HTTP workspaces.
- `study-anything-hermes-plugin-pack.zip` for Hermes Agent Skill plus local HTTP/CLI usage.

Each pack has a matching `.json` manifest and `.sha256` checksum. The packs still call a local or
private Study Anything runtime; they do not contain model keys. WorkBuddy/CodeBuddy also has an
installable marketplace wrapper:

```text
/plugin marketplace add jzvcpe-goat/study-anything
/plugin install study-anything@study-anything
```

The marketplace wrapper is generated from `.codebuddy-plugin/marketplace.json` and
`plugins/study-anything/.codebuddy-plugin/plugin.json`; it exposes `/study-anything:start`,
`/study-anything:learn`, `/study-anything:diagnose`, and `/study-anything:export`.
For release downloads, use `docs/platform-plugin-downloads.md` or the generated index
`platform/generated/study-anything-platform-plugin-downloads.json`; the GitHub Release must attach
each plugin pack archive, manifest, and checksum sidecar.

For Kimi Work, Codex, WorkBuddy-style HTTP workspaces, Hermes Agent, or another platform Agent, verify the copy-ready adoption pack:

```bash
python3 scripts/generate_platform_plugin_packs.py --check
python3 scripts/verify_platform_plugin_packs.py --check
python3 scripts/generate_platform_plugin_downloads.py --check
python3 scripts/verify_platform_plugin_downloads.py --check
python3 scripts/generate_workbuddy_plugin_marketplace.py --check
python3 scripts/verify_workbuddy_plugin_marketplace.py --check
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The platform packs prove that an external Agent can import the tool surface, run one source-bound learning loop, return audit/eval evidence, and export Obsidian or NotebookLM-style handoff artifacts without requiring a standalone frontend or storing real model keys in Study Anything.
For scenario-based operation, use `docs/cognitive-loop-adoption-cookbook.md` to map Kimi, Codex, WorkBuddy, or a private platform Agent to first adoption, daily project review, risk decisions, and learning handoff.

四个可下载插件包分别面向 Codex、Kimi-compatible、WorkBuddy-style 和 Hermes Agent 平台。它们只负责导入工具和启动本地运行时；真实模型、浏览器、外部应用和密钥仍然由用户自己的平台 Agent 管理。

WorkBuddy/CodeBuddy 还可以通过 `/plugin marketplace add jzvcpe-goat/study-anything` 和
`/plugin install study-anything@study-anything` 安装插件包装层。它只负责命令、Skill 和
OpenAPI/local HTTP 接入；真实模型密钥仍不进入 Study Anything。

平台接入包证明：外部 Agent 可以导入工具面、跑完一次基于来源的学习闭环、返回 audit/eval 证据，并导出 Obsidian 或 NotebookLM 式交接材料；整个过程不要求独立前端，也不把真实模型密钥存入 Study Anything。
如果要按场景操作，请使用 `docs/cognitive-loop-adoption-cookbook.md`，它把 Kimi、Codex、WorkBuddy 或私有平台 Agent 映射到首次接入、日常项目审查、风险决策和学习交接四条路径。

## Docker Self-Host

Install Docker Desktop, start its daemon, then run:

```bash
python3 scripts/setup_env.py
./scripts/doctor.sh
./scripts/launch_self_host.sh
```

The default Docker profile is `core`: API and Postgres. Enable observability and optional topology services later with:

```bash
STACK_PROFILE=full ./scripts/launch_self_host.sh
```

If your checkout path contains non-ASCII characters, Docker Desktop BuildKit/buildx may fail before the app build starts. Use published images or clone to an ASCII-only path for local source builds.

## Published Image Evidence

The current release evidence line is `v0.3.31-alpha`. If local source builds are blocked by non-ASCII checkout paths, slow build layers, or Docker Desktop friction, use the published API image path:

```bash
python3 scripts/setup_env.py
USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh
python3 scripts/verify_published_image_launch.py --tag v0.3.31-alpha --manifest-only
```

This keeps Cognitive Loop positioning separate from deployability proof: the current published image evidence still belongs to the Study Anything learning-adapter runtime, while Mastra/watchers/HTML Artifact console remain planned layers.

## Bring Your Own Agent

Real reasoning stays outside Study Anything. The user-owned Agent controls model choice, credentials, tools, browser access, and external data. Study Anything sends structured learning tasks, validates structured results, and records redacted evidence.

真实推理留在 Study Anything 外部。用户自己的 Agent 负责模型选择、密钥、工具、浏览器和外部数据；Study Anything 只发送结构化学习任务、校验结构化结果，并记录脱敏证据。

Provider shapes:

- `fake_agent`: deterministic local provider for tests and demos.
- `http_agent`: user-owned local or private HTTP gateway, recommended for MVP usage.
- `cli_agent`: reserved adapter, disabled by default until explicitly allowlisted.
- `mcp_agent`: future plugin ecosystem extension point.

## Product Direction

Short term:

- Keep Study Anything stable as the learning adapter and platform-Agent tool surface.
- Publish the Cognitive Loop positioning and architecture.
- Add conceptual contracts for `ProjectEvent`, `DecisionCard`, `LoopRun`, `MasteryRecord`, and `EvolutionReport`.

Next stages:

- Harden Cognitive Loop Core around the local SQLite Event Store and static HTML reports.
- Add Mastra runtime as the workflow/Agent/HITL adapter.
- Keep extending LoopRun, DecisionCard, RiskScore, HumanGateResult, and EvalResult mapping into Langfuse-style traces and scores from local receipts.
- Convert project diffs and events into Study Anything learning sessions.
- Add file/Git/test/Agent watchers and a realtime local HTML console.

短期目标：

- 保持 Study Anything 作为学习适配层和平台 Agent 工具面的稳定性。
- 发布 Cognitive Loop 的新定位和架构说明。
- 明确 `ProjectEvent`、`DecisionCard`、`LoopRun`、`MasteryRecord`、`EvolutionReport` 等概念契约。

下一阶段：

- 围绕本地 SQLite Event Store 和静态 HTML 报告继续加固 Cognitive Loop Core。
- 用 Mastra 作为 workflow、Agent、HITL 的运行时适配层。
- 继续把 LoopRun、DecisionCard、RiskScore、HumanGateResult、EvalResult 从本地 receipt 映射到 Langfuse 风格 trace 和 score。
- 把项目 diff 与事件转成 Study Anything 学习会话。
- 增加文件/Git/测试/Agent watcher 和实时本地 HTML Console。

## Commercial Path

The project remains Apache-2.0 and local-first. Monetization is not a paid app gate. Future paid services should sell convenience, collaboration, reliability, and trust infrastructure:

- hosted encrypted sync
- team workspaces
- publish/share workflows
- trusted plugin/ecosystem distribution
- professional support and managed infrastructure

项目保持 Apache-2.0 和本地优先。商业化不应该变成“付费才能使用核心能力”。未来付费服务只销售便利性、协作性、可靠性和可信生态基础设施：

- 托管加密同步
- 团队工作区
- 发布/分享工作流
- 可信插件/生态分发
- 专业支持和托管基础设施

## Status

This repository is a public self-host alpha. The current implementation is strongest as a Study Anything learning adapter and platform-Agent integration package. The Cognitive Loop System pivot is the next product layer: a local-first control system for learning, reversing, operating, verifying, auditing, and evolving any AI-assisted project.

本仓库目前是公开 self-host alpha。当前实现最成熟的是 Study Anything 学习适配层和平台 Agent 接入包。Cognitive Loop System 是下一层产品定位：一个本地优先的控制系统，用于学习、逆向、运行、验证、审计和进化任何 AI 辅助项目。

See:

- `docs/product-positioning.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/platform-agent-integrations.md`
- `docs/security.md`
