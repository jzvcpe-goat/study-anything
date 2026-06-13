# Ecosystem Submission Pack

Study Anything v0.3.15-alpha treats Kimi-compatible tools, Codex Skill usage,
WorkBuddy-style HTTP workspaces, and generic OpenAPI platforms as the first
public distribution surface.

The submission pack is intentionally not a standalone frontend. The platform
Agent keeps the conversation, browsing, files, external data lookup, video or
application tooling, and real model credentials. Study Anything runs as a
local learning engine that provides source-bound study workflows, Agent output
validation, mastery state, redacted eval evidence, retrieval quality checks,
aggregate adoption telemetry, PMF readiness checks, and portable Obsidian or
NotebookLM-style exports.

## Machine-Readable Contract

`platform/ecosystem-submission.json` is the source of truth for external
submission metadata. It declares:

- `schema_version=ecosystem-submission-v1`
- supported submission targets: Kimi-compatible tools, Codex Skill,
  WorkBuddy-style HTTP, and generic OpenAPI tools
- no standalone frontend requirement
- no billing requirement
- no managed hosted service in the MVP
- no Study Anything custody of real model API keys
- no raw learning data or Agent endpoints in the submission package
- `adoption-telemetry-v1` and `pmf-readiness-v1` as aggregate local evidence
- the exact assets and verification commands each target should use

Run:

```bash
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_platform_submission_dry_run.py --check
python3 scripts/verify_platform_manual_submission_rehearsal.py --check
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_external_eval_marketplace_harness.py --check
python3 scripts/verify_agent_eval_marketplace_enforcement.py --check
python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check
python3 scripts/verify_deployment_hardening.py --check
```

The verifier emits `ecosystem-submission-verification-v1` and fails if the
pack exposes management endpoints, references missing assets, drifts from the
platform pack privacy contract, or loses the `commercial-readiness-v1` link.
The dry-run emits `platform-submission-dry-run-v1` with per-platform
ready/warning/blocked status, import assets, acceptance commands, and a manual
submission checklist.
The manual rehearsal emits `platform-manual-submission-rehearsal-v1`, a redacted
operator handoff that covers unpacking, tool import, runtime health, user-owned
HTTP Agent setup, first lesson, export evidence, diagnostics, and remediation.
The deployment hardening report emits `deployment-hardening-verification-v1`,
covering Skill Mode, published-image, and source-build paths plus Docker/Compose
diagnostics, GHCR manifest fallback, non-ASCII path guidance, and local Agent
endpoint recovery.
The first lesson kit emits `first-run-lesson-authoring-kit-v1`, a copyable
Kimi/Codex/WorkBuddy handoff with bilingual prompts, a tool-call sequence,
Learning Context Package template, HTTP Agent setup, expected schemas, export
paths, remediation, and privacy assertions.
The external eval harness emits `external-eval-marketplace-harness-v1`, a
marketplace-quality eval contract covering native release gates, optional
Promptfoo/DeepEval/LangChain AgentEvals/Ragas adapters, fixtures, timeouts,
sample eval cases, expected evidence, and redaction assertions.
The Agent eval marketplace enforcement report emits
`agent-eval-marketplace-enforcement-v1`, proving optional external judge
adapters have explicit skip diagnostics, required judge mode fails closed, the
baseline and harness have not drifted, and Study Anything stores no judge or
model keys.
The plugin ecosystem adoption kit emits `plugin-ecosystem-adoption-kit-v1`, a
copy-ready trust contract covering bundled sample plugins, registry
`sourceDigest` verification, quarantine-first install policy, platform-pack
commands, and no plugin entrypoint execution during validation.

## Submission Targets

Kimi-compatible platforms should use
`platform/generated/study-anything-openai-tools.json` or
`platform/generated/study-anything-platform-openapi.json`, then follow
`docs/use-with-kimi.md`.

Codex or other terminal-capable Agents should use
`skills/study-anything/SKILL.md` and `scripts/study_anything_cli.py`.

WorkBuddy-style HTTP workspaces should import
`platform/generated/study-anything-platform-openapi.json` and keep the API
local or private.

Generic OpenAPI platforms should import the generated OpenAPI asset and use
`platform/generated/study-anything-tool-catalog.md` as the fallback tool map.

## Acceptance Evidence

Before calling a platform integration ready, run:

```bash
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_commercial_readiness.py
python3 scripts/verify_adoption_telemetry.py
python3 scripts/verify_agent_gateway_hardening.py
python3 scripts/verify_external_agent_adapter_hardening.py
python3 scripts/verify_notebooklm_obsidian_bridge_hardening.py
python3 scripts/verify_plugin_quarantine.py
python3 scripts/verify_security_recovery_hardening.py
python3 scripts/verify_platform_submission_dry_run.py --check
python3 scripts/verify_platform_manual_submission_rehearsal.py --check
python3 scripts/verify_first_lesson_authoring_kit.py --check
python3 scripts/verify_external_eval_marketplace_harness.py --check
python3 scripts/verify_agent_eval_marketplace_enforcement.py --check
python3 scripts/verify_plugin_ecosystem_adoption_kit.py --check
python3 scripts/verify_platform_ecosystem_packs.py
python3 scripts/generate_platform_bundle_manifest.py --check
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

For a live local API, also run the platform-specific checks listed in
`platform/ecosystem-submission.json`.

## Commercial Boundary

Do not sell a standalone Study Anything app at this stage. The OSS core should
stay local-first and free to inspect, fork, and self-host. Commercial work
should prepare future hosted sync, hosted publishing, team collaboration, and a
trusted plugin ecosystem. Those services sell convenience and reliability, not
access to the core learning workflow.
