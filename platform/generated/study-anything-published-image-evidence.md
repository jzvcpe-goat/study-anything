# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.26-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `50d2865e53ded046bebce4ea625d80879bc5999ecf90827ef5cd004b2c455cba`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.26-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.26-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.26-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `ba5fb569a53b66415fe9cd0b02ff1714347952964ff6f0abc03d82ef91971d46`
- `cached-image-missing`: `9fac55e48488f8957c9db0f1b73d5ed298c44e84610ed41ad876e3ed45eb0573`
- `compose-up-timeout`: `3a62fb8c1de310eba3912946663717a1af6363d5da6bb7155ed94a0137facebd`
- `manifest-only-runtime-unverified`: `acfcea56b16406451677e3fde8cc24fad7e99cf7ea9bcabd476343988a46cda8`
- `manifest-missing-platform`: `d9d93f779b703ac1b3f6a6e3dbe8d7a1e36a573818d1f2457da01d616a68a525`
- `docker-images-failed`: `cc59e7cfa233ebbf9474dedc00705a831d9b9dac483060b316b325ed683d802a`
- `ghcr-unavailable`: `0468b1777673cc30ab382a2bad64c96a1aa604dff94dd0a7080cac62b0a4a7ef`
- `remote-smoke-pass`: `d9250c9291635eeafb919e915afde1094695516927357dc1836c72dcf5efc8f3`
- `remote-smoke-failed`: `819f82d515f2ae27677a80b6c2edf1c9e7b37b6565421aca481cc70554751467`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
