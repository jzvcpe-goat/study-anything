# Cognitive Loop Mastra Runtime MVP

This package is the repository-started Mastra runtime adapter for the Cognitive Black Box reference harness.
It is intentionally small: it starts a local Mastra instance, registers the existing
`cognitive-loop-runtime-adapter` workflow, runs metadata-only evidence through it, and proves
the Human Mastery Gate paths.

It does not call a real model, start a watcher daemon, compile or expose a hosted service, store
Agent endpoint secrets, or include raw source text, diff bodies, learner answers, prompts, or
model keys.

## Verify

```bash
cd platform/mastra-runtime
npm ci
npm run verify
```

The repository-level verifier wraps these commands:

```bash
python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check
python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check
python3 scripts/verify_cognitive_loop_langfuse_observability.py --check
```

Expected coverage:

- high-risk workflow starts and suspends for Human Mastery Gate;
- approved gate resumes to success;
- rejected gate bails without continuing unsafe work;
- low-risk workflow completes without a gate;
- suspended high-risk state persists to a local libSQL file and resumes or bails from a
  separate Node process;
- watcher-generated `ProjectEvent` evidence is used without starting a watcher daemon;
- service and durable receipts map to local Langfuse trace/span/generation/score DTOs;
- all output remains metadata-only and redacted.

`npm run run-observability -- --json --service-report <service.json> --durable-report <durable.json>`
emits a local receipt only. It does not import the Langfuse SDK, call Langfuse Cloud or a
self-hosted Langfuse instance, or include source bodies, diffs, learner answers, Agent endpoints,
Agent metadata, prompts, model keys, storage paths, or absolute local paths.
