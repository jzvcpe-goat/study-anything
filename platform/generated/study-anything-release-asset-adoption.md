# Study Anything Release Asset Adoption

Schema: `release-asset-adoption-v1`
Version: `v0.3.25-alpha`
Status: `pass`

This evidence bundle makes the GitHub Release page the adoption entrypoint:
download the zip assets, verify their digests, extract the platform adoption
pack, then replay metadata-only, published-image, or Skill Mode checks.

## Archive

- Archive: `platform/generated/study-anything-release-asset-adoption.zip` sha256 `ae5e9c659286d8e3a0dae1658e3628180420144915d77e377ffdaca241408061`

## Commands

- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.25-alpha --runtime metadata-only`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.25-alpha --runtime published-image --skip-pull`
- `python3 scripts/verify_release_asset_adoption.py --tag v0.3.25-alpha --runtime skill-mode`
- `release-asset-adoption-proof-v1`

## Classification Matrix

- `release_asset_adoption_ready` -> `pass`: Required assets are present, digests match, and pack/evidence validation passes.
- `release_asset_missing` -> `block_release_claim`: A required release zip asset is missing.
- `release_asset_digest_mismatch` -> `block_release_claim`: An asset digest does not match GitHub release metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The adoption pack cannot be opened or its manifest hashes drifted.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Published-image evidence is absent from the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or asset download is unreachable from the operator network.

## Fixture Hashes

- `asset-only-pass`: `f123ce1d17f330427c57b03567512981cb9e97af69a548da42bd8b9f582ffd54`
- `asset-missing`: `465bb6c95becc80490802da06fd32ee593e9b21dfcf56fb33dfd54c5d8a6794d`
- `digest-mismatch`: `32a38663d196c849a63bc734bb1cb6218330d7de8149190d70947aecb7c1df48`
- `pack-corrupted`: `398ded5840c86d4c5b768f821eeac68169f894043ac066d208505bff0bd3184c`
- `published-evidence-missing`: `43906a5300ce34921c7e865098b5b1aa354bd39fc5a99e0d8986b0c151d9d347`
- `network-unavailable`: `5456378078771c3fe2acb067f59307ea2c0303a358f278dfea5c85245f91f542`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
