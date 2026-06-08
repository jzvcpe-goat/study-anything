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
2. Start a source-bound session. Use `--agent-mode demo` only for local demos and smoke tests. Use `configured` for a user-owned agent.
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

## Use A User-Owned HTTP Agent

Keep model credentials, tools, and internal reasoning inside the user's agent gateway. Store only its endpoint and capabilities in Study Anything.

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My local agent" \
  --endpoint "http://127.0.0.1:8787" \
  --set-default
```

Run `agent-test PROVIDER_ID` after configuration. Start real sessions with `--agent-mode configured`.

## Inspect And Resume

```bash
python3 scripts/study_anything_cli.py sessions
python3 scripts/study_anything_cli.py show SESSION_ID
python3 scripts/study_anything_cli.py resume SESSION_ID
python3 scripts/study_anything_cli.py mastery SESSION_ID
python3 scripts/study_anything_cli.py events SESSION_ID
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py hitl
```

Use `agent-audit` after every real learning loop when the user needs proof that Study Anything handled
the required learning tasks. Use `agent-eval` when another platform or CI job needs a redacted artifact
for Promptfoo, DeepEval, LangChain AgentEvals, or Ragas.

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
