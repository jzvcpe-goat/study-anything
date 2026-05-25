# GitHub Launch Guide

This guide is for the first public alpha launch. The goal is open-source and local-first: users should be able to clone, inspect, run, and extend Neural Console without creating an account or giving Neural Console model keys.

## Launch Positioning

- License: Apache-2.0.
- Distribution: GitHub repository first, Docker Compose self-host first.
- Real reasoning: Bring Your Own Agent. Neural Console stores endpoint/config metadata, not real model API keys.
- Monetization: not in the MVP. Future hosted services should sell convenience and collaboration, not lock-in.

## Before Creating The GitHub Repo

Run:

```bash
python3 scripts/setup_env.py --force --output /tmp/neural-console.env
python3 scripts/check_env.py --env /tmp/neural-console.env --strict
./scripts/release_check.sh
STACK_PROFILE=smoke ./scripts/launch_self_host.sh
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py
API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://mock-http-agent:8787 python3 scripts/verify_mock_http_agent_flow.py
./scripts/stop_self_host.sh
```

Confirm:

- `.env` is not staged.
- No screenshots, traces, or logs contain private source text or secrets.
- `docs/release-notes/v0.1.0-alpha.md` lists known limitations.
- Docker Compose starts with `STACK_PROFILE=core`, `STACK_PROFILE=smoke`, and `STACK_PROFILE=full`.

## Create And Push

If using GitHub CLI:

```bash
gh auth status
gh repo create neural-console --public --source=. --remote=origin --description "Open-source, self-host-first AI-native learning console"
git add -A
git commit -m "Release v0.1.0-alpha self-host MVP"
git push -u origin main
git tag v0.1.0-alpha
git push origin v0.1.0-alpha
```

If the repo already exists:

```bash
git remote add origin git@github.com:<owner>/neural-console.git
git add -A
git commit -m "Release v0.1.0-alpha self-host MVP"
git push -u origin main
git tag v0.1.0-alpha
git push origin v0.1.0-alpha
```

## GitHub Settings

Recommended repository settings:

- Enable Issues and Discussions.
- Require pull requests before merging to `main`.
- Require the `ci` workflow before merge.
- Enable Dependabot alerts.
- Enable secret scanning and push protection if available.
- Publish packages to GHCR through `.github/workflows/docker-images.yml`.

## First Release Notes

Use the existing release notes as the GitHub Release body:

```bash
gh release create v0.1.0-alpha \
  --title "v0.1.0-alpha Self-host MVP" \
  --notes-file docs/release-notes/v0.1.0-alpha.md
```

## What Is Intentionally Not Hosted Yet

- No managed cloud.
- No billing.
- No hosted Sync/Publish/Teams.
- No marketplace payments.
- No first-class real model runtime. Users bring their own agent.

These are PMF-stage decisions, not launch blockers for the OSS alpha.
