# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.27-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `98d5cf62bd16bb9413f6bc9f47e7bc8260a42d33beffb78996360f7b7b5afa34`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.27-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.27-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.27-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `514bafe2da3c65dcc3fe6d096e9f6682c8aec4938ac9a7ade2a8abfc40b1182e`
- `cached-image-missing`: `e243d43466c462b0eb537339a4cb05d578e6a3dccc6f4ca97b91537d97ea14cd`
- `compose-up-timeout`: `63eb855671f7a37c49acbd1b93aa0a4f0d2eae615466ebf6a45c693674820e64`
- `manifest-only-runtime-unverified`: `bff6102329c4e0c0b7709cf42cfb6b0b72c00b8fc41c92e8220af2f646553d45`
- `manifest-missing-platform`: `c6b4211e82230650ffe5e2cda459e4b80e7227a281535de0bdc53b3e0d5b5e10`
- `docker-images-failed`: `36d19b436b7da38efe1eeb9ef2f985a33a03b06200251e2f9eaf35d96211763a`
- `ghcr-unavailable`: `19921bc0900b5b2217786903e2273c8ae81abb6cf1ea5288b6128b3956edec35`
- `remote-smoke-pass`: `e07b1cd45bdca938ab838ca4c94b75b8062a363f383367e66042d0100f4dc547`
- `remote-smoke-failed`: `d08c5116aecfb379c4fbc8353f08a863a2aa075484a728498acca991a80f0f5f`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
