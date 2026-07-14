# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `2ae594fa4f772e90e6d385ec8699aa27480998dc853a5765b6b5ecdab0b8fada`

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

- `asset-only-pass`: `241ec9aba0e618b21f2e5008eac61ad437d7821934cfa80f8fd942947dd21ca9`
- `asset-missing`: `df20f1701c66787fa45528c165f0c6e152aa6c7ac853046037ae8c7ffd91cae0`
- `digest-mismatch`: `947103edfc6c277486c4d364af4a64fe4c8d21dbaa4c7181d5db4d5faf8aba25`
- `pack-corrupted`: `bcbc25ba68bf0c57d4a83b29fa3fe63ce8721c78efc858a2a566b913ad3fc239`
- `published-evidence-missing`: `611978c740604c7d208cf510cc0e44eb03123288ebe94c85511c52d8f5f11980`
- `network-unavailable`: `7289284d9d5e204a28f72dd290c55562a8b42ef4bbb46207ff1aeaaf4bd8a150`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
