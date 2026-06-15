# Architecture / 架构

Cognitive Loop System is a local-first control layer for AI-assisted projects. It keeps project state, evidence, risk, verification, learning, and audit outside the long context of any single Agent conversation.

Cognitive Loop System 是一个本地优先的 AI 项目控制层。它把项目状态、证据、风险、验证、学习和审计外化到文件、数据库、报告和事件账本中，而不是只存在某一次 Agent 长对话里。

## Layered Architecture

```text
Product Entries
  Personal Plugin Mode
  Professional HTML Artifact Mode

Cognitive Loop Core
  ProjectEvent
  DecisionCard
  RiskEngine
  HumanMasteryGate
  EventStore
  EvolutionReport

Runtime Layer
  Mastra agents
  Mastra workflows
  Tools
  Memory
  HITL suspend/resume

Project Runtime Layer
  File watcher
  Git watcher
  CI/test watcher
  Agent tool watcher
  Verifier
  Rollback

Learning Layer
  Study Anything Adapter
  LearningContextPackage
  StudyCard
  MasteryRecord
  ScribeLog

Observability Layer
  Langfuse traces
  Prompt versions
  Eval scores
  Cost/latency metadata

Artifact Layer
  Static HTML reports
  Realtime local HTML console
  Markdown/Obsidian/NotebookLM-style exports
```

## Current Implementation

The current repository already implements the Study Anything foundation:

- FastAPI API layer for local learning workflows.
- LangGraph-backed and deterministic workflow execution for the Study Anything learning loop.
- User-owned Agent registry and router; real model credentials stay outside Study Anything.
- Redacted Agent audit/eval artifacts and platform-Agent tool surfaces.
- Learning Enrichment packages for web, document, app, video-slice, Markdown, and Obsidian excerpts.
- Obsidian export, second-brain handoff, and NotebookLM-style manual bridge artifacts.
- Docker self-host path with Postgres, optional Langfuse, optional FalkorDB topology projection, and release evidence.

当前仓库已经实现的是 Study Anything 基础层：

- 面向本地学习工作流的 FastAPI API。
- 用于学习闭环的 LangGraph 和确定性 workflow 执行。
- 用户自有 Agent registry/router；真实模型密钥留在 Study Anything 外部。
- 脱敏 Agent audit/eval 证据和平台 Agent 工具面。
- 面向网页、文档、应用上下文、视频切片、Markdown、Obsidian 片段的 Learning Enrichment package。
- Obsidian 导出、second-brain handoff 和 NotebookLM 式手动桥接材料。
- Docker 自托管路径：Postgres、可选 Langfuse、可选 FalkorDB 拓扑投影和 release 证据。

## Planned Cognitive Loop Core

The Cognitive Loop Core is the product moat. It should be framework-independent and should not depend on Mastra or Langfuse as the source of truth.

Cognitive Loop Core 是产品护城河。它应该保持框架无关，不能把 Mastra 或 Langfuse 当作唯一事实源。

Conceptual objects:

- `ProjectEvent`: a normalized event from file changes, git diffs, CI, runtime logs, human actions, or Agent tool calls.
- `DecisionCard`: an evidence-bound explanation of a proposed or completed change, including impact, risk, verification, human gate, and rollback plan.
- `LoopRun`: one bounded execution cycle with status, iteration count, verification results, trace refs, and artifacts.
- `MasteryRecord`: the user's understanding level for a topic, file, subsystem, or risky change.
- `EvolutionReport`: a governed improvement proposal for prompts, policies, evals, docs, tasks, retrieval rules, or learning paths.

## Runtime Strategy

Mastra is the planned runtime layer for Agent/workflow/tool/HITL orchestration. It should sit below Cognitive Loop Core:

- Mastra executes workflows.
- Cognitive Loop Core owns event schemas, decision records, risk policy, approval status, and rollback evidence.
- Langfuse observes traces, prompts, costs, latency, and eval scores.
- Study Anything turns events and decision cards into learning packages, quizzes, mastery updates, and scribe logs.

Mastra 是计划中的运行时编排层，而不是产品事实源：

- Mastra 负责执行 workflow。
- Cognitive Loop Core 负责事件结构、决策记录、风险策略、审批状态和回滚证据。
- Langfuse 负责 trace、prompt、成本、延迟和 eval score。
- Study Anything 负责把事件和决策卡转成学习包、测验、掌握度和 scribe log。

## Product Entry Modes

### Personal Plugin Mode

Personal mode should stay lightweight:

- explain a page, README, source file, or git diff
- generate study cards and quizzes
- record mastery locally
- export Markdown or HTML reports
- avoid automatic code changes, deployment, and production operations by default

个人插件模式保持轻量：

- 解释网页、README、源码文件或 git diff
- 生成学习卡和测验
- 本地记录掌握度
- 导出 Markdown 或 HTML 报告
- 默认不自动改代码、不部署、不操作生产环境

### Professional HTML Artifact Mode

Professional mode should produce browser-readable artifacts:

- static HTML reports for project maps, timelines, decision cards, mastery, audit, and evolution
- realtime local HTML console for watcher events, human gates, Agent audit, and verification status
- CI-uploadable reports for PR review and team handoff

专业 HTML Artifact 模式输出可在浏览器打开和归档的材料：

- 项目地图、时间线、决策卡、掌握度、审计和进化报告的静态 HTML
- 面向 watcher event、human gate、Agent audit、验证状态的本地实时 HTML console
- 可上传到 CI 的 PR review 和团队交接报告

## Privacy And Safety Boundaries

- Study Anything does not store real model API keys.
- User-owned Agents keep model choice, credentials, tools, browsing, and external data access.
- Langfuse metadata must stay allowlisted and redacted.
- Event Store is the canonical audit ledger for Cognitive Loop state.
- `.env`, credentials, private keys, signed URLs, raw secrets, and sensitive local paths must not enter HTML reports, traces, learning packages, or public support bundles.
- Risk policy, audit, rollback, and human gate rules must not be weakened by automatic self-evolution.

## Near-Term Non-Goals

- Mastra runtime is not yet integrated in this positioning PR.
- Full project watchers are not yet shipped.
- HTML Artifact console is not yet a complete product UI.
- Hosted Sync, Teams, billing, SSO, and managed cloud are future services, not alpha requirements.
- The current launch path remains API/Skill/platform-Agent first, not a standalone frontend.
