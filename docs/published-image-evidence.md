# Published Image Evidence

Study Anything v0.3.25-alpha adds `published-image-evidence-v1` so an external
operator can tell the difference between a broken release and a slow local
Docker/GHCR pull.

The public evidence bundle is metadata-only. It records the release tag, API
image reference, required manifest platforms, docker-images workflow checks,
local smoke commands, optional remote replay commands, fixture classifications,
and privacy assertions. It does not include learning source text, learner
answers, Agent prompts, Agent endpoint secrets, model keys, local absolute paths,
or private support payloads.

## Generate And Verify

```bash
python3 scripts/generate_published_image_evidence.py
python3 scripts/verify_published_image_evidence.py --check
```

To verify the same assets from the adoption pack:

```bash
python3 scripts/verify_published_image_evidence.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

The generated assets are:

- `platform/generated/study-anything-published-image-evidence.json`
- `platform/generated/study-anything-published-image-evidence.md`
- `platform/generated/study-anything-published-image-evidence.zip`
- `platform/generated/study-anything-published-image-evidence.sha256`
- `fixtures/published-image-evidence/*.json`

## Classification

`published-image-evidence-fixture-v1` covers these public operator states:

- `published_image_ready`: manifest, docker-images CI, and local or remote smoke passed.
- `local_pull_timeout_with_valid_release_evidence`: local pull returned `blocked_by_local_ghcr_pull`, while manifest and CI evidence remain valid.
- `published_image_platform_gap`: the manifest is missing `linux/amd64` or `linux/arm64`.
- `ci_image_publish_failed`: docker-images did not publish the expected tag.
- `registry_or_network_unavailable`: GHCR or local network access failed before platform status could be proven.
- `published_image_runtime_failed`: the image exists but runtime health/version or full API smoke failed.

## Release Rule

A local pull timeout is acceptable only when all three are true:

- `docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.25-alpha` shows `linux/amd64` and `linux/arm64`.
- GitHub Actions `docker-images` succeeded for the release tag.
- `scripts/release_check.sh` and external adoption proof passed before tagging.

If any required platform is missing, docker-images failed, or a remote smoke run
fails after the image starts, treat the release claim as blocked.
