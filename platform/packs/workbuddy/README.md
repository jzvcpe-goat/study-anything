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

Before importing into a real workspace, prove the repo works from a disposable checkout:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
```

For release or workspace handoff acceptance, verify the distributable adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The verifier emits `adoption-proof-v1` and proves the WorkBuddy-style HTTP tool path without
requiring a standalone frontend.

For a scenario-based operator guide, read `docs/cognitive-loop-adoption-cookbook.md`. It shows how a
WorkBuddy-style platform Agent HTTP workspace can call the local API and local Cognitive Loop
commands while sharing only redacted artifact metadata back into the workspace.

For project memory handoff, run `python3 scripts/cognitive_loop_event_store.py rebuild` locally and
share only the `python3 scripts/cognitive_loop_event_store.py export --html` metadata report with the
workspace. The verifier is `python3 scripts/verify_cognitive_loop_event_store.py --check`.

For a WorkBuddy workspace that owns a Mastra runtime, expose `platform/mastra/` as a static adapter
pack. The template maps Cognitive Loop Human Mastery Gate state to Mastra suspend/resume/bail while
keeping raw source text and model keys outside Study Anything.
Run `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` before promoting that
workspace from adapter experiment to connected runtime.
With Node 22+, run `python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` to
verify the repo-local Mastra MVP against the same metadata-only workflow contract.
Then run `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` to prove local
libSQL suspend/resume or bail across separate Node processes from watcher-generated metadata events.
Then run `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` and inspect
`platform/generated/study-anything-cognitive-loop-langfuse-observability.json` before enabling real
observability. The verifier maps Mastra receipts to redacted Langfuse trace/span/generation/score
DTOs and keeps raw source, learner answers, Agent endpoints, prompts, model keys, storage paths, and
absolute local paths out of the local receipt.
Then run `python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` and inspect
`platform/generated/study-anything-cognitive-loop-study-anything-adapter.json` before promoting the
Learning Adapter integration. The verifier proves metadata-only `ProjectEvent` / `DecisionCard`
input can create a source-bound Study Anything learning context and project `MasteryRecord` /
`LoopRun` evidence without source bodies, raw diffs, learner answers, Agent endpoints, Agent
metadata, or model keys.

For machine-readable operation, import
`platform/generated/study-anything-cognitive-loop-adoption-recipes.json`, then read
`platform/generated/study-anything-cognitive-loop-recipe-replay.json` before running runtime or
human-gated steps. The entrypoint proof is
`platform/generated/study-anything-cognitive-loop-skill-entrypoint.json`. Verify the WorkBuddy
entrypoint chain locally with:

```bash
python3 scripts/verify_cognitive_loop_adoption_cookbook.py --check
python3 scripts/generate_cognitive_loop_adoption_recipes.py --check
python3 scripts/verify_cognitive_loop_recipe_replay.py --check
python3 scripts/verify_cognitive_loop_skill_entrypoint.py --check
python3 scripts/verify_cognitive_loop_recipe_cli.py --check
python3 scripts/verify_cognitive_loop_recipe_cli_receipts.py --check
python3 scripts/verify_cognitive_loop_recipe_cli_failures.py --check
python3 scripts/verify_cognitive_loop_recipe_cli_schemas.py --check
python3 scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py --check
python3 scripts/verify_cognitive_loop_schema_pack_consumer.py --check
python3 scripts/verify_cognitive_loop_schema_pack_consumer_failures.py --check
python3 scripts/verify_cognitive_loop_pack_extract_smoke.py --check
python3 scripts/verify_platform_handoff_checklist.py --check
python3 scripts/verify_launch_acceptance_ledger.py --check
python3 scripts/verify_github_launch_operator_guide.py --check
python3 scripts/cognitive_loop_recipe_cli.py list
python3 scripts/cognitive_loop_recipe_cli.py show risk_decision
```

`platform/generated/study-anything-cognitive-loop-recipe-cli.json` proves the read-only recipe CLI
returns `cognitive-loop-recipe-cli-v1` plans without executing recipe commands.
`platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json` provides deterministic
sample CLI outputs and hashes for platform Agent import tests.
`platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json` provides deterministic
failure receipts for unknown ids and invalid recipe matrices.
`platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json` provides offline JSON
Schemas for static WorkBuddy validation of the success, receipt, and failure reports.
`platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json` proves
those schemas reject drift, unsafe flags, malformed types, and private text probes.
`platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json` proves those assets are
discoverable and hash-checked from the adoption pack zip without a repo checkout.
`platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json` proves tampered or policy-violating adoption pack variants fail safely without persisted mutated payloads.
`platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json` proves the extracted
adoption pack can run its bundled schema consumer checks without a Study Anything runtime.
`platform/generated/study-anything-platform-handoff-checklist.json` gives WorkBuddy-style operators a
release handoff checklist for import, verification, runtime choice, and support escalation.
`platform/generated/study-anything-launch-acceptance-ledger.json` gives WorkBuddy-style operators the
aggregated launch acceptance state and current commercial boundary.
`platform/generated/study-anything-github-launch-operator-guide.json` gives WorkBuddy-style operators
the GitHub release sequence, required release assets, and local-first launch boundary.

For code-review acceptance, the WorkBuddy-style workspace can pass a temporary handoff request to its
private Review Agent, then validate the JSON response locally:

```bash
python3 scripts/cognitive_loop_review_agent_handoff.py prepare --base main --head HEAD > /tmp/workbuddy-review-handoff.json
python3 scripts/cognitive_loop_review_agent_handoff.py validate --report /tmp/workbuddy-review-report.json
python3 scripts/cognitive_loop_review_agent_receipt.py build --report /tmp/workbuddy-review-report.json --provider-id workbuddy-review-agent --pr-ref PR --commit-sha SHA --output /tmp/workbuddy-review-receipt.json
python3 scripts/cognitive_loop_review_agent_pr_comment.py build --receipt /tmp/workbuddy-review-receipt.json
python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py build --report /tmp/workbuddy-review-report.json --provider-id workbuddy-review-agent --pr-ref PR --commit-sha SHA --output-dir /tmp/workbuddy-review-acceptance
python3 scripts/verify_cognitive_loop_review_agent_handoff_cli.py --check
python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check
python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check
python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check
python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir /tmp/workbuddy-review-acceptance --policy soft
python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check
python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
python3 scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check
```

For GitHub-side reuse, copy `platform/workflows/cognitive-loop-review-agent-manual.yml` only as a
manual `workflow_dispatch` workflow after the external WorkBuddy report path is clear. It writes a
metadata-only Checks summary, runs the built-in `advisory` / `soft` / `strict` policy gate,
uploads only safe metadata artifacts when enabled, and must not upload the raw Review Agent report.
The workflow applies the captured policy exit code after artifact upload so WorkBuddy evidence is
available even when `needs-fix` or `needs-review` blocks CI. The install smoke proves the same
workflow and policy gate can be copied from the adoption pack into `.github/workflows/` without
requiring a repo checkout or raw report upload. The adoption drill rehearses the full zip-only path
from acceptance bundle to PR comment pack, policy matrix, and workflow install.

## Runtime Boundary

The workspace Agent should own:

- browser and app operation
- files and external data
- video or document extraction
- user-facing conversation
- model credentials

Study Anything should own:

- deployment-guide-v1 launch guidance and first-run diagnostic boundaries
- commercial-readiness-v1 launch boundaries, hosted-service contracts, and local-first invariants
- ecosystem-submission-v1 metadata for no-frontend platform submission
- ecosystem-submission-verification-v1 evidence for privacy and high-risk endpoint exclusions
- source-bound learning state
- Learning Context Package validation and import
- Plugin SDK contract, capability index, and local package validation
- confirmed local importer runtime
- optional retrieval projection and retrieval-to-session flows
- quiz, grading, mastery, scribe, HITL
- redacted Agent audit and eval artifacts

## Local Acceptance

Against a running API, verify the imported tool surface and redacted evidence:

```bash
curl http://127.0.0.1:8000/v1/deployment/guide
curl http://127.0.0.1:8000/v1/commercial/readiness
curl http://127.0.0.1:8000/v1/evals/policy
python3 scripts/verify_commercial_readiness.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_importer_runtime_retrieval_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool report --create-session --required
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

If the workspace also wants a copy-ready user-owned HTTP Agent example, use the OpenAI-compatible
gateway dry-run before replacing it with the workspace's private Agent endpoint:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

If setup fails, run the adoption diagnostics before changing workspace configuration:

```bash
python3 scripts/diagnose_adoption.py
```

## Acceptance

After every completed learning loop, the workspace Agent should fetch:

```text
GET /v1/evals/policy
GET /v1/commercial/readiness
GET /v1/adoption/telemetry
GET /v1/pmf/readiness
GET /v1/sessions/{session_id}/agent-audit
GET /v1/sessions/{session_id}/agent-eval/artifact
GET /v1/sessions/{session_id}/agent-eval/quality
GET /v1/sessions/{session_id}/agent-eval/report
GET /v1/sessions/{session_id}/exports/enrichment-artifact
GET /v1/sessions/{session_id}/exports/obsidian
GET /v1/sessions/{session_id}/exports/learning-package
GET /v1/sessions/{session_id}/exports/second-brain-handoff
```

The commercial readiness response is `commercial-readiness-v1`, which marks the local OSS and
platform-Agent launch path ready while keeping hosted paid services, billing, SSO, remote accounts,
and standalone app work out of scope. The enrichment artifact is a redacted Markdown+HTML
micro-lesson for the workspace conversation. The Obsidian Markdown export is for the user's
second-brain workflow. The learning package is for platform-agent handoff, NotebookLM-style bridges,
or local archives. The second-brain handoff is the preferred shared workspace export because it
excludes learner answers and grading feedback. The shared run summary should include only compact
mastery and redacted evidence, not raw source prose or learner answers.
`adoption-telemetry-v1` and `pmf-readiness-v1` add aggregate local adoption and PMF evidence without
source text, answers, insights, raw user ids, Agent endpoints, API keys, or browser/video/app private
context.

Use `POST /v1/context-packages/validate`, `POST /v1/sessions/from-context-package`, and
`POST /v1/sessions/{session_id}/context-package` when WorkBuddy has collected browser pages,
documents, app context, Markdown/Obsidian notes, or video slices before the learning loop. The older
`POST /v1/sessions/{session_id}/enrichment` endpoint remains available for simple one-off excerpts.

If the workspace uses a reviewed local importer plugin, call `POST /v1/importers/{plugin_id}/run` with
exact permission confirmation, then import the returned package. Keep `allow_network=false` unless the
user explicitly approves the importer's `network:http` permission.
Before installation or invocation, call `GET /v1/plugins/sdk`, `GET /v1/plugins/capabilities`, and
`POST /v1/plugins/validate-package`. These endpoints do not copy plugin packages or execute
entrypoints.

If optional retrieval is healthy, call `POST /v1/sessions/{session_id}/retrieval/rebuild`, then
`POST /v1/sessions/{session_id}/retrieval/search`, call
`POST /v1/sessions/{session_id}/retrieval/eval` for redacted retrieval/context quality gates, and use
`POST /v1/sessions/from-retrieval` to start a focused follow-up lesson from minimal snippets.
