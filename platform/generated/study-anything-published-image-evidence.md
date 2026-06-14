# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.22-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `2f41431dc8f11ea94d551b6f31a33fd76a30287246df050f75434143e6a33453`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.22-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.22-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.22-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
- Timeout status: `blocked_by_local_ghcr_pull`

## Local Pull Timeout Acceptance

- `manifest inspection shows linux/amd64 and linux/arm64`
- `docker-images workflow succeeded for the release tag`
- `release_check.sh and external adoption proof passed before tagging`

## Classification Matrix

- `published_image_ready` -> `pass`: Manifest, CI, and local or remote smoke all passed.
- `local_pull_timeout_with_valid_release_evidence` -> `acceptable_with_manifest_and_ci`: Local Docker/GHCR pull timed out, but independent manifest and CI evidence are valid.
- `published_image_platform_gap` -> `block_release_claim`: The manifest is missing linux/amd64 or linux/arm64.
- `ci_image_publish_failed` -> `block_release_claim`: The docker-images workflow failed or did not publish the expected tag.
- `registry_or_network_unavailable` -> `needs_independent_recheck`: GHCR or local network access failed before platform status could be proven.
- `published_image_runtime_failed` -> `block_release_claim`: Image exists, but the container failed health/version or full API smoke.

## Fixture Hashes

- `manifest-pass-local-pull-timeout`: `9c93fa6de6a0f0e64da8d3175229e8a59b3e45a47e1fd0bffe5ed03e358531c5`
- `manifest-missing-platform`: `430068299decf2b297f78beed5e6a0f3f6b5c778c0a77263ea7fc9e07fd4b509`
- `docker-images-failed`: `e695a983b212004fe842ce467dbca0ba6e3182b8743e8cbb054ad3b2c6fec98c`
- `ghcr-unavailable`: `192a00b80cf40fa5de7535dfea2bee31bd12270b5840b30182f6ac5756f9bf1d`
- `remote-smoke-pass`: `30f49bec6c89b243b9ee6228b51423618b991f0e43fe006c874104c73baa4abc`
- `remote-smoke-failed`: `ed2c1e4393b3191d4fb6f106e9528f46d21899b1626a42a602f2f9c984f04047`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
