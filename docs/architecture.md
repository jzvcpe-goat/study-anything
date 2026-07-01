# Architecture / 架构

Cognitive Black Box is a local-first Dual-Loop Trust Harness for AI-generated deliverables. It keeps failure evidence, human reconstruction evidence, propagation gates, delivery receipts, project state, risk, verification, learning, and audit outside the long context of any single Agent conversation.

认知黑箱是一个本地优先的 AI 交付 Dual-Loop Trust Harness。它把失败证据、人类重构证据、传播门、交付收据、项目状态、风险、验证、学习和审计外化到文件、数据库、报告和事件账本中，而不是只存在某一次 Agent 长对话里。

## Layered Architecture

```text
Product Entries
  Controlled customer handoff receipt
  Professional HTML Artifact Mode
  Personal Plugin Mode

Dual-Loop Trust Core
  FailureContract
  SandboxReceipt
  AttentionReconstructionTrace
  AttentionReconstructionSummary
  DualLoopGateReceipt
  DeliveryTrustReceipt

Cognitive Loop Project Core
  ProjectEvent
  DecisionCard
  RiskEngine
  LLMDepthRiskEngine
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
  Static Artifact Console Lite
  Professional Evolution Pack Export Lite
  Evolution Pack Consumer Smoke Lite
  Realtime local HTML console
  Markdown/Obsidian/NotebookLM-style exports
```

## Current Implementation

The current repository already implements the deterministic, metadata-only trust-harness foundation:

- Dual-Loop MVP with controlled failure contracts, sandbox receipts, attention reconstruction traces/summaries, and propagation gate receipts.
- Delivery Trust Receipt for controlled customer handoff decisions that require both loops and reject AI-review-only promotion.
- FastAPI API layer for local learning workflows.
- LangGraph-backed and deterministic workflow execution for the Study Anything learning loop.
- User-owned Agent registry and router; real model credentials stay outside Study Anything.
- Redacted Agent audit/eval artifacts and platform-Agent tool surfaces.
- Metadata-only LLM Depth Risk Engine Lite for prompt, hallucination, RAG, context-budget, and cost-quality evidence.
- Real-Agent Eval Bridge for importing user-owned Promptfoo, Ragas, DeepEval, and LangChain AgentEvals receipts without storing keys or raw model data.
- WorkBuddy/Kimi/Codex real-agent learning-quality harness for comparing deterministic demo, user-owned HTTP Agent, and platform-Agent evidence.
- Learning Enrichment packages for web, document, app, video-slice, Markdown, and Obsidian excerpts.
- Obsidian export, second-brain handoff, and NotebookLM-style manual bridge artifacts.
- Cognitive Loop contract files, optional manual watcher ingest config, static evidence artifacts, local event index, SQLite Event Store MVP, static Artifact Console Lite, Personal Plugin Mode Lite, Evolution Report Lite, Governed Apply Plan Lite, Measured Improvement Comparator Lite, Patch Proposal Lite, Mastra Evolution Receipt Link Lite, Mastra Evolution Workflow Replay Lite, Governed Patch Apply Sandbox Lite, Professional Evolution Pack Export Lite, Evolution Pack Consumer Smoke Lite, PR CI Receipt Lite, Maintainer Acceptance Ledger Lite, and a copy-ready Mastra adapter contract pack for metadata-only project evidence.
- Docker self-host path with Postgres, optional Langfuse, optional FalkorDB topology projection, and release evidence.

当前仓库已经实现的是确定性、只含 metadata 的 trust harness 基础层：

- Dual-Loop MVP：可控失败契约、沙箱收据、注意力重构 trace/summary，以及传播门收据。
- Delivery Trust Receipt：用于受控客户交付的收据，必须同时满足两个 loop，并拒绝 AI 审 AI 式放行。
- 面向本地学习工作流的 FastAPI API。
- 用于学习闭环的 LangGraph 和确定性 workflow 执行。
- 用户自有 Agent registry/router；真实模型密钥留在 Study Anything 外部。
- 脱敏 Agent audit/eval 证据和平台 Agent 工具面。
- metadata-only LLM Depth Risk Engine Lite，用于 prompt、幻觉、RAG、上下文预算、成本质量证据。
- Real-Agent Eval Bridge：导入用户自有 Promptfoo、Ragas、DeepEval、LangChain AgentEvals receipt，不保存密钥或 raw model data。
- WorkBuddy/Kimi/Codex real-agent 学习质量 harness：比较 deterministic demo、用户自有 HTTP Agent 和平台 Agent 证据。
- 面向网页、文档、应用上下文、视频切片、Markdown、Obsidian 片段的 Learning Enrichment package。
- Obsidian 导出、second-brain handoff 和 NotebookLM 式手动桥接材料。
- Cognitive Loop 契约文件、可选手动 watcher ingest 配置、静态 evidence artifacts、本地 event index、只存 metadata 的 SQLite Event Store MVP、静态 Artifact Console Lite、Personal Plugin Mode Lite、Evolution Report Lite、Governed Apply Plan Lite、Measured Improvement Comparator Lite、Patch Proposal Lite、Mastra Evolution Receipt Link Lite、Mastra Evolution Workflow Replay Lite、Governed Patch Apply Sandbox Lite、Professional Evolution Pack Export Lite、Evolution Pack Consumer Smoke Lite、PR CI Receipt Lite、Maintainer Acceptance Ledger Lite，以及可复制到外部 Mastra 项目的 Mastra adapter contract pack。
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
- `ImprovementComparison`: a read-only comparison of metadata-only loop artifacts for improved/regressed/unchanged/insufficient/ambiguous loop outcomes.
- `PatchProposal`: a read-only patch specification for prompt, policy, eval, task, doc, and retrieval categories.
- `EvolutionReceiptLink`: a metadata-only linkage record that turns evolution evidence into a future Mastra workflow receipt DTO without starting Mastra, calling models, executing apply, or modifying source files.
- `MastraEvolutionWorkflowReplay`: a metadata-only replay transcript that maps an EvolutionReceiptLink into future Mastra workflow steps without starting production Mastra, calling models, executing apply, or modifying source files.
- `PatchApplySandboxReceipt`: a metadata-only dry-run receipt that proves patch-apply readiness and rollback without mutating the real worktree.
- `EvolutionPackManifest`: a metadata-only professional handoff manifest and ZIP index for maintainers and platform Agents.

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

`.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter` is the current runner-lite bridge. It performs a bounded one-shot/polling pass over explicit local signals, debounces duplicate paths, skips excluded paths, writes metadata-only watcher events, ingests them into the SQLite Event Store, and can trigger the Study Anything adapter CLI for the first high-risk event. It is still not a daemon and does not read file contents, raw diffs, raw test output, learner answers, Agent endpoints, Agent metadata, or model keys.

`.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter` 是当前 runner-lite 桥接入口。它对显式传入的本地信号做有界 one-shot/polling 处理，合并重复路径，跳过 exclude 命中的路径，写出 metadata-only watcher event，摄入 SQLite Event Store，并可对第一个高风险事件触发 Study Anything adapter CLI。它仍然不是 daemon，也不读取文件正文、raw diff、raw test output、学习者答案、Agent endpoint、Agent metadata 或 model key。

`python3 scripts/cognitive_loop_artifact_console.py build --html --json` is the current static Artifact Console Lite entrypoint. It aggregates Event Store rows, watcher runner summaries, Study Adapter artifacts, DecisionCard, Human Gate, LoopRun, Evolution Chain artifact refs, and artifact-health metadata into `.cognitive-loop/artifacts/console/index.html` plus a JSON manifest. It is offline and metadata-only: no daemon, no standalone frontend, no SSE/WebSocket, and no embedded event JSON body, HTML/Markdown body, source text, raw diff, test output, learner answer, Agent endpoint, Agent metadata, prompt, or model key.

`python3 scripts/cognitive_loop_artifact_console.py build --html --json` 是当前静态 Artifact Console Lite 入口。它会把 Event Store rows、watcher runner summary、Study Adapter artifacts、DecisionCard、Human Gate、LoopRun、Evolution Chain artifact refs 和 artifact-health metadata 汇总到 `.cognitive-loop/artifacts/console/index.html` 以及 JSON manifest。它是离线且 metadata-only 的：不启动 daemon，不引入独立前端，不使用 SSE/WebSocket，也不嵌入 event JSON 正文、HTML/Markdown 正文、source text、raw diff、test output、学习者答案、Agent endpoint、Agent metadata、prompt 或 model key。

`python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json` is the current Personal Plugin Mode Lite entrypoint. It creates read-only metadata-only Study Cards, quiz items, and Markdown/HTML learning reports for a file, README, webpage metadata record, or diff summary. It is designed for Kimi, Codex, WorkBuddy, browser assistants, or local Agents that need a lightweight learning artifact without launching a daemon or standalone frontend. It does not modify source files, call a real model, store model keys, or embed raw source text, raw diff bodies, learner answers, Agent endpoints, Agent metadata, or prompts.

`python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json` 是当前 Personal Plugin Mode Lite 入口。它会为文件、README、网页 metadata 记录或 diff summary 生成只读、metadata-only 的 Study Cards、quiz items 和 Markdown/HTML 学习报告。它面向 Kimi、Codex、WorkBuddy、浏览器助手或本地 Agent 这类轻量入口，不启动 daemon，也不要求独立前端。它不会修改源文件、调用真实模型、保存模型密钥，也不会嵌入源文件正文、raw diff body、学习者答案、Agent endpoint、Agent metadata 或 prompt。

`python3 scripts/cognitive_loop_evolution.py build --html --json` is the current Evolution Report Lite entrypoint. It reads metadata-only evidence summaries, failure summaries, Personal Plugin Mode output, or Artifact Console/Event Store evidence references, then writes a governed `EvolutionReport` artifact with failure clusters, root-cause hypotheses, proposed next-loop improvements, regression plan, and success metric. It is read-only: no automatic source changes, no model calls, no daemon, and no weakening of risk, audit, privacy, rollback, test, or permission policy.

`python3 scripts/cognitive_loop_evolution.py build --html --json` 是当前 Evolution Report Lite 入口。它读取 metadata-only evidence summary、failure summary、Personal Plugin Mode 输出或 Artifact Console/Event Store 证据引用，写出受治理的 `EvolutionReport` artifact，包含 failure cluster、root-cause hypothesis、下一轮改进建议、回归计划和成功指标。它是只读的：不自动修改源文件、不调用模型、不启动 daemon，也不削弱 risk、audit、privacy、rollback、test 或 permission policy。

`python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json` is the current Governed Apply Plan Lite entrypoint. It converts low-risk metadata-only Evolution proposals into a dry-run apply plan and, only with `--apply --allow-generated-artifacts`, writes an idempotent receipt/marker under `.cognitive-loop/artifacts/applied/`. It does not write source files, docs, scripts, platform packs, policy files, raw source, raw diff, learner answers, Agent endpoints, Agent metadata, prompts, or model keys.

`python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json` 是当前 Governed Apply Plan Lite 入口。它把低风险、metadata-only 的 Evolution proposal 转换为 dry-run apply plan；只有显式传入 `--apply --allow-generated-artifacts` 时，才会在 `.cognitive-loop/artifacts/applied/` 下写入幂等 receipt/marker。它不会写源码、docs、scripts、platform packs、policy 文件、raw source、raw diff、学习者答案、Agent endpoint、Agent metadata、prompt 或 model key。

`python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json` is the current Measured Improvement Comparator Lite entrypoint. It compares two or more metadata-only Evolution, Apply Plan, receipt, or verification artifacts and classifies the latest loop as improved, regressed, unchanged, insufficient, or ambiguous. It is read-only: no model calls, no apply execution, no source changes, no daemon, and no raw source, raw diff, learner answers, Agent endpoints, Agent metadata, prompts, or model keys.

`python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json` 是当前 Measured Improvement Comparator Lite 入口。它比较两个或多个 metadata-only Evolution、Apply Plan、receipt 或 verification artifact，并将最新 loop 归类为改进、退化、无变化、证据不足或信号混合。它是只读的：不调用模型、不执行 apply、不修改源码、不启动 daemon，也不包含 raw source、raw diff、学习者答案、Agent endpoint、Agent metadata、prompt 或 model key。

`python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json` is the current Patch Proposal Lite entrypoint. It converts metadata-only Evolution, Apply Plan, Improvement Comparison, or verification artifacts into read-only `PatchProposal` specifications across prompt, policy, eval, task, doc, and retrieval categories. It rejects or downgrades high-risk, Human Mastery Gate required, manual-only, protected-path, insufficient, secret-like, raw-diff, and policy-weakening inputs; it never generates raw unified diffs, executes apply, calls models, modifies source files, starts daemons, or stores private learning data.

`python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json` 是当前 Patch Proposal Lite 入口。它把 metadata-only Evolution、Apply Plan、Improvement Comparison 或 verification artifact 转换为只读的 `PatchProposal` 规格，覆盖 prompt、policy、eval、task、doc 和 retrieval 六类。它会拒绝或降级高风险、Human Mastery Gate required、manual-only、受保护路径、证据不足、疑似 secret、raw diff 和 policy weakening 输入；它不会生成 raw unified diff、执行 apply、调用模型、修改源码、启动 daemon 或保存私有学习数据。

`python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json` is the current Mastra Evolution Receipt Link Lite entrypoint. It links metadata-only Evolution Report, Apply Plan, Improvement Comparison, and Patch Proposal artifacts into a read-only `EvolutionReceiptLink` JSON/HTML artifact for future Mastra workflow handoff. It accepts complete evidence as `ready`, degrades missing or insufficient evidence, blocks high-risk ungated or manual-only patch paths, and rejects unsupported schemas, secrets, raw diff bodies, policy weakening, and privacy flag regressions. It never starts Mastra, calls models, executes apply, modifies source files, or stores private learning data.

`python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json` 是当前 Mastra Evolution Receipt Link Lite 入口。它把 metadata-only Evolution Report、Apply Plan、Improvement Comparison 和 Patch Proposal artifact 链接成只读 `EvolutionReceiptLink` JSON/HTML artifact，供未来 Mastra workflow 交接使用。完整证据会标记为 `ready`，缺件或证据不足会降级，高风险未 gate 或 manual-only patch 路径会阻断，并拒绝 unsupported schema、secret、raw diff body、policy weakening 和 privacy flag 回归。它不会启动 Mastra、调用模型、执行 apply、修改源码或保存私有学习数据。

`python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json` is the current Mastra Evolution Workflow Replay Lite entrypoint. It consumes a metadata-only `EvolutionReceiptLink` and writes a read-only `MastraEvolutionWorkflowReplay` JSON/HTML transcript for future workflow handoff. Ready receipts become replay-ready; degraded receipts become manual review; blocked receipts stay blocked/manual-only. It rejects invalid schemas, unsupported statuses, ready receipts with missing roles, high-risk ungated receipts, manual-only patch paths, privacy flag regressions, secrets, raw diff bodies, and policy weakening. It never starts production Mastra, calls models, executes apply, modifies source files, or stores private learning data.

`python3 scripts/cognitive_loop_patch_apply_sandbox.py sandbox --html --json` is the current Governed Patch Apply Sandbox Lite entrypoint. It consumes metadata-only Patch Proposal, Apply Plan, EvolutionReceiptLink, and MastraEvolutionWorkflowReplay refs, builds a `PatchApplySandboxReceipt`, proves rollback through a temporary sandbox preview reference, and confirms the real worktree was not mutated. It rejects invalid schemas, secrets, raw diffs, protected target paths, privacy flag regressions, and policy weakening; it does not execute source-changing apply.

`python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json` 是当前 Mastra Evolution Workflow Replay Lite 入口。它消费 metadata-only `EvolutionReceiptLink`，并写出只读 `MastraEvolutionWorkflowReplay` JSON/HTML transcript，供未来 workflow 交接使用。ready receipt 会成为 replay-ready；degraded receipt 会进入 manual review；blocked receipt 会停在 blocked/manual-only。它拒绝 invalid schema、unsupported status、ready 但缺少 required roles 的 receipt、高风险未 gate receipt、manual-only patch path、privacy flag 回归、secret、raw diff body 和 policy weakening。它不会启动生产 Mastra、调用模型、执行 apply、修改源码或保存私有学习数据。

`python3 scripts/cognitive_loop_patch_apply_sandbox.py sandbox --html --json` 是当前 Governed Patch Apply Sandbox Lite 入口。它消费 metadata-only Patch Proposal、Apply Plan、EvolutionReceiptLink 和 MastraEvolutionWorkflowReplay 引用，写出 `PatchApplySandboxReceipt`，通过临时沙箱预演引用证明 rollback，并确认真实工作树未被修改。它会拒绝 invalid schema、secret、raw diff、受保护路径、privacy flag 回归和 policy weakening；它不执行源码改写 apply。

`python3 scripts/cognitive_loop_evolution_pack_export.py export --html --json --zip` is the current Professional Evolution Pack Export Lite entrypoint. It consumes Artifact Console, Evolution Report, Apply Plan, Improvement Comparison, Patch Proposal, EvolutionReceiptLink, MastraEvolutionWorkflowReplay, and PatchApplySandboxReceipt refs, then writes a metadata-only `EvolutionPackManifest`, static HTML index, and ZIP handoff bundle for maintainers and platform Agents. It rejects invalid schemas, secrets, raw diffs, protected target paths, privacy flag regressions, and policy weakening; it does not start a daemon, require a standalone frontend, call models, execute source-changing apply, or mutate the real worktree.

`python3 scripts/cognitive_loop_evolution_pack_export.py export --html --json --zip` 是当前 Professional Evolution Pack Export Lite 入口。它消费 Artifact Console、Evolution Report、Apply Plan、Improvement Comparison、Patch Proposal、EvolutionReceiptLink、MastraEvolutionWorkflowReplay 和 PatchApplySandboxReceipt 引用，写出 metadata-only `EvolutionPackManifest`、静态 HTML index 和面向维护者/平台 Agent 的 ZIP handoff 包。它会拒绝 invalid schema、secret、raw diff、受保护路径、privacy flag 回归和 policy weakening；它不启动 daemon、不要求独立前端、不调用模型、不执行源码改写 apply，也不修改真实工作树。

`python3 scripts/verify_cognitive_loop_evolution_pack_consumer.py --pack <cognitive-loop-professional-evolution-pack.zip>` is the current Evolution Pack Consumer Smoke Lite entrypoint. It verifies the Professional Evolution Pack from the ZIP alone: schema, manifest-derived pack id, archive layout, entry hashes, artifact refs, operator commands, privacy flags, and read-only guardrails. It rejects tampered ZIPs, manifest drift, missing files, hash mismatches, secrets, raw diffs, protected paths, policy weakening, privacy regressions, and unsafe ZIP paths without requiring API, Docker, a repo checkout, model calls, or source mutation.

`python3 scripts/verify_cognitive_loop_evolution_pack_consumer.py --pack <cognitive-loop-professional-evolution-pack.zip>` 是当前 Evolution Pack Consumer Smoke Lite 入口。它只依赖 Professional Evolution Pack ZIP 验证 schema、由 manifest 派生的 pack id、archive layout、entry hash、artifact refs、operator commands、privacy flags 和只读 guardrails。它会拒绝 tampered ZIP、manifest drift、缺失文件、hash mismatch、secret、raw diff、受保护路径、policy weakening、privacy regression 和 unsafe ZIP path；不需要 API、Docker、仓库 checkout、模型调用或源码修改。

`python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --check` is the current PR CI Receipt Lite entrypoint. It emits metadata-only `cognitive-loop-pr-ci-receipt-v1` evidence for required GitHub checks, currently from an offline redacted fixture and later from sanitized `gh pr checks --json` output. It records check names, statuses, PR number, head SHA, decision, and next review commands without GitHub tokens, raw logs, model calls, Docker/API, or source mutation.

`python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --check` 是当前 PR CI Receipt Lite 入口。它输出 metadata-only 的 `cognitive-loop-pr-ci-receipt-v1`，用于记录必需 GitHub checks；当前默认来自离线脱敏 fixture，后续可接入净化后的 `gh pr checks --json` 输出。它只记录 check name、status、PR number、head SHA、decision 和下一步 review command，不包含 GitHub token、raw log、模型调用、Docker/API 或源码修改。

`python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check` is the current Maintainer Acceptance Ledger Lite entrypoint. It aggregates the Professional Evolution Pack export report, zip-only consumer report, PR CI Receipt, public release/adoption evidence, and local release gate status into a metadata-only `ready|manual_review|blocked` go/no-go ledger. It rejects missing consumer evidence, stale pack hashes, failed CI, missing release evidence, unsafe operator commands, policy weakening, and privacy regressions without calling models, starting daemons, requiring Docker/API, or mutating source.

`python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check` 是当前 Maintainer Acceptance Ledger Lite 入口。它聚合 Professional Evolution Pack export report、zip-only consumer report、PR CI Receipt、公开 release/adoption evidence 和本地 release gate 状态，生成 metadata-only 的 `ready|manual_review|blocked` go/no-go 账本。它会拒绝缺失 consumer evidence、pack hash 过期、CI 失败、缺失 release evidence、unsafe operator command、policy weakening 和 privacy regression；不会调用模型、启动 daemon、要求 Docker/API 或修改源码。

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
- static metadata-only Artifact Console Lite for Event Store, watcher runner, Study Adapter, Human Gate, LoopRun, Evolution Chain, and artifact-health status
- Personal Plugin Mode Lite for read-only file, README, webpage metadata, and diff-summary learning artifacts
- realtime local HTML console for watcher events, human gates, Agent audit, and verification status
- CI-uploadable reports for PR review and team handoff

专业 HTML Artifact 模式输出可在浏览器打开和归档的材料：

- 项目地图、时间线、决策卡、掌握度、审计和进化报告的静态 HTML
- 面向 Event Store、watcher runner、Study Adapter、Human Gate、LoopRun、Evolution Chain 和 artifact-health 状态的静态 metadata-only Artifact Console Lite
- 面向文件、README、网页 metadata 和 diff summary 的只读 Personal Plugin Mode Lite 学习 artifact
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

- Production Mastra daemon/watch/storage operations are not yet shipped; the repository currently has a minimal Mastra MVP, local libSQL durable proof, local Langfuse DTO mapping proof, metadata-only Study Anything Adapter mastery projection proof, a platform-Agent-callable Study Adapter CLI Lite, static Artifact Console Lite, Personal Plugin Mode Lite, Evolution Report Lite, Governed Apply Plan Lite, Measured Improvement Comparator Lite, Patch Proposal Lite, Mastra Evolution Receipt Link Lite, Mastra Evolution Workflow Replay Lite, Governed Patch Apply Sandbox Lite, Professional Evolution Pack Export Lite, Evolution Pack Consumer Smoke Lite, PR CI Receipt Lite with optional GitHub CLI metadata adapter, and Maintainer Acceptance Ledger Lite.
- Governed source-changing auto-apply is not yet shipped; Apply Plan Lite only writes generated-artifact receipts when explicitly allowed, Patch Proposal Lite produces read-only patch specifications rather than raw diffs, Patch Apply Sandbox Lite only proves dry-run readiness without mutating the real worktree, Professional Evolution Pack Export Lite only packages redacted metadata evidence, and Evolution Pack Consumer Smoke Lite only validates that ZIP handoff offline.
- Full daemonized project watchers are not yet shipped.
- Realtime HTML Artifact console is not yet a complete product UI.
- Hosted Sync, Teams, billing, SSO, and managed cloud are future services, not alpha requirements.
- The current launch path remains API/Skill/platform-Agent first, not a standalone frontend.
