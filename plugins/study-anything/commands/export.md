# Export Study Anything Evidence

Export compact learning evidence for Obsidian, NotebookLM, local archive, or a
platform Agent handoff.

After a session is complete, use the Study Anything CLI or imported HTTP tools
to export:

```bash
python3 scripts/study_anything_cli.py mastery <SESSION_ID>
python3 scripts/study_anything_cli.py events <SESSION_ID>
```

For richer platform checks, run:

```bash
API_BASE="${STUDY_ANYTHING_API_BASE:-http://127.0.0.1:8000}" \
  python3 scripts/verify_platform_agent_tools.py
```

Exported handoff evidence should include schema names, session ids, mastery
state, source references, and redacted audit/eval metadata. It must not include
raw source text, learner answers, generated private insights, Agent endpoint
secrets, or model API keys.
