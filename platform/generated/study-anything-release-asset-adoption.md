# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `13febadd44ef17501ae0613aba79ad85d8e24be45528a623689e07b0452d4eb7`

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

- `asset-only-pass`: `e79247b2998f88bb75a3a3adfd161f5560065b17d348f88012e01a8200d978dd`
- `asset-missing`: `df20f1701c66787fa45528c165f0c6e152aa6c7ac853046037ae8c7ffd91cae0`
- `digest-mismatch`: `46a8bfb62f603fc44632e2a596dce6488afc9f82c7dee23db4a673e5deb9dcd9`
- `pack-corrupted`: `f68d6191cbf64a53342b04b7e79adbe27666ae772e77275472fa9dc7ac89c3ce`
- `published-evidence-missing`: `6cfa96df0d0558832e0ef52bc7ef1d5f46ef84fc894aad5844ec35647673998e`
- `network-unavailable`: `7289284d9d5e204a28f72dd290c55562a8b42ef4bbb46207ff1aeaaf4bd8a150`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
