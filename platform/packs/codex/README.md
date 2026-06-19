# Codex Pack

Use this pack when the platform Agent can run shell commands in this repository.

## Install

Expose the repo-local skill to Codex:

```bash
ln -s "$(pwd)/skills/study-anything" "${CODEX_HOME:-$HOME/.codex}/skills/study-anything"
```

For release or external handoff acceptance, verify the distributable adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The verifier emits `adoption-proof-v1` and proves that a terminal-capable platform Agent can complete
the learning loop, eval gates, Obsidian export, and NotebookLM-style handoff without a standalone
frontend.

For Cognitive Loop operations, start from `docs/cognitive-loop-adoption-cookbook.md`. It maps Codex
to local Cognitive Loop commands for first adoption, daily project review, risk decisions, and
learning handoff without adding a standalone frontend.

For local event memory, run `python3 scripts/cognitive_loop_event_store.py rebuild` after generating
`.cognitive-loop/events/*.json`, then run `python3 scripts/cognitive_loop_event_store.py export --html`.
Verify the SQLite metadata-only path with `python3 scripts/verify_cognitive_loop_event_store.py --check`.

For Mastra orchestration experiments, copy `platform/mastra/cognitive-loop-mastra-adapter.ts`
into an external Mastra project and keep Study Anything as the metadata source. Verify the
contract pack with `python3 scripts/verify_cognitive_loop_mastra_adapter.py --check`.
Then run `python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check` to rehearse
high-risk suspend, approved resume, rejected bail, and Event Store projection before claiming
a real Mastra runtime is connected.
When Node 22+ is available, run
`python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check` to start the repo-local
Mastra MVP and verify the same metadata-only workflow against `@mastra/core`.
Then run `python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check` to prove local
libSQL suspend/resume or bail across separate Node processes from watcher-generated metadata events.
Then run `python3 scripts/verify_cognitive_loop_langfuse_observability.py --check` and inspect
`platform/generated/study-anything-cognitive-loop-langfuse-observability.json` before enabling real
observability. The verifier maps Mastra receipts to redacted Langfuse trace/span/generation/score
DTOs and keeps raw source, learner answers, Agent endpoints, prompts, model keys, storage paths, and
absolute local paths out of the local receipt.
Then run `python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check` and inspect
`platform/generated/study-anything-cognitive-loop-study-anything-adapter.json` before claiming the
learning adapter is wired. The verifier proves metadata-only `ProjectEvent` / `DecisionCard` input
can create a source-bound Study Anything learning context and project `MasteryRecord` / `LoopRun`
evidence without source bodies, raw diffs, learner answers, Agent endpoints, Agent metadata, or model
keys.
Then run `.venv/bin/python scripts/cognitive_loop_cli.py study-adapter --event fixtures/cognitive-loop-study-adapter/project-event.json --decision fixtures/cognitive-loop-study-adapter/decision-card.json --html`
and inspect `platform/generated/study-anything-cognitive-loop-study-adapter-cli.json` before exposing
the bridge to a platform Agent. The CLI Lite writes JSON/HTML learning status, StudyCard,
understanding gaps, scribe summary, `MasteryRecord`, and `LoopRun` evidence from metadata-only files.
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

For Measured Improvement Comparator Lite, run
`python3 scripts/cognitive_loop_improvement_comparator.py compare --artifact previous.json --artifact current.json --html --json`.
It compares metadata-only loop artifacts, classifies `improved`, `regressed`, `unchanged`,
`insufficient`, or `ambiguous`, and never calls models, executes apply, modifies source files, or
stores raw source, raw diff, learner answers, Agent endpoints, Agent metadata, prompts, or model
keys. Verify it with `python3 scripts/verify_cognitive_loop_improvement_comparator.py --check`, then
inspect `platform/generated/study-anything-cognitive-loop-improvement-comparison.json`.

For Patch Proposal Lite, run
`python3 scripts/cognitive_loop_patch_proposal.py build --artifact evidence.json --html --json`.
It turns metadata-only loop evidence into six patch specification categories: `prompt`, `policy`,
`eval`, `task`, `doc`, and `retrieval`. It is read-only: high-risk, gated, manual-only, protected
path, insufficient, secret-like, raw-diff, and policy-weakening inputs are rejected or downgraded to
manual-only, and it never generates raw unified diffs, calls models, executes apply, modifies source
files, or stores private learning data. Verify it with
`python3 scripts/verify_cognitive_loop_patch_proposal.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-patch-proposal.json`.

For Mastra Evolution Receipt Link Lite, run
`python3 scripts/cognitive_loop_mastra_evolution_receipt.py build --artifact evidence.json --html --json`.
It links metadata-only Evolution Report, Apply Plan, Improvement Comparison, and Patch Proposal
artifacts into a future Mastra workflow receipt DTO. It does not start Mastra, call models, execute
apply, generate raw unified diffs, modify source files, or store private learning data. Verify it
with `python3 scripts/verify_cognitive_loop_mastra_evolution_receipt.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-mastra-evolution-receipt.json`.

For Mastra Evolution Workflow Replay Lite, run
`python3 scripts/cognitive_loop_mastra_evolution_replay.py replay --receipt .cognitive-loop/artifacts/mastra/mastra-evolution-receipt-link.json --html --json`.
It replays a metadata-only EvolutionReceiptLink into future Mastra workflow steps for evidence
validation, human gate evaluation, patch review, apply-plan review, and observability receipt
handoff. It does not start production Mastra, call models, execute apply, modify source files, or
store private learning data. Verify it with
`python3 scripts/verify_cognitive_loop_mastra_evolution_replay.py --check`, then inspect
`platform/generated/study-anything-cognitive-loop-mastra-evolution-replay.json`.

For machine-readable operation, import
`platform/generated/study-anything-cognitive-loop-adoption-recipes.json`, then read
`platform/generated/study-anything-cognitive-loop-recipe-replay.json` before running runtime or
human-gated steps. The entrypoint proof is
`platform/generated/study-anything-cognitive-loop-skill-entrypoint.json`. Verify the Skill
entrypoint and recipe path together:

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
Schemas for static platform-Agent validation of the success, receipt, and failure reports.
`platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json` proves
those schemas reject drift, unsafe flags, malformed types, and private text probes.
`platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json` proves those assets are
discoverable and hash-checked from the adoption pack zip without a repo checkout.
`platform/generated/study-anything-cognitive-loop-schema-pack-consumer-failures.json` proves tampered or policy-violating adoption pack variants fail safely without persisted mutated payloads.
`platform/generated/study-anything-cognitive-loop-pack-extract-smoke.json` proves the extracted
adoption pack can run its bundled schema consumer checks without a Study Anything runtime.
`platform/generated/study-anything-platform-handoff-checklist.json` gives Codex operators a release
handoff checklist for import, verification, runtime choice, and support escalation.
`platform/generated/study-anything-launch-acceptance-ledger.json` gives Codex operators the
aggregated launch acceptance state and current commercial boundary.
`platform/generated/study-anything-github-launch-operator-guide.json` gives Codex operators the
GitHub release sequence, required release assets, and local-first launch boundary.

For external code-review acceptance, keep Codex as the platform Agent and use the handoff CLI as the
privacy boundary. `prepare` emits the raw diff only as operator material; `validate` converts the
external Agent's JSON report into a redacted summary:

```bash
python3 scripts/cognitive_loop_review_agent_handoff.py prepare --base main --head HEAD > /tmp/codex-review-handoff.json
python3 scripts/cognitive_loop_review_agent_handoff.py validate --report /tmp/codex-review-report.json
python3 scripts/cognitive_loop_review_agent_receipt.py build --report /tmp/codex-review-report.json --provider-id codex-review-agent --pr-ref PR --commit-sha SHA --output /tmp/codex-review-receipt.json
python3 scripts/cognitive_loop_review_agent_pr_comment.py build --receipt /tmp/codex-review-receipt.json
python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py build --report /tmp/codex-review-report.json --provider-id codex-review-agent --pr-ref PR --commit-sha SHA --output-dir /tmp/codex-review-acceptance
python3 scripts/verify_cognitive_loop_review_agent_handoff_cli.py --check
python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check
python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check
python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check
python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir /tmp/codex-review-acceptance --policy soft
python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check
python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
python3 scripts/verify_cognitive_loop_review_agent_adoption_drill.py --check
```

For GitHub-side reuse, copy `platform/workflows/cognitive-loop-review-agent-manual.yml` only as a
manual `workflow_dispatch` workflow after the external report path is clear. It writes a
metadata-only Checks summary, runs the built-in `advisory` / `soft` / `strict` policy gate,
uploads only safe metadata artifacts when enabled, and must not upload the raw Review Agent report.
The workflow applies the captured policy exit code after artifact upload so Codex evidence is
available even when `needs-fix` or `needs-review` blocks CI. The install smoke proves the same
workflow and policy gate can be copied from the adoption pack into `.github/workflows/` without
requiring a repo checkout or raw report upload. The adoption drill rehearses the full zip-only path
from acceptance bundle to PR comment pack, policy matrix, and workflow install.

## Run

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
python3 scripts/verify_commercial_readiness.py
python3 scripts/verify_cognitive_loop_skill_entrypoint.py --check
python3 scripts/verify_cognitive_loop_recipe_cli.py --check
python3 scripts/verify_cognitive_loop_recipe_cli_receipts.py --check
python3 scripts/verify_cognitive_loop_recipe_cli_failures.py --check
./scripts/run_skill_mode_demo.sh
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
./scripts/launch_skill_mode.sh
curl http://127.0.0.1:8000/v1/deployment/guide
python3 scripts/study_anything_cli.py commercial-readiness
python3 scripts/study_anything_cli.py eval-policy
python3 scripts/study_anything_cli.py demo
python3 scripts/study_anything_cli.py context-validate \
  fixtures/notebooklm/notebooklm-style-context-package.json
python3 scripts/study_anything_cli.py plugin-sdk
python3 scripts/study_anything_cli.py plugin-capabilities
python3 scripts/study_anything_cli.py plugin-validate plugins/example-exporter
python3 scripts/study_anything_cli.py context-import \
  fixtures/notebooklm/notebooklm-style-context-package.json --session
python3 scripts/study_anything_cli.py importer-run example-note-importer \
  --confirm-permission write:context \
  --input-json '{"note_reference":"obsidian://Study Anything/Lesson","title":"Learning notes","markdown_excerpt":"Paste bounded note context here."}' \
  --create-session --session
python3 scripts/study_anything_cli.py retrieval-status
python3 scripts/study_anything_cli.py retrieval-rebuild SESSION_ID
python3 scripts/study_anything_cli.py retrieval-search SESSION_ID --query "focus topic"
python3 scripts/study_anything_cli.py retrieval-eval SESSION_ID --query "focus topic"
python3 scripts/study_anything_cli.py retrieval-import \
  --source-session-id SESSION_ID \
  --query "focus topic" \
  --session
python3 scripts/study_anything_cli.py lesson \
  --title "Learning notes" \
  --reference "local://notes" \
  --text "Paste source material here." \
  --enrichment-text "Paste platform-collected web, video, document, or app context here." \
  --answer "Answer the generated quiz in your own words."
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py agent-eval-report SESSION_ID
python3 scripts/study_anything_cli.py quality-eval SESSION_ID
python3 scripts/study_anything_cli.py enrichment-artifact SESSION_ID --markdown
python3 scripts/study_anything_cli.py obsidian-export SESSION_ID --markdown
python3 scripts/study_anything_cli.py package-export SESSION_ID
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_importer_runtime_retrieval_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool report --create-session --required
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

For importer-first work, Codex should gather external context itself, produce a Learning Context Package,
call `POST /v1/context-packages/validate`, then use
`POST /v1/sessions/from-context-package` or `POST /v1/sessions/{session_id}/context-package`.
If a reviewed local importer exists, Codex can instead call `importer-run` or
`POST /v1/importers/{plugin_id}/run` with exact permission confirmation. Keep network-capable importers
blocked unless the user explicitly approves the network permission.
Use `plugin-sdk`, `plugin-capabilities`, and `plugin-validate` before installing or invoking a new
plugin package; those commands are metadata-only and do not execute entrypoints.
This is the Plugin SDK path for terminal-capable agents.
After the API is reachable, `GET /v1/deployment/guide` returns `deployment-guide-v1`: the redacted
launch path, diagnostics, and platform-Agent privacy boundary.
`GET /v1/commercial/readiness` returns `commercial-readiness-v1`: GitHub OSS, self-host, and
platform-Agent distribution are ready; hosted paid services, billing, SSO, remote accounts, and a
standalone app are not in this alpha launch path.
`GET /v1/adoption/telemetry` returns `adoption-telemetry-v1` and `GET /v1/pmf/readiness` returns
`pmf-readiness-v1`: aggregate local adoption and PMF evidence only, with no source text, answers,
insights, raw user ids, Agent endpoints, API keys, or browser/video/app private context.
The older `POST /v1/sessions/{session_id}/enrichment` path remains available for one-off bounded
excerpts. After import, run teaching layers, quiz, grading, quality eval, and the Obsidian Markdown
export at `GET /v1/sessions/{session_id}/exports/obsidian`.
Use `GET /v1/sessions/{session_id}/exports/learning-package` or the CLI `package-export` command
to create a portable learning package when the next step is a NotebookLM-style bridge, local archive,
or platform-agent handoff.
Use `GET /v1/sessions/{session_id}/exports/second-brain-handoff` or the CLI `second-brain-handoff`
command when Codex needs a stricter Obsidian/NotebookLM/local archive handoff that excludes learner
answers, grading feedback, raw Agent metadata, endpoints, and secrets.

For retrieval-based follow-up lessons, enable LanceDB or the local smoke memory backend, rebuild the
source session with `retrieval-rebuild`, then use `retrieval-import` to create or expand a focused
learning session from minimal snippets.

## Acceptance

A Codex integration must return both:

- `agent-audit.status == verified`
- `commercial-readiness-v1` for local-first launch boundaries and hosted-service non-goals
- `adoption-telemetry-v1` and `pmf-readiness-v1` for aggregate adoption and PMF evidence
- `adoption-telemetry-verification-v1` for telemetry privacy verification
- `ecosystem-submission-v1` for Kimi/Codex/WorkBuddy/generic OpenAPI submission metadata
- `ecosystem-submission-verification-v1` for no-frontend, privacy, and high-risk endpoint checks
- `agent-eval-policy-v1` for the native release gate, optional adapters, fixtures, failure classes,
  and privacy contract
- `agent-eval-artifact-v1` with all required native gates passing
- `agent-quality-eval-v1` with status `pass`
- `agent-eval-report-v1` with `native_fast_gate.status == pass`
- `learning-context-package-v1` for importer-created Learning Context Package inputs
- `importer-run-v1` for reviewed local importer runtime
- `retrieval-search-v1` when optional retrieval is enabled
- `retrieval-quality-eval-v1` when optional retrieval quality is scored
- `learning-enrichment-artifact-v1` for redacted Markdown+HTML micro-lessons
- `obsidian-markdown-export-v1` for copy-ready Obsidian second-brain notes
- `learning-package-v1` for platform-agent, NotebookLM-style, or local archive workflows
- `second-brain-handoff-v1` for strict redacted Obsidian, NotebookLM-style, and archive handoff
- `plugin-sdk-v1`, `plugin-capability-index-v1`, and `plugin-package-validation-v1` for trusted
  plugin ecosystem handoff

Do not paste raw source text, learner answers, grading feedback, Agent endpoints, or secrets into
shared logs.

## Troubleshooting

```bash
python3 scripts/diagnose_adoption.py
```

Use the diagnostic output to distinguish API reachability, missing provider defaults, Agent endpoint
health, Docker daemon state, and GHCR image visibility.
