# Release Asset Adoption

Study Anything v0.3.31-alpha adds `release-asset-adoption-v1` so a platform
operator can start from the GitHub Release page instead of a local development
checkout.

The release entrypoint is the set of public zip assets attached to:

`https://github.com/jzvcpe-goat/study-anything/releases/tag/v0.3.31-alpha`

Required assets:

- `study-anything-platform-adoption-pack.zip`
- `study-anything-published-image-evidence.zip`
- `study-anything-adopter-evidence-archive.zip`
- `study-anything-platform-feedback-package.zip`
- `study-anything-release-asset-bootstrap.zip`
- `study-anything-platform-agent-replay.zip`

Schema contract:

- `release-asset-adoption-v1`: generated public evidence, Markdown, zip, and
  checksum for release asset replay.
- `release-asset-adoption-fixture-v1`: offline fixture catalog covering
  passing, missing asset, digest mismatch, corrupted pack, missing
  published-image evidence, and network-unavailable cases.
- `release-asset-adoption-proof-v1`: verifier output emitted by metadata-only,
  published-image, or Skill Mode replay.

## Commands

Metadata-only replay downloads the release assets, checks GitHub sha256
digests when available, extracts the platform adoption pack, verifies the pack
manifest hashes, and verifies the published-image evidence bundled inside the
pack:

```bash
python3 scripts/verify_release_asset_adoption.py \
  --tag v0.3.31-alpha \
  --runtime metadata-only
```

Published-image replay uses the release assets and then runs the published
Docker image smoke from the extracted adoption pack:

```bash
python3 scripts/verify_release_asset_adoption.py \
  --tag v0.3.31-alpha \
  --runtime published-image \
  --skip-pull
```

Skill Mode replay uses the downloaded release adoption pack while launching a
disposable local Skill Mode runtime from the current source checkout:

```bash
python3 scripts/verify_release_asset_adoption.py \
  --tag v0.3.31-alpha \
  --runtime skill-mode
```

Before the tag exists, maintainers can run the offline fixture path against the
current generated assets:

```bash
python3 scripts/verify_release_asset_adoption.py \
  --fixture fixtures/release-asset-adoption/asset-only-pass.json \
  --asset-dir platform/generated \
  --runtime metadata-only
```

## Classification

- `release_asset_adoption_ready`: required assets exist, digests match, and
  pack/evidence verification passes.
- `release_asset_missing`: a required release zip asset is missing.
- `release_asset_digest_mismatch`: a downloaded asset does not match GitHub's
  sha256 digest.
- `release_asset_pack_corrupted`: the adoption pack zip is unreadable or a
  manifest file hash drifted.
- `release_asset_published_evidence_missing`: published-image evidence is not
  present in the adoption pack.
- `release_asset_network_unavailable`: GitHub Release metadata or asset
  download is unavailable from the operator network.
- `release_asset_runtime_failed`: metadata passed but the selected runtime
  replay failed.

## Privacy

Release asset adoption evidence is metadata-only. It must not include raw
source text, learner answers, Agent prompts, Agent endpoint secrets, real model
keys, local absolute paths, private support payloads, or browser/video/app
private context.
