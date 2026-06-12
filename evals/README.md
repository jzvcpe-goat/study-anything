# Study Anything Evals

This directory contains adapters and templates for mature external eval tools.

Study Anything does not run judge models by default. The API emits redacted Agent eval artifacts, and
operators run the eval tool of their choice in their own environment.

## Promptfoo

Start Study Anything, complete a session, then run the wrapper:

```bash
API_BASE=http://127.0.0.1:8000 \
  .venv/bin/python scripts/run_external_agent_evals.py --tool promptfoo --create-session
```

Use `--required` in CI or release-candidate validation when Node/npm package installation is allowed
to fail the build:

```bash
API_BASE=http://127.0.0.1:8000 \
  .venv/bin/python scripts/run_external_agent_evals.py --tool promptfoo --create-session --required
```

The wrapper invokes Promptfoo with a pinned package version and a timeout so clean clones do not hang
silently on first package download. You can also call Promptfoo directly:

```bash
npx promptfoo@0.121.15 eval -c evals/promptfoo/agent-eval-artifact.yaml \
  --var apiBase=http://127.0.0.1:8000 \
  --var sessionId=<completed-session-id>
```

This checks the Agent eval artifact contract. It is a regression gate, not a semantic judge.

## Native Smoke

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
```

Set `EXPECT_EXTERNAL_AGENT=true` when validating a user-owned HTTP Agent path.

## Retrieval Context Quality

For retrieval and Learning Context Package handoff quality, use the Ragas-compatible native gate:

```bash
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

This consumes `retrieval-quality-eval-v1`. It checks result coverage, source binding, snippet
minimality, query relevance, context-package validity, and privacy invariants without returning raw
source text or retrieval snippets. A real Ragas suite can be layered on top outside Study Anything
with user-owned evaluator credentials.

## Asset Drift Gate

```bash
.venv/bin/python scripts/verify_agent_eval_assets.py
```

This release gate checks the API adapter matrix, redaction-safe sample artifact, Promptfoo config,
and docs stay aligned.
