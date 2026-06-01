# Skill Mode

Study Anything can be used before the Web UI is visually complete. The repository includes a small standard-library CLI and a repo-local Codex skill:

- CLI: `scripts/study_anything_cli.py`
- Skill: `skills/study-anything`

The CLI talks only to the public API. It does not store model API keys or execute real model logic inside Study Anything.

## Start

Launch the API or Docker stack, then run:

```bash
python3 scripts/study_anything_cli.py health
python3 scripts/study_anything_cli.py demo
```

The deterministic demo creates a source-bound question, submits a grounded answer, updates mastery, and synthesizes an insight.

## Learn From A Source

```bash
python3 scripts/study_anything_cli.py start \
  --title "Notes on retrieval practice" \
  --reference "local://retrieval-practice" \
  --text "Retrieval practice improves durable learning when recall is effortful and repeated."

python3 scripts/study_anything_cli.py answer SESSION_ID \
  --text "Effortful repeated recall strengthens durable learning."
```

Run `show SESSION_ID`, `mastery SESSION_ID`, or `events SESSION_ID` to inspect the resulting state.

## Connect Your Agent

Expose a user-owned gateway that implements `docs/agent-contract.md`, then configure its endpoint:

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My private learning agent" \
  --endpoint "http://127.0.0.1:8787" \
  --set-default

python3 scripts/study_anything_cli.py agent-test PROVIDER_ID
```

Use `--agent-mode configured` when starting a session with that gateway. Credentials, tools, and model choice remain inside the gateway.

## Install The Skill

Copy or symlink `skills/study-anything` into your Codex skills directory to make it discoverable:

```bash
ln -s "$(pwd)/skills/study-anything" "${CODEX_HOME:-$HOME/.codex}/skills/study-anything"
```

The skill teaches an Agent to operate the same CLI, including HITL resolution and explicit confirmation before discard.
