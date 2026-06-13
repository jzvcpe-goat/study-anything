# Ecosystem Submission Pack

Study Anything v0.3.8-alpha treats Kimi-compatible tools, Codex Skill usage,
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
```

The verifier emits `ecosystem-submission-verification-v1` and fails if the
pack exposes management endpoints, references missing assets, drifts from the
platform pack privacy contract, or loses the `commercial-readiness-v1` link.
The dry-run emits `platform-submission-dry-run-v1` with per-platform
ready/warning/blocked status, import assets, acceptance commands, and a manual
submission checklist.

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
