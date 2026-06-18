# Cognitive Loop System

**Cognitive Loop System** is a local-first cognitive control layer for AI-assisted projects. It helps people and platform Agents learn a project, reverse-engineer how it works, watch important changes, verify actions, preserve audit evidence, and evolve the project under human-understanding gates.

**认知自循环系统** 是一个本地优先的 AI 项目认知控制层。它帮助人类和平台 Agent 学习项目、逆向理解项目、监听关键变化、验证行动、保留审计证据，并在人类理解确认的约束下推动项目持续进化。

Study Anything is now positioned as the **Learning Adapter** inside Cognitive Loop System. It remains responsible for source-bound learning sessions, layered teaching, quizzes, mastery state, scribe logs, Agent audit/eval evidence, Obsidian exports, NotebookLM-style handoff packages, and platform-Agent adoption assets.

Study Anything 现在定位为 Cognitive Loop System 里的 **学习适配层**：负责基于来源的学习会话、分层教学、测验、掌握度、scribe log、Agent 审计/eval 证据、Obsidian 导出、NotebookLM 式交接包，以及平台 Agent 接入资产。

## What It Is

- **Study Anything**: learn knowledge, docs, code, papers, and project material.
- **Reverse Anything**: turn existing repos and legacy systems into maps, traces, and learning paths.
- **Operate Anything**: watch project diffs, tests, runtime signals, and Agent tool calls as evidence.
- **Evolve Anything**: let AI suggest and execute bounded improvements with verification, rollback, audit, and human mastery gates.

## 它解决什么

- **学习任何材料**：文档、代码、论文、资料、项目上下文。
- **逆向任何项目**：把开源项目、遗留系统和当前仓库变成项目地图、功能链路和学习路径。
- **监听任何变化**：把 diff、测试、CI、运行日志和 Agent 工具调用变成可审计事件。
- **进化任何项目**：让 AI 在验证、回滚、权限和人类理解确认下持续改进项目。

## Current Foundation

The current alpha already ships a local-first Study Anything foundation:

- FastAPI learning API and repo-local Skill Mode.
- Deterministic fake Agent for tests and demos.
- Bring Your Own Agent via user-owned HTTP gateway; Study Anything does not store real model keys.
- Source-bound learning loop: reading, teaching layers, quiz, grading, mastery, synthesis, scribe log, and discard/keep.
- Platform-Agent packs for Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, and generic OpenAPI hosts.
- Redacted Agent audit/eval artifacts, multi-teacher attribution gates, and optional mature eval adapters.
- Learning Enrichment bridge for web, document, app, video-slice, Markdown, and Obsidian context.
- Obsidian export, NotebookLM-style manual bridge, second-brain handoff, and local archive evidence.
- Docker self-host path with Postgres, optional Langfuse, optional FalkorDB topology projection, and GHCR image evidence.
- Cognitive Loop contract bootstrap with `.cognitive-loop/config.yaml`, `permissions.yaml`, `evals.yaml`, `risk.yaml`, and `cognitive-loop-contract-bootstrap-v1` verification.

当前 alpha 已经具备本地优先的 Study Anything 基础：

- FastAPI 学习 API 和仓库内 Skill Mode。
- 用于测试和 demo 的确定性 fake Agent。
- Bring Your Own Agent：真实推理由用户自己的 HTTP Agent Gateway 执行，Study Anything 不保存真实模型密钥。
- 基于来源的学习闭环：阅读、分层教学、测验、评分、掌握度、综合洞察、scribe log、保留或丢弃。
- 面向 Kimi-compatible、Codex Skill、WorkBuddy-style HTTP 和通用 OpenAPI 平台的 Agent 接入包。
- 脱敏 Agent audit/eval 证据、多层教学归因验收，以及可选成熟 eval 适配。
- Learning Enrichment bridge：接收网页、文档、应用上下文、视频切片、Markdown、Obsidian 片段。
- Obsidian 导出、NotebookLM 式手动桥接、second-brain handoff、本地归档证据。
- Docker 自托管路径：Postgres、可选 Langfuse、可选 FalkorDB 拓扑投影、GHCR 镜像证据。
- Cognitive Loop contract bootstrap：`.cognitive-loop/config.yaml`、`permissions.yaml`、`evals.yaml`、`risk.yaml` 和 `cognitive-loop-contract-bootstrap-v1` 验证。

## Feasibility And Boundary

This pivot is feasible as a public positioning and architecture reset because the repo already contains a working local learning adapter, platform-Agent adoption assets, eval/audit evidence, privacy boundaries, and self-host paths. It is **not** a claim that the full Cognitive Loop runtime has shipped.

这次 pivot 适合作为公开定位和架构重置，因为仓库已经有可运行的本地学习适配层、平台 Agent 接入资产、eval/audit 证据、隐私边界和自托管路径。它 **不表示** 完整 Cognitive Loop runtime 已经交付。

Current shipped surface: Study Anything API, Skill Mode, platform-Agent packs, Docker self-host, learning/eval/export flows.

Planned surface: Mastra runtime, project watchers, DecisionCard/Risk/Human Mastery Gate core, generic HTML Artifact console, personal plugins.

当前已交付表面：Study Anything API、Skill Mode、平台 Agent 包、Docker 自托管、学习/eval/导出闭环。

计划中表面：Mastra runtime、项目 watcher、DecisionCard/Risk/Human Mastery Gate core、通用 HTML Artifact console、个人插件。

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
  │   └── EvolutionReport
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

Mastra, project watchers, automated runtime gates, and the full HTML Artifact console are **planned Cognitive Loop layers**, not shipped runtime claims in this pivot PR. The current implementation includes public DecisionCard/Risk/Human Mastery Gate contracts plus local static evidence artifacts. The launch path remains API/Skill/platform-Agent first, without a standalone frontend requirement.

Mastra、项目监听器、自动化 runtime gate 和完整 HTML Artifact Console 是 **下一阶段 Cognitive Loop 层**，不是这次定位 PR 已经交付的运行时能力。当前实现已经包含公开的 DecisionCard/Risk/Human Mastery Gate 契约和本地静态 evidence artifact；上线路径仍然是 API/Skill/平台 Agent 优先，不要求独立前端。

## Public Conceptual Contracts

These names are documented now so future implementation work has a stable public vocabulary. They are conceptual contracts, not current HTTP endpoints:
The first local validator for these contracts is now available in `scripts/verify_cognitive_loop_contracts.py`. A companion local CLI can initialize the contracts, render a static HTML DecisionCard artifact with `python3 scripts/cognitive_loop_cli.py report --html`, produce one bounded local `LoopRun` / `DecisionCard` evidence cycle with `python3 scripts/cognitive_loop_cli.py run-once --html`, capture a redacted path-level project snapshot with `python3 scripts/cognitive_loop_cli.py snapshot --html`, record a local Human Mastery Gate approval or rejection with `python3 scripts/cognitive_loop_cli.py gate --approve --html`, create a metadata-only evidence bundle with `python3 scripts/cognitive_loop_cli.py bundle --html`, build a metadata-only local event timeline with `python3 scripts/cognitive_loop_cli.py index --html`, check local artifact consistency with `python3 scripts/cognitive_loop_cli.py doctor --html`, create a manual-only repair plan with `python3 scripts/cognitive_loop_cli.py repair-plan --html`, open a static local artifact index with `python3 scripts/cognitive_loop_cli.py artifact-index --html`, and generate advisory code-review evidence with `python3 scripts/cognitive_loop_review.py --base main --head HEAD --html`. Mastra, watchers, and the full realtime HTML console are still planned layers.

- `ProjectEvent`: normalized file, git, CI, runtime, human, or Agent event.
- `DecisionCard`: evidence-bound decision record with impact, risk, verification, human gate, and rollback plan.
- `LoopRun`: one bounded workflow execution cycle with status, trace refs, verification results, and artifacts.
- `MasteryRecord`: human understanding state for a topic, file, subsystem, or risky change.
- `EvolutionReport`: governed proposal for improving prompts, policies, evals, docs, tasks, retrieval, or learning paths.
- `ReviewRun` / `ReviewFinding` / `ReviewDecision` / `ReviewMetrics`: advisory code-review evidence from path-level git or PR summary metadata, documented in `docs/cognitive-loop-code-review.md`.

这些名称先作为公开概念契约，方便后续实现保持稳定词汇。它们现在不是 HTTP endpoint：
第一版本地 validator 已经在 `scripts/verify_cognitive_loop_contracts.py` 中可用。配套本地 CLI 可以初始化契约，通过 `python3 scripts/cognitive_loop_cli.py report --html` 渲染静态 HTML DecisionCard artifact，通过 `python3 scripts/cognitive_loop_cli.py run-once --html` 生成一次有边界的本地 `LoopRun` / `DecisionCard` evidence cycle，通过 `python3 scripts/cognitive_loop_cli.py snapshot --html` 捕获脱敏的路径级项目 snapshot，通过 `python3 scripts/cognitive_loop_cli.py gate --approve --html` 记录本地 Human Mastery Gate 的批准或拒绝，通过 `python3 scripts/cognitive_loop_cli.py bundle --html` 创建只含 metadata 的 evidence bundle，通过 `python3 scripts/cognitive_loop_cli.py index --html` 构建只含 metadata 的本地事件 timeline，通过 `python3 scripts/cognitive_loop_cli.py doctor --html` 检查本地 artifact consistency，通过 `python3 scripts/cognitive_loop_cli.py repair-plan --html` 创建仅手动执行的 repair plan，通过 `python3 scripts/cognitive_loop_cli.py artifact-index --html` 打开一个静态本地 artifact 入口页，并通过 `python3 scripts/cognitive_loop_review.py --base main --head HEAD --html` 生成咨询式代码审查证据；Mastra、watcher 和完整实时 HTML console 仍然是计划中的层。

- `ProjectEvent`：标准化的文件、Git、CI、运行时、人类或 Agent 事件。
- `DecisionCard`：绑定证据的决策记录，包含影响、风险、验证、人类门禁和回滚计划。
- `LoopRun`：一次有边界的 workflow 执行循环，包含状态、trace 引用、验证结果和产物。
- `MasteryRecord`：人类对 topic、文件、子系统或高风险变更的理解状态。
- `EvolutionReport`：对 prompt、policy、eval、文档、任务、检索或学习路径的受治理改进提案。
- `ReviewRun` / `ReviewFinding` / `ReviewDecision` / `ReviewMetrics`：来自路径级 git 或 PR 摘要元数据的咨询式代码审查证据，详见 `docs/cognitive-loop-code-review.md`。

Future project contract files:

```text
.cognitive-loop/config.yaml
.cognitive-loop/permissions.yaml
.cognitive-loop/evals.yaml
.cognitive-loop/risk.yaml
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

For Kimi Work, Codex, WorkBuddy-style HTTP workspaces, or another platform Agent, verify the copy-ready adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The platform packs prove that an external Agent can import the tool surface, run one source-bound learning loop, return audit/eval evidence, and export Obsidian or NotebookLM-style handoff artifacts without requiring a standalone frontend or storing real model keys in Study Anything.
For scenario-based operation, use `docs/cognitive-loop-adoption-cookbook.md` to map Kimi, Codex, WorkBuddy, or a private platform Agent to first adoption, daily project review, risk decisions, and learning handoff.

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

- Build Cognitive Loop Core with SQLite Event Store and static HTML reports.
- Add Mastra runtime as the workflow/Agent/HITL adapter.
- Map LoopRun, DecisionCard, RiskScore, and EvalResult into Langfuse traces and scores.
- Convert project diffs and events into Study Anything learning sessions.
- Add file/Git/test/Agent watchers and a realtime local HTML console.

短期目标：

- 保持 Study Anything 作为学习适配层和平台 Agent 工具面的稳定性。
- 发布 Cognitive Loop 的新定位和架构说明。
- 明确 `ProjectEvent`、`DecisionCard`、`LoopRun`、`MasteryRecord`、`EvolutionReport` 等概念契约。

下一阶段：

- 建立 Cognitive Loop Core、SQLite Event Store 和静态 HTML 报告。
- 用 Mastra 作为 workflow、Agent、HITL 的运行时适配层。
- 将 LoopRun、DecisionCard、RiskScore、EvalResult 映射到 Langfuse trace 和 score。
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
