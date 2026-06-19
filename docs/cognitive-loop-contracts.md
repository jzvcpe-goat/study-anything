# Cognitive Loop Contracts / 认知自循环契约

This document describes the first implemented Cognitive Loop contract bootstrap. It is not the Mastra runtime, not a watcher daemon, and not the full HTML console. It is the local, framework-independent contract layer that those pieces should use later.

本文说明第一版已经实现的 Cognitive Loop contract bootstrap。它不是 Mastra runtime，不是 watcher daemon，也不是完整 HTML console。它是这些后续能力应当复用的本地、框架无关契约层。

## What Shipped

The repository now includes four local contract files:

```text
.cognitive-loop/config.yaml
.cognitive-loop/permissions.yaml
.cognitive-loop/evals.yaml
.cognitive-loop/risk.yaml
```

And one verifier:

```bash
python3 scripts/verify_cognitive_loop_contracts.py --check
python3 scripts/verify_cognitive_loop_review.py --check
python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check
python3 scripts/verify_cognitive_loop_review_agent_report.py --check
```

The repository also includes a small local CLI:

```bash
python3 scripts/cognitive_loop_cli.py init
python3 scripts/cognitive_loop_cli.py verify
python3 scripts/cognitive_loop_cli.py report --html
python3 scripts/cognitive_loop_cli.py run-once --html
python3 scripts/cognitive_loop_cli.py snapshot --html
python3 scripts/cognitive_loop_cli.py gate --approve --html
python3 scripts/cognitive_loop_cli.py bundle --html
python3 scripts/cognitive_loop_cli.py index --html
python3 scripts/cognitive_loop_cli.py doctor --html
python3 scripts/cognitive_loop_cli.py repair-plan --html
python3 scripts/cognitive_loop_cli.py artifact-index --html
python3 scripts/cognitive_loop_review.py --base main --head HEAD --html
```

This CLI set is for repo-local contract bootstrap, static HTML DecisionCard artifacts, and advisory code-review evidence. It is not a daemon, does not watch files, does not call Mastra, does not call a model, does not store model keys, and does not require a standalone frontend.

The external Review Agent prompt contract is checked separately:

```bash
python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check
```

That prompt contract lives at `platform/prompts/cognitive-loop-review-agent.json`. It is for CI/platform delivery assurance, not for end-user learning sessions. It requires JSON-only output, diff-only review, line-level evidence, suppression of low-confidence findings, and a maximum of eight external Agent findings.

The external report handoff is checked with:

```bash
python3 scripts/verify_cognitive_loop_review_agent_report.py --check
```

The report schema lives at `platform/schemas/cognitive-loop-review-agent-report.schema.json`, with accepted and rejected examples in `fixtures/review-agent`. This keeps the Review Agent loop machine-checkable without storing raw diffs or file bodies in Study Anything.

仓库也包含一个小型本地 CLI：

```bash
python3 scripts/cognitive_loop_cli.py init
python3 scripts/cognitive_loop_cli.py verify
python3 scripts/cognitive_loop_cli.py report --html
python3 scripts/cognitive_loop_cli.py run-once --html
python3 scripts/cognitive_loop_cli.py snapshot --html
python3 scripts/cognitive_loop_cli.py gate --approve --html
python3 scripts/cognitive_loop_cli.py bundle --html
python3 scripts/cognitive_loop_cli.py index --html
python3 scripts/cognitive_loop_cli.py doctor --html
python3 scripts/cognitive_loop_cli.py repair-plan --html
python3 scripts/cognitive_loop_cli.py artifact-index --html
python3 scripts/cognitive_loop_review.py --base main --head HEAD --html
```

这组 CLI 用于本地契约初始化、静态 HTML DecisionCard artifact 和咨询式代码审查证据。它不是 daemon，不监听文件，不调用 Mastra，不调用模型，不保存模型 key，也不要求独立前端。

外部 Review Agent 的提示词契约单独验证：

```bash
python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check
```

该契约位于 `platform/prompts/cognitive-loop-review-agent.json`。它服务 CI/平台交付验收，不服务终端用户学习会话；它要求 JSON-only 输出、仅基于 diff 审查、行级证据、抑制 low-confidence findings，并且外部 Agent 最多输出八条发现。

外部报告交接用下面的命令验证：

```bash
python3 scripts/verify_cognitive_loop_review_agent_report.py --check
```

报告 schema 位于 `platform/schemas/cognitive-loop-review-agent-report.schema.json`，通过和拒绝样例位于 `fixtures/review-agent`。这样 Review Agent loop 可以机器验收，同时 Study Anything 仍不保存 raw diff 或文件正文。

The verifier emits `cognitive-loop-contract-bootstrap-v1` and proves:

- all four `.cognitive-loop` files exist and use the expected schema versions;
- default mode is read-only;
- real model keys and Agent endpoints stay outside Study Anything;
- raw source text is forbidden in public contracts;
- required evals include the Cognitive Loop contract verifier and CLI artifact verifier;
- required evals include the Cognitive Loop run-once evidence verifier;
- required evals include the Cognitive Loop project snapshot verifier;
- required evals include the Cognitive Loop Human Mastery Gate verifier;
- required evals include the Cognitive Loop evidence bundle verifier;
- required evals include the Cognitive Loop event index, SQLite Event Store, manual watcher ingest, Mastra adapter contract pack, artifact doctor, repair plan, and artifact index verifiers;
- high or blocked risk rules require a Human Mastery Gate;
- `ProjectEvent`, `DecisionCard`, `LoopRun`, `MasteryRecord`, and `EvolutionReport` validate as redacted public DTOs;
- secret-like values, raw excerpt fields, and high-risk decisions without a human gate are rejected.

验证器会输出 `cognitive-loop-contract-bootstrap-v1`，并证明：

- 四个 `.cognitive-loop` 文件都存在且 schema version 正确；
- 默认模式是只读；
- 真实模型密钥和 Agent endpoint 留在 Study Anything 外部；
- public contract 禁止包含原始 source text；
- required evals 包含 Cognitive Loop contract verifier 和 CLI artifact verifier；
- required evals 包含 Cognitive Loop run-once evidence verifier；
- required evals 包含 Cognitive Loop project snapshot verifier；
- required evals 包含 Cognitive Loop Human Mastery Gate verifier；
- required evals 包含 Cognitive Loop evidence bundle verifier；
- required evals 包含 Cognitive Loop event index、SQLite Event Store、手动 watcher ingest、Mastra adapter contract pack、artifact doctor、repair plan 和 artifact index verifier；
- high / blocked 风险规则必须有人类掌握度门禁；
- `ProjectEvent`、`DecisionCard`、`LoopRun`、`MasteryRecord`、`EvolutionReport` 可以作为脱敏 public DTO 校验；
- secret-like 值、raw excerpt 字段、没有 human gate 的高风险决策会被拒绝。

## Local HTML Artifact

`python3 scripts/cognitive_loop_cli.py report --html` writes a static local HTML report under `.cognitive-loop/artifacts/` by default. The artifact contains:

- local readiness status;
- a redacted `DecisionCard`;
- the four contract file statuses;
- the next commands for init, verify, and report;
- the redacted JSON payload used to render the page.

`python3 scripts/verify_cognitive_loop_cli.py --check` verifies this path in a temporary external-adopter project and emits `cognitive-loop-cli-artifact-verification-v1`.

`python3 scripts/cognitive_loop_cli.py report --html` 默认会在 `.cognitive-loop/artifacts/` 下写入静态本地 HTML 报告。该 artifact 包含：

- 本地 readiness 状态；
- 脱敏 `DecisionCard`；
- 四个 contract 文件状态；
- init、verify、report 的下一步命令；
- 用于渲染页面的脱敏 JSON payload。

`python3 scripts/verify_cognitive_loop_cli.py --check` 会在临时 external-adopter project 中验证这条路径，并输出 `cognitive-loop-cli-artifact-verification-v1`。

## Run-Once Evidence

`python3 scripts/cognitive_loop_cli.py run-once --html` performs one bounded local Cognitive Loop evidence cycle. It validates the contract files, builds a redacted `ProjectEvent`, `DecisionCard`, `LoopRun`, `MasteryRecord`, and `EvolutionReport`, writes JSON evidence under `.cognitive-loop/events/`, and writes an optional static HTML artifact under `.cognitive-loop/artifacts/`.

This is still not a watcher daemon, not Mastra, and not the final realtime HTML console. It is the smallest usable operational loop for external platform Agents and local operators.

`python3 scripts/verify_cognitive_loop_run_once.py --check` verifies this path in a temporary external-adopter project and emits `cognitive-loop-run-once-evidence-verification-v1`.

`python3 scripts/cognitive_loop_cli.py run-once --html` 会执行一次有边界的本地 Cognitive Loop evidence cycle。它会验证 contract 文件，生成脱敏的 `ProjectEvent`、`DecisionCard`、`LoopRun`、`MasteryRecord` 和 `EvolutionReport`，把 JSON evidence 写入 `.cognitive-loop/events/`，并可选地把静态 HTML artifact 写入 `.cognitive-loop/artifacts/`。

这仍然不是 watcher daemon，不是 Mastra，也不是最终实时 HTML console。它只是给外部平台 Agent 和本地操作者使用的最小可运行运营循环。

`python3 scripts/verify_cognitive_loop_run_once.py --check` 会在临时 external-adopter project 中验证这条路径，并输出 `cognitive-loop-run-once-evidence-verification-v1`。

## Project Snapshot Evidence

`python3 scripts/cognitive_loop_cli.py snapshot --html` captures a redacted path-level project snapshot. By default it reads `git status --short --untracked-files=all`; operators can also pass explicit repo-relative paths with repeated `--path` arguments.

The snapshot records changed path counts and repo-relative path refs only. It does not store diff bodies, file contents, source text, Agent endpoints, model keys, or watcher state.

`python3 scripts/verify_cognitive_loop_snapshot.py --check` verifies this path in a temporary external-adopter project and emits `cognitive-loop-project-snapshot-verification-v1`.

`python3 scripts/cognitive_loop_cli.py snapshot --html` 会捕获脱敏的路径级项目 snapshot。默认会读取 `git status --short --untracked-files=all`；操作者也可以通过重复的 `--path` 参数传入 repo-relative path。

snapshot 只记录 changed path 数量和 repo-relative path refs，不保存 diff body、文件内容、source text、Agent endpoint、model key 或 watcher state。

`python3 scripts/verify_cognitive_loop_snapshot.py --check` 会在临时 external-adopter project 中验证这条路径，并输出 `cognitive-loop-project-snapshot-verification-v1`。

## Human Mastery Gate Evidence

`python3 scripts/cognitive_loop_cli.py gate --approve --html` records a local Human Mastery Gate resolution for a high-risk DecisionCard. Operators can also use `--reject`, pass a public `--decision-id`, add repeated `--evidence-ref` values, and write JSON evidence under `.cognitive-loop/events/`.

The gate artifact records approval or rejection metadata, rationale, evidence refs, risk, rollback strategy, and verification commands. It does not execute the gated change, read source files, store diff bodies, store learner answers, store Agent endpoints, or store model keys.

`python3 scripts/verify_cognitive_loop_human_gate.py --check` verifies approved and rejected gate paths in a temporary external-adopter project and emits `cognitive-loop-human-gate-verification-v1`.

`python3 scripts/cognitive_loop_cli.py gate --approve --html` 会为高风险 DecisionCard 记录本地 Human Mastery Gate resolution。操作者也可以使用 `--reject`，传入公开的 `--decision-id`，重复添加 `--evidence-ref`，并把 JSON evidence 写入 `.cognitive-loop/events/`。

gate artifact 只记录批准或拒绝 metadata、理由、evidence refs、风险、回滚策略和验证命令。它不会执行被 gate 的变更，不读取源文件，不保存 diff body，不保存学习者答案，不保存 Agent endpoint，也不保存 model key。

`python3 scripts/verify_cognitive_loop_human_gate.py --check` 会在临时 external-adopter project 中验证批准和拒绝两条路径，并输出 `cognitive-loop-human-gate-verification-v1`。

## Evidence Bundle Manifest

`python3 scripts/cognitive_loop_cli.py bundle --html` creates a local evidence bundle manifest for Cognitive Loop artifacts. By default it scans `.cognitive-loop/events/` and `.cognitive-loop/artifacts/`, or operators can pass repeated `--artifact` paths.

The bundle stores artifact paths, kind, size, and SHA-256 digest only. It does not embed artifact contents, source text, diff bodies, learner answers, Agent endpoints, Agent metadata, or model keys.

`python3 scripts/verify_cognitive_loop_evidence_bundle.py --check` verifies a run/snapshot/gate bundle in a temporary external-adopter project and emits `cognitive-loop-evidence-bundle-verification-v1`.

`python3 scripts/cognitive_loop_cli.py bundle --html` 会为 Cognitive Loop artifact 创建本地 evidence bundle manifest。默认扫描 `.cognitive-loop/events/` 和 `.cognitive-loop/artifacts/`，操作者也可以重复传入 `--artifact` 路径。

bundle 只保存 artifact path、kind、size 和 SHA-256 digest，不嵌入 artifact 正文、source text、diff body、学习者答案、Agent endpoint、Agent metadata 或 model key。

`python3 scripts/verify_cognitive_loop_evidence_bundle.py --check` 会在临时 external-adopter project 中验证 run/snapshot/gate bundle，并输出 `cognitive-loop-evidence-bundle-verification-v1`。

## Event Index Manifest

`python3 scripts/cognitive_loop_cli.py index --html` creates a local event timeline index from Cognitive Loop JSON event artifacts. By default it scans `.cognitive-loop/events/*.json`, or operators can pass repeated `--event` paths.

The index stores event artifact path, kind, schema, status, generated timestamp, size, SHA-256 digest, and public ids such as `ProjectEvent`, `DecisionCard`, and `LoopRun` ids when present. It does not embed event JSON contents, artifact contents, source text, diff bodies, learner answers, Agent endpoints, Agent metadata, or model keys.

This is still a manual rebuild command, not a watcher daemon. It is intended as the bridge between local artifact evidence and a future realtime HTML console.

`python3 scripts/verify_cognitive_loop_event_index.py --check` verifies run/snapshot/gate/bundle indexing in a temporary external-adopter project and emits `cognitive-loop-event-index-verification-v1`.

`python3 scripts/cognitive_loop_cli.py index --html` 会从 Cognitive Loop JSON event artifacts 创建本地事件 timeline index。默认扫描 `.cognitive-loop/events/*.json`，操作者也可以重复传入 `--event` 路径。

index 只保存 event artifact path、kind、schema、status、generated timestamp、size、SHA-256 digest，以及存在时的 `ProjectEvent`、`DecisionCard`、`LoopRun` 等公开 id。它不嵌入 event JSON 正文、artifact 正文、source text、diff body、学习者答案、Agent endpoint、Agent metadata 或 model key。

这仍然是手动重建命令，不是 watcher daemon。它用于连接本地 artifact evidence 和未来实时 HTML console。

`python3 scripts/verify_cognitive_loop_event_index.py --check` 会在临时 external-adopter project 中验证 run/snapshot/gate/bundle index，并输出 `cognitive-loop-event-index-verification-v1`。

## SQLite Event Store

`python3 scripts/cognitive_loop_event_store.py rebuild` creates a local SQLite Event Store from validated Cognitive Loop JSON event artifacts. By default it reads `.cognitive-loop/events/*.json`, or operators can pass repeated `--event` paths.

The store records `ProjectEvent` metadata, artifact path, artifact kind, schema, status, size, SHA-256 digest, and public ids such as `DecisionCard` and `LoopRun` ids when present. It does not store artifact contents, source text, diff bodies, learner answers, Agent endpoints, Agent metadata, model keys, or prompt text.

`python3 scripts/cognitive_loop_event_store.py export --html` exports a static metadata-only Event Store report. The database is local and rebuildable; it is not a watcher daemon, background queue, Mastra runtime, or realtime HTML console.

`python3 scripts/verify_cognitive_loop_event_store.py --check` verifies SQLite schema creation, idempotent rebuild, HTML/JSON export, hash coverage, content exclusion, and unsafe Agent endpoint rejection in a temporary external-adopter project. It emits `cognitive-loop-event-store-verification-v1`.

`python3 scripts/cognitive_loop_event_store.py rebuild` 会从已经校验的 Cognitive Loop JSON event artifacts 创建本地 SQLite Event Store。默认读取 `.cognitive-loop/events/*.json`，操作者也可以重复传入 `--event` 路径。

Event Store 只记录 `ProjectEvent` metadata、artifact path、artifact kind、schema、status、size、SHA-256 digest，以及存在时的 `DecisionCard` 和 `LoopRun` 等公开 id。它不保存 artifact 正文、source text、diff body、学习者答案、Agent endpoint、Agent metadata、model key 或 prompt text。

`python3 scripts/cognitive_loop_event_store.py export --html` 会导出静态 metadata-only Event Store 报告。数据库是本地可重建的；它不是 watcher daemon、后台队列、Mastra runtime 或实时 HTML console。

`python3 scripts/verify_cognitive_loop_event_store.py --check` 会在临时 external-adopter project 中验证 SQLite schema 创建、重复 rebuild 幂等、HTML/JSON 导出、hash 覆盖、正文排除和 unsafe Agent endpoint 拒绝，并输出 `cognitive-loop-event-store-verification-v1`。

## Manual Watcher Ingest / 手动 Watcher 摄入

`.cognitive-loop/watchers.yaml` is the optional watcher ingest contract. It declares enabled watcher kinds, their `ProjectEvent` type, include/exclude globs, `maxRefs`, and the current MVP mode: `manual_ingest`.

`.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter` adds runner-lite on top of manual ingest. It accepts explicit path, git diff summary, and test failure summary signals; debounces repeated observations; skips excluded paths; writes metadata-only watcher events; ingests them into the SQLite Event Store; and can trigger Study Anything adapter CLI for the first high-risk event. It is bounded to local one-shot/polling execution and does not start a daemon.

`.venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check` verifies runner-lite with duplicate path debounce, `.env` exclusion, git diff summary, test failure summary, raw diff rejection, Event Store idempotency, Study Adapter gate triggering, and privacy flags. It emits `cognitive-loop-watcher-runner-verification-v1`.

`.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter` 在手动 ingest 之上加入 runner-lite。它接收显式 path、git diff summary、test failure summary 信号，合并重复 observation，跳过 exclude 路径，写出 metadata-only watcher event，摄入 SQLite Event Store，并可对第一个高风险事件触发 Study Anything adapter CLI。它只做有界本地 one-shot/polling，不启动 daemon。

`.venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check` 会验证 runner-lite 的重复路径 debounce、`.env` 排除、git diff summary、test failure summary、raw diff 拒绝、Event Store 幂等、Study Adapter gate 触发和隐私标记，并输出 `cognitive-loop-watcher-runner-verification-v1`。

`python3 scripts/cognitive_loop_watcher_ingest.py init-config` creates the default watcher config. `python3 scripts/cognitive_loop_watcher_ingest.py validate-config` validates that config stays metadata-only and that no daemon is enabled. `python3 scripts/cognitive_loop_watcher_ingest.py ingest --html --watcher-id file-change --target docs/cognitive-loop-contracts.md` writes a metadata-only watcher event artifact under `.cognitive-loop/events/`.

The ingest artifact stores watcher id, source kind, event type, target, public refs, `ProjectEvent`, `DecisionCard`, and `LoopRun` metadata only. It does not read or store file contents, diff bodies, event payload contents, source text, learner answers, Agent endpoints, Agent metadata, prompts, or model keys.

`python3 scripts/verify_cognitive_loop_watcher_ingest.py --check` verifies config creation, config validation, file-change event creation, Event Index classification as `watcher_ingest`, SQLite Event Store ingestion, excluded target rejection, malformed config rejection, and privacy boundaries. It emits `cognitive-loop-watcher-ingest-verification-v1`.

`.cognitive-loop/watchers.yaml` 是可选 watcher ingest contract。它声明启用的 watcher kind、对应 `ProjectEvent` 类型、include/exclude glob、`maxRefs`，以及当前 MVP 模式：`manual_ingest`。

`python3 scripts/cognitive_loop_watcher_ingest.py init-config` 会创建默认 watcher 配置。`python3 scripts/cognitive_loop_watcher_ingest.py validate-config` 会验证配置保持 metadata-only 且不启用 daemon。`python3 scripts/cognitive_loop_watcher_ingest.py ingest --html --watcher-id file-change --target docs/cognitive-loop-contracts.md` 会在 `.cognitive-loop/events/` 下写入只含 metadata 的 watcher event artifact。

ingest artifact 只保存 watcher id、source kind、event type、target、公开 refs、`ProjectEvent`、`DecisionCard` 和 `LoopRun` metadata。它不读取或保存文件正文、diff body、event payload 正文、source text、学习者答案、Agent endpoint、Agent metadata、prompt 或 model key。

`python3 scripts/verify_cognitive_loop_watcher_ingest.py --check` 会验证配置创建、配置校验、file-change event 创建、Event Index 识别为 `watcher_ingest`、SQLite Event Store 摄入、排除目标拒绝、错误配置拒绝和隐私边界，并输出 `cognitive-loop-watcher-ingest-verification-v1`。

## Mastra Adapter Contract Pack

`platform/mastra/cognitive-loop-mastra-adapter.ts` is a copy-ready TypeScript scaffold for external Mastra projects. It maps Cognitive Loop metadata-only evidence into Mastra workflow steps, with a Human Mastery Gate represented through suspend/resume and rejection represented through bail semantics.

`platform/mastra/manifest.json` records the current boundary: this repository ships an adapter contract pack, not a running Mastra service. Study Anything does not compile the TypeScript scaffold, start Mastra, run a watcher daemon, or store model keys.

`python3 scripts/verify_cognitive_loop_mastra_adapter.py --check` verifies required files, Mastra workflow markers, HITL mapping, privacy boundaries, and a deterministic dry-run contract. It emits `cognitive-loop-mastra-adapter-verification-v1`.

`python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` goes one step further without starting Mastra. It creates temporary local Cognitive Loop artifacts, forces a high-risk `LoopRun` into Human Mastery Gate suspension, records approved and rejected gate resolutions, rebuilds a local SQLite Event Store, and emits `cognitive-loop-mastra-runtime-dry-run-verification-v1`. This proves the runtime contract can be rehearsed by platform Agents while still excluding raw source text, diff bodies, learner answers, Agent endpoints, prompts, and model keys.

`python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` starts the isolated `platform/mastra-runtime/` package and runs the same HITL contract through `@mastra/core`. It emits `cognitive-loop-mastra-runtime-service-verification-v1` and proves the repository can start a minimal Mastra workflow MVP while still excluding raw source text, diff bodies, learner answers, Agent endpoints, prompts, and model keys. `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` emits `cognitive-loop-mastra-runtime-durable-verification-v1` and proves the same high-risk gate can persist to a local libSQL file, then resume or bail across separate Node processes from watcher-generated metadata evidence. `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` emits `cognitive-loop-langfuse-observability-verification-v1` and maps those service/durable receipts to local Langfuse trace/span/generation/score DTOs without calling Langfuse, importing the Langfuse SDK, or exposing source bodies, diffs, learner answers, Agent endpoints, Agent metadata, prompts, model keys, storage paths, or absolute local paths. `python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` emits `cognitive-loop-study-anything-adapter-v1` and proves Study Anything can serve as the Cognitive Loop Learning Adapter: metadata-only ProjectEvent/DecisionCard input becomes a source-bound LearningContextPackage, completes a deterministic local learning loop, then projects MasteryRecord/LoopRun evidence without leaking source bodies, raw diffs, learner answers, Agent endpoints, Agent metadata, or model keys. `.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html` exposes that bridge as CLI Lite for platform Agents, writing metadata-only JSON/HTML learning status, StudyCard, understanding gaps, scribe summary, MasteryRecord, and LoopRun evidence. Production daemon/watch/storage/observability operations remain planned.

`platform/mastra/cognitive-loop-mastra-adapter.ts` 是给外部 Mastra 项目复制使用的 TypeScript scaffold。它把 Cognitive Loop 的 metadata-only evidence 映射为 Mastra workflow steps，并用 suspend/resume 表达 Human Mastery Gate，用 bail 表达拒绝。

`platform/mastra/manifest.json` 记录当前边界：本仓库交付的是 adapter contract pack，不是正在运行的 Mastra 服务。Study Anything 不编译这个 TypeScript scaffold，不启动 Mastra，不运行 watcher daemon，也不保存 model key。

`python3 scripts/verify_cognitive_loop_mastra_adapter.py --check` 会验证必需文件、Mastra workflow 标记、HITL 映射、隐私边界和确定性 dry-run contract，并输出 `cognitive-loop-mastra-adapter-verification-v1`。

`python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` 会在不启动 Mastra 的前提下再推进一步。它会创建临时本地 Cognitive Loop artifact，让高风险 `LoopRun` 进入 Human Mastery Gate 暂停，记录批准与拒绝两种 gate resolution，重建本地 SQLite Event Store，并输出 `cognitive-loop-mastra-runtime-dry-run-verification-v1`。这证明 platform Agent 可以演练 runtime contract，同时仍然排除源码正文、diff body、学习者答案、Agent endpoint、prompt 和 model key。

`python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` 会启动隔离的 `platform/mastra-runtime/` package，并通过 `@mastra/core` 运行同一套 HITL contract。它输出 `cognitive-loop-mastra-runtime-service-verification-v1`，证明本仓库可以启动一个最小 Mastra workflow MVP，同时仍然排除源码正文、diff body、学习者答案、Agent endpoint、prompt 和 model key。`python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` 会输出 `cognitive-loop-mastra-runtime-durable-verification-v1`，证明同一个高风险 gate 可以持久化到本地 libSQL 文件，并跨独立 Node 进程基于 watcher 生成的 metadata evidence 恢复或 bail。`python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` 会输出 `cognitive-loop-langfuse-observability-verification-v1`，并把这些 service/durable receipt 映射成本地 Langfuse trace/span/generation/score DTO；它不调用 Langfuse，不导入 Langfuse SDK，也不暴露源码正文、diff body、学习者答案、Agent endpoint、Agent metadata、prompt、model key、storage path 或绝对本地路径。`python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` 会输出 `cognitive-loop-study-anything-adapter-v1`，证明 Study Anything 可以作为 Cognitive Loop Learning Adapter：metadata-only ProjectEvent/DecisionCard 生成 source-bound LearningContextPackage，完成确定性本地学习闭环，并把 MasteryRecord/LoopRun evidence 投回 Cognitive Loop，同时不泄露源码正文、raw diff、学习者答案、Agent endpoint、Agent metadata 或 model key。`.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html` 会把这个桥接暴露成平台 Agent 可调用的 CLI Lite，并写出只含 metadata 的 JSON/HTML 学习状态、StudyCard、理解缺口、scribe 摘要、MasteryRecord 和 LoopRun evidence。生产级 daemon/watch/storage/observability 运维仍然是计划能力。

## Artifact Doctor / Artifact 诊断器

`python3 scripts/cognitive_loop_cli.py doctor --html` checks local Cognitive Loop event and artifact consistency before watcher automation. It scans `.cognitive-loop/events/` and `.cognitive-loop/artifacts/` for JSON, HTML, and Markdown artifacts.

The doctor stores artifact path, kind, schema, status, modified timestamp, size, SHA-256 digest, issue code, severity, and repair command only. It does not embed event JSON contents, HTML contents, Markdown contents, source text, diff bodies, learner answers, Agent endpoints, Agent metadata, or model keys.

The first doctor checks detect missing same-stem HTML artifacts, duplicate hashes, invalid JSON, unsafe filenames, stale event-index hashes, and stale evidence-bundle hashes. This is still a manual consistency command, not a watcher daemon or realtime HTML console.

`python3 scripts/verify_cognitive_loop_artifact_doctor.py --check` verifies clean and intentionally broken artifact sets in temporary external-adopter projects and emits `cognitive-loop-artifact-doctor-verification-v1`.

`python3 scripts/cognitive_loop_cli.py doctor --html` 会在 watcher automation 之前检查本地 Cognitive Loop event 和 artifact consistency。它扫描 `.cognitive-loop/events/` 与 `.cognitive-loop/artifacts/` 里的 JSON、HTML 和 Markdown artifacts。

doctor 只保存 artifact path、kind、schema、status、modified timestamp、size、SHA-256 digest、issue code、severity 和 repair command。它不嵌入 event JSON 正文、HTML 正文、Markdown 正文、source text、diff body、学习者答案、Agent endpoint、Agent metadata 或 model key。

第一版 doctor 会检测缺失的同名 HTML artifact、重复 hash、无效 JSON、不安全文件名、过期 event-index hash 和过期 evidence-bundle hash。这仍然是手动一致性命令，不是 watcher daemon 或实时 HTML console。

`python3 scripts/verify_cognitive_loop_artifact_doctor.py --check` 会在临时 external-adopter project 中验证干净 artifact 集和故意构造的坏 artifact 集，并输出 `cognitive-loop-artifact-doctor-verification-v1`。

## Repair Plan / 修复计划

`python3 scripts/cognitive_loop_cli.py repair-plan --html` creates a manual-only repair plan from artifact doctor issues. It maps issue codes to suggested commands, risk levels, and Human Mastery Gate hints, but it does not execute file changes or delete artifacts.

The repair plan stores issue code, public path metadata, recommended command, risk level, gate recommendation, and verification command only. It keeps `manual_only=true` and `auto_apply=false`, and does not embed event JSON contents, HTML contents, Markdown contents, source text, diff bodies, learner answers, Agent endpoints, Agent metadata, or model keys.

`python3 scripts/verify_cognitive_loop_repair_plan.py --check` verifies clean and bad fixtures and emits `cognitive-loop-repair-plan-verification-v1`.

`python3 scripts/cognitive_loop_cli.py repair-plan --html` 会根据 artifact doctor issues 创建只允许手动执行的 repair plan。它把 issue code 映射为建议命令、风险级别和 Human Mastery Gate 提示，但不会执行文件修改，也不会删除 artifact。

repair plan 只保存 issue code、公开路径 metadata、recommended command、risk level、gate recommendation 和 verification command。它固定保持 `manual_only=true` 与 `auto_apply=false`，不嵌入 event JSON 正文、HTML 正文、Markdown 正文、source text、diff body、学习者答案、Agent endpoint、Agent metadata 或 model key。

`python3 scripts/verify_cognitive_loop_repair_plan.py --check` 会验证 clean / bad fixtures，并输出 `cognitive-loop-repair-plan-verification-v1`。

## Artifact Index / Artifact 入口页

`python3 scripts/cognitive_loop_cli.py artifact-index --html` creates a static local entry page for Cognitive Loop artifacts. It scans local `.cognitive-loop/events/` and `.cognitive-loop/artifacts/` files, records paths, relative links, sizes, SHA-256 hashes, and public JSON metadata such as schema/status/id fields. It does not embed artifact contents or start a server.

This is intentionally smaller than the planned full HTML Artifact console. It is a local navigation shell for operators and platform Agents, not a realtime watcher, Mastra runtime, or standalone web app.

`python3 scripts/verify_cognitive_loop_artifact_index.py --check` verifies the generated static index, relative links, unsafe-path rejection, and privacy boundary, and emits `cognitive-loop-artifact-index-verification-v1`.

`python3 scripts/cognitive_loop_cli.py artifact-index --html` 会创建一个静态本地 artifact 入口页。它扫描本地 `.cognitive-loop/events/` 和 `.cognitive-loop/artifacts/` 文件，只记录 path、相对链接、size、SHA-256 hash，以及 schema/status/id 这类公开 JSON metadata；不会嵌入 artifact 正文，也不会启动服务。

这和计划中的完整 HTML Artifact console 故意保持区别：它只是给操作者和平台 Agent 使用的本地导航壳，不是实时 watcher、Mastra runtime，也不是独立 Web App。

`python3 scripts/verify_cognitive_loop_artifact_index.py --check` 会验证静态入口页、相对链接、unsafe path 拒绝和隐私边界，并输出 `cognitive-loop-artifact-index-verification-v1`。

## Artifact Console Lite / Artifact Console Lite

`python3 scripts/cognitive_loop_artifact_console.py build --html --json` creates a static metadata-only console under `.cognitive-loop/artifacts/console/`. It aggregates Event Store rows, watcher runner summaries, Study Adapter artifact links, DecisionCard, Human Gate, LoopRun, Evolution Chain artifact refs, and artifact-health metadata into `index.html` and `manifest.json`.

This console is larger than the Artifact Index but still smaller than the planned realtime HTML console. It is an offline operator surface for platform Agents and maintainers, not a daemon, not a standalone web app, and not an SSE/WebSocket UI. Every section records provenance and redaction evidence, and the manifest keeps privacy flags for event JSON bodies, HTML/Markdown bodies, source text, raw diffs, test output, learner answers, Agent endpoints, Agent metadata, prompts, and model keys set to false.

`python3 scripts/verify_cognitive_loop_artifact_console.py --check` verifies empty project rendering, runner-lite Event Store aggregation, Study Adapter artifact links, Evolution Chain aggregation, missing Evolution artifact degradation, blocked replay preservation, invalid/secret/raw-diff/privacy-regression/policy-weakening rejection, mobile/narrow-screen HTML structure, and privacy boundaries. It emits `cognitive-loop-artifact-console-verification-v1`.

`python3 scripts/cognitive_loop_artifact_console.py build --html --json` 会在 `.cognitive-loop/artifacts/console/` 下创建静态 metadata-only console。它把 Event Store rows、watcher runner summary、Study Adapter artifact link、DecisionCard、Human Gate、LoopRun、Evolution Chain artifact refs 和 artifact-health metadata 汇总为 `index.html` 和 `manifest.json`。

这个 console 比 Artifact Index 更聚合，但仍小于计划中的实时 HTML console。它是给平台 Agent 和维护者使用的离线操作界面，不是 daemon，不是独立 Web App，也不是 SSE/WebSocket UI。每个 section 都记录 provenance 和 redaction evidence，并且 manifest 会把 event JSON 正文、HTML/Markdown 正文、source text、raw diff、test output、学习者答案、Agent endpoint、Agent metadata、prompt 和 model key 的隐私标记保持为 false。

`python3 scripts/verify_cognitive_loop_artifact_console.py --check` 会验证空项目渲染、runner-lite Event Store 聚合、Study Adapter artifact 链接、Evolution Chain 聚合、缺失 Evolution artifact 降级、blocked replay 保留、invalid/secret/raw-diff/privacy-regression/policy-weakening 拒绝、移动端/窄屏 HTML 结构和隐私边界，并输出 `cognitive-loop-artifact-console-verification-v1`。

## Personal Plugin Mode Lite / Personal Plugin Mode Lite

`python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json` creates read-only metadata-only learning artifacts for a file, README, webpage metadata record, or diff summary. The output schema is `cognitive-loop-personal-plugin-mode-v1` and includes target metadata, Study Cards, quiz items, report references, provenance, and privacy flags.

`python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --check` verifies file, README, webpage metadata, and diff summary targets; JSON/HTML/Markdown report structure; read-only/no-write behavior; missing target handling; secret-looking target rejection; raw diff body rejection; and privacy flags for raw source text, raw diff bodies, learner answers, Agent endpoints, Agent metadata, prompts, model keys, model calls, and daemons. It emits `cognitive-loop-personal-plugin-mode-verification-v1`.

`python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json` 会为文件、README、网页 metadata 记录或 diff summary 创建只读、metadata-only 的学习 artifact。输出 schema 是 `cognitive-loop-personal-plugin-mode-v1`，包含目标 metadata、Study Cards、quiz items、报告引用、provenance 和 privacy flags。

`python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --check` 会验证文件、README、网页 metadata、diff summary 四类目标，JSON/HTML/Markdown 报告结构，只读/no-write 行为，缺失目标处理，疑似 secret 目标拒绝，raw diff body 拒绝，以及源正文、raw diff body、学习者答案、Agent endpoint、Agent metadata、prompt、model key、model call 和 daemon 的隐私标记，并输出 `cognitive-loop-personal-plugin-mode-verification-v1`。

## Evolution Report Lite / Evolution Report Lite

`python3 scripts/cognitive_loop_evolution.py build --html --json` creates a read-only governed improvement artifact from metadata-only evidence and bounded failure summaries. The output schema is `cognitive-loop-evolution-report-lite-v1` and includes evidence summaries, failure clusters, root-cause hypotheses, proposed improvements, Human Mastery Gate state, regression plan, next-loop success metric, and a validated `EvolutionReport`.

`python3 scripts/verify_cognitive_loop_evolution_report.py --check` verifies successful clustering, root-cause generation, high-risk gate requirements, empty or missing evidence degradation, secret-looking evidence rejection, diff body rejection, policy-weakening rejection, JSON/HTML report structure, and privacy boundaries. It emits `cognitive-loop-evolution-report-verification-v1`.

`python3 scripts/cognitive_loop_evolution.py build --html --json` 会基于 metadata-only evidence 和有边界的 failure summary 创建只读的受治理改进 artifact。输出 schema 是 `cognitive-loop-evolution-report-lite-v1`，包含 evidence summary、failure cluster、root-cause hypothesis、改进建议、Human Mastery Gate 状态、回归计划、下一轮成功指标，以及通过校验的 `EvolutionReport`。

`python3 scripts/verify_cognitive_loop_evolution_report.py --check` 会验证成功聚类、root-cause 生成、高风险 gate 要求、空或缺失 evidence 降级、疑似 secret evidence 拒绝、diff body 拒绝、policy 弱化拒绝、JSON/HTML 报告结构和隐私边界，并输出 `cognitive-loop-evolution-report-verification-v1`。

## Governed Apply Plan Lite / Governed Apply Plan Lite

`python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json` creates a dry-run apply plan from low-risk metadata-only Evolution proposals. The output schema is `cognitive-loop-apply-plan-lite-v1`; an explicit `--apply --allow-generated-artifacts` writes only an idempotent `cognitive-loop-apply-receipt-lite-v1` receipt/marker under `.cognitive-loop/artifacts/applied/`.

`python3 scripts/verify_cognitive_loop_apply_plan.py --check` verifies dry-run output, explicit generated-artifact receipt apply, required allow flag, idempotent receipt, medium/high-risk and Human Mastery Gate rejection, forbidden target path rejection, secret-looking proposal rejection, diff body rejection, policy-weakening rejection, JSON/HTML report structure, and privacy boundaries. It emits `cognitive-loop-apply-plan-verification-v1`.

`python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json` 会从低风险、metadata-only 的 Evolution proposal 创建 dry-run apply plan。输出 schema 是 `cognitive-loop-apply-plan-lite-v1`；只有显式传入 `--apply --allow-generated-artifacts` 时，才会在 `.cognitive-loop/artifacts/applied/` 下写入幂等的 `cognitive-loop-apply-receipt-lite-v1` receipt/marker。

`python3 scripts/verify_cognitive_loop_apply_plan.py --check` 会验证 dry-run 输出、显式 generated-artifact receipt apply、必须带 allow flag、receipt 幂等、中高风险与 Human Mastery Gate 拒绝、禁止目标路径拒绝、疑似 secret proposal 拒绝、diff body 拒绝、policy 弱化拒绝、JSON/HTML 报告结构和隐私边界，并输出 `cognitive-loop-apply-plan-verification-v1`。

## Measured Improvement Comparator Lite / Measured Improvement Comparator Lite

`python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json` compares metadata-only loop artifacts. The output schema is `cognitive-loop-improvement-comparison-lite-v1` and includes per-artifact metrics, deltas, status classification, guardrails, privacy flags, and JSON/HTML output references.

`python3 scripts/verify_cognitive_loop_improvement_comparator.py --check` verifies improved, regressed, unchanged, insufficient, and ambiguous classifications; malformed JSON rejection; invalid schema rejection; secret-looking artifact rejection; diff body rejection; policy-weakening rejection; privacy regression detection; JSON/HTML report structure; and read-only boundaries. It emits `cognitive-loop-improvement-comparison-verification-v1`.

`python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json` 会比较 metadata-only loop artifacts。输出 schema 是 `cognitive-loop-improvement-comparison-lite-v1`，包含每个 artifact 的 metrics、delta、状态分类、guardrails、privacy flags，以及 JSON/HTML 输出引用。

`python3 scripts/verify_cognitive_loop_improvement_comparator.py --check` 会验证 improved、regressed、unchanged、insufficient、ambiguous 分类；malformed JSON 拒绝；invalid schema 拒绝；疑似 secret artifact 拒绝；diff body 拒绝；policy 弱化拒绝；privacy regression 检测；JSON/HTML 报告结构；以及只读边界，并输出 `cognitive-loop-improvement-comparison-verification-v1`。

## Patch Proposal Lite / Patch Proposal Lite

`python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json` creates a read-only patch proposal artifact from metadata-only Evolution Report, Apply Plan, Improvement Comparison, or verification evidence. The output schema is `cognitive-loop-patch-proposal-lite-v1` and includes `PatchProposal` candidates, manual-only candidates, degraded sources, coverage for `prompt`, `policy`, `eval`, `task`, `doc`, and `retrieval`, guardrails, privacy flags, and JSON/HTML output references.

`python3 scripts/verify_cognitive_loop_patch_proposal.py --check` verifies low-risk proposal generation, six-category coverage, mixed manual-only handling, high-risk and Human Mastery Gate degradation, forbidden path degradation, insufficient comparison degradation, secret-like proposal rejection, raw diff rejection, policy-weakening rejection, invalid schema rejection, JSON/HTML report structure, and read-only privacy boundaries. It emits `cognitive-loop-patch-proposal-verification-v1`.

`python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json` 会基于 metadata-only Evolution Report、Apply Plan、Improvement Comparison 或 verification evidence 创建只读 patch proposal artifact。输出 schema 是 `cognitive-loop-patch-proposal-lite-v1`，包含 `PatchProposal` candidates、manual-only candidates、degraded sources、`prompt`、`policy`、`eval`、`task`、`doc`、`retrieval` 六类覆盖、guardrails、privacy flags，以及 JSON/HTML 输出引用。

`python3 scripts/verify_cognitive_loop_patch_proposal.py --check` 会验证低风险 proposal 生成、六类覆盖、混合 manual-only 处理、高风险与 Human Mastery Gate 降级、禁止路径降级、证据不足 comparison 降级、疑似 secret proposal 拒绝、raw diff 拒绝、policy 弱化拒绝、invalid schema 拒绝、JSON/HTML 报告结构和只读隐私边界，并输出 `cognitive-loop-patch-proposal-verification-v1`。

## Mastra Evolution Receipt Link Lite / Mastra Evolution Receipt Link Lite

`python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json` creates a read-only Mastra evolution receipt link artifact from metadata-only Evolution Report, Apply Plan, Improvement Comparison, and Patch Proposal evidence. The output schema is `cognitive-loop-mastra-evolution-receipt-link-v1` and includes `EvolutionReceiptLink` artifact links, planned workflow steps, missing roles, degraded reasons, blockers, guardrails, privacy flags, and JSON/HTML output references.

`python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check` verifies complete four-artifact linkage, single-artifact degradation, insufficient comparison degradation, high-risk ungated blocking, manual-only Patch Proposal blocking, unsupported schema rejection, secret-like rejection, raw diff rejection, policy-weakening rejection, privacy flag regression blocking, JSON/HTML report structure, and read-only privacy boundaries. It emits `cognitive-loop-mastra-evolution-receipt-verification-v1`.

`python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json` 会基于 metadata-only Evolution Report、Apply Plan、Improvement Comparison 和 Patch Proposal evidence 创建只读 Mastra evolution receipt link artifact。输出 schema 是 `cognitive-loop-mastra-evolution-receipt-link-v1`，包含 `EvolutionReceiptLink` artifact links、计划 workflow steps、missing roles、degraded reasons、blockers、guardrails、privacy flags，以及 JSON/HTML 输出引用。

`python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check` 会验证完整四件套链接、单件 artifact 降级、证据不足 comparison 降级、高风险未 gate 阻断、manual-only Patch Proposal 阻断、unsupported schema 拒绝、疑似 secret 拒绝、raw diff 拒绝、policy weakening 拒绝、privacy flag 回归阻断、JSON/HTML 报告结构和只读隐私边界，并输出 `cognitive-loop-mastra-evolution-receipt-verification-v1`。

## Mastra Evolution Workflow Replay Lite / Mastra Evolution Workflow Replay Lite

`python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json` creates a read-only replay transcript from a metadata-only `EvolutionReceiptLink`. The output schema is `cognitive-loop-mastra-evolution-workflow-replay-v1` and includes `MastraEvolutionWorkflowReplay` source receipt metadata, workflow steps, gate actions, replay summary, operator next commands, guardrails, privacy flags, and JSON/HTML output references.

`python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check` verifies ready, degraded, and blocked receipt replay; invalid schema rejection; unsupported status rejection; ready-with-missing-roles rejection; high-risk ungated rejection; manual-only patch rejection; privacy flag regression rejection; secret-like rejection; raw diff rejection; policy-weakening rejection; JSON/HTML report structure; and read-only privacy boundaries. It emits `cognitive-loop-mastra-evolution-replay-verification-v1`.

`python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json` 会基于 metadata-only `EvolutionReceiptLink` 创建只读 replay transcript。输出 schema 是 `cognitive-loop-mastra-evolution-workflow-replay-v1`，包含 `MastraEvolutionWorkflowReplay` source receipt metadata、workflow steps、gate actions、replay summary、operator next commands、guardrails、privacy flags，以及 JSON/HTML 输出引用。

`python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check` 会验证 ready、degraded、blocked receipt replay；invalid schema 拒绝；unsupported status 拒绝；ready 但缺少 required roles 拒绝；高风险未 gate 拒绝；manual-only patch 拒绝；privacy flag 回归拒绝；疑似 secret 拒绝；raw diff 拒绝；policy weakening 拒绝；JSON/HTML 报告结构和只读隐私边界，并输出 `cognitive-loop-mastra-evolution-replay-verification-v1`。

## Public Objects

### `ProjectEvent`

Normalized event from file changes, git diffs, CI, runtime logs, human actions, or Agent tool calls.

来自文件变化、git diff、CI、运行时日志、人类动作或 Agent 工具调用的标准化事件。

Required fields:

- `event_id`
- `project_id`
- `actor`
- `event_type`
- `summary`
- `timestamp`

### `DecisionCard`

Evidence-bound decision record with impact, risk, verification, human gate, and rollback plan.

绑定证据的决策记录，包含影响、风险、验证、人类门禁和回滚计划。

Required fields:

- `decision_id`
- `project_id`
- `title`
- `status`
- `summary`
- `event_ids`
- `evidence_refs`
- `risk`
- `human_mastery_gate`
- `verification`
- `rollback`

High or blocked risk decisions must set `human_mastery_gate.required: true`.

高风险或阻塞风险的决策必须设置 `human_mastery_gate.required: true`。

### `LoopRun`

One bounded execution cycle with status, event refs, decision refs, trace refs, artifact refs, and verification status.

一次有边界的执行循环，包含状态、事件引用、决策引用、trace 引用、artifact 引用和验证状态。

### `MasteryRecord`

Human understanding state for a topic, file, subsystem, or risky change.

人类对某个主题、文件、子系统或风险变更的理解状态。

### `EvolutionReport`

Governed proposal for improving prompts, policies, evals, docs, tasks, retrieval rules, or learning paths.

对 prompt、policy、eval、文档、任务、检索规则或学习路径的受治理改进提案。

### `ImprovementComparison`

Read-only comparison of metadata-only loop artifacts showing whether the latest loop improved, regressed, stayed unchanged, lacks enough evidence, or needs manual review.

只读比较 metadata-only loop artifacts，用来判断最新 loop 是改进、退化、无变化、证据不足，还是需要人工复核。

### `PatchProposal`

Read-only patch specification covering prompt, policy, eval, task, doc, and retrieval categories. It records target path, intent, verification commands, risk level, and manual-only reasons, but never embeds raw unified diffs or applies changes.

只读补丁规格，覆盖 prompt、policy、eval、task、doc 和 retrieval 六类。它记录 target path、intent、验证命令、risk level 和 manual-only 原因，但不嵌入 raw unified diff，也不执行变更。

### `EvolutionReceiptLink`

Metadata-only linkage record that connects Evolution Report, Apply Plan, Improvement Comparison, and Patch Proposal evidence into a future Mastra workflow receipt DTO. It records artifact roles, workflow-step intent, degraded reasons, blockers, guardrails, and privacy flags, but never starts Mastra, calls models, executes apply, embeds raw diffs, or modifies source files.

只含 metadata 的链接记录，用来把 Evolution Report、Apply Plan、Improvement Comparison 和 Patch Proposal evidence 接成未来 Mastra workflow receipt DTO。它记录 artifact role、workflow-step 意图、degraded reasons、blockers、guardrails 和 privacy flags，但不启动 Mastra、不调用模型、不执行 apply、不嵌入 raw diff，也不修改源码。

### `MastraEvolutionWorkflowReplay`

Metadata-only replay transcript that maps an `EvolutionReceiptLink` into future Mastra workflow steps. It records source receipt status, workflow steps, gate actions, manual review or blocked reasons, operator next commands, guardrails, and privacy flags, but never starts production Mastra, calls models, executes apply, embeds raw diffs, or modifies source files.

只含 metadata 的 replay transcript，用来把 `EvolutionReceiptLink` 映射为未来 Mastra workflow steps。它记录 source receipt status、workflow steps、gate actions、manual review 或 blocked reasons、operator next commands、guardrails 和 privacy flags，但不启动生产 Mastra、不调用模型、不执行 apply、不嵌入 raw diff，也不修改源码。

## Privacy Boundary

Public Cognitive Loop contracts must not contain:

- raw source text;
- learner answers;
- grading feedback;
- generated private insights;
- Agent endpoints;
- raw Agent metadata;
- model keys, judge keys, API keys, bearer tokens, or other secrets.

公开 Cognitive Loop contract 不能包含：

- 原始 source text；
- 学习者答案；
- 评分反馈；
- 私有生成洞察；
- Agent endpoint；
- 原始 Agent metadata；
- 模型 key、judge key、API key、bearer token 或其他密钥。

## Current Limit

This bootstrap does not start a runtime, watch files, invoke Mastra, call Langfuse, or render the final realtime HTML console. It only makes the next runtime work safer by giving it stable local contracts, a verifier, and a static local artifact path.

这个 bootstrap 不会启动 runtime，不监听文件，不调用 Mastra，不调用 Langfuse，也不渲染最终实时 HTML console。它只通过稳定的本地契约、verifier 和静态本地 artifact 路径，让下一步 runtime 工作更安全。
