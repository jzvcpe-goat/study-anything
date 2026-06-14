# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.23-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `bbc5410a7bb078ea0daba5ab02e69409252a13666ce5a4c5a536ba991bcf9f9c`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.23-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.23-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.23-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `c4430883c1be80811ddf1c81373d0580eabf3802a9a60dd1deb111849540daec`
- `manifest-missing-platform`: `c96bf519d5aa5d1b90fe2d324687374bbba7f74097cde75639ec1d6a175e3691`
- `docker-images-failed`: `7202361270d7e5cc5982403ce8b01a1f44b6642cd41002c09e3dd5fccdfa6ae6`
- `ghcr-unavailable`: `7b0254a405917dbc741392393f9599a6e90bce025ad146d3a1ee9e36fc450de1`
- `remote-smoke-pass`: `7e62b2c60314352e6f9d6a1500cf08c5b2f5be405e25faff46af38a477b1dcd6`
- `remote-smoke-failed`: `4921947b98d78ca8eed79cb7b7c1d2d7f59a5fe8afae86fb5c629c73a91ea593`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
