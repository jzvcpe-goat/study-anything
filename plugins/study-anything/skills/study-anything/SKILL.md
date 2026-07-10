---
name: study-anything
description: Use when CodeBuddy or WorkBuddy should run a source-bound learning workflow for requests like system learning, interview preparation, help me master this topic, build a study plan, quiz me, or review this material. Prefer the WorkBuddy inline flow where WorkBuddy owns real model/search/file/context work and Study Anything records learning state, mastery, evidence, and exports. Use OpenAPI/local HTTP only as fallback. Do not store model keys in Study Anything.
---

# Study Anything Adapter For CodeBuddy/WorkBuddy

Study Anything is the Human Reconstruction / Learning Adapter. CodeBuddy/
WorkBuddy remains the main platform Agent: it owns real model credentials,
browsing, external apps, files, visualization, and private tool use. Study
Anything owns local learning workflow integrity, source binding, hidden session
refs, mastery, audit/eval evidence, and exports.

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
2. WorkBuddy uses its own model, such as the Kimi model available inside WorkBuddy, to produce teaching claims, glossary terms, quiz items, and grading feedback.
3. Include `agent_evidence.generated_by_platform_agent=true`, `platform_agent`, and a non-demo `model_label` in `workbuddy-learning-input.json`.
4. Call Study Anything inline:

```bash
python3 scripts/workbuddy_learning_flow.py run --input workbuddy-learning-input.json --output workbuddy-learning-output.json --markdown study-card.md
```

5. Keep `session_ref` in hidden WorkBuddy context. Do not ask the user to manage it.
6. Return the teaching summary, quiz, feedback, mastery, and export options conversationally.

`demo` is only for deterministic diagnostics. Do not use demo output as the
learner-facing lesson.

Validate the inline path:

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
python3 scripts/workbuddy_learning_flow.py doctor
```

The inline path does not start uvicorn, bind localhost, require a background
process, ask for real model API keys, or require manual `env -u HTTP_PROXY`
workarounds.

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
