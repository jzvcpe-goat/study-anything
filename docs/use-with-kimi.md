# Use Study Anything With Kimi

Study Anything works best when Kimi remains the user-facing Agent and Study
Anything acts as the local learning engine. Kimi can gather context, call tools,
and explain results; Study Anything validates learning context, runs the
learning workflow, and returns redacted audit/eval/export artifacts.

## Mode 1: Copy-Only

Use this when Kimi cannot call local HTTP tools.

1. Paste source or bounded excerpts into Kimi.
2. Ask Kimi to produce a `learning-context-package-v1`.
3. Validate it locally:

```bash
python3 scripts/study_anything_cli.py context-validate package.json
python3 scripts/study_anything_cli.py context-import package.json --session
```

This mode is lowest friction, but Kimi is not directly invoking Study Anything.

## Mode 2: HTTP Tool Mode

Use this when Kimi Work or a Kimi-compatible platform can import HTTP tools.

1. Start Study Anything:

```bash
./scripts/launch_skill_mode.sh
```

2. Import the constrained tool contract:

```text
platform/generated/study-anything-platform-openapi.json
platform/generated/study-anything-openai-tools.json
```

3. Let Kimi call the platform tools:

- `study_anything_create_session`
- `study_anything_validate_context_package`
- `study_anything_add_enrichment`
- `study_anything_teaching_layers`
- `study_anything_run`
- `study_anything_answer`
- `study_anything_agent_audit`
- `study_anything_enrichment_artifact_export`
- `study_anything_obsidian_export`
- `study_anything_learning_package_export`

This mode is the preferred early ecosystem path because it keeps the UX inside
Kimi while Study Anything remains local-first.

## Mode 3: Local Agent Gateway

Use this when you want Study Anything's learning Agent tasks to run through your
own Kimi-compatible local gateway.

```bash
export AGENT_LLM_BASE_URL="https://api.moonshot.cn/v1"
export AGENT_LLM_API_KEY="$MOONSHOT_API_KEY"
export AGENT_LLM_MODEL="${AGENT_LLM_MODEL:-kimi-k2.6}"

python3 scripts/openai_compatible_agent_gateway.py \
  --host 127.0.0.1 \
  --port 8787
```

Then register it:

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My Kimi gateway" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default
```

Kimi or the platform Agent still owns browsing, files, external data, and video
slice creation. The local gateway owns model credentials and reasoning. Study
Anything owns learning state, validation, audit, eval, and redacted exports.

## What To Commercialize Later

Do not sell a separate app before adoption is real. The early commercial
surface should be convenience and trust:

- hosted sync and backup for learning state;
- team workspaces and shared courses;
- trusted plugin/importer ecosystem;
- managed platform packs and integration support.

The open-source core stays useful without accounts, billing, hosted storage, or
real model keys inside Study Anything.
