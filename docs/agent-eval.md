# Agent Eval Foundation

Study Anything separates Agent invocation audit from Agent quality evaluation.

- Invocation audit proves that required learning tasks were handled by a Study Anything Agent provider.
- Eval artifacts turn that audit into a redacted, tool-neutral record.
- Mature open-source eval projects then score quality, task completion, trajectory, and grounding.

This avoids a false sense of safety from a tiny homegrown judge while keeping the core self-host alpha
usable without cloud accounts, judge-model API keys, or a mandatory eval service.

## Current Public Surface

- `GET /v1/sessions/{session_id}/agent-audit`
- `GET /v1/sessions/{session_id}/agent-eval/artifact`
- `GET /v1/sessions/{session_id}/agent-eval/quality`
- `GET /v1/evals/quality/cases`
- `GET /v1/evals/retrieval/cases`
- `GET|POST /v1/sessions/{session_id}/retrieval/eval`
- `GET /v1/sessions/{session_id}/agent-eval` deprecated alias for invocation audit only

`agent-audit` proves which provider handled `quiz.generate`, `answer.grade`, and
`insight.synthesize`. `agent-eval/artifact` packages that proof for external eval tooling.
`agent-eval/quality` adds the first deterministic teaching-quality layer: overview, glossary,
quiz, grading, synthesis, grounding, enrichment readiness, and Obsidian readiness.
`retrieval/eval` adds deterministic retrieval/context quality gates for source binding, snippet
minimality, query relevance, and Learning Context Package handoff validity.

These eval endpoints are redacted. They do not return reading prose, source titles, answers, grading
feedback, insights, Agent endpoints, raw Agent metadata, API keys, retrieval snippets, or tool secrets.

## Open-Source Eval Selection

GitHub metadata was checked on 2026-06-08.

| Project | Stars | License | Use In Study Anything |
| --- | ---: | --- | --- |
| [Promptfoo](https://github.com/promptfoo/promptfoo) | 21,992 | MIT | First CLI/CI adapter for HTTP contract checks, regression gates, and red-team assertions. |
| [DeepEval](https://github.com/confident-ai/deepeval) | 15,974 | Apache-2.0 | Python eval harness for task completion, component-level metrics, and judge-model scoring. |
| [Ragas](https://github.com/vibrantlabsai/ragas) | 14,278 | Apache-2.0 | Source grounding, answer relevance, context relevance, and citation-quality evaluation. |
| [LangChain AgentEvals](https://github.com/langchain-ai/agentevals) | 610 | MIT | Trajectory matching for expected Agent/tool step order. |
| [Phoenix](https://github.com/Arize-ai/phoenix) | 10,021 | Other | Observability/eval candidate, useful later if Study Anything needs a heavier local eval UI. |
| [OpenAI Evals](https://github.com/openai/evals) | 18,627 | Other | Benchmark registry reference, not the first integration because license and workflow fit are weaker. |
| [AgentBench](https://github.com/THUDM/AgentBench) | 3,473 | Apache-2.0 | Academic benchmark reference, not a product smoke/eval harness. |

The first implementation path is:

1. Promptfoo for local HTTP and CI gates.
2. DeepEval for Python quality eval suites.
3. LangChain AgentEvals for trajectory scoring.
4. Ragas for source grounding once enrichment/retrieval datasets are exported.

## Native Gates

`agent-eval/artifact` currently includes deterministic gates that require no judge model:

- `agent_invocation_coverage`: all required learning tasks were observed.
- `source_reference_present`: the session has a source reference.
- `excerpt_hash_present`: source evidence is represented by a hash, not raw prose.
- `privacy_redaction`: audit/eval artifacts omit private learning content and Agent endpoints.
- `external_agent_used`: advisory gate showing whether a user-owned Agent was used instead of demo.

The first four gates must pass before external quality evals are meaningful.

## Promptfoo

Create or reuse a completed learning session, then run the Study Anything wrapper:

```bash
API_BASE=http://127.0.0.1:8000 \
  .venv/bin/python scripts/run_external_agent_evals.py --tool promptfoo --create-session
```

For release-candidate validation where Node/npm package installation is allowed to fail the build,
require the external gate:

```bash
API_BASE=http://127.0.0.1:8000 \
  .venv/bin/python scripts/run_external_agent_evals.py --tool promptfoo --create-session --required
```

The wrapper pins Promptfoo and applies a timeout. This avoids clean clones hanging silently on first
`npx` package download while still using the mature Promptfoo runner when the operator enables the
external gate.

For the full adoption smoke from a disposable clone:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo . --with-promptfoo
```

If the output is `status=ok`, the Promptfoo path consumed the redacted artifact successfully. That is
still a contract/evidence gate, not a claim that the Agent's teaching quality is good.

You can also call Promptfoo directly:

```bash
npx promptfoo@0.121.15 eval -c evals/promptfoo/agent-eval-artifact.yaml \
  --var apiBase=http://127.0.0.1:8000 \
  --var sessionId=<completed-session-id>
```

The template calls `GET /v1/sessions/{session_id}/agent-eval/artifact` and asserts that the schema,
required gates, adapter matrix, and Agent trajectory are present.

## DeepEval

DeepEval is the preferred Python quality harness after the native gates pass. v0.2.18+ includes a
custom non-LLM metric adapter at:

```text
evals/deepeval/study_anything_quality_eval.py
```

Run it through the shared wrapper:

```bash
API_BASE=http://127.0.0.1:8000 \
  .venv/bin/python scripts/run_external_agent_evals.py \
  --tool deepeval \
  --create-session \
  --allow-native-quality-fallback
```

When `deepeval` is installed, the adapter uses DeepEval's custom metric interface against
`agent-eval/quality`. Without DeepEval, `--allow-native-quality-fallback` runs the same deterministic
quality report directly and labels the result `deepeval-compatible-native`. Do not treat fallback as
the same claim as a real DeepEval run.

Future judge-model metrics should include:

- `TaskCompletionMetric`: did the external Agent complete the learning task?
- `GEval`: Study Anything-specific rubric, such as source-bound learning usefulness.
- `AnswerRelevancy`: does feedback answer the learner's actual misunderstanding?
- `Faithfulness`: does generated synthesis remain grounded in the supplied source?

DeepEval can use multiple judge providers. Study Anything should never store the judge model key; the
operator configures judge credentials in their eval environment.

## LangChain AgentEvals

LangChain AgentEvals is the trajectory adapter. Study Anything already emits the canonical sequence:

1. `quiz.generate`
2. `answer.grade`
3. `insight.synthesize`

The exported `trajectory` field can be transformed into the expected message/tool-call shape for
`create_trajectory_match_evaluator`.

## Ragas

Ragas becomes important after Learning Enrichment Layer and LanceDB retrieval work. It should evaluate:

- faithfulness against selected source chunks
- answer relevance
- context relevance
- citation usefulness

Do not use Ragas as proof that the Agent was called. That remains `agent-audit`.

v0.2.21 adds a Ragas-compatible native retrieval gate. It is not a full Ragas run, but it gives Ragas
and judge-model pipelines a redacted, stable report to consume:

```bash
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

The report schema is `retrieval-quality-eval-v1`. It includes result metadata, scores, source
references, excerpt hashes, and gate outcomes, but not raw source text or retrieval snippets.

## Regression Baseline

v0.2.24 adds a committed fast native baseline at:

```text
evals/baselines/study-anything-agent-eval-baseline.json
```

Generate or verify it with:

```bash
.venv/bin/python scripts/verify_agent_eval_baseline.py --write
.venv/bin/python scripts/verify_agent_eval_baseline.py --check
```

The check emits `study-anything-agent-eval-regression-report-v1`. It compares the current scorecard
against the committed baseline for:

- Promptfoo, DeepEval, LangChain AgentEvals, and Ragas adapter ids.
- `quiz.generate -> answer.grade -> insight.synthesize` trajectory coverage.
- required native eval gates.
- `agent-quality-eval-v1` teaching quality score.
- `retrieval-quality-eval-v1` retrieval/context quality score.
- privacy invariants for source text, answers, feedback, endpoints, metadata, and model/judge keys.

This is the default CI/release gate because it is deterministic and local-first. External eval tools
remain available through `scripts/run_external_agent_evals.py`, but they are only blocking when the
operator explicitly passes `--required` and accepts package install/network cost.

## Local Smoke

Against a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
python3 scripts/verify_agent_eval_baseline.py --check
API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
```

When checking a user-owned HTTP Agent path, set:

```bash
python3 scripts/mock_http_agent.py --host 127.0.0.1 --port 8787
EXPECT_EXTERNAL_AGENT=true API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://127.0.0.1:8787 \
  python3 scripts/verify_agent_eval_flow.py
```

This smoke verifies native gates and adapter readiness. It does not call judge models.

To prevent drift between the API artifact, Promptfoo config, docs, and release claims:

```bash
.venv/bin/python scripts/verify_agent_eval_assets.py
```

## Launch Rule

A release can claim Agent Eval foundation only when:

- API tests cover `agent-eval/artifact`.
- `scripts/verify_agent_eval_assets.py` passes.
- `scripts/verify_agent_eval_baseline.py --check` passes and emits
  `study-anything-agent-eval-regression-report-v1`.
- `scripts/verify_agent_eval_flow.py` passes on the fake demo path.
- Promptfoo can be invoked through `scripts/run_external_agent_evals.py --tool promptfoo` when the
  release environment permits external Node package installation.
- DeepEval or the labeled native fallback can consume `agent-eval/quality`.
- Retrieval eval can consume rebuilt retrieval results through
  `scripts/run_external_agent_evals.py --tool retrieval`.
- Mock/user-owned HTTP Agent smoke verifies `agent-audit` and can optionally require external Agent usage.
- Docs list the selected mature eval projects and explain why Study Anything does not run judge models by default.

## Claim Boundaries

- `agent-audit.status=verified` means Study Anything observed the required Agent task invocations.
- `agent-eval/artifact.status=ready_for_external_eval` means the redacted artifact is structurally
  ready for external tools.
- Promptfoo passing the bundled config means the artifact contract and native gates passed.
- `agent-eval/quality.status=pass` means the deterministic minimum teaching-quality gates passed.
- `retrieval-quality-eval.status=pass` means the retrieval/context handoff gates and privacy invariants
  passed for the scored query.
- `study-anything-agent-eval-regression-report-v1.status=pass` means the current deterministic
  scorecard did not regress against the committed baseline.
- A real DeepEval run means the quality report was consumed through DeepEval's metric interface.
- A real Ragas run or judge-model suite is still required for stronger claims about
  trajectory quality, source-grounding quality, and learning usefulness at scale.
