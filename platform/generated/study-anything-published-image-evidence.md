# Study Anything Published Image Evidence

Schema: `published-image-evidence-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This evidence bundle helps an external operator decide whether published GHCR
images are deployable or whether a failure belongs to the local pull path,
registry access, CI publishing, manifest platforms, or runtime health.

## Archive

- Archive: `platform/generated/study-anything-published-image-evidence.zip` sha256 `869798dfa8c5e668d290232bac6acd646baab97cf8370e8178d92ec7c4edf97a`

## Manifest And Smoke

- API image: `ghcr.io/jzvcpe-goat/study-anything/api:v0.3.31-alpha`
- Manifest: `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.31-alpha`
- Local smoke: `python3 scripts/verify_published_image_launch.py --tag v0.3.31-alpha --pull-timeout-seconds 600 --allow-pull-timeout-report`
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

- `manifest-pass-local-pull-timeout`: `e63cc3814b2ed001ef952b68caeab3414ffcaf356b1cc97149e31d001b07aaae`
- `cached-image-missing`: `d80cd6f3e5f34e935416701861948d57cd7c1be2a5129a7bab7e51556834771e`
- `compose-up-timeout`: `2788449ac21960702d91c7c0228b324844bf9f96e9d318128620ec5aa8069053`
- `manifest-only-runtime-unverified`: `51b7832e42b9703630f18898d6a05f84cad7d64a41fd89aa7b90656b8100afac`
- `manifest-missing-platform`: `a67d2674c27a2b6f8be9307b35163a93ab42294f6508e95b833646c418e09bc2`
- `docker-images-failed`: `0a098a02d389e40ca96f1259d7ebe370703609f3b64a5228f120d4fb518584b0`
- `ghcr-unavailable`: `181338b1744d1d833ea86f45af47a9d4d0c798798a5ed4f6df537377d37c30d8`
- `remote-smoke-pass`: `fe10b6003bc27dea31fdc1bb218e27b6d8d6abbdf27241e9b4313637ff68497a`
- `remote-smoke-failed`: `2f0678853567ddac156e2661f57522d04689dfd230b82e88b27d9847bf876e05`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
