# Study Anything CodeBuddy/WorkBuddy Plugin

This plugin lets CodeBuddy/WorkBuddy use Study Anything as a local-first
learning workflow kernel. The default path is inline: CodeBuddy/WorkBuddy owns
model choice, browser access, external tools, files, and private credentials;
Study Anything records source-bound learning state, mastery, audit/eval
evidence, and exports. OpenAPI/local HTTP remains available as a fallback.

## Install

```text
/plugin marketplace add jzvcpe-goat/study-anything
/plugin install study-anything@study-anything
```

For local development:

```text
/plugin marketplace add ./path/to/study-anything
/plugin install study-anything@study-anything
```

## Commands

- `/study-anything:start` checks inline mode first and explains HTTP fallback.
- `/study-anything:learn` turns WorkBuddy-generated teaching, quiz, and grading into a source-bound learning package.
- `/study-anything:diagnose` checks local runtime, endpoints, and plugin assets.
- `/study-anything:export` exports Obsidian, NotebookLM, or learning-package handoff evidence.

## Default Inline Runtime

```bash
python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
```

## HTTP Fallback

If you need HTTP tools, run Study Anything from the repository checkout:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If your workspace can import OpenAPI tools, import:

```text
platform/generated/study-anything-platform-openapi.json
```

The default local API is `http://127.0.0.1:8000`. Do not use HTTP as the default
inside WorkBuddy sandboxes that do not preserve background processes.
