# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.29-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `69eb93edb87be273d1c30acea555363aeb8d624c88fe1329deab087a41c2531c`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.29-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.29-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.29-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `d6a87f4aebf879885b0cfa14a6c99520491e4bc9600565050ef3b826e5744dc4`
- `asset-missing`: `bc166970847d74a5b3a6ef97d63ce79a60d33efac98596997315aa2f3b344c8f`
- `digest-mismatch`: `cb955e5922800748bd86412cf3d73741bb3f460b23f0adf13d1498693130c684`
- `pack-corrupted`: `8e76ffab6c8319d8d5be08e6fd7a6fae3c7dce8e22fc4f096aaabacc97c9efec`
- `published-evidence-missing`: `cfb2860342e37c6481435caf06641c6d1d894cd56d63fb979adc4372346f0042`
- `network-unavailable`: `d025b5b9a31357b59e972458fe83b0ac5ae9a23b9c81e8bbc2c8e24f8488e75d`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
