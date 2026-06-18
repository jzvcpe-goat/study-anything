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
