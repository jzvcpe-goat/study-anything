# Second-Brain Handoff

Study Anything is not trying to become the user's only knowledge app. The
second-brain handoff lets Kimi, Codex, WorkBuddy-style Agents, Obsidian, and
NotebookLM-style workflows reuse the learning result without adopting a new
frontend.

## API

```http
GET /v1/sessions/{session_id}/exports/second-brain-handoff
```

The response schema is `second-brain-handoff-v1`.

It includes:

- `obsidian`: a redacted Markdown note with frontmatter, backlinks, note graph references, source map, learning map, mastery snapshot, and review queue.
- `notebooklm_bridge`: manual import guidance and suggested source references. No official NotebookLM API is required.
- `learning_package`: a stricter redacted learning package for archive and platform handoff.
- `enrichment_artifact`: the Markdown+HTML micro-lesson when enrichment context exists.
- `local_archive`: `second-brain-archive-manifest-v1` plus file payloads that can be written to disk by the CLI.

The strict handoff excludes raw source text, raw enrichment text, learner
answers, grading feedback, Agent endpoints, raw Agent metadata, and secrets.

## CLI

```bash
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --output handoff.json
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --obsidian-markdown
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --archive-manifest
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --archive-dir /tmp/study-anything-archive
```

Use `--archive-dir` when you want a local folder containing:

- `manifest.json`
- `obsidian/*.md`
- `learning-package/*.json`
- `enrichment/*.md`
- `enrichment/*.html`

## Platform-Agent Contract

The platform Agent should use `study_anything_second_brain_handoff_export` as
the default long-term handoff tool. The older `study_anything_obsidian_export`
and `study_anything_learning_package_export` remain available for user-owned
exports, but they may include answers, grading feedback, or generated private
learning data.

Minimum acceptance:

```bash
python3 scripts/verify_notebooklm_obsidian_bridge_hardening.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
```

The offline verifier emits `notebooklm-obsidian-bridge-hardening-v1` and proves
the NotebookLM fixture, Obsidian note, learning package, enrichment artifact,
and local archive hashes before any server starts. The API verifiers assert
`second-brain-handoff-v1` through a running learning loop and reject leaks of
raw source text, raw enrichment text, learner answers, Agent endpoints, raw
Agent metadata, or secret-like values.
