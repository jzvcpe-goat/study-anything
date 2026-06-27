# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.29-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `e4f7117003be4c1e707c3ab1c08e9be950811a62ad276387f9aa6f624b5436c1`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.29-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.29-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `a016b4faa76ed6f4264dbd9064cf6b0e693642ff56eefd5325ad781d5036a45b`
- `cached-image-missing`: `971f9c699b0d38c6b49a4b136312d7b65fe78bc855651d44e079cfe44b2d71c3`
- `compose-up-timeout`: `6834f392d7bcdd6b4791479eea1262792cf623e9c3de6a59a55afff5c67b736d`
- `manifest-only-runtime-unverified`: `2033dfe42edd6b70db641f250771979f12537a4a7ef7a0a9b432f94e8dcff2b9`
- `manifest-missing-platform`: `07f02864a7e55d85aecf92cfd7efcef261d29b3a49aa162c961a85891224d9c4`
- `docker-images-failed`: `696a398383dca06c649d119e01153e74a18154ef5308666a36be3e441ccbdc0c`
- `ghcr-unavailable`: `59c5aa30f1bdc94fa9089eda7899485553b5ba0a5115a41c33706e859b174000`
- `remote-smoke-pass`: `5ad34e66b82c73c5735ce80369e4d931669ed5cdb6b40abc9e5b6ecf3946b1f7`
- `remote-smoke-failed`: `0631652c3d98802f18bf7695ff7f530a7cf9253584204bc8732cb8320e82f125`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
