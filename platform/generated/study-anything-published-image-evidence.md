# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.25-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `1fbccfd4275000eb9ad9e41a31f3d4dde628b6f5dcfd4410f956c53d8b1f403c`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.25-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.25-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.25-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `551ee6ccf3b0ce3a3d864c84753f71e010ff52d211f39ddb764b9fd9536623ef`
- `cached-image-missing`: `165c1692c422536e7c81acb9269e33dffb988ea28f933a6f294036d4256ece5d`
- `compose-up-timeout`: `f03181989537dadd38a4c569b6f71d614e617871b8a719383480907ae9a60f4c`
- `manifest-only-runtime-unverified`: `32b1f19773f9704cc9283c5bb79b86577365d4d59ff26f17d97e1ae8c88bb5f0`
- `manifest-missing-platform`: `6976b9318f3fe707e4bd8e4ffa3889319304bf9fca8d10ede1ea23cbc3a5a341`
- `docker-images-failed`: `05a63c3a4cb537c321de17f4d8f1e8a1d7c25f67313d63301e97765771c73e91`
- `ghcr-unavailable`: `eff461ea4b60f6708719883a6a08c620ebc1debfa47717a9e910132f363a4dd8`
- `remote-smoke-pass`: `0600f7212ef2846ab285f05bd2a0c264810e8933b3ae6af61a2eb824f456ac59`
- `remote-smoke-failed`: `182bd6a4364b78b93da766620c404c38388d751b1699201d002e9176759b7c05`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
