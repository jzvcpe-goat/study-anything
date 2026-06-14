# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.24-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `7ac9246daae529bc5b7eabb5b0d63d4758705da95c463611556d1ad63c2aa925`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.24-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.24-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.24-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `07e402a95813a47d967fa60ad0bf4a618bea47d06f9cc42c77bf3c8e84730f96`
- `cached-image-missing`: `715f407c0a7f8395f31dcc66f4158c9455f894b7ba00d8388b1c0f7313a484ff`
- `compose-up-timeout`: `ebc09167fdb254fe82c11da3f4a56720cb715aed257000ba345bd782f03e162c`
- `manifest-only-runtime-unverified`: `06dcafd1db5d9ce00b63e8f7295732c6c0459c2a0bf94a23564628df110971c5`
- `manifest-missing-platform`: `2554cfb3d9a90405cd9807c32d1b8832d2c8cb2068d5f89947df94fe9ab51407`
- `docker-images-failed`: `306b90c70fd5dd6a0fc4362668a7dbc012697ae40fb8410bfb538dd5629ed33f`
- `ghcr-unavailable`: `bc346a256f02062cf02484169deb036a2d0fcb6de65415e4471b35f56531ca79`
- `remote-smoke-pass`: `64fc8976bfc163966796f3929b4e9cfde96ab229c5702d4dda6f86c5bd0b2d6e`
- `remote-smoke-failed`: `527f59383e8ae77ae91275ca5285f97ec340bf522b6433b4db745eea9609b56d`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
