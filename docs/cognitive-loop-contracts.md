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
```

The repository also includes a small local CLI:

```bash
python3 scripts/cognitive_loop_cli.py init
python3 scripts/cognitive_loop_cli.py verify
python3 scripts/cognitive_loop_cli.py report --html
python3 scripts/cognitive_loop_cli.py run-once --html
python3 scripts/cognitive_loop_cli.py snapshot --html
python3 scripts/cognitive_loop_cli.py gate --approve --html
```

This CLI is for repo-local contract bootstrap and a static HTML DecisionCard artifact. It is not a daemon, does not watch files, does not call Mastra, does not call a model, and does not require a standalone frontend.

仓库也包含一个小型本地 CLI：

```bash
python3 scripts/cognitive_loop_cli.py init
python3 scripts/cognitive_loop_cli.py verify
python3 scripts/cognitive_loop_cli.py report --html
python3 scripts/cognitive_loop_cli.py run-once --html
python3 scripts/cognitive_loop_cli.py snapshot --html
python3 scripts/cognitive_loop_cli.py gate --approve --html
```

这个 CLI 用于本地契约初始化和静态 HTML DecisionCard artifact。它不是 daemon，不监听文件，不调用 Mastra，不调用模型，也不要求独立前端。

The verifier emits `cognitive-loop-contract-bootstrap-v1` and proves:

- all four `.cognitive-loop` files exist and use the expected schema versions;
- default mode is read-only;
- real model keys and Agent endpoints stay outside Study Anything;
- raw source text is forbidden in public contracts;
- required evals include the Cognitive Loop contract verifier and CLI artifact verifier;
- required evals include the Cognitive Loop run-once evidence verifier;
- required evals include the Cognitive Loop project snapshot verifier;
- required evals include the Cognitive Loop Human Mastery Gate verifier;
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
