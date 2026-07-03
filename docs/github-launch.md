# GitHub Release Guide

This guide is for public alpha releases. The goal is open-source and local-first: users should be able to clone, inspect, run, and extend Study Anything without creating an account or giving Study Anything model keys.

## Launch Positioning

- License: Apache-2.0.
- Distribution: GitHub repository first, Docker Compose self-host first.
- Real reasoning: Bring Your Own Agent. Study Anything stores endpoint/config metadata, not real model API keys.
- Monetization: not in the MVP. Future hosted services should sell convenience and collaboration, not lock-in.

## Before Publishing A Release

Run:

```bash
python3 scripts/setup_env.py --force --output /tmp/study-anything.env
python3 scripts/check_env.py --env /tmp/study-anything.env --strict
./scripts/release_check.sh
python3 scripts/generate_platform_agent_assets.py --check
python3 scripts/verify_clean_clone_adoption.py --repo . --copy-worktree
python3 scripts/verify_platform_ecosystem_packs.py
python3 scripts/generate_platform_plugin_packs.py --check
python3 scripts/verify_platform_plugin_packs.py --check
python3 scripts/generate_platform_plugin_downloads.py --check
python3 scripts/verify_platform_plugin_downloads.py --check
python3 scripts/verify_launch_acceptance_ledger.py --check
python3 scripts/verify_github_launch_operator_guide.py --check
python3 scripts/verify_release_stack_readiness.py
python3 scripts/generate_platform_bundle_manifest.py --check
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
python3 scripts/verify_plugin_quarantine.py
python3 scripts/verify_security_recovery_hardening.py
python3 scripts/diagnose_adoption.py --ghcr-timeout-seconds 5
STACK_PROFILE=smoke ./scripts/launch_self_host.sh
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://mock-http-agent:8787 python3 scripts/verify_mock_http_agent_flow.py
curl -s http://127.0.0.1:8000/v1/metrics/pmf
./scripts/stop_self_host.sh
python3 scripts/verify_backup_restore_drill.py
```

Confirm:

- `.env` is not staged.
- No screenshots, traces, or logs contain private source text or secrets.
- `/v1/metrics/pmf` returns only aggregate local PMF signals and does not expose source text, answers,
  insights, raw user identifiers, Agent metadata, or raw contact values.
- `scripts/verify_backup_restore_drill.py` can create, mutate, restore, and clean up a disposable
  Docker stack.
- `scripts/verify_clean_clone_adoption.py --repo .` succeeds after the release candidate is committed,
  proving Skill Mode, gateway dry-run, teaching layers, quiz, grading, mastery, Agent audit, and Agent
  eval from a disposable checkout.
- `scripts/verify_platform_lesson_flow.py` succeeds against a running API, proving enrichment,
  teaching layers, quality eval, Obsidian export, and `learning-package-v1`.
- `scripts/verify_importer_lesson_flow.py` succeeds against a running API, proving Learning Context
  Package import, NotebookLM-style fixture handling, Obsidian backlinks, quality eval, and
  `learning-package-v1`.
- `scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree`
  emits `adoption-proof-v1`, proving the distributable Kimi/Codex/WorkBuddy/Hermes platform pack can be used
  by an external operator without the standalone frontend.
- `scripts/verify_deployment_hardening.py --check` and
  `scripts/verify_deployment_hardening.py --pack platform/generated/study-anything-platform-adoption-pack.zip`
  emit `deployment-hardening-verification-v1`, proving Skill Mode, published image, source build,
  diagnostics, GHCR fallback, and platform pack evidence are aligned.
- `scripts/verify_published_image_launch.py --tag v0.3.31-alpha` can pull the public API image,
  verify the running API version, and complete the API learning loop.
- `scripts/verify_ecosystem_submission_pack.py` returns `ecosystem-submission-verification-v1` for
  Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, Hermes Agent Skill, and generic OpenAPI submission assets.
- `scripts/verify_launch_acceptance_ledger.py --check` returns `launch-acceptance-ledger-v1` and
  proves the GitHub OSS launch, platform-Agent distribution, self-host alpha, Skill Mode, published
  image evidence, commercial boundary, and privacy assertions are aligned.
- `scripts/verify_github_launch_operator_guide.py --check` returns
  `github-launch-operator-guide-v1` and proves this guide, `docs/release-checklist.md`,
  `./scripts/release_check.sh`, the launch ledger, ecosystem submission, and adoption pack all expose
  the same release sequence.
- `scripts/verify_platform_plugin_downloads.py --check` returns `platform-plugin-downloads-v1` and
  proves the Codex, Kimi, WorkBuddy, and Hermes plugin packs have release download URLs, sha256 checksums,
  import manifests, and no model keys.
- `scripts/verify_release_stack_readiness.py` returns `release-stack-readiness-v1` and proves the
  current stacked GitHub PR order, required `api-tests` and `compose-smoke` checks, and local
  before-tag gates are aligned without storing GitHub tokens, live check payloads, source text,
  learner answers, Agent endpoint secrets, or real model keys.
- `scripts/verify_plugin_quarantine.py` returns `plugin-quarantine-verification-v1`, proving
  quarantine-first plugin handling and blocked digest mismatch behavior.
- `scripts/verify_security_recovery_hardening.py` returns
  `security-recovery-hardening-verification-v1`, proving backup manifest and restore-preview safety.
- `docs/release-notes/v0.3.31-alpha.md` lists known limitations.
- Docker Compose starts with `STACK_PROFILE=core`, `STACK_PROFILE=smoke`, and `STACK_PROFILE=full`.

## Machine-Readable Launch Acceptance

The public launch decision is backed by two generated reports:

- `platform/generated/study-anything-launch-acceptance-ledger.json` with
  `launch-acceptance-ledger-v1`.
- `platform/generated/study-anything-github-launch-operator-guide.json` with
  `github-launch-operator-guide-v1`.

Before publishing, run:

```bash
python3 scripts/verify_launch_acceptance_ledger.py --check
python3 scripts/verify_github_launch_operator_guide.py --check
python3 scripts/verify_release_stack_readiness.py
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_platform_ecosystem_packs.py
python3 scripts/generate_platform_plugin_packs.py --check
python3 scripts/verify_platform_plugin_packs.py --check
python3 scripts/generate_platform_plugin_downloads.py --check
python3 scripts/verify_platform_plugin_downloads.py --check
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

Attach these release assets to the GitHub prerelease:

- `study-anything-platform-adoption-pack.zip`
- `study-anything-platform-feedback-package.zip`
- `study-anything-published-image-evidence.zip`
- `study-anything-release-asset-bootstrap.zip`
- `study-anything-platform-agent-replay.zip`
- `study-anything-adopter-evidence-archive.zip`
- `study-anything-codex-plugin-pack.json`
- `study-anything-codex-plugin-pack.zip`
- `study-anything-codex-plugin-pack.sha256`
- `study-anything-kimi-plugin-pack.json`
- `study-anything-kimi-plugin-pack.zip`
- `study-anything-kimi-plugin-pack.sha256`
- `study-anything-workbuddy-plugin-pack.json`
- `study-anything-workbuddy-plugin-pack.zip`
- `study-anything-workbuddy-plugin-pack.sha256`
- `study-anything-hermes-plugin-pack.json`
- `study-anything-hermes-plugin-pack.zip`
- `study-anything-hermes-plugin-pack.sha256`
- `study-anything-dual-loop-trust-scenario-pack.json`
- `study-anything-dual-loop-trust-scenario-pack.zip`
- `study-anything-dual-loop-trust-scenario-pack.sha256`
- `study-anything-dual-loop-trust-pack-consumer-walkthrough.json`

The human download entrypoint is `docs/platform-plugin-downloads.md`; the machine-readable download
index is `platform/generated/study-anything-platform-plugin-downloads.json`.

Merge the release PR stack into `main` from oldest to newest only after GitHub CI is green, then run
the same commands from a clean `main` checkout before tagging.

## Release Stack Readiness

`platform/release-stack.json` is the offline merge-order manifest for the current stacked release
PRs. It records PR numbers, branch names, base branches, required checks, and local before-tag gates.
It intentionally does not record GitHub tokens, live CI payloads, raw source text, learner answers,
Agent endpoint secrets, or real model keys.

Run the release stack verifier before merging each layer and again from a clean `main` checkout before
tagging:

```bash
python3 scripts/verify_release_stack_readiness.py
```

When GitHub access is available, run the live status verifier before merging each layer:

```bash
python3 scripts/verify_release_stack_live_status.py
```

While preparing the next stacked PR before it exists on GitHub, use:

```bash
python3 scripts/verify_release_stack_live_status.py --allow-missing-top-pr
```

Before merging the stack, verify the full lineage reaches `main`:

```bash
python3 scripts/verify_release_stack_lineage.py
```

While preparing the next stacked PR before it exists on GitHub, use:

```bash
python3 scripts/verify_release_stack_lineage.py --allow-missing-top-pr --report-only
```

Before the maintainer starts the real merge run, generate the runbook:

```bash
python3 scripts/verify_release_stack_merge_runbook.py
```

The runbook lists every ancestor PR from oldest to newest, any required `gh pr ready` commands for
draft PRs, the check command for each PR, recommended and alternative `gh pr merge` commands,
next-PR retarget commands, post-merge verification commands, and final branch cleanup commands. It is
safe to run because it does not execute merge commands and does not persist GitHub tokens or live
check payloads.

While preparing the next stacked PR before it exists on GitHub, use:

```bash
python3 scripts/verify_release_stack_merge_runbook.py --allow-missing-top-pr --report-only
```

Immediately before merging, after converting drafts to ready, use the stricter gate:

```bash
python3 scripts/verify_release_stack_merge_runbook.py --fail-if-draft
```

The release stack must be merged from oldest to newest. Do not delete intermediate stacked branches
during the merge run. After each merge, sync `main`, retarget the next PR to `main`, and wait for the
required GitHub checks to go green before merging that next PR.

## Tag And Push

Merge the release candidate PR, sync `main`, then tag the exact merge commit:

```bash
git switch main
git pull --ff-only
git tag v0.3.31-alpha
git push origin v0.3.31-alpha
```

Create the prerelease after the tag is pushed:

```bash
gh release create v0.3.31-alpha \
  --prerelease \
  --title "Study Anything v0.3.31-alpha" \
  --notes-file docs/release-notes/v0.3.31-alpha.md
```

## GitHub Settings

Recommended repository settings:

- Enable Issues and Discussions.
- Require pull requests before merging to `main`.
- Require the `ci` workflow before merge.
- Enable Dependabot alerts.
- Enable secret scanning and push protection if available.
- Publish packages to GHCR through `.github/workflows/docker-images.yml`.
- Confirm the public images can be pulled anonymously and publish both `linux/amd64` and
  `linux/arm64` manifests:

```bash
docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.31-alpha
python3 scripts/verify_published_image_launch.py --tag v0.3.31-alpha
python3 scripts/verify_ecosystem_submission_pack.py
python3 scripts/verify_release_asset_adoption.py --tag v0.3.31-alpha --runtime metadata-only
```

If the local pull is too slow but the manifest and GitHub `docker-images` workflow are green, record
the diagnostic fallback instead of leaving the smoke ambiguous:

```bash
python3 scripts/verify_published_image_launch.py \
  --tag v0.3.31-alpha \
  --pull-timeout-seconds 180 \
  --allow-pull-timeout-report
```

## Release Notes

Use `docs/release-notes/v0.3.31-alpha.md` as the GitHub Release body. Keep the matching file in the
repository so self-host users can inspect upgrade notes before pulling an image.
Attach the generated release zips and verify them with
`release-asset-adoption-v1` before telling platform operators to import the pack.

## What Is Intentionally Not Hosted Yet

- No managed cloud.
- No billing.
- No hosted Sync/Publish/Teams.
- No marketplace payments.
- No first-class real model runtime. Users bring their own agent.

These are PMF-stage decisions, not launch blockers for the OSS alpha.
