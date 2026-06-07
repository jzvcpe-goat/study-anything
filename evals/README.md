# Study Anything Evals

This directory contains adapters and templates for mature external eval tools.

Study Anything does not run judge models by default. The API emits redacted Agent eval artifacts, and
operators run the eval tool of their choice in their own environment.

## Promptfoo

Start Study Anything, complete a session, then run:

```bash
npx promptfoo@latest eval -c evals/promptfoo/agent-eval-artifact.yaml \
  --var apiBase=http://127.0.0.1:8000 \
  --var sessionId=<completed-session-id>
```

This checks the Agent eval artifact contract. It is a regression gate, not a semantic judge.

## Native Smoke

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
```

Set `EXPECT_EXTERNAL_AGENT=true` when validating a user-owned HTTP Agent path.
