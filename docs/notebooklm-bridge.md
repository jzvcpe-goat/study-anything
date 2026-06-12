# NotebookLM Bridge

Study Anything does not require a NotebookLM official API. The current bridge is
a manual, local-first handoff contract for platform Agents.

## Why Manual Bridge

NotebookLM is useful for source-grounded exploration, but Study Anything should
not pretend to own the user's Google workspace or browser session. The platform
Agent owns browsing, file upload, source collection, and any NotebookLM UI
operation. Study Anything owns learning state, validation, audit, eval, mastery,
and redacted exports.

## Input Fixture

Use the fixture as the import-side contract:

```bash
python3 scripts/study_anything_cli.py context-validate fixtures/notebooklm/notebooklm-style-context-package.json
python3 scripts/study_anything_cli.py context-import fixtures/notebooklm/notebooklm-style-context-package.json --session
```

The fixture models `learning-context-package-v1` with web, document, video
slice, app context, Markdown, and Obsidian-note sources. Raw bounded excerpts are
accepted only at the import boundary and are not returned by exported handoff
artifacts.

## Output Handoff

After the learning loop, prefer:

```bash
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --output handoff.json
```

The `notebooklm_bridge` object includes:

- `status: ready_for_manual_import`
- `official_notebooklm_api_required: false`
- `bridge_mode: manual_export_import`
- suggested source references
- manual steps for platform Agents

For NotebookLM use:

1. Upload original user-approved sources through NotebookLM or the platform Agent.
2. Paste the redacted second-brain Obsidian note or learning package as study-state context.
3. Ask NotebookLM to compare its source-grounded answer with Study Anything's mastery and review queue.

## Verification

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
```

These checks validate the NotebookLM-style fixture, complete a learning loop,
and assert `second-brain-handoff-v1` without raw source text, raw enrichment
text, learner answers, Agent endpoints, raw Agent metadata, or secrets.
