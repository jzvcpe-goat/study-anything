# WorkBuddy Pack

Use this pack for WorkBuddy-style agent workspaces that can import HTTP tools or OpenAPI specs.

## Import

Preferred:

```text
platform/generated/study-anything-platform-openapi.json
```

Alternative function-tool shape:

```text
platform/generated/study-anything-openai-tools.json
```

Before importing into a real workspace, prove the repo works from a disposable checkout:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
```

For release or workspace handoff acceptance, verify the distributable adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The verifier emits `adoption-proof-v1` and proves the WorkBuddy-style HTTP tool path without
requiring a standalone frontend.

## Runtime Boundary

The workspace Agent should own:

- browser and app operation
- files and external data
- video or document extraction
- user-facing conversation
- model credentials

Study Anything should own:

- deployment-guide-v1 launch guidance and first-run diagnostic boundaries
- commercial-readiness-v1 launch boundaries, hosted-service contracts, and local-first invariants
- source-bound learning state
- Learning Context Package validation and import
- Plugin SDK contract, capability index, and local package validation
- confirmed local importer runtime
- optional retrieval projection and retrieval-to-session flows
- quiz, grading, mastery, scribe, HITL
- redacted Agent audit and eval artifacts

## Local Acceptance

Against a running API, verify the imported tool surface and redacted evidence:

```bash
curl http://127.0.0.1:8000/v1/deployment/guide
curl http://127.0.0.1:8000/v1/commercial/readiness
curl http://127.0.0.1:8000/v1/evals/policy
python3 scripts/verify_commercial_readiness.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_importer_runtime_retrieval_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool report --create-session --required
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

If the workspace also wants a copy-ready user-owned HTTP Agent example, use the OpenAI-compatible
gateway dry-run before replacing it with the workspace's private Agent endpoint:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

If setup fails, run the adoption diagnostics before changing workspace configuration:

```bash
python3 scripts/diagnose_adoption.py
```

## Acceptance

After every completed learning loop, the workspace Agent should fetch:

```text
GET /v1/evals/policy
GET /v1/commercial/readiness
GET /v1/sessions/{session_id}/agent-audit
GET /v1/sessions/{session_id}/agent-eval/artifact
GET /v1/sessions/{session_id}/agent-eval/quality
GET /v1/sessions/{session_id}/agent-eval/report
GET /v1/sessions/{session_id}/exports/enrichment-artifact
GET /v1/sessions/{session_id}/exports/obsidian
GET /v1/sessions/{session_id}/exports/learning-package
GET /v1/sessions/{session_id}/exports/second-brain-handoff
```

The commercial readiness response is `commercial-readiness-v1`, which marks the local OSS and
platform-Agent launch path ready while keeping hosted paid services, billing, SSO, remote accounts,
and standalone app work out of scope. The enrichment artifact is a redacted Markdown+HTML
micro-lesson for the workspace conversation. The Obsidian Markdown export is for the user's
second-brain workflow. The learning package is for platform-agent handoff, NotebookLM-style bridges,
or local archives. The second-brain handoff is the preferred shared workspace export because it
excludes learner answers and grading feedback. The shared run summary should include only compact
mastery and redacted evidence, not raw source prose or learner answers.

Use `POST /v1/context-packages/validate`, `POST /v1/sessions/from-context-package`, and
`POST /v1/sessions/{session_id}/context-package` when WorkBuddy has collected browser pages,
documents, app context, Markdown/Obsidian notes, or video slices before the learning loop. The older
`POST /v1/sessions/{session_id}/enrichment` endpoint remains available for simple one-off excerpts.

If the workspace uses a reviewed local importer plugin, call `POST /v1/importers/{plugin_id}/run` with
exact permission confirmation, then import the returned package. Keep `allow_network=false` unless the
user explicitly approves the importer's `network:http` permission.
Before installation or invocation, call `GET /v1/plugins/sdk`, `GET /v1/plugins/capabilities`, and
`POST /v1/plugins/validate-package`. These endpoints do not copy plugin packages or execute
entrypoints.

If optional retrieval is healthy, call `POST /v1/sessions/{session_id}/retrieval/rebuild`, then
`POST /v1/sessions/{session_id}/retrieval/search`, call
`POST /v1/sessions/{session_id}/retrieval/eval` for redacted retrieval/context quality gates, and use
`POST /v1/sessions/from-retrieval` to start a focused follow-up lesson from minimal snippets.
