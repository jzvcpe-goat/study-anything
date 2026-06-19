# Roadmap / 路线图

This roadmap reframes Study Anything as the Learning Adapter inside Cognitive Loop System. The goal is to grow from a local-first learning loop into a project-level cognitive control layer for AI-assisted work.

这份路线图将 Study Anything 重新定位为 Cognitive Loop System 内部的学习适配层。目标是从本地优先的学习闭环，升级为面向 AI 辅助项目的项目级认知控制层。

## Current Foundation: Study Anything Alpha

Already present:

- Local-first FastAPI learning API.
- Skill Mode and Docker self-host launch paths.
- Deterministic demo Agent and Bring Your Own Agent HTTP gateway.
- Source-bound learning loop with teaching layers, quiz, grading, mastery, synthesis, scribe logs, and discard/keep.
- Platform-Agent packs for Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, and generic OpenAPI hosts.
- Agent audit/eval evidence, multi-teacher attribution gates, and optional mature eval adapters.
- Learning Enrichment, Obsidian export, NotebookLM-style manual bridge, and second-brain handoff.
- Local encrypted sync package foundation, plugin trust boundaries, support diagnostics, and release adoption evidence.

已具备：

- 本地优先 FastAPI 学习 API。
- Skill Mode 和 Docker 自托管启动路径。
- 确定性 demo Agent 和 Bring Your Own Agent HTTP gateway。
- 基于来源的学习闭环：分层教学、测验、评分、掌握度、综合洞察、scribe log、保留或丢弃。
- 面向 Kimi-compatible、Codex Skill、WorkBuddy-style HTTP 和通用 OpenAPI 平台的 Agent 接入包。
- Agent audit/eval 证据、多层教学归因验收和可选成熟 eval 适配。
- Learning Enrichment、Obsidian 导出、NotebookLM 式手动桥接和 second-brain handoff。
- 本地加密同步包基础、插件信任边界、support diagnostics 和 release adoption evidence。

## Current Release Evidence Anchors

The current public alpha line is `v0.3.31-alpha`. Keep these evidence contracts visible while the product positioning pivots to Cognitive Loop System:

- `platform-field-adoption-rehearsal-v1`: rehearses Kimi, Codex, WorkBuddy, and generic OpenAPI import paths.
- `platform-support-triage-v1`: turns external adopter failures into redacted GitHub support tickets.
- `platform-onboarding-readiness-v1`: proves first-adopter walkthroughs, fallback paths, maintainer labels, and release-blocker fixtures are present.
- `public-support-status-v1`: publishes support status without support-bundle private fields.
- `published-image-evidence-v1`: separates GHCR/image release evidence from local pull or network friction.
- `adopter-evidence-archive-v1`: packages public release/adoption proof for maintainers and external testers.

当前公开 alpha 线是 `v0.3.31-alpha`。产品定位转向 Cognitive Loop System 时，仍保留这些可验收证据契约：

- `platform-field-adoption-rehearsal-v1`：演练 Kimi、Codex、WorkBuddy 和通用 OpenAPI 导入路径。
- `platform-support-triage-v1`：把外部采用失败转成脱敏 GitHub support ticket。
- `platform-onboarding-readiness-v1`：证明首个外部采用者 walkthrough、fallback、维护者标签和 release blocker fixture 已存在。
- `public-support-status-v1`：发布不包含私有 support bundle 字段的支持状态。
- `published-image-evidence-v1`：区分 GHCR/image 发布证据与本地拉取或网络摩擦。
- `adopter-evidence-archive-v1`：为维护者和外部测试者打包公开 release/adoption 证据。

## Phase 0: Positioning And Public Contract

Goal: make the GitHub project understandable as Cognitive Loop System without claiming unbuilt runtime features.

Deliver:

- bilingual README positioning
- Cognitive Loop architecture doc
- product positioning doc
- roadmap reset
- clear status boundary between current Study Anything capabilities and planned Cognitive Loop layers
- public conceptual contracts for `ProjectEvent`, `DecisionCard`, `LoopRun`, `MasteryRecord`, and `EvolutionReport`
- implemented project contract bootstrap: `.cognitive-loop/config.yaml`, `.cognitive-loop/permissions.yaml`, `.cognitive-loop/evals.yaml`, `.cognitive-loop/risk.yaml`
- `cognitive-loop-contract-bootstrap-v1` verifier output
- future CLI names, clearly marked as not implemented yet

Acceptance:

- A new reader can understand the four-part direction: Study, Reverse, Operate, Evolve.
- Docs state that daemonized watchers and the full realtime HTML Artifact console are planned layers, while static metadata-only Console Lite is a current local artifact path.
- Docs keep the current no-standalone-frontend launch path scoped to Study Anything/platform-Agent usage.
- Docs keep real model credentials outside Study Anything.
- Docs preserve current release evidence anchors while changing the product narrative.
- `python3 scripts/verify_cognitive_loop_contracts.py --check` passes and rejects secret-like values, raw excerpts, and high-risk decisions without a human gate.

Future CLI vocabulary for this phase:

```bash
cognitive-loop init
cognitive-loop import-repo .
cognitive-loop explain-diff --html
cognitive-loop report --html
cognitive-loop watch --html
```

These commands are naming commitments for the next implementation stages, not commands shipped by this docs-only pivot.

这些命令是下一阶段实现的命名约定，不是本次 docs-only pivot 已经交付的 CLI。

## Phase 1: Cognitive Loop Core

Goal: create the framework-independent core.

Deliver:

- `ProjectEvent`
- `DecisionCard`
- `RiskEngine`
- `HumanMasteryGate`
- `LoopRun`
- `MasteryRecord`
- `EvolutionReport`
- SQLite Event Store MVP with metadata-only rebuild/export proof
- static HTML report generator v0
- implemented `.cognitive-loop/config.yaml`
- implemented `.cognitive-loop/permissions.yaml`
- implemented `.cognitive-loop/evals.yaml`
- implemented `.cognitive-loop/risk.yaml`

Acceptance:

- A manually supplied project event can produce a decision card.
- A decision card can render into a static HTML report.
- Validated event artifacts can be rebuilt into a local SQLite Event Store and exported without content payloads.
- Core state is stored outside Langfuse and outside Agent chat context.
- A fresh repo can run `cognitive-loop init` and receive the four core contract files.
- Contract loaders reject unsafe defaults, unknown high-risk permission downgrades, and secret-like config values.

## Phase 2: Mastra Runtime Adapter

Goal: use Mastra for Agent/workflow/tool/HITL execution while keeping Core as the source of truth.

Current:

- Mastra adapter contract pack is available under `platform/mastra/`.
- `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check` verifies the TypeScript scaffold, HITL mapping, and privacy boundary.
- `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` rehearses the metadata-only runtime boundary: high-risk run suspension, approved resume, rejected bail, and Event Store projection.
- `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` starts the minimal repo-local Mastra runtime MVP against `@mastra/core` and verifies suspend/resume/bail and no-gate paths.
- `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` proves local libSQL suspend/resume or bail across separate Node processes from watcher-generated metadata events.
- `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` maps service and durable receipts to local Langfuse trace/span/generation/score DTOs without calling Langfuse or leaking private runtime data.
- Manual watcher ingest exists through `.cognitive-loop/watchers.yaml` and `python3 scripts/verify_cognitive_loop_watcher_ingest.py --check`; bounded watcher runner-lite and static metadata-only Console Lite are current, while daemonized watcher input and realtime console integration are still planned.

当前：

- Mastra adapter contract pack 已位于 `platform/mastra/`。
- `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check` 会验证 TypeScript scaffold、HITL 映射和隐私边界。
- `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` 会演练只含 metadata 的 runtime 边界：高风险运行暂停、批准后 resume、拒绝后 bail，以及 Event Store 投影。
- `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` 会通过 `@mastra/core` 启动最小本仓库 Mastra runtime MVP，并验证 suspend/resume/bail 和无需 gate 的路径。
- `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` 已证明本地 libSQL 可基于 watcher 生成的 metadata event 跨独立 Node 进程 suspend/resume 或 bail。
- `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` 已将 service 和 durable receipt 映射为本地 Langfuse trace/span/generation/score DTO，并且不调用 Langfuse，也不泄露私有运行时数据。
- 手动 watcher ingest 已通过 `.cognitive-loop/watchers.yaml` 和 `python3 scripts/verify_cognitive_loop_watcher_ingest.py --check` 接入；有界 watcher runner-lite 和静态 metadata-only Console Lite 已是当前能力，常驻 watcher 输入和实时 console 集成仍然是计划中的层。

Deliver:

- repository-started Mastra workflow service MVP
- tool registry
- basic Agent set: DiffExplainer, ProjectMapper, RiskAnalyst, StudyCard, Verifier
- durable suspend/resume proof connected to watcher-generated events

Acceptance:

- A diff analysis workflow runs through Mastra.
- Workflow output creates a DecisionCard.
- Medium/high risk work can suspend and resume through a human gate.

## Phase 3: Langfuse Observability Mapping

Goal: keep Langfuse as observability, not product state.

Current:

- `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` emits `cognitive-loop-langfuse-observability-verification-v1`.
- Service and durable Mastra receipts are mapped to local trace, span, generation, and score DTOs.
- DecisionCard, LoopRun, report, risk, HumanGate, privacy, latency, token, and cost metadata are represented without raw prompts or private data.
- The verifier proves `calls_real_langfuse=false`, `imports_langfuse_sdk=false`, and `network_calls=false`.

Deliver next:

- real self-hosted Langfuse sink wiring behind explicit operator configuration
- runtime trace IDs linked back into `LoopRun.trace_refs`
- operator docs for inspecting traces under a local Langfuse project

Acceptance:

- Every repo-local Mastra workflow run has a local Langfuse-style DTO receipt.
- Cost, latency, trace, and eval evidence are available in local metadata.
- Sensitive source text, answers, secrets, storage paths, and private Agent metadata stay out of Langfuse metadata.
- A later hosted or self-hosted Langfuse sink must pass the same redaction verifier before being treated as production-ready.

## Phase 4: Study Anything Adapter

Goal: connect project decisions to human learning and mastery.

Current:

- `python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` proves a metadata-only `ProjectEvent` and `DecisionCard` can create a source-bound `LearningContextPackage`, complete a deterministic Study Anything learning loop, and project the result back into `MasteryRecord` / `LoopRun` evidence.
- `.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html` turns that proof into a platform-Agent-callable CLI Lite. It writes JSON/HTML learning status, StudyCard, understanding gaps, scribe summary, `MasteryRecord`, and `LoopRun` evidence from metadata-only inputs.
- Cognitive Loop evidence stores only public summaries, source references, excerpt hashes, schemas, counts, and mastery metadata. It does not include source bodies, raw diffs, learner answers, grading feedback, Agent endpoints, Agent metadata, or model keys.
- The bridge uses the local `fake-deterministic` Agent for proof; real teaching remains delegated to the user's platform Agent or private HTTP Agent.

Deliver:

- richer mastery sync from full Study Anything sessions into Cognitive Loop MasteryRecord
- scribe log bridge into the future realtime HTML Artifact console
- optional external Agent handoff around the CLI Lite contract

## Phase 5: Watcher Runner Lite

Goal: move from manual watcher ingest to bounded local runner automation without shipping a daemon.

Current:

- `.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter` reads `.cognitive-loop/watchers.yaml`, accepts explicit path/git/test signals, debounces duplicate observations, skips excluded paths, writes metadata-only ProjectEvent artifacts, ingests them into the SQLite Event Store, and can trigger Study Anything adapter CLI for the first high-risk event.
- `.venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check` verifies file-save, git diff summary, test failure summary, exclude rules, raw diff rejection, idempotent Event Store writes, and Study Adapter gate triggering.
- Runner Lite does not start a background watcher, read source bodies, embed raw diffs or test output, store learner answers, expose Agent endpoints, capture Agent metadata, or store model keys.

Deliver:

- richer local signal adapters for CI receipts and platform-Agent tool call metadata
- static Artifact Console Lite promotion into the professional artifact path
- realtime HTML Artifact console fed by Event Store rows as a later layer
- optional Mastra watcher workflow that consumes runner-lite events after the same privacy verifier passes

Acceptance:

- A metadata-only project decision can generate a learning package.
- A high-risk decision can generate understanding questions through Study Anything.
- A completed learning loop updates MasteryRecord and appears in generated Cognitive Loop evidence.
- Future HTML reports can render the same MasteryRecord without adding private source or answer text.

## Phase 5: Realtime Watchers

Goal: turn project activity into normalized events.

Current:

- `.cognitive-loop/watchers.yaml` defines manual ingest watcher rules.
- `python3 scripts/cognitive_loop_watcher_ingest.py ingest --html` creates metadata-only `ProjectEvent` artifacts without a daemon.
- `python3 scripts/verify_cognitive_loop_watcher_ingest.py --check` proves Event Index classification, SQLite Event Store ingestion, excluded-target rejection, malformed-config rejection, and privacy boundaries.

当前：

- `.cognitive-loop/watchers.yaml` 定义手动 ingest watcher 规则。
- `python3 scripts/cognitive_loop_watcher_ingest.py ingest --html` 可以在不启动 daemon 的情况下创建只含 metadata 的 `ProjectEvent` artifact。
- `python3 scripts/verify_cognitive_loop_watcher_ingest.py --check` 证明 Event Index 分类、SQLite Event Store 摄入、排除目标拒绝、错误配置拒绝和隐私边界。

Deliver:

- daemonized file watcher
- daemonized git diff watcher
- daemonized test/CI watcher
- daemonized Agent tool-call watcher
- daemonized runtime log watcher
- debounce, batching, and secret redaction

Acceptance:

- Saving a file creates a ProjectEvent.
- A git diff can create a DecisionCard.
- A test failure creates a diagnostic event and recommended next step.
- A git diff or redacted PR summary can create an advisory `ReviewRun` with up to five high-confidence findings, suggested verification commands, and a non-blocking security gate.
- A user-owned CI/platform Review Agent can use `platform/prompts/cognitive-loop-review-agent.json` for JSON-only line-level diff review with at most eight findings; Study Anything still only stores redacted structured evidence.
- External Review Agent handoff now has `platform/schemas/cognitive-loop-review-agent-report.schema.json`, `fixtures/review-agent`, and `python3 scripts/verify_cognitive_loop_review_agent_report.py --check`.
- git diff 或脱敏 PR 摘要可以生成咨询式 `ReviewRun`，最多五条高置信发现、建议验证命令，以及不阻塞合并的安全门。
- 用户自有 CI/平台 Review Agent 可以使用 `platform/prompts/cognitive-loop-review-agent.json` 做 JSON-only 行级 diff 审查，最多八条发现；Study Anything 仍然只保存脱敏结构化证据。
- 外部 Review Agent 交接已经包含 `platform/schemas/cognitive-loop-review-agent-report.schema.json`、`fixtures/review-agent` 和 `python3 scripts/verify_cognitive_loop_review_agent_report.py --check`。

Current code-review scope:

- `python3 scripts/cognitive_loop_review.py --base main --head HEAD --html`
- `python3 scripts/verify_cognitive_loop_review.py --check`
- `python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check`
- `python3 scripts/verify_cognitive_loop_review_agent_report.py --check`
- v0.1 is advisory only; soft gate and hard gate adoption are later opt-in phases.

当前代码审查范围：

- `python3 scripts/cognitive_loop_review.py --base main --head HEAD --html`
- `python3 scripts/verify_cognitive_loop_review.py --check`
- `python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check`
- `python3 scripts/verify_cognitive_loop_review_agent_report.py --check`
- v0.1 仅做咨询；soft gate 和 hard gate 是后续可选升级阶段。

## Phase 6: Professional HTML Artifact Mode

Goal: make Cognitive Loop usable as a project console without building a heavy SaaS or desktop app.

Current:

- `python3 scripts/cognitive_loop_artifact_console.py build --html --json` generates `.cognitive-loop/artifacts/console/index.html` and a JSON manifest.
- `python3 scripts/verify_cognitive_loop_artifact_console.py --check` verifies empty projects, runner-lite Event Store aggregation, Study Adapter links, missing-artifact degradation, secret rejection, mobile/narrow-screen HTML structure, and privacy flags.
- Console Lite stays static and metadata-only: no daemon, no standalone frontend, no SSE/WebSocket, no raw event bodies, no source text, no diffs, no test output, no learner answers, no Agent endpoints, no Agent metadata, no prompts, and no model keys.

Still planned:

- `cognitive-loop report --html`
- `cognitive-loop watch --html`
- `cognitive-loop explain-diff --html`
- static pages for project map, timeline, decision cards, mastery, audit, and evolution
- local realtime console over SSE or WebSocket
- CI-uploadable HTML artifacts

Acceptance:

- Static HTML reports and Console Lite open offline.
- Console Lite includes provenance and redaction evidence for Event Store, watcher runner, Study Adapter, Human Gate, LoopRun, and artifact-health sections.
- Browser UI can display human gates but does not directly execute high-risk commands.
- Full realtime console updates from local watcher events remain a later acceptance target.

## Phase 7: Personal Plugin Mode

Goal: reduce adoption friction for individual users.

Current:

- `python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json` creates read-only metadata-only Study Cards, quiz items, and Markdown/HTML learning reports for file, README, webpage metadata, and diff-summary targets.
- `python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --check` verifies target coverage, missing-target handling, secret-looking target rejection, raw diff body rejection, no-write behavior, report structure, and privacy flags.
- Personal Plugin Mode Lite does not launch a daemon, start a standalone frontend, call real models, store real model keys, or embed raw source text, raw diff bodies, learner answers, Agent endpoints, Agent metadata, or prompts.

Still planned:

- VS Code/Cursor plugin
- browser extension
- Obsidian plugin
- richer Kimi/Codex/WorkBuddy platform shortcuts on top of the CLI

Acceptance:

- A personal user can explain a file, README, webpage, or diff.
- The plugin can generate study cards, quizzes, and Markdown/HTML learning reports.
- Personal mode defaults to read-only and explain-only.

## Phase 8: Evolution MVP

Goal: let the system improve prompts, policies, tasks, docs, evals, and learning paths under governance.

Current:

- `python3 scripts/cognitive_loop_evolution.py build --html --json` creates read-only Evolution Report Lite artifacts from metadata-only evidence and bounded failure summaries.
- `python3 scripts/verify_cognitive_loop_evolution_report.py --check` verifies failure clustering, root-cause hypotheses, proposed improvements, regression plan, high-risk Human Mastery Gate requirements, empty/missing evidence degradation, secret/diff-body rejection, policy-weakening rejection, and privacy flags.
- Evolution Report Lite is proposal-only: no automatic source changes, no model calls, no daemon, no stored real model keys, and no weakening of risk, audit, rollback, tests, production policy, privacy policy, or permissions.
- `python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json` creates Governed Apply Plan Lite artifacts for low-risk generated-artifact receipts.
- `python3 scripts/verify_cognitive_loop_apply_plan.py --check` verifies dry-run behavior, explicit generated-artifact receipt apply, required allow flag, idempotent receipt, high-risk/gated/forbidden-path rejection, secret/diff-body/policy-weakening rejection, and privacy flags.
- Apply Plan Lite is not source-changing auto-apply: it writes only `.cognitive-loop/artifacts/applied/` receipt markers when explicitly allowed.
- `python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json` creates read-only Measured Improvement Comparator Lite artifacts across metadata-only loop evidence.
- `python3 scripts/verify_cognitive_loop_improvement_comparator.py --check` verifies improved, regressed, unchanged, insufficient, and ambiguous outcomes; privacy regression detection; malformed/invalid/secret/diff-body/policy-weakening rejection; JSON/HTML artifact structure; and read-only guardrails.
- `python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json` creates read-only Patch Proposal Lite artifacts across prompt, policy, eval, task, doc, and retrieval categories.
- `python3 scripts/verify_cognitive_loop_patch_proposal.py --check` verifies low-risk proposal generation, mixed manual-only handling, high-risk/gated/forbidden-path degradation, insufficient comparison degradation, secret/raw-diff/policy-weakening/invalid-schema rejection, JSON/HTML artifact structure, and privacy flags.
- Patch Proposal Lite is not source-changing auto-apply: it produces bounded patch specifications and never generates raw unified diffs, calls models, executes apply, or modifies source files.
- `python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json` creates read-only Mastra Evolution Receipt Link Lite artifacts from metadata-only Evolution Report, Apply Plan, Improvement Comparison, and Patch Proposal evidence.
- `python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check` verifies complete four-artifact linkage, missing-evidence degradation, insufficient comparison degradation, high-risk ungated blocking, manual-only Patch Proposal blocking, unsupported-schema/secret/raw-diff/policy-weakening rejection, JSON/HTML artifact structure, and privacy flags.
- Mastra Evolution Receipt Link Lite is not production Mastra execution: it produces metadata-only `EvolutionReceiptLink` JSON/HTML receipt DTOs and never starts Mastra, calls models, executes apply, or modifies source files.

Still planned:

- low-risk source-changing auto-apply path with explicit policy guardrails
- source-changing patch application from accepted Patch Proposal Lite specifications
- realtime Artifact Console integration
- production Mastra workflow execution from accepted EvolutionReceiptLink artifacts

Acceptance:

- The next loop shows measurable improvement in task success, explanation quality, test coverage, or approval efficiency.
- The system never automatically weakens risk thresholds, audit, rollback, tests, production policy, privacy policy, or permissions.

## Commercial Direction

The core remains Apache-2.0 and local-first. Commercialization should follow trust-preserving convenience:

- hosted encrypted sync
- team workspaces
- publish/share workflows
- trusted plugin distribution
- managed infrastructure
- professional support

商业化方向保持本地优先和信任优先：核心能力开源，未来付费服务销售托管、同步、团队协作、可信生态分发、专业支持和可靠基础设施，而不是锁住核心学习/认知闭环。
