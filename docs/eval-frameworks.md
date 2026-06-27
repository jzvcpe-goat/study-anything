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
- `cognitive-loop-review-agent-pr-comment-pack-v1` via `scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check`.
- `cognitive-loop-review-agent-acceptance-bundle-v1` via `scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check`.
- `cognitive-loop-review-agent-github-workflow-verification-v1` via `scripts/verify_cognitive_loop_review_agent_github_workflow.py --check`.
- `cognitive-loop-review-agent-policy-gate-v1` via `scripts/verify_cognitive_loop_review_agent_policy_gate.py --check`.
- `cognitive-loop-review-agent-workflow-install-smoke-v1` via `scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check`.

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

## Review Agent PR Comment Pack

After the metadata-only CI receipt is valid, produce the safe PR surface from that receipt instead
of pasting the external Agent report:

```bash
python3 scripts/cognitive_loop_review_agent_pr_comment.py build --receipt REVIEW_AGENT_CI_RECEIPT.json
python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check
```

It emits `cognitive-loop-review-agent-pr-comment-pack-v1` with bilingual Markdown comments, Checks
summary metadata, suggested labels, validation commands, and human action. The pack must remain
metadata-only and reject raw diff text, file bodies, finding evidence, report summaries, Agent
endpoint secrets, real model keys, and hidden chain-of-thought.

## Review Agent Acceptance Bundle

For CI or platform operators who want one artifact directory, build an acceptance bundle directly
from the validated external Agent report:

```bash
python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py build --report REVIEW_AGENT_REPORT.json --output-dir /tmp/review-agent-acceptance
python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check
```

It emits `cognitive-loop-review-agent-acceptance-bundle-v1` and writes a receipt, PR comment pack,
manifest, and `SUMMARY.md`. The bundle still excludes raw handoff material, raw diff text, file
bodies, finding evidence, report summaries, endpoint secrets, real model keys, and hidden
chain-of-thought.

## Review Agent GitHub Workflow Template

For repository operators who want a safe GitHub Actions handoff, use the manual template:

```bash
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
```

The template lives at `platform/workflows/cognitive-loop-review-agent-manual.yml` and is
`workflow_dispatch` only. It validates an external report or existing acceptance bundle, writes a
metadata-only Checks/step summary, runs the policy gate with `advisory`, `soft`, or `strict`, and
may upload only the safe acceptance bundle plus `review-agent-policy-gate.json`. It captures the
policy exit code before upload and applies it in the final step. It does not invoke real models,
require external Agent secrets, upload raw Review Agent reports, or persist raw diffs.

## Review Agent Workflow Install Smoke

For release-asset or adoption-pack handoff, prove the workflow remains installable from the zip:

```bash
python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
```

It emits `cognitive-loop-review-agent-workflow-install-smoke-v1`. The smoke extracts the adoption
pack, copies the workflow into a temporary `.github/workflows/` path, builds metadata-only
acceptance bundles from synthetic fixtures, and runs the shipped policy gate for `advisory`, `soft`,
and `strict`. It must not require a repo checkout, start a runtime, upload raw reports, call real
models, or persist temporary files.

## Review Agent Adoption Drill

For a single external-adopter rehearsal of the full zip-only Review Agent path, run:

```bash
python3 scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check
```

It emits `cognitive-loop-review-agent-adoption-drill-v1`. The drill extracts the adoption pack,
validates embedded Review Agent evidence, builds acceptance bundles, validates bilingual PR comment
packs, runs the `advisory` / `soft` / `strict` policy matrix, and proves the manual workflow can be
installed from the zip. It remains metadata-only and must not upload raw reports, include raw diffs,
call real models, or depend on stored model keys.

## Review Agent Policy Gate

For CI or operator handoff, convert the metadata-only acceptance bundle into a policy-specific exit
code:

```bash
python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir /tmp/review-agent-acceptance --policy soft
python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check
```

`advisory` always exits 0 and records the decision. `soft` exits nonzero only for `needs-fix`.
`strict` exits nonzero for `needs-review` and `needs-fix`. The gate can also read a metadata-only
CI receipt with `--receipt REVIEW_AGENT_CI_RECEIPT.json`. It emits
`cognitive-loop-review-agent-policy-gate-v1` and must not include raw diffs, file bodies, finding
evidence, report summaries, Agent endpoint secrets, real model keys, or hidden chain-of-thought.
