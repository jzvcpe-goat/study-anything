# Study Anything CodeBuddy/WorkBuddy Plugin

This plugin lets CodeBuddy/WorkBuddy install Study Anything as a local-first
learning tool. The plugin does not contain model keys and does not call model
providers directly. CodeBuddy/WorkBuddy owns model choice, browser access,
external tools, and private credentials; Study Anything owns the local learning
loop, source-bound mastery, audit/eval evidence, and exports.

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

- `/study-anything:start` starts or verifies the local runtime.
- `/study-anything:learn` turns pasted material into a source-bound learning loop.
- `/study-anything:diagnose` checks local runtime, endpoints, and plugin assets.
- `/study-anything:export` exports Obsidian, NotebookLM, or learning-package handoff evidence.

## Runtime

Run Study Anything from the repository checkout:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If your workspace can import OpenAPI tools, import:

```text
platform/generated/study-anything-platform-openapi.json
```

The default local API is `http://127.0.0.1:8000`.
