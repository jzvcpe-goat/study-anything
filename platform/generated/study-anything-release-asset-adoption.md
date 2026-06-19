# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `2121ececb118793ff650ac3651db101d2c17090657e5ca10a9802f16e0caf0ee`

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

- `asset-only-pass`: `92b88baeeee5c1b067d8a689d2467f4b0a42767c6d04862c704289483be126cb`
- `asset-missing`: `df20f1701c66787fa45528c165f0c6e152aa6c7ac853046037ae8c7ffd91cae0`
- `digest-mismatch`: `3e58d2a2eac64685ad168918dd6a35a81b49a2ed6e4359ffb8e5856abc4fb4f5`
- `pack-corrupted`: `5f9a6a938847921152b53a2331e0f828051a0052d7e4b6389490c90b02a8f9de`
- `published-evidence-missing`: `b88557fbf1057f91b45a28e3275dbca557b744c171db0237faedfd0d606a2ab1`
- `network-unavailable`: `7289284d9d5e204a28f72dd290c55562a8b42ef4bbb46207ff1aeaaf4bd8a150`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
