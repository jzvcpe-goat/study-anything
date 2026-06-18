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
```

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
