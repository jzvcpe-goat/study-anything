# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.28-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `69170248df8809fbf5d047ac40f092697e0862988c62002a9fc63dd5f9dd0db1`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.28-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.28-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.28-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `9865b9122a95a576588464c7e5e1d261a375e4b7336dfe7529db87e4c0180963`
- `asset-missing`: `15ebf293aa9955564bb33193f88cb91c7519121b0363d1174932b29bbe4de65f`
- `digest-mismatch`: `4aa9f61ea1a9e36c2e7879ef929c23efb5a5d9d0bfcfe0604be61c397fcc0f20`
- `pack-corrupted`: `f7a2f1288338c9917a17e8e7da30acc3c715ac3fa366779348ade6b6acffe431`
- `published-evidence-missing`: `fb9f151a04acef73d8d689fc846f0cd5692400e577f21b263471338b4df72552`
- `network-unavailable`: `b12d5736b99cef387958c69509988f1982346cde202b1baf4a2725529a12752f`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
