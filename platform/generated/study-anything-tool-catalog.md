# Study Anything Platform Tool Catalog

Generated from `platform/study-anything-platform-tools.json`.

## Purpose

Minimal public tool contract for Codex, Kimi, WorkBuddy-style agents, and private agent workspaces that call Study Anything as a local-first learning engine.

## Privacy Contract

The platform Agent owns browsing, files, external data, application tooling, model credentials, and user-facing conversation.
Study Anything owns source-bound learning state, workflow orchestration, output validation, mastery, HITL, redacted audit, and redacted eval artifacts.

Never log or share:

- raw source text
- learner answers
- grading feedback
- generated insights
- agent endpoints
- agent metadata
- API keys or model secrets

## Generated Assets

- `study-anything-platform-openapi.json`: constrained OpenAPI 3.1 document for HTTP tool importers.
- `study-anything-openai-tools.json`: OpenAI-compatible function tool definitions for Kimi-compatible and other tool-calling agents.
- `study-anything-tool-catalog.md`: this human-readable catalog.

## Acceptance

A platform wrapper is acceptable only when it completes the local verification command:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
```

Additional gateway and release acceptance commands:

- API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
- API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
- API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
- python3 scripts/verify_openai_compatible_gateway.py --gateway-only
- python3 scripts/verify_clean_clone_adoption.py --repo .
- python3 scripts/verify_clean_clone_adoption.py --repo . --with-promptfoo
- python3 scripts/diagnose_adoption.py

## Tools

### `study_anything_health`

- Method: `GET`
- Path: `/v1/health`
- Description: Check that the local Study Anything API is reachable before starting a learning loop.

Output requirements:

- status == ok

Privacy:

```json
{
  "returns_private_learning_data": false
}
```

### `study_anything_create_session`

- Method: `POST`
- Path: `/v1/sessions`
- Description: Create a learning session for a local user. Use demo mode only for smoke tests.

Output requirements:

- session_id is present
- stage is initialized or awaiting_source

Privacy:

```json
{
  "returns_private_learning_data": false
}
```

### `study_anything_add_reading`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/reading`
- Description: Attach source material gathered by the platform agent to the learning session.

Output requirements:

- source.excerpt_hash is present

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "text",
    "title"
  ],
  "request_contains_private_learning_data": true
}
```

### `study_anything_add_enrichment`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/enrichment`
- Description: Attach web, document, video-slice, or app-context excerpts gathered by the platform agent and convert them into a Study Anything learning source bundle.

Output requirements:

- schema_version == learning-enrichment-v1
- source.excerpt_hash is present
- items contain excerpt_hash but not raw text

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "items.text",
    "items.title",
    "source.text"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": true
}
```

### `study_anything_run`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/run`
- Description: Advance the Study Anything workflow after a source is attached or after HITL resolution.

Output requirements:

- quiz_items contains at least one item, or open_hitl exists

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "quiz_items",
    "source",
    "insights"
  ],
  "returns_private_learning_data": true
}
```

### `study_anything_teaching_layers`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/teaching-layers`
- Description: Generate layered teaching output such as whole-topic overview, glossary, examples, or Obsidian-style notes through user-owned Agent capabilities.

Output requirements:

- schema_version == teaching-layers-v1
- layers contains each requested teaching layer
- each layer includes agent.task_type and content

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "layers.content",
    "layers.citations",
    "source"
  ],
  "returns_private_learning_data": true
}
```

### `study_anything_answer`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/answers`
- Description: Submit the learner's answer to one or more quiz items and advance mastery evaluation.

Output requirements:

- stage == completed or open HITL is returned
- mastery.level is present

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "answers",
    "grading_results",
    "insights"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": true
}
```

### `study_anything_mastery`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/mastery`
- Description: Read the compact mastery state for the completed learning loop.

Output requirements:

- level is numeric
- bloom is present

Privacy:

```json
{
  "returns_private_learning_data": false
}
```

### `study_anything_agent_audit`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/agent-audit`
- Description: Return redacted proof that Study Anything Agent providers handled the required learning tasks.

Output requirements:

- schema_version == agent-audit-v1
- status == verified
- observed_tasks includes quiz.generate, answer.grade, insight.synthesize

Privacy:

```json
{
  "must_not_return": [
    "source text",
    "answers",
    "feedback",
    "agent endpoints",
    "raw agent metadata",
    "secrets"
  ],
  "returns_private_learning_data": false
}
```

### `study_anything_agent_eval_artifact`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/agent-eval/artifact`
- Description: Return the redacted eval bridge for Promptfoo, DeepEval, LangChain AgentEvals, and Ragas.

Output requirements:

- schema_version == agent-eval-artifact-v1
- status == ready_for_external_eval
- all required native_gates pass
- adapter_strategy includes promptfoo, deepeval, langchain-agentevals, ragas

Privacy:

```json
{
  "must_not_return": [
    "source text",
    "answers",
    "feedback",
    "insights",
    "agent endpoints",
    "raw agent metadata",
    "secrets"
  ],
  "returns_private_learning_data": false
}
```

### `study_anything_agent_quality_eval`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/agent-eval/quality`
- Description: Return a redacted deterministic quality report that separates invocation proof, schema contract validity, and minimum teaching-quality gates.

Output requirements:

- schema_version == agent-quality-eval-v1
- status == pass or needs_review
- quality_score is numeric
- gates include overview_quality, glossary_quality, quiz_quality, grading_quality, synthesis_quality

Privacy:

```json
{
  "must_not_return": [
    "source text",
    "answers",
    "feedback",
    "insights",
    "agent endpoints",
    "raw agent metadata",
    "secrets"
  ],
  "returns_private_learning_data": false
}
```

### `study_anything_obsidian_export`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/exports/obsidian`
- Description: Return an Obsidian-compatible Markdown note with source references, teaching layers, quiz review, mastery, insights, and enrichment references.

Output requirements:

- schema_version == obsidian-markdown-export-v1
- format == markdown
- markdown contains Source, Quiz Review, Mastery, and Enrichment sections
- privacy.raw_source_text_included == false

Privacy:

```json
{
  "must_not_return": [
    "raw source text",
    "agent endpoints",
    "secrets"
  ],
  "platform_agent_should_redact_before_logging": [
    "markdown",
    "learner answers",
    "grading feedback"
  ],
  "returns_private_learning_data": true
}
```

### `study_anything_learning_package_export`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/exports/learning-package`
- Description: Return a portable redacted learning package for platform agents, NotebookLM-style bridges, Obsidian pipelines, and local archive workflows.

Output requirements:

- schema_version == learning-package-v1
- intended_consumers include platform_agent, notebooklm_bridge, obsidian_pipeline
- source_references include excerpt hashes
- privacy.raw_source_text_included == false
- privacy.raw_enrichment_text_included == false

Privacy:

```json
{
  "must_not_return": [
    "raw source text",
    "raw enrichment text",
    "agent endpoints",
    "secrets"
  ],
  "platform_agent_should_redact_before_logging": [
    "teaching_layers",
    "quiz_review",
    "learner answers",
    "grading feedback",
    "insights"
  ],
  "returns_private_learning_data": true
}
```
