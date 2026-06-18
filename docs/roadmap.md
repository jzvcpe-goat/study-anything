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
- Docs state that Mastra, watchers, and full HTML Artifact console are planned layers.
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

Deliver:

- Mastra workflow adapter
- tool registry
- basic Agent set: DiffExplainer, ProjectMapper, RiskAnalyst, StudyCard, Verifier
- suspend/resume proof for human gates

Acceptance:

- A diff analysis workflow runs through Mastra.
- Workflow output creates a DecisionCard.
- Medium/high risk work can suspend and resume through a human gate.

## Phase 3: Langfuse Observability Mapping

Goal: keep Langfuse as observability, not product state.

Deliver:

- LoopRun to Langfuse trace mapping
- workflow step to span mapping
- Agent call to generation mapping
- RiskScore, HumanGateResult, and EvalResult to score mapping
- DecisionCard and report IDs in trace metadata

Acceptance:

- Every Mastra workflow run is visible in Langfuse.
- Cost, latency, trace, and eval evidence are available.
- Sensitive source text, answers, secrets, and private Agent metadata stay out of Langfuse metadata.

## Phase 4: Study Anything Adapter

Goal: connect project decisions to human learning and mastery.

Deliver:

- LearningContextPackage from ProjectEvent and DecisionCard
- StudyCard generation
- mastery sync from Study Anything sessions into Cognitive Loop MasteryRecord
- scribe log bridge
- report sections for learning status and understanding gaps

Acceptance:

- A project diff can generate a learning package.
- A high-risk decision can generate understanding questions.
- A completed learning loop updates MasteryRecord and appears in the HTML report.

## Phase 5: Realtime Watchers

Goal: turn project activity into normalized events.

Deliver:

- file watcher
- git diff watcher
- test/CI watcher
- Agent tool-call watcher
- runtime log watcher
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

Deliver:

- `cognitive-loop report --html`
- `cognitive-loop watch --html`
- `cognitive-loop explain-diff --html`
- static pages for project map, timeline, decision cards, mastery, audit, and evolution
- local realtime console over SSE or WebSocket
- CI-uploadable HTML artifacts

Acceptance:

- Static HTML reports open offline.
- Realtime console updates from local watcher events.
- Browser UI can display human gates but does not directly execute high-risk commands.
- HTML reports include provenance and redaction evidence for every rendered event, decision card, and mastery section.

## Phase 7: Personal Plugin Mode

Goal: reduce adoption friction for individual users.

Deliver in priority order:

- VS Code/Cursor plugin
- browser extension
- Obsidian plugin
- CLI Lite

Acceptance:

- A personal user can explain a file, README, webpage, or diff.
- The plugin can generate study cards, quizzes, and Markdown/HTML learning reports.
- Personal mode defaults to read-only and explain-only.

## Phase 8: Evolution MVP

Goal: let the system improve prompts, policies, tasks, docs, evals, and learning paths under governance.

Deliver:

- failure clustering
- root-cause analysis
- prompt/policy/eval/task/doc/retrieval improvement suggestions
- low-risk auto-apply path
- high-risk Human Mastery Gate
- regression verification
- EvolutionReport

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
