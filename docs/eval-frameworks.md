# External Eval Frameworks

Study Anything treats eval as a release and ecosystem-submission contract, not as a hidden judge
inside the product. The local-first core must prove its own workflow, redaction, trajectory, and
minimum teaching-quality gates before optional mature eval tools are useful.

## Required Native Gates

These gates are required for release and marketplace-style submission:

- `agent-eval-report-v1` via `scripts/run_external_agent_evals.py --tool report --create-session --required`.
- `agent-eval-artifact-v1` asset checks via `scripts/verify_agent_eval_assets.py`.
- `study-anything-agent-eval-regression-report-v1` via `scripts/verify_agent_eval_baseline.py --check`.
- `external-agent-adapter-hardening-v1` via `scripts/verify_external_agent_adapter_hardening.py`.
- `external-eval-marketplace-harness-v1` via `scripts/verify_external_eval_marketplace_harness.py --check`.
- `cognitive-loop-review-agent-eval-harness-v1` via `scripts/verify_cognitive_loop_review_agent_eval_harness.py --check`.
- `cognitive-loop-review-agent-ci-receipt-v1` via `scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check`.

These gates do not require judge-model credentials and must not store real model keys in Study
Anything.

## Optional External Adapters

Promptfoo is the first optional external contract runner. It checks the redacted Agent eval artifact,
native gates, adapter matrix, and trajectory. Use it when Node/npm is available:

```bash
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool promptfoo --create-session
```

DeepEval is the preferred Python quality-eval adapter. It can run the Study Anything deterministic
quality report through a DeepEval-compatible interface, or fall back to the native quality gate when
the operator explicitly allows fallback:

```bash
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
```

LangChain AgentEvals is a trajectory adapter target. Study Anything exports the canonical sequence
`quiz.generate -> answer.grade -> insight.synthesize`; external operators can feed that trajectory
into `create_trajectory_match_evaluator`.

Ragas is the grounding target. The current release exposes a Ragas-compatible native retrieval gate:

```bash
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

Full Ragas/judge-model runs belong in the operator eval environment. Study Anything must not store judge or model keys.

## Marketplace Harness

`platform/generated/study-anything-external-eval-harness.json` is the copyable marketplace-quality
contract for Kimi, Codex, WorkBuddy-style workspaces, and generic OpenAPI tool platforms. It records:

- native fast gates and required commands
- optional adapter descriptors and timeout behavior
- fake and mock HTTP Agent fixtures
- sample eval cases
- expected evidence schema
- redaction assertions
- failure remediation
- platform pack alignment

The harness is redacted. It must not include raw source text, learner answers, grading feedback,
generated insights, Agent endpoints, Agent metadata, API keys, judge keys, or private browser/video
context.

## Review Agent Eval Harness

`evals/review-agent` is the offline eval set for the Cognitive Loop Review Agent. It contains
synthetic git diffs and golden JSON reports for approved, needs-review, and needs-fix decisions. Use
it before trusting a Kimi, Codex, WorkBuddy, or private CI Review Agent:

```bash
python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check
```

It emits `cognitive-loop-review-agent-eval-harness-v1` and checks decision coverage, critical
security findings with CWE references, low-confidence suppression, and privacy-leak rejection. These
fixtures may contain synthetic raw diff text; real operator diffs must stay in ephemeral handoff
requests and must not be committed.

## Review Agent CI Receipt

After a Kimi, Codex, WorkBuddy, or private CI Review Agent returns a JSON report, keep raw handoff
material and real report files outside the repo unless an operator explicitly needs them. The safe
artifact for PR comments, release evidence, or CI logs is the metadata-only receipt:

```bash
python3 scripts/cognitive_loop_review_agent_receipt.py build --report REVIEW_AGENT_REPORT.json --provider-id PROVIDER --pr-ref PR --commit-sha SHA
python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check
```

It emits `cognitive-loop-review-agent-ci-receipt-v1` and stores only provider/ref metadata, report
hash, decision, risk, finding counts, validation commands, and human follow-up action. It must reject
raw diff text, file bodies, finding evidence, report summaries, Agent endpoint secrets, real model
keys, and hidden chain-of-thought.
