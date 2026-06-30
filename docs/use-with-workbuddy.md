# Use Study Anything With WorkBuddy / CodeBuddy

This is the beginner path for using Study Anything inside WorkBuddy or
CodeBuddy. Treat WorkBuddy/CodeBuddy as the main Agent. It owns real model
choice, browsing, external tools, files, visualization, and private credentials.
Study Anything is the local learning workflow kernel: it records source-bound
learning state, quiz/mastery evidence, audit metadata, and exports.

## 0. The Important Change

Do **not** start with a local HTTP server in WorkBuddy.

Preferred WorkBuddy path:

```text
User asks for learning -> WorkBuddy gathers context and calls its own model
-> Study Anything inline flow records learning evidence
-> WorkBuddy continues the conversation and export flow
```

HTTP/OpenAPI remains available as fallback for hosts that can reliably reach a
local or private endpoint.

## 1. Add The Marketplace

In CodeBuddy/WorkBuddy:

```text
/plugin marketplace add jzvcpe-goat/study-anything
/plugin install study-anything@study-anything
```

For local development from a cloned repo:

```text
/plugin marketplace add ./path/to/study-anything
/plugin install study-anything@study-anything
```

Check that the marketplace is visible:

```text
/plugin marketplace list
```

## 2. Use It In Conversation

Good trigger phrases:

```text
系统学习 DeepSeek PM 面试准备
帮我掌握这段材料
建立一个学习计划
考我一下这个主题
复盘这份报告并导出 Obsidian 笔记
```

WorkBuddy should:

1. collect source material and learner context;
2. use its own model, such as the Kimi model available inside WorkBuddy, to create overview, glossary, quiz, and grading feedback;
3. call the Study Anything inline flow;
4. keep `session_ref` hidden in WorkBuddy context;
5. return a conversational learning card, quiz, feedback, mastery, and export options.

The user should not manage session ids, ports, proxy flags, or background
processes.

Do not use deterministic demo output as the learner-facing lesson. Demo mode is
only a verifier fixture. Real learning should include WorkBuddy/Kimi-generated
teaching, quiz, and grading content.

## 3. Inline Flow Contract

WorkBuddy passes a JSON file shaped like:

```text
platform/schemas/workbuddy-learning-input-v1.schema.json
```

Then runs:

```bash
python3 scripts/workbuddy_learning_flow.py run \
  --input workbuddy-learning-input.json \
  --output workbuddy-learning-output.json \
  --markdown study-card.md
```

For real learner sessions, `workbuddy-learning-input.json` must include:

```json
{
  "agent_evidence": {
    "generated_by_platform_agent": true,
    "platform_agent": "WorkBuddy",
    "model_label": "Kimi model via WorkBuddy",
    "mode": "platform_agent"
  }
}
```

If this is missing, `run` fails on purpose. That failure means WorkBuddy has not
yet used its own model to create the teaching content.

The output follows:

```text
platform/schemas/workbuddy-learning-output-v1.schema.json
```

For a deterministic diagnostic example only:

```bash
python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview
```

Verify the inline path:

```bash
python3 scripts/workbuddy_learning_flow.py doctor
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
```

This verifier proves the WorkBuddy path does not start uvicorn, bind localhost,
depend on background process persistence, require real model keys, leak raw
source probes, expose learner answers, or require manual `env -u HTTP_PROXY`
workarounds.

If WorkBuddy says the checkout is still old, run:

```bash
python3 scripts/workbuddy_learning_flow.py doctor
```

Use the doctor result to decide whether the inline feature files exist. In a
restricted WorkBuddy sandbox, do not rely on `git pull`; install the latest
plugin pack or update the checkout from a normal terminal.

## 4. What WorkBuddy Owns

WorkBuddy owns:

- real model choice and credentials;
- web search and browsing;
- file and app access;
- visualization;
- conversation context;
- private tools and external credentials.

Study Anything owns:

- learning session refs;
- source-bound claim evidence;
- quiz/mastery structure;
- audit and verifier evidence;
- Obsidian / NotebookLM / Markdown handoff contracts.

## 5. HTTP/OpenAPI Fallback

Use this only when the workspace can reliably call a local or private HTTP
endpoint.

Start fallback runtime:

```bash
./START_HERE.command
```

Or explicitly:

```bash
./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py health
```

If the host cannot keep background processes alive, use foreground mode:

```bash
./scripts/launch_skill_mode.sh --foreground
```

Import OpenAPI tools:

```text
platform/generated/study-anything-platform-openapi.json
```

Default fallback API base:

```text
http://127.0.0.1:8000
```

If localhost is blocked, expose Study Anything through a private endpoint you
control and point the imported tools at that endpoint.

## 6. Diagnose Failures

Start with inline diagnostics:

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
python3 scripts/verify_workbuddy_plugin_marketplace.py --check
```

Use HTTP diagnostics only for fallback mode:

```bash
python3 scripts/study_anything_cli.py health
python3 scripts/diagnose_adoption.py
python3 scripts/verify_platform_agent_tools.py
```

Common failures:

- Inline passes but HTTP fails: keep using inline mode in WorkBuddy.
- `run` rejects deterministic input: ask WorkBuddy/Kimi to generate teaching, quiz, and grading content first.
- Checkout looks old: run `python3 scripts/workbuddy_learning_flow.py doctor`; update outside the sandbox or reinstall the latest plugin pack.
- Localhost/proxy issues: avoid HTTP, or use a private endpoint.
- Proxy variables: inline mode sanitizes proxy environment variables automatically, so users should not need `env -u HTTP_PROXY`.
- Background process disappears: use inline mode or foreground fallback.
- Model key missing: configure it in WorkBuddy/CodeBuddy, not Study Anything.
- Python dependency download slow: retry from a normal terminal or prebuilt environment.

For CodeBuddy Code CLI headless validation, explicitly load the installed plugin
channel:

```bash
codebuddy -p \
  --channels plugin:study-anything@study-anything \
  "/study-anything:diagnose"
```

## 7. Export Learning Evidence

Inline mode writes a Markdown learning card and a JSON learning package:

```bash
python3 scripts/workbuddy_learning_flow.py run \
  --input workbuddy-learning-input.json \
  --output workbuddy-learning-output.json \
  --markdown study-card.md
```

WorkBuddy can then offer:

- import into Obsidian;
- create a NotebookLM context package;
- save a local learning archive;
- continue the quiz in conversation.

Exported evidence should include schema names, session refs, mastery state,
source references, and redacted audit/eval metadata. It must not include real
model keys, Agent endpoint secrets, raw private source text, learner answers, or
private browser/app/video context.

## 中文速通

1. 安装插件：

```text
/plugin marketplace add jzvcpe-goat/study-anything
/plugin install study-anything@study-anything
```

2. 在 WorkBuddy 里直接说：

```text
系统学习 DeepSeek PM 面试准备
```

3. WorkBuddy 负责搜索、Kimi、文件、上下文和可视化。

4. Study Anything 负责把这次学习变成可追踪的学习卡、测验、掌握度和导出证据。

5. 不需要用户启动服务器、记 session id、处理端口、处理代理或维护后台进程。
