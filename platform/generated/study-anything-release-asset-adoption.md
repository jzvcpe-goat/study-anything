# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.30-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `cca6ef7bef938ecf98959294562b70c1eee72cbaf010ae74ee8030221ce0b2bd`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.30-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.30-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.30-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `76891231a68654db29e7482341862a8e7df7736f1cf6a47ef01bb4f2bfc014d9`
- `asset-missing`: `70e3ab793ffd1c6d7f37f11a05a52a8cd49c24a7b64476206f9e236dae678065`
- `digest-mismatch`: `ed8a3ee31bbf456ed0ebe996b21c77eaedba754aaa58f6279612797cc04d3009`
- `pack-corrupted`: `44717fd6d01fc11cf44df09f9aa01e437e6b5094bf1479f330ad0f137eeb02a5`
- `published-evidence-missing`: `84d65e6a9d1c04563c46cf4fc6435fc4d110e689d0627b4d4e3b084c03fd401e`
- `network-unavailable`: `9b511d1caa29692c0a5b5f807a1ca5f3829c57a247b45598ff888256f55d0ff7`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
