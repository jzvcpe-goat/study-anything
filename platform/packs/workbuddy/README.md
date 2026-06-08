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

## Acceptance

After every completed learning loop, the workspace Agent should fetch:

```text
GET /v1/sessions/{session_id}/agent-audit
GET /v1/sessions/{session_id}/agent-eval/artifact
```

The shared run summary should include only compact mastery and redacted evidence, not raw source
prose or learner answers.
