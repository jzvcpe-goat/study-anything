# Obsidian Export

Study Anything supports two Obsidian-facing exports.

## User-Owned Obsidian Note

```http
GET /v1/sessions/{session_id}/exports/obsidian
```

This returns `obsidian-markdown-export-v1`: a Markdown note with source
references, teaching layers, quiz review, mastery, insights, enrichment
references, and backlinks.

This export is useful when the learner explicitly wants their full review note.
It never includes raw source or raw enrichment text, but it can include learner
answers and grading feedback. Platform wrappers should not log this response by
default.

## Strict Second-Brain Handoff

```http
GET /v1/sessions/{session_id}/exports/second-brain-handoff
```

This returns `second-brain-handoff-v1`, whose `obsidian` object contains a
`second-brain-obsidian-note-v1` note. It is the preferred export for platform
Agents and shared logs because it excludes answers, grading feedback, raw Agent
metadata, endpoints, and secrets.

The note includes:

- YAML frontmatter with `study_anything_session`, track, stage, mastery, source hash, tags, related notes, and review queue metadata.
- A source map that uses references, locators, and hashes instead of raw source text.
- A learning map from generated teaching layers.
- A review queue that keeps prompts but replaces answers with `_not included in second-brain handoff_`.
- Backlinks normalized as Obsidian wiki links.

## Recommended Flow

Use `study_anything_second_brain_handoff_export` from platform tools, or:

```bash
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --archive-dir ~/StudyAnythingArchive
```

Then move or symlink `obsidian/*.md` into the user's vault.
