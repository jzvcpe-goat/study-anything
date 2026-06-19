# Kimi Pack

Use this pack in two ways:

1. Import Study Anything learning tools into a Kimi-compatible function-calling environment.
2. Use Kimi as the user-owned reasoning model behind the local HTTP Agent gateway.

Browser-only Kimi chat cannot call `127.0.0.1` directly. A terminal, workspace Agent, or private
gateway must make the local HTTP calls.

## Tool Import

Use one of:

```text
platform/generated/study-anything-openai-tools.json
platform/generated/study-anything-platform-openapi.json
```

Set the API base to:

```text
http://127.0.0.1:8000
```

The tool surface includes:

- `study_anything_deployment_guide` for `deployment-guide-v1`, the redacted first-run launch and
  diagnostics guide.
- `study_anything_commercial_readiness` for `commercial-readiness-v1`, the OSS/local-first launch
  boundary and hosted-service non-goals.
- `platform/ecosystem-submission.json` for `ecosystem-submission-v1`, the submission-ready
  metadata that keeps Kimi as the conversation surface while Study Anything remains a local engine.
- `study_anything_health` for local API reachability.
- `study_anything_eval_policy` for `agent-eval-policy-v1`, the native release gate, optional
  external adapter policy, and failure classes.
- `study_anything_plugin_sdk` for the machine-readable Plugin SDK contract.
- `study_anything_plugin_capabilities` for installed plugin hooks, capabilities, and trust summaries.
- `study_anything_validate_plugin_package` for local plugin package validation before install.
- `study_anything_run_importer` for confirmed local importer runtime.
- `study_anything_validate_context_package` for Learning Context Package checks before import.
- `study_anything_create_session_from_context_package` for creating a session from Kimi-collected context.
- `study_anything_append_context_package` for expanding an existing session with new context.
- `study_anything_retrieval_status`, `study_anything_retrieval_rebuild`, and
  `study_anything_retrieval_search` for optional retrieval projection.
- `study_anything_retrieval_quality_eval` for redacted retrieval/context quality gates.
- `study_anything_create_session_from_retrieval` and `study_anything_append_retrieval_context` for
  turning retrieval results into a focused lesson.
- `study_anything_add_enrichment` for web/document/PDF/video-slice/app-context/Markdown/Obsidian excerpts gathered by Kimi or the platform agent.
- `study_anything_agent_quality_eval` for the minimum teaching-quality gate.
- `study_anything_agent_eval_report` for the per-session maturity report proving invocation,
  trajectory, teaching quality, export readiness, privacy, and external adapter readiness.
- `study_anything_enrichment_artifact_export` for a redacted Markdown+HTML micro-lesson Kimi can use in the conversation.
- `study_anything_obsidian_export` for a copy-ready Obsidian Markdown note.
- `study_anything_learning_package_export` for a portable package that a platform agent can pass into
  NotebookLM-style or local knowledge workflows.
- `study_anything_second_brain_handoff_export` for the strict redacted Obsidian, NotebookLM-style,
  and local archive handoff Kimi should prefer for long-term memory.

Run the clean-clone adoption smoke before wiring real credentials:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
```

For release or handoff acceptance, use the distributable adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The verifier emits `adoption-proof-v1` and proves the Kimi-compatible tool surface without requiring
browser-only Kimi to call localhost directly.

For a shorter operating path, read `docs/cognitive-loop-adoption-cookbook.md`. In Kimi workflows it
keeps Kimi as the conversation surface while a terminal, workspace Agent, or private gateway runs the
local Cognitive Loop commands and returns only redacted artifact metadata.

When a local event ledger is useful, the terminal or workspace Agent can run
`python3 scripts/cognitive_loop_event_store.py rebuild` and
`python3 scripts/cognitive_loop_event_store.py export --html`; Kimi should receive only the exported
metadata summary, not the SQLite file or private source artifacts. Verify with
`python3 scripts/verify_cognitive_loop_event_store.py --check`.

If Kimi is coordinating an external Mastra workspace, import `platform/mastra/README.md`,
`platform/mastra/manifest.json`, and `platform/mastra/cognitive-loop-mastra-adapter.ts` as the
Mastra-side adapter contract. Verify the pack with
`python3 scripts/verify_cognitive_loop_mastra_adapter.py --check`.
Then run `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` to prove the
metadata-only suspend/resume/bail contract before Kimi tells a user the external runtime is ready.
If the local workspace has Node 22+, run
`python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` to start the repo-local
Mastra MVP and verify the same workflow through `@mastra/core`.
Then run `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` to prove local
libSQL suspend/resume or bail across separate Node processes from watcher-generated metadata events.
Then run `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` and inspect
`platform/generated/study-anything-cognitive-loop-langfuse-observability.json` before enabling real
observability. The verifier maps Mastra receipts to redacted Langfuse trace/span/generation/score
DTOs and keeps raw source, learner answers, Agent endpoints, prompts, model keys, storage paths, and
absolute local paths out of the local receipt.
Then run `python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` and inspect
`platform/generated/study-anything-cognitive-loop-study-anything-adapter.json` before telling a user
that the Learning Adapter is connected. The verifier proves metadata-only `ProjectEvent` /
`DecisionCard` input can create a source-bound Study Anything learning context and project
`MasteryRecord` / `LoopRun` evidence without source bodies, raw diffs, learner answers, Agent
endpoints, Agent metadata, or model keys.
Then run `.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html`
and inspect `platform/generated/study-anything-cognitive-loop-study-adapter-cli.json` before wiring
this into a Kimi Work action. The CLI Lite writes JSON/HTML learning status, StudyCard, understanding
gaps, scribe summary, `MasteryRecord`, and `LoopRun` evidence from metadata-only files.
The pack includes `scripts/cognitive_loop_study_adapter_cli.py` and
`scripts/verify_cognitive_loop_study_adapter_cli.py` for this handoff.

For bounded local watcher automation, run
`.venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter --changed-path apps/api/study_anything/core/workflow.py --git-diff-summary "Metadata-only workflow boundary changed"`.
This runner reads `.cognitive-loop/watchers.yaml`, debounces duplicate paths, skips excluded
paths, writes metadata-only ProjectEvents into the local Event Store, and can trigger the Study
Anything adapter gate for the first high-risk event. Verify it with
`.venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-watcher-runner.json`.

For a static HTML Artifact Console Lite, run
`python3 scripts/cognitive_loop_artifact_console.py build --html --json`.
It aggregates Event Store rows, watcher runner summaries, Study Adapter outputs, and
DecisionCard/Human Gate/LoopRun metadata into `.cognitive-loop/artifacts/console/index.html`
without a daemon, standalone frontend, SSE, WebSocket, raw diffs, source bodies, learner answers,
Agent endpoints, Agent metadata, prompts, or model keys. Verify it with
`python3 scripts/verify_cognitive_loop_artifact_console.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-artifact-console.json`.

For Personal Plugin Mode Lite, run
`python3 scripts/cognitive_loop_personal_mode.py explain --file README.md --html --markdown --json`.
It creates read-only metadata-only Study Cards, quiz items, and Markdown/HTML reports for a file,
README, webpage metadata, or diff summary without modifying source files or storing raw source or
diff text, learner answers, Agent endpoints, Agent metadata, prompts, or model keys. Verify it with
`python3 scripts/verify_cognitive_loop_personal_plugin_mode.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-personal-plugin-mode.json`.

For Evolution Report Lite, run
`python3 scripts/cognitive_loop_evolution.py build --html --json`.
It clusters metadata-only failures, proposes governed next-loop improvements, requires a Human
Mastery Gate for high-risk suggestions, and writes JSON/HTML reports without modifying source files
or weakening risk, audit, privacy, rollback, test, or permission policy. Verify it with
`python3 scripts/verify_cognitive_loop_evolution_report.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-evolution-report.json`.

For Governed Apply Plan Lite, run
`python3 scripts/cognitive_loop_apply_plan.py plan --proposal .cognitive-loop/artifacts/evolution/evolution-report-lite.json --html --json`.
It is dry-run by default and only writes an idempotent generated-artifact receipt when explicitly
called with `--apply --allow-generated-artifacts`; it never writes source files, docs, scripts,
platform packs, policy files, raw source, raw diff, learner answers, Agent endpoints, Agent
metadata, prompts, or model keys. Verify it with
`python3 scripts/verify_cognitive_loop_apply_plan.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-apply-plan.json`.

For Measured Improvement Comparator Lite, a terminal or workspace Agent can run
`python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json`.
It compares metadata-only loop artifacts, classifies `improved`, `regressed`, `unchanged`,
`insufficient`, or `ambiguous`, and never calls models, executes apply, modifies source files, or
stores raw source, raw diff, learner answers, Agent endpoints, Agent metadata, prompts, or model
keys. Verify it with `python3 scripts/verify_cognitive_loop_improvement_comparator.py --check`, then
share only `platform/generated/study-anything-cognitive-loop-improvement-comparison.json` metadata
back to Kimi.

For Patch Proposal Lite, a terminal or workspace Agent can run
`python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json`.
It turns metadata-only loop evidence into six patch specification categories: `prompt`, `policy`,
`eval`, `task`, `doc`, and `retrieval`. It is read-only: high-risk, gated, manual-only, protected
path, insufficient, secret-like, raw-diff, and policy-weakening inputs are rejected or downgraded to
manual-only, and it never generates raw unified diffs, calls models, executes apply, modifies source
files, or stores private learning data. Verify it with
`python3 scripts/verify_cognitive_loop_patch_proposal.py --check`, then share only
`platform/generated/study-anything-cognitive-loop-patch-proposal.json` metadata back to Kimi.

For Mastra Evolution Receipt Link Lite, a terminal or workspace Agent can run
`python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json`.
It links metadata-only Evolution Report, Apply Plan, Improvement Comparison, and Patch Proposal
artifacts into a future Mastra workflow receipt DTO. It does not start Mastra, call models, execute
apply, generate raw unified diffs, modify source files, or store private learning data. Verify it
with `python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check`, then share only
`platform/generated/study-anything-cognitive-loop-mastra-evolution-receipt.json` metadata back to
Kimi.

For Mastra Evolution Workflow Replay Lite, a terminal or workspace Agent can run
`python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json`.
It replays a metadata-only EvolutionReceiptLink into future Mastra workflow steps for evidence
validation, human gate evaluation, patch review, apply-plan review, and observability receipt
handoff. It does not start production Mastra, call models, execute apply, modify source files, or
store private learning data. Verify it with
`python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check`, then share only
`platform/generated/study-anything-cognitive-loop-mastra-evolution-replay.json` metadata back to
Kimi.

For machine-readable operation, import
`platform/generated/study-anything-cognitive-loop-adoption-recipes.json`, then read
`platform/generated/study-anything-cognitive-loop-recipe-replay.json` before a terminal or workspace
Agent runs runtime or human-gated steps. The entrypoint proof is
`platform/generated/study-anything-cognitive-loop-skill-entrypoint.json`. The local operator should
verify the entrypoint chain with:

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
Schemas for static Kimi validation of the success, receipt, and failure reports.
`platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json` proves
those schemas reject drift, unsafe flags, malformed types, and private text probes.
`platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json` proves those assets are
discoverable and hash-checked from the adoption pack zip without a repo checkout.
`platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json` proves tampered or policy-violating adoption pack variants fail safely without persisted mutated payloads.
`platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json` proves the extracted
adoption pack can run its bundled schema consumer checks without a Study Anything runtime.
`platform/generated/study-anything-platform-handoff-checklist.json` gives Kimi operators a release
handoff checklist for import, verification, runtime choice, and support escalation.
`platform/generated/study-anything-launch-acceptance-ledger.json` gives Kimi operators the
aggregated launch acceptance state and current commercial boundary.
`platform/generated/study-anything-github-launch-operator-guide.json` gives Kimi operators the
GitHub release sequence, required release assets, and local-first launch boundary.

For code-review acceptance, use Kimi as the external Review Agent only through an operator-approved
handoff. The local command creates a temporary request with the real diff; Study Anything should not
persist that request:

```bash
python3 scripts/cognitive_loop_review_agent_handoff.py prepare --base main --head HEAD > /tmp/kimi-review-handoff.json
```

Paste or attach `/tmp/kimi-review-handoff.json` to Kimi, require JSON-only output, then validate the
returned report:

```bash
python3 scripts/cognitive_loop_review_agent_handoff.py validate --report /tmp/kimi-review-report.json
python3 scripts/cognitive_loop_review_agent_receipt.py build --report /tmp/kimi-review-report.json --provider-id kimi-review-agent --pr-ref PR --commit-sha SHA --output /tmp/kimi-review-receipt.json
python3 scripts/cognitive_loop_review_agent_pr_comment.py build --receipt /tmp/kimi-review-receipt.json
python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py build --report /tmp/kimi-review-report.json --provider-id kimi-review-agent --pr-ref PR --commit-sha SHA --output-dir /tmp/kimi-review-acceptance
python3 scripts/verify_cognitive_loop_review_agent_handoff_cli.py --check
python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check
python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check
python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check
python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir /tmp/kimi-review-acceptance --policy soft
python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check
python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
python3 scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check
```

For GitHub-side reuse, copy `platform/workflows/cognitive-loop-review-agent-manual.yml` only as a
manual `workflow_dispatch` workflow after the external Kimi report path is clear. It writes a
metadata-only Checks summary, runs the built-in `advisory` / `soft` / `strict` policy gate,
uploads only safe metadata artifacts when enabled, and must not upload the raw Review Agent report.
The workflow applies the captured policy exit code after artifact upload so Kimi evidence is
available even when `needs-fix` or `needs-review` blocks CI. The install smoke proves the same
workflow and policy gate can be copied from the adoption pack into `.github/workflows/` without
requiring a repo checkout or raw report upload. The adoption drill rehearses the full zip-only path
from acceptance bundle to PR comment pack, policy matrix, and workflow install.

## Kimi As Reasoning Agent

First verify the same gateway entrypoint without a real key:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

Then switch the gateway to real Kimi credentials:

```bash
export AGENT_LLM_BASE_URL="https://api.moonshot.cn/v1"
export AGENT_LLM_API_KEY="$MOONSHOT_API_KEY"
export AGENT_LLM_MODEL="${AGENT_LLM_MODEL:-kimi-k2.6}"

python3 scripts/openai_compatible_agent_gateway.py --host 127.0.0.1 --port 8787
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My Kimi gateway" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default
```

Keep Moonshot/Kimi credentials in the gateway environment, not in Study Anything. The default
`agent-add-http --set-default` command registers teaching layers, quiz generation, grading, synthesis,
scribe notes, source verification, and embedding tasks.

## Acceptance

After a completed learning loop, the platform Agent should fetch:

```text
GET /v1/evals/policy
GET /v1/commercial/readiness
GET /v1/sessions/{session_id}/agent-audit
GET /v1/sessions/{session_id}/agent-eval/artifact
GET /v1/sessions/{session_id}/agent-eval/quality
GET /v1/sessions/{session_id}/agent-eval/report
GET /v1/sessions/{session_id}/exports/enrichment-artifact
GET /v1/sessions/{session_id}/exports/obsidian
GET /v1/sessions/{session_id}/exports/learning-package
GET /v1/sessions/{session_id}/exports/second-brain-handoff
```

The commercial readiness response is `commercial-readiness-v1`: GitHub OSS, self-host, and
platform-Agent distribution are ready; hosted paid services, billing, SSO, remote accounts, and a
standalone app are not part of this alpha. The exports include a redacted enrichment micro-lesson, a
user-owned Obsidian Markdown note, a portable learning package, and the strict second-brain handoff.
Prefer the second-brain handoff for Kimi-visible long-term memory because it excludes learner answers
and grading feedback.
The ecosystem submission verifier returns `ecosystem-submission-verification-v1` and proves the Kimi
pack has no standalone frontend requirement, no Study Anything model-key custody, and no high-risk
management endpoints in the imported tool surface.
`GET /v1/adoption/telemetry` returns `adoption-telemetry-v1` and `GET /v1/pmf/readiness` returns
`pmf-readiness-v1`; use them for aggregate local adoption evidence and PMF review without logging
source text, answers, insights, raw user ids, Agent endpoints, API keys, or browser/video/app private
context.

For importer flows, Kimi or the surrounding platform Agent should first build a
`learning-context-package-v1` object from user-approved web pages, files, video slices, workspace
context, Markdown notes, or Obsidian notes. Validate it with `POST /v1/context-packages/validate`,
then create or expand a session with the context-package session tools. Do not store Kimi credentials
or raw model secrets in the package.

When a local importer plugin is installed and reviewed, Kimi-compatible platforms can call
`POST /v1/importers/{plugin_id}/run` instead of hand-building the package. Confirm every manifest
permission exactly. Leave `allow_network=false` unless the surrounding platform Agent has explicitly
reviewed the importer and accepted `network:http`.
Before proposing a plugin install, call `GET /v1/plugins/sdk`, `GET /v1/plugins/capabilities`, and
`POST /v1/plugins/validate-package`; these are metadata-only and never execute plugin entrypoints.

For retrieval-based follow-up lessons, first check `GET /v1/retrieval/status`. If it is healthy, rebuild
the source session index, search for the focus query, and create a new lesson with
`POST /v1/sessions/from-retrieval`. Then call `POST /v1/sessions/{session_id}/retrieval/eval` against
the indexed source session to prove retrieval/context quality without logging snippets. Browser-only
Kimi still needs a terminal, workspace Agent, or private gateway to make localhost calls.

For quality-gate smoke, run:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_importer_runtime_retrieval_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
python3 scripts/verify_adoption_telemetry.py --api-base http://127.0.0.1:8000
```

Share only compact mastery and redacted evidence. Do not log raw source text, learner answers,
grading feedback, Agent endpoints, or model secrets.

## Troubleshooting

```bash
python3 scripts/diagnose_adoption.py --agent-endpoint http://127.0.0.1:8787/invoke
```

If browser-only Kimi cannot call localhost, move the HTTP calls to a terminal-capable Agent, local
gateway, or authenticated private gateway.
