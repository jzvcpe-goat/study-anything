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

## Agent Eval Baseline

The fast release gate is the committed deterministic baseline:

```bash
.venv/bin/python scripts/verify_agent_eval_baseline.py --check
```

It emits `study-anything-agent-eval-regression-report-v1` and compares the current redacted
scorecard against `evals/baselines/study-anything-agent-eval-baseline.json`. The comparison covers
adapter ids, trajectory coverage, required native gates, teaching quality score, retrieval quality
score, and privacy invariants. This gate is local-first and does not install Promptfoo, DeepEval,
Ragas, or judge-model dependencies.

## Asset Drift Gate

```bash
.venv/bin/python scripts/verify_agent_eval_assets.py
```

This release gate checks the API adapter matrix, redaction-safe sample artifact, Promptfoo config,
baseline, and docs stay aligned.

## Review Agent Eval

The Cognitive Loop Review Agent has a separate offline eval harness:

```bash
python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check
```

It uses only synthetic git diffs under `evals/review-agent`, then validates golden reports against
the public Review Agent report schema. Use it before routing real PR diffs to Kimi, Codex,
WorkBuddy, or a private CI Review Agent.

For CI/PR evidence, pair the external report verifier with the metadata-only receipt verifier:

```bash
python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check
python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check
python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check
python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
```

The receipt path records provider/ref metadata and the validated report hash, but rejects raw diff
text, finding evidence, report summaries, Agent endpoint secrets, real model keys, and hidden
chain-of-thought. The PR comment pack turns that receipt into bilingual copy-ready comments and a
Checks summary without reintroducing report-body content. The acceptance bundle packages the receipt,
comment pack, manifest, and Markdown summary for operator handoff. The GitHub workflow verifier keeps
the copy-ready manual workflow on the same metadata-only boundary and rejects unsafe auto-trigger or
raw-report upload fixtures. The policy gate converts the same safe bundle or receipt into advisory,
soft, or strict CI exit-code behavior without reopening raw Review Agent content. The workflow
install smoke proves the same template and policy gate can be used from the adoption pack zip after
copying the workflow into `.github/workflows/`, still without raw report upload or real model calls.
