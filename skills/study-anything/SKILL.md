---
name: study-anything
description: Operate a self-hosted Study Anything learning loop through its repository CLI and public API. Use when Codex needs to start source-bound study sessions, answer generated questions, inspect mastery or events, handle HITL tasks, discard a session with explicit approval, or connect a user-owned HTTP agent without storing model credentials in Study Anything.
---

# Study Anything

Use the repository CLI from the Study Anything project root. First ensure the local API is ready:

```bash
./scripts/run_skill_mode_demo.sh
./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py health
python3 scripts/study_anything_cli.py commercial-readiness
```

Use `run_skill_mode_demo.sh` first when operating through a shell tool that may not preserve
background processes between commands. It starts the API, completes a deterministic CLI learning
flow, verifies discard confirmation, and cleans up in one command.

Set `STUDY_ANYTHING_API_BASE` when the API is not at `http://127.0.0.1:8000`.
Alternatively pass `--api-base` to `scripts/study_anything_cli.py`.
If the user already runs the Docker stack or a remote private deployment, do not launch another local
API. Check `health` against their configured API base instead.

## Start A Learning Loop

1. Check API health.
2. Start a source-bound session. The CLI default `--agent-mode auto` uses configured Agent defaults
   when the common learning capabilities are routed, and falls back to the zero-key demo Agent when
   no Agent is configured. Use `--agent-mode demo` only for local demos and smoke tests. Use
   `--agent-mode configured` only when explicitly debugging configured-Agent routing.
3. Read the generated question from the command output.
4. Submit the user's answer. Omit `--item-id` to answer the first unanswered question.
5. Report the mastery level, feedback, insight, and any open HITL task.

```bash
python3 scripts/study_anything_cli.py start \
  --title "Learning notes" \
  --reference "local://notes" \
  --text "Paste the source material here."

python3 scripts/study_anything_cli.py answer SESSION_ID \
  --text "Answer grounded in the source."
```

When the platform agent has gathered extra web, document, video, or app context, attach it before the
quiz loop:

```bash
python3 scripts/study_anything_cli.py enrich SESSION_ID \
  --source-type video_slice \
  --reference "video://lesson/clip-1" \
  --title "Lesson clip" \
  --locator "00:00:05-00:00:42" \
  --text "Paste the bounded excerpt here."

python3 scripts/study_anything_cli.py teach SESSION_ID \
  --layer overview \
  --layer glossary \
  --language zh \
  --level beginner
```

Prefer Learning Context Packages when the platform agent is importing mixed sources such as web pages,
PDF excerpts, video slices, app context, Markdown notes, or Obsidian notes:

```bash
python3 scripts/study_anything_cli.py context-validate \
  fixtures/notebooklm/notebooklm-style-context-package.json

python3 scripts/study_anything_cli.py context-import \
  fixtures/notebooklm/notebooklm-style-context-package.json --session

python3 scripts/study_anything_cli.py context-import \
  fixtures/notebooklm/notebooklm-style-context-package.json \
  --session-id SESSION_ID
```

The package schema is `learning-context-package-v1`. It supports `web`, `document`, `video_slice`,
`app_context`, `markdown_note`, and `obsidian_note`. Do not put model keys, agent secrets, or broad
unbounded workspace dumps into the package.
For import commands, bare `--session` prints the created/expanded session summary. Use
`--session SESSION_ID` or `--session-id SESSION_ID` to expand an existing session.

When a reviewed local importer plugin is available, use the controlled importer runtime instead of
manually assembling the package:

```bash
python3 scripts/study_anything_cli.py importer-run example-note-importer \
  --confirm-permission write:context \
  --input-json '{"note_reference":"obsidian://Study Anything/Lesson","title":"Learning notes","markdown_excerpt":"Paste bounded note context here."}' \
  --create-session --session
```

Network-capable importers require both exact permission confirmation and `--allow-network`. Use that
only after the user approves the network permission; the platform agent should normally gather browser,
file, app, and video context itself.

When retrieval is explicitly enabled, rebuild and search the source session before creating a focused
follow-up lesson:

```bash
python3 scripts/study_anything_cli.py retrieval-status
python3 scripts/study_anything_cli.py retrieval-rebuild SESSION_ID
python3 scripts/study_anything_cli.py retrieval-search SESSION_ID --query "focus topic"
python3 scripts/study_anything_cli.py retrieval-eval SESSION_ID --query "focus topic"
python3 scripts/study_anything_cli.py retrieval-import \
  --source-session-id SESSION_ID \
  --query "focus topic" \
  --session
```

Retrieval is optional and rebuildable. If `retrieval-status` reports `disabled`, continue with normal
context package or enrichment flows unless the user asks to enable LanceDB or the local smoke backend.

For a one-command lesson smoke, use:

```bash
python3 scripts/study_anything_cli.py lesson \
  --title "Learning notes" \
  --reference "local://notes" \
  --text "Paste the source material here." \
  --enrichment-text "Paste platform-collected context here." \
  --answer "Answer the generated quiz in your own words."
```

## Use A User-Owned HTTP Agent

Keep model credentials, tools, and internal reasoning inside the user's agent gateway. Store only its endpoint and capabilities in Study Anything.

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My local agent" \
  --endpoint "http://127.0.0.1:8787" \
  --set-default
```

Run `agent-test` after configuration. After `--set-default`, new sessions use the
configured Agent automatically through `--agent-mode auto`; add `--agent-mode configured` only when
you need to force configured routing while debugging.
If `auto` reports missing default capabilities and falls back to demo, run `agents`, then route the
provider with `agent-set-default PROVIDER_ID` unless the user intentionally configured split
providers with explicit `--capability` values.

## Inspect And Resume

```bash
python3 scripts/study_anything_cli.py sessions
python3 scripts/study_anything_cli.py show SESSION_ID
python3 scripts/study_anything_cli.py resume SESSION_ID
python3 scripts/study_anything_cli.py mastery SESSION_ID
python3 scripts/study_anything_cli.py events SESSION_ID
python3 scripts/study_anything_cli.py eval-policy
python3 scripts/study_anything_cli.py commercial-readiness
python3 scripts/study_anything_cli.py adoption-telemetry
python3 scripts/study_anything_cli.py pmf-readiness
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py agent-eval-report SESSION_ID
python3 scripts/study_anything_cli.py quality-eval SESSION_ID
python3 scripts/study_anything_cli.py retrieval-eval SOURCE_SESSION_ID --query "focus topic"
python3 scripts/study_anything_cli.py obsidian-export SESSION_ID --markdown
python3 scripts/study_anything_cli.py package-export SESSION_ID
python3 scripts/study_anything_cli.py hitl
```

Use `agent-audit` after every real learning loop when the user needs proof that Study Anything handled
the required learning tasks. Use `agent-eval` when another platform or CI job needs a redacted artifact
for Promptfoo, DeepEval, LangChain AgentEvals, or Ragas.
Use `eval-policy` to inspect release-gate rules and optional external adapter policy. Use
`commercial-readiness` to inspect the OSS/local-first launch boundary, hosted-service contracts, and
commercial non-goals before describing what can be sold or deployed. Use adoption telemetry and PMF
readiness only for aggregate local evidence; they must not include source text, answers, insights,
raw user ids, Agent endpoints, API keys, or browser/video/app private context. Use
`agent-eval-report` when another platform needs a per-session maturity report with
`native_fast_gate.status`. Use `quality-eval` before claiming teaching quality. Use `obsidian-export` for second-brain notes and
`package-export` for platform-agent, NotebookLM-style, or local archive handoff.
Use `retrieval-eval` before claiming retrieval/context quality for follow-up lessons.

Resolve a HITL task only after obtaining the missing information or user decision:

```bash
python3 scripts/study_anything_cli.py resolve TASK_ID \
  --session-id SESSION_ID \
  --note "User approved the recovery step."
```

Discard only after explicit user approval:

```bash
python3 scripts/study_anything_cli.py discard SESSION_ID --yes
```

## Demo

Use the deterministic fake agent to verify the local loop without external credentials:

```bash
python3 scripts/study_anything_cli.py demo
```

Do not present demo output as real model reasoning.

For the full platform ecosystem gate, start Skill Mode with retrieval enabled and run:

```bash
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory ./scripts/run_skill_mode_demo.sh
```

This includes importer runtime, platform enrichment, retrieval quality eval, DeepEval-compatible
quality eval, Obsidian export, and learning-package export.

For release, external platform handoff, or "can another Agent actually use this?" acceptance, run the
adoption pack verifier:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_adoption_telemetry.py
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The verifier emits `adoption-proof-v1`. Treat that proof as the minimum evidence before claiming a
Kimi/Codex/WorkBuddy-style integration works.
