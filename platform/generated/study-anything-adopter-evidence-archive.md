# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.30-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `1cbc856a3cd5aeef63f3d4e77d4a654d39e767f513252e6e9648aa457bfc27de`

## Reproduction Commands

- `python3 scripts/verify_adopter_evidence_archive.py --check`
- `python3 scripts/generate_adopter_evidence_archive.py --check`
- `python3 scripts/verify_published_image_evidence.py --check`
- `python3 scripts/generate_published_image_evidence.py --check`
- `python3 scripts/verify_release_asset_adoption.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only`
- `python3 scripts/generate_release_asset_adoption.py --check`
- `python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree`
- `python3 scripts/verify_platform_public_support_status.py --check`
- `scripts/release_check.sh`

## Known Limitations

- Localhost access depends on the host platform.
- Real model credentials stay inside the user's own Agent or platform runtime.
- Local GHCR pulls can be slower than CI and may need manifest-backed timeout evidence.

## Fixture Hashes

- `successful-release`: `10abb78eb6357b9f596085af00329c3620fcf72730b69f03ba1f096d7c9e781c`
- `local-ghcr-pull-timeout`: `1e2c8eda8494590efa90bdb31aafd8b75352cd7cf9576f390716d18311ae8b04`
- `needs-repro-issue`: `f66a5bf25f68abcf5168d6a69acb2637f0ec629f807d6bd1bb347102d86c9964`
- `release-blocker`: `505c40ab4c92a678ebfd009a91d1ecdd21bc6fe13dc24f66550f60ef3e4f9f62`
- `platform-blocked`: `aaaecec325311bff261091b919216931c528a49281d2f841b722afe183da7fda`
- `resolved-support-case`: `f061bb8de333a888ebc83dce163b7c0f28427d04f1a50fcd16535182119b598e`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
