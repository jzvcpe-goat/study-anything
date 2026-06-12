# Codex Pack

Use this pack when the platform Agent can run shell commands in this repository.

## Install

Expose the repo-local skill to Codex:

```bash
ln -s "$(pwd)/skills/study-anything" "${CODEX_HOME:-$HOME/.codex}/skills/study-anything"
```

## Run

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
./scripts/run_skill_mode_demo.sh
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py demo
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
```

For enrichment-first work, Codex should gather external context itself, call
`POST /v1/sessions/{session_id}/enrichment`, then run teaching layers, quiz, grading, quality eval,
and the Obsidian Markdown export at `GET /v1/sessions/{session_id}/exports/obsidian`.

## Acceptance

A Codex integration must return both:

- `agent-audit.status == verified`
- `agent-eval-artifact-v1` with all required native gates passing
- `agent-quality-eval-v1` with status `pass`
- `obsidian-markdown-export-v1` for copy-ready Obsidian second-brain notes

Do not paste raw source text, learner answers, grading feedback, Agent endpoints, or secrets into
shared logs.

## Troubleshooting

```bash
python3 scripts/diagnose_adoption.py
```

Use the diagnostic output to distinguish API reachability, missing provider defaults, Agent endpoint
health, Docker daemon state, and GHCR image visibility.
