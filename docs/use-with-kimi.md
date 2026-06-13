# Use Study Anything With Kimi

Study Anything works best when Kimi remains the user-facing Agent and Study
Anything acts as the local learning engine. Kimi can gather context, call tools,
and explain results; Study Anything validates learning context, runs the
learning workflow, and returns redacted audit/eval/export artifacts.

## Mode 1: Copy-Only

Use this when Kimi cannot call local HTTP tools.

1. Paste source or bounded excerpts into Kimi.
2. Ask Kimi to produce a `learning-context-package-v1`.
3. Validate it locally:

```bash
python3 scripts/study_anything_cli.py context-validate package.json
python3 scripts/study_anything_cli.py context-import package.json --session
```

This mode is lowest friction, but Kimi is not directly invoking Study Anything.

## Mode 2: HTTP Tool Mode

Use this when Kimi Work or a Kimi-compatible platform can import HTTP tools.

1. Start Study Anything:

```bash
./scripts/launch_skill_mode.sh
```

2. Import the constrained tool contract:

```text
platform/generated/study-anything-platform-openapi.json
platform/generated/study-anything-openai-tools.json
platform/ecosystem-submission.json
```

3. Let Kimi call the platform tools:

- `study_anything_deployment_guide`
- `study_anything_commercial_readiness`
- `study_anything_adoption_telemetry`
- `study_anything_pmf_readiness`
- `study_anything_health`
- `study_anything_create_session`
- `study_anything_validate_context_package`
- `study_anything_add_enrichment`
- `study_anything_teaching_layers`
- `study_anything_run`
- `study_anything_answer`
- `study_anything_agent_audit`
- `study_anything_enrichment_artifact_export`
- `study_anything_obsidian_export`
- `study_anything_learning_package_export`
- `study_anything_second_brain_handoff_export`

This mode is the preferred early ecosystem path because it keeps the UX inside
Kimi while Study Anything remains local-first.

Before treating the Kimi integration as ready, run:

```bash
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_platform_manual_submission_rehearsal.py --check
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_adoption_telemetry.py --api-base http://127.0.0.1:8000
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The first command emits `ecosystem-submission-verification-v1`; the manual rehearsal command emits
`platform-manual-submission-rehearsal-v1`; the first lesson kit emits
`first-run-lesson-authoring-kit-v1` with copyable Chinese and English prompts for Kimi-compatible
operators; the telemetry command emits `adoption-telemetry-verification-v1`; the final command emits
`adoption-proof-v1`.

Start with `study_anything_deployment_guide` after the local API is reachable. It returns
`deployment-guide-v1`: launch commands, common first-run failure classes, and the privacy boundary
between Kimi, the user-owned Agent gateway, and Study Anything.
Then call `study_anything_adoption_telemetry` and `study_anything_pmf_readiness` when Kimi needs
aggregate local adoption or PMF evidence. These tools must not return source text, answers, insights,
raw user ids, Agent endpoints, API keys, or browser/video/app private context.

For long-term memory, Kimi should prefer
`study_anything_second_brain_handoff_export`. It returns an Obsidian note,
NotebookLM manual bridge metadata, and a local archive manifest without raw
source text, learner answers, grading feedback, Agent metadata, endpoints, or
secrets.

## Mode 3: Local Agent Gateway

Use this when you want Study Anything's learning Agent tasks to run through your
own Kimi-compatible local gateway.

```bash
export AGENT_LLM_BASE_URL="https://api.moonshot.cn/v1"
export AGENT_LLM_API_KEY="$MOONSHOT_API_KEY"
export AGENT_LLM_MODEL="${AGENT_LLM_MODEL:-kimi-k2.6}"

python3 scripts/openai_compatible_agent_gateway.py \
  --host 127.0.0.1 \
  --port 8787
```

Then register it:

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My Kimi gateway" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default
```

Kimi or the platform Agent still owns browsing, files, external data, and video
slice creation. The local gateway owns model credentials and reasoning. Study
Anything owns learning state, validation, audit, eval, and redacted exports.

Before sharing the Kimi-compatible pack for manual import, run:

```bash
python3 scripts/verify_platform_submission_dry_run.py --check
python3 scripts/verify_platform_manual_submission_rehearsal.py --check
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_external_eval_marketplace_harness.py --check
python3 scripts/verify_external_agent_adapter_hardening.py
```

The report verifies the OpenAI-compatible tools, OpenAPI asset, gateway guide,
known limits, acceptance commands, and redacted Kimi submission checklist.
The manual rehearsal report adds a copyable operator handoff: unpack the pack,
import tools, start the local runtime, configure the user-owned HTTP Agent, run
a first lesson, export Obsidian/learning-package/second-brain evidence, and
collect diagnostics without sharing raw learning data.
The first lesson kit gives Kimi a bounded copy/paste workflow for turning user-provided materials
into a Learning Context Package, running the Study Anything lesson tools, and exporting Obsidian plus
NotebookLM-style evidence.
The external eval marketplace harness gives Kimi a single redacted checklist for native eval gates,
optional mature eval adapters, fixtures, timeouts, and evidence schemas before manual submission.
The external Agent adapter verifier separately proves that Kimi-backed or Kimi-compatible HTTP
Agents produce redacted eval evidence and that bad outputs become explicit diagnostics.

## What To Commercialize Later

Do not sell a separate app before adoption is real. The early commercial
surface should be convenience and trust:

- hosted sync and backup for learning state;
- team workspaces and shared courses;
- trusted plugin/importer ecosystem;
- managed platform packs and integration support.

For plugin ecosystem work, let Kimi call `GET /v1/plugins/sdk`,
`GET /v1/plugins/capabilities`, and `POST /v1/plugins/validate-package` before
asking the user to install anything. These endpoints are metadata-only: they do
not execute plugin entrypoints, copy plugin packages, or expose model secrets.

The open-source core stays useful without accounts, billing, hosted storage, or
real model keys inside Study Anything.
