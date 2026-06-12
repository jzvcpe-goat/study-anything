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

## Runtime Boundary

The workspace Agent should own:

- browser and app operation
- files and external data
- video or document extraction
- user-facing conversation
- model credentials

Study Anything should own:

- source-bound learning state
- quiz, grading, mastery, scribe, HITL
- redacted Agent audit and eval artifacts

## Local Acceptance

Against a running API, verify the imported tool surface and redacted evidence:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
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
GET /v1/sessions/{session_id}/agent-audit
GET /v1/sessions/{session_id}/agent-eval/artifact
GET /v1/sessions/{session_id}/agent-eval/quality
GET /v1/sessions/{session_id}/exports/obsidian
GET /v1/sessions/{session_id}/exports/learning-package
```

The Obsidian Markdown export is for the user's second-brain workflow. The learning package is for
platform-agent handoff, NotebookLM-style bridges, or local archives. The shared run summary should
include only compact mastery and redacted evidence, not raw source prose or learner answers.

Use `POST /v1/sessions/{session_id}/enrichment` when WorkBuddy has collected browser pages,
documents, app context, or video slices before the learning loop.
