# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.27-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `c1f3601aa1a8d31cf10de7baceca3b97c6fdff1abafde810e060be7f4c292bf4`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.27-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.27-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.27-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `0e2358a1c348f7d83190997814440d5a9ae453359647c383d214ff2db7f45459`
- `asset-missing`: `5a9c79a3f6cfae4e96277aceb6a737ab1861a3933faf8faa885fa2876d1396c1`
- `digest-mismatch`: `db596e0d62b7143fe9f07fe0c79f0ada0959dcc42a2a19d31a8b0fb3b06d93c1`
- `pack-corrupted`: `5733a7b688fe9ae1a8be2569c8fe44b02cf54da9fbb9ff9360b7a6e5d576534c`
- `published-evidence-missing`: `d97d9963edb5b8b6fc456d506efed9c0b26d64a78ae026a0db9ea79f0f6e8729`
- `network-unavailable`: `5d06e9db1581691e03201c55a701c694f129558e9ba9741c03aa6249fc93b91a`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
