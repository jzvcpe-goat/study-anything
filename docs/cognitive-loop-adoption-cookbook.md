# Cognitive Loop Adoption Cookbook / 认知自循环接入手册

This cookbook is the short operating path for Kimi, Codex, WorkBuddy-style agents, and private
platform agents that use Study Anything as the local Learning Adapter inside the Cognitive Loop
System rather than a standalone frontend.

这份手册面向 Kimi、Codex、WorkBuddy 类工作区 Agent，以及私有平台 Agent。目标是让平台 Agent
把 Study Anything 当作 Cognitive Loop System 的本地 Learning Adapter 使用，而不是把它当成一个独立
前端 App。

## Operating Split / 分工

| Layer | Owns | Does not own |
| --- | --- | --- |
| Platform Agent / 平台 Agent | User conversation, browser, files, apps, video slices, external data, model credentials. | Cognitive Loop state integrity or local evidence retention. |
| Study Anything Learning Adapter | Source-bound learning loops, mastery, scribe logs, Agent audit, eval evidence, exports. | Browser automation, real model keys, paid hosted accounts, or a standalone frontend. |
| Cognitive Loop local artifacts | DecisionCards, LoopRuns, snapshots, gates, bundles, event indexes, doctor reports, repair plans, artifact index pages. | Raw source text, diff bodies, learner answers, Agent endpoints, or model secrets. |

## Path 1: First Adoption / 路径一：首次接入

Use this when an operator wants to prove the local-first path works before adding real model keys.

当操作者想先证明本地路径可用，再接入真实模型密钥时使用。

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

Acceptance evidence:

- `adoption-proof-v1`
- `ecosystem-submission-verification-v1`
- no standalone frontend requirement
- no Study Anything custody of real model keys

验收证据：

- `adoption-proof-v1`
- `ecosystem-submission-verification-v1`
- 不要求独立前端
- Study Anything 不托管真实模型密钥

## Path 2: Daily Project Review / 路径二：日常项目审查

Use this when a platform Agent has changed files, gathered new material, or needs to explain current
project state without embedding private content into reports.

当平台 Agent 修改了文件、收集了新材料，或者需要解释当前项目状态但不能把私有内容嵌入报告时使用。

```bash
python3 scripts/cognitive_loop_cli.py init
python3 scripts/cognitive_loop_cli.py snapshot --html
python3 scripts/cognitive_loop_cli.py run-once --html
python3 scripts/cognitive_loop_cli.py index --html
python3 scripts/cognitive_loop_cli.py artifact-index --html
```

Operator output:

- open `.cognitive-loop/artifacts/cognitive-loop-artifact-index.html`
- use linked static HTML artifacts for review
- copy only artifact paths, hashes, schema versions, status, and next commands into the platform chat

操作者输出：

- 打开 `.cognitive-loop/artifacts/cognitive-loop-artifact-index.html`
- 通过其中的静态 HTML 链接审查证据
- 只把 artifact 路径、hash、schema version、status 和 next command 复制给平台对话

## Path 3: Risk Decision / 路径三：风险决策

Use this when the Agent proposes a risky change, a release, a merge, a plugin install, or any action
that should wait for explicit human approval.

当 Agent 提议高风险改动、发布、合并、插件安装，或任何需要人类明确批准的操作时使用。

```bash
python3 scripts/cognitive_loop_cli.py report --html
python3 scripts/cognitive_loop_cli.py gate --reject --html --reason "Needs human review"
python3 scripts/cognitive_loop_cli.py doctor --html
python3 scripts/cognitive_loop_cli.py repair-plan --html
python3 scripts/cognitive_loop_cli.py artifact-index --html
```

Use `--approve` only after the human has explicitly approved the decision in the current workflow.
The repair plan is manual-only: it suggests commands and next actions but does not execute file
changes.

只有在人类已经在当前工作流中明确批准后，才使用 `--approve`。repair plan 是 manual-only：它只提供
命令和下一步建议，不执行文件修改。

## Path 4: Learning Handoff / 路径四：学习交接

Use this when the user is learning a repo, document, video slice, or project decision through Kimi,
Codex, or another platform Agent.

当用户通过 Kimi、Codex 或其他平台 Agent 学习一个 repo、文档、视频切片或项目决策时使用。

```bash
./scripts/run_skill_mode_demo.sh
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
```

After a real learning session, fetch these redacted artifacts:

- `agent-audit`
- `agent-eval/artifact`
- `agent-eval/quality`
- `agent-eval/report`
- Obsidian export
- NotebookLM-style learning package
- second-brain handoff

真实学习会话完成后，获取这些脱敏产物：

- `agent-audit`
- `agent-eval/artifact`
- `agent-eval/quality`
- `agent-eval/report`
- Obsidian export
- NotebookLM-style learning package
- second-brain handoff

## Platform Prompts / 平台 Agent 提示词

English:

```text
Use Study Anything as a local Learning Adapter. Do not ask it to browse, store model keys, or replace
the platform Agent. Run the Cognitive Loop commands, inspect only redacted artifact metadata, and
summarize status, risks, next commands, and human approval requirements.
```

Chinese:

```text
把 Study Anything 当成本地 Learning Adapter 使用。不要让它负责浏览器、真实模型密钥，或替代平台
Agent。运行 Cognitive Loop 命令，只检查脱敏 artifact metadata，并总结状态、风险、下一步命令和是否需要
人类批准。
```

## Privacy Boundary / 隐私边界

Do not paste these into Kimi, Codex, WorkBuddy, support tickets, or public issues:

- raw source text
- diff bodies or file contents
- learner answers
- grading feedback
- generated private insights
- Agent endpoints or raw Agent metadata
- API keys, judge keys, or model secrets
- browser, video, app, or personal private context

不要把以下内容粘贴到 Kimi、Codex、WorkBuddy、support ticket 或公开 issue 中：

- 原始 source text
- diff body 或文件全文
- learner answers
- grading feedback
- 私有 insight
- Agent endpoint 或 raw Agent metadata
- API key、judge key 或模型密钥
- 浏览器、视频、应用或个人私有上下文

## Quick Acceptance / 快速验收

```bash
python3 scripts/verify_cognitive_loop_contracts.py --check
python3 scripts/verify_cognitive_loop_artifact_index.py --check
python3 scripts/verify_cognitive_loop_adoption_cookbook.py --check
python3 scripts/generate_platform_bundle_manifest.py --check
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_ecosystem_submission_pack.py
```

This cookbook documents the current local-first artifact workflow. Mastra runtime, watcher daemon,
and a realtime HTML console remain planned layers, not shipped requirements.

这份手册记录的是当前本地优先 artifact 工作流。Mastra runtime、watcher daemon 和实时 HTML console
仍是计划中的层，不是当前已上线要求。
