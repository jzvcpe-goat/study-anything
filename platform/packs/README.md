# Study Anything Platform Packs

These packs are copy-ready starting points for agent platforms that call Study Anything as a
local-first learning engine.

Each pack points back to the same constrained public contract:

- `platform/study-anything-platform-tools.json`
- `platform/generated/study-anything-platform-openapi.json`
- `platform/generated/study-anything-openai-tools.json`
- `platform/generated/study-anything-tool-catalog.md`
- `platform/ecosystem-submission.json`
- `platform/generated/study-anything-platform-bundle.json`
- `platform/generated/study-anything-operator-drill-transcript.json`
- `platform/generated/study-anything-platform-adoption-pack.json`
- `platform/generated/study-anything-platform-adoption-pack.zip`
- `docs/cognitive-loop-adoption-cookbook.md`
- `platform/generated/study-anything-cognitive-loop-adoption-recipes.json`
- `platform/generated/study-anything-cognitive-loop-recipe-replay.json`
- `platform/generated/study-anything-cognitive-loop-skill-entrypoint.json`
- `platform/generated/study-anything-cognitive-loop-recipe-cli.json`
- `platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json`
- `platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json`
- `platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json`
- `platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json`
- `platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json`
- `evals/baselines/study-anything-agent-eval-baseline.json`
- `evals/fixtures/fake-agent-learning-loop.json`
- `evals/fixtures/mock-http-agent-learning-loop.json`

The packs do not configure real model credentials. Keep model keys and browsing/tool access inside
the user's platform Agent or user-owned HTTP Agent gateway.

v0.3.1 packs add ecosystem submission metadata and commercial readiness boundaries on top of Agent Eval maturity, Plugin SDK, trusted package validation, the second-brain handoff layer, Learning Enrichment Layer, operator drill, deterministic Agent
eval regression baseline, distributable adoption archive, `adoption-proof-v1` verifier, importer,
retrieval, and ecosystem eval capabilities:

- `deployment-guide-v1` gives platform Agents a redacted, copyable launch guide for Skill Mode,
  Docker source builds, published GHCR images, diagnostics, and privacy boundaries.
- `commercial-readiness-v1` tells platform Agents which launch paths are ready, which hosted
  services remain contract-only, and why billing/SSO/standalone app work is outside this alpha.
- `ecosystem-submission-v1` turns the Kimi/Codex/WorkBuddy/generic OpenAPI assets into a
  submission-ready package with no standalone frontend requirement, no billing requirement, and no
  Study Anything custody of real model keys.
- `ecosystem-submission-verification-v1` proves the submission metadata, generated assets, privacy
  boundary, and high-risk endpoint exclusions are still aligned.
- Learning Context Package import for web, document, video-slice, app-context, Markdown, and Obsidian
  material gathered by the platform;
- enrichment input for web, document/PDF, video-slice, app-context, Markdown, and Obsidian excerpts
  gathered by the platform;
- redacted Markdown+HTML enrichment micro-lessons for platform-agent teaching surfaces;
- quality eval evidence that separates invocation proof, schema validity, and teaching-quality gates;
- `agent-eval-policy-v1` and `agent-eval-report-v1` evidence that platform Agents can prove the
  Study Anything Agent workflow actually ran and passed native release gates;
- retrieval/context quality eval evidence for source binding, snippet minimality, query relevance, and
  Learning Context Package handoff;
- Obsidian-compatible markdown export for second-brain workflows;
- a portable learning package for platform agents, NotebookLM-style bridges, Obsidian pipelines, and
  local archives.
- a strict `second-brain-handoff-v1` export with Obsidian note, NotebookLM manual bridge metadata,
  and local archive manifest that excludes learner answers and grading feedback.
- a `plugin-sdk-v1` contract, `plugin-capability-index-v1` inventory, and
  `plugin-package-validation-v1` package check for local plugin ecosystem handoff.
- a copy-ready platform adoption pack that proves the Kimi/Codex/WorkBuddy-style tool surface works
  without requiring a standalone frontend.
- `study-anything-operator-drill-v1` transcript evidence that proves the pack can be consumed as an
  external platform tool directory.
- `study-anything-agent-eval-regression-report-v1` evidence that the native eval scorecard did not
  regress against the committed baseline.

## Packs

- `codex`: terminal-capable agents that can use the repo-local Skill and CLI.
- `kimi`: Kimi-compatible or OpenAI-compatible tool-calling agents, plus Kimi as a user-owned
  reasoning model through the local gateway.
- `workbuddy`: HTTP-tool workspace agents that import OpenAPI tools and call the local API.

## Verify

```bash
.venv/bin/python scripts/verify_clean_clone_adoption.py --repo . --copy-worktree
.venv/bin/python scripts/verify_commercial_readiness.py
.venv/bin/python scripts/verify_ecosystem_submission_pack.py
.venv/bin/python scripts/verify_platform_ecosystem_packs.py
.venv/bin/python scripts/verify_cognitive_loop_adoption_cookbook.py --check
.venv/bin/python scripts/generate_cognitive_loop_adoption_recipes.py --check
.venv/bin/python scripts/verify_cognitive_loop_recipe_replay.py --check
.venv/bin/python scripts/verify_cognitive_loop_skill_entrypoint.py --check
.venv/bin/python scripts/verify_cognitive_loop_recipe_cli.py --check
.venv/bin/python scripts/verify_cognitive_loop_recipe_cli_receipts.py --check
.venv/bin/python scripts/verify_cognitive_loop_recipe_cli_failures.py --check
.venv/bin/python scripts/verify_cognitive_loop_recipe_cli_schemas.py --check
.venv/bin/python scripts/verify_cognitive_loop_recipe_cli_schema_negative_fixtures.py --check
.venv/bin/python scripts/verify_cognitive_loop_schema_pack_consumer.py --check
.venv/bin/python scripts/cognitive_loop_recipe_cli.py list
.venv/bin/python scripts/cognitive_loop_recipe_cli.py show risk_decision
.venv/bin/python scripts/generate_platform_bundle_manifest.py --check
.venv/bin/python scripts/verify_platform_operator_drill.py --check
.venv/bin/python scripts/generate_platform_adoption_pack.py --check
.venv/bin/python scripts/verify_agent_eval_baseline.py --check
.venv/bin/python scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

For a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_ecosystem_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

For adoption troubleshooting:

```bash
python3 scripts/diagnose_adoption.py
```

The diagnostic output includes `adoption-diagnostic-plan-v1`, a copyable next-command plan that
separates missing Docker, slow GHCR pulls, missing `.env`, API reachability, Agent endpoint, and
provider-default issues.

For day-to-day use, start from `docs/cognitive-loop-adoption-cookbook.md`. It maps Kimi, Codex,
WorkBuddy, and private platform Agents to the local Cognitive Loop commands for first adoption, daily
project review, risk decisions, and learning handoff. Platform Agents can also import
`platform/generated/study-anything-cognitive-loop-adoption-recipes.json` for the same paths as a
machine-readable recipe matrix, and
`platform/generated/study-anything-cognitive-loop-recipe-replay.json` to verify the matrix is
safe for metadata-only replay before an operator runs runtime or human-gated commands.
`platform/generated/study-anything-cognitive-loop-skill-entrypoint.json` proves the same recipe path
is visible from the repo-local Skill and every platform pack README.
`platform/generated/study-anything-cognitive-loop-recipe-cli.json` proves platform Agents can query
read-only `cognitive-loop-recipe-cli-v1` plans without executing recipe commands.
`platform/generated/study-anything-cognitive-loop-recipe-cli-receipts.json` gives deterministic
sample outputs and hashes for those read-only CLI calls.
`platform/generated/study-anything-cognitive-loop-recipe-cli-failures.json` gives deterministic
negative-path receipts for unknown recipe ids and invalid recipe matrices.
`platform/generated/study-anything-cognitive-loop-recipe-cli-schemas.json` gives offline JSON
Schemas for static validation of the recipe CLI success, receipt, and failure reports.
`platform/generated/study-anything-cognitive-loop-recipe-cli-schema-negative-fixtures.json` proves
those schemas reject drift, unsafe flags, malformed types, and private text probes.
`platform/generated/study-anything-cognitive-loop-schema-pack-consumer.json` proves those assets are
discoverable and hash-checked from the adoption pack zip without a repo checkout.
