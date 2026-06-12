# Learning Enrichment Layer

Study Anything does not try to be the browser, file reader, video editor, or
all-purpose assistant. The platform Agent owns those capabilities. The Learning
Enrichment Layer is the boundary where that Agent hands bounded, user-approved
context to Study Anything for source-bound learning.

## Responsibilities

| Layer | Owns |
| --- | --- |
| Platform Agent | Browser/app operation, file access, video slicing, external data lookup, user conversation, real model credentials. |
| Study Anything | Context validation, source hashes, learning state, teaching layers, quiz, grading, mastery, audit, eval, and redacted exports. |

## Supported Context Types

Use these `source_type` values:

- `web`
- `document` or alias `pdf`
- `video_slice` or alias `video`
- `app_context`
- `markdown_note`
- `obsidian_note`

Every enrichment item must include:

- `reference`: stable source reference such as URL, file URI, app object URI, or Obsidian URI.
- `title`: human-readable source title.
- `text`: bounded excerpt selected by the platform Agent.
- `locator`: page, timestamp range, heading, object id, or selection marker.
- `provenance.collector`: platform or importer that captured the excerpt.
- `provenance.capture_method`: one of `browser_excerpt`, `document_excerpt`,
  `video_transcript_slice`, `app_selection`, `markdown_excerpt`,
  `obsidian_excerpt`, `manual_excerpt`, `retrieval_result`, or
  `importer_plugin`.
- `redaction_policy`: `reference_only`, `hash_and_locator`, or `summary_only`.

Study Anything recomputes `excerpt_hash` and rejects mismatches. It also rejects
secret-like keys and text so Agent/API keys do not cross into learning state.

## Direct Enrichment Example

```json
{
  "title": "Lesson Enrichment Bundle",
  "items": [
    {
      "source_type": "video_slice",
      "reference": "video://local/lesson-01",
      "title": "Lesson One Clip",
      "text": "Bounded user-approved transcript excerpt.",
      "locator": "00:01:10-00:02:20",
      "provenance": {
        "collector": "kimi-work",
        "capture_method": "video_transcript_slice",
        "source_owner": "user"
      },
      "redaction_policy": "reference_only"
    }
  ]
}
```

Send it to:

```bash
POST /v1/sessions/{session_id}/enrichment
```

The response returns references, hashes, locator, provenance, and redaction
policy, not raw item text.

## Micro-Lesson Export

After enrichment and optional teaching layers, call:

```bash
GET /v1/sessions/{session_id}/exports/enrichment-artifact
```

The response schema is `learning-enrichment-artifact-v1`. It includes:

- `markdown`: a compact source map and teaching brief.
- `html`: a small embeddable teaching snippet.
- `source_references`: primary and enrichment references with hashes,
  locators, provenance, and redaction policies.
- `privacy`: explicit flags confirming raw source/enrichment text, answers,
  Agent endpoints, raw Agent metadata, and secrets are excluded.

Use this artifact when a platform Agent wants to enrich a Kimi/Codex/WorkBuddy
conversation, hand material to a NotebookLM-style workflow, or paste a compact
learning brief into Obsidian.

## Verification

```bash
python3 scripts/generate_platform_agent_assets.py --check
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
```
