# Cognitive Loop Mastra Runtime MVP

This package is the first repository-started Mastra runtime surface for Cognitive Loop System.
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
```

Expected coverage:

- high-risk workflow starts and suspends for Human Mastery Gate;
- approved gate resumes to success;
- rejected gate bails without continuing unsafe work;
- low-risk workflow completes without a gate;
- all output remains metadata-only and redacted.

