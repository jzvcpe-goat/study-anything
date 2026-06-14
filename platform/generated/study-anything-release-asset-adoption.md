# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.23-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `25aaada5315eb1274ae30b0f5c5325e750eab9f0b1da9bc7ada501264556f66a`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.23-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.23-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.23-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `cfd242c2a1fc1ad4b0762c65aa010aa429bf4d1a494645f89c9d0379f4a26c4a`
- `asset-missing`: `53a084158efa4099940fe7cdf17aa8ed222e08ab75ef5cd496e1070b98425782`
- `digest-mismatch`: `6101d93d6b784651af9c7cc255ade0c4e60a1400f6d160c275e7fa1c9aa0371c`
- `pack-corrupted`: `ff8f1832c88cfaedcd523d76b3e667e541f7cb8aa2bdea2d46c177084a42c841`
- `published-evidence-missing`: `8a7346f925bee96be91390d0d2b7d5b670ae2197fcc036a25f945d4e1714129b`
- `network-unavailable`: `dcf50dc3e53839c5f7729e0552f609a5a2280ff528565ca7f8e3487d9290ed6b`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
