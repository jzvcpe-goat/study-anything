# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.23-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `c8d75b236b7c53574165a379ad18aa0573337022a1ffb858f9f4d4d7af4f21f5`

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

- `asset-only-pass`: `bed7084f9e03360161701e1d7e3fd29f35a2801234a2bc5f2117b613bb4a4766`
- `asset-missing`: `53a084158efa4099940fe7cdf17aa8ed222e08ab75ef5cd496e1070b98425782`
- `digest-mismatch`: `b8d6942b5f196f8316a46b47737b2e699a9d9db2c2abba1c8a7d440158535d3c`
- `pack-corrupted`: `866f8a11fc3651ad2ae7f81596622944ab8cec4156867974b8fdcc3833df0101`
- `published-evidence-missing`: `779ef66d6086e5215ec71b6e1e2bf2f7ebb3d60a4343fcb072761d95cfa4940c`
- `network-unavailable`: `dcf50dc3e53839c5f7729e0552f609a5a2280ff528565ca7f8e3487d9290ed6b`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
