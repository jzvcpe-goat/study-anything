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
- `GET /v1/sessions/{session_id}/agent-eval` deprecated alias for invocation audit only

`agent-audit` proves which provider handled `quiz.generate`, `answer.grade`, and
`insight.synthesize`. `agent-eval/artifact` packages that proof for external eval tooling.

Both endpoints are redacted. They do not return reading prose, source titles, answers, grading
feedback, insights, Agent endpoints, raw Agent metadata, API keys, or tool secrets.

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

Create or reuse a completed learning session, then run:

```bash
npx promptfoo@latest eval -c evals/promptfoo/agent-eval-artifact.yaml \
  --var apiBase=http://127.0.0.1:8000 \
  --var sessionId=<completed-session-id>
```

The template calls `GET /v1/sessions/{session_id}/agent-eval/artifact` and asserts that the schema,
required gates, adapter matrix, and Agent trajectory are present.

## DeepEval

DeepEval is the preferred Python judge harness after the native gates pass. The first useful metrics are:

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

## Local Smoke

Against a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
```

When checking a user-owned HTTP Agent path, set:

```bash
python3 scripts/mock_http_agent.py --host 127.0.0.1 --port 8787
EXPECT_EXTERNAL_AGENT=true API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://127.0.0.1:8787 \
  python3 scripts/verify_agent_eval_flow.py
```

This smoke verifies native gates and adapter readiness. It does not call judge models.

## Launch Rule

A release can claim Agent Eval foundation only when:

- API tests cover `agent-eval/artifact`.
- `scripts/verify_agent_eval_flow.py` passes on the fake demo path.
- Mock/user-owned HTTP Agent smoke verifies `agent-audit` and can optionally require external Agent usage.
- Docs list the selected mature eval projects and explain why Study Anything does not run judge models by default.
