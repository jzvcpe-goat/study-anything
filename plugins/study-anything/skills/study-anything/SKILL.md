---
name: study-anything
description: Use when CodeBuddy or WorkBuddy should run a source-bound learning workflow for requests like system learning, interview preparation, help me master this topic, build a study plan, quiz me, or review this material. Prefer the WorkBuddy inline flow where WorkBuddy owns real model/search/file/context work and Study Anything records learning state, mastery, evidence, and exports. Use OpenAPI/local HTTP only as fallback. Do not store model keys in Study Anything.
---

# Study Anything For CodeBuddy/WorkBuddy

Study Anything is the learning workflow kernel. CodeBuddy/WorkBuddy remains the
main platform Agent: it owns real model credentials, browsing, external apps,
files, visualization, and private tool use. Study Anything owns local learning
workflow integrity, source binding, hidden session refs, mastery, audit/eval
evidence, and exports.

## Trigger Phrases

Use this skill when the user says things like:

- "systematically teach me ..."
- "prepare me for an interview ..."
- "help me master this topic"
- "build a study plan"
- "quiz me on this material"
- "review this source and turn it into learning cards"

## Default Inline Flow

1. WorkBuddy collects source material, user context, and any visual/search/file context.
2. WorkBuddy uses its own model to produce teaching claims, glossary terms, quiz items, and grading feedback.
3. Call Study Anything inline:

```bash
python3 scripts/workbuddy_learning_flow.py run --input workbuddy-learning-input.json --output workbuddy-learning-output.json --markdown study-card.md
```

4. Keep `session_ref` in hidden WorkBuddy context. Do not ask the user to manage it.
5. Return the teaching summary, quiz, feedback, mastery, and export options conversationally.

Validate the inline path:

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
```

The inline path does not start uvicorn, bind localhost, require a background
process, or ask for real model API keys.

## HTTP Fallback

Use HTTP only when the workspace can reliably reach a local or private endpoint.
From the Study Anything checkout:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If a background server will not persist in this host, use the bounded demo:

```bash
./scripts/run_skill_mode_demo.sh
```

Use `STUDY_ANYTHING_API_BASE` or `--api-base` when the fallback runtime is not at
`http://127.0.0.1:8000`.

## Tool Contract

Fallback WorkBuddy/CodeBuddy import asset:

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
