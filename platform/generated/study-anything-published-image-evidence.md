# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.30-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `040bfc69ecd5367479b8657f1a8b218f2ee83e0fb7d615156521b133f95248ab`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.30-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.30-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.30-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
- Timeout status: `blocked_by_local_ghcr_pull`

## Local Pull Timeout Acceptance

- `manifest inspection shows linux/amd64 and linux/arm64`
- `docker-images workflow succeeded for the release tag`
- `release_check.sh and external adoption proof passed before tagging`

## Classification Matrix

- `published_image_ready` -> `pass`: Manifest, CI, and local or remote smoke all passed.
- `local_pull_timeout_with_valid_release_evidence` -> `acceptable_with_manifest_and_ci`: Local Docker/GHCR pull timed out, but independent manifest and CI evidence are valid.
- `cached_image_missing` -> `needs_pull_or_manifest_only_recheck`: Cached-only verification was requested, but the local machine does not have the image.
- `compose_up_timeout` -> `needs_independent_recheck`: docker compose up did not finish within the bounded verifier timeout.
- `manifest_available_runtime_unverified` -> `acceptable_only_with_successful_ci_and_release_check`: Manifest platforms are available, but no local runtime smoke was executed.
- `published_image_platform_gap` -> `block_release_claim`: The manifest is missing linux/amd64 or linux/arm64.
- `ci_image_publish_failed` -> `block_release_claim`: The docker-images workflow failed or did not publish the expected tag.
- `registry_or_network_unavailable` -> `needs_independent_recheck`: GHCR or local network access failed before platform status could be proven.
- `published_image_runtime_failed` -> `block_release_claim`: Image exists, but the container failed health/version or full API smoke.

## Fixture Hashes

- `manifest-pass-local-pull-timeout`: `626a07e4223c0f981bc364fe77235088e0f5c086e3541dc892aa0e883ffcedd4`
- `cached-image-missing`: `3c02fb8936e391597a648cd5d3b52b7c43422712d2a5fbe129e1c0677875922a`
- `compose-up-timeout`: `f86e1f6766225f19bdf79a53fa702a92811986b32eb19e90ec44e9bc6118a49c`
- `manifest-only-runtime-unverified`: `87fade1d1c5b8fcab643a0cb30a95208882ef262a2b296bee926c5a386403d13`
- `manifest-missing-platform`: `97099004fbfe27e054bf11778cb4dc20ddd2c71202db96ee138c7cb232435ae1`
- `docker-images-failed`: `dd346c359144f9aa6159bc0d9a48cd0e67f73305ec9f2714edbed7c31a3b5502`
- `ghcr-unavailable`: `e06abf74cc53311f9b242f4433e225eb24c0a7c3333dbd11aee2a82e0c3af8d1`
- `remote-smoke-pass`: `c376b52f993cc00743fb6f697256aa6a507c2589987c9cccc41ffc806993253f`
- `remote-smoke-failed`: `cfed2779c6b6580c87a24cf9a6e458ac8b931c95d4719d826db4dc58b57738ef`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
