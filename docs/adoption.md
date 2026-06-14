# Adoption Readiness

This guide is for external users and maintainers who want to prove Study Anything works from a clean
checkout before connecting real model credentials.

## Platform Adoption Pack

For Kimi Work, Codex, WorkBuddy-style HTTP workspaces, or another platform Agent, start from the
copy-ready adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_platform_operator_drill.py --check
python3 scripts/verify_platform_submission_dry_run.py --check
python3 scripts/verify_platform_manual_submission_rehearsal.py --check
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_external_eval_marketplace_harness.py --check
python3 scripts/verify_agent_eval_marketplace_enforcement.py --check
python3 scripts/verify_learning_enrichment_bridge.py --check
python3 scripts/generate_platform_field_rehearsal.py --check
python3 scripts/verify_platform_field_rehearsal.py --check
python3 scripts/generate_platform_support_triage.py --check
python3 scripts/verify_platform_support_triage.py --check
python3 scripts/generate_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py --check
python3 scripts/generate_platform_public_support_status.py --check
python3 scripts/verify_platform_public_support_status.py --check
python3 scripts/verify_agent_eval_baseline.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The archive contains OpenAPI/OpenAI tool import assets, Kimi/Codex/WorkBuddy packs, the repo-local
Skill, gateway examples, mock agent, NotebookLM fixture, verifier scripts, and a SHA256 manifest.
The operator drill emits `study-anything-operator-drill-v1` evidence that the pack can be consumed as
an external platform tool directory. The submission dry-run emits `platform-submission-dry-run-v1`
with ready/warning/blocked status for each target platform. The manual rehearsal emits
`platform-manual-submission-rehearsal-v1`, a redacted operator handoff covering tool import, runtime
health, user-owned HTTP Agent setup, first lesson, export evidence, diagnostics, and failure
remediation. The first lesson authoring kit emits `first-run-lesson-authoring-kit-v1`, with bilingual
copyable platform-Agent prompts, a tool-call sequence, Learning Context Package template, user-owned
HTTP Agent setup, expected output schemas, export paths, and privacy assertions. The external eval
marketplace harness emits `external-eval-marketplace-harness-v1`, tying native release gates,
optional Promptfoo/DeepEval/LangChain AgentEvals/Ragas adapters, fixtures, timeout policy, and
redaction assertions into one platform-submission contract. The Agent eval marketplace enforcement
verifier emits `agent-eval-marketplace-enforcement-v1`; it proves native eval gates are required,
external judge adapters are optional unless explicitly required, required judge mode fails closed,
baseline evidence has not regressed, and judge/model keys remain outside Study Anything. The Learning
Enrichment bridge verifier
emits `learning-enrichment-bridge-verification-v1`; it proves platform-collected web, document,
video-slice, app-context, Markdown, and Obsidian inputs can be transformed into redacted Markdown+HTML
micro-lessons, NotebookLM-style manual bridge metadata, Obsidian handoff, and strict second-brain
archive evidence. The adoption verifier emits
`adoption-proof-v1` and exercises importer, enrichment, retrieval, teaching layers, eval, Obsidian
export, and NotebookLM-style learning-package export through Skill Mode.
The onboarding readiness verifier emits `platform-onboarding-readiness-v1` plus
`platform-triage-dashboard-v1`; it proves first external adopter walkthroughs, maintainer SLA labels,
release-blocker fixtures, dashboard privacy checks, ecosystem metadata, and adoption-pack inclusion
are aligned before an external handoff.
The public support status verifier emits `public-support-status-v1` and
`public-maintainer-dashboard-v1`; it proves platform status, known blocker fixtures, SLA labels,
fixture hashes, and public commands can be published without source text, learner answers, Agent
prompts, Agent endpoints, model keys, private context, or full support bundle payloads.

Use this path before claiming a platform integration works. It does not require the standalone
frontend, and it does not store real model keys in Study Anything.

## Clean Clone Smoke

From an existing checkout, run the adoption verifier:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
```

The verifier creates a temporary clone, generates `.env`, starts Skill Mode, verifies the
OpenAI-compatible gateway dry-run path, and completes:

- teaching layers
- quiz generation
- answer grading
- mastery update
- `agent-audit`
- `agent-eval/artifact`
- `agent-eval/quality`
- platform tool, enriched lesson, and importer lesson smoke through Skill Mode

For development before committing local edits, use:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo . --copy-worktree
```

## Optional Promptfoo Evidence

Promptfoo is the first external eval runner. It checks the redacted eval artifact contract; it does
not judge learning quality by itself.

```bash
python3 scripts/verify_clean_clone_adoption.py --repo . --with-promptfoo
```

Use `--promptfoo-required` only in an environment where Node/npm package installation is allowed to
fail the run:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo . --with-promptfoo --promptfoo-required
```

Study Anything separates these layers:

- Invocation proof: `agent-audit` and native `agent-eval/artifact` gates prove the learning tasks were
  handled and redacted.
- Quality evaluation: Promptfoo, DeepEval, LangChain AgentEvals, and Ragas can score contract quality,
  task completion, trajectory, and grounding after native gates pass.

## Platform Adoption Paths

Kimi/OpenAI-compatible:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

Then add real credentials to your own gateway environment. Study Anything does not store model API
keys.

Codex or another terminal-capable Agent:

```bash
ln -s "$(pwd)/skills/study-anything" "${CODEX_HOME:-$HOME/.codex}/skills/study-anything"
./scripts/run_skill_mode_demo.sh
```

WorkBuddy or another HTTP-tool workspace:

```bash
platform/generated/study-anything-platform-openapi.json
platform/generated/study-anything-openai-tools.json
```

Import one of those assets, set the API base to `http://127.0.0.1:8000`, and require the Agent to
return `agent-audit`, `agent-eval/artifact`, `agent-eval/quality`, Obsidian export, and
`learning-package-v1` after each learning loop.

To prove the complete plugin-style lesson path against a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
```

This verifier runs source input, enrichment, overview/glossary teaching, quiz, answer grading, quality
eval, Obsidian export, and the portable learning package. The importer verifier starts from
`fixtures/notebooklm/notebooklm-style-context-package.json` and proves Learning Context Package import
without depending on an official NotebookLM API.

## Diagnostics

When adoption fails, run:

```bash
python3 scripts/diagnose_adoption.py
```

It checks:

- missing `.env` and copyable setup command
- localhost API reachability
- Docker daemon availability
- GHCR manifest visibility
- Agent endpoint health
- provider capability defaults

Use `--strict` in CI-like environments where warnings should fail the run.
The JSON payload is `adoption-diagnostics-v1` and includes `adoption-diagnostic-plan-v1`, a
platform-agent-friendly next-command plan.

Common remediation classes are included in `adoption-proof-v1` and `diagnose_adoption.py`: GHCR or
Docker Hub availability, non-ASCII checkout paths, port conflicts, local Agent endpoint reachability,
Node/npm availability, and optional Promptfoo setup.

## Ecosystem Submission Smoke

Before submitting Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, or generic OpenAPI assets to an
external platform, run:

```bash
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_platform_manual_submission_rehearsal.py --check
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_agent_eval_marketplace_enforcement.py --check
python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check
python3 scripts/verify_learning_enrichment_bridge.py --check
```

The verifier emits `ecosystem-submission-verification-v1` and proves the submission pack has no
standalone frontend requirement, no Study Anything custody of real model keys, no raw learning data
in submission metadata, and no high-risk management endpoints in the imported platform tool surface.
The manual rehearsal report is the shareable operator checklist for the same submission: share that
redacted JSON instead of raw source text, learner answers, Agent endpoints, browser/video context, or
model keys.
The first lesson kit is the shareable teaching runbook for Kimi, Codex, WorkBuddy, and generic
OpenAPI operators. It is safe to share because it uses placeholders and schema evidence instead of
raw source, answers, endpoints, model keys, or private browser/video context.
The Agent eval marketplace enforcement report is the shareable proof that native learning-Agent
evaluation ran, optional external judge adapters are clearly diagnosed, required judge failures are
blocking, and no external judge keys or real model credentials are stored by Study Anything.
The platform adoption feedback diagnostics report emits
`platform-adoption-feedback-diagnostics-v1`. It proves import failures, version drift, missing
commands, unsupported platform capabilities, local endpoint health, and missing Agent eval evidence
are diagnosable without sharing private learning data.
The feedback package emits `platform-feedback-package-v1`. It is local-only by default and contains
diagnostic summaries plus redacted logs, not raw source text, answers, Agent prompts, personal
profiles, endpoint secrets, judge keys, or model keys. Generate or verify it with:

```bash
python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check
python3 scripts/generate_platform_feedback_package.py --check
```

The field adoption rehearsal emits `platform-field-adoption-rehearsal-v1`.
It packages Kimi, Codex, WorkBuddy, and generic OpenAPI rehearsal transcripts
plus an import quirks catalog and mock failed-import fixtures using
`platform-import-failure-fixture-v1`. Use it before handing the pack to an
external tester:

```bash
python3 scripts/generate_platform_field_rehearsal.py --check
python3 scripts/verify_platform_field_rehearsal.py --check
```

The fixtures cover schema mismatch, missing local gateway, unsupported auth
mode, tool naming drift, timeout, browser localhost restrictions, package
corruption, and version drift. They contain actionable next commands and
redacted diagnostic fields only.

The support desk verifier emits `platform-support-triage-v1`. It proves the GitHub issue templates,
`platform-support-ticket-fixture-v1` mock tickets, support bundle contract, maintainer response
playbook, platform packs, ecosystem submission metadata, adoption pack, and docs are aligned. Use it
when an external tester cannot import a platform pack or cannot produce Agent eval evidence:

```bash
python3 scripts/generate_platform_support_triage.py --check
python3 scripts/verify_platform_support_triage.py --check
python3 scripts/verify_platform_support_triage.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
python3 scripts/generate_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py --check
python3 scripts/verify_platform_onboarding_readiness.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

Issue reports should include version, platform, command, diagnostic code, fixture id, redacted log
excerpt, and next commands tried. They should not include source text, learner answers, Agent
prompts, Agent endpoints, model keys, personal profiles, or private browser/video/app context.

The first adopter onboarding verifier emits `platform-onboarding-readiness-v1`. It adds
`first-external-adopter-walkthrough-v1`, `maintainer-sla-labels-v1`,
`platform-triage-dashboard-v1`, and `platform-release-blocker-fixture-v1` on top of the support desk
so Kimi, Codex, WorkBuddy, and generic OpenAPI/MCP operators can follow the shortest success path,
fall back to a redacted issue, and have maintainers close with verified evidence.

The plugin ecosystem adoption kit is the shareable plugin trust runbook. It proves the adoption pack
contains bundled sample plugins, a digest-verified `plugins/registry.json`, quarantine-first install
policy, platform-pack commands, and redacted evidence without executing plugin entrypoints.
The Learning Enrichment bridge report is the shareable proof that external platform context,
NotebookLM-style workflows, Obsidian notes, and strict second-brain archives are connected through
source hashes and redaction rules rather than through a separate Study Anything frontend.

## User-Owned Agent Gateway Hardening

Before connecting Kimi, OpenAI-compatible providers, or another private Agent gateway, run:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
python3 scripts/verify_agent_gateway_hardening.py
python3 scripts/verify_external_agent_adapter_hardening.py
```

The hardening verifier emits `agent-gateway-hardening-verification-v1` and proves unsafe endpoint
secrets, secret metadata, malformed Agent output, unsupported tasks, and raw task payload leakage are
blocked or redacted.
The adapter hardening verifier emits `external-agent-adapter-hardening-v1` and proves the real
external Agent eval path is separated from fake demo evidence while malformed JSON, invalid status,
missing content, invalid score/confidence, timeouts, missing citations, and missing capabilities are
diagnosed without leaking source text, answers, endpoints, or model keys.

## Adoption Telemetry And PMF Readiness

After the API is reachable, verify the local aggregate adoption contracts:

```bash
python3 scripts/verify_adoption_telemetry.py --api-base http://127.0.0.1:8000
curl http://127.0.0.1:8000/v1/adoption/telemetry
curl http://127.0.0.1:8000/v1/pmf/readiness
```

The verifier emits `adoption-telemetry-verification-v1`. The API contracts are
`adoption-telemetry-v1` and `pmf-readiness-v1`; they report aggregate clean-clone/runtime/tool/eval,
repeat-learning, plugin-validation, and explicit opt-in feedback counts only. They do not include raw
source text, answers, insights, user ids, Agent endpoints, API keys, browser context, app context, or
video transcripts.

## Published Image Fallback

Before publishing or handing the project to another operator, run the deployment hardening verifier:

```bash
python3 scripts/verify_deployment_hardening.py --check
python3 scripts/verify_deployment_hardening.py --pack platform/generated/study-anything-platform-adoption-pack.zip
```

It emits `deployment-hardening-verification-v1`, covering Skill Mode, published-image, source-build,
Docker/Compose diagnostics, non-ASCII path recovery, port checks, GHCR manifest fallback, local Agent
endpoint guidance, and platform-pack inclusion.

The normal published-image smoke is:

```bash
python3 scripts/verify_published_image_launch.py --tag v0.3.23-alpha
```

If the local machine can inspect the multi-arch manifest but GHCR layer download is too slow, record a
diagnostic instead of leaving the run ambiguous:

```bash
python3 scripts/verify_published_image_launch.py \
  --tag v0.3.23-alpha \
  --pull-timeout-seconds 180 \
  --allow-pull-timeout-report
```

This fallback is acceptable only when GitHub `docker-images` succeeded and
`docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.23-alpha` shows `linux/amd64`
and `linux/arm64`. The timeout report includes `manifest_evidence` plus explicit fallback acceptance
conditions so reviewers do not confuse a local GHCR download stall with a broken release image.

For public handoff, also generate `published-image-evidence-v1`:

```bash
python3 scripts/generate_published_image_evidence.py --check
python3 scripts/verify_published_image_evidence.py --check
```

This evidence layer records manifest platform requirements, docker-images workflow expectations,
local pull-timeout fallback rules, optional remote smoke replay commands, and release-blocking
classifications without storing learning content, Agent endpoints, local paths, or model secrets.

## Release Asset Adoption

For platform operators who start from the GitHub Release page, publish and verify
`release-asset-adoption-v1` alongside the platform adoption pack:

```bash
python3 scripts/generate_release_asset_adoption.py --check
python3 scripts/verify_release_asset_adoption.py \
  --tag v0.3.23-alpha \
  --runtime metadata-only
```

Before the tag exists, maintainers can run the offline generated-asset path:

```bash
python3 scripts/verify_release_asset_adoption.py \
  --fixture fixtures/release-asset-adoption/asset-only-pass.json \
  --asset-dir platform/generated \
  --runtime metadata-only
```

This emits `release-asset-adoption-proof-v1` and verifies required GitHub Release
zip assets, sha256 digests, adoption-pack manifest hashes, and embedded
published-image evidence without storing learning content, Agent endpoints,
local paths, model keys, or private support payloads.

## Adopter Evidence Archive

For v0.3.23-alpha, publish or hand off `adopter-evidence-archive-v1` alongside the release. It
packages public support status hashes, platform pack checksums, Docker manifest commands, local GHCR
pull-timeout fallback evidence, known limitations, and maintainer checklist items.

```bash
python3 scripts/generate_adopter_evidence_archive.py --check
python3 scripts/verify_adopter_evidence_archive.py --check
python3 scripts/verify_adopter_evidence_archive.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

The archive is metadata-only and must not include raw source text, learner answers, Agent prompts,
Agent endpoint secrets, model keys, support bundle private payloads, personal profile data, or
browser/video/app private context.
