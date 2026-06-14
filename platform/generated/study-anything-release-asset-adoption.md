# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.24-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `3f4429de197f8046e11421c5925c21b22469c1dd556e9668aaa794c78b52bdc0`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.24-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.24-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.24-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `fc2984a8abc63c5448d0ce3e899aef667bf78cbeae184a575b8388e6b414143c`
- `asset-missing`: `e3ce1fa990b11f9e91eca569330b449bd67936f24ee224587baf4ba41ad9c0e7`
- `digest-mismatch`: `3ae1f83b6a6981c910c7da1993ee2a0dd2aebf6115e4d7a95be3266923b4a43d`
- `pack-corrupted`: `a3b51b809f750d231e80b381968d45dd3f8e87c7d474165d336412569db890db`
- `published-evidence-missing`: `5aa222c729147611fc2d3e9012da5a99fdc85aad492240567ae97b6f2aa9564f`
- `network-unavailable`: `f78d9200c23dee7aaf931148c0ae86daac6a75fa5ce40be528ef1933a757e05e`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
