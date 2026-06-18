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
- required evals include the Cognitive Loop event index, artifact doctor, repair plan, and artifact index verifiers;
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
- required evals 包含 Cognitive Loop event index、artifact doctor、repair plan 和 artifact index verifier；
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
