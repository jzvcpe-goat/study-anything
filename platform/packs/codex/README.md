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
python3 scripts/study_anything_cli.py lesson \
  --title "Learning notes" \
  --reference "local://notes" \
  --text "Paste source material here." \
  --enrichment-text "Paste platform-collected web, video, document, or app context here." \
  --answer "Answer the generated quiz in your own words."
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py quality-eval SESSION_ID
python3 scripts/study_anything_cli.py obsidian-export SESSION_ID --markdown
python3 scripts/study_anything_cli.py package-export SESSION_ID
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
```

For enrichment-first work, Codex should gather external context itself, call
`POST /v1/sessions/{session_id}/enrichment`, then run teaching layers, quiz, grading, quality eval,
and the Obsidian Markdown export at `GET /v1/sessions/{session_id}/exports/obsidian`.
Use `GET /v1/sessions/{session_id}/exports/learning-package` or the CLI `package-export` command
to create a portable learning package when the next step is a NotebookLM-style bridge, local archive,
or platform-agent handoff.

## Acceptance

A Codex integration must return both:

- `agent-audit.status == verified`
- `agent-eval-artifact-v1` with all required native gates passing
- `agent-quality-eval-v1` with status `pass`
- `obsidian-markdown-export-v1` for copy-ready Obsidian second-brain notes
- `learning-package-v1` for platform-agent, NotebookLM-style, or local archive workflows

Do not paste raw source text, learner answers, grading feedback, Agent endpoints, or secrets into
shared logs.

## Troubleshooting

```bash
python3 scripts/diagnose_adoption.py
```

Use the diagnostic output to distinguish API reachability, missing provider defaults, Agent endpoint
health, Docker daemon state, and GHCR image visibility.
