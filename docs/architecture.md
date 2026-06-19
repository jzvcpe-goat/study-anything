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
- Cognitive Loop contract files, optional manual watcher ingest config, static evidence artifacts, local event index, SQLite Event Store MVP, and a copy-ready Mastra adapter contract pack for metadata-only project evidence.
- Docker self-host path with Postgres, optional Langfuse, optional FalkorDB topology projection, and release evidence.

当前仓库已经实现的是 Study Anything 基础层：

- 面向本地学习工作流的 FastAPI API。
- 用于学习闭环的 LangGraph 和确定性 workflow 执行。
- 用户自有 Agent registry/router；真实模型密钥留在 Study Anything 外部。
- 脱敏 Agent audit/eval 证据和平台 Agent 工具面。
- 面向网页、文档、应用上下文、视频切片、Markdown、Obsidian 片段的 Learning Enrichment package。
- Obsidian 导出、second-brain handoff 和 NotebookLM 式手动桥接材料。
- Cognitive Loop 契约文件、可选手动 watcher ingest 配置、静态 evidence artifacts、本地 event index、只存 metadata 的 SQLite Event Store MVP，以及可复制到外部 Mastra 项目的 Mastra adapter contract pack。
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

The first local contract validator is now implemented before runtime migration so docs, platform packs, and future code use the same vocabulary. The contracts are validated by `scripts/verify_cognitive_loop_contracts.py`, which emits `cognitive-loop-contract-bootstrap-v1`.

第一版本地 contract validator 已在 runtime 迁移前实现，确保文档、平台包和未来代码使用同一套词汇。契约由 `scripts/verify_cognitive_loop_contracts.py` 校验，并输出 `cognitive-loop-contract-bootstrap-v1`。

## Conceptual Contract Sketches

The following shapes are intentionally compact. They define the public mental model, not the final persistence schema or HTTP API.

以下结构故意保持紧凑。它们定义公开心智模型，不是最终数据库结构或 HTTP API。

```ts
export type ProjectEvent = {
  event_id: string;
  project_id: string;
  actor: "human" | "ai" | "ci" | "github" | "runtime";
  event_type:
    | "file_changed"
    | "git_diff_changed"
    | "pre_commit"
    | "post_commit"
    | "pull_request_opened"
    | "ci_failed"
    | "test_failed"
    | "agent_tool_called"
    | "runtime_error"
    | "dependency_changed"
    | "config_changed"
    | "schema_changed";
  target?: string;
  summary: string;
  timestamp: string;
  raw_ref?: {
    git_sha?: string;
    diff_id?: string;
    trace_id?: string;
    langfuse_trace_id?: string;
  };
  sensitivity?: "public" | "internal" | "secret_like";
};
```

```ts
export type DecisionCard = {
  decision_id: string;
  event_id: string;
  project_id: string;
  goal: string;
  actor: "human" | "ai" | "workflow";
  evidence: Array<{
    type: "prd" | "test" | "diff" | "log" | "trace" | "doc";
    ref: string;
    excerpt?: string;
  }>;
  changed_files: string[];
  impact: Array<{ area: string; description: string; confidence: number }>;
  risk: {
    score: number;
    level: "low" | "medium" | "high" | "blocked";
    reasons: string[];
  };
  verification: {
    commands: string[];
    status: "not_run" | "passed" | "failed";
    output_ref?: string;
  };
  human_gate: {
    required: boolean;
    questions: string[];
    approval_status: "not_required" | "pending" | "approved" | "rejected";
  };
  rollback: {
    strategy: "git_checkout" | "git_reset" | "patch_reverse" | "manual";
    command?: string;
    checkpoint_ref?: string;
  };
};
```

```ts
export type LoopRun = {
  run_id: string;
  project_id: string;
  task_id: string;
  status:
    | "created"
    | "running"
    | "suspended"
    | "verifying"
    | "succeeded"
    | "failed"
    | "rolled_back"
    | "rejected";
  mastra_workflow_run_id?: string;
  langfuse_trace_id?: string;
  started_at: string;
  finished_at?: string;
  iteration: number;
  max_iterations: number;
  artifacts: {
    patch_id?: string;
    decision_card_id?: string;
    html_report_path?: string;
  };
};
```

```ts
export type MasteryRecord = {
  mastery_id: string;
  user_id: string;
  project_id: string;
  topic: string;
  evidence: {
    quiz_score?: number;
    explanation_score?: number;
    trace_score?: number;
    prediction_score?: number;
    review_score?: number;
  };
  level: "unknown" | "basic" | "working" | "review_ready" | "owner_ready";
  updated_at: string;
};
```

```ts
export type EvolutionReport = {
  cycle_id: string;
  project_id: string;
  observed_failures: string[];
  root_causes: Array<{
    category:
      | "prompt"
      | "task_decomposition"
      | "missing_tests"
      | "tool_failure"
      | "bad_context"
      | "risk_policy"
      | "human_gate";
    evidence: string[];
  }>;
  proposed_changes: Array<{
    target: "prompt" | "policy" | "eval" | "task" | "doc" | "retrieval";
    change: string;
    risk: "low" | "medium" | "high";
  }>;
  verification_plan: string[];
  status: "draft" | "approved" | "applied" | "rejected";
};
```

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

## Project Contract Files

Project onboarding can create a `.cognitive-loop/` directory in the target repo. The current repo validates the first four core files with `python3 scripts/verify_cognitive_loop_contracts.py --check` and validates optional manual watcher ingest config with `python3 scripts/verify_cognitive_loop_watcher_ingest.py --check`:

```text
.cognitive-loop/
  config.yaml       project identity, language, package manager, runtime mode, output paths
  permissions.yaml  allowed, approval-required, and denied AI operations
  evals.yaml        test, lint, typecheck, build, coverage, and release gates
  risk.yaml         risk thresholds, high-risk paths, circuit breakers, mastery gates
  watchers.yaml     optional manual watcher ingest rules; no daemon is started
```

任意项目接入时，可以在目标仓库中创建 `.cognitive-loop/` 目录。当前仓库已经可以用 `python3 scripts/verify_cognitive_loop_contracts.py --check` 校验前四个核心文件，并用 `python3 scripts/verify_cognitive_loop_watcher_ingest.py --check` 校验可选的手动 watcher ingest 配置：

```text
.cognitive-loop/
  config.yaml       项目身份、语言、包管理器、运行模式、输出路径
  permissions.yaml  AI 可执行、需审批、禁止的操作
  evals.yaml        test、lint、typecheck、build、coverage、release gates
  risk.yaml         风险阈值、高风险路径、熔断器、掌握度门禁
  watchers.yaml     可选手动 watcher ingest 规则；不会启动 daemon
```

The extended project protocol may later add `learning.yaml` and daemon runtime config, but the public contract should stay small enough for a new repository to adopt.

扩展协议后续可以加入 `learning.yaml` 和 daemon runtime config，但公开契约仍要足够小，让一个新仓库能快速接入。

`python3 scripts/cognitive_loop_event_store.py rebuild` is the current local Event Store entrypoint. It rebuilds a SQLite database from validated `.cognitive-loop/events/*.json` artifacts and `python3 scripts/cognitive_loop_event_store.py export --html` creates a static metadata-only report. It is not a watcher daemon or Mastra runtime.

`python3 scripts/cognitive_loop_event_store.py rebuild` 是当前本地 Event Store 入口。它会从已经校验的 `.cognitive-loop/events/*.json` artifact 重建 SQLite 数据库，`python3 scripts/cognitive_loop_event_store.py export --html` 会创建静态 metadata-only 报告。它不是 watcher daemon，也不是 Mastra runtime。

`python3 scripts/cognitive_loop_watcher_ingest.py ingest --html` is the current watcher bridge. It reads `.cognitive-loop/watchers.yaml`, normalizes one file/git/test/runtime-style observation into a metadata-only `ProjectEvent` artifact, and can be indexed or rebuilt into the SQLite Event Store. It does not run a background watcher daemon, read file contents, embed diff bodies, or call external Agents.

`python3 scripts/cognitive_loop_watcher_ingest.py ingest --html` 是当前 watcher 桥接入口。它读取 `.cognitive-loop/watchers.yaml`，把一次文件/Git/测试/runtime 风格 observation 标准化为只含 metadata 的 `ProjectEvent` artifact，并可被 Event Index 或 SQLite Event Store 重建。它不会运行后台 watcher daemon，不读取文件正文，不嵌入 diff body，也不调用外部 Agent。

`platform/mastra/cognitive-loop-mastra-adapter.ts` is the current Mastra bridge. It is a TypeScript scaffold for an external Mastra project, mapping Cognitive Loop evidence validation and Human Mastery Gate state to workflow steps, suspend/resume, and bail semantics. It is verified by `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check`; it does not mean this repository starts or hosts Mastra.

`platform/mastra/cognitive-loop-mastra-adapter.ts` 是当前的 Mastra 桥接层。它是给外部 Mastra 项目使用的 TypeScript scaffold，把 Cognitive Loop evidence validation 与 Human Mastery Gate 状态映射到 workflow step、suspend/resume 和 bail 语义。它由 `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check` 验证；这不代表本仓库已经启动或托管 Mastra。

`python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` is the current runtime rehearsal. It uses local Cognitive Loop artifacts and the SQLite Event Store to prove the suspend/resume/bail contract without compiling TypeScript, starting Mastra, running a watcher daemon, or calling an external Agent.

`python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` 是当前的 runtime 演练入口。它使用本地 Cognitive Loop artifact 和 SQLite Event Store 来证明 suspend/resume/bail 契约，但不编译 TypeScript、不启动 Mastra、不运行 watcher daemon，也不调用外部 Agent。

`python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` is the first repository-started Mastra runtime MVP. It installs the isolated `platform/mastra-runtime/` Node package, typechecks the workflow against `@mastra/core`, starts an in-memory Mastra instance, and verifies high-risk suspend, approved resume, rejected bail, and low-risk no-gate paths. `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` adds a local libSQL storage proof: a watcher-generated metadata-only `ProjectEvent` suspends, survives a separate Node process, then resumes or bails from the persisted workflow snapshot. `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` maps those service and durable receipts to local Langfuse trace/span/generation/score DTOs without importing the Langfuse SDK or calling a hosted service. These checks still do not start watcher daemons, call external Agents, expose a hosted service, or claim production storage operations.

`python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` 是第一版由本仓库启动的 Mastra runtime MVP。它会安装隔离的 `platform/mastra-runtime/` Node package，用 `@mastra/core` typecheck workflow，启动 in-memory Mastra 实例，并验证高风险暂停、批准恢复、拒绝 bail、低风险无需 gate 四条路径。`python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` 会进一步给出本地 libSQL storage 证明：由 watcher 生成的 metadata-only `ProjectEvent` 进入暂停状态，跨独立 Node 进程后可从持久化 workflow snapshot 恢复或 bail。`python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` 会把这些 service 和 durable receipt 映射成本地 Langfuse trace/span/generation/score DTO，但不导入 Langfuse SDK，也不调用 hosted service。这些检查仍然不启动常驻 watcher daemon，不调用外部 Agent，不暴露 hosted service，也不声称已经具备生产级 storage 运维能力。

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
- Study Anything Adapter evidence must stay metadata-only; learning packages may be used internally, and the CLI Lite report may expose learning status, StudyCard, understanding gaps, scribe summary, MasteryRecord, and LoopRun metadata, but Cognitive Loop reports must not embed source bodies, raw diffs, learner answers, grading feedback, Agent endpoints, Agent metadata, or model keys.
- Event Store is the canonical audit ledger for Cognitive Loop state.
- `.env`, credentials, private keys, signed URLs, raw secrets, and sensitive local paths must not enter HTML reports, traces, learning packages, or public support bundles.
- Risk policy, audit, rollback, and human gate rules must not be weakened by automatic self-evolution.

## Near-Term Non-Goals

- Production Mastra daemon/watch/storage operations are not yet shipped; the repository currently has a minimal Mastra MVP, local libSQL durable proof, local Langfuse DTO mapping proof, metadata-only Study Anything Adapter mastery projection proof, and a platform-Agent-callable Study Adapter CLI Lite.
- Full daemonized project watchers are not yet shipped.
- HTML Artifact console is not yet a complete product UI.
- Hosted Sync, Teams, billing, SSO, and managed cloud are future services, not alpha requirements.
- The current launch path remains API/Skill/platform-Agent first, not a standalone frontend.
