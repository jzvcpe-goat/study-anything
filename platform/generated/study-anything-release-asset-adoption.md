# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `04fe43ce082564a6c61e5950ffe5aebeeb84f5fa03e7b89c779d6e46247bc275`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.31-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.31-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.31-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `3715aaab731b87183e0c0171f52548294cc6d5b5f4ff91df0aea5dd3251647e3`
- `asset-missing`: `df20f1701c66787fa45528c165f0c6e152aa6c7ac853046037ae8c7ffd91cae0`
- `digest-mismatch`: `de76c9a958e7647d8cd04c3103a8135f4e52b3b6a15155e5dada81180338b762`
- `pack-corrupted`: `ec73e9d4f8522f3fa79dfa6dc846de30b77768c749a3242849b4b1f212f3582a`
- `published-evidence-missing`: `b83e99873ea02b805e980b2ed1b22ba7181a5ea33eebe977a947933ea648d69d`
- `network-unavailable`: `7289284d9d5e204a28f72dd290c55562a8b42ef4bbb46207ff1aeaaf4bd8a150`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
