# Use Study Anything With WorkBuddy / CodeBuddy

This is the beginner path for using Study Anything inside WorkBuddy or
CodeBuddy. Treat WorkBuddy/CodeBuddy as the main Agent. It owns real model
choice, browsing, external tools, files, and private credentials. Study Anything
is the local learning engine.

## 0. What You Are Installing

You are installing a CodeBuddy/WorkBuddy plugin wrapper. It gives the Agent four
commands and one skill:

- `/study-anything:start`
- `/study-anything:learn`
- `/study-anything:diagnose`
- `/study-anything:export`
- `/study-anything:study-anything`

It still calls your local or private Study Anything runtime. It does not contain
model API keys.

## 1. Add The Marketplace

In CodeBuddy/WorkBuddy:

```text
/plugin marketplace add jzvcpe-goat/study-anything
```

For local development from a cloned repo:

```text
/plugin marketplace add ./path/to/study-anything
```

Then install:

```text
/plugin install study-anything@study-anything
```

Check that the marketplace is visible:

```text
/plugin marketplace list
```

## 2. Start Study Anything Locally

In a terminal:

```bash
cd /path/to/study-anything
./START_HERE.command
```

If you prefer explicit commands:

```bash
./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py health
```

If your platform cannot keep background processes alive, run the bounded demo:

```bash
./scripts/run_skill_mode_demo.sh
```

## 3. Import HTTP Tools

If WorkBuddy/CodeBuddy can import OpenAPI tools, import:

```text
platform/generated/study-anything-platform-openapi.json
```

Default API base:

```text
http://127.0.0.1:8000
```

If localhost is blocked, expose Study Anything through a private endpoint you
control and point the imported tools at that endpoint.

## 4. Run The First Learning Flow

In WorkBuddy/CodeBuddy, ask:

```text
/study-anything:learn Rust ownership basics
```

Then paste a short source passage when asked. The Agent should create a Study
Anything session, request overview and glossary layers, ask or grade an answer,
and return mastery evidence.

CLI fallback:

```bash
python3 scripts/study_anything_cli.py start \
  --title "Rust ownership basics" \
  --text "Rust uses ownership and borrowing to make memory safety a compile-time property." \
  --reference "rust-book-note"

python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer overview
python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer glossary
python3 scripts/study_anything_cli.py answer <SESSION_ID> --text "Ownership controls who can use and free a value."
python3 scripts/study_anything_cli.py mastery <SESSION_ID>
```

## 5. Diagnose Failures

Run:

```text
/study-anything:diagnose
```

Or in terminal:

```bash
python3 scripts/study_anything_cli.py health
python3 scripts/diagnose_adoption.py
python3 scripts/verify_workbuddy_plugin_marketplace.py --check
```

Common failures:

- API unreachable: run `./START_HERE.command`.
- Localhost blocked: use a private reachable endpoint.
- OpenAPI import rejected: verify the JSON file and try the CLI fallback.
- Python dependency download slow: set `PIP_INDEX_URL` or retry from a normal terminal.
- Model key missing: configure it in WorkBuddy/CodeBuddy or your private Agent, not in Study Anything.

## 6. Export Learning Evidence

Use:

```text
/study-anything:export
```

The export should contain compact session, source reference, mastery, schema,
and redacted audit/eval evidence. It must not contain real model keys, Agent
endpoint secrets, raw source text, learner answers, grading feedback, or private
browser/app/video context.

## 中文速通

1. 在 CodeBuddy/WorkBuddy 里添加市场：

```text
/plugin marketplace add jzvcpe-goat/study-anything
```

2. 安装插件：

```text
/plugin install study-anything@study-anything
```

3. 在本地启动 Study Anything：

```bash
./START_HERE.command
```

4. 如果平台支持 OpenAPI 工具导入，导入：

```text
platform/generated/study-anything-platform-openapi.json
```

5. 在 WorkBuddy/CodeBuddy 里说：

```text
/study-anything:learn 我想学习这段材料
```

真实模型、浏览器和外部工具由 WorkBuddy/CodeBuddy 管；Study Anything 只负责本地学习流程、
测验、掌握度、审计证据和导出。

