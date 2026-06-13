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
- API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
- API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
- python3 scripts/verify_openai_compatible_gateway.py --gateway-only
- python3 scripts/verify_clean_clone_adoption.py --repo .
- python3 scripts/verify_clean_clone_adoption.py --repo . --with-promptfoo
- API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
- python3 scripts/diagnose_adoption.py

## Tools

### `study_anything_deployment_guide`

- Method: `GET`
- Path: `/v1/deployment/guide`
- Description: Read the redacted first-run deployment guide, local launch commands, failure classes, and platform-agent privacy boundary.

Output requirements:

- schema_version == deployment-guide-v1
- no_frontend_required == true
- entrypoints include skill_mode, docker_source, and published_image
- privacy.real_model_keys_stored_by_study_anything == false

Privacy:

```json
{
  "must_not_return": [
    "API keys",
    "agent endpoint secrets",
    "raw source text",
    "learner answers"
  ],
  "returns_private_learning_data": false
}
```

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

### `study_anything_validate_context_package`

- Method: `POST`
- Path: `/v1/context-packages/validate`
- Description: Validate a Learning Context Package built by a platform Agent before importing web, document, video, app, Markdown, or Obsidian context into Study Anything.

Output requirements:

- schema_version == learning-context-package-v1
- status == valid
- package.source_types include web, document, video_slice, app_context, markdown_note, or obsidian_note as applicable
- response omits item text

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "package.items.text",
    "package.items.title"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": false
}
```

### `study_anything_create_session_from_context_package`

- Method: `POST`
- Path: `/v1/sessions/from-context-package`
- Description: Create a learning session directly from a validated Learning Context Package.

Output requirements:

- schema_version == learning-context-package-v1
- status == session_created
- session.stage == enrichment_attached
- session.enrichment_items include excerpt_hash values

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "package.items.text",
    "session.source.text",
    "session.enrichment_items.text"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": true
}
```

### `study_anything_append_context_package`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/context-package`
- Description: Expand an existing learning session with a Learning Context Package.

Output requirements:

- schema_version == learning-context-package-v1
- status == session_expanded
- session.enrichment_items include appended context

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "package.items.text",
    "session.source.text",
    "session.enrichment_items.text"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": true
}
```

### `study_anything_plugin_sdk`

- Method: `GET`
- Path: `/v1/plugins/sdk`
- Description: Read the public Study Anything Plugin SDK contract without executing plugin code.

Output requirements:

- schema_version == plugin-sdk-v1
- manifest_schema_version == plugin-manifest-v1
- entrypoints_executed == false
- remote_code_downloads_allowed == false

Privacy:

```json
{
  "returns_agent_secrets": false,
  "returns_plugin_source_code": false,
  "returns_private_learning_data": false
}
```

### `study_anything_plugin_capabilities`

- Method: `GET`
- Path: `/v1/plugins/capabilities`
- Description: List installed plugin hooks, capabilities, trust summaries, and alpha runtime contracts without executing plugin code.

Output requirements:

- schema_version == plugin-capability-index-v1
- privacy.entrypoints_executed == false
- items include bundled importer/exporter examples

Privacy:

```json
{
  "returns_agent_secrets": false,
  "returns_plugin_source_code": false,
  "returns_private_learning_data": false
}
```

### `study_anything_validate_plugin_package`

- Method: `POST`
- Path: `/v1/plugins/validate-package`
- Description: Validate one explicitly selected local plugin package against the SDK contract without installing or executing it.

Output requirements:

- schema_version == plugin-package-validation-v1
- privacy.entrypoints_executed == false
- privacy.package_copied == false
- execution_allowed_by_validation == false

Privacy:

```json
{
  "returns_agent_secrets": false,
  "returns_plugin_source_code": false,
  "returns_private_learning_data": false
}
```

### `study_anything_run_importer`

- Method: `POST`
- Path: `/v1/importers/{plugin_id}/run`
- Description: Run a locally installed importer plugin after explicit permission confirmation and return a validated Learning Context Package.

Output requirements:

- schema_version == importer-run-v1
- status == package_created
- package.schema_version == learning-context-package-v1
- redacted_package omits item text

Privacy:

```json
{
  "network_disabled_by_default": true,
  "platform_agent_should_redact_before_logging": [
    "inputs",
    "package.items.text",
    "redacted_package.items.title"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": true
}
```

### `study_anything_retrieval_status`

- Method: `GET`
- Path: `/v1/retrieval/status`
- Description: Check whether optional retrieval projection is disabled, healthy, or unavailable.

Output requirements:

- status is disabled, healthy, or unavailable

Privacy:

```json
{
  "returns_private_learning_data": false
}
```

### `study_anything_retrieval_rebuild`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/retrieval/rebuild`
- Description: Rebuild the optional retrieval index for one session from canonical Study Anything session state.

Output requirements:

- status == rebuilt
- indexed_count >= 1

Privacy:

```json
{
  "canonical_source": "session_state",
  "returns_private_learning_data": false
}
```

### `study_anything_retrieval_search`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/retrieval/search`
- Description: Search the rebuilt retrieval index for one session and return minimal source snippets.

Output requirements:

- schema_version == retrieval-search-v1
- results include reference, excerpt_hash, locator, snippet, and score
- full_source_text_returned == false

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "query",
    "results.snippet"
  ],
  "request_contains_private_learning_data": false,
  "returns_private_learning_data": true
}
```

### `study_anything_retrieval_quality_eval`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/retrieval/eval`
- Description: Return redacted retrieval/context quality gates for a rebuilt retrieval index and query.

Output requirements:

- schema_version == retrieval-quality-eval-v1
- status == pass or needs_review
- quality_score is numeric
- gates include retrieval_available, result_count, source_binding, snippet_minimality, query_relevance, context_package_valid
- privacy.result_snippets_included == false

Privacy:

```json
{
  "must_not_return": [
    "full source text",
    "answers",
    "feedback",
    "agent endpoints",
    "raw agent metadata",
    "secrets",
    "retrieval snippets"
  ],
  "returns_private_learning_data": false
}
```

### `study_anything_create_session_from_retrieval`

- Method: `POST`
- Path: `/v1/sessions/from-retrieval`
- Description: Create a new learning session from retrieval results produced by an existing indexed session.

Output requirements:

- schema_version == retrieval-session-v1
- status == session_created
- session.stage == enrichment_attached

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "query",
    "retrieval.results.snippet",
    "session.source.text"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": true
}
```

### `study_anything_append_retrieval_context`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/retrieval/context-package`
- Description: Expand an existing learning session with a Learning Context Package generated from retrieval results.

Output requirements:

- schema_version == retrieval-session-v1
- status == session_expanded
- session.enrichment_items include retrieval context

Privacy:

```json
{
  "platform_agent_should_redact_before_logging": [
    "query",
    "retrieval.results.snippet",
    "session.source.text"
  ],
  "request_contains_private_learning_data": true,
  "returns_private_learning_data": true
}
```

### `study_anything_add_enrichment`

- Method: `POST`
- Path: `/v1/sessions/{session_id}/enrichment`
- Description: Attach web, document, video-slice, app-context, Markdown, or Obsidian excerpts gathered by the platform agent and convert them into a Study Anything learning source bundle.

Output requirements:

- schema_version == learning-enrichment-v1
- source.excerpt_hash is present
- contract.requires_provenance == true
- contract.requires_redaction_policy == true
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

### `study_anything_enrichment_artifact_export`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/exports/enrichment-artifact`
- Description: Return a redacted Markdown and HTML micro-lesson built from platform-collected enrichment references for Kimi, Codex, WorkBuddy, NotebookLM-style, or Obsidian workflows.

Output requirements:

- schema_version == learning-enrichment-artifact-v1
- format == markdown+html
- source_references include provenance and excerpt hashes
- privacy.raw_source_text_included == false
- privacy.raw_enrichment_text_included == false
- privacy.agent_metadata_included == false

Privacy:

```json
{
  "must_not_return": [
    "raw source text",
    "raw enrichment text",
    "learner answers",
    "agent endpoints",
    "raw agent metadata",
    "secrets"
  ],
  "returns_private_learning_data": false
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

### `study_anything_second_brain_handoff_export`

- Method: `GET`
- Path: `/v1/sessions/{session_id}/exports/second-brain-handoff`
- Description: Return the strict redacted second-brain handoff for Obsidian, NotebookLM-style manual import, local archives, Kimi, Codex, and WorkBuddy-style platform Agents.

Output requirements:

- schema_version == second-brain-handoff-v1
- obsidian.schema_version == second-brain-obsidian-note-v1
- notebooklm_bridge.status == ready_for_manual_import
- local_archive.manifest.schema_version == second-brain-archive-manifest-v1
- privacy.learner_answers_included == false
- privacy.grading_feedback_included == false
- privacy.agent_metadata_included == false

Privacy:

```json
{
  "must_not_return": [
    "raw source text",
    "raw enrichment text",
    "learner answers",
    "grading feedback",
    "agent endpoints",
    "raw agent metadata",
    "secrets"
  ],
  "returns_private_learning_data": false
}
```
