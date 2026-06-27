---
name: study-anything
description: Use when CodeBuddy or WorkBuddy should run a source-bound Study Anything learning loop through a local or private HTTP runtime. Start the runtime, import OpenAPI tools when available, create sessions, add reading material, request teaching layers, answer quizzes, check mastery, diagnose local setup, or export Obsidian/NotebookLM handoff evidence without storing model keys in Study Anything.
---

# Study Anything For CodeBuddy/WorkBuddy

Study Anything is the local learning engine. CodeBuddy/WorkBuddy remains the
platform Agent: it owns real model credentials, browsing, external apps, files,
and private tool use. Study Anything owns local learning workflow integrity,
source binding, mastery, audit/eval evidence, and exports.

## Start Or Verify Runtime

From the Study Anything checkout:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If a background server will not persist in this host, use the bounded demo:

```bash
./scripts/run_skill_mode_demo.sh
```

Use `STUDY_ANYTHING_API_BASE` or `--api-base` when the runtime is not at
`http://127.0.0.1:8000`.

## Tool Contract

Preferred WorkBuddy/CodeBuddy import asset:

```text
platform/generated/study-anything-platform-openapi.json
```

Fallback local HTTP flow:

```bash
python3 scripts/study_anything_cli.py start --title "Topic" --text "Source text" --reference "source"
python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer overview
python3 scripts/study_anything_cli.py answer <SESSION_ID> --text "My answer"
python3 scripts/study_anything_cli.py mastery <SESSION_ID>
```

MCP is a planned extension point in this repository, not a shipped runtime in
this plugin. Do not claim MCP support until an explicit MCP server is added.

## Privacy Boundary

Do not put raw private source text, learner answers, grading feedback, generated
private insights, Agent endpoints, Agent metadata, API keys, model secrets, or
browser/video/app private context into shared marketplace metadata, issue
reports, public logs, or release assets.

Study Anything may store local learning state and redacted evidence in the
operator's local runtime. It must not store real model provider keys.
