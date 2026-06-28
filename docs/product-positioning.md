# Product Positioning / 产品定位

## One-Line Positioning

**Cognitive Loop System is a local-first cognitive control layer for AI-assisted projects: learn, reverse, operate, verify, audit, and evolve any repo with human-understanding gates.**

**Cognitive Loop System 是一个本地优先的 AI 项目认知控制层：让任何仓库都能被学习、逆向、运行、验证、审计，并在人类理解确认下持续进化。**

## Product Shift

Study Anything started as a learning system. The new positioning keeps that strength but moves the product up one level:

- Study Anything becomes the learning adapter.
- Cognitive Loop Core becomes the project-level control layer.
- Mastra becomes the planned Agent/workflow runtime.
- Langfuse becomes the observability and eval layer.
- HTML Artifact becomes the professional product surface.
- Plugins become the personal adoption surface.

Study Anything 最初是学习系统。新定位保留这个优势，但把产品上移一层：

- Study Anything 成为学习适配层。
- Cognitive Loop Core 成为项目级控制层。
- Mastra 成为计划中的 Agent/workflow 运行时。
- Langfuse 成为观测和 eval 层。
- HTML Artifact 成为专业用户的产品表面。
- 插件成为个人用户的低摩擦入口。

## Feasibility

Feasibility is high if this is treated as a public positioning and architecture reset before a runtime rewrite.

Already reusable:

- local-first learning loop
- platform-Agent packs for Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, Hermes Agent Skill, and generic OpenAPI hosts
- Bring Your Own Agent boundary
- redacted Agent audit/eval evidence
- Obsidian export and NotebookLM-style handoff
- Learning Enrichment packages
- Docker and Skill Mode self-host paths

Still missing:

- Mastra runtime adapter
- project watchers
- DecisionCard, RiskEngine, HumanMasteryGate, and LoopRun core
- generic HTML Artifact renderer and realtime console
- personal plugins

如果把这次改造先当作公开定位和架构重置，而不是直接重写 runtime，可行性很高。

已经可复用：

- 本地优先学习闭环
- 面向 Kimi-compatible、Codex Skill、WorkBuddy-style HTTP、Hermes Agent Skill 和通用 OpenAPI host 的平台 Agent 包
- Bring Your Own Agent 边界
- 脱敏 Agent audit/eval 证据
- Obsidian 导出和 NotebookLM 式交接
- Learning Enrichment package
- Docker 和 Skill Mode 自托管路径

仍然缺失：

- Mastra runtime adapter
- 项目 watcher
- DecisionCard、RiskEngine、HumanMasteryGate、LoopRun core
- 通用 HTML Artifact renderer 和实时 console
- 个人插件

## Target Users

Primary users:

- builders using AI Agents to work inside real repos
- maintainers who need audit, verification, and rollback evidence
- learners reverse-engineering open-source or legacy projects
- platform-Agent users in Kimi, Codex, Hermes Agent, WorkBuddy-style workspaces, and private tool hosts
- teams that want local-first AI operation before hosted collaboration

主要用户：

- 用 AI Agent 在真实仓库里工作的开发者
- 需要审计、验证和回滚证据的维护者
- 逆向学习开源项目或遗留系统的学习者
- Kimi、Codex、Hermes Agent、WorkBuddy-style workspace 和私有工具平台里的平台 Agent 用户
- 在引入托管协作前，希望先本地优先运行 AI 工作流的团队

## Product Promise

The system does not try to beat future foundation models at reasoning. It becomes the external control layer those models need when they enter real projects:

- state externalization
- evidence-first explanations
- deterministic verification
- risk gates
- rollback planning
- human mastery checks
- redacted audit
- cross-model continuity

系统不试图在“智能本身”上和未来大模型竞争。它成为大模型进入真实项目时需要的外部控制层：

- 状态外化
- 证据优先解释
- 确定性验证
- 风险门禁
- 回滚计划
- 人类掌握度检查
- 脱敏审计
- 跨模型连续性

## Use Modes

### Personal Plugin Mode

For individual learning and lightweight project understanding:

- explain current page, README, file, or diff
- generate study cards and quizzes
- record local mastery
- export Markdown or HTML
- stay read-only by default

个人插件模式用于个人学习和轻量项目理解：

- 解释当前网页、README、文件或 diff
- 生成学习卡和测验
- 本地记录掌握度
- 导出 Markdown 或 HTML
- 默认只读

### Professional HTML Artifact Mode

For project operators and teams:

- import a repo
- map modules and feature paths
- watch diffs, tests, CI, runtime logs, and Agent tool calls
- generate DecisionCards and risk scores
- run Human Mastery Gates
- produce static or realtime HTML reports
- preserve audit and rollback evidence

专业 HTML Artifact 模式用于项目操作者和团队：

- 导入仓库
- 映射模块和功能链路
- 监听 diff、测试、CI、运行日志和 Agent 工具调用
- 生成 DecisionCard 和风险评分
- 运行 Human Mastery Gate
- 生成静态或实时 HTML 报告
- 保留审计和回滚证据

## Why No Standalone App First

The current product does not need to win by forcing users into a new frontend. The lowest-friction path is to meet users inside the AI workspaces they already use:

- Kimi Work or Kimi-compatible tool hosts
- Codex Skill workflows
- WorkBuddy-style HTTP tool environments
- Hermes Agent Skill environments
- local Agent gateways owned by the user
- future browser, editor, and Obsidian plugins

The professional product surface should become HTML artifacts because they are easy to archive, inspect, attach to PRs, share with teams, and open locally without accounts.

当前产品不需要靠强迫用户进入一个新前端来获胜。最低认知负担的路径，是进入用户已经在使用的 AI 工作空间：

- Kimi Work 或 Kimi-compatible tool host
- Codex Skill workflow
- WorkBuddy-style HTTP tool environment
- Hermes Agent Skill environment
- 用户自己控制的本地 Agent gateway
- 未来的浏览器、编辑器和 Obsidian 插件

专业产品表面应优先成为 HTML artifact，因为它们容易归档、检查、附到 PR、分享给团队，并且可以本地打开，不需要账号。

## What Is In Scope Now

Current shipped foundation:

- Study Anything learning loop
- API/Skill/platform-Agent usage
- Bring Your Own Agent
- redacted audit/eval evidence
- Learning Enrichment
- Obsidian and NotebookLM-style handoff
- local-first self-hosting and adoption packs

当前已经交付的基础：

- Study Anything 学习闭环
- API/Skill/平台 Agent 使用方式
- Bring Your Own Agent
- 脱敏 audit/eval 证据
- Learning Enrichment
- Obsidian 和 NotebookLM 式交接
- 本地优先自托管和 adoption pack

## What Is Planned

Planned Cognitive Loop layers:

- framework-independent Core
- Mastra runtime adapter
- project watchers
- risk and permission engine
- DecisionCard and Human Mastery Gate
- static and realtime HTML Artifact
- personal plugins
- governed self-evolution

计划中的 Cognitive Loop 层：

- 框架无关 Core
- Mastra runtime adapter
- 项目 watcher
- 风险和权限引擎
- DecisionCard 和 Human Mastery Gate
- 静态与实时 HTML Artifact
- 个人插件
- 受治理的自进化

## What Is Out Of Scope For The Pivot PR

- no API changes
- no Mastra integration
- no new watcher daemon
- no full HTML console
- no repo rename
- no paid hosted app claim
- no standalone frontend relaunch

本次定位 PR 不做：

- 不改 API
- 不接 Mastra
- 不新增 watcher daemon
- 不交付完整 HTML console
- 不重命名仓库
- 不宣称付费托管 App 已上线
- 不重新启动独立前端路线
- 不重命名 GitHub 仓库；`study-anything` 暂时保留为仓库名和当前 learning-adapter 发布线

## Commercial Model

The core should stay Apache-2.0 and local-first. Paid services should sell convenience and trust infrastructure, not access to the core loop:

- hosted encrypted sync
- team workspaces
- publishing and sharing reports
- trusted plugin distribution
- managed runtime and support

核心保持 Apache-2.0 和本地优先。付费服务应该销售便利性和可信基础设施，而不是锁住核心认知闭环：

- 托管加密同步
- 团队工作区
- 报告发布和分享
- 可信插件分发
- 托管运行环境和专业支持

Commercialization should not start as a paid standalone app. It should start as trust-preserving services around the open core:

- hosted encrypted sync for loop state, mastery, reports, and settings
- team workspaces for shared decision cards, project maps, and learning gates
- publish/share workflows for selected HTML reports and learning trails
- trusted plugin distribution and verification badges
- professional setup, support, and managed infrastructure

商业化暂时不应从“付费独立 App”开始，而应该围绕开源核心销售可信便利服务：

- 托管加密同步：同步 loop state、mastery、report、settings
- 团队工作区：共享 DecisionCard、项目地图和学习门禁
- 发布/分享工作流：发布选定 HTML report 和 learning trail
- 可信插件分发和验证标识
- 专业部署、支持和托管基础设施
