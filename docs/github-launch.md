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
python3 scripts/generate_platform_bundle_manifest.py --check
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
python3 scripts/diagnose_adoption.py --ghcr-timeout-seconds 5
STACK_PROFILE=smoke ./scripts/launch_self_host.sh
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
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
- `scripts/verify_published_image_launch.py --tag v0.2.16-alpha` can pull the public API image,
  verify the running API version, and complete the API learning loop.
- `docs/release-notes/v0.2.16-alpha.md` lists known limitations.
- Docker Compose starts with `STACK_PROFILE=core`, `STACK_PROFILE=smoke`, and `STACK_PROFILE=full`.

## Tag And Push

Merge the release candidate PR, sync `main`, then tag the exact merge commit:

```bash
git switch main
git pull --ff-only
git tag v0.2.16-alpha
git push origin v0.2.16-alpha
```

Create the prerelease after the tag is pushed:

```bash
gh release create v0.2.16-alpha \
  --prerelease \
  --title "Study Anything v0.2.16-alpha" \
  --notes-file docs/release-notes/v0.2.16-alpha.md
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
docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.2.16-alpha
python3 scripts/verify_published_image_launch.py --tag v0.2.16-alpha
```

If the local pull is too slow but the manifest and GitHub `docker-images` workflow are green, record
the diagnostic fallback instead of leaving the smoke ambiguous:

```bash
python3 scripts/verify_published_image_launch.py \
  --tag v0.2.16-alpha \
  --pull-timeout-seconds 180 \
  --allow-pull-timeout-report
```

## Release Notes

Use `docs/release-notes/v0.2.16-alpha.md` as the GitHub Release body. Keep the matching file in the
repository so self-host users can inspect upgrade notes before pulling an image.

## What Is Intentionally Not Hosted Yet

- No managed cloud.
- No billing.
- No hosted Sync/Publish/Teams.
- No marketplace payments.
- No first-class real model runtime. Users bring their own agent.

These are PMF-stage decisions, not launch blockers for the OSS alpha.
