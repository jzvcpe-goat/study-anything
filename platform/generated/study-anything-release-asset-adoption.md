# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.26-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `776e605379a92aca145f469d61d59256e2765293b57baa557ad1740ce77c592d`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.26-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.26-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.26-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `2a231784816f2791dbc119802479ed9ed36f02e2c716b3e430a14cf507a243ab`
- `asset-missing`: `42d60f60b8a998fa6b0c94446599f4570ab63d6a201fa16fa99ec033d3d37a9a`
- `digest-mismatch`: `bbb4e1a8d4c6c3060cc0bd7dc0c69a9d4855a019ba398c7433a4d1f643d83530`
- `pack-corrupted`: `d333cfa1069e48d98410f6fd19aaa213b920b682f2aed43bb4e8923d263292a3`
- `published-evidence-missing`: `b4ff5c72d6962110562fa1f8563a3f93d4e56d31f1b7c9f572c4bd44372e7b8f`
- `network-unavailable`: `cc46f458ca049828b02dd097f5911c9672d34d431ff5b8ea6f8916935baaf804`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
