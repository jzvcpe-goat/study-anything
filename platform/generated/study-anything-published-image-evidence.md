# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.28-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `19bef579d00d2befcf3fad84bb6858b1c905b3f367894ce0f60ee7b9fa9a00aa`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.28-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.28-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.28-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `a8331a3331dbf1466938c52256bf9e2526962c708e623c04f74e82bbeae21311`
- `cached-image-missing`: `3fb852f9cbbca1c6db6a476c2423938366e8e36216b3c3b50f18df4e4c9b289a`
- `compose-up-timeout`: `f121266134a4e32f91c03107343ea4e18787e23e54cc92d98a7f7d5ad804509c`
- `manifest-only-runtime-unverified`: `334eae713a826425d36c4204420323611fafdf07f728affcc9056c7f946a224e`
- `manifest-missing-platform`: `1cbe29d9ac33a87fa5966746e9dda1e691fe5e699418d18a663d32c182d81d5b`
- `docker-images-failed`: `25691f4f508b2bd010b42e51e6ab41f1230ee23ed7247f703f8fc5b6cc1992b2`
- `ghcr-unavailable`: `ea22e3fa58260c8c01c43cf7a17ab4e996e42b7d2aea5fd286302f15f499aa1d`
- `remote-smoke-pass`: `abdffe0365123d87aab5dc2de7191ada77f6124fa901c8edc7c36253989b539c`
- `remote-smoke-failed`: `6a850ac95d5597d8c36cac04bbfe7af7a7fcd81503d167d32bce514750b5d875`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
